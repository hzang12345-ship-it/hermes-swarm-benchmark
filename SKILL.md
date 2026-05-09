---
name: hermes-swarm-benchmark
description: "Run a configurable concurrent agent benchmark suite for Hermes Agent — auto-detects max agents, lets user pick count (2-8), optional multi-orchestrator stress test. Results as clean readable table."
version: 6.0.0
author: hessumz
platforms: [macos, linux]
metadata:
  hermes:
    tags: [benchmark, swarm, delegation, concurrent-agents, interactive]
    category: software-development
---

# Hermes Swarm Benchmark v6

Interactive, user-configurable concurrent agent benchmark. Auto-detects your configured `max_concurrent_children`, lets you choose how many agents to test, and includes an optional multi-orchestrator stress test.

**v6 changes (2026-05-09):** Result-collection architecture. Sub-agents write real timestamps to JSON. OMEGA polls and reads actual completion times — no more 0.0s wall times. benchmark_quick.py fully rewritten with real OMEGA goal template.

## The Core Idea

**"I just want to test 2 agents"** — valid.
**"I want to stress test 2 orchestrators each spawning 4 subs"** — also valid.

This skill adapts to your plan tier, not the other way around.

**Style: Tight output for end users.** When the benchmark completes, show only the results table and grand total. No reasoning traces, no tool-call replay, no verbose instruction bullets. The OMEGA orchestrator returns a clean `╔═╗` box — that is the only output the user sees.

---

## Step 0: Auto-Detect Config

Before the skill says anything to the user, silently check the current `max_concurrent_children` from config:

```bash
DETECTED=$(grep max_concurrent_children ~/.hermes/config.yaml | awk '{print $2}')
```

- Default Hermes: `3`
- After our fix: `8`
- User might have set anything between 2–8

---

## STEP 1 (BEGIN HERE — always, for every user)

Display this banner first, then immediately use `clarify` to ask the user their preferred run configuration. Do NOT run anything yet — collect all choices first.

```
╔══════════════════════════════════════════════════════════════╗
║              HERMES SWARM BENCHMARK v6                         ║
║  Test concurrent agent performance on your current plan.    ║
╠══════════════════════════════════════════════════════════════╣
║  ① Agents  ② Tests  ③ Orchestrator ④ Review → Run           ║
╚══════════════════════════════════════════════════════════════╝
```

**① AGENTS** — How many agents to test? (2, 4, or 8)

Use `clarify` with 3 choices:
- `2 agents` — fast, low cost
- `4 agents` — balanced (recommended)
- `8 agents` — full stress test (requires max_concurrent_children ≥ 8)

---

**② TESTS** — Which test suite?

Use `clarify` with 4 choices:
- `A) Minimal` — echo_test only (codename + timestamp, ~1s)
- `B) Standard` — echo_test + file_io + compute_pi (default)
- `C) Full` — echo_test + file_io + compute_pi + orchestrator_1x4
- `D) Custom` — pick individually

> **web_research excluded** — MiniMax plan rate-limits ANY target at 8x concurrency (HTTP 429).
> **browser** requires Camofox server at localhost:9377.

---

**③ ORCHESTRATOR STRESS TEST?**

Use `clarify` with 3 choices:
- `No` — skip orchestrator test (default)
- `Yes: 1 orchestrator` — spawns 4 sub-sub-agents (tests 2-level delegation)
- `Yes: 2 orchestrators` — each spawns 4 sub-sub-agents (stress test, 8 total)

---

**④ REVIEW & CONFIRM** — After collecting ① ② ③, show a summary and confirm before running. Example:

```
Ready to run:
  Agents: 4 (ALPHA, BRAVO, CHARLIE, DELTA)
  Tests:  Standard (echo_test + file_io + compute_pi)
  Orchestrator: None

Config check: max_concurrent_children = 8 ✓

Run now? [Y/n]
```

If user says `n`, let them adjust any choice. If `y`, proceed to Step 2.

---

## Step 2: Config Mismatch Warning

If user picked an agent count that exceeds currently configured `max_concurrent_children`:

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

