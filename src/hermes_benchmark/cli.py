"""Command-line entry point for the benchmark.

This module *does not* spawn agents — it builds the OMEGA goal text the same
way the original ``benchmark_quick.py`` did, but with proper input validation
and a Markdown-first reporting story.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from .tasks import ALL_AGENT_NAMES, TASKS, goal_for, known_tests


def _safe_results_dir(value: str) -> Path:
    """Reject obviously hostile result-dir paths (traversal, empty)."""
    if not value:
        raise argparse.ArgumentTypeError("results-dir cannot be empty")
    p = Path(value).expanduser()
    if ".." in p.parts:
        raise argparse.ArgumentTypeError(
            f"results-dir must not contain '..': {value!r}"
        )
    return p


def _parse_tests(value: str) -> list[str]:
    """Validate ``--tests`` against the known TASKS registry."""
    raw = [t.strip() for t in value.split(",") if t.strip()]
    if not raw:
        raise argparse.ArgumentTypeError("at least one test must be specified")
    bad = [t for t in raw if t not in TASKS]
    if bad:
        raise argparse.ArgumentTypeError(
            f"unknown test(s): {bad}. known tests: {known_tests()}"
        )
    return raw


def _parse_agents(value: str) -> int:
    try:
        n = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"agents must be an integer: {value!r}") from exc
    if not 1 <= n <= len(ALL_AGENT_NAMES):
        raise argparse.ArgumentTypeError(
            f"agents must be between 1 and {len(ALL_AGENT_NAMES)} (got {n})"
        )
    return n


def get_configured_max_agents() -> int:
    """Auto-detect ``max_concurrent_children`` from ~/.hermes/config.yaml."""
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        for line in config_path.read_text().splitlines():
            if "max_concurrent_children" in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        continue
    except OSError:
        pass
    return 3


def build_omega_goal(
    agent_names: list[str],
    tests: list[str],
    orchestrator: str,
    *,
    results_dir: str = "/tmp/bench_results",
) -> str:
    """Assemble the OMEGA orchestrator goal text."""

    assert orchestrator in {"none", "1x4", "2x4"}

    spawn_blocks: list[str] = []
    for test in tests:
        lines = [f"TEST: {test} — spawn {len(agent_names)} agents:"]
        for name in agent_names:
            body = goal_for(name, test)
            preview = body.replace("\n", " \\n ")[:200]
            lines.append(
                f"  delegate_task(goal=\"You are {name}. Run the script and write "
                f"result to {results_dir}/{test}/{name}.json: {preview}...\", "
                f"toolsets=['terminal'])"
            )
        spawn_blocks.append("\n".join(lines))

    return (
        "You are OMEGA, the autonomous benchmark orchestrator.\n\n"
        f"AGENTS: {', '.join(agent_names)}\n"
        f"TESTS: {', '.join(tests)}\n"
        f"ORCHESTRATOR_MODE: {orchestrator}\n"
        f"RESULT_DIR: {results_dir}\n\n"
        "Spawn the following sub-agents and poll for their result JSONs:\n\n"
        + "\n\n".join(spawn_blocks)
        + "\n\nWhen all results exist, run:\n"
        f"    python -m hermes_benchmark.report --results-dir {results_dir} "
        "--out REPORT.md --json report.json\n"
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hermes-benchmark",
        description=(
            "Hermes Swarm Benchmark — generate the OMEGA orchestrator goal "
            "(Markdown reporting via `hermes_benchmark.report`)."
        ),
    )
    parser.add_argument(
        "--agents",
        type=_parse_agents,
        default=None,
        help="Number of agents (1..8). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--tests",
        type=_parse_tests,
        default=_parse_tests("echo_test,file_io,compute_pi"),
        help=f"Comma-separated test names. Known: {known_tests()}.",
    )
    parser.add_argument(
        "--orchestrator",
        choices=["none", "1x4", "2x4"],
        default="none",
        help="Orchestrator topology (default: none).",
    )
    parser.add_argument(
        "--results-dir",
        type=_safe_results_dir,
        default=Path("/tmp/bench_results"),
        help="Where sub-agents write result JSONs.",
    )
    parser.add_argument(
        "--goal-out",
        type=Path,
        default=Path("/tmp/omega_goal.txt"),
        help="Where to write the generated OMEGA goal text.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    max_agents = get_configured_max_agents()
    agents = args.agents if args.agents is not None else max_agents
    if agents > len(ALL_AGENT_NAMES):
        print(
            f"error: agents={agents} exceeds {len(ALL_AGENT_NAMES)} known names",
            file=sys.stderr,
        )
        return 2
    if agents > max_agents:
        print(
            f"warning: agents={agents} exceeds detected "
            f"max_concurrent_children={max_agents}",
            file=sys.stderr,
        )

    selected = ALL_AGENT_NAMES[:agents]
    goal = build_omega_goal(
        selected,
        args.tests,
        args.orchestrator,
        results_dir=str(args.results_dir),
    )
    args.goal_out.parent.mkdir(parents=True, exist_ok=True)
    args.goal_out.write_text(goal)
    print(f"wrote {args.goal_out} ({len(goal)} bytes)")
    print(
        f"agents={agents} tests={args.tests} "
        f"orchestrator={args.orchestrator} results_dir={args.results_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
