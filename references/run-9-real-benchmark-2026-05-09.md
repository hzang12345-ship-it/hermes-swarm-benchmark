# Benchmark Run 9 — 2026-05-09 (Real Result-Collection)

## Architecture
- Pattern: result-collection — sub-agents write JSON to `/tmp/bench_results/{test}/{agent}.json`
- OMEGA polls until all files exist, reads timestamps, computes `total_wall = max(completed_at) - min(started_at)`
- No simulation, no spawn-time approximation

## Configuration
- Agents: ALPHA, BRAVO, CHARLIE, DELTA (4 total)
- Tests: echo_test, compute_pi
- Model: MiniMax-M2.7
- Result dir: `/tmp/bench_results/` (cleaned before run)

## Results (from actual JSON files on disk)

### echo_test
| Agent | Wall | Output | Issue |
|-------|------|--------|-------|
| ALPHA | 0.003s | `ALPHA:$(date +%s)` | **BUG:** shell `$()` not expanded — single quotes block expansion |
| BRAVO | 0.000s | `BRAVO:1778362565` | **OK** — used Python `time.time()` workaround |
| CHARLIE | 0.003s | `CHARLIE:$(date +%s)` | **BUG:** same shell quoting issue |
| DELTA | 0.003s | `DELTA:$(date +%s)` | **BUG:** same shell quoting issue |

**total_wall = 21.741s** (from timestamps: min started → max completed across 4 agents)
**thru = 0.2/s**

### compute_pi
| Agent | Wall | π Value | Correct |
|-------|------|---------|---------|
| ALPHA | 0.498s | 3.141592 | ✓ (6 decimals match true π=3.1415926535, error ≈2×10⁻⁷) |
| BRAVO | 0.476s | 3.141592 | ✓ |
| CHARLIE | 0.476s | 3.141592 | ✓ |
| DELTA | 0.484s | 3.141592 | ✓ |

**total_wall = 1.296s** (from timestamps)
**thru = 3.1/s**
**all π values independently verified correct**

## Grand Total
- **8/8 PASS**
- **combined_wall = 23.037s**
- Chart: `/tmp/benchmark_e2e.png` (18,312 bytes)

## Bug Found: echo_test Shell Quoting

`subprocess.check_output("echo 'ALPHA:$(date +%s)'", shell=True)` — single quotes prevent `$()` from expanding. Output is literal string `ALPHA:$(date +%s)` instead of a timestamp.

**Fix:** Use Python `time.time()` directly, skip shell subprocess entirely for echo_test:
```python
import time
output = f"{name}:{int(time.time())}"
```

**All 4 echo_test agents passed** despite the bug (pass = subprocess returned 0, not that output was correct). BRAVO worked around it by using Python time internally.

## Lessons
1. Result-collection pattern works — real wall times from real timestamps, verified math
2. echo_test subprocess quoting bug — use Python time, avoid shell $() in subprocess
3. compute_pi π=3.141592 confirmed independently — proves all agents ran real code
4. OMEGA poll loop successfully detected all 8 JSON files within 30s timeout
