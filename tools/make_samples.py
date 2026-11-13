#!/usr/bin/env python3
"""Make the made-up sample packages in samples/ (FORMAT.md section 8).

    python3 tools/make_samples.py            # write samples/sample-house.hpscene and samples/sample-house.hpbake
    python3 tools/make_samples.py --check    # make them in memory and say whether samples/ is up to date

Everything here is invented: a plain two-storey box house at a made-up place in the North Sea. The light maps are
*made up too* (flat shades per face from a simple sky-and-sun guess) – they only have to be valid, not right.
Run it again after every change to the format; the same code gives the same bytes.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsf import surface as S  # noqa: E402
from hsf.glb import Glb, GlbWriter  # noqa: E402
from hsf.images import png_read_rgb, png_rgb  # noqa: E402
from hsf.package import Package, write as write_package  # noqa: E402
from hsf.sun import sun_position, utc_moment  # noqa: E402
from hsf.uv1 import GAP, layout, project  # noqa: E402

OUT = ROOT / "samples"
SCENE_FILE = "sample-house.hpscene"
BAKE_FILE = "sample-house.hpbake"
CREATED = "2026-11-13T12:00:00Z"
GENERATOR = {"app": "house-scene-format sample maker", "version": "1.0"}
TPM = 16.0          # texels per metre of the sample (a Draft bake): the recipe's default
TPM_BY_GROUP = {"garden": 6.0}  # the plot needs less detail than the house (recipe.quality.texels_per_m_by_group)
PAGE = 1024
PLACE = {"latitude": 53.5, "longitude": 3.5, "north_deg": 15.0, "ground_level": -0.15}  # a made-up spot at sea

MATERIALS = {  # House Planner material id -> (base colour, roughness, alpha)
    "brick": ((0.45, 0.2, 0.14), 0.9, 1.0), "plaster": ((0.85, 0.84, 0.8), 0.9, 1.0),
    "oak": ((0.55, 0.38, 0.22), 0.6, 1.0), "tiles": ((0.6, 0.62, 0.64), 0.4, 1.0),
    "concrete": ((0.55, 0.55, 0.53), 0.95, 1.0), "roof": ((0.15, 0.15, 0.16), 0.8, 1.0),
    "grass": ((0.2, 0.42, 0.15), 1.0, 1.0), "paving": ((0.58, 0.55, 0.5), 0.85, 1.0),
    "frame": ((0.92, 0.92, 0.9), 0.5, 1.0), "glass": ((0.8, 0.9, 0.95), 0.05, 0.25),
    "wood": ((0.42, 0.28, 0.17), 0.55, 1.0), "lamp": ((0.95, 0.95, 0.92), 0.4, 1.0),
    "snow": ((0.92, 0.94, 0.97), 0.8, 1.0),
}


# ------------------------------------------------------------------ geometry helpers (glTF axes: x, y up, z)
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def quad(pts, normal):
    """A flat face of four corners, wound so that it faces ``normal``."""
    if dot(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])), normal) < 0:
        pts = pts[::-1]
    return (list(pts), normal)


def box(x0, x1, y0, y1, z0, z1, faces="+x -x +y -y +z -z"):
    """Faces of a box as separate quads (each its own chart)."""
    out = []
    want = faces.split()
    if "+x" in want:
        out.append(quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)))
    if "-x" in want:
        out.append(quad([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0)))
    if "+y" in want:
        out.append(quad([(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)], (0, 1, 0)))
    if "-y" in want:
        out.append(quad([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)))
    if "+z" in want:
        out.append(quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)))
    if "-z" in want:
        out.append(quad([(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)], (0, 0, -1)))
    return out


def rect_y(x0, x1, z0, z1, y, up=True):
    """A horizontal rectangle at height y (plan x 0..1, plan y = z)."""
    return quad([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], (0, 1 if up else -1, 0))


def ring_y(outer, inner, y, up=True):
    """A horizontal rectangle with a rectangular hole, as four quads (one chart)."""
    (X0, X1, Z0, Z1), (x0, x1, z0, z1) = outer, inner
    return [rect_y(X0, X1, Z0, z0, y, up), rect_y(X0, X1, z1, Z1, y, up),
            rect_y(X0, x0, z0, z1, y, up), rect_y(x1, X1, z0, z1, y, up)]


class Part:
    """One surface: charts (lists of quads), its House Planner labels, and how it is baked."""

    def __init__(self, sid, kind, storey, group, bake, material, charts, source=None, matrix=None, light=None,
                 on=None, tpm=None):
        self.tpm = tpm  # its own texels per metre (extras.hp.texels_per_m), else the recipe's for its group
        self.id, self.kind, self.storey, self.group, self.bake = sid, kind, storey, group, bake
        self.material, self.charts, self.source, self.matrix, self.light, self.on = (
            material, charts, source, matrix, light, on)


def wall(wid, storey, a, b, t, y0, y1, material_a, material_b, holes=()):
    """A wall from plan point a to b (centre line), thickness t, from height y0 to y1. Three surfaces: side a (left of
    a→b on the plan), side b, edge (top, ends, reveals). holes: (from, width, sill, height) along the wall."""
    (ax, az), (bx, bz) = a, b
    L = math.hypot(bx - ax, bz - az)
    dx, dz = (bx - ax) / L, (bz - az) / L
    nx, nz = dz, -dx  # left of a→b on the plan (plan y = glTF z, drawn downwards)

    def at(s, off, y):
        return (ax + dx * s + nx * off, y, az + dz * s + nz * off)

    def side(off, n):
        spans = []
        cuts = [0.0]
        for f, w, sill, h in holes:
            cuts += [f, f + w]
        cuts.append(L)
        for i in range(0, len(cuts), 2):
            if cuts[i + 1] > cuts[i]:
                spans.append((cuts[i], cuts[i + 1], y0, y1))
        for f, w, sill, h in holes:
            if sill > y0:
                spans.append((f, f + w, y0, sill))
            if sill + h < y1:
                spans.append((f, f + w, sill + h, y1))
        return [quad([at(s0, off, ya), at(s1, off, ya), at(s1, off, yb), at(s0, off, yb)], n)
                for s0, s1, ya, yb in spans]

    na, nb = (nx, 0, nz), (-nx, 0, -nz)
    top = quad([at(0, t / 2, y1), at(L, t / 2, y1), at(L, -t / 2, y1), at(0, -t / 2, y1)], (0, 1, 0))
    end0 = quad([at(0, t / 2, y0), at(0, -t / 2, y0), at(0, -t / 2, y1), at(0, t / 2, y1)], (-dx, 0, -dz))
    end1 = quad([at(L, t / 2, y0), at(L, -t / 2, y0), at(L, -t / 2, y1), at(L, t / 2, y1)], (dx, 0, dz))
    edge = [[top], [end0], [end1]]
    for f, w, sill, h in holes:
        edge += [[quad([at(f, t / 2, sill), at(f + w, t / 2, sill), at(f + w, -t / 2, sill), at(f, -t / 2, sill)],
                       (0, 1, 0))],
                 [quad([at(f, t / 2, sill + h), at(f + w, t / 2, sill + h), at(f + w, -t / 2, sill + h),
                        at(f, -t / 2, sill + h)], (0, -1, 0))],
                 [quad([at(f, t / 2, sill), at(f, -t / 2, sill), at(f, -t / 2, sill + h), at(f, t / 2, sill + h)],
                       (dx, 0, dz))],
                 [quad([at(f + w, t / 2, sill), at(f + w, -t / 2, sill), at(f + w, -t / 2, sill + h),
                        at(f + w, t / 2, sill + h)], (-dx, 0, -dz))]]
    return [Part(f"wall:{wid}:a", "wall", storey, "house", "MAP", material_a, [side(t / 2, na)], wid),
            Part(f"wall:{wid}:b", "wall", storey, "house", "MAP", material_b, [side(-t / 2, nb)], wid),
            Part(f"wall:{wid}:edge", "wall", storey, "house", "MAP", material_a, edge, wid)]


def rot_y(deg, t):
    """Column-major matrix: turn about +y by deg, then move by t."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, t[0], t[1], t[2], 1]


