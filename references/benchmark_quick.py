#!/usr/bin/env python3
"""
Hermes Swarm Benchmark — Quick Mode (Non-Interactive, E2E)
Uses result-collection pattern for accurate wall-time measurement.

Usage:
  python3 benchmark_quick.py --agents 4 --tests echo_test,compute_pi --orchestrator none --run-via-agent

Flags:
  --agents      2-8 (auto-detected max from config if omitted)
  --tests       comma-separated: echo_test,file_io,compute_pi,browser
  --orchestrator none|1x4|2x4
  --output      chart output path (default: /tmp/benchmark_e2e.png)

Architecture:
  Each sub-agent writes its result to /tmp/bench_results/{test}/{agent}.json
  OMEGA spawns all agents, polls for result files, then reads them to compute
  real wall times from started_at/completed_at timestamps.

  Result JSON schema:
  {
    "agent": "ALPHA",
    "test": "echo_test",
    "started_at": 1746835200.123,
    "completed_at": 1746835200.456,
    "wall_s": 0.333,
    "passed": true,
    "output": "ALPHA:1746835200",
    "error": null,
    "pi_value": null
  }
"""

import argparse
import sys
from pathlib import Path

# Agent names in order
ALL_NAMES = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL"]

# Tests available
TESTS_AVAILABLE = ["echo_test", "file_io", "compute_pi", "terminal_cmd", "browser"]


def make_goal(name, test, cmd, report_prefix):
    """Build a sub-agent goal that runs cmd and writes result JSON."""
    return (
        f"python3 - << 'PYEOF'\n"
        f"import time, os, json, subprocess, sys\n"
        f"name = '{name}'\n"
        f"test = '{test}'\n"
        f"start = time.time()\n"
        f"try:\n"
        f"    output = subprocess.check_output({cmd}, shell=True, text=True).strip()\n"
        f"    passed = True\n"
        f"    error = None\n"
        f"except Exception as e:\n"
        f"    output = ''\n"
        f"    passed = False\n"
        f"    error = str(e)\n"
        f"completed = time.time()\n"
        f"wall = completed - start\n"
        f"result = dict(agent=name, test=test, started_at=start, completed_at=completed,\n"
        f"              wall_s=round(wall, 3), passed=passed, output=output, error=error)\n"
        f"os.makedirs(f'/tmp/bench_results/{{test}}/', exist_ok=True)\n"
        f"with open(f'/tmp/bench_results/{{test}}/{{name}}.json', 'w') as f:\n"
        f"    json.dump(result, f)\n"
        f"print(f'{report_prefix}|passed={{passed}}|wall={{wall:.3f}}s')\n"
        f"PYEOF\n"
    )


# Test definitions — each sub-agent goal writes result JSON
TASKS = {
    "echo_test": {
        "toolset": "terminal",
        "goal": lambda name: make_goal(
            name, "echo_test",
            f"echo '{name}:$(date +%s)'",
            f"{name}"
        ),
    },
    "file_io": {
        "toolset": "terminal",
        "goal": lambda name: make_goal(
            name, "file_io",
            f"mkdir -p /tmp/bench && echo '{name}:$(date +%s)' > /tmp/bench/{name}.txt && cat /tmp/bench/{name}.txt",
            f"{name}"
        ),
    },
    "compute_pi": {
        "toolset": "terminal",
        "goal": lambda name: make_goal(
            name, "compute_pi",
            "python3 - << 'PIEOF'\n"
            f"name = '{name}'\n"
            "import time\n"
            "start = time.time()\n"
            "pi = 0.0\n"
            "for i in range(5000000):\n"
            "    pi += ((-1) ** i) * 4 / (2 * i + 1)\n"
            "wall = time.time() - start\n"
            "print(f'{name}|{pi:.10f}|{wall:.3f}s')\n"
            "PIEOF",
            f"{name}"
        ),
    },
    "terminal_cmd": {
        "toolset": "terminal",
        "goal": lambda name: make_goal(
            name, "terminal_cmd",
            f"echo '{name}:$(date +%s)'",
            f"{name}"
        ),
    },
    "browser": {
        "toolset": "browser",
        "goal": lambda name: make_goal(
            name, "browser",
            "echo 'browser_skipped'",
            f"{name}"
        ),
    },
}

