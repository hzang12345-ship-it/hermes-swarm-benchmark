# hermes-swarm-benchmark

A concurrent-agent benchmark suite packaged as a **Hermes skill**. An OMEGA
orchestrator spawns sub-agents that run small workloads (echo, file I/O,
compute_pi, etc.) in parallel and write per-agent result JSONs. A Python
report renderer aggregates them into a Markdown `REPORT.md`.

## Why this exists

This started as a way to find out, in practice, what you can actually do
with a lower-tier AI subscription before the rate limits, queue depth, or
session caps bite. Marketing pages claim concurrency numbers; this suite
measures them under a Hermes-style swarm workload so different
subscription tiers (or different model backends) can be compared on the
same axis: agents launched, agents completed, wall-time, throughput, and
where it fell over. It's deliberately small — the value is in the
methodology and the honest reporting, not in the workloads themselves.

## What's in the repo

- `SKILL.md` — installable Hermes skill.
- `hermes_benchmark` Python package with two CLI entry points:
  - `hermes-benchmark` — generates the OMEGA goal text + a result manifest.
  - `hermes-benchmark-report` — renders `REPORT.md` from per-agent JSONs.
- A pytest suite that pins the contract: generated scripts always parse,
  atomic writes leave nothing behind, and every selected `(test, agent)`
  pair appears in the report — as a real result or an explicit `missing`
  failure row, never as a fabricated pass.

## How the pieces fit together

The Python package generates files. **The Hermes harness is what executes
the orchestrator and sub-agents.**

| Step | Runs in | Writes |
|---|---|---|
| `hermes-benchmark` | Plain Python (this package) | `omega_goal.txt`, `<results-dir>/manifest.json` |
| OMEGA orchestrator | Hermes harness (`delegate_task`) | spawns sub-agents per the goal text |
| Each sub-agent | Hermes harness terminal toolset | `<results-dir>/{test}/{agent}.json` (atomic) |
| `hermes-benchmark-report` | Plain Python (this package) | `REPORT.md` (+ optional `report.json`) |

This package does not spawn agents. There is no shortcut path that runs
the workloads in plain Python — without a Hermes harness, the only thing
this CLI produces is the goal text and a manifest.

## Requirements

- Python 3.10+.
- A Hermes harness exposing `delegate_task` and a terminal toolset, if you
  want to actually run the workloads.

No image / plotting dependencies.

## Install — Python package

```bash
git clone https://github.com/hzang12345-ship-it/hermes-swarm-benchmark.git
cd hermes-swarm-benchmark
pip install -e .[dev]
```

Exposes `hermes-benchmark` and `hermes-benchmark-report` on `$PATH`.

## Install — Hermes skill

The skill is `SKILL.md` at the repo root. Hermes loads skills from a
skills directory (typically `~/.hermes/skills/<category>/<skill-name>/`).

### Option A — install script (dry-run by default)

```bash
./scripts/install_skill.sh --dry-run        # preview, no changes
./scripts/install_skill.sh --apply          # copy SKILL.md + src/
./scripts/install_skill.sh --apply --dest ~/my-hermes/skills/benchmarks
```

The script is copy-only. It never edits `~/.hermes/config.yaml`.

### Option B — manual

```bash
mkdir -p ~/.hermes/skills/software-development/hermes-swarm-benchmark
cp SKILL.md ~/.hermes/skills/software-development/hermes-swarm-benchmark/
cp -R src    ~/.hermes/skills/software-development/hermes-swarm-benchmark/
```

Then `pip install -e .` so the skill can invoke the CLI.

## Quick start

```bash
# 1. Generate the OMEGA goal text and a results manifest.
hermes-benchmark --agents 4 --tests echo_test,compute_pi --orchestrator none

# 2. Have the OMEGA agent execute the goal inside the Hermes harness.
#    Sub-agents write /tmp/bench_results/{test}/{agent}.json (atomic, 60s timeout).

# 3. Render the report.
hermes-benchmark-report --results-dir /tmp/bench_results \
    --out REPORT.md --json report.json
```

