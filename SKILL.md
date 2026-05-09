---
name: hermes-swarm-benchmark
description: "Run a configurable concurrent agent benchmark suite for Hermes Agent — auto-detects max agents, lets the user pick count (2–8), optional multi-orchestrator stress test. Results emitted as a polished Markdown report. The renderer never fabricates pass rows: missing results render as explicit `missing` failures."
version: 6.2.0
author: hzang12345-ship-it
license: MIT
homepage: https://github.com/hzang12345-ship-it/hermes-swarm-benchmark
platforms: [macos, linux]
metadata:
  hermes:
    tags: [benchmark, swarm, delegation, concurrent-agents, interactive]
    category: software-development
---

# Hermes Swarm Benchmark

Interactive, user-configurable concurrent agent benchmark. Auto-detects your
configured `max_concurrent_children`, lets the user choose how many agents to
test, and includes an optional multi-orchestrator stress test.

## Discovery / install

This skill lives at the root of the public repository
[hermes-swarm-benchmark](https://github.com/hzang12345-ship-it/hermes-swarm-benchmark).

**Install into a Hermes harness (recommended):**

```bash
git clone https://github.com/hzang12345-ship-it/hermes-swarm-benchmark.git
cd hermes-swarm-benchmark
./scripts/install_skill.sh --apply        # default dest: ~/.hermes/skills/software-development/hermes-swarm-benchmark
pip install -e .                          # so the skill can call hermes-benchmark / hermes-benchmark-report
```

The install script is a copy-only operation with `--dry-run` by default; it
never edits `~/.hermes/config.yaml` or any other user config.

If your harness expects skills under a different path, pass `--dest <path>`
or copy `SKILL.md` and `src/` manually. Hermes loads the skill from
whichever directory it ends up in — the SKILL.md file at the repo root is
the canonical, installable artifact.

## Hermes Harness Contract

This skill *generates* files; the Hermes harness is what actually
*executes* the OMEGA orchestrator and its sub-agents.

| Step | Runs in | Writes |
|---|---|---|
| `hermes-benchmark …` | plain Python (this package) | `omega_goal.txt`, `<results-dir>/manifest.json` |
| OMEGA orchestrator | Hermes harness (`delegate_task`) | spawns sub-agents per the goal text |
| Each sub-agent | Hermes harness terminal toolset | `<results-dir>/{test}/{agent}.json` (atomic) |
| `hermes-benchmark-report …` | plain Python (this package) | `REPORT.md` (+ optional `report.json`) |

### Report contract — no fabricated rows

The renderer **never invents pass/success rows**. Every `(test, agent)`
pair listed in `manifest.json` produces exactly one row in `REPORT.md`:

- If the sub-agent wrote a JSON, the row reflects it verbatim.
- If no JSON exists, the row is rendered as `passed=false`,
  `error="missing result file"`, with a literal `missing` marker in the
  per-test detail table.

Concretely:

- A `REPORT.md` rendered before any agent runs is a **fully populated
  failure report** — every row reads `missing`. It is *not* an empty
  stub, and it is *not* a fake success.
- Pass rows only ever appear when a real sub-agent wrote `passed: true`.

Sub-agents that cannot run should still write a JSON with `passed=false`
and a meaningful `error` — that produces a richer failure row than the
synthesised `missing result file` placeholder. The OMEGA goal text from
`hermes-benchmark` repeats this invariant explicitly to sub-agents.

## End-user output

When the orchestrator finishes, surface the grand-total line and the
report path. No reasoning traces, no tool-call replay, no verbose
"Important:" instruction bullets.

```
Hermes Swarm Benchmark — N/M passed in T.Ts
  Report: REPORT.md
```

`REPORT.md` is the canonical artifact — open it in any Markdown viewer or
let GitHub render it. **No PNG output is produced.** If a chart is
needed, plot from `report.json` with a separate tool.

---

## Step 0: Auto-detect config

Before the skill says anything to the user, silently check the current
`max_concurrent_children` from config:

```bash
DETECTED=$(grep max_concurrent_children ~/.hermes/config.yaml | awk '{print $2}')
```

- Default Hermes: `3`
- After the operator's fix: `8`
- User might have set anything between 2–8

The Python CLI does the same lookup automatically (`get_configured_max_agents`).

## Step 1: Pick agent count and tests

Offer the user a quick interactive prompt:

- agent count (2–8, default = detected max)
- tests (default: `echo_test,file_io,compute_pi`)
- orchestrator topology (`none` / `1x4` / `2x4`)

If user says `n`, let them adjust any choice. If `y`, proceed to Step 2.

## Step 2: Config mismatch warning

If the user picked an agent count that exceeds currently configured
`max_concurrent_children`:

```
⚠️  Config mismatch detected.
    You chose {USER_CHOICE} agents but config has max_concurrent_children: {CURRENT}.

Options:
  1) Update config to {USER_CHOICE} and restart gateway (recommended)
  2) Run with current {CURRENT} agents instead
  3) Keep config but cap at {USER_CHOICE} (will fail if {CURRENT} < {USER_CHOICE})
```

This skill does **not** edit `~/.hermes/config.yaml` automatically. If the
user picks option 1, surface the explicit commands and let them run them:

```bash
# macOS:
sed -i '' "s/^  max_concurrent_children: [0-9]*/  max_concurrent_children: {USER_CHOICE}/" ~/.hermes/config.yaml
launchctl unload ~/Library/LaunchAgents/ai.hermes.gateway.plist
launchctl load   ~/Library/LaunchAgents/ai.hermes.gateway.plist
```

## Step 3: Run

Once the config is valid and the user confirms, generate the OMEGA goal:

```bash
hermes-benchmark --agents {USER_CHOICE} \
    --tests echo_test,file_io,compute_pi \
    --orchestrator none \
    --goal-out /tmp/omega_goal.txt \
    --results-dir /tmp/bench_results
```

This writes:

- `/tmp/omega_goal.txt` — the OMEGA goal text.
- `/tmp/bench_results/manifest.json` — selected agents/tests/orchestrator.

Then have OMEGA execute the goal text via `delegate_task`. Sub-agents
will write `/tmp/bench_results/{test}/{agent}.json` (atomic writes, 60s
timeout per workload).

Agent naming by count:

| Count | Names used |
|-------|-----------|
| 2 | ALPHA, BRAVO |
| 3 | ALPHA..CHARLIE |
| 4 | ALPHA..DELTA |
| 5 | ALPHA..ECHO |
| 6 | ALPHA..FOXTROT |
| 7 | ALPHA..GOLF |
| 8 | ALPHA..HOTEL |

### Render the report

```bash
hermes-benchmark-report \
    --results-dir /tmp/bench_results \
    --out REPORT.md \
    --json report.json
```

Or invoke as a module if the script is not on `$PATH`:

```bash
python -m hermes_benchmark.report \
    --results-dir /tmp/bench_results \
    --out REPORT.md --json report.json
```

`REPORT.md` is the primary artifact:

- PASS / FAIL / NO RESULTS banner and grand-total wall time.
- Run configuration (agent count, orchestrator, model, test count).
- Environment (Python version, platform, generation timestamp).
- Summary table per test (pass/total/wall/throughput) with a totals row.
- Per-test detail tables with started/completed timestamps per agent.
- Failures section with error message and last output (or "None" when
  every real agent passed).
- Reproduce block with the exact CLI commands.
- Raw data pointers to the per-agent JSON files and aggregated `report.json`.

`report.json` is optional, written only when `--json` is supplied —
useful for downstream tooling but not required for human review.

Sub-agent names for orchestrator stress tests:

- Orchestrator 1 spawns: ALPHA, BRAVO, CHARLIE, DELTA
- Orchestrator 2 spawns: ECHO, FOXTROT, GOLF, HOTEL

---

## Available tests

| Test | Toolset | Task | Notes |
|------|---------|------|-------|
| `echo_test` | terminal | codename + timestamp | fast, always works |
| `file_io` | terminal | write/verify `/tmp/bench/[AGENT].txt` | tests filesystem |
| `compute_pi` | terminal | Leibniz series, 5M iterations | CPU-bound, deterministic |
| `terminal_cmd` | terminal | alias for echo_test | back-compat |
| `browser` | browser | not implemented; runs `echo 'browser_skipped'` so the row is honest, not fabricated |

### Recommended echo_test sub-agent body

The Python package generates this for you (see
`hermes_benchmark.tasks.make_goal`). For reference, a hand-written
equivalent:

```python
import time, json, os
name = 'ALPHA'    # or BRAVO, CHARLIE, ...
test = 'echo_test'
start = time.time()
output = f"{name}:{int(time.time())}"
wall = time.time() - start
result = dict(agent=name, test=test, started_at=start, completed_at=time.time(),
              wall_s=round(wall, 3), passed=True, output=output, error=None)
os.makedirs(f'/tmp/bench_results/{test}/', exist_ok=True)
with open(f'/tmp/bench_results/{test}/{name}.json', 'w') as f:
    json.dump(result, f, indent=2)
print(f"{name}|{output}|wall={wall:.3f}s")
```

> ⚠️ **Do not** use
> `subprocess.check_output("echo 'AGENTNAME:$(date +%s)'", shell=True)` —
> single quotes prevent `$()` expansion. Use Python `time.time()` instead.

### Orchestrator stress test pattern

```python
delegate_task(
    goal="""You are OMEGA-1. Spawn 4 named sub-agents (ALPHA, BRAVO, CHARLIE, DELTA).
    Each sub-agent runs: python3 -c "import time; print('SUB_AGENT done')".
    Wait for all 4 to complete, then report:
    OMEGA-1 | wall_time | spawned: 4 | completed: N | failed: Z""",
    toolsets=["delegation", "terminal"],
)
```

> **Pitfall:** When building orchestrator sub-agent goals, each name must
> be expanded inline — never pass a literal `{name}` placeholder to
> sub-agents:
>
> ```python
> sub_lines = "\n".join(
>     "  - {}: python3 -c \"print('{} done')\"".format(n, n) for n in subs
> )
> ```
>
> A literal `{name}` will reach sub-agents unexpanded, breaking the test.

> **Pitfall:** Orchestrator sub-agents using
> `tee /tmp/bench_results/orchestrator/{name}.json` may write plain text
> instead of structured JSON. Use Python to write JSON explicitly:
>
> ```python
> with open(f"/tmp/bench_results/orchestrator/{name}.json", "w") as f:
>     json.dump(dict(agent=name, test="orchestrator", passed=True, output="done"), f)
> ```
>
> Never rely on `tee` for structured JSON in benchmark result collection.

---

## CLI reference

`hermes-benchmark`:

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--agents` | 1–8 | auto-detected max | Number of agents to spawn |
| `--tests` | comma-separated | `echo_test,file_io,compute_pi` | Tests to run |
| `--orchestrator` | `none`, `1x4`, `2x4` | `none` | Orchestrator config |
| `--results-dir` | path | `/tmp/bench_results` | Where sub-agents write JSON; also where `manifest.json` lands |
| `--goal-out` | path | `/tmp/omega_goal.txt` | Where to write the OMEGA goal |
| `--model` | string | _(none)_ | Optional model id stored in manifest/report |

`hermes-benchmark-report`:

| Flag | Default | Description |
|------|---------|-------------|
| `--results-dir` | `/tmp/bench_results` | Per-agent result directory |
| `--out` | `REPORT.md` | Markdown report output (primary artifact) |
| `--json` | _(none)_ | Optional aggregated JSON output |

### Orchestrator options

- `none` — skip orchestrator test
- `1x4` — 1 orchestrator spawning 4 sub-agents
- `2x4` — 2 orchestrators each spawning 4 sub-agents (stress test)

### Example runs

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

### Exit codes

- `0` — all tests passed
- `1` — one or more tests failed
- `2` — config mismatch (agents > max_concurrent_children) or invalid input

---

## Why no PNG chart?

A previous PIL-based chart generator had multiple bugs and required a
font path that doesn't exist on Linux CI. PR #1 deleted it. Markdown is
more reviewable, diffs cleanly in Git, and renders in any PR. Pillow is
no longer a dependency. If a chart is needed, run a separate plotting
tool against `report.json` — that's a deliberate boundary.

## Pitfalls and invariants

**Sub-agent goals must expand names inline** — never pass a literal
`{name}` placeholder to sub-agents.

**`compute_pi` must use `%%` shell modulo** — not `.format()` on f-string
brace syntax.

**OMEGA goal truncation** — keep sub-agent goal strings under ~500
tokens; use a temp-file approach for large inline scripts.

**Wall-time accuracy by test type:**

- `compute_pi` (5M iterations): wall time is accurate — workload takes
  >1s per agent, measurement captures it.
- `echo_test`, `file_io`: wall time often reads as 0.0s because
  sub-second tasks complete before the parent observes them separately.
  Pass counts are always correct; wall time is informational only.

**No fabricated rows.** The renderer surfaces only what sub-agents
actually wrote (or an explicit `missing` row). It does not synthesise
successes, populate placeholder metrics, or backfill from defaults.