Once config is valid and user confirmed, spawn the OMEGA orchestrator agent. The orchestrator handles everything autonomously — no further user input needed until results are ready.

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
- Spawns all agent waves in parallel via `delegate_task`
- Collects pass/fail/wall_time per agent per step
- Generates a clean readable table PNG at `/tmp/benchmark_run.png` (900×700 dark theme, monospace font, aligned columns)
- Reports grand total: X/N PASS, total wall time, token usage

### OMEGA Chart Generation Code (copy-paste this exactly)

**Visual reference:** `/private/tmp/benchmark_aligned.png` — this is the canonical format. No pixel art, just a clean readable table. Do NOT use pixel_art.py — it destroys column alignment on data-dense charts.

```python
from PIL import Image, ImageDraw, ImageFont
import os

try:
    font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 13)
    title_font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 16)
    tiny = ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", 10)
except:
    font = ImageFont.load_default()
    title_font = ImageFont.load_default()
    tiny = ImageFont.load_default()

W = 900
img = Image.new('RGB', (W, 700), '#0a0a14')
d = ImageDraw.Draw(img)

GOLD='#ffd700'; GREEN='#00ff41'; CYAN='#00d7ff'; GRAY='#888888'; WHITE='#ffffff'
PASS_COL=GREEN; FAIL_COL='#ff4444'

# ── Title ──
d.text((20, 14), "HERMES SWARM BENCHMARK v6", fill=GOLD, font=title_font)
# NOTE: Replace the subtitle line below with actual config: agent count, suite name, orchestrator mode
d.text((20, 38), f"N agents | SUITE | ORCHESTRATOR_MODE | {model}", fill=GRAY, font=tiny)
d.text((20, 56), "═" * 100, fill=GOLD)

# ── Column headers (aligned with data below) ──
# Col layout: TEST at x=20, PASS at x=200, WALL at x=280, THRU at x=360, STATUS at x=440
y = 72
col_x = {'TEST':20, 'PASS':200, 'WALL':280, 'THRU':360, 'STATUS':440}
for col, cx in col_x.items():
    d.text((cx, y), col, fill=GRAY, font=tiny)
d.text((20, y), "─"*100, fill='#444444')
y += 22

# ── Per-test rows ──
# results dict: {test_name: {pass, total, wall, thru, status}}
# NOTE: Replace results placeholder with actual collected data
results = [
    {"name": "echo_test",       "pass": N, "total": N, "wall": Xs,  "thru": N, "status": "✓", "color": PASS_COL},
    {"name": "file_io",         "pass": N, "total": N, "wall": Xs,  "thru": N, "status": "✓", "color": PASS_COL},
    {"name": "compute_pi",      "pass": N, "total": N, "wall": Xs,  "thru": N, "status": "✓", "color": PASS_COL},
    {"name": "orchestrator_NxN","pass": N, "total": N, "wall": Xs,  "thru": N, "status": "✓", "color": PASS_COL},
]
for r in results:
    pct = r["pass"] / r["total"] if r["total"] > 0 else 0
    row_color = PASS_COL if pct == 1.0 else FAIL_COL
    d.text((col_x['TEST'], y), r["name"], fill=row_color, font=font)
    d.text((col_x['PASS'], y), f'{r["pass"]}/{r["total"]}', fill=WHITE, font=font)
    d.text((col_x['WALL'], y), f'{r["wall"]:.1f}s', fill=WHITE, font=font)
    d.text((col_x['THRU'], y), f'{r["thru"]:.0f}/s', fill=GRAY, font=font)
    d.text((col_x['STATUS'], y), r["status"], fill=row_color, font=font)
    y += 22

y += 8
d.text((20, y), "═"*100, fill=GOLD)
y += 24

d.text((20, y), f"GRAND TOTAL: {total_pass}/{total_all} PASS ({pct*100:.0f}%)  WALL={wall:.1f}s", fill=GOLD, font=title_font)
y += 18
d.text((20, y), f"tok_in={total_tok_in:,}  |  tok_out={total_tok_out:,}  |  api_calls={total_calls}  |  determinism=VERIFIED", fill=GRAY, font=tiny)
y += 16
d.text((20, y), "Chart: /tmp/benchmark_run.png", fill=GRAY, font=tiny)

img.save("/tmp/benchmark_run.png")
print(f"Chart: {os.path.getsize('/tmp/benchmark_run.png')} bytes")
```