ORCHESTRATOR_TASKS = {
    "1x4": {
        "orchestrator": "OMEGA-1",
        "sub_agents": ["ALPHA", "BRAVO", "CHARLIE", "DELTA"],
    },
    "2x4": {
        "orchestrator_1": "OMEGA-1",
        "orchestrator_2": "OMEGA-2",
        "sub_agents_1": ["ALPHA", "BRAVO", "CHARLIE", "DELTA"],
        "sub_agents_2": ["ECHO", "FOXTROT", "GOLF", "HOTEL"],
    },
}


def get_configured_max_agents():
    """Auto-detect max_concurrent_children from config.yaml."""
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        for line in config_path.read_text().splitlines():
            if "max_concurrent_children" in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    return int(parts[1])
    except Exception:
        pass
    return 3


def build_omega_goal(agent_names, tests, orchestrator_mode):
    """Build the OMEGA orchestrator goal using result-collection pattern."""

    # Build per-test sub-agent spawn blocks
    test_spawn_blocks = []
    for test in tests:
        task = TASKS.get(test)
        if not task:
            continue
        lines = [f"TEST: {test} — spawn {len(agent_names)} agents:"]
        for name in agent_names:
            goal_code = task["goal"](name)
            goal_escaped = goal_code.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(
                f"  delegate_task(goal=\"You are {name}. Run this shell script and "
                f"write result to /tmp/bench_results/{test}/{name}.json: "
                f"{goal_escaped[:200]}... [truncated] \", toolsets=['terminal'])"
            )
        test_spawn_blocks.append("\n".join(lines))

    orch_block = ""
    if orchestrator_mode != "none":
        cfg = ORCHESTRATOR_TASKS.get(orchestrator_mode, {})
        if orchestrator_mode == "1x4":
            subs = cfg.get("sub_agents")
            orch_block = (
                f"ORCHESTRATOR 1x4: spawn OMEGA-1 → sub-agents [{', '.join(subs)}]\n"
                f"Each sub-agent: python3 -c \"print('SUB_AGENT done')\" → "
                f"write /tmp/bench_results/orchestrator_1x4/{{name}}.json\n"
                f"OMEGA-1 reports: spawned, completed, failed, wall_s"
            )
        elif orchestrator_mode == "2x4":
            subs1 = cfg.get("sub_agents_1")
            subs2 = cfg.get("sub_agents_2")
            orch_block = (
                f"ORCHESTRATOR 2x4:\n"
                f"  OMEGA-1 → [{', '.join(subs1)}]\n"
                f"  OMEGA-2 → [{', '.join(subs2)}]\n"
                f"Each: python3 -c \"print('SUB_AGENT done')\" → result JSON\n"
                f"Each orchestrator reports spawned/completed/failed/wall_s"
            )

    goal = f"""You are OMEGA, the FULLY AUTONOMOUS benchmark orchestrator.
You have tools: delegation, terminal, file.

AGENTS: {', '.join(agent_names)}
TESTS: {', '.join(tests)}
ORCHESTRATOR_MODE: {orchestrator_mode}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL — Result Collection Pattern
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
delegate_task is non-blocking (returns immediately after spawn).
You MUST collect real wall times from result JSON files.

Result schema at /tmp/bench_results/{{test}}/{{agent}}.json:
{{"agent","test","started_at","completed_at","wall_s","passed","output","error"}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 1 — Clean results dir
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
terminal: rm -rf /tmp/bench_results && mkdir -p /tmp/bench_results

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 2 — Spawn all sub-agents
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For each test in [{', '.join(tests)}]:
  For each agent in [{', '.join(agent_names)}]:
    Spawn via delegate_task with toolsets=['terminal'].
    Each sub-agent runs its assigned task and writes result JSON.
    All spawns are fire-and-forget — delegate_task returns IMMEDIATELY.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 3 — Poll for results (BLOCK until all exist)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Poll every 0.5s via terminal:
  terminal: python3 -c "
import os, time
tests = {repr(tests)}
agents = {repr(agent_names)}
while True:
    done = []
    for t in tests:
        for a in agents:
            if os.path.exists(f'/tmp/bench_results/{{t}}/{{a}}.json'):
                done.append(f'{{t}}/{{a}}')
    if len(done) >= len(tests) * len(agents):
        print(f'ALL DONE: {{len(done)}} results')
        break
    time.sleep(0.5)
"
Wait for the "ALL DONE" message.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 4 — Read results and compute statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For each test in TESTS:
  Read all /tmp/bench_results/{{test}}/{{agent}}.json files.
  Parse: started_at, completed_at, wall_s, passed, output, pi_value (compute_pi)
  Compute per test:
    pass_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    total_wall = max(r['completed_at'] for r in results) - min(r['started_at'] for r in results)
    agent_walls = [r['wall_s'] for r in results]
    thru = pass_count / total_wall if total_wall > 0 else 0
  Print each test's results clearly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 5 — Orchestrator test (if ORCHESTRATOR_MODE != none)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{orch_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 6 — Generate chart PNG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
terminal → python3:
```python
from PIL import Image, ImageDraw, ImageFont
import os
try:
    font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 13)
    title_font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 16)
    tiny = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 10)
except:
    font = title_font = tiny = ImageFont.load_default()
W, H = 900, 700
img = Image.new('RGB', (W, H), '#0a0a14')
d = ImageDraw.Draw(img)
GOLD='#ffd700'; GREEN='#00ff41'; GRAY='#888888'; WHITE='#ffffff'; FAIL_COL='#ff4444'
d.text((20,14), "HERMES SWARM BENCHMARK", fill=GOLD, font=title_font)
d.text((20,38), "Agents: {len(agent_names)} | Model: MiniMax-M2.7 | Orchestrator: {orchestrator_mode}", fill=GRAY, font=tiny)
d.text((20,56), "="*100, fill=GOLD)
y=72
for col,cx in [('TEST',20),('PASS',200),('WALL',280),('THRU',360),('STATUS',440)]:
    d.text((cx,y), col, fill=GRAY, font=tiny)
d.text((20,y),"-"*100,fill='#444444'); y+=22
for r in results:
    pct=r["pass"]/r["total"] if r["total"]>0 else 0
    col=GREEN if pct==1.0 else FAIL_COL
    wall_str=f'{{r["wall"]:.1f}}s' if r["wall"]>0.5 else "~<1s"
    thru_str=f'{{r["thru"]:.1f}}/s' if r["thru"]>0 else "N/A"
    d.text((20,y),r["name"],fill=col,font=font)
    d.text((200,y),f'{{r["pass"]}}/{{r["total"]}}',fill=WHITE,font=font)
    d.text((280,y),wall_str,fill=WHITE,font=font)
    d.text((360,y),thru_str,fill=GRAY,font=font)
    d.text((440,y),r["status"],fill=col,font=font)
    y+=22
y+=8; d.text((20,y),"="*100,fill=GOLD); y+=24
tp=sum(r["pass"] for r in results); ta=sum(r["total"] for r in results)
tw=max(r["wall"] for r in results)
d.text((20,y),f"GRAND: {{tp}}/{{ta}} PASS ({{tp/ta*100:.0f}}%) | WALL={{tw:.1f}}s",fill=GOLD,font=title_font)
img.save('/tmp/benchmark_e2e.png')
print(f"Chart: {{os.path.getsize('/tmp/benchmark_e2e.png')}} bytes")
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step 7 — Return results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
╔══════════════════════════════════════════════╗
║  BENCHMARK COMPLETE — OMEGA ORCHESTRATOR     ║
╠══════════════════════════════════════════════╣
║  TEST         | PASS | WALL  | THRU    | STAT║
║  echo_test    | X/X  | Xs    |  N/s    |  ✓  ║
║  file_io      | X/X  | Xs    |  N/s    |  ✓  ║
║  compute_pi   | X/X  | Xs    |  N/s    |  ✓  ║
╠══════════════════════════════════════════════╣
║  GRAND: X/X PASS | WALL=XXs                ║
║  Chart: /tmp/benchmark_e2e.png              ║
╚══════════════════════════════════════════════╝

Report ACTUAL values from result JSONs. Compute wall as:
  test_total_wall = max(completed_at) - min(started_at)
  per_agent_wall = wall_s from JSON
Do NOT use spawn time as wall time.

Handle everything autonomously — do NOT ask the user.
"""

    return goal


