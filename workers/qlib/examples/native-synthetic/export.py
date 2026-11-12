"""Export only this immediately preceding synthetic qrun's own trusted artifacts."""

import hashlib
import importlib.metadata
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1]).resolve()
with sqlite3.connect(root / "mlflow.db") as connection:
    connection.row_factory = sqlite3.Row
    runs = list(connection.execute("SELECT run_uuid,status,artifact_uri FROM runs"))
    if len(runs) != 1 or runs[0]["status"] != "FINISHED":
        raise ValueError("one FINISHED native synthetic recorder is required")
    run = dict(runs[0])
    metrics = {
        r["key"]: r["value"] for r in connection.execute("SELECT key,value FROM latest_metrics")
    }
artifacts = Path(run["artifact_uri"]).resolve()
if not artifacts.is_relative_to(root):
    raise ValueError("native artifacts must belong to this fresh local invocation")
pred = pd.read_pickle(artifacts / "pred.pkl")
label = pd.read_pickle(artifacts / "label.pkl")
if not pred.index.equals(label.index) or pred.shape != (128, 1):
    raise ValueError("unexpected native synthetic prediction identities")
flat = (
    pred.join(label)
    .reset_index()
    .rename(columns={"datetime": "session_ts", "instrument": "symbol"})
)
flat["session_ts"] = pd.to_datetime(flat["session_ts"], utc=True)
if not np.isfinite(flat[["score", "synthetic_target"]].to_numpy()).all():
    raise ValueError("native synthetic predictions must be finite")
flat.sort_values(["session_ts", "symbol"]).to_csv(root / "native_predictions.csv", index=False)
daily = pd.DataFrame(
    {
        "ic": pd.read_pickle(artifacts / "sig_analysis/ic.pkl"),
        "rank_ic": pd.read_pickle(artifacts / "sig_analysis/ric.pkl"),
    }
)
daily.rename_axis("session_ts").reset_index().to_csv(
    root / "daily_signal_diagnostics.csv", index=False
)
source = Path(importlib.metadata.distribution("pyqlib").locate_file("qlib/cli/run.py"))
(root / "qrun-result.json").write_text(
    json.dumps(
        {
            "synthetic": True,
            "admission": "not_admitted",
            "recorder": run,
            "metrics": metrics,
            "qlib_version": importlib.metadata.version("pyqlib"),
            "worker_packages": {
                name: importlib.metadata.version(name)
                for name in ("pyqlib", "lightgbm", "numpy", "pandas", "mlflow")
            },
            "qrun_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "qlib_sources_sha256": {
                name: hashlib.sha256(
                    Path(importlib.metadata.distribution("pyqlib").locate_file(name)).read_bytes()
                ).hexdigest()
                for name in (
                    "qlib/cli/run.py",
                    "qlib/model/trainer.py",
                    "qlib/contrib/model/gbdt.py",
                    "qlib/data/dataset/loader.py",
                    "qlib/workflow/record_temp.py",
                )
            },
            "artifacts_sha256": {
                str(p.relative_to(artifacts)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(artifacts.rglob("*"))
                if p.is_file()
            },
        },
        indent=2,
        allow_nan=False,
    )
    + "\n"
)
