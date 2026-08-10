# Changelog

## Unreleased

- **Smooth Motion** — geometry and object transforms now interpolate between
  steps in playback and export, so moves and edits glide instead of snapping.
  Uses a linear (constant-velocity) blend so it reads like the real drag
  rather than an eased keyframe animation. Same-topology objects only.
  (Renamed from "Smooth Camera", which only moved the viewport.)
- **Export speed matches playback** — step duration is derived from the
  playback "Hold (s)" value (`frames = hold × fps`) instead of a separate
  Frames/Step count. The two used different units, so exports ran faster than
  the scrub. The redundant Frames/Step property was removed and the panel now
  shows the resulting seconds-per-step.
- **Reliable keystroke capture** — Blender silently drops a passive modal
  operator after a menu or modal tool runs (Shift+A, Grab, Extrude), so only
  the first keystroke of a session was ever captured. The logger now stamps a
  heartbeat and a watchdog re-arms it when it goes quiet; a sequence counter
  retires stale duplicates so re-arming never double-counts. The panel shows a
  live "Keys captured" count while recording.
- **Keystroke repeat-collapse** — repeated keys fold into a counter
  (`X ×3`) both live and per-step.
- **Build** — `scripts/build.py` emits both the 4.2+ extension zip and the
  nested-layout legacy add-on zip; fixed zip entry names using a backslash
  separator on Windows for `--pro` builds.

## 1.0.0

Initial release.

- **Step recording** — settled edits become steps capturing geometry, object
  transforms, active object, vert/edge/face selection, 3D cursor, pivot,
  transform orientation, select mode, and pressed keys
- **Multi-object capture** with per-step visibility (objects added mid-session
  hide when scrubbing before their creation)
- **Collection isolation** — recorded objects gathered into a dedicated
  collection on Record, restored on Clear
- **Edit-mode replay** — edit cage with original selection highlighted
  (bmesh rebuild path), watchdog-backed edit-mode capture
- **Smooth camera** — quaternion slerp + smoothstep easing between recorded
  views in playback and export
- **Keystroke overlay** — screencast-style key display, live while recording
  and per-step during playback, with operator labels
- **Export** — MP4 (H.264) or PNG sequence via viewport OpenGL render, with
  per-step frame holds and optional recorded-view camera
- **Scrub timeline** with play/pause, hold time, loop, and per-step info