# ------------------------------------------------------------------ the made-up house
GF, FF = "st_ground", "st_first"
STOREYS = [{"id": GF, "name": "Ground floor", "level": 0, "elevation": 0.0, "height": 2.8},
           {"id": FF, "name": "First floor", "level": 1, "elevation": 2.8, "height": 2.8}]
G = PLACE["ground_level"]
VOID = (0.5, 1.5, 6.0, 8.5)  # the stair void in the first floor's slab (plan x0, x1, y0, y1)


def house_parts() -> list[Part]:
    parts: list[Part] = []
    win = [(2.0, 1.5, 0.9, 1.2)]
    for st, y0, y1, yin0, yin1, tag in ((GF, G, 2.8, 0.0, 2.6, "g"), (FF, 2.8, 5.6, 2.8, 5.4, "f")):
        parts += wall(f"w_{tag}_front", st, (0, 0.15), (7, 0.15), 0.3, y0, y1, "brick", "plaster",
                      win if st == GF else ())
        parts += wall(f"w_{tag}_back", st, (7, 8.85), (0, 8.85), 0.3, y0, y1, "brick", "plaster")
        parts += wall(f"w_{tag}_left", st, (0.15, 8.7), (0.15, 0.3), 0.3, y0, y1, "brick", "plaster")
        parts += wall(f"w_{tag}_right", st, (6.85, 0.3), (6.85, 8.7), 0.3, y0, y1, "brick", "plaster")
        parts += wall(f"w_{tag}_mid", st, (0.3, 5.55), (6.7, 5.55), 0.1, yin0, yin1, "plaster", "plaster")
    parts += wall("w_f_cross", FF, (3.5, 0.3), (3.5, 5.5), 0.1, 2.8, 5.4, "plaster", "plaster")
    # floors and ceilings, per room
    rooms = [("r_living", GF, (0.3, 6.7, 0.3, 5.5), "oak"), ("r_kitchen", GF, (0.3, 6.7, 5.6, 8.7), "tiles"),
             ("r_bed", FF, (0.3, 3.45, 0.3, 5.5), "oak"), ("r_bath", FF, (3.55, 6.7, 0.3, 5.5), "tiles"),
             ("r_landing", FF, (0.3, 6.7, 5.6, 8.7), "oak")]
    for rid, st, (x0, x1, z0, z1), mat in rooms:
        el = 0.0 if st == GF else 2.8
        floor = ring_y((x0, x1, z0, z1), VOID, el) if rid == "r_landing" else [rect_y(x0, x1, z0, z1, el)]
        ceil = (ring_y((x0, x1, z0, z1), VOID, el + 2.6, up=False) if rid == "r_kitchen"
                else [rect_y(x0, x1, z0, z1, el + 2.6, up=False)])
        parts.append(Part(f"floor:{rid}", "floor", st, "house", "MAP", mat, [floor], rid))
        parts.append(Part(f"ceiling:{rid}", "ceiling", st, "house", "MAP", "plaster", [ceil], rid))
    # the void's edges in the first floor's slab (between the kitchen's ceiling and the landing's floor)
    vx0, vx1, vz0, vz1 = VOID
    void = box(vx0, vx1, 2.6, 2.8, vz0, vz1, "+x -x +z -z")
    void = [quad(q[0], tuple(-c for c in q[1])) for q in void]  # faces looking into the void
    parts.append(Part("slab-edge:fv_stair", "slab-edge", FF, "house", "MAP", "concrete", [[q] for q in void],
                      "fv_stair"))
    # the stair, in the kitchen under the void: 13 steps going up towards -z
    run = 2.5 / 14
    steps = []
    for k in range(13):
        z1 = vz1 - k * run
        steps += [[q] for q in box(vx0, vx1, 0.0, 0.2 * (k + 1), z1 - run, z1, "+y +z +x -x")]
    parts.append(Part("stair:s_main", "stair", GF, "house", "MAP", "wood", steps, "s_main"))
    # flat roof on the first floor
    parts.append(Part("roof:st_first:0", "roof", FF, "house", "MAP", "roof",
                      [[q] for q in box(0, 7, 5.6, 5.8, 0, 9, "+y +x -x +z -z")], "roof"))
    # the window in the ground floor's front wall: frame (light per vertex) and glass (no light of its own)
    f, w, sill, h, fr = 2.0, 1.5, 0.9, 1.2, 0.06
    frame = (box(f, f + w, sill, sill + fr, 0.11, 0.19) + box(f, f + w, sill + h - fr, sill + h, 0.11, 0.19)
             + box(f, f + fr, sill + fr, sill + h - fr, 0.11, 0.19) + box(f + w - fr, f + w, sill + fr, sill + h - fr,
                                                                          0.11, 0.19))
    parts.append(Part("opening:o_g_win1", "opening", GF, "house", "VERTEX", "frame", [frame], "o_g_win1"))
    glass = quad([(f + fr, sill + fr, 0.15), (f + w - fr, sill + fr, 0.15), (f + w - fr, sill + h - fr, 0.15),
                  (f + fr, sill + h - fr, 0.15)], (0, 0, -1))
    parts.append(Part("glass:o_g_win1", "glass", GF, "house", "NO", "glass", [[glass]], "o_g_win1"))
    # one furniture piece, placed by its node's matrix (light per vertex)
    table = box(-0.8, 0.8, 0.72, 0.76, -0.45, 0.45)
    for lx in (-0.72, 0.72):
        for lz in (-0.37, 0.37):
            table += box(lx - 0.025, lx + 0.025, 0.0, 0.72, lz - 0.025, lz + 0.025, "+x -x +z -z")
    parts.append(Part("furniture:f_table:0", "furniture", GF, "furniture", "VERTEX", "wood", [table], "f_table",
                      matrix=rot_y(30, (3.5, 0.0, 3.0))))
    # a ceiling lamp in the living room: a small body with a point light
    lamp = box(-0.15, 0.15, -0.08, 0.0, -0.15, 0.15, "+x -x -y +z -z")
    parts.append(Part("lamp:p_living_1", "lamp", GF, "ceilItems", "VERTEX", "lamp", [lamp], "p_living_1",
                      matrix=rot_y(0, (3.5, 2.6, 2.8)), light={"type": "point", "intensity": 80.0,
                                                               "color": [1.0, 0.85, 0.7], "range": 12.0}))
    # the plot round the house, and a terrace
    parts.append(Part("ground:plot", "ground", None, "garden", "MAP", "grass",
                      [ring_y((-4, 11, -6, 17), (0, 7, 0, 12), G)], "plot"))
    parts.append(Part("garden:ga_terrace", "garden", None, "garden", "MAP", "paving",
                      [[q] for q in box(0, 7, G, G + 0.02, 9, 12, "+y +x -x +z")], "ga_terrace", tpm=10.0))
    return parts


