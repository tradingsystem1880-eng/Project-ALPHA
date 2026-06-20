"""Prop-firm Monte Carlo: would a strategy pass a funded-trader evaluation, and what would it pay?

QuantPad's prop-firm simulator answers a concrete trader question — *"can this edge clear a
Topstep / Apex / TakeProfitTrader combine, survive the funded phase, and produce payouts?"*
This module is the engine-agnostic core: it resamples a strategy's daily **return** series with
the Politis-Romano stationary bootstrap (the same primitive behind :func:`risk_of_ruin`, so
losing streaks are preserved) and walks each synthetic path through an EVAL → FUNDED → payout
state machine.

**Return-scaled.** Rules are quoted in prop-account dollars (a $50k combine), but the input is a
*return* stream, so any backtest — run at any capital — can be scored against any account size.

**End-of-day granularity (a stated limitation).** Daily bars carry no intraday path, so the
daily-loss limit and the trailing drawdown are evaluated on **end-of-day** balances. Intraday
max-adverse-excursion is invisible; results are an EOD approximation, never an intraday guarantee.

``FIRM_PRESETS`` ships three illustrative 50k-combine presets. Their numbers are **approximate and
fully overridable — NOT authoritative firm terms** (prop-firm rules change often); this is a
research tool, so always confirm against the firm's current contract.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_validation.bootstrap import stationary_bootstrap_indices
from alpha_validation.metrics import FloatArray, FloatSeq


@dataclass(frozen=True)
class PropFirmRules:
    """One prop firm's evaluation + funded rules, in prop-account dollars.

    ``trailing`` drawdown ratchets the bust floor up with the equity high-water mark; with a
    ``lock_at_profit`` the floor stops trailing once profit reaches that buffer (Topstep-style).
    A non-trailing firm uses a static floor at ``account_size - max_drawdown``. ``daily_loss_limit``
    of ``None`` means no daily cap. Validates its invariants on construction (fail loud).
    """

    account_size: float
    profit_target: float
    max_drawdown: float
    trailing: bool
    lock_at_profit: float | None
    daily_loss_limit: float | None
    min_trading_days: int
    profit_split: float
    min_payout: float
    min_funded_days: int
    eval_fee: float

    def __post_init__(self) -> None:
        if self.account_size <= 0.0:
            raise DataError(f"account_size must be > 0, got {self.account_size}")
        if self.profit_target <= 0.0:
            raise DataError(f"profit_target must be > 0, got {self.profit_target}")
        if self.max_drawdown <= 0.0:
            raise DataError(f"max_drawdown must be > 0, got {self.max_drawdown}")
        if self.lock_at_profit is not None and self.lock_at_profit <= 0.0:
            raise DataError(f"lock_at_profit must be None or > 0, got {self.lock_at_profit}")
        if self.daily_loss_limit is not None and self.daily_loss_limit <= 0.0:
            raise DataError(f"daily_loss_limit must be None or > 0, got {self.daily_loss_limit}")
        if self.min_trading_days < 0:
            raise DataError(f"min_trading_days must be >= 0, got {self.min_trading_days}")
        if not 0.0 <= self.profit_split <= 1.0:
            raise DataError(f"profit_split must be in [0, 1], got {self.profit_split}")
        if self.min_payout < 0.0:
            raise DataError(f"min_payout must be >= 0, got {self.min_payout}")
        if self.min_funded_days < 0:
            raise DataError(f"min_funded_days must be >= 0, got {self.min_funded_days}")
        if self.eval_fee < 0.0:
            raise DataError(f"eval_fee must be >= 0, got {self.eval_fee}")


@dataclass(frozen=True)
class PropFirmResult:
    """Monte-Carlo outcome distribution for a strategy against one firm's rules."""

    pass_probability: float  # P(clear the evaluation within the horizon)
    bust_probability: float  # P(breach a limit in the eval OR the funded phase)
    payout_probability: float  # P(take >= 1 funded payout)
    median_days_to_pass: float  # median trading days to pass, over passing paths (NaN if none pass)
    expected_payout: float  # mean trader take ($), net of eval_fee, across all paths
    n_paths: int
    horizon_days: int


def _drawdown_floor(peak: float, rules: PropFirmRules) -> float:
    """The bust floor for a given high-water mark (trailing, optionally locked, or static)."""
    if not rules.trailing:
        return rules.account_size - rules.max_drawdown
    if rules.lock_at_profit is not None:
        peak = min(peak, rules.account_size + rules.lock_at_profit)
    return peak - rules.max_drawdown


def _walk_funded(returns: FloatArray, rules: PropFirmRules) -> tuple[float, bool, bool]:
    """Walk the funded phase for one passing path: ``(total_withdrawn, got_payout, busted)``.

    Same EOD ordering as the eval phase: realise the day's PnL, check the daily-loss limit, mark to
    market, ratchet the trailing floor, then (if eligible) withdraw all profit back to the starting
    balance. A drawdown / daily-loss breach loses the account.
    """
    balance = rules.account_size
    peak = rules.account_size
    funded_days = 0
    withdrawn = 0.0
    got_payout = False
    for r in returns:
        pnl = balance * float(r)
        if rules.daily_loss_limit is not None and pnl <= -rules.daily_loss_limit:
            return withdrawn, got_payout, True
        balance += pnl
        peak = max(peak, balance)
        if balance <= _drawdown_floor(peak, rules):
            return withdrawn, got_payout, True
        funded_days += 1
        profit = balance - rules.account_size
        if profit >= rules.min_payout and funded_days >= rules.min_funded_days:
            withdrawn += profit
            got_payout = True
            balance = rules.account_size
            peak = rules.account_size
            funded_days = 0
    return withdrawn, got_payout, False


