"""The checker on the samples and on broken copies of them: each broken copy must give its own error."""
from __future__ import annotations

import io
import json
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hsf import surface as S  # noqa: E402
from hsf.check import check  # noqa: E402
from hsf.glb import Glb, pack  # noqa: E402
from hsf.package import Package, write  # noqa: E402

SCENE = ROOT / "samples" / "sample-house.hpscene"
BAKE = ROOT / "samples" / "sample-house.hpbake"


def files_of(path) -> dict[str, bytes]:
    return dict(Package.open(path).files)


def zipped(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    write(buf, files)
    return buf.getvalue()


def edit_json(files, name, fn):
    doc = json.loads(files[name])
    fn(doc)
    files[name] = json.dumps(doc).encode()
    return files


def edit_glb(files, name, fn):
    g = Glb.parse(files[name])
    fn(g.json, g)
    files[name] = pack(g.json, g.bin)
    return files


def node(doc, sid):
    return next(n for n in doc["nodes"] if n.get("name") == sid)


def scene_errors(files) -> list[str]:
    return check(zipped(files)).errors


def bake_errors(bake_files, scene_files=None) -> list[str]:
    scene = zipped(scene_files) if scene_files is not None else zipped(files_of(SCENE))
    return check(zipped(bake_files), scene=scene).errors


def has(errors, text):
    assert any(text in e for e in errors), f"no error with {text!r} in {errors}"


# ------------------------------------------------------------------ the samples
def test_samples_are_valid():
    s = check(SCENE)
    assert s.ok and not s.warnings, s.text()
    b = check(BAKE, scene=SCENE)
    assert b.ok and not b.warnings, b.text()
    assert check(BAKE).ok  # also alone


def test_samples_are_up_to_date():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "make_samples.py"), "--check"], capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_samples_have_what_the_task_asks_for():
    pkg = Package.open(SCENE)
    doc = pkg.doc
    assert len(doc["storeys"]) == 2
    g = Glb.parse(pkg.files["house.glb"])
    hps = [n["extras"]["hp"] for n in g.json["nodes"]]
    kinds = {h["kind"] for h in hps}
    assert {"wall", "floor", "ceiling", "slab-edge", "stair", "roof", "glass", "furniture", "lamp", "ground",
            "garden"} <= kinds
    assert len([h for h in hps if h["kind"] == "floor"]) >= 4  # a few rooms
    assert all(len(h["hash"]) == 32 for h in hps)
    bake = Package.open(BAKE)
    assert bake.doc["snow"] and bake.doc["photos"] and bake.doc["pages"]
    assert any(m["open"] for m in bake.doc["moments"])


def test_cli_exit_codes(tmp_path):
    ok = subprocess.run([sys.executable, str(ROOT / "check.py"), str(SCENE), str(BAKE)], capture_output=True,
                        text=True)
    assert ok.returncode == 0, ok.stdout
    assert "against" in ok.stdout  # the bake was checked against the scene it names
    bad = tmp_path / "bad.hpscene"
    bad.write_bytes(zipped(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(version="2.0"))))
    r = subprocess.run([sys.executable, str(ROOT / "check.py"), str(bad)], capture_output=True, text=True)
    assert r.returncode == 1 and "newer app" in r.stdout


# ------------------------------------------------------------------ versions
def test_newer_major_is_refused():
    has(scene_errors(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(version="2.0"))), "newer app")
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", lambda d: d.update(version="3.1"))), "newer app")


def test_newer_minor_is_read_and_unknown_fields_ignored():
    def newer(d):
        d["version"] = "1.4"
        d["walk_paths"] = [{"id": "w1", "points": [[0, 0, 0], [1, 0, 0]]}]
        d["recipe"]["something_new"] = True
        d["recipe"]["moments"][0]["wind_gusts"] = 3
    f = edit_json(files_of(SCENE), "scene.json", newer)
    f = edit_glb(f, "house.glb", lambda d, g: node(d, "floor:r_bed")["extras"]["hp"].update(kind="sauna-floor",
                                                                                            glow=1))
    rep = check(zipped(f))
    assert rep.ok, rep.text()
    assert any("1.4 is newer" in w for w in rep.warnings)


