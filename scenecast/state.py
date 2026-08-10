"""Shared session state and configuration constants."""

import time


# -- Config -------------------------------------------------------------------
DEBOUNCE = 0.25            # seconds of "quiet" before a settled edit is snapshotted
MAX_VERTS_FULL = 400_000   # total vert budget per step across all captured objects
APPLY_LOCKOUT = 0.6        # ignore depsgraph fires for this long after a scrub
PLAY_DT = 1.0 / 30.0       # playback timer tick
WATCHDOG_DT = 0.7          # edit-mode capture safety-net interval
KEY_FADE = 1.8             # seconds a live keystroke stays visible
KEY_MAX_SHOWN = 5          # max keystroke chips drawn at once

# Viewport navigation never fires the depsgraph, so view changes are polled.
# Thresholds are deliberately loose: they gate whole steps, and an orbit that
# creeps under them would otherwise spam one step per watchdog tick.
VIEW_ROT_EPS = 0.9995      # |quaternion dot| below this counts as rotated
VIEW_DIST_EPS = 0.04       # zoom delta as a fraction of view distance
VIEW_LOC_EPS = 0.04        # pan delta as a fraction of view distance

# ----------------------------------------------------------------------------
# Session store  (module-global: lives for the session, NOT saved to the .blend)
# ----------------------------------------------------------------------------
class _Session:
    def __init__(self):
        self.reset()

    def reset(self):
        self.steps = []
        self.all_names = set()
        self.recording = False
        self.playing = False
        self.play_pos = 0.0
        self.play_last_idx = -1
        self.play_last_t = 0.0
        self.pending = False
        self.last_stamp = 0.0
        self.applying_until = 0.0
        self.original_collections = {}   # obj_name -> [original collection names]
        self.key_buffer = []             # [(text, timestamp)] live keystrokes
        self.pending_keys = []           # keystrokes since the last captured step
        self.keylogger_running = False
        self.keylogger_seq = 0           # bumped each (re)arm; stale loggers retire
        self.keylogger_heartbeat = 0.0   # last modal tick; watchdog death-detect
        self.keys_captured_total = 0     # running count this session (panel signal)
        self.export_active = False       # true while rendering an export
        self.export_step_idx = 0

SESSION = _Session()

_EXPORT = {"hold": 1, "n": 0, "last": -1, "follow": False,
           "smooth": True, "editmode": False, "stamp": False}

