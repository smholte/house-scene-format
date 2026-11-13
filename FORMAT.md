# House scene format – version 1.0

The files between **House Planner** (plans a house; three.js in a browser, also on a phone) and **Fresing Render**
(Blender 5.2 + Cycles on a PC with a graphics card) for one round trip:

```
House Planner  ── Export to Fresing Render ──▶  house.hpscene   (the house + a recipe of what to bake)
Fresing Render ── Import from House Planner, Bake, Export ──▶  house.hpbake   (light, snow, photos back)
House Planner  ── Import bake ──▶  the version shows baked light; switching moments is instant on any device
```

Status: **draft for the two leads' review** (task 0016 of House Planner). Nothing is final until the tag `v1.0`.
The words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119. The schemas in `schemas/` are part of this text;
where they and this text differ, tell the leads – it is a bug in one of them.

Contents: 1 Ideas · 2 Packages and versions · 3 Coordinates · 4 Surfaces · 5 The surface hash · 6 Light-map UVs ·
7 scene.json · 8 bake.json · 9 How House Planner uses a bake · 10 How Fresing Render reads a scene · 11 Sizes ·
12 Samples and the checker · 13 Options of version 1.0

---

## 1. Ideas

- **The house travels as glTF**, the format both apps already read and write. Every piece of geometry is a node with
  a stable id; nothing is matched by name or by order.
- **Results are per surface.** A wall side, a floor, a roof face each get their own light (their own rectangle on an
  atlas page, or their own values per vertex). House Planner can hide a storey, a Show-button group or a single piece
  and the rest keeps its baked light.
- **A surface knows when its bake is out of date**: each carries a hash of its geometry. When the owner changes a
  wall after a bake, that wall's hash changes; House Planner shows live light there and says so.
- **House Planner decides the light-map UVs**, the same way every time, and sends them (UV set 1). Fresing Render
  bakes onto them as they are (its 0107 `lightbake.bake(..., uv="UV1")`) and never unwraps the house.
- **House Planner decides where the sun is** for every moment and writes it out. Fresing Render does not work it out
  again – so the bake's shadows fall where House Planner's own sun puts them.
- **Fresing Render's own features are called, not copied**: the three light choices of its 0107 (`LIVE`, `SOFT`,
  `ALL`) and the weather settings of its 0109 (clouds, snow cover, wet, wind) are used by name.

## 2. Packages and versions

Both packages are **zip files** (stored or deflated, no encryption, UTF-8 names, forward slashes, no absolute paths,
no `.` or `..` parts, no file listed twice). Readers MUST refuse anything else. Pictures and `.glb` files SHOULD be
stored (they are compressed already), JSON deflated.

| Package | Extension | Holds |
| --- | --- | --- |
| House scene | `.hpscene` | `scene.json` (required), `house.glb` (required), `pictures/…` (optional: `preview.png`) |
| Bake | `.hpbake` | `bake.json` (required), `light/…` (atlas pages `.png`/`.jpg`, optional `.ktx2` copies, vertex light `.bin`), `snow/…` (`.glb` per season), `photos/…` (`.jpg`/`.png`), `videos/…` (`.mp4`/`.webm`) |

Paths other than `scene.json`, `bake.json` and `house.glb` are free; the JSON names every file it uses. A file the
JSON does not use is a warning, not an error.

**Versions.** `scene.json` and `bake.json` start with `"format": "house-scene"` / `"house-bake"` and
`"version": "<major>.<minor>"` (this text: `"1.0"`). A reader written for version *M.n*:

- MUST refuse a package of another **major** version with a clear message, e.g. *"This bake was made by a newer
  Fresing Render (format 2.0). Update House Planner to read it."* – never read half of it.
- MUST read a newer **minor** version (*M.n+1* …) and ignore fields it does not know. A minor version only ever
  **adds** optional fields or new values in places where readers are told to skip what they do not know (section 13).
- SHOULD tell the user once when it read a newer minor version ("made by a newer app; some extras are not shown").

