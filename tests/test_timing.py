"""Playback easing, step sequencing, and export frame mapping."""

def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)

def test_smoothstep_endpoints_and_shape():
    assert smoothstep(0) == 0 and smoothstep(1) == 1
    assert abs(smoothstep(0.5) - 0.5) < 1e-9
    assert smoothstep(0.25) < 0.25 and smoothstep(0.75) > 0.75
    prev = -1
    for i in range(101):
        v = smoothstep(i / 100)
        assert v >= prev
        prev = v

def test_playback_fires_each_step_once_in_order():
    n, hold, dt = 5, 0.8, 1 / 30
    pos, last_idx, fired = 0.0, -1, []
    while True:
        pos += dt / hold
        end = float(n - 1)
        if pos >= end:
            pos = end
        idx = int(pos)
        if idx != last_idx:
            last_idx = idx
            fired.append(idx)
        if pos == end:
            break
    assert fired == [0, 1, 2, 3, 4]

def test_export_frame_mapping_holds_each_step_exactly():
    n, hold = 4, 12
    counts = {}
    for frame in range(1, n * hold + 1):
        idx = min(n - 1, (frame - 1) // hold)
        counts[idx] = counts.get(idx, 0) + 1
    assert counts == {0: 12, 1: 12, 2: 12, 3: 12}