def test_unknown_field_in_this_version_is_an_error():
    has(scene_errors(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(colour="red"))),
        "Additional properties")


def test_wrong_format_and_bad_version():
    has(scene_errors(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(format="house-bake"))), "'format'")
    has(scene_errors(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(version="1"))), "major.minor")


# ------------------------------------------------------------------ the zip
def test_not_a_zip_and_unsafe_paths():
    has(check(b"hello").errors, "not a zip")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("scene.json", "{}")
        z.writestr("../evil.txt", "x")
    has(check(buf.getvalue()).errors, "'..'")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("scene.json", "{}")
        z.writestr("bake.json", "{}")
    has(check(buf.getvalue()).errors, "exactly one")


def test_zip_names_must_be_utf8():
    def zip_with(name, flag):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("scene.json", "{}")
            info = zipfile.ZipInfo(name)
            z.writestr(info, "x")
        data = bytearray(buf.getvalue())
        # zipfile sets bit 11 itself for non-ASCII names; set it the way the test wants (local + central headers)
        for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            i = 0
            while (i := data.find(sig, i)) >= 0:
                nlen = int.from_bytes(data[i + 28:i + 30] if sig == b"PK\x01\x02" else data[i + 26:i + 28], "little")
                nstart = i + (46 if sig == b"PK\x01\x02" else 30)
                if bytes(data[nstart:nstart + nlen]) == name.encode("utf-8"):
                    flags = int.from_bytes(data[i + off:i + off + 2], "little")
                    flags = (flags | 0x800) if flag else (flags & ~0x800)
                    data[i + off:i + off + 2] = flags.to_bytes(2, "little")
                i += 4
        return bytes(data)
    has(check(zip_with("caf\u00e9.txt", False)).errors, "not a UTF-8 name")
    assert not any("UTF-8 name" in e for e in check(zip_with("caf\u00e9.txt", True)).errors)
    assert not any("UTF-8 name" in e for e in check(zip_with("plain.txt", False)).errors)
    # flag set but the bytes are not valid UTF-8: zipfile itself raises, the checker must report it
    bad = zip_with("caf\u00e9.txt", True).replace("caf\u00e9.txt".encode(), b"caf\xe9\xe9.txt")
    has(check(bad).errors, "not a UTF-8 name")


def test_missing_and_unused_files():
    f = files_of(SCENE)
    del f["house.glb"]
    has(scene_errors(f), "house.glb is not in the package")
    f = files_of(SCENE)
    f["notes.txt"] = b"hi"
    rep = check(zipped(f))
    assert rep.ok and any("notes.txt" in w for w in rep.warnings)


# ------------------------------------------------------------------ surfaces in house.glb
def test_duplicate_id():
    def dup(doc, g):
        node(doc, "floor:r_kitchen")["extras"]["hp"]["id"] = "floor:r_living"
        node(doc, "floor:r_kitchen")["name"] = "floor:r_living"
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", dup)), "used by two nodes")


def test_bad_id_and_name():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_kitchen")["extras"]["hp"].update(id="Floor kitchen"))),
        "does not match '^")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_kitchen").update(name="Kitchen floor"))), "must be named")


def test_normals_are_needed():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", lambda d, g: d["meshes"][node(d, "floor:r_bed")["mesh"]]
                              ["primitives"][0]["attributes"].pop("NORMAL"))), "no NORMAL")


def test_mesh_without_labels():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_kitchen").pop("extras"))), "without extras.hp")


def test_hash_must_match_the_geometry():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_kitchen")["extras"]["hp"].update(hash="0" * 32))),
        "does not match its geometry")

    def move_vertex(doc, g):  # change the geometry, keep the old hash
        acc = doc["accessors"][doc["meshes"][node(doc, "floor:r_kitchen")["mesh"]]["primitives"][0]["attributes"]
                               ["POSITION"]]
        view = doc["bufferViews"][acc["bufferView"]]
        b = bytearray(g.bin)
        x = struct.unpack_from("<f", b, view["byteOffset"])[0]
        struct.pack_into("<f", b, view["byteOffset"], x + 0.01)
        g.bin = bytes(b)
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", move_vertex)), "does not match its geometry")


