# Benchmark Chart Visual Spec

**Reference image:** `/private/tmp/benchmark_aligned.png`

## Canvas & Layout
- Canvas: 900×900px (not 700px)
- Background: `#0a0a14` (dark navy-black)
- Font: Monaco (try `ImageFont.truetype("/System/Library/Fonts/Monaco.ttc", ...)`)

## Bar Geometry (Critical)
- `BAR_START = 110` — first colored pixel of bar
- `BAR_MAX_W = 400` — bar at max ratio extends to x=510
- `DATA_ROW_H = 10` — each data row bar is 10px tall (not 14px, not 20px)
- Bar height per data row: 10px (NOT 14px as previously coded)
- Each data row occupies exactly 10px vertical (bar occupies rows y to y+9)
- Section labels have 18px height before 8 rows of 10px each
- Spacer between sections: 20px

## Per-Agent Bar Width
- `ratio = agent_time / max_agent_time_in_test`
- `bar_w = int(ratio * BAR_MAX_W)` where BAR_MAX_W=400
- Unknown times → `ratio=1.0` (uniform bars are correct when no timing data)
- compute_pi is the canonical example: HOTEL (0.584s) → 400px, FOXTROT (0.456s) → 312px, others proportional

## Color System
- GREEN (`#00ff41`) — echo_test, compute_pi
- CYAN (`#00d7ff`) — file_io, orchestrator
- GOLD (`#ffd700`) — title, section dividers, grand total
- GRAY (`#888888`) — column headers, metadata text
- WHITE — agent names

## Text Positions
- Agent name: x=20
- Status text: x=480
- Time: x=750
- Section label: x=20 (18px before first row)
- Bar starts at x=110

## Verified Output (Round 5)
- `/tmp/benchmark_run.png` — 900×900, ~39KB readable table
- No arcade version — pixel art removed from benchmark results