Both apps pin a tag of this repository (`v1.0`, `v1.1`, …) and test against its samples. House Planner offers in its
export dialog only what the pinned version lists (section 13).

## 3. Coordinates and units

- glTF's own axes and units: **metres, +Y up, right-handed**. House Planner's plan point (x, y) at height h is the
  glTF point **(x, h, y)**: plan x → +X, plan y (drawn downwards on the plan) → +Z. Seen from above, +X is to the
  right and +Z towards the bottom of the plan.
- Blender's glTF importer turns this into Blender's Z-up: glTF (x, y, z) → Blender (x, −z, y). (Measured with
  Blender 5.2.3: a table node at glTF (3.5, 0, 3.0) arrives at (3.5, −3.0, 0).)
- `place.north` is a unit vector **[x, z]** in the horizontal plane pointing to geographic north. House Planner
  writes `[sin n, −cos n]` for its `site.north` = n degrees (its `planDir(site, 0)`). East is north turned 90°
  clockwise seen from above: `[−north.z, north.x]`.
- Directions of the sun: unit vector from the house **towards** the sun, in glTF axes (section 7.5).
- Times: a date `YYYY-MM-DD`, a clock time `HH:MM` and the clock's `utc_offset` (`+02:00` = Dutch summer time).
- Colours and light are linear RGB (Rec.709 primaries), not sRGB-encoded, unless a picture file says otherwise.

## 4. Surfaces (`house.glb`)

`house.glb` is a binary glTF 2.0 file with **one scene**. Its pictures are inside it (PNG or JPEG; no KTX2, no
Draco or meshopt compression in version 1 – both apps must read it without extensions). It holds exactly the parts
the recipe includes (section 7.3), nothing else.

**Every node that has a mesh is a surface** and MUST carry `extras.hp`; a node without a mesh MAY carry it only when
it is a lamp (section 4.4). Grouping nodes without a mesh carry no `extras.hp`. The node's `name` MUST equal its id
(Blender keeps names up to 63 bytes – ids are never longer). Blender's importer keeps `extras` as a custom property
`hp` on the object (measured, Blender 5.2.3).

```json
"extras": { "hp": {
  "id": "wall:w_g_front:a", "kind": "wall", "storey": "st_ground", "group": "house",
  "bake": "MAP", "hash": "1f0c…(32 hex)", "uv1_px": [116, 52],
  "source": "w_g_front", "material": "plaster"
} }
```

| Field | | Meaning |
| --- | --- | --- |
| `id` | required | Unique in the package (and across `house.glb` and the bake's snow files). `<kind>:<name>`, letters, digits and `_ . : -`, at most 63 bytes. **Stable**: the same piece gets the same id in every export of the same house version. |
| `kind` | required | What it is (table below). |
| `storey` | required | The storey id (section 7.2) the piece belongs to, or `null` for parts of the plot and the neighbourhood (groups `garden`, `street`, `houses`, `park` – and only they). |
| `group` | required | Which of House Planner's **Show buttons** hides it: `house` (the building; follows the storey choice), `garden`, `street`, `houses` (Neighbours), `park` (Water & park), `furniture`, `installs` (Electrics), `ceilItems` (Ceiling). These are House Planner's own settings keys. |
| `bake` | required | `MAP` (a light map on UV set 1), `VERTEX` (light per vertex), or `NO` (takes part in the light – casts shadows, lets light through by its material – but gets no result). |
| `hash` | required with a mesh | The surface hash (section 5). |
| `uv1_px` | required for `MAP` | [W, H]: the size in texels of this surface's light map (section 6). |
| `source` | optional | The id in House Planner's model the piece comes from (wall, room, furniture item, garden area …). Several surfaces can share one (a wall's two sides and edge). For furniture it names the **piece** that moves as a whole. |
| `material` | optional | House Planner's material id (`oak`, `brick`, …): lets Fresing Render swap in its own, better looks later. The glTF material holds the look itself. |
| `on` | snow only | The id of the surface a snow layer lies on (section 8.6). |

### 4.1 Kinds and ids

