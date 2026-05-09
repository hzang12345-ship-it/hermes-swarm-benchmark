"""Tests for hermes_benchmark.report and schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_benchmark.report import (
    load_results,
    main,
    render_markdown,
    write_report,
)
from hermes_benchmark.schema import AgentResult, BenchmarkReport, TestResult


def _write(tmp_path: Path, test: str, agent: str, **overrides: object) -> None:
    base = {
        "agent": agent,
        "test": test,
        "started_at": 1000.0,
        "completed_at": 1001.5,
        "wall_s": 1.5,
        "passed": True,
        "output": f"{agent}-out",
        "error": None,
    }
    base.update(overrides)
    test_dir = tmp_path / test
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / f"{agent}.json").write_text(json.dumps(base))


def test_agent_result_roundtrip() -> None:
    a = AgentResult(
        agent="ALPHA", test="t", started_at=0.0, completed_at=1.0,
        wall_s=1.0, passed=True, output="x",
    )
    assert AgentResult.from_dict(a.to_dict()) == a


def test_test_result_aggregates() -> None:
    agents = [
        AgentResult("A", "t", 0.0, 1.0, 1.0, True),
        AgentResult("B", "t", 0.5, 2.5, 2.0, True),
        AgentResult("C", "t", 0.0, 3.0, 3.0, False),
    ]
    tr = TestResult(name="t", agents=agents)
    assert tr.total == 3
    assert tr.passed == 2
    # wall_s = max(completed_at) - min(started_at) = 3.0 - 0.0
    assert tr.wall_s == pytest.approx(3.0)
    assert tr.throughput == pytest.approx(2 / 3.0)


def test_load_results_full_run(tmp_path: Path) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    _write(tmp_path, "echo_test", "BRAVO", passed=False, error="boom")
    _write(tmp_path, "compute_pi", "ALPHA", wall_s=3.0, completed_at=1003.0)

    report = load_results(tmp_path)
    assert {t.name for t in report.tests} == {"echo_test", "compute_pi"}
    assert report.agent_count == 2
    assert report.grand_total == 3
    assert report.grand_passed == 2


def test_load_results_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_results(tmp_path / "nope")


def test_load_results_invalid_json(tmp_path: Path) -> None:
    test_dir = tmp_path / "bad"
    test_dir.mkdir()
    (test_dir / "ALPHA.json").write_text("{not json")
    with pytest.raises(ValueError):
        load_results(tmp_path)


def test_render_markdown_contains_summary_table(tmp_path: Path) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    _write(tmp_path, "echo_test", "BRAVO", passed=False, error="boom")
    md = render_markdown(load_results(tmp_path), results_dir=tmp_path)
    assert "# Hermes Swarm Benchmark — Report" in md
    assert "## Summary" in md
    assert (
        "| Test | Pass | Total | Wall (s) | Throughput (pass/s) | Status |"
        in md
    )
    assert "ALPHA" in md and "BRAVO" in md


def test_render_markdown_includes_environment_and_run_config(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    md = render_markdown(load_results(tmp_path), results_dir=tmp_path)
    assert "## Run configuration" in md
    assert "## Environment" in md
    # Environment table includes a Python version row.
    assert "| Python |" in md


def test_render_markdown_per_test_detail_section(tmp_path: Path) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    _write(tmp_path, "compute_pi", "BRAVO", wall_s=2.0)
    md = render_markdown(load_results(tmp_path), results_dir=tmp_path)
    assert "## Test: echo_test" in md
    assert "## Test: compute_pi" in md
    # Per-test detail table column header.
    assert (
        "| Agent | Started | Completed | Wall (s) | Passed | Output |" in md
    )


def test_render_markdown_failures_section_lists_each_failure(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    _write(
        tmp_path,
        "echo_test",
        "BRAVO",
        passed=False,
        error="boom\nstack-trace",
        output="last-bytes",
    )
    md = render_markdown(load_results(tmp_path), results_dir=tmp_path)
    assert "## Failures" in md
    assert "echo_test / BRAVO" in md
    assert "boom" in md
    assert "last-bytes" in md
    # Passing agent should NOT show up under Failures.
    assert "echo_test / ALPHA" not in md


def test_render_markdown_failures_section_says_none_when_clean(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    md = render_markdown(load_results(tmp_path), results_dir=tmp_path)
    assert "## Failures" in md
    assert "_None — all agents passed._" in md


def test_render_markdown_reproduce_block_uses_real_test_names(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    _write(tmp_path, "compute_pi", "ALPHA")
    md = render_markdown(load_results(tmp_path), results_dir=tmp_path)
    assert "## Reproduce" in md
    assert "hermes-benchmark --agents" in md
    # Tests are loaded in directory-sorted order, so compute_pi precedes echo_test.
    assert "compute_pi,echo_test" in md
    assert "hermes-benchmark-report" in md


def test_render_markdown_raw_data_pointers(tmp_path: Path) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    md = render_markdown(
        load_results(tmp_path),
        results_dir=tmp_path,
        json_path=tmp_path / "report.json",
    )
    assert "## Raw data" in md
    assert "{test}/{agent}.json" in md
    assert "report.json" in md


def test_render_markdown_status_banner_reflects_outcome(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    md_pass = render_markdown(load_results(tmp_path))
    assert "**PASS**" in md_pass

    _write(tmp_path, "echo_test", "BRAVO", passed=False, error="x")
    md_fail = render_markdown(load_results(tmp_path))
    assert "**FAIL**" in md_fail


def test_render_markdown_pipe_in_output_is_escaped(tmp_path: Path) -> None:
    _write(tmp_path, "echo_test", "ALPHA", output="a|b|c")
    md = render_markdown(load_results(tmp_path))
    # The literal pipe inside output must be escaped so it doesn't break
    # the surrounding Markdown table column boundaries.
    assert "a\\|b\\|c" in md


def test_write_report_creates_files(tmp_path: Path) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    out_md = tmp_path / "out" / "REPORT.md"
    out_json = tmp_path / "out" / "report.json"
    report = write_report(tmp_path, out_md, out_json)
    assert isinstance(report, BenchmarkReport)
    assert out_md.is_file()
    parsed = json.loads(out_json.read_text())
    assert parsed["grand_passed"] == 1
    assert parsed["tests"][0]["name"] == "echo_test"


def test_write_report_markdown_only_when_no_json(tmp_path: Path) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    out_md = tmp_path / "REPORT.md"
    write_report(tmp_path, out_md)
    assert out_md.is_file()
    assert not (tmp_path / "report.json").exists()


def test_write_report_does_not_create_png(tmp_path: Path) -> None:
    """Regression: PNG output must never be produced."""
    _write(tmp_path, "echo_test", "ALPHA")
    out_md = tmp_path / "out" / "REPORT.md"
    write_report(tmp_path, out_md, tmp_path / "out" / "report.json")
    pngs = list((tmp_path / "out").glob("*.png"))
    assert pngs == []


def test_main_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "echo_test", "ALPHA")
    out_md = tmp_path / "REPORT.md"
    rc = main(["--results-dir", str(tmp_path), "--out", str(out_md)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "wrote" in captured.out
    assert out_md.is_file()


def test_main_cli_missing_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--results-dir", str(tmp_path / "nope"), "--out", str(tmp_path / "x.md")])
    assert rc == 2


# ── Manifest-driven population ────────────────────────────────────────────

def _write_manifest(
    tmp_path: Path,
    *,
    agents: list[str],
    tests: list[str],
    orchestrator: str = "none",
    model: str | None = None,
) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "agents": agents,
                "tests": tests,
                "orchestrator": orchestrator,
                "results_dir": str(tmp_path),
                "model": model,
                "created_at": 1000.0,
            }
        )
    )


def test_manifest_populates_orchestrator_and_model(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path, agents=["ALPHA"], tests=["echo_test"],
        orchestrator="2x4", model="claude-opus-4-7",
    )
    _write(tmp_path, "echo_test", "ALPHA")
    report = load_results(tmp_path)
    assert report.orchestrator == "2x4"
    assert report.model == "claude-opus-4-7"
    assert report.agent_count == 1
    md = render_markdown(report, results_dir=tmp_path)
    assert "| Orchestrator | 2x4 |" in md
    assert "| Model | claude-opus-4-7 |" in md


def test_manifest_synthesises_missing_agent_row(tmp_path: Path) -> None:
    _write_manifest(tmp_path, agents=["ALPHA", "BRAVO"], tests=["echo_test"])
    _write(tmp_path, "echo_test", "ALPHA")
    # BRAVO never produced a JSON.
    report = load_results(tmp_path)
    test = report.tests[0]
    agents = {a.agent: a for a in test.agents}
    assert agents["BRAVO"].passed is False
    assert agents["BRAVO"].error == "missing result file"
    md = render_markdown(report, results_dir=tmp_path)
    # Missing row should appear in the per-test detail table.
    assert "| BRAVO " in md
    assert "missing" in md
    assert "_(no result file written)_" in md
    # Failures section should call out the missing row.
    assert "echo_test / BRAVO" in md


def test_manifest_synthesises_missing_test_section(tmp_path: Path) -> None:
    """A test listed in the manifest with NO results still gets a section."""
    _write_manifest(tmp_path, agents=["ALPHA"], tests=["echo_test", "compute_pi"])
    _write(tmp_path, "echo_test", "ALPHA")
    # compute_pi directory absent entirely.
    report = load_results(tmp_path)
    test_names = [t.name for t in report.tests]
    assert "compute_pi" in test_names
    md = render_markdown(report, results_dir=tmp_path)
    assert "## Test: compute_pi" in md
    assert "compute_pi / ALPHA" in md  # Missing row surfaces in failures.


def test_no_manifest_no_results_renders_populated_no_results_report(
    tmp_path: Path,
) -> None:
    """results_dir exists but is empty — populated report, not a stub."""
    report = load_results(tmp_path)
    md = render_markdown(report, results_dir=tmp_path)
    assert "**NO RESULTS**" in md
    assert "## Run configuration" in md
    assert "## Environment" in md
    assert "## Summary" in md
    # Reproduce block should still be present and non-trivial.
    assert "hermes-benchmark --agents" in md
    # No empty placeholders or TBDs leaked through.
    for forbidden in ("TBD", "...\n", "<placeholder>", " | | "):
        assert forbidden not in md


def test_manifest_with_zero_results_still_lists_every_selected_test(
    tmp_path: Path,
) -> None:
    """Worst case: manifest exists, no agent ever wrote a JSON."""
    _write_manifest(
        tmp_path,
        agents=["ALPHA", "BRAVO"],
        tests=["echo_test", "file_io", "compute_pi"],
        orchestrator="1x4",
    )
    report = load_results(tmp_path)
    md = render_markdown(report, results_dir=tmp_path)
    for test in ("echo_test", "file_io", "compute_pi"):
        assert f"## Test: {test}" in md
    # Every (test, agent) pair contributes a missing failure row.
    assert md.count("missing result file") == 6
    assert "**FAIL**" in md
    assert "| Orchestrator | 1x4 |" in md


def test_render_markdown_all_known_tests_populated(tmp_path: Path) -> None:
    """All registered TASKS produce a populated section when present."""
    from hermes_benchmark.tasks import TASKS

    _write_manifest(tmp_path, agents=["ALPHA"], tests=list(TASKS))
    for test in TASKS:
        _write(tmp_path, test, "ALPHA", output=f"{test}-output")
    report = load_results(tmp_path)
    md = render_markdown(report, results_dir=tmp_path)
    for test in TASKS:
        assert f"## Test: {test}" in md
        assert f"{test}-output" in md
    assert "**PASS**" in md


def test_invalid_manifest_raises(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{not json")
    with pytest.raises(ValueError, match="manifest"):
        load_results(tmp_path)


def test_write_report_with_manifest_writes_consistent_json(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path, agents=["ALPHA", "BRAVO"], tests=["echo_test"],
        orchestrator="1x4",
    )
    _write(tmp_path, "echo_test", "ALPHA")
    out_md = tmp_path / "out" / "REPORT.md"
    out_json = tmp_path / "out" / "report.json"
    write_report(tmp_path, out_md, out_json)
    parsed = json.loads(out_json.read_text())
    assert parsed["orchestrator"] == "1x4"
    assert parsed["agent_count"] == 2
    assert parsed["grand_total"] == 2  # ALPHA real + BRAVO missing
    assert parsed["grand_passed"] == 1