def test_hash_ignores_a_tenth_of_a_millimetre_but_not_a_millimetre():
    g = Glb.parse(Package.open(SCENE).files["house.glb"])
    i = node(g.json, "floor:r_kitchen")["mesh"]
    before = S.surface_hash(g, i)
    view = g.json["bufferViews"][g.json["accessors"][g.json["meshes"][i]["primitives"][0]["attributes"]["POSITION"]]
                                 ["bufferView"]]
    for delta, same in ((0.00004, True), (0.0015, False)):
        b = bytearray(g.bin)
        x = struct.unpack_from("<f", b, view["byteOffset"])[0]
        struct.pack_into("<f", b, view["byteOffset"], x + delta)
        assert (S.surface_hash(Glb(g.json, bytes(b)), i) == before) is same


def test_round_half_away_from_zero():
    assert [S.round_half_away(x) for x in (0.5, 1.5, 2.5, -0.5, -1.5, 0.49999, -2.4)] == [1, 2, 3, -1, -2, 0, -2]


def test_scene_hash():
    has(scene_errors(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(scene_hash="f" * 32))),
        "scene_hash")


def test_storey_and_group_rules():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "ground:plot")["extras"]["hp"].update(storey="st_ground"))),
        "storey must be null")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_bed")["extras"]["hp"].update(storey=None))),
        "needs its storey")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_bed")["extras"]["hp"].update(storey="st_attic"))),
        "not an included storey")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "ground:plot")["extras"]["hp"].update(group="street"))),
        "leaves out")


def test_glass_never_gets_light():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "glass:o_g_win1")["extras"]["hp"].update(bake="VERTEX"))),
        "must have bake 'NO'")


def test_map_needs_uv1_and_its_size():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_bed")["extras"]["hp"].pop("uv1_px"))), "no uv1_px")

    def drop_uv1(doc, g):
        doc["meshes"][node(doc, "floor:r_bed")["mesh"]]["primitives"][0]["attributes"].pop("TEXCOORD_1")
    f = edit_glb(files_of(SCENE), "house.glb", drop_uv1)
    errs = scene_errors(f)
    has(errs, "without TEXCOORD_1")

    def drop_uv0(doc, g):  # glTF numbers UV sets from 0: Blender's importer then loses the light-map UVs
        doc["meshes"][node(doc, "floor:r_bed")["mesh"]]["primitives"][0]["attributes"].pop("TEXCOORD_0")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", drop_uv0)), "without TEXCOORD_0")


def _set_uv1(doc, g, sid, fn):
    acc = doc["accessors"][doc["meshes"][node(doc, sid)["mesh"]]["primitives"][0]["attributes"]["TEXCOORD_1"]]
    view = doc["bufferViews"][acc["bufferView"]]
    b = bytearray(g.bin)
    uv = [struct.unpack_from("<2f", b, view["byteOffset"] + 8 * i) for i in range(acc["count"])]
    for i, t in enumerate(fn(uv)):
        struct.pack_into("<2f", b, view["byteOffset"] + 8 * i, *t)
    g.bin = bytes(b)
    hp = node(doc, sid)["extras"]["hp"]
    hp["hash"] = S.surface_hash(Glb(doc, g.bin), node(doc, sid)["mesh"], hp.get("uv1_px"))


def _rehash_scene(files):
    g = Glb.parse(files["house.glb"])
    pairs = {n["extras"]["hp"]["id"]: n["extras"]["hp"]["hash"] for n in g.json["nodes"]}
    return edit_json(files, "scene.json", lambda d: d.update(scene_hash=S.scene_hash(pairs)))


