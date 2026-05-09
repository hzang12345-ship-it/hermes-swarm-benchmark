# hermes-swarm-benchmark

A concurrent-agent benchmark suite packaged as a **Hermes skill**. Sub-agents
spawned by an OMEGA orchestrator run small workloads (echo, file IO,
compute_pi, etc.) in parallel and write per-agent result JSONs; a Python
report renderer aggregates the data into a polished Markdown `REPORT.md`.

> **Status (PR #1):** production-readiness pass. Generated agent scripts
> always parse, results are atomic, the report is always populated for every
> selected `(test, agent)` pair (real result OR explicit `missing` row), and
> there are no PNG/font dependencies.

## What this repo gives you

- A `SKILL.md` you can install into a Hermes harness so users can invoke
  the benchmark as a skill.
- A small Python package (`hermes_benchmark`) with two CLI entry points:
  - `hermes-benchmark` — generates an OMEGA goal text + a result manifest.
  - `hermes-benchmark-report` — renders `REPORT.md` from per-agent JSONs.
- A test suite that pins the contract: generated scripts parse, atomic
  writes leave nothing behind, and the report is fully populated even when
  no agent has run yet (every selected pair shows up as `missing`).

## Search keywords

`hermes` · `hermes-skill` · `agent-benchmark` · `swarm-benchmark` ·
`ai-harness` · `benchmark` · `concurrent-agents`

## Requirements

- Python 3.10+
- A working Hermes harness (any version that exposes `delegate_task` and a
  terminal toolset). The Python CLI runs anywhere — but the actual
  benchmark workloads only execute when an OMEGA orchestrator runs the
  generated goal text inside Hermes.

No image/plotting dependencies. Markdown only.

## Install — Python package

For local development or to run the report renderer outside Hermes:

```bash
git clone https://github.com/hzang12345-ship-it/hermes-swarm-benchmark.git
cd hermes-swarm-benchmark
pip install -e .[dev]
```

This exposes `hermes-benchmark` and `hermes-benchmark-report` on `$PATH`.

## Install — Hermes skill

The skill is `SKILL.md` at the repo root. Hermes loads skills from a
skills directory (typically `~/.hermes/skills/<category>/<skill-name>/`).

### Option A — recommended install script (dry-run by default)

```bash
# Preview what would be copied (no changes made):
./scripts/install_skill.sh --dry-run

# Copy SKILL.md and src/ helpers into ~/.hermes/skills/...:
./scripts/install_skill.sh --apply

# Custom destination:
./scripts/install_skill.sh --apply --dest ~/my-hermes/skills/benchmarks
```

The script never edits user config (`~/.hermes/config.yaml`). It only
copies files into the destination directory.

### Option B — manual install

```bash
mkdir -p ~/.hermes/skills/software-development/hermes-swarm-benchmark
cp SKILL.md ~/.hermes/skills/software-development/hermes-swarm-benchmark/
cp -R src    ~/.hermes/skills/software-development/hermes-swarm-benchmark/
```

Then `pip install -e .` (or copy `src/hermes_benchmark/` onto
`PYTHONPATH`) so the skill can invoke the CLI.

## Quick start (end-to-end)

```bash
# 1. Generate the OMEGA orchestrator goal text and a results manifest.
hermes-benchmark --agents 4 --tests echo_test,compute_pi --orchestrator none

# 2. Have the OMEGA agent execute the goal inside the Hermes harness.
#    Sub-agents will write /tmp/bench_results/{test}/{agent}.json files
#    (atomic writes, 60s timeout per workload).

# 3. Render the report. Always produces a populated REPORT.md, even if
#    some sub-agents never wrote a result file.
hermes-benchmark-report --results-dir /tmp/bench_results \
    --out REPORT.md --json report.json
```

## Output location

| File | Written by | Default path |
|---|---|---|
| `omega_goal.txt` | `hermes-benchmark` | `/tmp/omega_goal.txt` (override with `--goal-out`) |
| `manifest.json` | `hermes-benchmark` | `<results-dir>/manifest.json` |
| `{test}/{agent}.json` | each sub-agent (inside Hermes) | `<results-dir>/{test}/{agent}.json` |
| `REPORT.md` | `hermes-benchmark-report` | `REPORT.md` (override with `--out`) |
| `report.json` | `hermes-benchmark-report` | not written unless `--json` is given |

## Hermes harness contract

This package generates files; **the Hermes AI harness is what actually
executes the OMEGA orchestrator and its sub-agents.** The split:

| Step | Runs in | Writes |
|---|---|---|
| `hermes-benchmark …` | Plain Python (this package) | `omega_goal.txt`, `<results-dir>/manifest.json` |
| OMEGA orchestrator | Hermes harness (`delegate_task`) | spawns sub-agents per the goal text |
| Each sub-agent | Hermes harness terminal toolset | `<results-dir>/{test}/{agent}.json` (atomic write) |
| `hermes-benchmark-report …` | Plain Python (this package) | `REPORT.md` (+ optional `report.json`) |

### Report contract — no fabricated rows

The renderer **never invents pass/success rows**. Every `(test, agent)`
pair listed in `manifest.json` produces exactly one row in `REPORT.md`:

- If the sub-agent wrote a result JSON, the row reflects its
  `passed` / `output` / `error` fields verbatim.
- If no JSON exists for that pair when the renderer runs, the row is
  rendered as **`passed=false`** with `error="missing result file"` and a
  literal `missing` marker in the per-test detail table.

Concretely:

- A `REPORT.md` rendered before any agent runs is a **valid, fully
  populated failure report** — every row reads `missing`. It is *not* an
  empty stub, and it is not a fake success.
- Sub-agents that fail to launch should still attempt to write a JSON
  with `passed=false` and a meaningful `error` — that gives a richer
  failure row than the synthesised `missing result file` placeholder.
- A passing row only ever appears when a real sub-agent wrote
  `passed: true` in its JSON. Nothing in this package fabricates a
  successful run.

The OMEGA goal text emitted by `hermes-benchmark` repeats this invariant
explicitly to sub-agents.

### Banner status

| `grand_total` | `grand_passed == grand_total` | Banner |
|---|---|---|
| 0 | n/a | `**NO RESULTS**` |
| > 0 | yes | `**PASS**` |
| > 0 | no | `**FAIL**` |

## Available tests

| Name | Toolset | Notes |
|---|---|---|
| `echo_test` | terminal | minimal smoke test |
| `file_io` | terminal | mkdir + write + cat |
| `compute_pi` | terminal | 5M-iter Leibniz CPU bench |
| `terminal_cmd` | terminal | alias for echo |
| `browser` | browser | not implemented; runs an `echo` no-op so the row is never simulated |

Unknown tests are rejected by the CLI (`--tests` validates against the
registry in [`tasks.py`](src/hermes_benchmark/tasks.py)).

## Result schema

A single dataclass-backed schema lives in
[`src/hermes_benchmark/schema.py`](src/hermes_benchmark/schema.py):

```python
AgentResult(agent, test, started_at, completed_at, wall_s, passed, output, error)
RunManifest(agents, tests, orchestrator, results_dir, model, created_at)
```

Each sub-agent writes one `AgentResult` per `{test}/{agent}.json`. The
renderer groups them into `TestResult`s and a top-level `BenchmarkReport`.

## Output (`REPORT.md`)

The default and only first-class artifact is **`REPORT.md`** — a
Markdown document with:

- A **PASS / FAIL / NO RESULTS banner** and grand-total summary.
- A **Run configuration** table (agent count, orchestrator, model, test count).
- An **Environment** table (Python version, platform, generation timestamp).
- A **Summary** table per test (pass/total/wall/throughput) plus a totals row.
- **Per-test detail** sections with started/completed timestamps per agent
  and a truncated output column. Missing results render as `missing` with
  `_(no result file written)_`.
- A **Failures** section with the error message and last output of every
  failed agent (or "None" when everything passed).
- A **Reproduce** block with the exact CLI commands to re-run.
- A **Raw data** pointer to the per-agent JSON files and aggregated
  `report.json` (when written).

`--json report.json` optionally writes the same data as a structured JSON
document for downstream tooling.

## No PNG / image output

PR #1 deleted the previous Pillow-based chart generator. Markdown is more
reviewable, diffs cleanly in Git, and renders in any PR or README. If you
need a chart, run a separate plotting tool against `report.json` — that's
a deliberate boundary. Pillow is **not** a dependency.

## Tests

```bash
PYTHONPATH=src pytest
```

Notable coverage:

- Every generated task body parses with `ast.parse` for every test in `TASKS`.
- The generated body actually runs end-to-end and writes valid JSON.
- Atomic writes leave no `.tmp` files behind on success.
- Unknown `--tests` arguments are rejected.
- `..` in `--results-dir` is rejected.
- Markdown report contains the summary table, per-test detail, failures
  section, environment block, and reproduce command.
- An end-to-end test runs `hermes-benchmark` → `hermes-benchmark-report`
  with **no agent results yet** and asserts every selected `(test, agent)`
  pair shows up as a `missing` failure row, never a fabricated success.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `error: results_dir does not exist` | Run `hermes-benchmark` first to create it (and the manifest). |
| `**NO RESULTS**` banner | No manifest *and* no per-agent JSONs found. The Python CLI never ran or `--results-dir` is wrong. |
| Every row says `missing` | `hermes-benchmark` ran but the OMEGA orchestrator never executed in Hermes (or sub-agents never wrote JSONs). |
| `error: invalid manifest in …` | `manifest.json` was hand-edited and is no longer valid JSON. Regenerate by re-running `hermes-benchmark`. |
| Test fails on Linux CI complaining about a font | You're on an old version. PR #1 removed all PIL/font code; pull `main`. |
| `unknown test(s)` from `--tests` | Typo. See the table above or `python -c "from hermes_benchmark.tasks import known_tests; print(known_tests())"`. |

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and PRs are welcome.

## Security

See [SECURITY.md](SECURITY.md) for the disclosure process.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
