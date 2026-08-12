# Changelog

## Unreleased

- **View picker** — one **View** setting decides where the camera sits for both
  playback and export: *Current View* (never touches the viewport), *Recorded
  Views* (the old restore-and-blend behaviour), static *Front* / *Right* /
  *Top* orthographic, or *Scene Camera*. Static modes are pointed once and then
  left alone, framed on the session's **final** step so the model grows into
  frame instead of overflowing it, and the viewport you started from is handed
  back when playback or export ends. Replaces the *Restore View on Scrub* and
  *Use Recorded Views* checkboxes, which overlapped and could fight each other.
  Playing back in Current View no longer knocks a Front-orthographic viewport
  into perspective. Smooth Motion greys out outside Recorded Views, where it
  has nothing to move between.

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
- **Capture Camera Moves** — orbiting, panning and zooming become steps.
  Viewport navigation never fires a depsgraph update, so previously nothing at
  all was recorded between hitting Record and the first mesh edit.
- **Keystrokes in exported video** — `render.opengl` does not run Python draw
  handlers, so the viewport overlay could never reach the output. **Keys in
  Video** picks the route: *Bottom Centre* renders frames first and composites
  text over them through the sequencer (screencast placement), *Top Left* uses
  Blender's render stamp in one pass (position fixed by Blender), or *Off*.
- **Reliable keystroke capture** — the modal logger is started from the panel
  button, where the context has a real window; starting it from a timer left
  `context.window` as None and `modal_handler_add()` silently attached
  nothing. A watchdog re-arms it if it is dropped, and a sequence counter
  retires stale duplicates so re-arming never double-counts.
- **Steps labelled from the keymap** — keys pressed inside a running modal
  operator never reach a `PASS_THROUGH` handler, and clock-driven camera steps
  used to drain the pending-key buffer before the edit step landed. Steps are
  now labelled from the operator's own shortcut, which is deterministic;
  timestamped logged keys cover steps where no operator ran. Menu entry points
  (`Shift+A` for add, `X` for delete) are supplied, since nothing is bound to
  the operators those menus run.
- **Stale labels suppressed** — `wm.operators` keeps reporting the last
  operator, so a camera step captured after an extrude captioned itself
  "Extrude Region and Move". Labels are dropped once the operator repeats
  without new geometry.
- **Keystroke repeat-collapse** — repeated keys fold into a counter
  (`X ×3`) both live and per-step.
- **Diagnostics** — a panel button reports capture state, per-step keys and
  shortcut resolution to the console and a text block, plus a build marker so
  a report can be tied to the code that produced it.
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
