# ADR-0028: Govern market state, calibrated Kronos, and Qlib rank ensembles as separate candidates

**Status:** Accepted
**Date:** 2026-08-11
**Deciders:** Project ALPHA owner and AI build agents

## Context

Project ALPHA needs stronger conditional evaluation and candidate modeling without weakening its
point-in-time, fold-local, immutable, and owner-authority boundaries. Market-state diagnostics,
Kronos calibration, and a Qlib ensemble solve different problems; combining them into one tuned
meta-model would add researcher degrees of freedom without evidence that the extra complexity helps.

## Decision

- Add a versioned `MarketStateV1` for calendar-aligned daily universes. Trailing volatility,
  trend, breadth, and correlation state use only information available at each session close.
  Windows, thresholds, universe, benchmark, calendar, and minimum state samples are frozen in the
  experiment contract. Equity and crypto calendars remain separate.
- Add `kronos_calibrated` as an additive candidate. Rolling-origin conformal residual calibration
  and a preregistered convex blend against random walk fit on training/validation folds only and are
  frozen before OOS or holdout. Each validation-origin diagnostic is scored using only its prior
  validation prefix; the contract's minimum validation-origin count is the exact frozen prefix
  length used by the CLI composer. State diagnostics use an explicit pooled fallback when sparse.
- Add Qlib `rank_ensemble_v1` without changing v1 LightGBM exchanges. It combines deterministic
  LightGBM and pinned ridge `LinearModel` members by equal-weight percentile-rank average; member
  predictions and disagreement live in a separate versioned diagnostic artifact.
- Treat market state, Kronos, and Qlib as separate candidate families under the existing evidence
  vocabulary. No cross-model meta-ensemble is authorized.
- Candidate signals become usable only after research promotion inside immutable strategy versions.
  They retain all cost, walk-forward, null, overfitting, holdout, and owner gates and gain no paper
  or order authority.

## Consequences

All schemas and migrations are additive. Existing `kronos`, `lightgbm`, CLI, REST, MCP, SQLite, and
v1 artifacts remain supported. Capability delivery is not evidence of profitable improvement: each
candidate must publish its preregistered hurdle result as passed, rejected, or inconclusive.

## Required verification

Future-poison and availability-time tests cover every state feature and calibration step; fitting
and selection are fold-local; CPU reruns are byte-identical; Kronos reports raw and calibrated
proper scores and coverage; Qlib reports member/ensemble IC, rank-IC, disagreement, turnover, and
net-cost replay. Owner pilot, security review, and distribution-license review remain separate
release gates.