The id is House Planner's own business, but it MUST NOT depend on the order of export or on anything that changes
without the piece changing. Recommended forms (the samples use them):

| kind | What | Recommended id | Usual `bake` |
| --- | --- | --- | --- |
| `wall` | one side of a wall, or its edge (top, ends, the reveals round its openings) | `wall:<wall id>:a` / `:b` (a = left of a→b on the plan) / `:edge` | MAP |
| `floor` | a room's floor (top) | `floor:<room id>` | MAP |
| `ceiling` | a room's ceiling (underside of the storey above) | `ceiling:<room id>` | MAP |
| `slab-edge` | edges of a floor slab: round a stair void, round the house | `slab-edge:<void id>` | MAP |
| `roof` | one roof face (with its underside when seen) | `roof:<storey id>:<n>` | MAP |
| `opening` | a door or window frame, a door leaf | `opening:<opening id>` | VERTEX |
| `glass` | glass in a window or door | `glass:<opening id>` | **NO** (always) |
| `stair` | a stair | `stair:<stair id>` | MAP |
| `furniture` | one mesh of a furniture piece | `furniture:<item id>:<n>` | VERTEX |
| `install` | electrics and other things on walls and ceilings | `install:<point id>` | VERTEX |
| `lamp` | a light fitting (its body and/or its light) | `lamp:<point id>` | VERTEX or NO |
| `ground` | the plot's ground (split in tiles when it does not fit a page) | `ground:plot` / `ground:plot:<n>` | MAP |
| `garden` | a garden area, path, wall, hedge, pond edge | `garden:<area or line id>` | MAP |
| `plant` | a plant, shrub, a tree's trunk and branches | `plant:<id>` | VERTEX |
| `foliage` | a tree's or hedge's leaves | `foliage:<id>` | VERTEX |
| `street` | road, pavement, kerb, street furniture | `street:<n>` | MAP |
| `neighbour` | a house around the plot | `neighbour:<n>` | MAP or NO |
| `water` | water | `water:<n>` | **NO** (always) |
| `park` | quays, reeds, the park | `park:<n>` | MAP |
| `snow` | a snow layer – only in a bake's snow files | `snow:<id of the surface it lies on>` | VERTEX |
| `other` | anything else | `other:<n>` | any |

Surfaces whose map would be larger than a page (section 6) MUST be split into several surfaces (`ground:plot:0`,
`ground:plot:1` …).

### 4.2 Geometry

- Triangles only (primitive mode 4), with `POSITION` and `NORMAL`; `TEXCOORD_0` (the texture UVs House Planner uses
  for its materials) and `indices` SHOULD be there. `MAP` surfaces add **`TEXCOORD_1`** (the light-map UVs).
  glTF numbers UV sets from 0 without gaps: a primitive with `TEXCOORD_1` MUST have `TEXCOORD_0` (Blender's importer
  drops the light-map UVs otherwise – found while making the samples).
- A mesh MAY be used by several nodes (a furniture model placed twice); each node is its own surface with its own
  result.
- A node MAY be placed by a transform (furniture, lamps, plants). House parts are usually written in place (no
  transform). Either is fine; a bake records the world matrix of every surface that has one (section 8.2).

### 4.3 Materials

Plain glTF metallic-roughness materials with their pictures inside the `.glb`. Glass: `alphaMode` `BLEND` (and MAY
add `KHR_materials_transmission`, which other viewers may ignore); kind `glass`, bake `NO`. Fresing Render bakes with
the parts' own materials (0107: glass and see-through parts let light through).

### 4.4 Lamps

A lamp is a node with a `KHR_lights_punctual` light (glTF's own lamp extension: point or spot, colour, intensity in
candela, range), kind `lamp`, and `extras.hp` (group `ceilItems` or `installs`). It MAY have a mesh (the fitting),
then it is also a surface (usually `VERTEX`); without a mesh its `bake` is `NO` and it has no hash. Each moment says
which lamps are on (section 7.5). Blender's importer makes the light a child object of the fitting (measured).

