# hermes-swarm-benchmark

A concurrent-agent benchmark suite for Hermes Agent. Sub-agents run small
workloads (echo, file IO, compute_pi, etc.) in parallel and write per-agent
result JSONs; an OMEGA orchestrator polls for them and a report renderer
aggregates the data into a polished Markdown report.

> Status: production-readiness PR #1 — fixes the unparsable generated-script
> bug, removes the broken PIL chart path, adds a polished Markdown report
> with run config / environment / per-test detail / failures / repro
> command, plus CLI validation, atomic JSON writes, timeouts, tests, and
> packaging.

## Install

```bash
pip install -e .[dev]
```

Requires Python 3.10+. No image/plotting dependencies — Markdown only.

## Quick start

```bash
# 1. Generate the OMEGA orchestrator goal text.
hermes-benchmark --agents 4 --tests echo_test,compute_pi --orchestrator none

# 2. Have the OMEGA agent execute the goal — sub-agents will write
#    /tmp/bench_results/{test}/{agent}.json files (atomic writes, with
#    a 60s timeout per workload).

# 3. Render the report.
hermes-benchmark-report --results-dir /tmp/bench_results \
    --out REPORT.md --json report.json
```

## Output

The default and only first-class artifact is **`REPORT.md`** — a Markdown
document with:

- A **PASS/FAIL banner** and grand-total summary.
- A **Run configuration** table (agent count, orchestrator, model, test count).
- An **Environment** table (Python version, platform, generation timestamp).
- A **Summary** table per test (pass/total/wall/throughput) plus a totals row.
- **Per-test detail** sections with started/completed timestamps per agent
  and a truncated output column.
- A **Failures** section with the error message and last output of every
  failed agent (or "None" when everything passed).
- A **Reproduce** block with the exact CLI commands to re-run.
- A **Raw data** pointer to the per-agent JSON files and aggregated
  `report.json` (when written).

`--json report.json` optionally writes the same data as a structured JSON
document for downstream tooling.

## No PNG chart output

Earlier versions of this skill shipped a PIL-based chart generator. It had
multiple bugs (dict-iteration on test rows, mis-counted `total_passed`,
hardcoded stale data) and required a font path that doesn't exist on Linux
CI. PR #1 removes it entirely.

Markdown is more reviewable, diffs cleanly in Git, and renders in any PR
or README. If you need a chart, run a separate plotting tool against
`report.json` — that's a deliberate boundary.

## Result schema

A single dataclass-backed schema lives in
[`src/hermes_benchmark/schema.py`](src/hermes_benchmark/schema.py):

```python
AgentResult(agent, test, started_at, completed_at, wall_s, passed, output, error)
```

Each sub-agent writes one of these per `{test}/{agent}.json`. The renderer
groups them into `TestResult`s and a top-level `BenchmarkReport`.

## Available tests

| Name | Toolset | Notes |
|---|---|---|
| `echo_test` | terminal | minimal smoke test |
| `file_io` | terminal | mkdir + write + cat |
| `compute_pi` | terminal | 5M-iter Leibniz CPU bench |
| `terminal_cmd` | terminal | alias for echo |
| `browser` | browser | placeholder, currently a no-op |

Unknown tests are rejected by the CLI (`--tests` validates against the
registry in [`tasks.py`](src/hermes_benchmark/tasks.py)).

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

## Layout

```
src/hermes_benchmark/
  __init__.py
  schema.py     # AgentResult / TestResult / BenchmarkReport dataclasses
  tasks.py      # TASKS registry + safe goal-body generator
  cli.py        # `hermes-benchmark` entry point + input validation
  report.py     # `hermes-benchmark-report` entry point (Markdown-only)
references/     # legacy v6 notes (kept for diff context, not on import path)
tests/          # pytest suite
```

## License

MIT — see [LICENSE](LICENSE).
