"""Tests for hermes_benchmark.tasks — focuses on generated-script parseability.

The previous implementation interpolated raw shell commands into Python source
unquoted, which produced unparsable scripts for any command containing single
quotes (e.g. ``echo '$NAME'``). These tests guarantee that every generated
body parses with ``ast.parse``.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from hermes_benchmark.tasks import (
    ALL_AGENT_NAMES,
    TASKS,
    goal_for,
    known_tests,
    make_goal_body,
)


@pytest.mark.parametrize("test_name", list(TASKS.keys()))
@pytest.mark.parametrize("agent", ALL_AGENT_NAMES[:3])
def test_generated_body_parses(test_name: str, agent: str) -> None:
    """Every (agent, test) body must round-trip through ast.parse."""
    goal = goal_for(agent, test_name)
    # Extract the python body between PYEOF markers.
    assert goal.startswith("python3 - <<'PYEOF'\n")
    assert goal.endswith("PYEOF\n")
    body = goal[len("python3 - <<'PYEOF'\n") : -len("PYEOF\n")]
    ast.parse(body)


@pytest.mark.parametrize(
    "evil_cmd",
    [
        "echo 'hello'",
        'echo "hi"',
        "echo $'\\nfoo'",
        "printf '%s\\n' 'a' 'b'",
        "echo $(date +%s)",
        "true && false || echo done",
    ],
)
def test_make_goal_body_handles_evil_quoting(evil_cmd: str) -> None:
    body = make_goal_body("ALPHA", "echo_test", evil_cmd)
    ast.parse(body)
    # The shell command should appear once, embedded as a Python literal.
    assert repr(evil_cmd) in body


def test_unknown_test_rejected() -> None:
    with pytest.raises(KeyError):
        goal_for("ALPHA", "definitely_not_a_test")


def test_known_tests_returns_registry_keys() -> None:
    assert set(known_tests()) == set(TASKS.keys())


def test_generated_script_writes_valid_json(tmp_path: Path) -> None:
    """End-to-end smoke: run the generated body and check the JSON it writes."""
    body = make_goal_body(
        "ALPHA", "echo_test", "echo hello-world",
        result_dir=str(tmp_path), timeout_s=10,
    )
    script = tmp_path / "run.py"
    script.write_text(body)
    proc = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    out_file = tmp_path / "echo_test" / "ALPHA.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["agent"] == "ALPHA"
    assert data["test"] == "echo_test"
    assert data["passed"] is True
    assert data["output"].startswith("hello-world")
    assert isinstance(data["wall_s"], float)
    assert data["error"] is None


def test_generated_script_records_failure(tmp_path: Path) -> None:
    body = make_goal_body(
        "BRAVO", "echo_test", "exit 7",
        result_dir=str(tmp_path), timeout_s=10,
    )
    script = tmp_path / "run.py"
    script.write_text(body)
    proc = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0
    data = json.loads((tmp_path / "echo_test" / "BRAVO.json").read_text())
    assert data["passed"] is False
    assert data["error"] is not None
    assert "7" in data["error"]


def test_browser_test_is_not_a_fabricated_pass(tmp_path: Path) -> None:
    """The browser test is not implemented; it must record passed=false.

    Returning a passing row for a workload that ran nothing would violate the
    "no fabricated rows" invariant. The shell command exits non-zero so the
    sub-agent records an honest failure with a clear error message.
    """
    goal = goal_for("ALPHA", "browser")
    body = goal[len("python3 - <<'PYEOF'\n") : -len("PYEOF\n")]
    body = body.replace("/tmp/bench_results", str(tmp_path))
    script = tmp_path / "run.py"
    script.write_text(body)
    subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=30,
        check=True,
    )
    data = json.loads((tmp_path / "browser" / "ALPHA.json").read_text())
    assert data["passed"] is False
    assert data["error"] is not None
    assert "not implemented" in (data.get("output", "") + (data["error"] or ""))


def test_generated_script_atomic_write_no_tmp_left_behind(tmp_path: Path) -> None:
    body = make_goal_body(
        "CHARLIE", "echo_test", "echo done",
        result_dir=str(tmp_path), timeout_s=10,
    )
    script = tmp_path / "run.py"
    script.write_text(body)
    subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=30,
        check=True,
    )
    leftovers = list((tmp_path / "echo_test").glob("*.tmp"))
    assert leftovers == []
