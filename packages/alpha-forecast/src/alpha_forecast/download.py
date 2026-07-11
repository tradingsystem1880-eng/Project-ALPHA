"""Weight download — the ONLY module in alpha_forecast allowed to touch the network."""

from __future__ import annotations

from typing import TYPE_CHECKING

from alpha_core import DataError
from alpha_forecast.models import resolve_model

if TYPE_CHECKING:
    from pathlib import Path


def pull_model(name: str, weights_dir: Path, *, force: bool = False) -> dict[str, str]:
    """Download the model + tokenizer snapshots into `weights_dir` (HF cache layout).

    Uses the same cache layout `from_pretrained(cache_dir=weights_dir)` reads, then verifies
    by loading both once with local_files_only=True — so a successful pull guarantees a
    later offline load succeeds. Returns {repo_id: snapshot_path}.
    """
    spec = resolve_model(name)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise DataError(
            f"the Kronos torch stack is not installed; run `uv sync --group kronos` first: {exc}"
        ) from exc
    weights_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    for repo in (spec.tokenizer_repo, spec.model_repo):
        try:
            paths[repo] = snapshot_download(
                repo_id=repo,
                cache_dir=str(weights_dir),
                revision=spec.revision,
                force_download=force,
            )
        except Exception as exc:  # noqa: BLE001 - re-raised typed with context
            raise DataError(f"failed to download {repo} into {weights_dir}: {exc}") from exc

    # Verification load: prove the pulled snapshot is loadable offline.
    from alpha_forecast._vendor.kronos import Kronos, KronosTokenizer

    try:
        KronosTokenizer.from_pretrained(
            spec.tokenizer_repo,
            cache_dir=str(weights_dir),
            local_files_only=True,
            revision=spec.revision,
        )
        Kronos.from_pretrained(
            spec.model_repo,
            cache_dir=str(weights_dir),
            local_files_only=True,
            revision=spec.revision,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised typed with context
        raise DataError(
            f"downloaded Kronos-{name} but the offline verification load failed "
            f"(snapshot under {weights_dir} may be incomplete): {exc}"
        ) from exc
    return paths