def test_uv1_rules():
    # outside 0 … 1
    f = _rehash_scene(edit_glb(files_of(SCENE), "house.glb",
                               lambda d, g: _set_uv1(d, g, "floor:r_bed", lambda uv: [(u * 1.5, v) for u, v in uv])))
    errs = scene_errors(f)
    assert len(errs) == 1, errs
    has(errs, "outside 0")
    # a chart pushed onto the edge of its map
    f = _rehash_scene(edit_glb(files_of(SCENE), "house.glb",
                               lambda d, g: _set_uv1(d, g, "floor:r_bed",
                                                     lambda uv: [(max(0.0, u - 0.02), v) for u, v in uv])))
    has(scene_errors(f), "closer than 2 texels to the edge")

    # one of the roof's charts (one quad each) slid to 1 texel from another, not stretched
    def near(doc, g):
        W = node(doc, "roof:st_first:0")["extras"]["hp"]["uv1_px"][0]

        def fn(uv):
            q1, q2 = uv[4:8], uv[8:12]
            H = node(doc, "roof:st_first:0")["extras"]["hp"]["uv1_px"][1]
            r1 = [min(u for u, v in q1), min(v for u, v in q1), max(u for u, v in q1), max(v for u, v in q1)]
            w2 = max(u for u, v in q2) - min(u for u, v in q2)
            h2 = max(v for u, v in q2) - min(v for u, v in q2)
            for x, y in ((r1[2] + 1 / W, r1[1]), (r1[0] - 1 / W - w2, r1[1]), (r1[0], r1[3] + 1 / H),
                         (r1[0], r1[1] - 1 / H - h2)):
                if 3 / W <= x and x + w2 <= 1 - 3 / W and 3 / H <= y and y + h2 <= 1 - 3 / H:
                    break
            du, dv = x - min(u for u, v in q2), y - min(v for u, v in q2)
            return uv[:8] + [(u + du, v + dv) for u, v in q2] + uv[12:]
        _set_uv1(doc, g, "roof:st_first:0", fn)
    f = _rehash_scene(edit_glb(files_of(SCENE), "house.glb", near))
    errs = scene_errors(f)
    assert len(errs) == 1, errs
    has(errs, "closer than 4 texels")

    # a map four times too large for its texels per metre: stretched
    def bigger(doc, g):
        node(doc, "floor:r_bed")["extras"]["hp"]["uv1_px"] = [4 * x for x in
                                                               node(doc, "floor:r_bed")["extras"]["hp"]["uv1_px"]]
        _set_uv1(doc, g, "floor:r_bed", lambda uv: uv)
    f = _rehash_scene(edit_glb(files_of(SCENE), "house.glb", bigger))
    has(scene_errors(f), "stretched")


def test_folded_map_is_found():
    from hsf.check import _covered_twice
    a, b, c, d = (0.5, 0.5), (8.5, 0.5), (8.5, 8.5), (0.5, 8.5)
    assert _covered_twice([((a, b, c), 0), ((a, c, d), 0)], 10, 10) == 0          # a quad: the shared edge once
    assert _covered_twice([((a, b, c), 0), ((a, c, b), 0)], 10, 10) > 0           # the same triangle, turned over
    assert _covered_twice([((a, b, c), 0), ((a, (8.5, 4.5), d), 0)], 10, 10) > 0  # two that overlap in part


def test_map_must_fit_a_page():
    f = edit_glb(files_of(SCENE), "house.glb",
                 lambda d, g: node(d, "ground:plot")["extras"]["hp"].update(uv1_px=[1500, 400]))
    has(scene_errors(f), "does not fit")


# ------------------------------------------------------------------ the recipe
def test_sun_must_match_its_angles():
    def turn(d):
        d["recipe"]["moments"][0]["sun"]["azimuth"] = (d["recipe"]["moments"][0]["sun"]["azimuth"] + 30) % 360
    has(scene_errors(edit_json(files_of(SCENE), "scene.json", turn)), "away from its azimuth")


def test_time_zone_mistake_is_a_warning():
    f = edit_json(files_of(SCENE), "scene.json",
                  lambda d: d["recipe"]["moments"][0].update(utc_offset="+05:00"))
    rep = check(zipped(f))
    assert rep.ok and any("time zone" in w for w in rep.warnings), rep.text()


