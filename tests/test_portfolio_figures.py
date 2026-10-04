"""Portfolio figures must preserve measured counts and reject altered evidence."""

import copy
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from experiments import benchmark_queries as benchmark
from scripts.build_portfolio_figures import (
    FIGURE_NAMES,
    build_figures,
    validate_accounting,
    validate_benchmark,
)

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "reports" / "20130208"
BENCHMARK = ROOT / "reports" / "benchmarks" / "query-benchmark.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_published_evidence_reconciles_without_rerunning_measurements(monkeypatch):
    def no_measurement(*args, **kwargs):
        pytest.fail(
            "Validation must not time queries, launch workers, or run baselines"
        )

    for name in ("perf_counter", "run_worker", "_launch_worker", "_baseline"):
        monkeypatch.setattr(benchmark, name, no_measurement)
    validate_benchmark(read_json(BENCHMARK))
    validate_accounting(
        read_json(ANALYSIS / "audit.json"), read_json(ANALYSIS / "analysis.json")
    )


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("sizes", [64, 128, 256]),
        ("cycle_sizes", [5, 6, 7]),
        ("repeats", 2),
        ("warmup_queries_per_worker", 0),
    ],
)
def test_benchmark_captions_require_the_recorded_measurement_preset(parameter, value):
    report = read_json(BENCHMARK)
    report["parameters"][parameter] = value
    with pytest.raises(ValueError):
        validate_benchmark(report)


@pytest.mark.parametrize(
    "corruption", ["median", "speedup", "parity", "missing_run", "duplicate_run"]
)
def test_benchmark_validation_rejects_corrupt_summaries_and_runs(corruption):
    report = read_json(BENCHMARK)
    case = report["cases"][0]
    if corruption == "median":
        case["summary"]["baseline"]["wall_seconds"]["median"] *= 2
    elif corruption == "speedup":
        case["speedup_baseline_over_optimized"] *= 2
    elif corruption == "parity":
        case["runs"][0]["selected_nodes_sha256"] = "0" * 64
    elif corruption == "missing_run":
        case["runs"].pop()
    else:
        case["runs"][0] = copy.deepcopy(case["runs"][1])
    with pytest.raises(ValueError):
        validate_benchmark(report)


def test_benchmark_validation_rejects_measurements_assigned_to_the_wrong_size():
    report = read_json(BENCHMARK)
    cases = {c["size"]: c for c in report["cases"] if c["query"] == "root_family"}
    case = cases[512]
    identity = {key: case[key] for key in ("topology", "size", "query")}
    case.update(benchmark.summarize_case(identity, copy.deepcopy(cases[128]["runs"])))

    with pytest.raises(ValueError, match="declared topology and size"):
        validate_benchmark(report)


@pytest.mark.parametrize("field", ["input", "selected_nodes", "selected_nodes_sha256"])
def test_benchmark_validation_rejects_consistently_wrong_case_evidence(field):
    report = read_json(BENCHMARK)
    case = report["cases"][0]
    for run in case["runs"]:
        if field == "input":
            run["input"]["sha256"] = "0" * 64
        elif field == "selected_nodes":
            run[field] -= 1
        else:
            run[field] = "0" * 64
    identity = {key: case[key] for key in ("topology", "size", "query")}
    case.update(benchmark.summarize_case(identity, case["runs"]))

    with pytest.raises(ValueError, match="declared"):
        validate_benchmark(report)


@pytest.mark.parametrize("source", ["benchmark_queries.py", "queries.py"])
def test_benchmark_validation_requires_the_recorded_implementation(source):
    report = read_json(BENCHMARK)
    report["implementation_sha256"][source] = "0" * 64

    with pytest.raises(ValueError, match="recorded implementation"):
        validate_benchmark(report)


@pytest.mark.parametrize("corruption", ["records", "seeds", "overlap", "languages"])
def test_plot_denominators_are_checked(corruption):
    audit, analysis = read_json(ANALYSIS / "audit.json"), read_json(
        ANALYSIS / "analysis.json"
    )
    if corruption == "records":
        audit["projections"]["normalized"]["excluded_assertions"] += 1
    elif corruption == "seeds":
        analysis["projections"]["normalized"]["raw_language_nodes_excluded"] += 1
    elif corruption == "overlap":
        analysis["projections"]["normalized"]["overlaps"][0]["right_only_nodes"] += 1
    else:
        analysis["projections"]["normalized"]["queries"]["ancestors"]["node_languages"][
            "eng"
        ] += 1
    with pytest.raises(ValueError):
        validate_accounting(audit, analysis)


