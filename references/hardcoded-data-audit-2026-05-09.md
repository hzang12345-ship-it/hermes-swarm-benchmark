# Hardcoded Data Audit — May 9, 2026

## What Triggered the Audit

Before handing off the benchmark skill to another agent (or to Hermes creator review), Hessum asked to check for hardcoded data that shouldn't be there. The risk: template code that embeds actual run values produces new benchmark results that look like copies of old ones.

## Findings

### Hardcoded data FOUND and fixed (5 instances across 3 files)

| File | Was | Now |
|------|-----|-----|
| `SKILL.md` chart template | `GRAND TOTAL: 16/16 PASS (100%) WALL=3.3s` | `f"GRAND TOTAL: {total_pass}/{total_all} PASS ({pct*100:.0f}%) WALL={wall:.1f}s"` |
| `SKILL.md` chart template | `tok_in=38,894 \| tok_out=3,113 \| api_calls=5` | `f"tok_in={total_tok_in:,} \| tok_out={total_tok_out:,} \| api_calls={total_calls}"` |
| `SKILL.md` chart template | `N agents \| SUITE \| ORCHESTRATOR_MODE \| MiniMax-M2.7` | `f"N agents \| SUITE \| ORCHESTRATOR_MODE \| {model}"` |
| `SKILL.md` output format box | `Model: MiniMax-M2.7 \| Config: 8 \| Tested: N` | `Model: {model} \| Config: {config} \| Tested: N` |
| `hermes-swarm-runner/SKILL.md` | `GRAND: 12/12 PASS \| WALL=41.3s` | `f"GRAND: {{total_pass}}/{{total_all}} PASS \| WALL={{total_wall:.1f}s"` |
| `hermes-swarm-runner/SKILL.md` | `f"Agents: {{len(AGENTS)}} \| Model: MiniMax-M2.7"` | `f"Agents: {{len(AGENTS)}} \| Model: {model}"` |
| `benchmark_chart_generator.py` | `subtitle: "8 Workers \| Model: MiniMax-M2.7"` | `"N Workers \| Model: auto-detected"` |
| `benchmark_chart_generator.py` | `max_wall = 35.0` (arbitrary) | `max((w for t in tests for _, w, *_ in [t]), default=35.0)` |

### Legitimate historical records (NOT hardcoded — preserved as-is)

- `references/benchmark-results.md` — Round 1-5 actual results from real runs ✓
- `references/round-5-2026-05-09.md` — per-agent Pi values (3.1415924536) from real run ✓
- `references/session-state.md` — session record with actual 16/16 WALL=3.3s ✓
- `references/chart-visual-spec.md` — purely geometric spec, no hardcoded run data ✓
- `swarm-benchmarks.md` (hermes-agent skill) — actual benchmark results from real run ✓
- `hermes-swarm-runner` inline example box — illustrative format only, not live template code ✓

## Pattern

The bug was in **chart template code embedded in SKILL.md** — PIL generation scripts that looked like they were templates but actually had literal values from the last run baked in. The difference between a proper template and a broken one:

```python
# BROKEN — literal values baked in
d.text((20, y), "GRAND TOTAL: 16/16 PASS (100%)  WALL=3.3s", ...)

# CORRECT — variable interpolation
d.text((20, y), f"GRAND TOTAL: {total_pass}/{total_all} PASS ({pct*100:.0f}%)  WALL={wall:.1f}s", ...)
```

## Rule Going Forward

When updating any chart template code in a skill:
1. Check for numeric literals that look like measured values (times, counts, token totals)
2. Check for model name strings hardcoded in subtitle lines
3. Replace all with `f"{variable}"` interpolation

Audit scope: any PIL chart code, any output format box, any example result row in a skill that generates dynamically-varying output.