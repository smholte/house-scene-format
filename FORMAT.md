# House scene format – version 1.0.1

The files between **House Planner** (plans a house; three.js in a browser, also on a phone) and **Fresing Render**
(Blender 5.2 + Cycles on a PC with a graphics card) for one round trip:

```
House Planner  ── Export to Fresing Render ──▶  house.hpscene   (the house + a recipe of what to bake)
Fresing Render ── Import from House Planner, Bake, Export ──▶  house.hpbake   (light, snow, photos back)
House Planner  ── Import bake ──▶  the version shows baked light; switching moments is instant on any device
```

Status: **version 1.0 reviewed by both leads (13 Nov 2026), tag `v1.0`; text 1.0.1 (15 Nov 2026, task 0030) only
clarifies – the packages are still version "1.0" – and makes the checker refuse what section 2 already forbade.** The words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119. The schemas
in `schemas/` are part of this text; where they and this text differ, tell the leads – it is a bug in one of them.

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
stored (they are compressed already), JSON deflated. A name is UTF-8 when the zip's UTF-8 flag (general purpose bit 11)
is set, or when its bytes are all ASCII (many writers set the flag only for non-ASCII names); a name without the flag
that holds any other byte MUST be refused.

| Package | Extension | Holds |
| --- | --- | --- |
| House scene | `.hpscene` | `scene.json` (required), `house.glb` (required), `pictures/…` (optional: `preview.png`) |
| Bake | `.hpbake` | `bake.json` (required), `light/…` (atlas pages `.png`, optional `.ktx2` copies, vertex light `.bin`), `snow/…` (`.glb` per season), `photos/…` (`.jpg`/`.png`), `videos/…` (`.mp4`/`.webm`) |

Paths other than `scene.json`, `bake.json` and `house.glb` are free; the JSON names every file it uses. A file the
JSON does not use is a warning, not an error.

**JSON** (`scene.json`, `bake.json`, the `.glb` files' JSON): UTF-8, no `NaN` or `Infinity` (JavaScript cannot read
them), and **no control characters** (line breaks, tabs …) in any text or key – so a pattern means the same in
JavaScript and Python.

**Versions.** `scene.json` and `bake.json` start with `"format": "house-scene"` / `"house-bake"` and
`"version": "<major>.<minor>"` (this text: `"1.0"`), two whole numbers compared as numbers (`1.10` is newer than
`1.9`). A reader written for version *M.n*:

- MUST refuse a package of another **major** version with a clear message, e.g. *"This bake was made by a newer
  Fresing Render (format 2.0). Update House Planner to read it."* – never read half of it.
- MUST read a newer **minor** version (*M.n+1* …) and ignore fields it does not know. A minor version only ever
  **adds** optional fields, or new values in the **open lists** of section 13, where readers are told what to do
  with a value they do not know. Everything else (the closed lists, the hash, the UV rules, the encoding) changes
  only with a new major version.
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
- Light values are linear RGB (Rec.709 primaries). The pictures of materials inside `house.glb` follow glTF (base
  colour sRGB). Light-map pages are raw numbers (section 8.3), not colours.

## 4. Surfaces (`house.glb`)

`house.glb` is a binary glTF 2.0 file with **exactly one scene** (the default one); every surface is reached from
it, and every node has at most one parent. Its pictures are inside it (PNG or JPEG). `extensionsRequired` MUST be
empty (no Draco, meshopt or KTX2 in version 1 – both apps must read it as it is); `extensionsUsed` MAY name only
`KHR_lights_punctual`, `KHR_materials_transmission`, `KHR_materials_emissive_strength`, `KHR_texture_transform`. It
holds exactly the parts the recipe includes (section 7.3), nothing else.

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
| `bake` | required | `MAP` (a light map on UV set 1), `VERTEX` (light per vertex), or `NO` (takes part in the light – casts shadows, lets light through by its material – but gets no result). A `MAP` surface's node may be turned and moved but not scaled or mirrored (its metres are the map's metres). |
| `hash` | required with a mesh | The surface hash (section 5). |
| `uv1_px` | required for `MAP` | [W, H]: the size in texels of this surface's light map (section 6). |
| `texels_per_m` | optional, `MAP` | This surface's texel density (4 … 400), when it differs from its group's (section 6). |
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

So that every reader (three.js, Blender, the checker) sees the same vertices in the same order:

- Triangles only (primitive mode 4). `POSITION`, `NORMAL` (and `TEXCOORD_1`) are float32; `TEXCOORD_0` (the texture
  UVs House Planner uses for its materials) and `indices` SHOULD be there. `MAP` surfaces add **`TEXCOORD_1`** (the
  light-map UVs), float32 – not normalised integers.
