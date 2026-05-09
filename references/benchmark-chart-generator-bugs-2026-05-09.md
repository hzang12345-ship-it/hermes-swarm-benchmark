# benchmark_chart_generator.py — Bugs Found & Fixed (2026-05-09)

## Bug 1: max_wall dict iteration (TypeError at render)

**Broken:**
```python
max_wall = max((w for t in tests for _, w, *_ in [t]), default=35.0)
```

**Why it breaks:**
- `for _, w, *_ in [t]` unpacks items from iterating a **dict**
- Dict iteration yields **keys** (strings: `'passed'`, `'color'`, `'agents'`), not values
- `w` becomes a string like `'wall'` → `wall / max_wall` → `TypeError: unsupported operand type(s) for /: 'float' and 'str'`
- Bug is LATENT — never triggered when `tests=None` (ValueError raised first) and no callers passed real data

**Fix:**
```python
max_wall = max((agent[1] for test in tests for agent in test['agents']), default=35.0)
```
Index into agent tuples directly — each agent is a 6-element tuple: `(name, wall, tin, tout, calls, color)`.

---

## Bug 2: total_passed counted 8x per test (wrong grand total)

**Broken:** `total_passed += 1` was inside `for name, wall, tin, tout, calls, col in test['agents']`:
```python
for name, wall, tin, tout, calls, col in test['agents']:
    ...
    total_in += tin; total_out += tout; total_calls += calls
    if test['passed'] == 8:
        total_passed += 1   # ← ran 8 times per test!
    total_agents += 1
    y += row_height
```

**Fix:** Move outside the per-agent loop:
```python
for name, wall, tin, tout, calls, col in test['agents']:
    ...
    total_agents += 1
    y += row_height

# Count passed tests (not individual agents)
if test['passed'] == len(test['agents']):
    total_passed += 1
```

---

## Bug 3: Hardcoded default data (stale results)

`generate_benchmark_chart(tests=None)` had ~60 lines of per-agent timing data from a May 9 run as defaults.

**Fix:** Replaced with:
```python
if tests is None:
    raise ValueError(
        "generate_benchmark_chart() requires explicit tests data. "
        "Pass a list of dicts with keys: name, wall, passed, color, agents."
    )
```

---

## Verification

```bash
cd ~/.hermes/skills/software-development/hermes-swarm-benchmark/references
python3 -c "
from benchmark_chart_generator import generate_benchmark_chart
test_data = [
    {'name':'echo_test','wall':0.8,'passed':8,'color':'#00FF41',
     'agents':[('ALPHA',0.1,100,50,1,'#00FF41'),('BRAVO',0.1,100,50,1,'#00D7FF'),
               ('CHARLIE',0.1,100,50,1,'#FFD700'),('DELTA',0.1,100,50,1,'#FF6B00'),
               ('ECHO',0.1,100,50,1,'#00FF41'),('FOXTROT',0.1,100,50,1,'#00D7FF'),
               ('GOLF',0.1,100,50,1,'#FFD700'),('HOTEL',0.1,100,50,1,'#FF00FF')]},
    {'name':'compute_pi','wall':5.6,'passed':8,'color':'#00FF41',
     'agents':[('ALPHA',0.5,200,100,1,'#00FF41'),('BRAVO',0.6,200,100,1,'#00D7FF'),
               ('CHARLIE',0.5,200,100,1,'#FFD700'),('DELTA',0.6,200,100,1,'#FF6B00'),
               ('ECHO',0.5,200,100,1,'#00FF41'),('FOXTROT',0.6,200,100,1,'#00D7FF'),
               ('GOLF',0.5,200,100,1,'#FFD700'),('HOTEL',0.6,200,100,1,'#FF00FF')]},
]
img = generate_benchmark_chart(output_path='/tmp/test_fix.png',
    title='BENCHMARK CHART FIX VERIFIED',
    subtitle='8 Agents | Model: MiniMax-M2.7',
    tests=test_data)
import os; print(f'OK: {os.path.getsize(\"/tmp/test_fix.png\")} bytes')
"
```
Expected output: `OK: 47757 bytes` or similar, no errors.