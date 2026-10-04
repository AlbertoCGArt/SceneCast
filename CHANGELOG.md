# Changelog

## 1.1.0

- **Sessions stop eating memory** — a snapshot's topology is now int32 numpy
  buffers filled by `foreach_get`, instead of a Python list holding one tuple
  per edge and per face; faces are stored CSR-style (flat indices + a loop
  count per face) because a mesh mixes triangles, quads and n-gons. On top of
  that, every object snapshot carries a content digest, and an object that is
  byte-for-byte what it was a step ago shares the previous step's snapshot by
  reference instead of storing a second copy — so a five-object scene where
  one object is edited per step costs one snapshot per step, not five. When
  nothing at all changed, the whole object table is shared. Replay only reads
  snapshots, which is what makes the sharing safe.
- **Memory readout and budget** — the panel shows what the session is holding,
  next to a **Memory Limit** (default 2048 MB, 0 = no limit). Running out of
  memory does not raise in Blender, it takes the process and the unsaved file
  with it, so recording stops at the limit with everything captured so far
  kept and an explanation in the panel. Diagnostics reports the measured
  footprint, the running estimate, and how many snapshots are shared.
- **Modifier stacks are recorded** — each step captures every object's
  modifier list, in order, with its settings, and replay puts the stack back.
  Hard-surface sessions replayed as the naked control cage before this, with
  the Mirror/Bevel/Subdivision that was most of the work simply missing.
  Settings are read generically off `bl_rna` rather than from a per-type
  table, so modifier types SceneCast has never heard of are still captured;
  datablock links are stored by name and looked up again on replay. Two
  switches: **Capture Modifiers** while recording, **Replay Modifiers** while
  scrubbing and exporting.
- **Export resolution** — a **Resolution** picker in the Export box:
  720p/1080p/1440p/4K, **Vertical (1080x1920)** for Shorts, Reels and TikTok,
  **Square (1080x1080)**, Custom, or the scene's own settings. Independent of
  Output Properties, restored afterwards. A static view frames itself to the
  export's aspect rather than the viewport's, so a vertical export no longer
  loses the model out of the sides, and composited keystroke text is sized and
  placed from the shared layout table against the output height — a pixel size
  picked for 1080p was a rounding error at 4K.
- **Exporting from an unsaved file** — every output path defaults to `//`,
  "next to the .blend", which has nothing to point at before the file is first
  saved; it resolved against whatever folder Blender started in, often the
  root of `C:` or Blender's install folder, and the export failed or landed
  somewhere unexpected. An unsaved file now exports to `Documents\SceneCast`,
  the panel says so under the (red) path field before you export, and the
  report gives the full path afterwards. A folder that refuses a file comes
  back as something to do about it — choose a folder you own, or save the
  .blend — rather than an error number. The export also checks its
  destination before touching the scene, instead of leaving Edit Mode and
  moving the view first and then failing.
- **View filters** — an extension point in `viewnav`: anything registered
  gets the last word on where the camera sits, in every view mode, on all
  three paths that move it (scrub, playback, export), with the step index and
  the fraction between steps. Filters are always handed the view as it was
  *before* filtering, never their own previous output — in views that do not
  reset the camera every frame, that compounding is what made a 50%
  punch-in creep to full zoom. `refresh_view()` re-applies the camera to the
  paused step when a setting changes, so view settings take effect live.
  Nothing in the free build registers a filter; it is what the Pro punch-in
  and director camera hang off, and it costs a single emptiness check per
  frame when unused.
- **Export box hook** — an extension can draw into the Export box and choose
  which operator its button runs, so a paid build adds to the one Export
  button rather than growing a second export elsewhere. A hook that fails is
  reported inside the box instead of blanking the rest of the panel.
- **Fixed: the Scrub number now moves on Blender 5.0** — it sat at 0 through
  every recording and every playback, even though both were working. The
  playhead was moved with `scene["scenecast_playhead"] = idx`, a direct write
  to the property's storage that skips its update callback. Blender 5.0 keeps
  properties defined with `bpy.props` in a separate container from custom
  properties, so that line started creating an unrelated custom property
  instead, and the slider -- which reads the real one -- never saw a change.
  Writes now go through the property with the callback told to stand down,
  and the stray custom property is removed from scenes that picked one up.
  The playhead is also clamped to the session's length: it could be dragged
  past the last step and show a step that did not exist.
- **Fixed** — the keymap fallback that labels a step from its operator's
  shortcut referenced an undefined name and raised on every step that had no
  logged keys, so the fallback never once ran.

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