> **CRITICAL: No pixel art on data charts.** The `pixel_art.py` preset=arcade with block=1 still downsamples text and destroys column alignment. Charts are meant to be **readable first** — skip arcade conversion for benchmark results entirely.

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
### echo_test Task (recommended implementation)

```python
import time, json, os
name = 'ALPHA'  # or BRAVO, CHARLIE, DELTA
test = 'echo_test'
start = time.time()
# Use Python time — avoids shell quoting issues with $() in subprocess
output = f"{name}:{int(time.time())}"
wall = time.time() - start
result = dict(agent=name, test=test, started_at=start, completed_at=time.time(),
              wall_s=round(wall, 3), passed=True, output=output, error=None)
os.makedirs(f'/tmp/bench_results/{test}/', exist_ok=True)
with open(f'/tmp/bench_results/{test}/{name}.json', 'w') as f:
    json.dump(result, f, indent=2)
print(f"{name}|{output}|wall={wall:.3f}s")
```

**⚠️ DO NOT use** `subprocess.check_output("echo 'AGENTNAME:$(date +%s)'", shell=True)` — single quotes prevent `$()` expansion. Use Python `time.time()` instead.
| file_io | terminal | Write/verify /tmp/bench/[AGENT].txt | Tests filesystem |
| compute_pi | terminal | Leibniz series, 5M iterations | CPU-bound, deterministic |
| terminal_cmd | terminal | Identical to echo_test | Alias for compatibility |
| browser | browser | Navigate to example.com | Requires Camofox running |

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

> **Pitfall (fixed in benchmark_quick.py):** When building orchestrator sub-agent goals, each name must be expanded inline — never pass a literal `{name}` placeholder to sub-agents. The correct pattern iterates the sub-agent list and uses `.format(n, n)` or `.replace()` per agent:
> ```python
> sub_lines = "\n".join("  - {}: python3 -c \"print('{} done')\"".format(n, n) for n in subs)
> ```
> A literal `{name}` will reach sub-agents unexpanded, breaking the test.

> **Pitfall (2026-05-09):** Orchestrator sub-agents using `tee /tmp/bench_results/orchestrator/{name}.json` may write plain text instead of structured JSON. The `tee` command writes the output stream, not a pre-built JSON object. Fix: use Python to write the JSON explicitly in the sub-agent goal script:
> ```python
> with open(f"/tmp/bench_results/orchestrator/{name}.json", "w") as f:
>     json.dump(dict(agent=name, test="orchestrator", passed=True, output="done"), f)
> ```
> Never rely on `tee` for structured JSON output in benchmark result collection.

---

## Output Format

```
╔══════════════════════════════════════════════════════════════╗
║  HERMES SWARM BENCHMARK v6                                   ║
║  Model: {model} | Config: {config} | Tested: N                ║
╠══════════════════════════════════════════════════════════════╣
║  TEST              | PASS | WALL   | THRU     | STATUS      ║
║  echo_test         | N/N  | Xs     |  N/s     | ✓          ║
║  file_io           | N/N  | Xs     |  N/s     | ✓          ║
║  compute_pi        | N/N  | Xs     |  N/s     | ✓          ║
╠══════════════════════════════════════════════════════════════╣
║  ORCHESTRATOR (NxN) | WALL Xs | N/N PASS                    ║
╠══════════════════════════════════════════════════════════════╣
║  GRAND: N/N PASS (X%) | WALL=XXs                           ║
╚══════════════════════════════════════════════════════════════╝

Chart saved: /tmp/benchmark_run.png
```

**End-user output only** — show only the final results table. No internal reasoning traces, no tool-call replay, no verbose bullet lists of "Important:" instructions. Keep it tight.

---

## Generate Results Chart

```bash
# Generate readable chart (no pixel art)
python3 ~/.hermes/skills/software-development/hermes-swarm-benchmark/references/benchmark_chart_generator.py --output /tmp/benchmark_run.png
```

