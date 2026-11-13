# Changelog

Versions of the house scene format. Newest first. A minor version only adds (section 2 of FORMAT.md); each version is
a tag (`v1.0`, `v1.1` …) that House Planner and Fresing Render pin.

## 1.0 – draft (13 Nov 2026) – not tagged yet

First version (House Planner task 0016), for the two leads' review:
- `.hpscene` (scene.json + house.glb) and `.hpbake` (bake.json + light-map pages, light per vertex, snow, photos,
  videos); versions `major.minor`, a newer major refused.
- Surfaces with stable ids, storey, Show-button group, bake kind (`MAP` / `VERTEX` / `NO`) and the surface hash
  `hp-hash/1`; light-map UVs `hp-uv/1` laid out by House Planner.
- Recipe: light choice (Fresing Render 0107: `LIVE` / `SOFT` / `ALL`), quality, what is included, storeys baked
  "open", seasons (0109: snow cover, wet; foliage), moments with House Planner's sun, cameras, photos, turntable
  videos. Walk paths reserved for a later minor version.
- Made-up samples (`tools/make_samples.py`), `check.py`, tests, GitHub workflow.
