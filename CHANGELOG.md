# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `scripts/install_skill.sh` — safe dry-run-by-default installer that copies
  `SKILL.md` and `src/` into a Hermes skills directory without ever editing
  user config.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` — public-repo metadata.
- README sections covering search keywords, install (Python package + Hermes
  skill), output location, troubleshooting, and an explicit "no fabricated
  rows" report contract.

### Changed

- README and `SKILL.md` rewritten around discovery and installation: what the
  repo is, how to find it, how to install into Hermes, where output lands,
  and how to read the report contract.
- `SKILL.md` version bumped to 6.2.0; `author` corrected to the GitHub owner.
- Removed `references/` legacy session notes — they contained historical
  benchmark numbers that could be mistaken for current product output, and
  referenced the deleted PNG chart pipeline.

### Removed

- `references/` directory (7 historical run-log files). Test fixtures live
  only under `tests/`.

### Fixed / clarified

- The "no simulated returns" invariant is now stated front-and-centre in
  both README and `SKILL.md`: the renderer never fabricates pass rows; a
  `(test, agent)` pair with no JSON renders as
  `passed=false, error="missing result file"`.

## [0.1.0] — PR #1, production-readiness

### Added

- `hermes-benchmark` CLI — generates the OMEGA orchestrator goal text plus
  a `manifest.json` declaring the selected agents/tests/orchestrator.
- `hermes-benchmark-report` CLI — renders `REPORT.md` (always populated,
  every selected pair shows up as either a real result or an explicit
  `missing` failure row) and an optional aggregated `report.json`.
- Dataclass-backed result schema (`AgentResult`, `TestResult`,
  `BenchmarkReport`, `RunManifest`).
- Atomic per-agent JSON writes (write to `*.tmp` then `os.replace`).
- 60-second per-workload timeout in generated sub-agent scripts.
- Pytest suite covering: ast-parseability of every generated body,
  end-to-end execution writing valid JSON, atomic-write hygiene, CLI
  input validation (unknown tests, empty/`..` results-dir), Markdown
  report contents (summary, per-test detail, failures, environment,
  reproduce), and the manifest-driven "missing row" invariant.
- GitHub Actions workflow running pytest on Python 3.10 / 3.11 / 3.12.

### Removed

- Pillow / PIL chart generator. PNG output is gone; Markdown is the only
  first-class artifact. Pillow is not a dependency.

### Fixed

- Generated sub-agent scripts now embed all runtime values via `repr()`,
  so they always parse with `ast.parse` regardless of quoting in the
  shell command.
- Unknown `--tests` arguments are rejected with a clear error.
- `..` traversal in `--results-dir` is rejected.
