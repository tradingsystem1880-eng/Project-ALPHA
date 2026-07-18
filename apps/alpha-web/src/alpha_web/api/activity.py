"""``/api/activity/stream`` — the live-desk SSE feed of run-store + job changes.

One polling generator per connection (see ``_activity``); sse-starlette's built-in ping keeps the
connection alive through quiet stretches.
"""

from __future__ import annotations

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from alpha_web import _activity
from alpha_web.api._common import data_dir

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activity/stream")
async def stream_activity(poll: float = 1.5, max_events: int | None = None) -> EventSourceResponse:
    """SSE: ``snapshot``, then ``run_added/run_updated`` + ``job_*`` diffs each poll tick.

    ``max_events`` bounds the stream for tests/diagnostics; browsers omit it and stream forever.
    """
    interval = _activity.clamp_poll(poll)
    return EventSourceResponse(
        _activity.activity_events(data_dir(), poll=interval, max_events=max_events)
    )
