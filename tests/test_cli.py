"""Tests for hermes_benchmark.cli — input validation and goal generation."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

import pytest

from hermes_benchmark import cli
from hermes_benchmark.tasks import ALL_AGENT_NAMES


def test_parse_tests_accepts_known() -> None:
    assert cli._parse_tests("echo_test, compute_pi") == ["echo_test", "compute_pi"]


def test_parse_tests_rejects_unknown() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="unknown"):
        cli._parse_tests("echo_test,not_a_real_test")


def test_parse_tests_rejects_empty() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_tests("")


def test_parse_tests_rejects_only_whitespace() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_tests(" , , ")


def test_parse_agents_bounds() -> None:
    assert cli._parse_agents("4") == 4
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_agents("0")
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_agents("99")
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_agents("not-a-number")


def test_safe_results_dir_rejects_traversal() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=r"\.\."):
        cli._safe_results_dir("/tmp/../etc")


def test_safe_results_dir_rejects_empty() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._safe_results_dir("")


def test_safe_results_dir_accepts_normal() -> None:
    p = cli._safe_results_dir("/tmp/bench_results")
    assert p == Path("/tmp/bench_results")


def test_build_omega_goal_includes_inputs() -> None:
    goal = cli.build_omega_goal(
        ALL_AGENT_NAMES[:2], ["echo_test", "compute_pi"], "1x4",
    )
    assert "ALPHA" in goal and "BRAVO" in goal
    assert "echo_test" in goal and "compute_pi" in goal
    assert "1x4" in goal
    assert "/tmp/bench_results" in goal
    assert "hermes_benchmark.report" in goal


def test_build_omega_goal_rejects_bad_orchestrator() -> None:
    with pytest.raises(AssertionError):
        cli.build_omega_goal(["ALPHA"], ["echo_test"], "bogus")


def test_main_writes_goal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    goal_out = tmp_path / "omega_goal.txt"
    rc = cli.main(
        [
            "--agents", "2",
            "--tests", "echo_test",
            "--orchestrator", "none",
            "--results-dir", str(tmp_path / "results"),
            "--goal-out", str(goal_out),
        ]
    )
    assert rc == 0
    assert goal_out.is_file()
    text = goal_out.read_text()
    assert "ALPHA" in text and "BRAVO" in text
    assert "echo_test" in text


def test_main_rejects_unknown_test(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--tests", "no_such_test", "--goal-out", str(tmp_path / "g.txt")])
    assert excinfo.value.code == 2


def test_generated_goal_preview_does_not_break_outer_format(tmp_path: Path) -> None:
    """Even with quotes/backticks in test bodies, the preview is sanitized."""
    goal = cli.build_omega_goal(["ALPHA"], list(cli.TASKS.keys()), "none")
    # Goal is plain text — must not contain any literal newlines inside
    # the preview that would break the surrounding line structure.
    for line in goal.splitlines():
        assert "\x00" not in line