## Output

| File | Written by | Default path |
|---|---|---|
| `omega_goal.txt` | `hermes-benchmark` | `/tmp/omega_goal.txt` (override with `--goal-out`) |
| `manifest.json` | `hermes-benchmark` | `<results-dir>/manifest.json` |
| `{test}/{agent}.json` | each sub-agent (inside Hermes) | `<results-dir>/{test}/{agent}.json` |
| `REPORT.md` | `hermes-benchmark-report` | `REPORT.md` (override with `--out`) |
| `report.json` | `hermes-benchmark-report` | only when `--json` is given |

`REPORT.md` contains: a status banner, run-config and environment tables,
a per-test summary, per-test detail rows, a failures section, and a
reproduce block.

## Report contract — no fabricated rows

Every `(test, agent)` pair listed in `manifest.json` produces exactly one
row in `REPORT.md`:

- If the sub-agent wrote a JSON, the row reflects its `passed` / `output`
  / `error` fields verbatim.
- If no JSON exists, the row renders as `passed=false`,
  `error="missing result file"`, with a literal `missing` marker.

A `REPORT.md` rendered before any agent runs is a fully populated failure
report — every row reads `missing`. It is not an empty stub and not a
fake success. A passing row only ever appears when a sub-agent wrote
`passed: true` itself.

The OMEGA goal text repeats this invariant to sub-agents.

### Banner status

| `grand_total` | `grand_passed == grand_total` | Banner |
|---|---|---|
| 0 | n/a | `NO RESULTS` |
| > 0 | yes | `PASS` |
| > 0 | no | `FAIL` |

## Available tests

| Name | Toolset | What it measures |
|---|---|---|
| `echo_test` | terminal | minimum spawn + return path |
| `file_io` | terminal | mkdir + write + cat |
| `compute_pi` | terminal | 5M-iter Leibniz, CPU-bound |
| `terminal_cmd` | terminal | alias for `echo_test` (back-compat) |
| `browser` | browser | not implemented — exits non-zero so the row is `passed=false`, never a fabricated success |

Unknown tests are rejected by the CLI (`--tests` validates against the
registry in [`tasks.py`](src/hermes_benchmark/tasks.py)).

## Benchmark logic analysis

Be honest about what the current suite does and does not measure. This
section is the practical reading of the workloads as they exist today.

### What today's tests do measure

| Test | Signal it produces | Limit |
|---|---|---|
| `echo_test` | sub-agent spawn → return path works at all | finishes in milliseconds; wall-time often reads `0.0` |
| `file_io` | local filesystem path is writable from the sub-agent | uses `/tmp/bench/`, no contention between agents |
| `compute_pi` | CPU-bound work across N agents in parallel | pure local CPU; no model tokens, no tool calls |
| `terminal_cmd` | nothing new (alias of `echo_test`) | redundant — kept only for back-compat |
| `browser` | placeholder slot — currently `passed=false` | does not test a browser at all |

### What today's tests do not measure

- **Model token throughput.** No workload sends any non-trivial prompt to
  the model. Concurrency limits at the model / API tier are invisible.
- **Tool-call latency.** No real tool round-trip — each sub-agent makes
  one shell call and exits. Long tool chains are uncovered.
- **Filesystem contention.** Each agent writes a different file in `/tmp`.
  Lock contention or shared-state correctness is uncovered.
- **Rate limits and backoff.** Workloads are too short and too local to
  hit any provider quota.
- **Long-context behaviour.** Nothing exercises the model's context
  window. A subscription that throttles long contexts looks the same as
  one that does not.
- **Error recovery.** Sub-agents either pass or fail and exit. Multi-step
  recovery (retry, re-plan, re-delegate) is not tested.
- **Browser / web automation.** The `browser` slot is a placeholder.

The headline number — *N of M agents passed, T seconds wall-time* — is a
real measurement of the spawn + return path under a given configuration.
It is not a measurement of model-side capacity. When comparing
subscription tiers, that distinction is the point of the suite, not a
caveat to it: the swarm-overhead floor and the model-throughput ceiling
are different signals, and right now this measures the floor.