def test_recipe_references():
    has(scene_errors(edit_json(files_of(SCENE), "scene.json",
                               lambda d: d["recipe"]["moments"][0].update(season="autumn"))), "not in recipe.seasons")
    has(scene_errors(edit_json(files_of(SCENE), "scene.json",
                               lambda d: d["recipe"]["photos"][0].update(camera="drone"))), "not in recipe.cameras")
    has(scene_errors(edit_json(files_of(SCENE), "scene.json",
                               lambda d: d["recipe"]["photos"][0].update(moment="dawn"))), "not in recipe.moments")
    has(scene_errors(edit_json(files_of(SCENE), "scene.json",
                               lambda d: d["recipe"].update(open_storeys=["st_attic"]))), "not an included storey")
    has(scene_errors(edit_json(files_of(SCENE), "scene.json",
                               lambda d: d["recipe"]["moments"][3].update(lamps=["lamp:p_nowhere"]))),
        "not a lamp")
    has(scene_errors(edit_json(files_of(SCENE), "scene.json",
                               lambda d: d["recipe"]["moments"].append(dict(d["recipe"]["moments"][0])))),
        "listed twice")


def test_a_turntable_video_in_the_recipe():
    def add(d):
        d["recipe"]["videos"].append({"id": "turn", "kind": "turntable", "camera": "garden-view",
                                      "moment": "summer-morning", "size": [1280, 720], "seconds": 8, "fps": 25})
    assert check(zipped(edit_json(files_of(SCENE), "scene.json", add))).ok


# ------------------------------------------------------------------ the bake
def test_bake_rect_outside_page_and_overlap():
    def outside(d):
        e = d["moments"][0]["maps"]["floor:r_bed"]
        e["rect"][0] = 1000
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", outside)), "does not lie inside")

    def overlap(d):
        m = d["moments"][0]["maps"]
        m["floor:r_bed"]["rect"][:2] = m["floor:r_bath"]["rect"][:2]
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", overlap)), "overlap")


def test_bake_rect_must_be_the_surface_map_size():
    def grow(d):
        d["moments"][0]["maps"]["floor:r_bed"]["rect"][2] -= 1
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", grow)), "its uv1_px")


def test_bake_vertex_counts():
    def fewer(d):
        d["moments"][0]["maps"]["furniture:f_table:0"]["count"] -= 4
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", fewer)), "vertex values for")

    def past_end(d):
        d["moments"][0]["maps"]["furniture:f_table:0"]["offset"] = 10 ** 6
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", past_end)), "run past the end")


def test_bake_kind_must_fit_the_surface():
    def as_vertex(d):
        d["moments"][0]["maps"]["floor:r_bed"] = {"vertex": "v0", "offset": 0, "count": 4}
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", as_vertex)), "is bake 'MAP'")


def test_bake_unknown_surface_and_page():
    def unknown(d):
        d["moments"][0]["maps"]["floor:r_cellar"] = {"page": "p0", "rect": [1020, 1020, 2, 2]}
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", unknown)), "not in bake.json's surfaces")

    def nopage(d):
        d["moments"][0]["maps"]["floor:r_bed"]["page"] = "p9"
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", nopage)), "does not exist")


def test_bake_pictures():
    f = files_of(BAKE)
    del f["light/p1.png"]
    has(bake_errors(f), "is not in the package")
    f = edit_json(files_of(BAKE), "bake.json", lambda d: d["pages"][0].update(size=[2048, 2048]))
    has(bake_errors(f), "bake.json says 2048")
    f = files_of(BAKE)
    f["light/p0.png"] = b"not a picture"
    has(bake_errors(f), "is not a PNG")


def test_bake_against_the_recipe():
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", lambda d: d.update(light="ALL"))), "differs from the recipe")
    # the bake's own texels_per_m is only an echo: each result is checked against its surface's map size
    assert not bake_errors(edit_json(files_of(BAKE), "bake.json", lambda d: d["quality"].update(texels_per_m=32)))
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", lambda d: d["moments"][0].update(id="dawn"))),
        "not in the recipe")

    def open_wrong(d):
        d["moments"][0]["open"]["st_ground"]["floor:r_bed"] = d["moments"][0]["maps"]["floor:r_bed"]
    errs = bake_errors(edit_json(files_of(BAKE), "bake.json", open_wrong))
    has(errs, "surfaces of that storey only")

    def open_unknown(d):
        d["moments"][0]["open"]["st_first"] = {}
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", open_unknown)), "open_storeys")


def test_live_bakes_nothing():
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", lambda d: d.update(light="LIVE"))),
        "bakes nothing")


