# Changelog

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
