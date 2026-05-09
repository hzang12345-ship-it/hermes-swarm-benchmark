---
name: hermes-swarm-benchmark
description: "Run a configurable concurrent agent benchmark suite for Hermes Agent — auto-detects max agents, lets user pick count (2-8), optional multi-orchestrator stress test. Results emitted as a polished Markdown report."
version: 6.1.0
author: hessumz
platforms: [macos, linux]
metadata:
  hermes:
    tags: [benchmark, swarm, delegation, concurrent-agents, interactive]
    category: software-development
---

# Hermes Swarm Benchmark v6

Interactive, user-configurable concurrent agent benchmark. Auto-detects your
configured `max_concurrent_children`, lets you choose how many agents to test,
and includes an optional multi-orchestrator stress test.

**v6.1 changes:** PNG chart output removed. The benchmark now produces a
single first-class artifact, **`REPORT.md`** — a polished Markdown report with
a PASS/FAIL banner, run config, environment, per-test detail, failures
section, and reproduce command. Optional aggregated `report.json` for
downstream tooling.

**v6 changes (2026-05-09):** Result-collection architecture. Sub-agents write
real timestamps to JSON. OMEGA polls and reads actual completion times — no
more 0.0s wall times.

## The Core Idea

**"I just want to test 2 agents"** — valid.
**"I want to stress test 2 orchestrators each spawning 4 subs"** — also valid.

This skill adapts to your plan tier, not the other way around.

**Style: tight output for end users.** When the benchmark completes, point
the user at `REPORT.md` and surface the grand-total line. No reasoning
traces, no tool-call replay, no verbose instruction bullets.

---

## Step 0: Auto-Detect Config

Before the skill says anything to the user, silently check the current
`max_concurrent_children` from config:

```bash
DETECTED=$(grep max_concurrent_children ~/.hermes/config.yaml | awk '{print $2}')
```

- Default Hermes: `3`
- After our fix: `8`
- User might have set anything between 2–8

## Step 1: Pick Agent Count and Tests

Offer the user a quick interactive prompt:

- agent count (2–8, default = detected max)
- tests (default: `echo_test,file_io,compute_pi`)
- orchestrator topology (`none` / `1x4` / `2x4`)

If user says `n`, let them adjust any choice. If `y`, proceed to Step 2.

---

## Step 2: Config Mismatch Warning

If user picked an agent count that exceeds currently configured
`max_concurrent_children`:

```
⚠️  Config mismatch detected.
    You chose {USER_CHOICE} agents but config has max_concurrent_children: {CURRENT}.

Options:
  1) Update config to {USER_CHOICE} and restart gateway (recommended)
  2) Run with current {CURRENT} agents instead
  3) Keep config but cap at {USER_CHOICE} (will fail if {CURRENT} < {USER_CHOICE})
```

To update config automatically:

```bash
sed -i '' "s/^  max_concurrent_children: [0-9]*/  max_concurrent_children: {USER_CHOICE}/" ~/.hermes/config.yaml
launchctl unload ~/Library/LaunchAgents/ai.hermes.gateway.plist
launchctl load ~/Library/LaunchAgents/ai.hermes.gateway.plist
echo "Gateway restarted with max_concurrent_children: {USER_CHOICE}"
```

---

## Step 3: Run Fully Autonomous

Once config is valid and the user confirms, spawn the OMEGA orchestrator
agent. The orchestrator handles everything autonomously — no further user
input needed until results are ready.

Agent naming by count:

| Count | Names used |
|-------|-----------|
| 2 | ALPHA, BRAVO |
| 3 | ALPHA, BRAVO, CHARLIE |
| 4 | ALPHA, BRAVO, CHARLIE, DELTA |
| 5 | ALPHA..ECHO |
| 6 | ALPHA..FOXTROT |
| 7 | ALPHA..GOLF |
| 8 | ALPHA..HOTEL |

The OMEGA orchestrator goal:

- Spawns all agent waves in parallel via `delegate_task`.
- Sub-agents write `/tmp/bench_results/{test}/{agent}.json` (atomic writes,
  60s timeout per workload).
- OMEGA polls until all files exist, then runs the report renderer.

### Render the report

```bash
python -m hermes_benchmark.report \
    --results-dir /tmp/bench_results \
    --out REPORT.md \
    --json report.json
```