def test_placed_surfaces_need_their_matrix():
    has(bake_errors(edit_json(files_of(BAKE), "bake.json",
                              lambda d: d["surfaces"]["furniture:f_table:0"].pop("matrix"))), "no 'matrix'")
    has(bake_errors(edit_json(files_of(BAKE), "bake.json",
                              lambda d: d["surfaces"]["floor:r_bed"].update(box=[0, 0, 0, 1, 1, 1]))), "'box'")


def test_snow():
    def lies_nowhere(doc, g):
        node(doc, "snow:roof:st_first:0")["extras"]["hp"]["on"] = "roof:st_first:9"
    has(bake_errors(edit_glb(files_of(BAKE), "snow/winter.glb", lies_nowhere)), "not in the scene")

    def not_snow(doc, g):
        node(doc, "snow:roof:st_first:0")["extras"]["hp"]["kind"] = "roof"
    has(bake_errors(edit_glb(files_of(BAKE), "snow/winter.glb", not_snow)), "a snow file holds only snow")

    def other_group(doc, g):
        node(doc, "snow:ground:plot")["extras"]["hp"]["group"] = "street"
    has(bake_errors(edit_glb(files_of(BAKE), "snow/winter.glb", other_group)), "hides with it")

    def summer_snow(d):
        d["moments"][0]["maps"]["snow:ground:plot"] = d["moments"][2]["maps"]["snow:ground:plot"]
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", summer_snow)), "lit in a moment of season")


def test_photos():
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", lambda d: d["photos"][0].update(id="photo-9"))),
        "not in the recipe")
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", lambda d: d["photos"][0].update(size=[640, 480]))),
        "bake.json says 640")


def test_a_bake_of_an_older_export_is_readable_with_warnings():
    """The owner changed a wall after the bake: the new export has another id and that wall's hash differs – the bake
    still reads, the wall is out of date."""
    def changed(doc, g):
        _set_uv1(doc, g, "wall:w_g_front:a", lambda uv: [(u, v) for u, v in uv[:-1]] + [(uv[-1][0], uv[-1][1] + 0.001)])
    scene = _rehash_scene(edit_glb(files_of(SCENE), "house.glb", changed))
    scene = edit_json(scene, "scene.json", lambda d: d.update(id="sample-house-b"))
    rep = check(zipped(files_of(BAKE)), scene=zipped(scene))
    assert rep.ok, rep.text()
    assert any("out of date" in w and "w_g_front:a" in w for w in rep.warnings), rep.text()
    # the same export id with a changed hash is an error (it cannot be the scene it was made from)
    scene = _rehash_scene(edit_glb(files_of(SCENE), "house.glb", changed))
    has(check(zipped(files_of(BAKE)), scene=zipped(scene)).errors, "scene_hash differs")


def test_broken_scene_for_cross_checks():
    bad = zipped(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(scene_hash="0" * 32)))
    has(check(zipped(files_of(BAKE)), scene=bad).errors, "check it first")


@pytest.mark.parametrize("name", ["scene-1", "bake-1", "surface-1"])
def test_schemas_are_valid(name):
    import jsonschema
    jsonschema.Draft202012Validator.check_schema(json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text()))


# ------------------------------------------------------------------ the independent review's findings (task 0016)
def _pos_view(doc, sid):
    acc = doc["accessors"][doc["meshes"][node(doc, sid)["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
    return doc["bufferViews"][acc["bufferView"]]["byteOffset"]


def _poke_pos(sid, value):
    def fn(doc, g):
        b = bytearray(g.bin)
        struct.pack_into("<f", b, _pos_view(doc, sid), value)
        g.bin = bytes(b)
    return fn


@pytest.mark.parametrize("what,fn,text", [
    ("NaN position", _poke_pos("floor:r_bed", float("nan")), "not a finite number"),
    ("3,000 km away", _poke_pos("floor:r_bed", 3.0e6), "2,147 km"),
    ("mesh as text", lambda d, g: node(d, "floor:r_bed").update(mesh="0"), "does not exist"),
    ("extras a list", lambda d, g: node(d, "floor:r_bed").update(extras=[1]), "without extras.hp"),
    ("node a list", lambda d, g: d["nodes"].__setitem__(3, [1]), "not an object"),
    ("count as text", lambda d, g: d["accessors"][0].update(count="x"), "values for"),
    ("index past the end", lambda d, g: d["accessors"][d["meshes"][node(d, "floor:r_bed")["mesh"]]["primitives"][0]
                                                       ["indices"]].update(count=10 ** 3), "cannot be read"),
])
def test_hostile_glb_is_reported_not_raised(what, fn, text):
    errs = scene_errors(edit_glb(files_of(SCENE), "house.glb", fn))
    assert errs, what
    has(errs, text)


def test_json_without_nan_and_control_characters():
    f = files_of(SCENE)
    f["scene.json"] = f["scene.json"].replace(b'"latitude": 53.5', b'"latitude": NaN')
    has(scene_errors(f), "NaN")
    has(scene_errors(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(id="sample-house-a\n"))),
        "control character")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "floor:r_bed")["extras"]["hp"].update(id="floor:r_bed\n"))),
        "control character")