## 5. The surface hash (`hp-hash/1`)

A surface's hash changes when its geometry or its light-map UVs change, and only then. It is worked out from the
mesh **as stored in the .glb** (float32 values), in the node's own coordinates (its transform is not part of it):

```
h = SHA-256 of:  "hp-hash/1" + one zero byte
  for each primitive of the mesh, in order:
    "P"  + uint32 vertex count
         + int32 x, y, z of each vertex   = round(coordinate × 1000)          (millimetres)
    "U"  + uint16 u, v of each vertex      = clamp(round(TEXCOORD_1 × 65535), 0, 65535)   when TEXCOORD_1 is there
    "N"                                                                       when it is not
         + uint32 index count + uint32 each index        (0, 1, 2 … when the primitive has no indices)
hash = the first 32 hex digits (lower case) of h
```

All numbers little-endian. `round` is *round half away from zero* – in JavaScript
`Math.sign(x) * Math.floor(Math.abs(x) + 0.5)`, never `Math.round` (which rounds −0.5 up). Normals, texture UVs and
materials are not in the hash: a new floor colour does not throw a bake away. The order of vertices and indices
**is** in it: light per vertex (section 8.4) follows that order.

`scene_hash` = the first 32 hex digits of SHA-256 over the lines `"<id> <hash>\n"` of all surfaces with a hash,
sorted by id (UTF-8). It identifies one export.

`hsf/surface.py` is the reference; `check.py` recomputes every hash.

## 6. Light-map UVs (`hp-uv/1`)

House Planner lays out `TEXCOORD_1` for every `MAP` surface. Each surface has **its own map** of `uv1_px` = [W, H]
texels, and UV (0, 0)…(1, 1) covers exactly that map (glTF convention: (0, 0) is the top-left corner of the top-left
texel). The bake gives each map its own rectangle on an atlas page, and House Planner turns UV set 1 into the page's
coordinates with one scale and offset per surface (no geometry is changed):

```
page_uv = ((rect.x + u × W) / page_width,  (rect.y + v × H) / page_height)       rect.w = W, rect.h = H
```

Rules (checked by `check.py`):

1. Texel density: `texels_per_m` of the recipe (section 7.1). W and H follow from it; each is at most
   `page_size − 4`.
2. A surface's triangles fall into **charts** – flat, connected pieces that share their UV points (a wall side with its
   window hole is one chart; each face of a step is one). Each chart is projected onto its own plane without
   stretching (1 m = `texels_per_m` texels).
