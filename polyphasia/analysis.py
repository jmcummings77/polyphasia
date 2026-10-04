"""Reproduce an audit, query comparison, rankings, and source-traced examples.

Run with the optional analysis environment: ``python -m polyphasia.analysis
INPUT.tsv --output NEW_DIRECTORY``. The original TSV remains the evidence source.
"""

import argparse
import hashlib
import json
import logging
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from polyphasia.analysis_artifacts import write_figures, write_tables
from polyphasia.analysis_metrics import analysis_parameters, analyze_assertions
from polyphasia.assertions import prepare_assertions
from polyphasia.audit import audit_assertions
from polyphasia.loader import load_to_pandas

logger = logging.getLogger(__name__)
IMPLEMENTATION_FILES = (
    "analysis.py",
    "analysis_artifacts.py",
    "analysis_metrics.py",
    "audit.py",
    "assertions.py",
    "queries.py",
    "loader.py",
    "constants.py",
)
ARTIFACTS = (
    "audit.json",
    "analysis.json",
    "queries.csv",
    "overlaps.csv",
    "rankings.csv",
    "figures/retention.png",
    "figures/query-comparison.png",
    "figures/rankings.png",
)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _implementation_hashes() -> dict[str, str]:
    return {
        name: _sha256(Path(__file__).with_name(name)) for name in IMPLEMENTATION_FILES
    }


def _git_state() -> dict[str, Any]:
    """Identify the source checkout, never an unrelated caller's repository."""
    root = Path(__file__).resolve().parent.parent
    unavailable = {"revision": None, "dirty": None}
    try:

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", "-C", str(root), *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()

        if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
            return unavailable
        return {
            "revision": git("rev-parse", "HEAD"),
            "dirty": bool(git("status", "--porcelain", "--untracked-files=normal")),
        }
    except (OSError, subprocess.SubprocessError):
        return unavailable


def _peak_rss_bytes() -> int | None:
    if sys.platform not in {"darwin", "linux"}:
        return None
    import resource

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform == "darwin" else rss * 1024)


def validate_run(output: Path) -> dict[str, Any]:
    """Check a completed run's artifact sizes and hashes; return its manifest.

    Checksums detect modification relative to this manifest, not authenticity.
    No source TSV, installed implementation, or external URL is trusted/fetched.
    """
    root = Path(output).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("workflow") != "analysis"
    ):
        raise ValueError("Unsupported analysis manifest")
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict) or set(artifacts) != set(ARTIFACTS):
        raise ValueError("Manifest must account for every analysis artifact")
    for name, metadata in artifacts.items():
        if not isinstance(metadata, dict) or not {"bytes", "sha256"} <= metadata.keys():
            raise ValueError(f"Incomplete artifact metadata: {name}")
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Artifact leaves the run directory: {name}")
        if (
            path.stat().st_size != metadata["bytes"]
            or _sha256(path) != metadata["sha256"]
        ):
            raise ValueError(f"Artifact checksum/size mismatch: {name}")
    return manifest


