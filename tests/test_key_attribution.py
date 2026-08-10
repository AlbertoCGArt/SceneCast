"""Keys are credited to steps by time window, not by a drainable buffer.

Camera steps fire on a clock and used to drain the pending-key buffer before
the edit step that the keys actually belonged to ever landed.
"""
from scenecast.overlay import keys_for_step
from scenecast.state import SESSION, KEY_LOOKBACK


def _session(steps, log):
    SESSION.reset()
    SESSION.steps.extend(steps)
    SESSION.key_log.extend(log)


def test_step_uses_its_own_keys_when_present():
    _session([{"t": 10.0, "keys": ["E"]}], [("G", 9.5)])
    assert keys_for_step(0) == ["E"]


def test_keys_claimed_from_the_window_between_steps():
    _session([{"t": 10.0}, {"t": 20.0}, {"t": 30.0}],
             [("A", 15.0), ("B", 25.0)])
    assert keys_for_step(1) == ["A"]
    assert keys_for_step(2) == ["B"]


def test_first_step_looks_back_a_fixed_window():
    _session([{"t": 100.0}], [("X", 100.0 - KEY_LOOKBACK / 2),
                              ("Y", 100.0 - KEY_LOOKBACK * 5)])
    assert keys_for_step(0) == ["X"]      # Y is too old to belong to step 0


def test_window_is_exclusive_at_start_inclusive_at_end():
    _session([{"t": 10.0}, {"t": 20.0}], [("edge", 20.0), ("prev", 10.0)])
    assert keys_for_step(1) == ["edge"]   # ts == previous step time is not ours


def test_multiple_keys_keep_press_order():
    _session([{"t": 10.0}, {"t": 20.0}],
             [("G", 12.0), ("Z", 13.0), ("5", 14.0)])
    assert keys_for_step(1) == ["G", "Z", "5"]


def test_step_with_no_keys_in_window_is_empty():
    _session([{"t": 10.0}, {"t": 20.0}], [("A", 55.0)])
    assert keys_for_step(1) == []


def test_out_of_range_index_is_safe():
    _session([{"t": 1.0}], [])
    assert keys_for_step(-1) == []
    assert keys_for_step(99) == []