3. Charts are packed by their **rectangles**: at least **4 texels** between two charts' rectangles, at least
   **2 texels** from a chart to the edge of the map. All UVs lie in 0 … 1. So nothing overlaps and the baker's
   padding (Cycles' bake margin) can fill the gutters.
4. The same surface gives the same layout every time (the hash includes the UVs).

`hsf/uv1.py` is the reference layout (projection: faces looking mostly up or down use (x, z); other faces use the
horizontal direction in the face and the height, top row first; rectangles packed in rows, tallest first). A better
packer is allowed as long as rules 1–4 hold.

Because the UVs follow from `texels_per_m`, a bake MUST use the recipe's `texels_per_m` exactly; a bake at another
density needs a new export.

**In Blender** (measured, 5.2.3, the sample): `TEXCOORD_1` becomes the second UV layer (`UVMap.001`) with
v → 1 − v, and the vertex count and order are kept (the importer's "merge vertices" off, its default). So Blender's
row 0 of a baked image is the **bottom** of the map: write it to the page bottom-up (PNG row r = Blender row H−1−r).

## 7. `scene.json`

```json
{
  "format": "house-scene", "version": "1.0",
  "generator": {"app": "House Planner", "version": "39"},
  "id": "sample-house-a", "created": "2026-11-13T12:00:00Z", "title": "Made-up sample house",
  "house": {"version_id": "v_sample", "version_name": "Made-up plan"},
  "files": {"house": "house.glb", "preview": "pictures/preview.png"},
  "hash": "hp-hash/1", "uv1": "hp-uv/1", "scene_hash": "a28f32e0…",
  "place": {"latitude": 53.5, "longitude": 3.5, "north": [0.258819, -0.965926], "ground_level": -0.15},
  "storeys": [{"id": "st_ground", "name": "Ground floor", "level": 0, "elevation": 0.0, "height": 2.8}, …],
  "recipe": { … }
}
```

- `id`: unique per export (House Planner makes a new one each time). The bake names it.
- `house`: which version of the house (the owner's plans have versions); shown, not used for matching.
- `place.ground_level`: height of the ground outside (m, glTF y). `storeys[].level`: 0 = ground floor, 1, 2 …
  (−1 a cellar); `elevation`: floor height; `height`: storey height.

### 7.1 `recipe.light`, `recipe.quality`

| `light` | Fresing Render (0107) | What is baked | What House Planner keeps live |
| --- | --- | --- | --- |
| `LIVE` | Live only | nothing (only snow, photos, videos) | everything |
| `SOFT` | Soft light baked, sun live | sky light without the sun's direct light, all bounce light (also of the sun), the lamps that are on | the sun's direct light and its moving shadows, reflections |
| `ALL` | Everything baked | sky + sun + lamps, direct and bounce | reflections and the sun's highlight; no live matte sun on baked surfaces |

`quality`: `preset` (`DRAFT` / `NORMAL` / `FINE`: 0107's samples 16 / 64 / 256 when `samples` is null),
`texels_per_m` (4 … 400, decided by House Planner from the preset and the area – it lays out the UVs for it),
`samples` (or null = from the preset), `page_size` (1024 or 2048: the largest atlas page the bake may write).

### 7.2 Storeys

The list of the house version's storeys. Surfaces name theirs; "above" and "below" go by `level`.

### 7.3 `recipe.include`

`storeys` (ids) and `groups` (Show-button keys, section 4) in the export. `house.glb` holds exactly those; a
neighbour that should only cast shadows is still included (bake `NO`).

### 7.4 `recipe.open_storeys`

Storeys to bake **also without everything above them** – as House Planner shows one storey seen from above. Their
results come as a second set (`open`) in each moment (section 8.3), for that storey's surfaces only.

### 7.5 Seasons and moments

```json
"seasons": [{"id": "winter", "label": "Winter", "date": "2026-01-15",
             "snow_cover": 0.6, "wet": 0.2, "foliage": "bare"}],
"moments": [{"id": "summer-morning", "label": "Morning", "season": "summer",
             "time": "09:00", "utc_offset": "+02:00",
             "sun": {"azimuth": 89.564, "elevation": 29.351, "direction": [0.843629, 0.490152, 0.219185]},
             "sky": {"clouds": 0.1, "low_clouds": 0.0, "visibility": 40000.0},
             "lamps": "none"}]
```

- A **season** is a date and what lies on the ground: `snow_cover` 0 … 1 (0109's `snow_cover`: 1 ≈ 10 cm on upward
  faces under the open sky), `wet` 0 … 1 (0109), `foliage` `full` / `autumn` / `bare` (bare: the baker hides
  `foliage` surfaces – leafless trees cast less shadow).
- A **moment** is one light situation the owner picks (I22: morning, afternoon, evening, night …): a clock time on its
  season's date, the sky (0109's `clouds`, `low_clouds`, `visibility` in metres) and which lamps are on (`"all"`,
  `"none"` or a list of lamp ids). Each moment gets its own baked light; the owner chooses which combinations to bake.
- `sun` is written by House Planner with its own sun formula (NOAA, `src/sun.js`; `hsf/sun.py` is the same):
  `azimuth` degrees clockwise from north, `elevation` degrees above the horizon (negative at night) and `direction`,
  the unit vector towards the sun in glTF axes (section 3). The baker MUST use these – for Fresing Render:
  `lightbake.bake(..., sky={"sun_height": elevation, "sun_direction": <direction turned into the scene's azimuth>})`
  – and not work the sun out from the time. The checker warns when the sun is more than 2° from where it stands at
  the date, time, offset and place (a time-zone mistake).

### 7.6 Cameras, photos, videos

```json
"cameras": [{"id": "garden-view", "label": "From the garden", "position": [3.5, 1.7, 22.0],
             "target": [3.5, 2.5, 4.5], "fov": 50.0}],
"photos": [{"id": "photo-1", "camera": "garden-view", "moment": "summer-morning", "size": [320, 240],
            "falling": {"rain": 0.0, "snow": 0.0, "wind": 2.0, "wind_from": 225.0}}],
"videos": [{"id": "turn", "kind": "turntable", "camera": "garden-view", "moment": "summer-morning",
            "size": [1280, 720], "seconds": 8, "fps": 25}]
```

Cameras: glTF axes, `fov` = vertical field of view in degrees, up = +Y. A photo or video is rendered at a moment;
`falling` (optional) adds what only renders show: falling `rain` and `snow` 0 … 1 (0109), `wind` in Beaufort and
`wind_from` (compass bearing). Version 1 has one video kind, `turntable` (around the camera's target).
**Walk paths** (a route through the house, rendered as a walk-through video) are reserved for a later minor version:
a `recipe.walk_paths` list and a video kind `walk`.

## 8. `bake.json`

```json
{
  "format": "house-bake", "version": "1.0",
  "generator": {"app": "Fresing Render", "version": "0.2.90"},
  "id": "sample-bake-a", "created": "2026-11-13T12:00:00Z",
  "scene": {"id": "sample-house-a", "scene_hash": "a28f32e0…"},
  "light": "SOFT", "uv1": "hp-uv/1",
  "quality": {"texels_per_m": 16.0, "samples": 16, "denoised": true},
  "surfaces": { "<id>": {"hash": "…", "box": [x0, y0, z0, x1, y1, z1], "matrix": [16 numbers]} },
  "pages": [{"id": "p0", "file": "light/p0.png", "size": [1024, 1024]}],
  "vertex_files": [{"id": "v0", "file": "light/v0.bin"}],
  "moments": [{"id": "summer-morning",
               "encoding": {"curve": 2.0, "scale": 1.073523, "reference": [1.0, 0.97, 0.92], "exposure": 0.0},
               "maps": {"floor:r_bed": {"page": "p0", "rect": [871, 0, 55, 88]},
                        "furniture:f_table:0": {"vertex": "v0", "offset": 96, "count": 88}},
               "open": {"st_ground": { … same form, that storey's surfaces only … }}}],
  "snow": [{"season": "winter", "file": "snow/winter.glb"}],
  "photos": [{"id": "photo-1", "file": "photos/photo-1.png", "size": [320, 240], "moment": "summer-morning",
              "camera": {"position": […], "target": […], "fov": 50.0}}],
  "videos": [],
  "problems": ["Roof 12: no UV set 1 – baked per vertex"]
}
```

### 8.1 Which export

`scene.id` and `scene.scene_hash` name the export the bake was made from. `light`, `uv1` and
`quality.texels_per_m` MUST be the recipe's.

### 8.2 `surfaces`

Every surface that has a result, with its `hash` **at bake time**, its world bounding `box` (metres, glTF axes) and –
when its node had a transform – its world `matrix` (column-major, as glTF). These let House Planner decide later
what is out of date (section 9), also for pieces that have since been moved or deleted.

### 8.3 Light: `moments`, pages and `maps`

One entry per baked moment of the recipe. `maps` holds the results of the whole export; `open` holds, per storey of
`recipe.open_storeys`, the results of that storey's surfaces with everything above it left out.

A result is either **on a page** – `{"page", "rect": [x, y, w, h]}` in texels, (0, 0) = the page's top-left
corner, `w × h` = the surface's `uv1_px` – or **per vertex** (8.4). A surface is `MAP` in the scene ⇔ its result is on
a page; `VERTEX` ⇔ per vertex.

**Pages** are PNG (lossless, preferred) or JPEG (quality ≥ 90) pictures, 8-bit RGB, 256, 512, 1024 or 2048 px on
each side and at most the recipe's `page_size`. Rectangles on a page MUST NOT overlap; the baker SHOULD leave 2 texels between them
and fill each rectangle's gutters (rule 3 of section 6). A page MAY carry an optional `ktx2` copy (Basis Universal,
same size, for phones – 0009); a reader that does not use KTX2 ignores it.

**Encoding** (the same curve as 0107's `core/lightmap.encode`): a stored byte `b` (0 … 255) per channel means

```
L = scale × (b / 255) ^ curve          curve = 2.0
```

`L` is linear RGB light: **the colour a white matte surface shows** (0107's units: Cycles DIFFUSE without colour,
before exposure and view transform). Multiply by a surface's base colour for its matte look. `scale` is one number per
moment (0107: the 99.9th percentile of the moment's values, at least the reference). `reference` = the same light on
an open, upward-facing surface with nothing round it (0107's probe) – `L / reference` is the *light factor* (1 =
open sky above, corners < 1). `exposure` = the EV Fresing Render's render of that moment uses (0109's exposure
channel), so night moments can be shown as bright as Fresing Render shows them.

House Planner can show a moment two ways: **factor** – `L / reference` times its own sky light (as 0107's web page
does: baked and live surfaces agree even if its sky differs a little from Cycles'); or **absolute** – `L` × 2^exposure
(for night moments, where `reference` is near 0).

### 8.4 Light per vertex

`vertex_files` are raw `.bin` files: 3 bytes (R, G, B; the encoding of 8.3, with the moment's `scale`) per vertex.
A result `{"vertex", "offset", "count"}` starts at vertex `offset` of that file; `count` MUST equal the surface's
vertex count (all its primitives, in order) and the values follow the `.glb`'s vertex order. Several surfaces and
moments may share one file.

### 8.5 Furniture and other placed pieces

Furniture is baked `VERTEX` (no UV layout needed for library models) and its node's world `matrix` is recorded.
House Planner's rule (proposed – section 9) decides what happens when a piece moves.

### 8.6 Snow

One `.glb` per season with snow (`snow`). Each node is a **snow layer on one surface**: kind `snow`, `on` = that
surface's id, its `storey` and `group` (so it hides with the surface), `bake` `VERTEX` and a `hash`. The layers are in
the scene's coordinates and their light is in the moments of that season (`maps` keyed by the snow ids). Fresing
Render makes them from its 0109 snow (upward faces under the open sky, thickness from `snow_cover`); House Planner
shows them with its own snow material. Falling snow is only in photos and videos.

### 8.7 Photos, videos, problems

Photos (`.jpg` or `.png`) and videos (`.mp4` or `.webm`) of the recipe, with the camera and moment they were made
with. `problems`: plain sentences for the owner (what was skipped or changed); House Planner shows them after import.

## 9. How House Planner uses a bake (proposed – I24b decides the details)

- **Matching:** for each surface of the version as it is now, House Planner builds its export geometry and hash. A
  baked result is used only when the surface's id and hash match the bake's `surfaces`. Otherwise the surface is
  **out of date**: it gets live light, and House Planner says so ("3 parts changed since the bake – Bake again").
  A surface the bake does not know has no bake (live light).
- **Neighbours of a change:** a changed wall also changes the shadows round it. Proposed: surfaces whose `box` comes
  within 0.5 m of a changed or deleted surface's old or new box count as out of date too.
- **Furniture moved** (its `matrix` differs; hash the same): the piece **keeps its own baked light** (mostly its own
  shading); the surfaces near its old and new place (the boxes, + 0.3 m) are out of date. A deleted piece: the
  surfaces near its old box. A new piece: live light, and the surfaces near it out of date.
- **Show buttons, storeys, Explode, cut walls, walk mode** keep working: results are per surface, so a hidden surface
  simply is not drawn; Explode moves whole storeys (the maps go with them); cut walls clip the drawn wall as now
  (the cut's cap stays live); walk mode is just another camera.
- **One storey seen from above:** when the storeys above a storey are hidden and the bake has `open` results for it,
  that storey's surfaces use them; all others use `maps`.
- **Snow** layers are shown with their surface and hidden when it is hidden or out of date.
- The bake is stored in the asset library (0009) with the house version, one moment loaded at a time.

## 10. How Fresing Render reads a scene (for I24c)

- Import `house.glb` with Blender's glTF importer (merge vertices off). Each object's custom property `hp` is its
  label; `hp["id"]` is the id to write results under (0107's `ids={object: hp["id"]}`).
- `MAP` objects: `lightbake.bake(objects, light=recipe.light, uv="UV1", texels_per_m=recipe.quality.texels_per_m,
  samples=…, sky=<the moment's sun>, lamps=<the moment's lamps>, ...)`; `Item.pixels` (H × W, Blender rows bottom-up)
  → the page rectangle (top-down). `VERTEX` objects: `uv="VERTEX"`; `Item.values` → the vertex file in the glb's
  vertex order. `NO` objects take part in the light only.
- Per moment: move the sun (`sky`), set clouds and lamps; per season: build the snow (0109's snow on imported
  objects, `weather_look.add_objects`), hide `foliage` when `bare`; for each `open` storey: hide what lies above it
  and bake that storey's objects again.
- Encode with the moment's `scale` and write the package.

## 11. Sizes (phones)

- Pages of 1024 px (phones) or 2048 px (PC); House Planner sets `page_size`. One moment SHOULD fit in **4 pages**
  (the checker warns above that): on a phone one moment's pages are held in memory, 4 × 1024² × 4 bytes = 16 MB.
- `texels_per_m`: about 16 (Draft) … 40 (Fine) for a house; the sample house (two storeys, 7 × 9 m, plot
  15 × 23 m) at 16 texels/m fills 37 % of one 1024 px page per moment, 51 % with its open ground floor.
- Furniture, frames, lamps and plants per vertex (3 bytes a vertex): small.
- `house.glb`: the checker warns above 300 MB.

## 12. Samples and the checker

- `samples/sample-house.hpscene` and `samples/sample-house.hpbake`: a **made-up** two-storey house at a made-up place
  at sea (two rooms per storey, a stair void, a window, a terrace, a table, a ceiling lamp; four moments in two
  seasons, snow on the roof and the plot, one photo). Their light maps are invented flat shades, not a real bake.
  `tools/make_samples.py` makes them again (same bytes every time); both apps' tests use them.
- `python3 check.py <package> [--scene <hpscene>]`: schema, versions, ids, hashes (recomputed), UV rules, page
  rectangles, vertex counts, and – with the scene – whether the bake fits it. ERROR = a reader must refuse it;
  WARNING = readable, look at it.

## 13. Options of version 1.0

What House Planner may offer and Fresing Render must handle. A later minor version adds to these lists; readers
skip values they do not know (a moment with an unknown `lamps` value, a video of an unknown kind, an unknown `kind`
of surface – treated as `other`, an unknown `group` – treated as `house`).

| Where | Values |
| --- | --- |
| `recipe.light` | `LIVE`, `SOFT`, `ALL` |
| `recipe.quality.preset` | `DRAFT`, `NORMAL`, `FINE` |
| `recipe.quality.page_size` | 1024, 2048 |
| `seasons[].foliage` | `full`, `autumn`, `bare` |
| `moments[].lamps` | `all`, `none`, a list of lamp ids |
| `videos[].kind` | `turntable` |
| `videos[].fps` | 24, 25, 30, 50, 60 |
| surface `kind` | section 4.1 |
| surface `group` | `house`, `garden`, `street`, `houses`, `park`, `furniture`, `installs`, `ceilItems` |
| surface `bake` | `MAP`, `VERTEX`, `NO` |
| result | page rectangle, per vertex |
| pages | PNG, JPEG (+ optional KTX2 copy); 256, 512, 1024, 2048 px a side |
| photos / videos | JPEG, PNG / MP4, WebM |
