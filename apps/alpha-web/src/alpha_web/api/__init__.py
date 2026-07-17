"""Thin JSON routers for the workstation SPA — one module per concern.

Each router wraps the existing filesystem readers (``_runs``) / subprocess helpers
(``_invoke``/``_catalog``/``_candles``/``_workspaces``); no engine runs in the web process.
"""
