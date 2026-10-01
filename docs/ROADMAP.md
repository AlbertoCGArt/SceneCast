# Roadmap

Direction: tutorials and progress/evolution videos (teaching + timelapse).

The split: **free** makes one complete, shareable video easy. **Pro** is for
authoring a teaching artifact out of a session — editing it, narrating it,
directing it, branding it, keeping it.

## Tier 0 — Storage (the wall)
Was: a 50k-vert object filled 8 GB in ~360 steps, because topology was stored
as Python lists of tuples (~10x an int32 buffer) and unchanged objects were
copied in full every step.

- [x] int32 topology buffers instead of tuple lists (`meshdata.py`)
- [x] content-hash per object per step; unchanged objects share a reference
- [x] memory readout + budget that stops recording instead of losing the file
- [ ] quantized int16 coordinate deltas for same-topology runs, keyframe every
      N steps (video-codec model) — the remaining ~4x, and a lossy-quantisation
      decision that wants measuring first
- [ ] the same compact binary format as the on-disk save format (Pro,
      `pro/storage.py` — already shipping a dedup'd `.scast`)

## Tier 1 — Capture what artists actually do
- [x] Modifier stack snapshots (types, order, parameters) — `modifiers.py`
- [ ] Detect UV/material presence so topology rebuilds can warn about loss
- [ ] Active element (not just selection set)

## Tier 2 — The timeline as a real object  *(Pro)*
- [x] Bookmarks/notes with names, chapters in playback, titles in export
      (`pro/notes.py`)
- [ ] **Trim / merge / delete steps** — cut the boring stretches
- [ ] **Per-chapter retiming** — linger on the interesting edit, sprint
      through eight extrudes. The distance between a raw capture and
      something watchable.

## Tier 3 — Playback & export craft
- [x] Export resolution decoupled from render settings, with vertical and
      square presets (free)
- [x] Composited text overlay path, sized from the shared layout table (free
      core + `pro/vse_export.py`)
- [x] **Punch-in / focus** *(Pro)* — per-step camera push toward the active
      object or the selected vertices (`pro/focus.py`)
- [x] **Director camera** *(Pro)* — custom camera keys independent of the
      recorded views, eased in proportion to how far the camera travels
      (`pro/camera.py`)
- [x] **Branding** *(Pro)* — title card, end card, logo/text watermark
      (`pro/branding.py`)
- [x] **Written guide export** *(Pro)* — chapters + notes + keystrokes +
      per-step stills to Markdown and HTML (`pro/guide.py`). PDF still open.
- [x] **Headless export** *(Pro)* — `blender -b` with a camera built from the
      recorded angles, plus render-variants from one session
      (`pro/headless.py`). Renders through Workbench, not the viewport.
- [x] **View filter hook** (free core) — the extension point the two camera
      features hang off
- [ ] **Audio** *(Pro)* — import a VO track or record mic during capture;
      chapters snap to markers. The edit scene already exists, a sound strip
      is small.
- [ ] Undo-history pollution fix for edit-mode replay

## Tier 4 — Robustness
- [ ] UUID object identity (rename-proof)
- [ ] Own object creation so deletion can be replayed
- [ ] Off-thread snapshot compression (kill capture hitches). Packed
      `foreach_get` capture removed most of the per-step cost; what remains
      is the copy itself.

## Tier 5 — Session library *(Pro)*
- [x] Autosave on interval and save-with-.blend handler (`pro/library.py`)
- [x] A browser for `.scast` files, described from their headers
- [ ] Unify notes and steps: notes save with the .blend and steps don't, so a
      Clear Session leaves notes flagged stale. The session should be one
      thing.
