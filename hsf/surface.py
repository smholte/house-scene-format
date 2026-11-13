"""Surfaces: ids, kinds, Show-button groups, the surface hash and the sun's direction (FORMAT.md sections 4–6).

Everything here is written so House Planner (JavaScript) can do exactly the same: the rounding rules are spelled out.
"""
from __future__ import annotations

import hashlib
import math
import re
import struct

from .glb import Glb, GlbError

HASH_NAME = "hp-hash/1"
UV1_NAME = "hp-uv/1"

# What a surface is (extras.hp.kind). FORMAT.md section 4.
KINDS = (
    "wall",        # one side of a wall ("a" / "b"), or its "edge": top, ends, reveals round openings
    "floor",       # the top of a room's floor
    "ceiling",     # the underside of the storey above, per room
    "slab-edge",   # the edges of a floor slab: round the house, round a stair void
    "roof",        # one roof face (top and its underside) or a flat roof
    "opening",     # door and window frames, door leaves
    "glass",       # glass: lets light through, never gets a result (bake "NO")
    "stair",       # a stair (steps, stringers, handrail)
    "furniture",   # one mesh of a furniture piece (extras.hp.piece = the piece's id)
    "install",     # electrics and things on walls and ceilings (not lamps themselves)
    "lamp",        # a light fitting's body; the light itself is a KHR_lights_punctual light on the same node
    "ground",      # the plot's ground outside garden areas
    "garden",      # a garden area, path, wall, hedge or pond edge
    "plant",       # a plant, shrub or tree trunk
    "foliage",     # a tree's or hedge's leaves (the baker hides it when a season's foliage is "bare")
    "street",      # road, pavement, kerb, street furniture
    "neighbour",   # a house around the plot
    "water",       # water surfaces: let light through or reflect, never get a result (bake "NO")
    "park",        # quays, reeds, the park
    "snow",        # a snow layer (only in a bake package's snow files)
    "other",
)

# House Planner's Show buttons, by its own settings keys; "house" = the building itself (shown per storey).
GROUPS = ("house", "garden", "street", "houses", "park", "furniture", "installs", "ceilItems")

BAKE = ("MAP", "VERTEX", "NO")

ID_RE = re.compile(r"^[a-z][a-z0-9-]*:[A-Za-z0-9_.:-]+$")
ID_MAX = 63  # Blender's longest object name, in bytes


def id_problem(sid) -> str | None:
    if not isinstance(sid, str):
        return "is not text"
    if len(sid.encode("utf-8")) > ID_MAX:
        return f"is longer than {ID_MAX} bytes"
    if not ID_RE.match(sid):
        return "is not '<kind>:<name>' (letters, digits, _ . : - only)"
    return None


def round_half_away(x: float) -> int:
    """Round to the nearest integer, halves away from zero (JavaScript: Math.sign(x) * Math.floor(Math.abs(x) + 0.5))."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def surface_hash(glb: Glb, mesh_index: int) -> str:
    """The surface hash ``hp-hash/1`` of a mesh (FORMAT.md section 5): SHA-256 of its primitives' positions (mm),
    light-map UVs (TEXCOORD_1, 1/65535) and indices, in the file's order; the first 32 hex digits."""
    try:
        mesh = glb.json["meshes"][mesh_index]
    except (KeyError, IndexError, TypeError):
        raise GlbError(f"mesh {mesh_index} does not exist") from None
    h = hashlib.sha256(HASH_NAME.encode() + b"\0")
    for prim in mesh.get("primitives", []):
        attrs = prim.get("attributes", {})
        if "POSITION" not in attrs:
            raise GlbError(f"mesh {mesh_index}: a primitive without POSITION")
        pos = glb.accessor(attrs["POSITION"])
        flat = [round_half_away(c * 1000.0) for p in pos for c in p]
        h.update(b"P" + struct.pack("<I", len(pos)) + struct.pack(f"<{len(flat)}i", *flat))
        if "TEXCOORD_1" in attrs:
            uv = glb.accessor(attrs["TEXCOORD_1"])
            if len(uv) != len(pos):
                raise GlbError(f"mesh {mesh_index}: TEXCOORD_1 has {len(uv)} values for {len(pos)} vertices")
            q = [min(65535, max(0, round_half_away(c * 65535.0))) for t in uv for c in t]
            h.update(b"U" + struct.pack(f"<{len(q)}H", *q))
        else:
            h.update(b"N")
        idx = glb.accessor(prim["indices"]) if "indices" in prim else list(range(len(pos)))
        h.update(struct.pack("<I", len(idx)) + struct.pack(f"<{len(idx)}I", *[int(i) for i in idx]))
    return h.hexdigest()[:32]


def scene_hash(pairs: dict[str, str]) -> str:
    """One hash for the whole export: SHA-256 of the lines "<id> <hash>\\n" sorted by id (UTF-8), first 32 hex."""
    text = "".join(f"{k} {pairs[k]}\n" for k in sorted(pairs))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def vertex_count(glb: Glb, mesh_index: int) -> int:
    mesh = glb.json["meshes"][mesh_index]
    return sum(glb.json["accessors"][p["attributes"]["POSITION"]]["count"] for p in mesh.get("primitives", []))


# ---- the sun ----
def east_of(north: list[float]) -> tuple[float, float]:
    """East in the scene's horizontal plane (x, z) for a north (x, z): north turned clockwise seen from above."""
    nx, nz = north
    return (-nz, nx)


def sun_direction(azimuth: float, elevation: float, north: list[float]) -> tuple[float, float, float]:
    """Unit vector towards the sun in glTF coordinates (+Y up). Azimuth: degrees clockwise from north seen from
    above; elevation: degrees above the horizon."""
    a, e = math.radians(azimuth), math.radians(elevation)
    nx, nz = north
    ex, ez = east_of(north)
    hx = math.cos(a) * nx + math.sin(a) * ex
    hz = math.cos(a) * nz + math.sin(a) * ez
    return (math.cos(e) * hx, math.sin(e), math.cos(e) * hz)


def angle_between(u, v) -> float:
    lu = math.sqrt(sum(x * x for x in u)) or 1.0
    lv = math.sqrt(sum(x * x for x in v)) or 1.0
    c = sum(a * b for a, b in zip(u, v)) / (lu * lv)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))