def snow_parts() -> list[Part]:
    """Winter's snow: a layer on the flat roof and on the plot (light per vertex)."""
    roof = box(0.05, 6.95, 5.8, 5.9, 0.05, 8.95, "+y +x -x +z -z")
    ground = ring_y((-4, 11, -6, 17), (0, 7, 0, 12), G + 0.06)
    return [Part("snow:roof:st_first:0", "snow", FF, "house", "VERTEX", "snow", [roof], on="roof:st_first:0"),
            Part("snow:ground:plot", "snow", None, "garden", "VERTEX", "snow", [ground], on="ground:plot")]


# ------------------------------------------------------------------ .glb
def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def build_glb(parts: list[Part]) -> tuple[bytes, dict]:
    """The .glb with every part a node of its own; returns (bytes, {id: (mesh vertex normals, charts' uv rects)})."""
    extra = {}
    for attempt in (0, 1):
        w = GlbWriter("house-scene-format sample maker")
        doc = w.doc
        mats = sorted({p.material for p in parts})
        doc["materials"] = []
        for m in mats:
            col, rough, alpha = MATERIALS[m]
            mat = {"name": m, "pbrMetallicRoughness": {"baseColorFactor": [*col, alpha], "metallicFactor": 0.0,
                                                       "roughnessFactor": rough}}
            if alpha < 1:
                mat["alphaMode"] = "BLEND"
                mat["doubleSided"] = True
            doc["materials"].append(mat)
        doc["meshes"], doc["nodes"] = [], []
        lights = []
        for p in parts:
            pos, nor, idx, uv0, uv1 = [], [], [], [], []
            charts_flat = []
            for chart in p.charts:
                pts = [c for q in chart for c in q[0]]
                charts_flat.append((pts, chart[0][1]))
            dens = p.tpm or TPM_BY_GROUP.get(p.group, TPM)
            uvs, px = layout(charts_flat, dens) if p.bake == "MAP" else (None, None)
            chart_rects = []
            for ci, chart in enumerate(p.charts):
                k = 0
                for corners, n in chart:
                    base = len(pos)
                    pos += [tuple(f32(c) for c in pt) for pt in corners]
                    nor += [n] * 4
                    uv0 += [tuple(f32(c) for c in t) for t in project(corners, n)]  # texture UVs: metres
                    idx += [base, base + 1, base + 2, base, base + 2, base + 3]
                    if uvs:
                        uv1 += [tuple(f32(c) for c in t) for t in uvs[ci][k:k + 4]]
                    k += 4
                if uvs:
                    us = [t[0] for t in uvs[ci]]
                    vs = [t[1] for t in uvs[ci]]
                    chart_rects.append(((min(us) * px[0], min(vs) * px[1], max(us) * px[0], max(vs) * px[1]),
                                        chart[0][1]))
            attrs = {"POSITION": w.accessor(pos, "VEC3", minmax=True), "NORMAL": w.accessor(nor, "VEC3")}
            attrs["TEXCOORD_0"] = w.accessor(uv0, "VEC2")
            if uv1:
                attrs["TEXCOORD_1"] = w.accessor(uv1, "VEC2")
            prim = {"attributes": attrs, "indices": w.accessor(idx, "SCALAR", 5125, target=34963),
                    "material": mats.index(p.material)}
            doc["meshes"].append({"name": p.id, "primitives": [prim]})
            hp = {"id": p.id, "kind": p.kind, "storey": p.storey, "group": p.group, "bake": p.bake,
                  "hash": "0" * 32}
            if px:
                hp["uv1_px"] = list(px)
            if p.tpm:
                hp["texels_per_m"] = p.tpm
            if p.source:
                hp["source"] = p.source
            hp["material"] = p.material
            if p.on:
                hp["on"] = p.on
            if attempt:
                hp["hash"] = extra[p.id]["hash"]
            node = {"name": p.id, "mesh": len(doc["meshes"]) - 1, "extras": {"hp": hp}}
            if p.matrix:
                node["matrix"] = p.matrix
            if p.light:
                lights.append(dict(p.light, name=p.id))
                node["extensions"] = {"KHR_lights_punctual": {"light": len(lights) - 1}}
            doc["nodes"].append(node)
            if not attempt:
                extra[p.id] = {"normals": nor, "rects": chart_rects, "px": px, "verts": len(pos)}
        if lights:
            doc["extensionsUsed"] = ["KHR_lights_punctual"]
            doc["extensions"] = {"KHR_lights_punctual": {"lights": lights}}
        doc["scenes"] = [{"name": "house", "nodes": list(range(len(doc["nodes"])))}]
        doc["scene"] = 0
        data = w.to_bytes()
        if not attempt:
            g = Glb.parse(data)
            for i, p in enumerate(parts):
                extra[p.id]["hash"] = S.surface_hash(g, i, extra[p.id]["px"] if p.bake == "MAP" else None)
    return data, extra