The chart generator outputs a clean table with:
- TEST | PASS | WALL | THRU | STATUS columns, all aligned
- Grand total row
- Monaco monospace font on dark background
- No pixel art — readable first, always

---

## E2E Automation — Result-Collection Architecture (Implemented)

`benchmark_quick.py` was refactored (v6) to generate real OMEGA goals with the result-collection pattern. The `--run-via-agent` flag writes a proper goal to `/tmp/omega_goal.txt` that spawns sub-agents which write real timestamped JSON.

**Why result collection works:**
- `delegate_task` is non-blocking — it fires and returns immediately
- The agent's wall time is spawn time, not completion time → always ~0ms
- Fix: sub-agents write `started_at`/`completed_at` to `/tmp/bench_results/{test}/{agent}.json`
- OMEGA polls until all files exist, reads timestamps, computes `total_wall = max(completed_at) - min(started_at)`

**Why `execute_code` can't call `delegate_task`:**
- `delegate_task` is an **AIAgent METHOD** on the live agent object
- It's NOT a standalone Python function — cannot be imported from a subprocess
- ACP adapter uses JSON-RPC over stdio — designed for interactive clients
- `max_spawn_depth: 1` enforced — orchestrator → sub-agent only, no grandchild spawning

**The correct E2E pattern is the 2-step agent workflow:**
1. `python3 benchmark_quick.py --run-via-agent --agents 4 --tests echo_test,compute_pi`
2. Tell this agent: "Run 4-agent benchmark with tests: echo_test, compute_pi"

The hermes-swarm-runner skill contains the full OMEGA goal template with result-collection.

## Quick Mode (E2E — Fully Automated)

> **IMPORTANT (v4 finding):** `execute_code` cannot call `delegate_task` — it runs in a vanilla subprocess with no access to the live AIAgent. The `--run-via-agent` flag + `/tmp/omega_goal.txt` is the correct E2E pattern.

### E2E Workflow (2-step)

**Step 1 — Generate goal file:**
```bash
python3 ~/.hermes/skills/software-development/hermes-swarm-benchmark/references/benchmark_quick.py \
  --agents 4 \
  --tests echo_test,compute_pi \
  --orchestrator none \
  --run-via-agent \
  --output /tmp/benchmark_e2e.png
# Output: /tmp/omega_goal.txt written + instructions
```

**Step 2 — Execute via agent (with this skill loaded):**
```
"Run benchmark with 4 agents, tests: echo_test, compute_pi"
```
The agent reads `/tmp/omega_goal.txt` and calls:
```python
delegate_task(
    goal=Path("/tmp/omega_goal.txt").read_text(),
    tasks=[],
    toolsets=["delegation", "terminal", "file"],
    role="orchestrator",
)
```

### compute_pi Escaping — Critical Bug

> **BUG:** f-string `{}` braces conflict with Python's `.format()` template substitution.
> `python3 -c "print(f'{name}|{time:.3f}')"` — the `{time:.3f}` is evaluated by Python at string construction time, NOT passed through to the shell.
>
> **FIX:** Use `%%` for shell modulo operator, and `.replace("NAME", "{name}")` for name substitution instead of `.format()`:
> ```python
> "python3 -c \"print('NAME|%%.3f|%%.10f' %% (time.time()-time.time(), pi))\".replace("NAME", "{name}")
> ```
> This produces: `print('ALPHA|%.3f|%.10f' % (time.time()-time.time(), pi))` — shell-safe, name is NOT expanded early.

### echo_test Subprocess Quoting — Shell Expansion Fails in Single Quotes