Default and only first-class output: **`REPORT.md`** — a polished Markdown
document with:

- PASS/FAIL banner and grand-total wall time.
- Run configuration (agent count, orchestrator, model, test count).
- Environment (Python version, platform, generation timestamp).
- Summary table per test (pass/total/wall/throughput) with a totals row.
- Per-test detail tables with started/completed timestamps per agent.
- Failures section with error message and last output (or "None" when all
  passed).
- Reproduce block with the exact CLI commands.
- Raw data pointers to the per-agent JSON files and aggregated `report.json`.

`report.json` is optional, written only when `--json` is supplied — useful
for downstream tooling but not required for human review.

Sub-agent names for orchestrator test:

- Orchestrator 1 spawns: ALPHA, BRAVO, CHARLIE, DELTA
- Orchestrator 2 spawns: ECHO, FOXTROT, GOLF, HOTEL

---

## Run Tests

### Standard Parallel Test

```python
delegate_task(
    goal="You are {AGENT_NAME}. Your task: {TASK}.
    Report: {AGENT_NAME} | wall_time | tokens_in | tokens_out | api_calls | PASS/FAIL",
    tasks=[
        {"goal": "{NAME}: {TASK}", "toolsets": ["terminal"]}
        for NAME in selected_names
    ],
    toolsets=["terminal", "file", "web", "delegation"],
)
```

### Tests Available

| Test | Toolset | Task | Notes |
|------|---------|------|-------|
| `echo_test` | terminal | codename + timestamp | fast, always works |
| `file_io` | terminal | write/verify `/tmp/bench/[AGENT].txt` | tests filesystem |
| `compute_pi` | terminal | Leibniz series, 5M iterations | CPU-bound, deterministic |
| `terminal_cmd` | terminal | alias for echo_test | back-compat |
| `browser` | browser | placeholder | no-op currently |

### echo_test Task (recommended implementation)

```python
import time, json, os
name = 'ALPHA'  # or BRAVO, CHARLIE, DELTA
test = 'echo_test'
start = time.time()
# Use Python time — avoids shell quoting issues with $() in subprocess.
output = f"{name}:{int(time.time())}"
wall = time.time() - start
result = dict(agent=name, test=test, started_at=start, completed_at=time.time(),
              wall_s=round(wall, 3), passed=True, output=output, error=None)
os.makedirs(f'/tmp/bench_results/{test}/', exist_ok=True)
with open(f'/tmp/bench_results/{test}/{name}.json', 'w') as f:
    json.dump(result, f, indent=2)
print(f"{name}|{output}|wall={wall:.3f}s")
```

> **⚠️ DO NOT use** `subprocess.check_output("echo 'AGENTNAME:$(date +%s)'", shell=True)` —
> single quotes prevent `$()` expansion. Use Python `time.time()` instead.

## Orchestrator Test

```python
delegate_task(
    goal="""You are OMEGA-1. Your job: spawn 4 named sub-agents (ALPHA, BRAVO, CHARLIE, DELTA).
    Each sub-agent runs: python3 -c "import time; print('SUB_AGENT done')"
    Wait for all 4 to complete, then report:
    OMEGA-1 | wall_time | spawned: 4 | completed: N | failed: Z""",
    toolsets=["delegation", "terminal"],
)
# Run N times for N orchestrators
```

> **Pitfall:** When building orchestrator sub-agent goals, each name must
> be expanded inline — never pass a literal `{name}` placeholder to
> sub-agents. The correct pattern iterates the sub-agent list and uses
> `.format(n, n)` or `.replace()` per agent:
>
> ```python
> sub_lines = "\n".join("  - {}: python3 -c \"print('{} done')\"".format(n, n) for n in subs)
> ```
>
> A literal `{name}` will reach sub-agents unexpanded, breaking the test.

> **Pitfall (2026-05-09):** Orchestrator sub-agents using
> `tee /tmp/bench_results/orchestrator/{name}.json` may write plain text
> instead of structured JSON. Use Python to write the JSON explicitly:
>
> ```python
> with open(f"/tmp/bench_results/orchestrator/{name}.json", "w") as f:
>     json.dump(dict(agent=name, test="orchestrator", passed=True, output="done"), f)
> ```
>
> Never rely on `tee` for structured JSON output in benchmark result collection.

---

## Output Format

The orchestrator surfaces only the grand-total line and the path to
`REPORT.md`:

```
✓ Hermes Swarm Benchmark — 16/16 passed (100%) in 12.3s
  Report: REPORT.md
```

`REPORT.md` is the canonical artifact — open it in any Markdown viewer or
let GitHub render it. **No PNG output is produced.** If you need a chart,
plot from `report.json` with a separate tool — that's a deliberate
boundary.

**End-user output only** — show the final summary line plus the report
path. No internal reasoning traces, no tool-call replay, no verbose bullet
lists of "Important:" instructions. Keep it tight.

---

## E2E Automation — Result-Collection Architecture (Implemented)

The `hermes-benchmark` CLI generates a real OMEGA goal with the
result-collection pattern.

**Why result collection works:**

- `delegate_task` is non-blocking — it fires and returns immediately.
- The agent's wall time is spawn time, not completion time → always ~0ms.
- Fix: sub-agents write `started_at`/`completed_at` to
  `/tmp/bench_results/{test}/{agent}.json`.
- OMEGA polls until all files exist, reads timestamps, computes
  `total_wall = max(completed_at) - min(started_at)`.

**Why `execute_code` can't call `delegate_task`:**

- `delegate_task` is an **AIAgent METHOD** on the live agent object.
- It's NOT a standalone Python function — cannot be imported from a subprocess.
- ACP adapter uses JSON-RPC over stdio — designed for interactive clients.
- `max_spawn_depth: 1` enforced — orchestrator → sub-agent only, no
  grandchild spawning.

**The correct E2E pattern is the 2-step agent workflow:**

1. `hermes-benchmark --agents 4 --tests echo_test,compute_pi`
2. Tell this agent: "Run 4-agent benchmark with tests: echo_test, compute_pi"

### compute_pi Escaping — Critical Bug

> **BUG:** f-string `{}` braces conflict with Python's `.format()` template substitution.
> `python3 -c "print(f'{name}|{time:.3f}')"` — the `{time:.3f}` is evaluated
> by Python at string construction time, NOT passed through to the shell.
>
> **FIX:** Use `%%` for shell modulo operator, and `.replace("NAME", "{name}")`
> for name substitution instead of `.format()`.

### echo_test Subprocess Quoting — Shell Expansion Fails in Single Quotes

> **BUG (found in benchmark Run 9):**
> `subprocess.check_output("echo 'AGENTNAME:$(date +%s)'", shell=True)` — single
> quotes around `$(date +%s)` prevent shell `$()` expansion. Subprocess
> receives literal string `AGENTNAME:$(date +%s)` instead of a timestamp.
>
> **RECOMMENDED FIX:** Use Python's `time.time()` directly.

### OMEGA Sub-Agent Goal Truncation — Critical Bug

> **BUG:** When OMEGA passes a goal to a sub-agent via `delegate_task`,
> the goal string can get truncated at ~500 tokens. The compute_pi
> 5M-iteration inline script was being cut off.
>
> **FIX:** For CPU-bound compute tasks, prefer a temp-file approach — have
> OMEGA write the script to `/tmp/pi_{name}.py` first, then run it.

### Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--agents` | 1–8 | auto-detected max | Number of agents to spawn |
| `--tests` | comma-separated | `echo_test,file_io,compute_pi` | Tests to run |
| `--orchestrator` | `none`, `1x4`, `2x4` | `none` | Orchestrator config |
| `--results-dir` | path | `/tmp/bench_results` | Where sub-agents write JSON |
| `--goal-out` | path | `/tmp/omega_goal.txt` | Where to write the OMEGA goal |

For the report renderer:

| Flag | Default | Description |
|------|---------|-------------|
| `--results-dir` | `/tmp/bench_results` | Per-agent result directory |
| `--out` | `REPORT.md` | Markdown report output (primary artifact) |
| `--json` | _(none)_ | Optional aggregated JSON output |

### Available Tests

- `echo_test` — codename + timestamp (fast, always works)
- `file_io` — write/verify `/tmp/bench/[AGENT].txt`
- `compute_pi` — Leibniz 5M iterations (CPU-bound, deterministic) — ⚠️ use
  temp-file approach to avoid goal truncation
- `terminal_cmd` — alias for echo_test
- `browser` — placeholder, currently a no-op

### Orchestrator Options