def simulate_propfirm(
    daily_returns: FloatSeq,
    rules: PropFirmRules,
    *,
    n_paths: int = 5000,
    mean_block: float = 5.0,
    seed: int | None = None,
) -> PropFirmResult:
    """Estimate pass / bust / payout probabilities for ``daily_returns`` against ``rules``.

    Stationary-bootstraps the daily return series into ``n_paths`` synthetic histories (each the
    length of the input — the strategy's demonstrated track record, reshuffled, no extrapolation),
    then walks each through the EVAL → FUNDED state machine. The evaluation phase is vectorised
    (compound the balance, ratchet the trailing floor, find the first pass/bust day); the funded
    phase is walked per passing path. ``expected_payout`` is the mean trader take across *all* paths
    net of ``eval_fee`` (every path pays the fee to attempt). Fails loud (``DataError``) on fewer
    than 2 finite returns; a flat (no-edge) stream yields all-zero probabilities, NaN
    days-to-pass, and ``-eval_fee`` expected payout (here ``0`` when the fee is ``0``).
    """
    r = np.asarray(daily_returns, dtype=np.float64)
    if r.ndim != 1 or r.size < 2:
        raise DataError(f"simulate_propfirm needs >= 2 returns, got shape {r.shape}")
    if not bool(np.all(np.isfinite(r))):
        raise DataError("simulate_propfirm requires finite returns")

    n = int(r.size)
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(n, mean_block=mean_block, n_resamples=n_paths, rng=rng)
    paths = r[idx]  # (n_paths, n) synthetic daily-return histories

    # --- vectorised evaluation phase ---------------------------------------------------------
    acct = rules.account_size
    growth = np.cumprod(1.0 + paths, axis=1)  # B_t / account_size
    balance = acct * growth
    prev_balance = acct * np.concatenate([np.ones((n_paths, 1)), growth[:, :-1]], axis=1)
    pnl = prev_balance * paths
    peak = np.maximum(np.maximum.accumulate(balance, axis=1), acct)  # high-water mark >= start

    if rules.trailing:
        if rules.lock_at_profit is None:
            capped = peak
        else:
            capped = np.minimum(peak, acct + rules.lock_at_profit)
        floor = capped - rules.max_drawdown
    else:
        floor = np.full_like(balance, acct - rules.max_drawdown)

    bust = balance <= floor
    if rules.daily_loss_limit is not None:
        bust = bust | (pnl <= -rules.daily_loss_limit)

    can_pass = (np.arange(n) + 1) >= rules.min_trading_days
    passed_today = (balance >= acct + rules.profit_target) & can_pass

    first_pass = np.where(passed_today.any(axis=1), passed_today.argmax(axis=1), n)
    first_bust = np.where(bust.any(axis=1), bust.argmax(axis=1), n)
    passed_eval = first_pass < first_bust  # a bust on the same day disqualifies the pass
    busted_eval = (~passed_eval) & (first_bust < n)

    # --- funded phase (only the paths that passed the eval) ----------------------------------
    total_withdrawn = np.zeros(n_paths, dtype=np.float64)
    got_payout = np.zeros(n_paths, dtype=bool)
    funded_busted = np.zeros(n_paths, dtype=bool)
    for i in np.nonzero(passed_eval)[0]:
        p = int(first_pass[i])
        withdrawn, payout_flag, busted = _walk_funded(paths[i, p + 1 :], rules)
        total_withdrawn[i] = withdrawn
        got_payout[i] = payout_flag
        funded_busted[i] = busted

    busted_any = busted_eval | funded_busted
    days_to_pass = (first_pass[passed_eval] + 1).astype(np.float64)
    median = float(np.median(days_to_pass)) if days_to_pass.size else float("nan")
    payout_cash = rules.profit_split * total_withdrawn - rules.eval_fee

    return PropFirmResult(
        pass_probability=float(passed_eval.mean()),
        bust_probability=float(busted_any.mean()),
        payout_probability=float(got_payout.mean()),
        median_days_to_pass=median,
        expected_payout=float(payout_cash.mean()),
        n_paths=n_paths,
        horizon_days=n,
    )


# Illustrative 50k-combine presets. APPROXIMATE and overridable — NOT authoritative firm terms;
# prop-firm contracts change, so verify against the firm before trusting these numbers.
FIRM_PRESETS: dict[str, PropFirmRules] = {
    "topstep": PropFirmRules(
        account_size=50_000.0,
        profit_target=3_000.0,
        max_drawdown=2_000.0,
        trailing=True,
        lock_at_profit=3_000.0,  # trailing floor locks once profit reaches the target buffer
        daily_loss_limit=None,
        min_trading_days=2,
        profit_split=0.90,
        min_payout=1_000.0,
        min_funded_days=5,
        eval_fee=165.0,
    ),
    "apex": PropFirmRules(
        account_size=50_000.0,
        profit_target=3_000.0,
        max_drawdown=2_500.0,
        trailing=True,
        lock_at_profit=None,  # trailing follows the close until the account converts
        daily_loss_limit=None,
        min_trading_days=7,
        profit_split=0.90,
        min_payout=2_000.0,
        min_funded_days=8,
        eval_fee=167.0,
    ),
    "takeprofit": PropFirmRules(
        account_size=50_000.0,
        profit_target=3_000.0,
        max_drawdown=2_000.0,
        trailing=True,
        lock_at_profit=2_000.0,
        daily_loss_limit=1_200.0,  # TPT carries an EOD daily-loss cap
        min_trading_days=5,
        profit_split=0.80,
        min_payout=1_500.0,
        min_funded_days=5,
        eval_fee=150.0,
    ),
}
