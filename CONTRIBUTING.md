# Contributing

Thanks for your interest in `hermes-swarm-benchmark`. This project aims to
stay small, focused, and honest about what it measures. Contributions that
fit that scope are welcome.

## Ground rules

1. **No fabricated rows.** The renderer must never synthesise a passing
   result. Every `(test, agent)` pair with no JSON file must surface as a
   failure row (`passed=false`, `error="missing result file"`). Tests
   pin this invariant — please add new ones rather than relax existing
   ones.
2. **No image / font dependencies.** PR #1 removed Pillow. The first-class
   artifact is `REPORT.md`. Plotting belongs in a separate downstream tool
   that consumes `report.json`.
3. **Small dependency surface.** Runtime deps should stay empty; dev deps
   should stay minimal (`pytest`).
4. **Generated scripts must parse.** Every body produced by
   `hermes_benchmark.tasks` must round-trip through `ast.parse`. There's
   a parametrised test that enforces this — keep it green.

## Development setup

```bash
git clone https://github.com/hzang12345-ship-it/hermes-swarm-benchmark.git
cd hermes-swarm-benchmark
pip install -e .[dev]
```

Run the tests:

```bash
pytest -v
```

Run a smoke benchmark generation locally (no Hermes needed):

```bash
hermes-benchmark --agents 2 --tests echo_test --orchestrator none \
    --results-dir /tmp/bench_smoke --goal-out /tmp/omega_goal.txt
hermes-benchmark-report --results-dir /tmp/bench_smoke --out /tmp/REPORT.md
cat /tmp/REPORT.md
```

The report should render every selected `(test, agent)` pair as a
`missing` row — that's the contract.

## Filing issues

When opening an issue, include:

- The CLI commands you ran (verbatim).
- The `manifest.json` and any per-agent JSONs that were written.
- The full `REPORT.md` (or whatever was produced).
- Python version and OS.

Avoid pasting secrets or full Hermes config — the benchmark itself does
not need them.

## Pull requests

- Add or update tests for any change in behaviour. Test fixtures live
  under `tests/` only; do **not** add example "successful run" data
  anywhere else in the repo, and do not commit a real `REPORT.md` or
  `report.json` (they are in `.gitignore`).
- Run `pytest -v` locally and ensure CI passes on Python 3.10/3.11/3.12.
- Keep the public CLI surface stable. Adding flags is fine; renaming or
  removing them is a breaking change and needs a CHANGELOG entry.
- Update `CHANGELOG.md` under `## [Unreleased]`.

## Scope — what does NOT belong here

- Plotting, charting, screenshots.
- Running the OMEGA orchestrator itself in Python — that lives inside the
  Hermes harness; this package only generates the goal text.
- Any code path that fabricates pass / success values when real data is
  missing.

If you're unsure whether a change fits, open an issue first and we can
talk it through before you build anything.