def _prim(d, sid):
    return d["meshes"][node(d, sid)["mesh"]]["primitives"][0]


def test_meshes_every_reader_reads_the_same():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", lambda d, g: _prim(d, "furniture:f_table:0")
                              .update(mode=0))), "mode 4")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", lambda d, g: d["accessors"][
        _prim(d, "furniture:f_table:0")["attributes"]["POSITION"]].update(
        sparse={"count": 1, "indices": {"bufferView": 0, "componentType": 5125}, "values": {"bufferView": 0}}))),
        "sparse")

    def unused(d, g):  # leave out the last triangle: its vertices are no longer used
        acc = d["accessors"][_prim(d, "furniture:f_table:0")["indices"]]
        acc["count"] -= 6
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", unused)), "not used by any triangle")

    def odd(d, g):
        d["accessors"][_prim(d, "furniture:f_table:0")["indices"]]["count"] -= 1
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", odd)), "whole number of triangles")


def test_map_surfaces_are_not_scaled():
    f = edit_glb(files_of(SCENE), "house.glb",
                 lambda d, g: node(d, "floor:r_bed").update(scale=[2.0, 1.0, 2.0]))
    has(scene_errors(f), "scaled or mirrored")


def test_lamp_groups():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: node(d, "lamp:p_living_1")["extras"]["hp"].update(group="house"))),
        "lamps are in")


def test_glb_structure():
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb",
                              lambda d, g: d.update(extensionsRequired=["KHR_draco_mesh_compression"]))),
        "extensionsRequired")

    def second_scene(d, g):
        i = d["nodes"].index(node(d, "floor:r_bed"))
        d["scenes"][0]["nodes"].remove(i)
        d["scenes"].append({"nodes": [i]})
    errs = scene_errors(edit_glb(files_of(SCENE), "house.glb", second_scene))
    has(errs, "exactly one")
    has(errs, "does not reach its node")

    def two_parents(d, g):
        d["nodes"].append({"name": "group a", "children": [5]})
        d["nodes"].append({"name": "group b", "children": [5]})
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", two_parents)), "two parents")
    has(scene_errors(edit_glb(files_of(SCENE), "house.glb", lambda d, g: node(d, "lamp:p_living_1")["extensions"]
                              ["KHR_lights_punctual"].update(light=99))), "light 99 does not exist")