def test_corrupt_benchmark_fails_before_output_creation(tmp_path):
    report = read_json(BENCHMARK)
    report["cases"][0]["summary"]["optimized"]["peak_rss_bytes"]["median"] += 1
    altered = tmp_path / "benchmark.json"
    altered.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="summary"):
        build_figures(ANALYSIS, altered, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_existing_output_is_not_replaced(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("existing work", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_figures(ANALYSIS, BENCHMARK, output)
    assert sentinel.read_text(encoding="utf-8") == "existing work"


def test_direct_script_from_another_directory_renders_verified_pngs(tmp_path):
    output = tmp_path / "figures"
    before = {
        name: hashlib.sha256((ANALYSIS / name).read_bytes()).hexdigest()
        for name in ("manifest.json", "audit.json", "analysis.json")
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_portfolio_figures.py"),
            "--analysis",
            str(ANALYSIS),
            "--benchmark",
            str(BENCHMARK),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    manifest = read_json(output / "manifest.json")
    assert set(manifest["artifacts"]) == set(FIGURE_NAMES)
    assert (
        manifest["input_sha256"]["query-benchmark.json"]
        == hashlib.sha256(BENCHMARK.read_bytes()).hexdigest()
    )
    assert (
        manifest["renderer_sha256"]
        == hashlib.sha256(
            (ROOT / "scripts" / "build_portfolio_figures.py").read_bytes()
        ).hexdigest()
    )
    for name in FIGURE_NAMES:
        contents = (output / name).read_bytes()
        assert contents.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", contents[16:24])
        assert width > 0 and height > 0
        assert manifest["artifacts"][name] == {
            "sha256": hashlib.sha256(contents).hexdigest(),
            "bytes": len(contents),
        }
    assert before == {
        name: hashlib.sha256((ANALYSIS / name).read_bytes()).hexdigest()
        for name in before
    }


def test_same_environment_renders_identical_artifacts(tmp_path):
    first = build_figures(ANALYSIS, BENCHMARK, tmp_path / "first")
    second = build_figures(ANALYSIS, BENCHMARK, tmp_path / "second")
    assert first == second


def test_language_subtitles_render_literal_math_characters(tmp_path, monkeypatch):
    import matplotlib
    from matplotlib.backends.backend_agg import RendererAgg

    from polyphasia.analysis import write_analysis

    language = r"$\invalidcommand$"
    source = tmp_path / "literal-language.tsv"
    source.write_text(
        f"lat: root\trel:etymological_origin_of\t{language}: leaf\n",
        encoding="utf-8",
    )
    run = tmp_path / "run"
    write_analysis(source, run, language=language, input_kind="synthetic")
    rendered = []
    draw_text = RendererAgg.draw_text

    def inspect_text(renderer, gc, x, y, text, prop, angle, ismath=False, mtext=None):
        if language in text:
            assert ismath is False
            rendered.append(text)
        return draw_text(renderer, gc, x, y, text, prop, angle, ismath, mtext)

    monkeypatch.setattr(RendererAgg, "draw_text", inspect_text)
    with matplotlib.rc_context({"text.parse_math": True, "text.usetex": True}):
        manifest = build_figures(run, BENCHMARK, tmp_path / "figures")
        assert matplotlib.rcParams["text.parse_math"] is True
        assert matplotlib.rcParams["text.usetex"] is True
    assert any(f"projected {language} seeds" in text for text in rendered)
    assert set(manifest["artifacts"]) == set(FIGURE_NAMES)


def test_published_figures_match_current_inputs_renderer_and_recorded_hashes():
    directory = ROOT / "docs" / "figures"
    manifest = read_json(directory / "manifest.json")
    inputs = {
        name: ANALYSIS / name
        for name in ("manifest.json", "audit.json", "analysis.json")
    }
    inputs["query-benchmark.json"] = BENCHMARK
    assert manifest["input_sha256"] == {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in inputs.items()
    }
    assert (
        manifest["renderer_sha256"]
        == hashlib.sha256(
            (ROOT / "scripts" / "build_portfolio_figures.py").read_bytes()
        ).hexdigest()
    )
    assert manifest["artifacts"] == {
        name: {
            "sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest(),
            "bytes": (directory / name).stat().st_size,
        }
        for name in FIGURE_NAMES
    }
