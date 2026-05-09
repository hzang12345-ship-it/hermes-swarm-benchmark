# Hermes Swarm Benchmark — Results History

## Round 5 (May 9, 2026) — OMEGA Orchestrator E2E, 8 agents, Full suite + 2x4 orchestrator stress test

| Test | Pass | Fail | Wall(s) | Notes |
|------|------|------|---------|-------|
| echo_test | 8/8 | 0 | ~7.6 | ✓ All ALPHA→HOTEL respond |
| file_io | 8/8 | 0 | ~32 | ✓ All write/verify /tmp/bench/[AGENT].txt |
| compute_pi | 8/8 | 0 | ~40 | ✓ Leibniz 5M — all → 3.1415924536 (determinism verified at 8-agent scale) |
| orchestrator (2x4) | 8/8 | 0 | ~28 | ✓ OMEGA→OMEGA-1→4 subs + OMEGA→OMEGA-2→4 subs |

**Grand total:** 36/36 PASS (100%) | 187.3s wall | 141,560 tok in | 5,900 tok out | 12 api_calls

**compute_pi per-agent:**
- ALPHA: 3.1415924536 (0.517s), BRAVO: 3.1415924536 (0.479s), CHARLIE: 3.1415924536 (0.483s), DELTA: 3.1415924536 (0.471s)
- ECHO: 3.1415924536 (0.471s), FOXTROT: 3.1415924536 (0.456s), GOLF: 3.1415924536 (0.470s), HOTEL: 3.1415924536 (0.584s)

**Charts:**
- `/tmp/benchmark_run.png` — 43KB, 900×700 readable dark-theme table
- `/tmp/benchmark_run_arcade.png` — removed (no pixel art on data charts)

**Key findings:**
- All 8 compute_pi agents returned exact same value → deterministic at scale ✓
- 2 orchestrators (OMEGA-1, OMEGA-2) each cleanly spawned and managed 4 sub-sub-agents
- Total sub-sub-agents in flight: 8 (max_spawn_depth=1 confirmed)
- Token throughput: 141,560 in / 5,900 out = 24:1 ratio (normal for batch orchestration)

---

## Round 4 (May 9, 2026) — OMEGA Orchestrator E2E, 8 agents, Full suite + 2x4 orchestrator

| Test | Pass | Fail | Wall(s) | Notes |
|------|------|------|---------|-------|
| echo_test | 8/8 | 0 | ~3s | ✓ All named agents respond |
| file_io | 8/8 | 0 | ~0s | ✓ All write/verify /tmp/bench/[AGENT].txt |
| compute_pi | 8/8 | 0 | ~0.5s | ✓ Leibniz 5M — all → 3.1415924536 |
| orchestrator (2x4) | 8/8 | 0 | ~0s | ✓ OMEGA→OMEGA-1,2 → 4 sub-sub-agents each |

**Grand total:** 24/24 PASS (100%) | ~59s wall | 55,668 tok in | 2,417 tok out | 8 api_calls

**Charts:**
- `/tmp/benchmark_full_run.png` — 31KB, 900×700 readable table
- `/tmp/benchmark_full_run_arcade.png` — removed (no pixel art on data charts)

---

## Round 3 (May 9, 2026) — OMEGA Orchestrator E2E, 4 agents

| Test | Pass | Fail | Wall(s) | Notes |
|------|------|------|---------|-------|
| echo_test | 4/4 | 0 | 12.0 | ✓ OMEGA spawned 4 sub-agents |
| compute_pi | 4/4 | 0 | 2.1 | ✓ Leibniz 5M iterations |
| orchestrator (1x4) | 4/4 | 0 | ~0.4 | ✓ OMEGA spawned OMEGA-1 → 4 subs |

**Grand total:** 8/8 PASS | ~15s wall | Chart: /tmp/benchmark_e2e.png