def _png_with(chunk: bytes, depth=8, ctype=2) -> bytes:
    import zlib
    w = h = 1024
    raw = (b"\0" + b"\0" * (w * 3 * depth // 8 * (4 if ctype == 6 else 3) // 3)) * h

    def c(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + c(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, 0)) + chunk
            + c(b"IDAT", zlib.compress(raw)) + c(b"IEND", b""))


def test_pages_carry_raw_values():
    import zlib
    gama = struct.pack(">I", 4) + b"gAMA" + struct.pack(">I", 45455) + struct.pack(
        ">I", zlib.crc32(b"gAMA" + struct.pack(">I", 45455)) & 0xFFFFFFFF)
    f = files_of(BAKE)
    f["light/p0.png"] = _png_with(gama)
    has(bake_errors(f), "gAMA")
    f = files_of(BAKE)
    f["light/p0.png"] = _png_with(b"", depth=16)
    has(bake_errors(f), "8-bit RGB")


def test_vertex_results_do_not_share_values():
    def share(d):
        d["moments"][0]["maps"]["lamp:p_living_1"] = dict(d["moments"][0]["maps"]["furniture:f_table:0"],
                                                          count=20)
    has(bake_errors(edit_json(files_of(BAKE), "bake.json", share)), "share values")


def test_minor_versions_extend_only_the_open_lists():
    def newer_group(doc, g):
        node(doc, "garden:ga_terrace")["extras"]["hp"]["group"] = "allotment"  # has its own texels_per_m
    f = edit_json(edit_glb(files_of(SCENE), "house.glb", newer_group), "scene.json",
                  lambda d: (d.update(version="1.1"), d["recipe"]["include"]["groups"].append("allotment")))
    rep = check(zipped(f))
    assert rep.ok, rep.text()
    # the light choice, bake kinds and page sizes are not open: a new value there needs a new major version
    f = edit_json(files_of(SCENE), "scene.json", lambda d: (d.update(version="1.1"), d["recipe"].update(light="HALF")))
    has(check(zipped(f)).errors, "light")
    f = edit_glb(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(version="1.1")), "house.glb",
                 lambda d, g: node(d, "floor:r_bed")["extras"]["hp"].update(bake="PROBE"))
    has(check(zipped(f)).errors, "bake")


def test_minor_versions_compare_as_numbers():
    rep = check(zipped(edit_json(files_of(SCENE), "scene.json", lambda d: d.update(version="1.10"))))
    assert rep.ok and any("1.10 is newer" in w for w in rep.warnings)


# ------------------------------------------------------------------ the two leads' review (task 0016)
def test_density_per_surface_and_per_group():
    pkg = Package.open(SCENE)
    assert pkg.doc["recipe"]["quality"]["texels_per_m_by_group"] == {"garden": 6.0}
    g = Glb.parse(pkg.files["house.glb"])
    assert node(g.json, "garden:ga_terrace")["extras"]["hp"]["texels_per_m"] == 10.0
    # the plot was laid out at its group's 6 texels/m: checked at the default 16 it is stretched
    f = edit_json(files_of(SCENE), "scene.json", lambda d: d["recipe"]["quality"].pop("texels_per_m_by_group"))
    errs = scene_errors(f)
    has(errs, "'ground:plot'")
    has(errs, "stretched")
    assert not any("ga_terrace" in e for e in errs)  # its own value wins over the group's
    # a surface's own value that does not fit its layout
    f = edit_glb(files_of(SCENE), "house.glb",
                 lambda d, g: node(d, "garden:ga_terrace")["extras"]["hp"].update(texels_per_m=20.0))
    has(scene_errors(f), "stretched")


def test_sun_light():
    b = Package.open(BAKE).doc
    by = {m["id"]: m for m in b["moments"]}
    assert by["winter-night"]["sun_light"] is None and len(by["summer-morning"]["sun_light"]) == 3
    has(bake_errors(edit_json(files_of(BAKE), "bake.json",
                              lambda d: d["moments"][3].update(sun_light=[1.0, 1.0, 1.0]))), "at night")

    def all_baked(d):
        d["light"] = "ALL"
    errs = check(zipped(edit_json(files_of(BAKE), "bake.json", all_baked))).errors
    has(errs, "only for light 'SOFT'")
    # optional: a bake without it is fine
    assert not bake_errors(edit_json(files_of(BAKE), "bake.json",
                                     lambda d: [m.pop("sun_light") for m in d["moments"]]))


def test_sun_light_zero_under_full_overcast_and_null_by_day():
    day = next(m for m in Package.open(BAKE).doc["moments"] if m.get("sun_light") is not None)

    def set_day(v):
        return lambda d: next(m for m in d["moments"] if m["id"] == day["id"]).update(sun_light=v)
    assert not bake_errors(edit_json(files_of(BAKE), "bake.json", set_day([0, 0, 0])))
    assert not bake_errors(edit_json(files_of(BAKE), "bake.json", set_day(None)))
    has(bake_errors(edit_json(files_of(BAKE), "bake.json",
                              lambda d: next(m for m in d["moments"] if m["id"] == "winter-night")
                                         .update(sun_light=[0, 0, 0]))), "at night")