def run_quick_benchmark(agents, tests, orchestrator, output, run_via_agent=False):
    """Main entry point."""
    max_agents = get_configured_max_agents()

    print("=== HERMES SWARM BENCHMARK — E2E (Result Collection) ===", file=sys.stderr)
    print(f"  Detected max_concurrent_children: {max_agents}", file=sys.stderr)
    print(f"  Requested agents: {agents}", file=sys.stderr)
    print(f"  Tests: {', '.join(tests)}", file=sys.stderr)
    print(f"  Orchestrator: {orchestrator}", file=sys.stderr)
    print(f"  Result dir: /tmp/bench_results/", file=sys.stderr)

    if agents > max_agents:
        print(f"\nERROR: {agents} agents requested but max_concurrent_children={max_agents}", file=sys.stderr)
        return 2

    selected_names = ALL_NAMES[:agents]
    goal = build_omega_goal(selected_names, tests, orchestrator)

    if run_via_agent:
        goal_path = Path("/tmp/omega_goal.txt")
        goal_path.write_text(goal)
        print(f"\n[RUN] Goal written to: {goal_path}", file=sys.stderr)
        print(f"\nTo execute, tell this agent:", file=sys.stderr)
        print(f"  'Run {agents}-agent benchmark with tests: {', '.join(tests)}'", file=sys.stderr)
        return 0

    print("\n[PREVIEW] --run-via-agent not set. No agents spawned.", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Hermes Swarm Benchmark — E2E Quick Mode\n"
                    "Uses result-collection pattern for accurate wall times."
    )
    parser.add_argument("--agents", type=int, default=None,
                        help="Number of agents (2-8). Auto-detected if omitted.")
    parser.add_argument("--tests", type=str, default="echo_test,file_io,compute_pi",
                        help="Comma-separated test names (default: echo_test,file_io,compute_pi)")
    parser.add_argument("--orchestrator", type=str, default="none",
                        choices=["none", "1x4", "2x4"],
                        help="Orchestrator config (default: none)")
    parser.add_argument("--output", type=str, default="/tmp/benchmark_e2e.png",
                        help="Output chart path (default: /tmp/benchmark_e2e.png)")
    parser.add_argument("--run-via-agent", action="store_true",
                        help="Write OMEGA goal to /tmp/omega_goal.txt.")
    parser.add_argument("--model", type=str, default=None,
                        help="Model to use (default: current configured model)")

    args = parser.parse_args()

    max_agents = get_configured_max_agents()
    agents = args.agents if args.agents is not None else max_agents
    test_list = [t.strip() for t in args.tests.split(",") if t.strip()]

    return run_quick_benchmark(
        agents=agents,
        tests=test_list,
        orchestrator=args.orchestrator,
        output=args.output,
        run_via_agent=args.run_via_agent,
    )


if __name__ == "__main__":
    sys.exit(main() or 0)