# ------------------------------------------------------------------ the recipe
NORTH = [round(math.sin(math.radians(PLACE["north_deg"])), 6), round(-math.cos(math.radians(PLACE["north_deg"])), 6)]
SEASONS = [{"id": "summer", "label": "Summer", "date": "2026-06-21", "snow_cover": 0.0, "wet": 0.0, "foliage": "full"},
           {"id": "winter", "label": "Winter", "date": "2026-01-15", "snow_cover": 0.6, "wet": 0.2,
            "foliage": "bare"}]
MOMENTS = [("summer-morning", "Morning", "summer", "09:00", "+02:00", 0.1, "none"),
           ("summer-evening", "Evening", "summer", "21:30", "+02:00", 0.2, "none"),
           ("winter-noon", "Afternoon", "winter", "13:00", "+01:00", 0.8, "none"),
           ("winter-night", "Night", "winter", "22:00", "+01:00", 0.3, "all")]


def moments() -> list[dict]:
    out = []
    dates = {s["id"]: s["date"] for s in SEASONS}
    for mid, label, season, time, off, clouds, lamps in MOMENTS:
        az, el = sun_position(PLACE["latitude"], PLACE["longitude"], utc_moment(dates[season], time, off))
        d = S.sun_direction(az, el, NORTH)
        out.append({"id": mid, "label": label, "season": season, "time": time, "utc_offset": off,
                    "sun": {"azimuth": round(az, 3), "elevation": round(el, 3),
                            "direction": [round(c, 6) for c in d]},
                    "sky": {"clouds": clouds, "low_clouds": 0.0 if clouds < 0.5 else 0.3, "visibility": 40000.0},
                    "lamps": lamps})
    return out