- `none` — skip orchestrator test
- `1x4` — 1 orchestrator spawning 4 sub-agents
- `2x4` — 2 orchestrators each spawning 4 sub-agents (stress test)

### Example Runs

```bash
# Minimal: 2 agents, echo only
hermes-benchmark --agents 2 --tests echo_test

# Balanced: 4 agents, standard tests
hermes-benchmark --agents 4 --tests echo_test,file_io,compute_pi

# Full: 8 agents, all tests, 1 orchestrator
hermes-benchmark --agents 8 --tests echo_test,file_io,compute_pi,browser --orchestrator 1x4

# Stress: 8 agents + 2 orchestrators
hermes-benchmark --agents 8 --tests echo_test,file_io,compute_pi --orchestrator 2x4
```

### Exit Codes

- `0` — all tests passed
- `1` — one or more tests failed
- `2` — config mismatch (agents > max_concurrent_children) or invalid input

---

## Key Changes v3

1. **Auto-detect** max_concurrent_children from config at runtime.
2. **Interactive** — user picks agent count (2–8) and test suite.
3. **Dynamic agent names** — adapts to count, no hardcoded 8.
4. **Config mismatch warning** — offers to update and restart.
5. **Multi-orchestrator support** — 1 or 2 orchestrators, each with sub-agents.
6. **Graceful degradation** — if camofox is down, browser test fails fast.

## Why no PNG chart?

The previous PIL-based chart generator had multiple bugs (dict iteration on
test rows, mis-counted `total_passed`, hardcoded stale data) and required
a font path that doesn't exist on Linux CI. PR #1 deleted it. Markdown is
more reviewable, diffs in Git, and renders in any PR. If you need a chart
later, run a separate plotting tool against `report.json` — that's a
deliberate boundary.

## Bugs Fixed (Historical)

| Bug | Fix |
|-----|-----|
| max_concurrent_children=3 hard-coded | Now auto-detected from config |
| No restart warning when config changed | Explicit warning + restart commands |
| 8 agents always hardcoded | Dynamic based on user choice |
| Orchestrator test was 1x4 only | Now supports 1x4 or 2x4 |
| web_research always failed | Removed — MiniMax rate-limits any target at 8x concurrency |
| benchmark_quick.py skeleton | Confirmed as non-executable; agent-orchestrator path is the real solution |
| compute_pi f-string brace escaping | Use `%%` shell modulo + `.replace("NAME","{name}")` instead of `.format()` |
| OMEGA goal truncation at ~500 tokens | Use temp-file approach for large inline scripts |
| PIL chart generator: multiple bugs | **Deleted in PR #1.** Markdown report replaces it entirely. |
| Pillow font dependency on Linux CI | **Removed.** Reports are plain Markdown, no fonts/images required. |

## Pitfalls and Invariants

**Sub-agent goals must expand names inline** — never pass a literal `{name}`
placeholder to sub-agents.

**compute_pi must use `%%` shell modulo** — never `.format()` on f-string
brace syntax.

**OMEGA goal truncation** — keep sub-agent goal strings under ~500 tokens;
use temp-file approach for large inline scripts.

**Wall time accuracy by test type:**

- `compute_pi` (5M iterations): wall time is accurate — takes >1s per
  agent, measurement captures it.
- `echo_test`, `file_io`: wall time reads as 0.0s because sub-second tasks
  complete before parent observes them separately — PASS counts are always
  correct.

## Key Delegate Architecture (Session 2026-05-09)

- `delegate_task` lives at `run_agent.py:_dispatch_delegate_task` →
  `tools/delegate_tool.py:delegate_task`.
- It's a method on the live AIAgent, not importable from subprocess.
- ACP adapter uses JSON-RPC over stdio — local-trust, designed for
  interactive clients.
- ACP stdio reserves stdout for JSON-RPC frames; logging goes to stderr.
- Subagent approval callback: `tools/terminal_tool.py` uses
  `threading.local()` — not inherited by ThreadPoolExecutor workers;
  delegate_tool installs `_subagent_auto_deny` by default.
- `max_spawn_depth: 1` enforced — orchestrator → sub-agent only, no
  grandchild spawning.

## Verification

```bash
# Step 0: auto-detect
grep max_concurrent_children ~/.hermes/config.yaml

# Step 1: pick count
# Step 2: pick tests
# Step 3: pick orchestrator

# If config changed:
launchctl list | grep hermes  # confirm running
```
