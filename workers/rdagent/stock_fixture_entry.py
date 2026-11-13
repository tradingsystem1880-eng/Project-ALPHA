"""Explicit subprocess entry: fixed synthetic inputs, pinned upstream, no external effects."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.abc
import importlib.machinery
import json
import os
import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Literal, TypedDict, cast


def offline(event: str, args: tuple[object, ...]) -> None:
    if (
        event == "subprocess.Popen"
        and len(args) > 1
        and isinstance(args[0], str | bytes)
        and isinstance(args[1], (list, tuple))
        and (
            (os.fsdecode(args[0]) == "uname" and tuple(args[1]) == ("uname", "-p"))
            or (
                os.fsdecode(args[0]) == "/sbin/ldconfig"
                and tuple(args[1]) == ("/sbin/ldconfig", "-p")
            )
        )
    ):
        return  # Standard-library metadata during pinned installed dependency imports.
    if event in {
        "socket.connect",
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.sendto",
        "socket.bind",
        "subprocess.Popen",
        "os.system",
    }:
        raise RuntimeError("stock fixture external effect denied")
    if event == "open" and args and isinstance(args[0], str | bytes):
        p = Path(os.fsdecode(args[0]))
        if (
            {".codex", ".aws", ".ssh", ".azure"}.intersection(p.parts)
            or p.name
            in {"auth.json", "credentials", ".env", "application_default_credentials.json"}
            or p.name.startswith(".env.")
        ):
            raise RuntimeError("stock fixture credential read denied")


class SourceFinder(importlib.abc.MetaPathFinder):
    def __init__(self, source: Path) -> None:
        self.source = source

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname == "rdagent":
            spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [str(self.source / "rdagent")]
            return spec
        if fullname.startswith("rdagent."):
            return importlib.machinery.PathFinder.find_spec(
                fullname, [str(self.source.joinpath(*fullname.split(".")[:-1]))]
            )
        return None


class StockRequest(TypedDict):
    schema: Literal["StockRDLoopFixtureRequestV1"]
    job_id: str
    reservation_id: str
    owner_id: str
    spec_sha256: str
    manifest_sha256: str
    loop_steps: Literal[5]
    model_calls: Literal[2]
    tool_calls: Literal[2]
    cpu_milliseconds: int
    mode: Literal["resume", "cancel", "exhaust", "tamper"]


def parse_request(raw: bytes) -> StockRequest:
    if len(raw) > 8192:
        raise ValueError("stock request exceeds bound")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for k, v in items:
            if k in value:
                raise ValueError("duplicate request key")
            value[k] = v
        return value

    request = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(request, dict):
        raise ValueError("stock request must be an object")
    if (
        set(request)
        != {
            "schema",
            "job_id",
            "reservation_id",
            "owner_id",
            "spec_sha256",
            "manifest_sha256",
            "loop_steps",
            "model_calls",
            "tool_calls",
            "cpu_milliseconds",
            "mode",
        }
        or request["schema"] != "StockRDLoopFixtureRequestV1"
        or type(request["mode"]) is not str
        or request["mode"] not in {"resume", "cancel", "exhaust", "tamper"}
    ):
        raise ValueError("invalid closed stock request")
    if (
        any(
            type(request[k]) is not int or request[k] != v
            for k, v in {"loop_steps": 5, "model_calls": 2, "tool_calls": 2}.items()
        )
        or type(request["cpu_milliseconds"]) is not int
        or not 0 < request["cpu_milliseconds"] <= 60_000
    ):
        raise ValueError("invalid stock fixture budget")
    if any(
        type(request[k]) is not str or not request[k] or len(request[k]) > 200
        for k in ("job_id", "reservation_id", "owner_id")
    ):
        raise ValueError("invalid stock identity")
    if any(
        type(request[k]) is not str
        or len(request[k]) != 64
        or any(c not in "0123456789abcdef" for c in request[k])
        for k in ("spec_sha256", "manifest_sha256")
    ):
        raise ValueError("invalid stock fingerprint")
    # Every closed field/type/range is validated above before this typed boundary.
    return cast(StockRequest, request)


def main() -> None:
    root = Path.cwd()
    supervised = len(sys.argv) == 4 and sys.argv[2] == "supervised"
    if supervised:
        if (
            root.parent.parent != Path("/tmp")
            or not root.parent.name.startswith("alpha-native-fixture-")
            or root.name.find("payload-") != 0
            or (root.parent / "synthetic-only").read_text()
            != "ALPHA synthetic native lifecycle v1\n"
            or any(root.iterdir())
        ):
            raise ValueError("supervised stock fixture workspace is invalid")
    elif (
        root.parent != Path("/tmp")
        or not root.name.startswith("alpha-stock-rdloop-")
        or any(root.iterdir())
    ):
        raise ValueError("stock fixture requires a new empty temporary workspace")
    raw = sys.argv[3].encode() if supervised else sys.stdin.buffer.read(8193)
    request = parse_request(raw)
    # Defense in depth: callers cannot import native settings from inherited secrets.
    os.environ.clear()
    os.environ.update(
        {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "HOME": str(root),
            "TMPDIR": str(root),
            "LOG_TRACE_PATH": str(root / "logs"),
            "ARTIFACT_SIGNING_KEY": "synthetic-public-test-material-0000000000000000",
            "ARTIFACT_SIGNING_KEY_PATH": str(root / "synthetic.key"),
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "STEP_SEMAPHORE": "1",
            "SUBPROC_STEP": "False",
            "ENABLE_MLFLOW": "False",
        }
    )
    if supervised and root.name != "payload-" + request["job_id"]:
        raise ValueError("stock request workspace/job mismatch")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    worker = Path(__file__).resolve().parent
    manifest = {
        name: hashlib.sha256((worker / name).read_bytes()).hexdigest()
        for name in ("stock_fixture.py", "stock_fixture_entry.py", "source_pin.py")
    }
    if (
        hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        != request["manifest_sha256"]
    ):
        raise ValueError("stock fixture worker changed after request")
    from source_pin import verify_source

    source = Path(sys.argv[1])
    if source.is_symlink() or source != source.resolve():
        raise ValueError("unsafe stock source")
    verify_source(source)
    sys.meta_path.insert(0, SourceFinder(source))
    sys.addaudithook(offline)
    with redirect_stdout(sys.stderr):
        from rdagent.core.conf import RD_AGENT_SETTINGS

        if (
            RD_AGENT_SETTINGS.step_semaphore != 1
            or RD_AGENT_SETTINGS.subproc_step
            or RD_AGENT_SETTINGS.enable_mlflow
        ):
            raise ValueError("stock fixture native concurrency configuration is unsafe")
        from stock_fixture import run

        result = asyncio.run(run(request))
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
