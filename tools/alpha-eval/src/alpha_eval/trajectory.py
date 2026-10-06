"""Normalize raw SUT event streams (Claude stream-json, Codex --json) into TrajectoryEvents."""

from __future__ import annotations

import json
import re
import shlex
from typing import Any

from alpha_eval.models import TrajectoryEvent

_WORD = re.compile(r"^[a-z][a-z0-9-]*$")
MAX_TEXT = 60_000


def cli_signature(command: str) -> str:
    """'uv run alpha research note add P1 --body x' -> 'cli:research note add'."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for i, tok in enumerate(tokens):
        if tok == "alpha" or tok.endswith("/alpha"):
            words: list[str] = []
            for nxt in tokens[i + 1 :]:
                if len(words) == 3 or not _WORD.match(nxt):
                    break
                words.append(nxt)
            return "cli:" + " ".join(words) if words else "cli:"
    return "bash"


def tool_signature(name: str, args: dict[str, Any]) -> str:
    if name.startswith("mcp__alpha__"):
        return "mcp:" + name.removeprefix("mcp__alpha__")
    if name == "Bash":
        return cli_signature(str(args.get("command", "")))
    if name == "Skill":
        return f"skill:{args.get('skill') or args.get('name') or ''}"
    return name


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                else:
                    parts.append(json.dumps(block)[:2000])
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return json.dumps(content)


class Normalizer:
    """Stateful: feed raw events in order; `events` accumulates normalized ones."""

    def __init__(self) -> None:
        self.events: list[TrajectoryEvent] = []
        self.turn = 0
        self._names: dict[str, tuple[str, str, dict[str, Any]]] = {}

    def _add(self, **kw: Any) -> None:
        text = kw.pop("text", "")
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT] + " …[truncated during normalization; inspect raw stream]"
        self.events.append(TrajectoryEvent(idx=len(self.events), turn=self.turn, text=text, **kw))

    def user(self, text: str) -> None:
        self.turn += 1
        self._add(kind="user", text=text)

    def system(self, text: str) -> None:
        self._add(kind="system", text=text)

    # ---- Claude Code stream-json
    def claude(self, ev: dict[str, Any]) -> None:
        etype = ev.get("type")
        if etype == "assistant":
            for block in ev.get("message", {}).get("content", []):
                btype = block.get("type")
                if btype == "text" and block.get("text", "").strip():
                    self._add(kind="assistant_text", text=block["text"])
                elif btype == "tool_use":
                    name, args = block.get("name", ""), block.get("input", {}) or {}
                    sig = tool_signature(name, args)
                    self._names[block.get("id", "")] = (sig, name, args)
                    self._add(
                        kind="tool_call",
                        tool=sig,
                        raw_tool=name,
                        args=args,
                        call_id=block.get("id", ""),
                        text=json.dumps(args)[:4000],
                    )
        elif etype == "user":
            content = ev.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        cid = block.get("tool_use_id", "")
                        sig, name, _ = self._names.get(cid, ("", "", {}))
                        self._add(
                            kind="tool_result",
                            tool=sig,
                            raw_tool=name,
                            call_id=cid,
                            is_error=bool(block.get("is_error")),
                            text=_content_text(block.get("content", "")),
                        )
        elif etype == "result":
            self._add(
                kind="final",
                text=str(ev.get("result", "") or ""),
                is_error=bool(ev.get("is_error")),
            )

    # ---- Codex exec --json
    def codex(self, ev: dict[str, Any]) -> None:
        etype = ev.get("type", "")
        item = ev.get("item") or {}
        itype = item.get("type") or item.get("item_type") or ""
        if etype == "item.completed" and itype in {"agent_message", "assistant_message"}:
            text = item.get("text", "")
            if text.strip():
                self._add(kind="assistant_text", text=text)
        elif etype in {"item.started", "item.completed"} and itype == "command_execution":
            cmd = item.get("command", "")
            if etype == "item.started":
                self._add(
                    kind="tool_call",
                    tool=cli_signature(cmd),
                    raw_tool="shell",
                    args={"command": cmd},
                    call_id=item.get("id", ""),
                    text=cmd,
                )
            else:
                self._add(
                    kind="tool_result",
                    tool=cli_signature(cmd),
                    raw_tool="shell",
                    call_id=item.get("id", ""),
                    is_error=item.get("exit_code") not in (0, None),
                    text=str(item.get("aggregated_output", "")),
                )
        elif etype in {"item.started", "item.completed"} and itype == "mcp_tool_call":
            tool = f"mcp:{item.get('tool', '')}"
            if etype == "item.started":
                args = item.get("arguments") or {}
                self._add(
                    kind="tool_call",
                    tool=tool,
                    raw_tool=str(item.get("tool", "")),
                    args=args if isinstance(args, dict) else {"raw": args},
                    call_id=item.get("id", ""),
                    text=json.dumps(args)[:4000],
                )
            else:
                result = item.get("result") or item.get("error") or ""
                self._add(
                    kind="tool_result",
                    tool=tool,
                    raw_tool=str(item.get("tool", "")),
                    call_id=item.get("id", ""),
                    is_error=bool(item.get("error")),
                    text=_content_text(
                        result.get("content", result) if isinstance(result, dict) else result
                    ),
                )
        elif etype in {"item.started", "item.completed"} and itype in {
            "web_search",
            "file_change",
            "collab_tool_call",
        }:
            self._add(
                kind="tool_call" if etype == "item.started" else "tool_result",
                tool=itype,
                raw_tool=itype,
                call_id=item.get("id", ""),
                args={"action": item.get("action", {}), "changes": item.get("changes", [])},
                text=json.dumps(item),
                is_error=item.get("status") == "failed",
            )
        elif etype == "item.completed" and itype not in {"reasoning", "todo_list"}:
            self.system("Unclassified Codex event (evidence retained): " + json.dumps(item))
        elif etype in {"error", "turn.failed"}:
            self._add(kind="system", text=json.dumps(ev), is_error=True)
        elif etype == "turn.completed":
            last = next((e.text for e in reversed(self.events) if e.kind == "assistant_text"), "")
            self._add(kind="final", text=last)
