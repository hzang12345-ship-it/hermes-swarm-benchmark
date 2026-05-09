---
name: hermes-swarm-benchmark
description: "Concurrent agent benchmark for Hermes — auto-detects max agents, lets the user pick a count (2–8), optional multi-orchestrator stress test. Renders a Markdown report. Missing results render as explicit `missing` failure rows; the renderer never fabricates a pass."
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

Interactive concurrent-agent benchmark. Auto-detects the harness's
configured `max_concurrent_children`, lets the user pick a count, and
optionally adds a multi-orchestrator stress test.

For full background — what the workloads do and don't measure, the
roadmap of next tests, and the report contract — see the public
[README](https://github.com/hzang12345-ship-it/hermes-swarm-benchmark).
This file is the skill manifest plus the runtime steps.

## Install

```bash
git clone https://github.com/hzang12345-ship-it/hermes-swarm-benchmark.git
cd hermes-swarm-benchmark
./scripts/install_skill.sh --apply        # default dest: ~/.hermes/skills/software-development/hermes-swarm-benchmark
pip install -e .                          # so the skill can call hermes-benchmark / hermes-benchmark-report
```

The install script is copy-only, dry-run by default; it never edits
`~/.hermes/config.yaml`. If your harness expects a different path, pass
`--dest <path>` or copy `SKILL.md` and `src/` manually.

## Harness contract

The Python package generates files; the Hermes harness executes the
OMEGA orchestrator and its sub-agents.

| Step | Runs in | Writes |
|---|---|---|
| `hermes-benchmark` | plain Python (this package) | `omega_goal.txt`, `<results-dir>/manifest.json` |
| OMEGA orchestrator | Hermes harness (`delegate_task`) | spawns sub-agents per the goal text |
| Each sub-agent | Hermes harness terminal toolset | `<results-dir>/{test}/{agent}.json` (atomic) |
| `hermes-benchmark-report` | plain Python (this package) | `REPORT.md` (+ optional `report.json`) |

**Report contract.** Every `(test, agent)` pair listed in `manifest.json`
gets exactly one row. Real result JSONs are surfaced verbatim; missing
ones render as `passed=false`, `error="missing result file"`. A pass row
only appears when a sub-agent itself wrote `passed: true`.

Sub-agents that cannot run should still write a JSON with `passed=false`
and a meaningful error — that is a richer failure row than the
synthesised `missing result file` placeholder. The OMEGA goal repeats
this invariant to sub-agents.

## End-user output

When the orchestrator finishes, surface the grand-total line and the
report path. No reasoning traces or tool-call replay.

```
Hermes Swarm Benchmark — N/M passed in T.Ts
  Report: REPORT.md
```

`REPORT.md` is the canonical artifact. **No PNG output is produced.**

## Step 1 — Auto-detect config

Before prompting, silently read `max_concurrent_children`:

```bash
DETECTED=$(grep max_concurrent_children ~/.hermes/config.yaml | awk '{print $2}')
```

The Python CLI does the same lookup automatically
(`get_configured_max_agents`).

## Step 2 — Pick agent count and tests

Offer:

- agent count (2–8, default = detected max)
- tests (default: `echo_test,file_io,compute_pi`)
- orchestrator topology (`none` / `1x4` / `2x4`)

## Step 3 — Config mismatch warning

If the user picked an agent count above currently configured
`max_concurrent_children`:

```
Config mismatch: chose {USER_CHOICE} agents but config has max_concurrent_children: {CURRENT}.

Options:
  1) Update config to {USER_CHOICE} and restart gateway (recommended)
  2) Run with current {CURRENT} agents instead
  3) Keep config but cap at {USER_CHOICE} (will fail if {CURRENT} < {USER_CHOICE})
```

This skill does **not** edit `~/.hermes/config.yaml`. If the user picks
option 1, surface the explicit commands and let them run them:

```bash
# macOS:
sed -i '' "s/^  max_concurrent_children: [0-9]*/  max_concurrent_children: {USER_CHOICE}/" ~/.hermes/config.yaml
launchctl unload ~/Library/LaunchAgents/ai.hermes.gateway.plist
launchctl load   ~/Library/LaunchAgents/ai.hermes.gateway.plist
```

## Step 4 — Run

Once config is valid:

```bash
hermes-benchmark --agents {USER_CHOICE} \
    --tests echo_test,file_io,compute_pi \
    --orchestrator none \
    --goal-out /tmp/omega_goal.txt \
    --results-dir /tmp/bench_results
```

This writes `/tmp/omega_goal.txt` (the OMEGA goal) and
`/tmp/bench_results/manifest.json`. Have OMEGA execute the goal via
`delegate_task`. Sub-agents will write
`/tmp/bench_results/{test}/{agent}.json` (atomic, 60s timeout per
workload).

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

Orchestrator stress mode names:

- Orchestrator 1 spawns: ALPHA, BRAVO, CHARLIE, DELTA
- Orchestrator 2 spawns: ECHO, FOXTROT, GOLF, HOTEL

## Step 5 — Render the report

```bash
hermes-benchmark-report \
    --results-dir /tmp/bench_results \
    --out REPORT.md \
    --json report.json
```

Or as a module if the script is not on `$PATH`:

```bash
python -m hermes_benchmark.report \
    --results-dir /tmp/bench_results \
    --out REPORT.md --json report.json
```

`report.json` is optional and only written when `--json` is supplied.

---

## Available tests

| Test | Toolset | Workload | Notes |
|------|---------|----------|-------|
| `echo_test` | terminal | codename + timestamp | fast smoke test |
| `file_io` | terminal | write/verify `/tmp/bench/[AGENT].txt` | local FS |
| `compute_pi` | terminal | Leibniz series, 5M iterations | CPU-bound, deterministic |
| `terminal_cmd` | terminal | alias for `echo_test` | back-compat only |
| `browser` | browser | not implemented; sub-agent exits non-zero so the row is `passed=false` (no fabricated pass) |

See the README's *Benchmark logic analysis* section for what these tests
do and do not measure, and the recommended next-test roadmap.

## CLI reference

`hermes-benchmark`:

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--agents` | 1–8 | auto-detected max | Number of agents to spawn |
| `--tests` | comma-separated | `echo_test,file_io,compute_pi` | Tests to run |
| `--orchestrator` | `none`, `1x4`, `2x4` | `none` | Orchestrator topology |
| `--results-dir` | path | `/tmp/bench_results` | Where sub-agents write JSON; also where `manifest.json` lands |
| `--goal-out` | path | `/tmp/omega_goal.txt` | Where to write the OMEGA goal |
| `--model` | string | _(none)_ | Optional model id stored in manifest/report |

`hermes-benchmark-report`:

| Flag | Default | Description |
|------|---------|-------------|
| `--results-dir` | `/tmp/bench_results` | Per-agent result directory |
| `--out` | `REPORT.md` | Markdown report output |
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

## Pitfalls and invariants

- **Sub-agent goals must expand names inline** — never pass a literal
  `{name}` placeholder to sub-agents.
- **Wall-time accuracy by test type:**
  - `compute_pi` (5M iterations): wall time is accurate — workload takes
    >1s per agent.
  - `echo_test`, `file_io`: wall time often reads `0.0s` because
    sub-second tasks complete before the parent observes them
    separately. Pass counts are correct; wall time is informational.
- **No fabricated rows.** The renderer surfaces only what sub-agents
  actually wrote (or an explicit `missing` row). It does not synthesise
  successes, populate placeholder metrics, or backfill from defaults.