- Indices are unsigned integers, all below the vertex count, a multiple of 3; **every vertex is used** by a triangle
  (importers drop unused vertices, and light per vertex would no longer line up). No `sparse` accessors.
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
candela, range), kind `lamp`, and `extras.hp` (group `ceilItems`, `installs` or – a standing lamp – `furniture`). It MAY have a mesh (the fitting),
then it is also a surface (usually `VERTEX`); without a mesh its `bake` is `NO` and it has no hash. Each moment says
which lamps are on (section 7.5). Blender's importer makes the light a child object of the fitting (measured).

## 5. The surface hash (`hp-hash/1`)

A surface's hash changes when its geometry, its light-map UVs or its map size change, and only then. It is worked out from the
mesh **as stored in the .glb** (float32 values), in the node's own coordinates (its transform is not part of it):

```
h = SHA-256 of:  "hp-hash/1" + one zero byte
  for each primitive of the mesh, in order:
    "P"  + uint32 vertex count
         + int32 x, y, z of each vertex   = round(coordinate × 1000)          (millimetres)
    "U"  + uint16 u, v of each vertex      = clamp(round(TEXCOORD_1 × 65535), 0, 65535)   when TEXCOORD_1 is there
    "N"                                                                       when it is not
         + uint32 index count + uint32 each index        (0, 1, 2 … when the primitive has no indices)
  then, for a MAP surface only:  "S" + uint32 W + uint32 H        (its uv1_px)
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

1. Texel density, **per surface**, in the node's own metres: the surface's own `texels_per_m` when it has one, else
   the recipe's `quality.texels_per_m_by_group` for its group, else the recipe's `quality.texels_per_m` (section
   7.1). The plot, the street and the neighbours need far less detail than the rooms. W and H follow from it; each is
   at most `page_size − 4`.
2. A surface's triangles fall into **charts** – flat, connected pieces that share their UV points (a wall side with its
   window hole is one chart; each face of a step is one). Each chart is projected onto its own plane without
   stretching: every triangle edge is as long in texels as in metres × the surface's density (the checker allows 2 % +
   0.1 texel), and no texel centre is covered by two triangles (no folds).
3. Charts are packed by their **rectangles**: at least **4 texels** between two charts' rectangles, at least
   **2 texels** from a chart to the edge of the map. All UVs lie in 0 … 1. So nothing overlaps and the baker's
   padding (Cycles' bake margin) can fill the gutters.
4. The same surface gives the same layout every time (the hash includes the UVs).

`hsf/uv1.py` is the reference layout (projection: faces looking mostly up or down use (x, z); other faces use the
horizontal direction in the face and the height, top row first; rectangles packed in rows, tallest first). A better
packer is allowed as long as rules 1–4 hold.

Because the UVs follow from the densities, a bake MUST give each surface a map of exactly its `uv1_px`; a bake at
other densities needs a new export.

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
`texels_per_m` (4 … 400: the default density, decided by House Planner from the preset and the area – it lays out the
UVs for it), `texels_per_m_by_group` (optional: Show-button group → density, e.g. `{"garden": 6, "street": 4,
"houses": 4, "park": 4}`; a surface's own `texels_per_m` wins over both), `samples` (or null = from the preset),
`page_size` (1024 or 2048: the largest atlas page the bake may write).

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
  the unit vector towards the sun in glTF axes (section 3). The baker MUST use these and not work the sun out from
  the time. In Blender's axes the direction is **(d.x, −d.z, d.y)**; for Fresing Render:
  `lightbake.bake(..., sky={"sun_height": elevation, "sun_direction": <that vector's azimuth in its own sky
  convention>})` – the turn from a vector to its sky's `sun_rotation` (0109's `SUN_ROTATION_ZERO_AZ`) is Fresing
  Render's to write (I24c). Example (the sample's summer morning): direction (0.8436, 0.4902, 0.2192) → Blender
  (0.8436, −0.2192, 0.4902): elevation 29.35°, the sun's bearing turned 14.6° from Blender's +X towards −Y. A moment with the sun
  below the horizon (elevation < 0) has **no sun** in the bake (no sun disc, no sun lamp): the night sky as Fresing
  Render renders that clock time (0109: stars, the moon when it shows one) and the moment's lamps – so the bake and
  the photos of the same moment agree. At night `SOFT` and `ALL` give the same light. The checker warns when the sun is
  more than 2° from where it stands at
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
               "sun_light": [2.5, 2.425, 2.3],
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

`scene.id` and `scene.scene_hash` name the export the bake was made from. `light` and `uv1` MUST be the recipe's.
Each `MAP` result's rectangle is that surface's `uv1_px` (densities are per surface, section 6); `quality` only
echoes the recipe's default `texels_per_m` and says how the bake was made.

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

**Pages** are **PNG**, 8-bit RGB (colour type 2), not interlaced, with **no colour chunks** (`gAMA`, `iCCP`,
`sRGB`, `cHRM`, `cICP` …: their bytes are raw numbers, and a browser would convert them), 256, 512, 1024 or 2048 px
on each side and at most the recipe's `page_size`. (No JPEG: its 8 × 8 blocks bleed across the 2-texel gutters.)
Rectangles on a page MUST NOT overlap; the baker SHOULD leave 2 texels between them and fill each rectangle's
gutters (rule 3 of section 6). Readers load pages **without any colour conversion, without flipping** (row 0 is the
top) and **without mipmaps** – in three.js `colorSpace = NoColorSpace`, `flipY = false`, `generateMipmaps = false`,
`minFilter = LinearFilter`. A page MAY carry an optional `ktx2` copy (Basis Universal, same size and content, for
phones – 0009); a reader that does not use KTX2 ignores it.

**Encoding.** The stored value is **absolute light** `L`, per channel:

```
encode:  b = clamp(round(255 × sqrt(max(L, 0) / scale)), 0, 255)      round = half away from zero (section 5)
decode:  L = scale × (b / 255) ^ 2
```

`L` is linear RGB light: **the colour a white matte surface shows** (0107's units: Cycles DIFFUSE without colour,
before exposure and view transform). Multiply by a surface's base colour for its matte look. `curve` is 2.0 (the
square root above); `scale` is one positive number per moment, chosen by the baker – recommended: the 99.9th
percentile of all channel values of the moment's results (brighter values clip at 255). `reference` = the light on an
open, upward-facing surface with nothing round it (0107's probe), RGB – `L / reference` is 0107's *light factor* F
(1 = open sky above, corners < 1). `exposure` = the EV Fresing Render's render of that moment uses (0109's exposure
channel), so night moments can be shown as bright as Fresing Render shows them.

This is the curve of 0107's `core/lightmap.encode`, but on **L**, not on F: 0107's web export stores F with one
scale for the export. Fresing Render must not store F here (it would be off by the reference – about 250× at
night); with 0107's function: `encode(L, scale)`, i.e. its F replaced by L and its scale by this moment's.

House Planner can show a moment two ways: **factor** – `L / reference` times its own sky light (as 0107's web page
does: baked and live surfaces agree even if its sky differs a little from Cycles'); or **absolute** – `L` × 2^exposure
(for night moments, where `reference` is near 0).

`sun_light` (optional, per moment): [R, G, B], the sun's **direct** light on a white matte surface facing the sun,
in the same units as L (Fresing Render: its open probe's reference minus the reference without the sun). With `SOFT`
in absolute mode House Planner adds its live sun at this strength. It is `null` (or left out) with `ALL` and `LIVE`,
at night, and when the light has no separate sun (a 360° photo, a studio). Under a **full overcast** by day with `SOFT`
it is `[0, 0, 0]` (a measured direct sun of nothing), not `null`. In factor mode House Planner can ignore it.

"Facing the sun" means the light on a surface turned **straight at the sun** (normal incidence): House Planner's live
sun is a directional light of exactly that strength, times N·L. A baker may measure it any way it likes, but SHOULD NOT
get it by dividing an upward probe's sun light by sin(elevation) when the sun is low (the noise grows as
1 / sin(elevation): ×12 at 4.8°); a probe facing the sun, or the sky model's own sun value, gives it without that noise.

### 8.4 Light per vertex

`vertex_files` are raw `.bin` files: 3 bytes (R, G, B; the encoding of 8.3, with the moment's `scale`) per vertex.
A result `{"vertex", "offset", "count"}` starts at vertex `offset` of that file; `count` MUST equal the surface's
vertex count (all its primitives, in order) and the values follow the `.glb`'s vertex order. Several surfaces and
moments may use one file, but every result has **its own** values (ranges never overlap).

### 8.5 Furniture and other placed pieces

Furniture is baked `VERTEX` (no UV layout needed for library models) and its node's world `matrix` is recorded.
House Planner's rule (proposed – section 9) decides what happens when a piece moves.

### 8.6 Snow

One `.glb` per season with snow (`snow`). Each node is a **snow layer on one surface**: kind `snow`, `on` = that
surface's id, its `storey` and `group` (so it hides with the surface), `bake` `VERTEX` and a `hash`. The layers are in
the scene's coordinates and their light is in the moments of that season (`maps` keyed by the snow ids). They are
**new geometry built by 0109's rule** – 0109's own snow is a material layer, which three.js cannot run: faces that
look up and lie under the open sky (nothing within 0109's `SKY_DISTANCE`, 25 m, above them), thickness from
`snow_cover` (1 ≈ 10 cm). Large layers (plot, roofs) are cut into pieces of about 0.5 m so their light per vertex has
enough points. Fresing Render's own photos and videos keep 0109's material layer; both follow the same rule, so they
agree. House Planner shows the layers with its own snow material. Falling snow is only in photos and videos.

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
- The 0.5 m and 0.3 m margins are one constant each in House Planner (agreed by its lead, 13 Nov).
- The bake is the owner's own work: stored with the house version (a copied version shares it), one moment loaded at
  a time – not in the re-downloadable model library.

## 10. How Fresing Render reads a scene (for I24c)

- Import `house.glb` with Blender's glTF importer: merge vertices off, **Lighting Mode "Standard"** (its default:
  candela → watts), so both apps test the sample's ceiling lamp the same way. Each object's custom property `hp` is
  its label; `hp["id"]` is the id to write results under (0107's `ids={object: hp["id"]}`). A lamp's light is a
  child object of its fitting; `lamps=` gets the moment's light objects.
- `MAP` objects: `lightbake.bake(objects, light=recipe.light, uv="UV1", sizes={object: hp["uv1_px"]},
  samples=…, sky=<the moment's sun>, lamps=<the moment's lamps>, ...)` – each object's image is exactly its
  `uv1_px` (W × H; `sizes` is the additive argument the Fresing Render lead agreed, 13 Nov; a size that disagrees
  with the layout by more than 2 % becomes a `problems` line). `Item.pixels` (H × W, Blender rows bottom-up) → the
  page rectangle (top-down). `VERTEX` objects: `uv="VERTEX"`; `Item.values` → the vertex file in the glb's
  vertex order. `NO` objects take part in the light only.
- Per moment: the sun from its vector – glTF (x, y, z) → Blender (x, −z, y) → scene azimuth and elevation → 0109's
  sky (`sun_rotation = radians(SUN_ROTATION_ZERO_AZ − azimuth)`), checked against the moment's own azimuth and
  elevation (a `problems` line above 0.5°); clouds and lamps. Per season: build the snow **layer meshes** (8.6) for
  the package; `weather_look.add_objects` (0109's material layer) only for Fresing Render's own photos and videos;
  hide `foliage` when `bare`. For each `open` storey: hide everything of a higher `level` and bake that storey's
  objects again.
- Encode absolute L with the moment's `scale` (8.3; rounding half away from zero – 0107's own encode rounds half to
  even, so the house package writes its own), add `sun_light` for `SOFT`, and write the package.

## 11. Sizes (phones)

- Pages of 1024 px (phones) or 2048 px (PC); House Planner sets `page_size`. One moment SHOULD fit in **4 pages**
  (the checker warns above that): on a phone one moment's pages are held in memory, 4 × 1024² × 4 bytes = 16 MB.
- Densities: about 16 (Draft) … 40 (Fine) texels/m for the house, 4 … 8 for the plot, the street, the neighbours and
  the park (`texels_per_m_by_group`). The sample house (two storeys, 7 × 9 m) at 16 texels/m with its plot
  (15 × 23 m) at 6 fills 30 % of one 1024 px page per moment, 43 % with its open ground floor (37 % / 51 % with the
  plot at 16). Real numbers for the owner's house are measured on his devices (House Planner's I24d).
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

What House Planner may offer and Fresing Render must handle.

**Open lists** – a later minor version may add values; a reader that meets a value it does not know does what the
last column says (the checker accepts it in a newer minor version):

| Where | Values in 1.0 | Unknown value |
| --- | --- | --- |
| surface `kind` | section 4.1 | treat as `other` |
| surface `group`, `recipe.include.groups` | `house`, `garden`, `street`, `houses`, `park`, `furniture`, `installs`, `ceilItems` | show it with the house; no storey rule |
| `recipe.quality.preset` | `DRAFT`, `NORMAL`, `FINE` | use `texels_per_m` and `samples` as given (`NORMAL` when samples is null) |
| `seasons[].foliage` | `full`, `autumn`, `bare` | treat as `full` |
| `moments[].lamps` | `all`, `none`, a list of lamp ids | treat as `none` |
| `videos[].kind` | `turntable` | skip that video |
| `videos[].fps` | 24, 25, 30, 50, 60 | use 25 |

**Closed lists** – a new value is a new **major** version (a reader that does not know it cannot do the right thing):

| Where | Values |
| --- | --- |
| `recipe.light`, `bake.light` | `LIVE`, `SOFT`, `ALL` |
| surface `bake` | `MAP`, `VERTEX`, `NO` |
| a result | a page rectangle, light per vertex |
| `recipe.quality.page_size`, page sizes | 1024, 2048 / 256, 512, 1024, 2048 px a side |
| `hash`, `uv1`, the encoding | `hp-hash/1`, `hp-uv/1`, `curve` 2.0 |
| files | pages PNG (+ optional KTX2 copy), photos JPEG / PNG, videos MP4 / WebM, `.glb` without required extensions |
