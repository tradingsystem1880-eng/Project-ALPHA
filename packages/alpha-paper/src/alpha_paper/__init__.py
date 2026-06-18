"""Project ALPHA paper-trading package (Phase 4): sandbox sessions + run artifacts."""

from __future__ import annotations

from alpha_paper.artifacts import (
    AuditLog,
    new_session_id,
    read_session,
    session_dir,
    write_equity_curve,
    write_session,
)
from alpha_paper.config import PaperSpec, paper_spec_from_settings
from alpha_paper.errors import PaperError
from alpha_paper.node import build_paper_node, run_node_for
from alpha_paper.reconcile import Reconciliation, realized_slippage_bps, reconcile

__version__ = "0.0.0"

__all__ = [
    "AuditLog",
    "PaperError",
    "PaperSpec",
    "Reconciliation",
    "build_paper_node",
    "new_session_id",
    "paper_spec_from_settings",
    "read_session",
    "realized_slippage_bps",
    "reconcile",
    "run_node_for",
    "session_dir",
    "write_equity_curve",
    "write_session",
    "__version__",
]