def write_analysis(
    source: Path,
    output: Path,
    *,
    language: str = "eng",
    policies: tuple[str, ...] = ("root_only", "normalized"),
    top_n: int = 10,
    trace_words: tuple[str, ...] = (),
    trace_max_depth: int = 8,
    trace_max_nodes: int = 1000,
    source_url: str | None = None,
    dataset_version: str | None = None,
    input_kind: str = "unspecified",
    input_description: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Publish a new, complete run directory; never replace an existing run.

    Deterministic analytical artifacts are separate from execution provenance.
    Full graphs are constructed sequentially by the audit and analysis. The
    original input plus its checksum identify every sampled assertion ordinal.
    """
    started = perf_counter()
    source, output = Path(source), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output directory already exists: {output}")
    if input_kind not in {"synthetic", "full", "extract", "unspecified"}:
        raise ValueError("input_kind must be synthetic, full, extract, or unspecified")
    parameters = analysis_parameters(
        language=language,
        policies=policies,
        top_n=top_n,
        trace_words=trace_words,
        trace_max_depth=trace_max_depth,
        trace_max_nodes=trace_max_nodes,
    )
    # Import before the costly corpus work so missing optional dependencies fail early.
    try:
        import matplotlib
    except ImportError as exc:
        raise ValueError(
            "Install polyphasia[analysis] to render analysis figures"
        ) from exc
    input_hash = _sha256(source)
    if expected_sha256 is not None and input_hash != expected_sha256:
        raise ValueError("Input SHA-256 does not match the expected pinned input")
    source_bytes = source.stat().st_size
    implementation = _implementation_hashes()
    git = _git_state()
    logger.info("Loading and validating %s", source)
    assertions = prepare_assertions(load_to_pandas(source))
    if _sha256(source) != input_hash:
        raise ValueError("Input changed while loading; rerun with a stable file")
    logger.info("Auditing %s assertions", len(assertions))
    audit = audit_assertions(assertions)
    logger.info("Comparing graph policies and queries")
    report = analyze_assertions(
        assertions,
        **{
            key: value
            for key, value in parameters.items()
            if key != "trace_evidence_limit"
        },
    )
    del assertions
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        staging = Path(temporary)
        _write_json(staging / "audit.json", audit)
        _write_json(staging / "analysis.json", report)
        write_tables(report, staging)
        write_figures(audit, report, staging)
        if _sha256(source) != input_hash:
            raise ValueError("Input changed during analysis; rerun with a stable file")
        if _implementation_hashes() != implementation:
            raise ValueError(
                "Implementation changed during analysis; rerun with stable code"
            )
        manifest = {
            "schema_version": 1,
            "workflow": "analysis",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input": {
                "path": str(source),
                "sha256": input_hash,
                "bytes": source_bytes,
                "source_url": source_url,
                "dataset_version": dataset_version,
                "kind": input_kind,
                "description": input_description,
            },
            "git": git,
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                **{
                    name: version(name)
                    for name in ("polyphasia", "pandas", "networkx", "numpy")
                },
                "matplotlib": matplotlib.__version__,
            },
            "implementation_sha256": implementation,
            "parameters": report["parameters"],
            "policies": {
                p: r["policy_version"] for p, r in report["projections"].items()
            },
            "assertion_id_definition": "1-based nonblank parsed record ordinal in input SHA-256",
            "execution": {
                "wall_seconds": round(perf_counter() - started, 6),
                "peak_rss_bytes": _peak_rss_bytes(),
                "scope": "Elapsed workflow through artifact rendering and input/code verification, before manifest writing; RSS is process lifetime high-water including interpreter/imports, not incremental allocation; unsupported RSS platforms report null",
            },
            "artifacts": {
                name: {
                    "sha256": _sha256(staging / name),
                    "bytes": (staging / name).stat().st_size,
                }
                for name in ARTIFACTS
            },
        }
        _write_json(staging / "manifest.json", manifest)
        validate_run(staging)
        # Reserve the destination exclusively, including when another process
        # created it while this run was computing. Manifest is copied last.
        output.mkdir(exist_ok=False)
        for name in (*ARTIFACTS, "manifest.json"):
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            (staging / name).replace(destination)
    logger.info("Completed verified run at %s", output)
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--language", default="eng")
    parser.add_argument(
        "--policies",
        nargs="+",
        choices=("root_only", "normalized"),
        default=("root_only", "normalized"),
    )
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument(
        "--word", action="append", default=[], help="Exact label to trace; repeatable"
    )
    parser.add_argument("--trace-max-depth", type=int, default=8)
    parser.add_argument("--trace-max-nodes", type=int, default=1000)
    parser.add_argument("--source-url")
    parser.add_argument("--dataset-version")
    parser.add_argument(
        "--input-kind",
        choices=("synthetic", "full", "extract", "unspecified"),
        default="unspecified",
    )
    parser.add_argument("--input-description")
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    try:
        report = write_analysis(
            args.source,
            args.output,
            language=args.language,
            policies=tuple(args.policies),
            top_n=args.top_n,
            trace_words=tuple(args.word),
            trace_max_depth=args.trace_max_depth,
            trace_max_nodes=args.trace_max_nodes,
            source_url=args.source_url,
            dataset_version=args.dataset_version,
            input_kind=args.input_kind,
            input_description=args.input_description,
            expected_sha256=args.expected_sha256,
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Analysis failed: {exc}\n")
    print(f"Analyzed {report['input']['assertions']} assertions into {args.output}")


if __name__ == "__main__":
    main()
