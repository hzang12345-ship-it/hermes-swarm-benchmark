"""Render benchmark results to Markdown / JSON.

Reads result JSONs written by sub-agents (one per ``{test}/{agent}.json``)
and emits the primary artifact, a polished Markdown report (``REPORT.md``).
A structured JSON copy can be written alongside it via ``--json``.

Markdown is the default and only first-class output. PNG chart generation
was removed in PR #1: it relied on a brittle PIL path with hard-coded font
locations, did not diff cleanly in PRs, and bundled a runtime dependency
purely for screenshots. If a chart is needed, run a separate plotting tool
against ``report.json``.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .schema import (
    AgentResult,
    BenchmarkReport,
    MISSING_RESULT_ERROR,
    RunManifest,
    TestResult,
    synthesize_missing,
)

MANIFEST_FILENAME = "manifest.json"


def _load_manifest(results_dir: Path) -> RunManifest | None:
    """Read ``results_dir/manifest.json`` if it exists, else None."""
    path = results_dir / MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        return RunManifest.from_dict(json.loads(path.read_text()))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"invalid manifest in {path}: {exc}") from exc


def load_results(results_dir: Path) -> BenchmarkReport:
    """Load all result JSONs from ``results_dir/{test}/{agent}.json``.

    If a ``manifest.json`` is present, it is used to (a) populate
    orchestrator/model/agent_count metadata in the report, and (b)
    synthesise explicit failure rows for any (test, agent) pair the user
    selected but for which no result JSON exists. This keeps the rendered
    Markdown report fully populated for every selected configuration.
    """

    if not results_dir.exists():
        raise FileNotFoundError(f"results_dir does not exist: {results_dir}")
    if not results_dir.is_dir():
        raise NotADirectoryError(f"results_dir is not a directory: {results_dir}")

    manifest = _load_manifest(results_dir)

    # Discover tests from disk: any subdirectory containing JSON files.
    found: dict[str, list[AgentResult]] = {}
    for test_dir in sorted(p for p in results_dir.iterdir() if p.is_dir()):
        agents: list[AgentResult] = []
        for agent_file in sorted(test_dir.glob("*.json")):
            try:
                data = json.loads(agent_file.read_text())
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {agent_file}: {exc}") from exc
            agents.append(AgentResult.from_dict(data))
        if agents:
            found[test_dir.name] = agents

    # Union of disk-discovered tests and manifest-declared tests, sorted to
    # keep report ordering stable.
    test_names: list[str] = sorted(
        set(found) | (set(manifest.tests) if manifest else set())
    )

    tests: list[TestResult] = []
    for test_name in test_names:
        present = found.get(test_name, [])
        present_agents = {a.agent for a in present}
        expected_agents = list(manifest.agents) if manifest else []
        synthesised = [
            synthesize_missing(test_name, agent)
            for agent in expected_agents
            if agent not in present_agents
        ]
        merged = sorted(present + synthesised, key=lambda a: a.agent)
        # Always include a TestResult for each manifest-declared test, even
        # if no agents were expected — the user must see one row per
        # selected test in the report.
        if merged or test_name in (manifest.tests if manifest else []):
            tests.append(TestResult(name=test_name, agents=merged))

    if manifest is not None:
        agent_count = len(manifest.agents)
        orchestrator = manifest.orchestrator
        model = manifest.model
    else:
        agent_count = max((t.total for t in tests), default=0)
        orchestrator = "none"
        model = None

    return BenchmarkReport(
        tests=tests,
        agent_count=agent_count,
        orchestrator=orchestrator,
        model=model,
    )


def _environment_block() -> dict[str, str]:
    return {
        "Python": sys.version.split()[0],
        "Platform": platform.platform(),
        "Machine": platform.machine() or "unknown",
        "Generated at (UTC)": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    }


def render_markdown(
    report: BenchmarkReport,
    *,
    results_dir: Path | None = None,
    json_path: Path | None = None,
) -> str:
    """Render a BenchmarkReport as a polished Markdown document."""

    lines: list[str] = []
    lines.append("# Hermes Swarm Benchmark — Report")
    lines.append("")

    pct = (
        100.0 * report.grand_passed / report.grand_total
        if report.grand_total
        else 0.0
    )
    if report.grand_total == 0:
        status = "NO RESULTS"
    elif report.grand_passed == report.grand_total:
        status = "PASS"
    else:
        status = "FAIL"
    lines.append(
        f"**{status}** — {report.grand_passed}/{report.grand_total} agents passed "
        f"({pct:.1f}%) in {report.grand_wall_s:.3f}s wall time."
    )
    lines.append("")

    # ── Run configuration ──────────────────────────────────────────────
    lines.append("## Run configuration")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Agent count | {report.agent_count} |")
    lines.append(f"| Orchestrator | {report.orchestrator} |")
    if report.model:
        lines.append(f"| Model | {report.model} |")
    lines.append(f"| Tests run | {len(report.tests)} |")
    lines.append("")

    # ── Environment ────────────────────────────────────────────────────
    lines.append("## Environment")
    lines.append("")
    lines.append("| Key | Value |")
    lines.append("|---|---|")
    for k, v in _environment_block().items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    # ── Summary table ──────────────────────────────────────────────────
    lines.append("## Summary")
    lines.append("")
    lines.append("| Test | Pass | Total | Wall (s) | Throughput (pass/s) | Status |")
    lines.append("|---|---:|---:|---:|---:|:-:|")
    if report.tests:
        for t in report.tests:
            mark = "✓" if t.total and t.passed == t.total else "✗"
            lines.append(
                f"| {t.name} | {t.passed} | {t.total} | "
                f"{t.wall_s:.3f} | {t.throughput:.3f} | {mark} |"
            )
    else:
        lines.append("| _no tests_ | 0 | 0 | 0.000 | 0.000 | — |")
    lines.append(
        f"| **Total** | **{report.grand_passed}** | **{report.grand_total}** | "
        f"**{report.grand_wall_s:.3f}** | — | "
        f"**{'✓' if status == 'PASS' else '✗'}** |"
    )
    lines.append("")

    # ── Per-test detail ────────────────────────────────────────────────
    if not report.tests:
        lines.append("## Test results")
        lines.append("")
        lines.append(
            "_No result JSONs were found and no manifest declared any "
            "expected tests. Run `hermes-benchmark` first to write a "
            "manifest, then have the OMEGA orchestrator execute the goal._"
        )
        lines.append("")
    for t in report.tests:
        lines.append(f"## Test: {t.name}")
        lines.append("")
        lines.append(
            f"_{t.passed}/{t.total} passed — wall {t.wall_s:.3f}s — "
            f"throughput {t.throughput:.3f} pass/s_"
        )
        lines.append("")
        lines.append("| Agent | Started | Completed | Wall (s) | Passed | Output |")
        lines.append("|---|---:|---:|---:|:-:|---|")
        for a in t.agents:
            if a.error == MISSING_RESULT_ERROR:
                mark = "missing"
            else:
                mark = "✓" if a.passed else "✗"
            output_cell = (a.output or "").replace("|", "\\|").replace("\n", " ⏎ ")
            if not output_cell and a.error == MISSING_RESULT_ERROR:
                output_cell = "_(no result file written)_"
            if len(output_cell) > 80:
                output_cell = output_cell[:77] + "..."
            lines.append(
                f"| {a.agent} | {a.started_at:.3f} | {a.completed_at:.3f} | "
                f"{a.wall_s:.3f} | {mark} | {output_cell} |"
            )
        lines.append("")

    # ── Failures ───────────────────────────────────────────────────────
    failures: list[tuple[str, AgentResult]] = []
    for t in report.tests:
        for a in t.agents:
            if not a.passed:
                failures.append((t.name, a))

    lines.append("## Failures")
    lines.append("")
    if not failures and report.grand_total == 0:
        lines.append("_No agent results were collected — see above._")
    elif not failures:
        lines.append("_None — all agents passed._")
    else:
        lines.append(f"{len(failures)} agent run(s) failed:")
        lines.append("")
        for test_name, a in failures:
            lines.append(f"### {test_name} / {a.agent}")
            lines.append("")
            err = a.error or "(no error message)"
            lines.append("```")
            lines.append(err)
            lines.append("```")
            if a.output:
                lines.append("")
                lines.append("Last output:")
                lines.append("")
                lines.append("```")
                lines.append(a.output)
                lines.append("```")
            lines.append("")
    lines.append("")

    # ── Reproduce ──────────────────────────────────────────────────────
    lines.append("## Reproduce")
    lines.append("")
    test_arg = ",".join(t.name for t in report.tests) or "echo_test"
    repro_agents = report.agent_count if report.agent_count > 0 else 1
    lines.append("```bash")
    lines.append(
        f"hermes-benchmark --agents {repro_agents} "
        f"--tests {test_arg} --orchestrator {report.orchestrator}"
    )
    if results_dir is not None:
        lines.append(
            f"hermes-benchmark-report --results-dir {results_dir} "
            "--out REPORT.md --json report.json"
        )
    else:
        lines.append("hermes-benchmark-report --out REPORT.md --json report.json")
    lines.append("```")
    lines.append("")

    # ── Raw data pointers ──────────────────────────────────────────────
    lines.append("## Raw data")
    lines.append("")
    if results_dir is not None:
        lines.append(
            f"- Per-agent JSON: `{results_dir}/{{test}}/{{agent}}.json`"
        )
    else:
        lines.append("- Per-agent JSON: `<results-dir>/{test}/{agent}.json`")
    if json_path is not None:
        lines.append(f"- Aggregated JSON: `{json_path}`")
    else:
        lines.append(
            "- Aggregated JSON: pass `--json report.json` to the report command."
        )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_report(
    results_dir: Path,
    out_md: Path,
    out_json: Path | None = None,
) -> BenchmarkReport:
    """Load + render a report. Returns the loaded BenchmarkReport."""
    report = load_results(results_dir)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        render_markdown(report, results_dir=results_dir, json_path=out_json)
    )
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report.to_dict(), indent=2))
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render Hermes Swarm Benchmark results as Markdown."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("/tmp/bench_results"),
        help="Directory containing {test}/{agent}.json files.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("REPORT.md"),
        help="Markdown output path (default: REPORT.md).",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        report = write_report(args.results_dir, args.out, args.json)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"wrote {args.out} "
        f"({report.grand_passed}/{report.grand_total} passed, "
        f"wall={report.grand_wall_s:.3f}s)"
    )
    if args.json:
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
