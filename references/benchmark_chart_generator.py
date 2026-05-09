"""
HERMES SWARM BENCHMARK — Chart Generator (readable, aligned)

Usage:
  python3 benchmark_chart_generator.py [--output /path/to/output.png]

Generates a high-res benchmark chart with:
  - Per-agent bars + stats columns
  - Column headers aligned with data
  - "Why Parallelism is Faster" explanation section
  - Arcade color scheme

IMPORTANT: block=1 or skip pixel_art.py entirely for data charts.
block=4 (arcade preset) destroys small text readability.
"""

from PIL import Image, ImageDraw

def generate_benchmark_chart(
    output_path: str = "/tmp/benchmark_hires.png",
    width: int = 900,
    title: str = "HERMES SWARM BENCHMARK — FULL SUITE RESULTS",
    subtitle: str = "N Workers | Model: auto-detected",
    tests: list = None,
) -> Image.Image:
    """
    tests: list of dicts with keys:
      name, wall, passed, color,
      agents: [(name, wall, tin, tout, calls, color), ...]
    """

    if tests is None:
        raise ValueError(
            "generate_benchmark_chart() requires explicit tests data. "
            "Pass a list of dicts with keys: name, wall, passed, color, agents. "
            "Example: tests=[{'name':'echo_test','wall':5.2,'passed':8,'color':'#00FF41','agents':[...]}]"
        )

    # Calculate height dynamically
    n_tests = len(tests)
    agents_per_test = 8
    row_height = 24
    test_spacing = 10
    header_height = 100  # title + headers
    footer_height = 280  # totals + metric guide + footer
    height = header_height + n_tests * (agents_per_test * row_height + test_spacing) + footer_height

    img = Image.new('RGB', (width, height), 'black')
    draw = ImageDraw.Draw(img)

    # ── Title ──
    draw.text((25, 15), title, fill='#00FF41')
    draw.text((25, 38), subtitle + ' | max_concurrent_children=8', fill='#888888')
    draw.text((25, 58), '═' * 85, fill='#00FF41')

    # ── Column layout (headers MUST match data x coords) ──
    # NAME at x=25, BAR at x=110, WALL at x=470, TKN_IN at x=540
    # TKN_OUT at x=620, CALLS at x=710
    y = 80
    draw.text((25, y), 'NAME', fill='#888888')
    draw.text((110, y), 'BAR (wall time, max=35s)', fill='#888888')
    draw.text((470, y), 'WALL', fill='#888888')
    draw.text((540, y), 'TKN_IN', fill='#888888')
    draw.text((620, y), 'TKN_OUT', fill='#888888')
    draw.text((710, y), 'CALLS', fill='#888888')
    y += 26

    max_wall = max((agent[1] for test in tests for agent in test['agents']), default=35.0)
    total_in = 0
    total_out = 0
    total_calls = 0
    total_passed = 0
    total_agents = 0
    grand_wall = 0.0

    for test in tests:
        status_col = test['color'] if test['passed'] == 8 else '#FF6B00'
        draw.text((25, y), f"{test['name']} | WALL={test['wall']:.2f}s | {test['passed']}/8 {'PASS' if test['passed']==8 else 'FAIL'}", fill=status_col)
        y += 22

        for name, wall, tin, tout, calls, col in test['agents']:
            bar_w = int((wall / max_wall) * 340)
            # Bar (aligned with header at x=110)
            draw.rectangle((110, y, 110 + bar_w, y + 20), fill=col)
            # Name (aligned at x=25)
            draw.text((25, y + 1), name, fill='white')
            # Stats (aligned under column headers)
            draw.text((470, y + 1), f'{wall:.1f}s', fill='white')
            draw.text((540, y + 1), f'{tin:,}', fill='#888888')
            draw.text((620, y + 1), f'{tout:,}', fill='#888888')
            draw.text((710, y + 1), f'{calls}', fill='#888888')

            total_in += tin
            total_out += tout
            total_calls += calls
            total_agents += 1
            y += row_height

        # count passed tests (not individual agents) — loop over agents, not tests
        if test['passed'] == len(test['agents']):
            total_passed += 1

        grand_wall += test['wall']
        y += test_spacing

    # Divider
    draw.text((25, y), '═' * 85, fill='#00FF41')
    y += 26

    # Grand totals
    throughput = total_out / grand_wall if grand_wall > 0 else 0
    draw.text((25, y), f'GRAND: WALL={grand_wall:.1f}s | TOK_IN={total_in:,} | TOK_OUT={total_out:,} | CALLS={total_calls}', fill='#00FF41')
    y += 22
    draw.text((25, y), f'SUCCESS={total_passed}/{total_agents}={total_passed/total_agents*100:.0f}% | THRU={throughput:.0f} tok/s', fill='#888888')
    y += 45

    # Why parallelism section
    draw.text((25, y), '── WHY IS PARALLELISM FASTER? ──', fill='#FFD700')
    y += 24

    left = [
        ('WALL', 'Agent completion time. Lower = faster.'),
        ('TKN_IN', 'Input tokens. Smaller = less prompt overhead.'),
        ('TKN_OUT', 'Output tokens. Lower = more concise.'),
        ('CALLS', 'Tool calls. Fewer = more efficient.'),
    ]
    right = [
        ('THROUGHPUT', 'tok/sec. Higher = faster swarm output.'),
        ('SUCCESS', 'Pass/Total. 100% = all agents succeeded.'),
        ('WHY?', 'Latency hides + no re-context waste + focus gain.'),
        ('IMPROVE', 'Shorter prompts, faster model, fewer tools.'),
    ]

    lx, rx = 25, 450
    ly = ry = y
    for m, d in left:
        draw.text((lx, ly), f'{m}:', fill='#00D7FF')
        draw.text((lx + 80, ly), d, fill='#888888')
        ly += 20
    for m, d in right:
        draw.text((rx, ry), f'{m}:', fill='#00D7FF')
        draw.text((rx + 100, ry), d, fill='#888888')
        ry += 20

    y = max(ly, ry) + 14
    draw.text((25, y), '═' * 85, fill='#00FF41')

    img.save(output_path)
    print(f'Saved: {output_path} ({width}x{y+30}px)')
    return img


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate Hermes Swarm Benchmark chart')
    parser.add_argument('--output', default='/tmp/benchmark_hires.png')
    args = parser.parse_args()
    generate_benchmark_chart(args.output)
