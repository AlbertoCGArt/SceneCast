# Roadmap

Direction: tutorials and progress/evolution videos (teaching + timelapse).

## Tier 0 — Differential storage (the wall)
The current scheme stores full topology per step as Python lists (~10x
heavier than numpy) and full copies of unchanged objects (~Nx waste on
N-object scenes). Measured: a single 50k-vert object fills 8 GB in ~360
steps. Plan:
- numpy int32 topology buffers (edges/faces) instead of tuple lists
- content-hash per object per step; unchanged objects store a reference
- quantized int16 coordinate deltas for same-topology runs, keyframe
  every N steps (video-codec model)
- the same compact binary format becomes the on-disk save format ->
  persistence falls out for free

## Tier 1 — Capture what artists actually do
- Modifier stack snapshots (types, order, parameters) — cheap, closes the
  biggest blind spot for hard-surface work
- Detect UV/material presence so topology rebuilds can warn about loss
- Active element (not just selection set)

## Tier 2 — The timeline as a real object
- Bookmarks with names ("blockout done", "detail pass")
- Chapters in playback; titles in export
- Trim/merge steps; delete boring stretches

## Tier 3 — Playback & export craft
- Distance-proportional camera transition speed
- Custom camera keyframes independent of recorded views
- Export resolution decoupled from render settings; overlay control
- Composited text overlay path (guaranteed keys-in-video, independent of
  viewport-render overlay behavior)
- Undo-history pollution fix for edit-mode replay

## Tier 4 — Robustness
- UUID object identity (rename-proof)
- Own object creation so deletion can be replayed
- Off-thread snapshot compression (kill capture hitches)