CAMERA = {"id": "garden-view", "label": "From the garden", "position": [3.5, 1.7, 22.0], "target": [3.5, 2.5, 4.5],
          "fov": 50.0}


def scene_doc(extra: dict, parts: list[Part]) -> dict:
    return {
        "format": "house-scene", "version": "1.0", "generator": GENERATOR, "id": "sample-house-a",
        "created": CREATED, "title": "Made-up sample house", "house": {"version_id": "v_sample",
                                                                        "version_name": "Made-up plan"},
        "files": {"house": "house.glb", "preview": "pictures/preview.png"},
        "hash": S.HASH_NAME, "uv1": S.UV1_NAME,
        "scene_hash": S.scene_hash({p.id: extra[p.id]["hash"] for p in parts}),
        "place": {"latitude": PLACE["latitude"], "longitude": PLACE["longitude"], "north": NORTH,
                  "ground_level": G},
        "storeys": STOREYS,
        "recipe": {
            "light": "SOFT",
            "quality": {"preset": "DRAFT", "texels_per_m": TPM, "texels_per_m_by_group": TPM_BY_GROUP, "samples": 16,
                        "page_size": PAGE},
            "include": {"storeys": [GF, FF], "groups": ["house", "garden", "furniture", "ceilItems"]},
            "open_storeys": [GF],
            "seasons": SEASONS,
            "moments": moments(),
            "cameras": [CAMERA],
            "photos": [{"id": "photo-1", "label": "Garden side, summer morning", "camera": "garden-view",
                        "moment": "summer-morning", "size": [320, 240],
                        "falling": {"rain": 0.0, "snow": 0.0, "wind": 2.0, "wind_from": 225.0}}],
            "videos": [],
        },
    }


