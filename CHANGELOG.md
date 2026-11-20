# Changelog

Versions of the house scene format. Newest first. A minor version only adds (section 2 of FORMAT.md); each version is
a tag (`v1.0`, `v1.1` …) that House Planner and Fresing Render pin.

## 1.0.2 – 20 Nov 2026 – a second sample and the licence (tag `v1.0.2` by the owner)

House Planner task 0044. Packages stay version "1.0"; the format, the schemas and the checker are unchanged.
- `samples/example-house.hpscene`: House Planner's made-up example house as a second, more real-looking sample – three
  storeys, a 40° gable roof with windows and doors, furnished rooms, a terrace and a planted garden (for snow); exported
  by the app (Export → For Fresing Render…, version "Plan – study", groups house, furniture, ceiling lamps and garden –
  no electrics points, street, neighbours or park; Draft, Soft, summer and winter, morning / afternoon / evening, the
  current camera). 5.8 MB, 44,808 triangles, 297 surfaces, 1.17 light-map pages a moment. The checker passes it with no
  error or warning (a test). Not made by `tools/make_samples.py`: the brick box `sample-house.*` stays as it was.
- `LICENSE`: MIT.

## 1.0.1 – 15 Nov 2026 – clarifications and a stricter name check (tag `v1.0.1` by the owner)

Answers to Fresing Render's task 0114 (House Planner task 0030). Packages stay version "1.0"; samples unchanged.
- Section 2: what a UTF-8 name is (flag set, or pure ASCII); the checker now refuses a non-ASCII name without the flag
  (it accepted it, Python reading it as cp437).
- Section 8.3: `sun_light` is `[0, 0, 0]` under a full overcast by day; "facing the sun" is normal incidence, and how not
  to measure it at a low sun. Checker tests for `[0, 0, 0]` and `null` by day under `SOFT`.
- Section 10: unchanged (the 0.5° sun check judges the writer; a reader that reads on and reports a problem is already
  what it asks).
- Review fixes (Fresing Render lead): a zip name with the UTF-8 flag set that is not valid UTF-8 no longer crashes the
  checker – it is reported as "not a UTF-8 name" (broken-copy test); section 2 explains the third version number
  (1.0.1 = text and checker only, packages still say "1.0", the apps pin the tag).

## 1.0 – 13 Nov 2026 – first version (tag `v1.0` by the House Planner lead)

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
- After both leads' review: texel density per surface (`extras.hp.texels_per_m`, `recipe.quality.texels_per_m_by_group`;
  each map checked against its own surface – the plot of the sample at 6 texels/m); optional `sun_light` per moment
  (the sun's direct light for `SOFT` in absolute mode); the night sky in the bake as Fresing Render renders it; snow
  layers as new geometry by 0109's rule; Blender's import with Lighting Mode "Standard" and `lightbake.bake(...,
  sizes=...)` named in section 10.
