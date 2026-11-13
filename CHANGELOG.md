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
- After an independent review (same task): light stored as absolute L with an exact encode (not 0107's factor F);
  pages PNG only, 8-bit RGB without colour chunks, loaded raw; meshes every reader reads alike (triangles, float
  positions and light-map UVs, every vertex used, no sparse accessors); the UV rules checked in full (no stretching,
  no folds) and the map size in the hash; one scene, single parents, no required extensions; no NaN and no control
  characters in JSON; open and closed lists of choices (minor versions extend only the open ones); the checker reports
  a hostile file instead of crashing.