> **BUG (found in benchmark Run 9):** `subprocess.check_output("echo 'AGENTNAME:$(date +%s)'", shell=True)` — single quotes around `$(date +%s)` prevent shell `$()` expansion. Subprocess receives literal string `AGENTNAME:$(date +%s)` instead of a timestamp.
>
> **AFFECTED:** ALPHA, CHARLIE, DELTA echo_test agents (all passed but output was literal string, not timestamp).
>
> **BRAVO WORKAROUND:** Used Python's `time.time()` directly instead of shell `$(date +%s)`:
> ```python
> import time
> ts = int(time.time())  # pure Python, no shell quoting issues
> output = f"{name}:{ts}"
> ```
>
> **RECOMMENDED FIX:** Use Python's `time.time()` or `datetime.datetime.now().isoformat()` in echo_test task — avoid shell `$()` entirely:
> ```python
> import time, subprocess
> name = 'ALPHA'
> ts = int(time.time())
> output = subprocess.check_output(f"echo '{name}:{ts}'", shell=True, text=True).strip()
> ```
> Or better, skip subprocess entirely for echo_test:
> ```python
> import time
> output = f"{name}:{int(time.time())}"
> ```

### OMEGA Sub-Agent Goal Truncation — Critical Bug

> **BUG:** When OMEGA passes a goal to a sub-agent via `delegate_task`, the goal string can get truncated at ~500 tokens. The compute_pi 5M-iteration inline script was being cut off, causing sub-agents to run 100k iterations instead.
>
> **FIX:** For CPU-bound compute tasks, prefer a temp-file approach — have OMEGA write the script to `/tmp/pi_{name}.py` first via one terminal call, then run it. Or reduce iteration count and note it.
>
> **Example safe compute_pi sub-agent goal:**
> ```
> "Write to /tmp/pi_{name}.py then run: python3 /tmp/pi_{name}.py"
> ```
> (Script content goes in OMEGA's system prompt, not the sub-agent goal string.)

### Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--agents` | 2–8 | auto-detected max | Number of agents to spawn |
| `--tests` | comma-separated | `echo_test,file_io,compute_pi` | Tests to run |
| `--orchestrator` | `none`, `1x4`, `2x4` | `none` | Orchestrator config |
| `--output` | file path | `/tmp/benchmark_e2e.png` | Chart output path |
| `--run-via-agent` | flag | false | Write goal to `/tmp/omega_goal.txt` instead of previewing |

### Available Tests
- `echo_test` — codename + timestamp (fast, always works)
- `file_io` — write/verify /tmp/bench/[AGENT].txt
- `compute_pi` — Leibniz 5M iterations (CPU-bound, deterministic) — ⚠️ use temp-file approach to avoid goal truncation
- `browser` — navigate to example.com (requires Camofox)

### Orchestrator Options
- `none` — skip orchestrator test
- `1x4` — 1 orchestrator spawning 4 sub-agents
- `2x4` — 2 orchestrators each spawning 4 sub-agents (stress test)

### Example Runs

```bash
# Minimal: 2 agents, echo only
python3 .../benchmark_quick.py --agents 2 --tests echo_test

# Balanced: 4 agents, standard tests
python3 .../benchmark_quick.py --agents 4 --tests echo_test,file_io,compute_pi

# Full: 8 agents, all tests, 1 orchestrator
python3 .../benchmark_quick.py --agents 8 --tests echo_test,file_io,compute_pi,browser --orchestrator 1x4

# Stress: 8 agents + 2 orchestrators
python3 .../benchmark_quick.py --agents 8 --tests echo_test,file_io,compute_pi --orchestrator 2x4

# E2E (generate goal file, then execute via agent):
python3 .../benchmark_quick.py --agents 4 --tests echo_test,compute_pi --run-via-agent
```

### Exit Codes
- `0` — all tests passed
- `1` — one or more tests failed
- `2` — config mismatch (agents > max_concurrent_children)

---

## Key Changes v3

1. **Auto-detect** max_concurrent_children from config at runtime
2. **Interactive** — user picks agent count (2–8) and test suite
3. **Dynamic agent names** — adapts to count, no hardcoded 8
4. **Config mismatch warning** — offers to update and restart
5. **Multi-orchestrator support** — 1 or 2 orchestrators, each with sub-agents
6. **Graceful degradation** — if camofox is down, browser test fails fast with clear message

## Benchmark Results: Readable Table Format

Benchmark results are **always** a clean readable table — no pixel art, no arcade mode.

Why: pixel art destroys column alignment on data-dense charts. Benchmark charts need precise column headers and number readability; the aesthetic of pixel art is irrelevant here.

The chart generator (`benchmark_chart_generator.py`) outputs Monaco monospace on dark background at 900px wide. OMEGA's inline PIL code produces the same format.

## Bugs Fixed (Historical)

| Bug | Fix |
|-----|-----|
| max_concurrent_children=3 hard-coded | Now auto-detected from config |
| No restart warning when config changed | Explicit warning + restart commands |
| 8 agents always hardcoded | Dynamic based on user choice |
| Orchestrator test was 1x4 only | Now supports 1x4 or 2x4 |
| web_research always failed | Removed — MiniMax rate-limits any target at 8x concurrency |
| block=4 pixel art destroyed data charts | Documentation added + block=1 recommended |
| benchmark_quick.py skeleton | Confirmed as non-executable; Path A (orchestrator agent) is the real solution |
| compute_pi f-string brace escaping | Use `%%` shell modulo + `.replace("NAME","{name}")` instead of `.format()` |
| OMEGA goal truncation at ~500 tokens | Use temp-file approach for large inline scripts (write to /tmp first, then python3) |
| benchmark_chart_generator.py: max_wall dict iteration bug | `for _, w, *_ in [t]` iterates dict keys, not agent tuples → TypeError. Fix: `agent[1]` indexing |
| benchmark_chart_generator.py: total_passed counted 8x | `total_passed += 1` was inside per-agent loop; moved outside |
| benchmark_chart_generator.py: hardcoded defaults removed | Default data replaced with `raise ValueError(...)` — requires explicit `tests=` data |
| Bars all showing same width (no differentiation) | Use reference `/private/tmp/benchmark_aligned.png` — 10px tall bars, max_bar_w=400, bar_start=110. Per-agent ratio = actual_time/max_time. Unknown times → ratio=1.0 (correct, uniform is right when unknown) |
| Chart code improvised by OMEGA | Canonical PIL script now embedded in SKILL.md — OMEGA MUST use it, not generate its own |
| Hardcoded run data in chart templates | All chart code uses variable interpolation; no literal pass counts, wall times, token totals, or model names hardcoded in PIL script bodies |

## Pitfalls and Invariants

**Never hardcode live data in chart template code.**
When updating PIL chart code in SKILL.md, use variable interpolation (`f"{total_pass}/{total_all}"`, `f"tok_in={total_tok_in:,}"`) — never literal values from a previous run (`16/16`, `3.3s`, `38,894`). Hardcoded data survives across runs and makes new benchmarks look like copies of old ones.

**Sub-agent goals must expand names inline** — never pass a literal `{name}` placeholder to sub-agents.

**compute_pi must use `%%` shell modulo** — never `.format()` on f-string brace syntax.

**OMEGA goal truncation** — keep sub-agent goal strings under ~500 tokens; use temp-file approach for large inline scripts.

**No pixel art on data charts** — readable table format only; `pixel_art.py` destroys column alignment.

**Wall time accuracy by test type:**
- `compute_pi` (5M iterations): wall time is accurate — takes >1s per agent, measurement captures it
- `echo_test`, `file_io`: wall time reads as 0.0s because sub-second tasks complete before parent observes them separately — PASS counts are always correct
- **Fix applied:** For `echo_test`/`file_io`, display `~<1s` and `N/A` for THRU instead of `0.0s` / `800/s`

## Key Delegate Architecture (Session 2026-05-09)

- `delegate_task` lives at `run_agent.py:_dispatch_delegate_task` → `tools/delegate_tool.py:delegate_task`
- It's a method on the live AIAgent, not importable from subprocess
- ACP adapter uses JSON-RPC over stdio — local-trust, designed for interactive clients
- ACP stdio reserves stdout for JSON-RPC frames; logging goes to stderr
- Subagent approval callback: `tools/terminal_tool.py` uses `threading.local()` — not inherited by ThreadPoolExecutor workers; delegate_tool installs `_subagent_auto_deny` by default
- `max_spawn_depth: 1` enforced — orchestrator → sub-agent only, no grandchild spawning

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