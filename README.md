# SceneCast

**SceneCast** is a Blender add-on that records your modeling session — mesh edits, selection,
3D cursor, pivot changes, viewport angles, and keystrokes — and replays it as
a smooth, scrubbable timeline. Export the session as an MP4 or PNG sequence
to show the evolution of a scene, build tutorials, or create progress videos.

## Features

- **Step recording** — every settled edit becomes a step: geometry, transforms,
  which object was active, what was selected, where the 3D cursor was, which
  pivot/orientation/select-mode was set, and the keys you pressed.
- **Multi-object** — captures every visible mesh object; objects added
  mid-session hide when you scrub before their creation.
- **Edit-mode replay** — steps recorded in Edit Mode replay with the edit cage
  and the original selection highlighted (bmesh rebuild path).
- **Smooth camera** — playback and export glide between recorded viewport
  angles (quaternion slerp + smoothstep easing) instead of hard cuts.
- **Keystroke overlay** — screencast-style key display at the bottom of the
  viewport, live while recording and per-step during playback.
- **Collection isolation** — recorded objects are gathered into a dedicated
  collection on Record and restored on Clear.
- **Export** — MP4 (H.264) or PNG sequence via the viewport OpenGL renderer,
  with per-step frame holds and optional recorded-view camera.

## Install

**Blender 4.2+ (extension):** run `python scripts/build.py`, then in Blender:
Edit > Preferences > Get Extensions > (dropdown) > Install from Disk >
pick `dist/scenecast-<version>.zip`.

> Because the zip carries `blender_manifest.toml` at its root, Blender 4.2+
> installs it as an **extension**. It therefore appears under **Extensions**,
> *not* in the legacy Add-ons list — that is expected. Enable it there.

**Legacy add-on install (pre-4.2):** use the separate
`dist/scenecast-<version>-legacy.zip`, which nests the files under
`scenecast/`, via Edit > Preferences > Add-ons > Install. That is the build
that shows up in the Add-ons list. `python scripts/build.py` produces both.

Either way the UI lives in the 3D viewport sidebar (**N**) under the
**SceneCast** tab.

## Usage

1. Open the N-panel > **SceneCast** tab.
2. Hit **Start Recording** and model. Steps accumulate live.
3. Stop, drop to Object Mode, and **scrub** or **play** the timeline.
4. Use the **Export** box to render the session to video.

## Development

Pure-logic modules are testable without Blender:

```
pip install pytest
pytest tests/
```

`tests/stubs/` contains minimal `bpy`/`bmesh`/`blf`/`mathutils` stand-ins so
the package can be imported and its logic exercised in CI.

## Project layout

```
scenecast/
  __init__.py    registration hub (bl_info, register/unregister)
  state.py       session store + config constants
  viewnav.py     viewport discovery, view classification, view interpolation
  capture.py     snapshots, change detection, depsgraph handler, watchdog
  replay.py      mesh rebuilds, context restore, playback clock
  exporter.py    frame-mapped export, render settings stash/restore
  overlay.py     keystroke capture (modal op) + on-screen drawing
  ops.py         user-facing operators
  ui.py          N-panel
  props.py       scene property registration
```

## Known limitations (v1.0)

- Sessions are in-memory only; closing the file discards the recording.
- Memory grows with mesh size × steps (differential storage is the next
  major milestone — see ROADMAP).
- Deleted objects can't be resurrected on rewind (they hide instead).
- Objects are tracked by name; renaming mid-session breaks the thread.
- Menu popups can't be captured (no API); the keystroke + operator-label
  overlay conveys the trigger and result instead.
- Keys pressed *inside* a running modal operator (the `Z` `5` of a `G` `Z` `5`
  move) are consumed by that operator and never reach the logger; the trigger
  key plus the operator label are what get recorded.
- The keystroke overlay is a viewport draw handler, and `render.opengl` does
  not run those — so keys are visible on screen but do **not** appear in
  exported video. A composited text pass is on the roadmap.
- Smooth Motion only blends objects whose topology is unchanged between two
  steps; a vert-count change snaps (you can't morph 8 verts into 12).
- "Edit Mode in Export" is experimental; mode switching during render can
  be fragile.

## License

GPL-3.0-or-later. (Blender add-ons that import `bpy` are GPL-derived works;
GPL does not prevent selling the add-on — Blender Market, Gumroad and
FlippedNormals all distribute GPL add-ons commercially.)
