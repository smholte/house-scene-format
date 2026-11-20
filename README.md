# House scene format

The files between two apps, for one round trip:

- **House Planner** exports a house version as a **`.hpscene`** package: the house as glTF (`house.glb`) with a
  stable id on every surface, and a recipe of what to bake (place, seasons, moments of the day, weather, light
  choice, quality, cameras).
- **Fresing Render** (Blender + Cycles on a PC with a graphics card) imports it, bakes, and exports a **`.hpbake`**
  package: light maps per surface and moment, snow layers per season, photos and videos.
- House Planner imports the bake: live 3D – also on a phone – then looks close to a rendered photo, and the owner
  switches between the moments he baked.

This repository is the neutral ground both apps build on. It holds:

| What | Where |
| --- | --- |
| The format, in plain words with examples | [`FORMAT.md`](FORMAT.md) |
| JSON schemas of `scene.json`, `bake.json` and a surface's label (`extras.hp`) | [`schemas/`](schemas/) |
| Made-up sample packages both apps test against | [`samples/`](samples/) – the brick box `sample-house.hpscene` / `.hpbake` made by `tools/make_samples.py`; `example-house.hpscene` (1.0.2): House Planner's made-up example house (3 storeys, gable roof, furnished, a terrace and garden), exported by the app |
| The checker | `python3 check.py <package> [--scene <hpscene>]` |
| Reference code (glTF reading, the surface hash, the UV layout, the sun) | [`hsf/`](hsf/) |
| What changed | [`CHANGELOG.md`](CHANGELOG.md) |

Everything here is **public and made up**: no real house, plot, address or person.

## Use

```bash
python3 -m pip install -r requirements.txt
python3 check.py samples/sample-house.hpscene samples/sample-house.hpbake
python3 check.py samples/example-house.hpscene
python3 -m pytest -q tests
```

`check.py` prints `OK` or a list of errors (a reader must refuse the package) and warnings (readable, look at it);
the exit code is 1 when there is an error. A `.hpbake` given together with the `.hpscene` it names is also checked
against it.

## Versions

`v1.0`, `v1.1` … are tags. House Planner and Fresing Render each pin one and test against its samples. A newer
**minor** version only adds; a newer **major** version is refused by older apps with a clear message. How the format
is changed: [`CLAUDE.md`](CLAUDE.md).

## Licence

MIT ([`LICENSE`](LICENSE)).
