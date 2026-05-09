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

from .schema import AgentResult, BenchmarkReport, TestResult


def load_results(results_dir: Path) -> BenchmarkReport:
    """Load all result JSONs from ``results_dir/{test}/{agent}.json``."""

    if not results_dir.exists():
        raise FileNotFoundError(f"results_dir does not exist: {results_dir}")
    if not results_dir.is_dir():
        raise NotADirectoryError(f"results_dir is not a directory: {results_dir}")

    tests: list[TestResult] = []
    for test_dir in sorted(p for p in results_dir.iterdir() if p.is_dir()):
        agents: list[AgentResult] = []
        for agent_file in sorted(test_dir.glob("*.json")):
            try:
                data = json.loads(agent_file.read_text())
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {agent_file}: {exc}") from exc
            agents.append(AgentResult.from_dict(data))
        if agents:
            tests.append(TestResult(name=test_dir.name, agents=agents))

    agent_count = max((t.total for t in tests), default=0)
    return BenchmarkReport(tests=tests, agent_count=agent_count)


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
    status = "PASS" if report.grand_passed == report.grand_total and report.grand_total else "FAIL"
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
    for t in report.tests:
        mark = "✓" if t.passed == t.total else "✗"
        lines.append(
            f"| {t.name} | {t.passed} | {t.total} | "
            f"{t.wall_s:.3f} | {t.throughput:.3f} | {mark} |"
        )
    lines.append(
        f"| **Total** | **{report.grand_passed}** | **{report.grand_total}** | "
        f"**{report.grand_wall_s:.3f}** | — | "
        f"**{'✓' if status == 'PASS' else '✗'}** |"
    )
    lines.append("")

    # ── Per-test detail ────────────────────────────────────────────────
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
            mark = "✓" if a.passed else "✗"
            output_cell = (a.output or "").replace("|", "\\|").replace("\n", " ⏎ ")
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
    if not failures:
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
    lines.append("```bash")
    lines.append(
        f"hermes-benchmark --agents {report.agent_count} "
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
