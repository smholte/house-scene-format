# CLAUDE.md – house scene format

The format between **House Planner** (`smholte/house-planner` public, `smholte/house-planner-dev` private) and
**Fresing Render** (`smholte/cad-render-animation`). Read `README.md`, then `FORMAT.md`.

## Rules

- **Changes only by a task** of House Planner or Fresing Render (its task file names this repository), never on the
  side. **Both lead chats review** every change before it is merged and tagged: the worker stops at a pushed branch,
  the owner carries each lead's OK. `main` is always a reviewed version.
- **Minor version = only additions**: new optional fields, new values in a list of choices (FORMAT.md section 13).
  Renaming, removing, changing a meaning or a rule (the hash, the UV rules, the encoding) = a **new major version**.
- **Every change** updates, in the same commit: `FORMAT.md`, the schemas, `tools/make_samples.py` and the samples it
  writes (`python3 tools/make_samples.py`), `check.py` / `hsf/` and their tests (a new rule gets a broken-copy test),
  and `CHANGELOG.md`. The checker's `SUPPORTED` version follows the format's.
- **Tags** `v1.0`, `v1.1` … are made on `main` after both leads' OK (the owner or a lead pushes the tag); both apps pin
  a tag. Never move a tag.
- **Public and made up only.** Never anything of the owner's house – no part of `smholte/house-planner-dev`'s `house/`,
  no real plot, address, name or photo. Samples come only from `tools/make_samples.py`. Fresing Render workers never
  attach `house-planner-dev`.
- Plain Python 3.10+ and PyPI (`requirements.txt`); no Blender, no Node in this repository's tests.
- Owner: Sebastian – plain language, results first (his rules: `CLAUDE.md` of either app).

## Tests

```bash
python3 tools/make_samples.py --check   # samples/ up to date
python3 check.py samples/*              # samples valid
python3 -m pytest -q tests              # the checker on the samples and on broken copies
```

GitHub runs the same at every push (`.github/workflows/check.yml`, about a minute).

## Things learned

- Blender's glTF importer (5.2.3) drops `TEXCOORD_1` when a primitive has no `TEXCOORD_0` (glTF numbers UV sets from
  0 without gaps): the light-map UVs vanished. A primitive with `TEXCOORD_1` must have `TEXCOORD_0` (checked).
- Blender's importer keeps vertex count and order (merge vertices off), turns v into 1 − v and keeps `extras` as a
  custom property (`ob["hp"]`); glTF (x, y, z) arrives as Blender (x, −z, y).
