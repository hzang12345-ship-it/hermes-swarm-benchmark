"""Render benchmark results to Markdown / JSON.

Reads result JSONs written by sub-agents (one per ``{test}/{agent}.json``)
and emits two artifacts:

* ``REPORT.md`` — a Markdown report (default)
* ``report.json`` — the same data as a structured JSON document

PNG charts are intentionally not produced here; the previous PIL-based path
was broken and Markdown renders fine in PR reviews and GitHub README.
"""

from __future__ import annotations

import argparse
import json
import sys
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


def render_markdown(report: BenchmarkReport) -> str:
    """Render a BenchmarkReport as Markdown."""

    lines: list[str] = []
    lines.append("# Hermes Swarm Benchmark — Report")
    lines.append("")
    lines.append(f"- Agent count: **{report.agent_count}**")
    lines.append(f"- Orchestrator: **{report.orchestrator}**")
    if report.model:
        lines.append(f"- Model: **{report.model}**")
    lines.append(
        f"- Grand total: **{report.grand_passed}/{report.grand_total} passed** "
        f"in **{report.grand_wall_s:.3f}s** wall time"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Test | Pass | Total | Wall (s) | Throughput (pass/s) |")
    lines.append("|---|---:|---:|---:|---:|")
    for t in report.tests:
        lines.append(
            f"| {t.name} | {t.passed} | {t.total} | "
            f"{t.wall_s:.3f} | {t.throughput:.3f} |"
        )
    lines.append("")

    for t in report.tests:
        lines.append(f"## {t.name}")
        lines.append("")
        lines.append("| Agent | Wall (s) | Passed | Error |")
        lines.append("|---|---:|:-:|---|")
        for a in t.agents:
            err = a.error or ""
            mark = "✓" if a.passed else "✗"
            lines.append(f"| {a.agent} | {a.wall_s:.3f} | {mark} | {err} |")
        lines.append("")

    return "\n".join(lines)


def write_report(
    results_dir: Path,
    out_md: Path,
    out_json: Path | None = None,
) -> BenchmarkReport:
    """Load + render a report. Returns the loaded BenchmarkReport."""
    report = load_results(results_dir)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report))
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