**Key findings:**
- OMEGA orchestrator pattern (Path A) is fully functional: one `delegate_task(role="orchestrator")` spawns all sub-agents, collects results, generates chart autonomously
- `role="orchestrator"` confirmed valid in delegate_tool.py:569,885 — grants child delegation capability
- Orchestrator sub-agent name expansion bug fixed in benchmark_quick.py (literal `{name}` placeholder → per-agent expansion with `.format(n,n)`)

**E2E workflow (Path A — fully automated):**
```bash
# Generate goal file
python3 benchmark_quick.py --agents 4 --tests echo_test,compute_pi --orchestrator 1x4 --run-via-agent
# Output: /tmp/omega_goal.txt

# Execute via agent (with hermes-swarm-runner skill loaded):
# "Run benchmark with 4 agents, tests: echo_test, compute_pi"
```

---

## Round 2 (May 9, 2026) — MiniMax-M2.7, max_concurrent_children=8

| Test | Pass | Fail | Wall(s) | Notes |
|------|------|------|---------|-------|
| echo_test | 8/8 | 0 | 12.5 | ✓ All named agents respond |
| file_io | 8/8 | 0 | 16.3 | ✓ All write/verify /tmp/bench/[AGENT].txt |
| compute_pi | 8/8 | 0 | 13.2 | ✓ Leibniz 5M iter — all compute 3.1415924536 (determinism confirmed) |
| terminal_cmd | 8/8 | 0 | 21.9 | ✓ All echo codename:timestamp |
| orchestrator | 4/4 | 0 | 22.1 | ✓ OMEGA spawned 4 sub-agents, all completed |
| web_research | 0/8 | 8 | 22.6 | ✗ MiniMax plan rate-limits at 8x concurrency (429 on any target) |
| browser | 0/8 | 8 | 24.6 | ✗ Camofox browser server not running (localhost:9377) |

**Grand total:** 36/44 PASS (82%) | 133.2s wall | ~178K tok in | ~12K tok out | ~91 calls

**Key findings:**
- compute_pi: All 8 agents independently computed Pi = 3.1415924536 → **determinism verified**
- orchestrator: delegation toolset works — OMEGA managed 4 sub-agents successfully
- web_research: **Rate-limit is provider-tier, not target-specific** — httpbin, github/zen, any 8x concurrent web tool calls fail the same way
- browser: Infrastructure not available; Camofox server must be started before running this test

**Charts generated:**
- `/tmp/benchmark_run2.png` — readable high-res chart
- `/tmp/benchmark_run2.png` — readable table (no arcade)

---

## Round 1 (May 9, 2026) — Baseline

| Test | Pass | Fail | Wall(s) | Notes |
|------|------|------|---------|-------|
| echo_test | 8/8 | 0 | 11.0 | ✓ |
| file_io | 8/8 | 0 | 34.4 | ✓ |
| terminal_cmd | 8/8 | 0 | 11.0 | ✓ |
| web_research | 0/8 | 8 | 23.8 | ✗ httpbin 400 (rate-limited) |

**Grand total:** 24/32 PASS (75%) | 80.1s wall | 178K tok in | 12.6K tok out | 91 calls

---

## Provider Rate-Limit Findings

MiniMax Token Plan is designed for **individual interactive workflows** — not concurrent automated agents.
- 8 concurrent web tool calls → HTTP 429 on any target
- Affects `web` toolset (web_search, web_extract)
- Terminal curl works (bypasses the web toolset rate-limit)
- Workaround: use `terminal` toolset with `curl` for web access under concurrent load

---

## Known Issues (Historical)

| Bug | File | Status |
|-----|------|--------|
| Orchestrator literal `{name}` in sub-agent goals | benchmark_quick.py:120,126 | **Fixed** — per-agent expansion now used |
| compute_pi f-string syntax in runner SKILL.md | hermes-swarm-runner/SKILL.md:109 | **Fixed** — corrected to `%%` shell-modulo syntax |
| benchmark_omega.py reads unwritten JSON | references/benchmark_omega.py | Dead code — OMEGA generates chart inline |
| `terminal_cmd` undocumented | Both SKILL.md files | **Fixed** — added to test tables |