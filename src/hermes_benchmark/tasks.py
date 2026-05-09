"""Task definitions for Hermes Swarm Benchmark.

Each task knows how to build a Python script body that, when executed by a
sub-agent, runs the workload and writes an AgentResult JSON file.

Important: the previous version interpolated raw shell commands directly into
generated Python source, which produced unparsable output for any command
containing quotes or backslashes. We now use ``repr()`` to embed every
runtime value as a Python literal, so the generated body is always parseable.
Every body produced here must round-trip through ``ast.parse`` (see tests).
"""

from __future__ import annotations

from typing import Callable

ALL_AGENT_NAMES = [
    "ALPHA",
    "BRAVO",
    "CHARLIE",
    "DELTA",
    "ECHO",
    "FOXTROT",
    "GOLF",
    "HOTEL",
]


_RESULT_TEMPLATE = '''\
import json
import os
import subprocess
import sys
import tempfile
import time

NAME = {name!r}
TEST = {test!r}
SHELL_CMD = {cmd!r}
RESULT_DIR = {result_dir!r}
TIMEOUT_S = {timeout_s!r}

start = time.time()
try:
    output = subprocess.check_output(
        SHELL_CMD, shell=True, text=True, timeout=TIMEOUT_S,
        stderr=subprocess.STDOUT,
    ).strip()
    passed = True
    error = None
except subprocess.TimeoutExpired as exc:
    output = ""
    passed = False
    error = "timeout after " + str(TIMEOUT_S) + "s"
except subprocess.CalledProcessError as exc:
    output = (exc.output or "").strip()
    passed = False
    error = "exit " + str(exc.returncode)
except Exception as exc:
    output = ""
    passed = False
    error = repr(exc)
completed = time.time()

result = {{
    "agent": NAME,
    "test": TEST,
    "started_at": start,
    "completed_at": completed,
    "wall_s": round(completed - start, 3),
    "passed": passed,
    "output": output,
    "error": error,
}}

test_dir = os.path.join(RESULT_DIR, TEST)
os.makedirs(test_dir, exist_ok=True)
final_path = os.path.join(test_dir, NAME + ".json")
fd, tmp_path = tempfile.mkstemp(prefix=NAME + ".", suffix=".json.tmp", dir=test_dir)
try:
    with os.fdopen(fd, "w") as f:
        json.dump(result, f)
    os.replace(tmp_path, final_path)
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise

print(NAME + "|passed=" + str(passed) + "|wall=" + format(result["wall_s"], ".3f") + "s")
'''


def _shell_for_test(name: str, test: str) -> str:
    """Return the shell snippet a sub-agent should execute for the given test.

    These are intentionally simple. Anything involving multi-line Python is
    embedded as a single shell command (heredocs etc. round-trip fine because
    we pass the whole string through ``repr()`` later).
    """

    if test == "echo_test" or test == "terminal_cmd":
        return f"echo '{name}:'$(date +%s)"
    if test == "file_io":
        return (
            f"mkdir -p /tmp/bench && echo '{name}:'$(date +%s) > "
            f"/tmp/bench/{name}.txt && cat /tmp/bench/{name}.txt"
        )
    if test == "compute_pi":
        return (
            "python3 -c \"import time;s=time.time();"
            "p=sum(((-1)**i)*4/(2*i+1) for i in range(5000000));"
            f"print('{name}|'+format(p,'.10f')+'|'+format(time.time()-s,'.3f')+'s')\""
        )
    if test == "browser":
        # The browser workload is not implemented. Exit non-zero so the
        # sub-agent records passed=false with a clear error, rather than
        # producing a fabricated "passed" row for a workload that ran nothing.
        return "echo 'browser test not implemented in this build' >&2 && exit 1"
    raise KeyError(f"unknown test: {test!r}")


def make_goal_body(
    name: str,
    test: str,
    cmd: str,
    *,
    result_dir: str = "/tmp/bench_results",
    timeout_s: int = 60,
) -> str:
    """Return a Python source string the sub-agent should execute.

    All runtime values are embedded as Python literals via ``repr()`` so the
    body is always syntactically valid regardless of quoting in ``cmd``.
    """

    return _RESULT_TEMPLATE.format(
        name=name,
        test=test,
        cmd=cmd,
        result_dir=result_dir,
        timeout_s=timeout_s,
    )


def make_goal(
    name: str,
    test: str,
    *,
    result_dir: str = "/tmp/bench_results",
    timeout_s: int = 60,
) -> str:
    """High-level goal builder used by callers.

    Wraps the generated Python body in a ``python3 - << 'PYEOF'`` heredoc so
    a sub-agent can execute it via a single shell command.
    """

    cmd = _shell_for_test(name, test)
    body = make_goal_body(name, test, cmd, result_dir=result_dir, timeout_s=timeout_s)
    return "python3 - <<'PYEOF'\n" + body + "PYEOF\n"


def _terminal_toolset(_name: str) -> dict:
    return {"toolset": "terminal"}


# Test registry: name -> (toolset, goal-builder).
TASKS: dict[str, dict[str, object]] = {
    "echo_test": {
        "toolset": "terminal",
        "goal": (lambda name: make_goal(name, "echo_test")),
    },
    "file_io": {
        "toolset": "terminal",
        "goal": (lambda name: make_goal(name, "file_io")),
    },
    "compute_pi": {
        "toolset": "terminal",
        "goal": (lambda name: make_goal(name, "compute_pi")),
    },
    "terminal_cmd": {
        "toolset": "terminal",
        "goal": (lambda name: make_goal(name, "terminal_cmd")),
    },
    "browser": {
        "toolset": "browser",
        "goal": (lambda name: make_goal(name, "browser")),
    },
}


def known_tests() -> list[str]:
    return list(TASKS.keys())


def goal_for(name: str, test: str) -> str:
    """Lookup-and-build helper used by tests and the CLI."""
    if test not in TASKS:
        raise KeyError(f"unknown test: {test!r}")
    builder: Callable[[str], str] = TASKS[test]["goal"]  # type: ignore[assignment]
    return builder(name)