### Recommended next test suite (roadmap)

Listed roughly in increasing order of value-per-effort. Each adds a
distinct axis of signal that the current workloads cannot produce.

| Test | What it would measure | Why it would matter for tier comparison |
|---|---|---|
| Token-heavy summarization | tokens/s across N agents on a fixed corpus | Reveals model-side throttling that local CPU work cannot |
| Tool-call latency loop | round-trip latency for a fixed tool, N times | Surfaces tool-execution overhead at concurrency |
| Filesystem contention | N agents append to one file under a lock | Tests serialization correctness, not just parallel throughput |
| Multi-step planning | plan → execute → verify, multiple steps | Catches tiers that allow concurrency but not depth |
| Rate-limit / backoff | drive past the documented quota, observe behaviour | Distinguishes graceful backoff from hard 429 |
| Error recovery | inject a failing sub-agent, require re-delegation | Tests orchestrator retry, not just spawn |
| Long-context handling | ask each agent to process a large document | Surfaces context-window throttling and truncation |
| Real browser task | open a URL, extract text | Replaces the current `browser` placeholder |

Adding any of these is intentionally deferred to a follow-up PR. The
current PR keeps the workloads small and the contract honest; the
roadmap above is the next reasonable expansion.

## Result schema

A single dataclass-backed schema lives in
[`src/hermes_benchmark/schema.py`](src/hermes_benchmark/schema.py):

```python
AgentResult(agent, test, started_at, completed_at, wall_s, passed, output, error)
RunManifest(agents, tests, orchestrator, results_dir, model, created_at)
```

Each sub-agent writes one `AgentResult` per `{test}/{agent}.json`. The
renderer groups them into `TestResult`s and a top-level `BenchmarkReport`.

## Why no PNG output

The previous Pillow-based chart generator had several bugs and required a
font path that does not exist on Linux CI. It was removed. Markdown is
diff-friendly and renders in any PR. If you want a chart, run a separate
plotting tool against `report.json`. Pillow is **not** a dependency.

## Tests

```bash
pytest
```

Coverage:

- Every generated task body parses with `ast.parse` for every test.
- The generated body actually runs end-to-end and writes valid JSON.
- The `browser` test records `passed=false` (no fabricated pass).
- Atomic writes leave no `.tmp` files behind on success.
- Unknown `--tests` and `..` in `--results-dir` are rejected.
- Markdown report contains the summary table, per-test detail, failures
  section, environment block, and reproduce command.
- An end-to-end run with no agent results renders every selected pair as
  a `missing` failure row.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `error: results_dir does not exist` | Run `hermes-benchmark` first to create it (and the manifest). |
| `NO RESULTS` banner | No manifest *and* no per-agent JSONs found. The Python CLI never ran or `--results-dir` is wrong. |
| Every row says `missing` | `hermes-benchmark` ran but the OMEGA orchestrator never executed (or sub-agents never wrote JSONs). |
| `error: invalid manifest in …` | `manifest.json` was hand-edited and is no longer valid JSON. Regenerate. |
| `unknown test(s)` from `--tests` | Typo. See the table above. |

## Layout

```
SKILL.md                        # installable Hermes skill
src/hermes_benchmark/
  __init__.py
  schema.py                     # AgentResult / TestResult / BenchmarkReport / RunManifest
  tasks.py                      # TASKS registry + safe goal-body generator
  cli.py                        # `hermes-benchmark` entry point + input validation
  report.py                     # `hermes-benchmark-report` entry point (Markdown-only)
scripts/install_skill.sh        # safe dry-run install helper
tests/                          # pytest suite (test fixtures only — never product output)
```

## Search keywords

`hermes` · `hermes-skill` · `agent-benchmark` · `swarm-benchmark` ·
`ai-harness` · `benchmark` · `concurrent-agents`

## Contributing / Security / License

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [CHANGELOG.md](CHANGELOG.md)
- MIT — see [LICENSE](LICENSE).