# ------------------------------------------------------------------ made-up light
SKY = {"summer-morning": 1.0, "summer-evening": 0.45, "winter-noon": 0.55, "winter-night": 0.004}
INSIDE = ("wall", "floor", "ceiling", "slab-edge", "stair", "furniture", "lamp", "opening")


def made_up_light(mid: str, sun: dict, part: Part, normal, side_inside: bool, open_storey: bool):
    """A plausible light (linear RGB a white matte surface shows) – invented, flat per face."""
    sky = SKY[mid]
    up = 0.55 + 0.45 * normal[1]
    s = sun["direction"]
    bounce = 0.15 * max(0.0, dot(normal, s)) * (sun["elevation"] > 0)
    if side_inside:
        k = 0.7 if open_storey else 0.3
        val = sky * k * (0.6 + 0.4 * up)
    else:
        val = sky * up + bounce
    if mid == "winter-night" and side_inside:
        val += 0.08  # the lamps
    warm = (1.0, 0.97, 0.92) if mid != "winter-night" else (1.0, 0.86, 0.7)
    return tuple(val * c for c in warm)


def is_inside(part: Part, normal) -> bool:
    if part.kind in ("ground", "garden", "roof", "snow"):
        return False
    if part.kind == "wall" and part.id.endswith(":a") and part.material == "brick":
        return False
    return part.kind in INSIDE


def encode(L, scale):
    return bytes(min(255, max(0, S.round_half_away(255 * math.sqrt(max(0.0, c) / scale)))) for c in L)


