"""Screen layout shared by the viewport overlay and the video export.

Both renderers used to carry their own hardcoded numbers -- the overlay in
pixels, the exporter in normalised strip coordinates -- chosen independently.
Elements crowded each other because nothing knew what else was on screen, and
what you saw while scrubbing was not what landed in the video.

Everything here is a fraction of frame height, so the same table drives a
900px viewport and a 4K render and they agree proportionally.
"""

# name -> (y from bottom, font size), both as a fraction of frame height.
# Ordered bottom-up: op, keys, note. Chapter sits near the top on its own.
BANDS = {
    "op":      (0.040, 0.016),
    "keys":    (0.070, 0.022),
    "note":    (0.150, 0.030),
    "chapter": (0.880, 0.052),
}

# The user's overlay size preference scales text without moving the bands,
# so the stack keeps its spacing at any size.
SCALES = {'SMALL': 0.85, 'MEDIUM': 1.0, 'LARGE': 1.35}

MIN_FONT_PX = 9.0


def scale_for(name):
    return SCALES.get(name, 1.0)


def band_px(name, frame_height, scale=1.0):
    """(y in pixels from the bottom, font size in pixels) for a viewport."""
    y, size = BANDS[name]
    return y * frame_height, max(MIN_FONT_PX, size * frame_height * scale)


def band_norm(name, scale=1.0):
    """(y as 0-1 from the bottom, font size as a fraction of height).

    The sequencer positions text in 0-1 and sizes it in pixels, so callers
    multiply the size by the output resolution's height.
    """
    y, size = BANDS[name]
    return y, size * scale