def bake_package(scene: dict, parts: list[Part], extra: dict, snow: list[Part], snow_extra: dict):
    files: dict[str, bytes] = {}
    moms = scene["recipe"]["moments"]
    pages, vfiles, out_moments = [], [], []
    surfaces = {}
    for p in parts:
        if p.bake == "NO":
            continue
        e = extra[p.id]
        world = p.matrix or [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
        pts = [c for ch in p.charts for q in ch for c in q[0]]
        ws = [tuple(world[k] * x + world[4 + k] * y + world[8 + k] * z + world[12 + k] for k in range(3))
              for x, y, z in ((f32(a), f32(b), f32(c)) for a, b, c in pts)]
        box_ = [round(min(w[k] for w in ws), 4) for k in range(3)] + [round(max(w[k] for w in ws), 4)
                                                                         for k in range(3)]
        surfaces[p.id] = {"hash": e["hash"], "box": box_}
        if p.matrix:
            surfaces[p.id]["matrix"] = p.matrix
    for mi, m in enumerate(moms):
        mid = m["id"]
        winter = m["season"] == "winter"
        # values first (to find the moment's scale)
        maps_vals = []   # (variant, part, [(rect, L)])
        for variant in ("", GF):
            for p in parts:
                if p.bake != "MAP" or (variant and p.storey != variant):
                    continue
                rects = [(r, made_up_light(mid, m["sun"], p, n, is_inside(p, n), bool(variant)))
                         for r, n in extra[p.id]["rects"]]
                maps_vals.append((variant, p, rects))
        vert_vals = []
        for p in parts + (snow if winter else []):
            if p.bake != "VERTEX":
                continue
            e = extra.get(p.id) or snow_extra[p.id]
            vert_vals.append((p, [made_up_light(mid, m["sun"], p, n, is_inside(p, n), False) for n in e["normals"]]))
        allv = [c for _, _, rs in maps_vals for _, L in rs for c in L] + [c for _, vs in vert_vals for L in vs
                                                                          for c in L]
        ref = SKY[mid]
        scale = max(max(allv), ref)
        # the page: shelf-pack the surfaces' maps
        pid = f"p{mi}"
        img = [bytearray(PAGE * 3) for _ in range(PAGE)]
        x = y = 0
        row = 0
        entries = {"": {}, GF: {}}
        order = sorted(maps_vals, key=lambda t: (-extra[t[1].id]["px"][1], t[1].id, t[0]))
        for variant, p, rects in order:
            W, H = extra[p.id]["px"]
            if x + W > PAGE:
                x, y, row = 0, y + row + 2, 0
            if y + H > PAGE:
                raise SystemExit("the sample's light maps do not fit one page – raise PAGE or lower TPM")
            for (x0, y0, x1, y1), L in rects:
                px = encode(L, scale)
                for yy in range(max(0, int(y0) - GAP // 2), min(H, math.ceil(y1) + GAP // 2)):
                    line = img[y + yy]
                    a = x + max(0, int(x0) - GAP // 2)
                    b = x + min(W, math.ceil(x1) + GAP // 2)
                    line[a * 3:b * 3] = px * (b - a)
            entries[variant][p.id] = {"page": pid, "rect": [x, y, W, H]}
            x += W + 2
            row = max(row, H)
        files[f"light/{pid}.png"] = png_rgb(PAGE, PAGE, [bytes(r) for r in img])
        pages.append({"id": pid, "file": f"light/{pid}.png", "size": [PAGE, PAGE]})
        vid = f"v{mi}"
        blob = bytearray()
        for p, vs in vert_vals:
            entries[""][p.id] = {"vertex": vid, "offset": len(blob) // 3, "count": len(vs)}
            for L in vs:
                blob += encode(L, scale)
        files[f"light/{vid}.bin"] = bytes(blob)
        vfiles.append({"id": vid, "file": f"light/{vid}.bin"})
        out_moments.append({"id": mid, "encoding": {"curve": 2.0, "scale": round(scale, 6),
                                                    "reference": [round(ref * c, 6) for c in
                                                                  ((1.0, 0.97, 0.92) if mid != "winter-night"
                                                                   else (1.0, 0.86, 0.7))],
                                                    "exposure": 0.0},
                            "sun_light": None if m["sun"]["elevation"] < 0 else
                            [round(2.5 * SKY[mid] * c, 6) for c in (1.0, 0.97, 0.92)],
                            "maps": dict(sorted(entries[""].items())), "open": {GF: dict(sorted(entries[GF].items()))}})
    snow_glb, _ = build_glb(snow)
    files["snow/winter.glb"] = snow_glb
    files["photos/photo-1.png"] = photo()
    doc = {
        "format": "house-bake", "version": "1.0", "generator": GENERATOR, "id": "sample-bake-a",
        "created": CREATED, "scene": {"id": scene["id"], "scene_hash": scene["scene_hash"]},
        "light": scene["recipe"]["light"], "uv1": S.UV1_NAME,
        "quality": {"texels_per_m": TPM, "samples": 16, "denoised": True},
        "surfaces": dict(sorted(surfaces.items())),
        "pages": pages, "vertex_files": vfiles, "moments": out_moments,
        "snow": [{"season": "winter", "file": "snow/winter.glb"}],
        "photos": [{"id": "photo-1", "file": "photos/photo-1.png", "size": [320, 240], "moment": "summer-morning",
                    "camera": {k: CAMERA[k] for k in ("position", "target", "fov")}}],
        "videos": [],
        "problems": ["Sample only: the light maps are made up, not baked."],
    }
    files["bake.json"] = dumps(doc)
    return files


# ------------------------------------------------------------------ pictures
def preview() -> bytes:
    """A top view, 140 x 115 px: grass, the house's roof, the terrace (1 px = 0.2 m)."""
    W, H = 75, 115
    rows = []
    for j in range(H):
        z = -6 + (j + 0.5) * 0.2
        row = bytearray()
        for i in range(W):
            x = -4 + (i + 0.5) * 0.2
            if 0 <= x <= 7 and 0 <= z <= 9:
                c = (40, 40, 44)
            elif 0 <= x <= 7 and 9 < z <= 12:
                c = (150, 140, 128)
            else:
                c = (52, 107, 38)
            row += bytes(c)
        rows.append(bytes(row))
    return png_rgb(W, H, rows)


def photo() -> bytes:
    """A made-up 'photo': sky, the house as a block, the lawn."""
    W, H = 320, 240
    rows = []
    for j in range(H):
        row = bytearray()
        for i in range(W):
            if 70 <= i <= 250 and 60 <= j <= 170:
                c = (150, 70, 50) if j > 75 else (40, 40, 44)
                if 120 <= i <= 160 and 110 <= j <= 140:
                    c = (120, 160, 190)
            elif j > 165:
                c = (60, 120 - (j - 165) // 3, 45)
            else:
                c = (120 + j // 3, 170 + j // 4, 230)
            row += bytes(c)
        rows.append(bytes(row))
    return png_rgb(W, H, rows)


def dumps(doc: dict) -> bytes:
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def make() -> dict[str, dict[str, bytes]]:
    parts = house_parts()
    glb, extra = build_glb(parts)
    snow = snow_parts()
    _, snow_extra = build_glb(snow)
    scene = scene_doc(extra, parts)
    scene_files = {"scene.json": dumps(scene), "house.glb": glb, "pictures/preview.png": preview()}
    bake_files = bake_package(scene, parts, extra, snow, snow_extra)
    return {SCENE_FILE: scene_files, BAKE_FILE: bake_files}


def same_files(old: dict[str, bytes], new: dict[str, bytes]) -> bool:
    """The same files with the same contents; pictures compared by their pixels (zlib's bytes may differ between
    machines)."""
    if set(old) != set(new):
        return False
    for k, v in new.items():
        if k.endswith(".png"):
            if png_read_rgb(old[k]) != png_read_rgb(v):
                return False
        elif old[k] != v:
            return False
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="only say whether samples/ is up to date")
    a = ap.parse_args(argv)
    made = make()
    if a.check:
        stale = []
        for name, files in made.items():
            path = OUT / name
            if not path.exists() or not same_files(Package.open(path).files, files):
                stale.append(name)
        if stale:
            print("samples/ is out of date: " + ", ".join(stale) + " – run python3 tools/make_samples.py")
            return 1
        print("samples/ is up to date")
        return 0
    OUT.mkdir(exist_ok=True)
    for name, files in made.items():
        write_package(OUT / name, files)
        print(f"wrote samples/{name} ({(OUT / name).stat().st_size / 1024:.0f} KB, {len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
