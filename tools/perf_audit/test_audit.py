"""Offline regression coverage for the client performance audit.

The fixtures are synthetic and deliberately small; neither Godot nor project
assets are required. Run with the repository-local pytest temporary directory.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import sys
import zlib

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "client_perf_audit", Path(__file__).with_name("audit.py")
)
assert _SPEC is not None and _SPEC.loader is not None
audit = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = audit
_SPEC.loader.exec_module(audit)


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    rows = (b"\0" + b"\0\0\0\xff" * width) * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def _jpeg(width: int, height: int, sof: int = 0xC0) -> bytes:
    # Include a length-bearing APP segment before the SOF. This catches parsers
    # which assume a fixed offset or confuse the JPEG segment length endianness.
    app = b"JFIF\0\x01\x01\0\0\x01\0\x01\0\0"
    frame = struct.pack(">BHHB", 8, height, width, 3)
    frame += b"\x01\x11\0\x02\x11\x01\x03\x11\x01"
    return (
        b"\xff\xd8\xff\xe0"
        + struct.pack(">H", len(app) + 2)
        + app
        + bytes((0xFF, sof))
        + struct.pack(">H", len(frame) + 2)
        + frame
        + b"\xff\xd9"
    )


def _webp(width: int, height: int, kind: bytes) -> bytes:
    if kind == b"VP8X":
        payload = b"\0" * 4
        payload += (width - 1).to_bytes(3, "little")
        payload += (height - 1).to_bytes(3, "little")
    elif kind == b"VP8L":
        payload = b"\x2f" + ((width - 1) | ((height - 1) << 14)).to_bytes(4, "little")
    else:
        payload = b"\0\0\0\x9d\x01\x2a" + struct.pack("<HH", width, height)
    chunk = kind + struct.pack("<I", len(payload)) + payload
    if len(payload) % 2:
        chunk += b"\0"
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


def _glb(primitives: list[tuple[int, int, bool]]) -> bytes:
    """Build a GLB with (mode, element count, indexed) primitives."""
    data = bytearray()
    views = []
    accessors = []
    primitive_records = []

    def accessor(count: int, indices: bool) -> int:
        # All positions and indices may be zero: the auditor measures declared
        # rendering work, not geometric area or distinct vertices.
        while len(data) % 4:
            data.append(0)
        start = len(data)
        data.extend(b"\0" * count * (2 if indices else 12))
        views.append({"buffer": 0, "byteOffset": start, "byteLength": len(data) - start})
        accessors.append(
            {
                "bufferView": len(views) - 1,
                "componentType": 5123 if indices else 5126,
                "count": count,
                "type": "SCALAR" if indices else "VEC3",
            }
        )
        return len(accessors) - 1

    for mode, count, indexed in primitives:
        position = accessor(3 if indexed else count, False)
        primitive = {"attributes": {"POSITION": position}, "mode": mode, "material": 0}
        if indexed:
            primitive["indices"] = accessor(count, True)
        primitive_records.append(primitive)
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(data)}],
        "bufferViews": views,
        "accessors": accessors,
        "materials": [{"name": "Glass", "alphaMode": "BLEND"}],
        "meshes": [{"name": "Fixture", "primitives": primitive_records}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    data.extend(b"\0" * (-len(data) % 4))
    chunks = struct.pack("<I4s", len(encoded), b"JSON") + encoded
    chunks += struct.pack("<I4s", len(data), b"BIN\0") + bytes(data)
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def _write(root: Path, name: str, content: str | bytes) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _line(source: str, fragment: str) -> int:
    return next(i for i, line in enumerate(source.splitlines(), 1) if fragment in line)


@pytest.mark.parametrize("width,height", [(1, 1), (17, 31), (1024, 512)])
def test_png_dimensions(width: int, height: int) -> None:
    assert audit.read_image_size(_png(width, height)) == (width, height)


@pytest.mark.parametrize("sof", [0xC0, 0xC2])
def test_jpeg_baseline_and_progressive_dimensions(sof: int) -> None:
    assert audit.read_image_size(_jpeg(2048, 1024, sof)) == (2048, 1024)


@pytest.mark.parametrize("kind", [b"VP8X", b"VP8L", b"VP8 "])
def test_webp_dimensions(kind: bytes) -> None:
    assert audit.read_image_size(_webp(513, 257, kind)) == (513, 257)


@pytest.mark.parametrize("data", [b"", b"not an image", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff\xe0\0\x10"])
def test_truncated_or_unknown_image_is_not_a_valid_size(data: bytes) -> None:
    assert audit.read_image_size(data) is None


def test_mipmap_estimates_include_exact_non_power_of_two_chain() -> None:
    assert audit.mip_bytes(3, 5) == 60
    assert audit.mip_bytes(3, 5, mipmaps=True) == 60 + 8 + 4
    assert audit.mip_bytes(1, 1, mipmaps=True) == 4
    assert audit.mip_bytes(1, 8, bytes_per_pixel=2, mipmaps=True) == 16 + 8 + 4 + 2


def test_texture_import_limit_mipmaps_and_compression_are_reported(tmp_path: Path) -> None:
    _write(tmp_path, "texture.png", _png(1024, 512))
    _write(
        tmp_path,
        "texture.png.import",
        '[remap]\nimporter="texture"\n\n[params]\n'
        'process/size_limit=256\nmipmaps/generate=true\ncompress/mode=2\n',
    )
    textures = audit.scan(tmp_path)["textures"]
    assert len(textures) == 1
    texture = textures[0]
    assert (texture["source_width"], texture["source_height"]) == (1024, 512)
    assert (texture["width"], texture["height"]) == (256, 128)
    assert texture["mipmaps"] is True
    assert texture["compression_mode"] == 2
    assert texture["rgba8_bytes"] == 131072 + 32768 + 8192 + 2048 + 512 + 128 + 32 + 8 + 4


def test_glb_counts_indexed_nonindexed_and_strip_triangles(tmp_path: Path) -> None:
    _write(tmp_path, "mixed.glb", _glb([(4, 900, True), (4, 600, False), (5, 102, True)]))
    result = audit.scan(tmp_path)
    assert len(result["meshes"]) == 1
    mesh = result["meshes"][0]
    assert mesh["path"] == f"{tmp_path.name}/mixed.glb"
    assert mesh["triangles"] == 600
    assert mesh["surfaces"] == 3
    assert mesh["material_count"] == 1
    assert mesh["transparent_materials"] == [0]


@pytest.mark.parametrize("lod_enabled", [False, True])
def test_mesh_lod_setting_comes_from_import_metadata(tmp_path: Path, lod_enabled: bool) -> None:
    _write(tmp_path, "dense.glb", _glb([(4, 180_000, True)]))
    _write(
        tmp_path,
        "dense.glb.import",
        '[remap]\nimporter="scene"\ntype="PackedScene"\n\n[params]\n'
        f'meshes/generate_lods={str(lod_enabled).lower()}\n',
    )
    result = audit.scan(tmp_path)
    expected = "import_enabled_unverified" if lod_enabled else "disabled"
    assert result["meshes"][0]["lod"] == expected
    mesh_findings = [finding for finding in result["findings"] if finding["category"] == "mesh"]
    assert len(mesh_findings) == 1
    assert f"LOD={expected}" in mesh_findings[0]["evidence"]
    assert ("set meshes/generate_lods=true" in mesh_findings[0]["recommendation"]) is not lod_enabled


def test_duplicates_compare_bytes_not_size_or_filename(tmp_path: Path) -> None:
    # Trailing bytes preserve the image header while making these large source
    # resources. The third file has exactly the same size but a different hash.
    payload = _png(2, 2) + b"a" * (2 * 1024 * 1024)
    _write(tmp_path, "first/a.png", payload)
    _write(tmp_path, "second/b.png", payload)
    _write(tmp_path, "third/a.png", payload[:-1] + b"b")
    duplicates = audit.scan(tmp_path)["duplicates"]
    assert len(duplicates) == 1
    assert set(duplicates[0]["paths"]) == {
        f"{tmp_path.name}/first/a.png", f"{tmp_path.name}/second/b.png"
    }
    assert duplicates[0]["bytes_each"] == len(payload)


def test_frame_audit_follows_called_helpers_and_excludes_unrelated_functions(tmp_path: Path) -> None:
    source = '''extends Node

func _process(delta):
    for child in get_children():
        get_node("Target").position.x += delta
    _tick()

func _tick():
    var nodes = []
    var state = {}
    for index in range(2):
        await get_tree().process_frame

func never_called():
    find_children("*")
'''
    _write(tmp_path, "tick.gd", source)
    findings = audit.scan(tmp_path)["findings"]
    lines = {finding["line"] for finding in findings if finding["path"] == f"{tmp_path.name}/tick.gd"}
    for fragment in ['get_node("Target")', "var nodes = []", "var state = {}", "await get_tree()"]:
        assert _line(source, fragment) in lines
    assert _line(source, 'find_children("*")') not in lines


def test_frame_audit_ignores_comments_and_literal_method_names(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "comments.gd",
        '''extends Node

func _physics_process(_delta):
    # for item in values: get_node("Target"); await get_tree().process_frame
    # var temporary = []; find_children("*")
    var message = 'find_children("*") get_node("Target")'
    pass
''',
    )
    findings = audit.scan(tmp_path)["findings"]
    assert not [finding for finding in findings if finding["path"] == f"{tmp_path.name}/comments.gd"]


def test_deferred_lambda_body_and_its_helpers_are_not_frame_work(tmp_path: Path) -> None:
    source = '''extends Node

func _process(_delta):
    pressed.connect(func():
        _later()
        find_children("Deferred")
    )
    var active_values = []

func _later():
    get_children()
'''
    _write(tmp_path, "deferred.gd", source)
    findings = audit.scan(tmp_path)["findings"]
    lines = {finding["line"] for finding in findings if finding["category"].startswith("script_")}
    assert _line(source, "active_values") in lines
    assert _line(source, 'find_children("Deferred")') not in lines
    assert _line(source, "get_children()") not in lines


@pytest.mark.parametrize(
    "source,target",
    [
        ('extends Node\nfunc _process(_delta): find_children("*")\n', "func _process"),
        (
            'extends Node\nfunc _process(_delta): _tick()\n'
            'func _tick() -> void: find_children("*")\n',
            "func _tick",
        ),
    ],
)
def test_inline_frame_functions_and_reachable_helpers_are_inspected(tmp_path: Path, source: str, target: str) -> None:
    _write(tmp_path, "inline.gd", source)
    findings = audit.scan(tmp_path)["findings"]
    assert any(finding["category"] == "script_tree_search" and finding["line"] == _line(source, target) for finding in findings)


def test_frame_allocations_in_default_arguments_and_string_join_are_detected(tmp_path: Path) -> None:
    source = '''extends Node

func _physics_process(_delta):
    var fallback = state.get("missing", {})
    var choices = state.get("choices", [])
    var text = ", ".join(names)
'''
    _write(tmp_path, "expressions.gd", source)
    findings = audit.scan(tmp_path)["findings"]
    observed = {(finding["category"], finding["line"]) for finding in findings}
    assert ("script_allocation", _line(source, "var fallback")) in observed
    assert ("script_allocation", _line(source, "var choices")) in observed
    assert ("script_string_build", _line(source, "var text")) in observed


def test_quoted_node_path_is_detected_but_string_documentation_is_not(tmp_path: Path) -> None:
    source = '''extends Node

func _process(_delta):
    var child = $"Node With Spaces"
    var help_text = '$"Example Node"'
'''
    _write(tmp_path, "node_path.gd", source)
    findings = audit.scan(tmp_path)["findings"]
    lookups = {finding["line"] for finding in findings if finding["category"] == "script_node_lookup"}
    assert _line(source, "var child") in lookups
    assert _line(source, "var help_text") not in lookups


def test_preload_is_not_runtime_loading_but_load_is(tmp_path: Path) -> None:
    source = '''extends Node

func _process(_delta):
    var cached = preload("res://asset.tres")
    var loaded = load("res://asset.tres")
'''
    _write(tmp_path, "loading.gd", source)
    findings = audit.scan(tmp_path)["findings"]
    heavy = {finding["line"] for finding in findings if finding["category"] == "script_heavy_call"}
    assert _line(source, "var cached") not in heavy
    assert _line(source, "var loaded") in heavy


def test_scene_counts_actual_node_types(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "effects.tscn",
        '''[gd_scene format=3]

[node name="Root" type="Node3D"]
[node name="Sun" type="DirectionalLight3D" parent="."]
[node name="Lamp" type="OmniLight3D" parent="."]
[node name="Beam" type="SpotLight3D" parent="."]
[node name="Mist" type="GPUParticles3D" parent="."]
[node name="Dust" type="CPUParticles3D" parent="."]
[node name="OmniLight3D" type="Sprite3D" parent="."]
# [node name="Commented" type="OmniLight3D" parent="."]
''',
    )
    scenes = audit.scan(tmp_path)["scenes"]
    assert len(scenes) == 1
    assert scenes[0]["path"] == f"{tmp_path.name}/effects.tscn"
    assert scenes[0]["local_lights"] == scenes[0]["serialized_lights"] == 3
    assert scenes[0]["local_particles"] == scenes[0]["serialized_particles"] == 2


def test_scene_instance_counts_include_each_serialized_instance(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "child.tscn",
        '[gd_scene format=3]\n[node name="Root" type="Node3D"]\n'
        '[node name="Lamp" type="OmniLight3D" parent="."]\n'
        '[node name="Mist" type="GPUParticles3D" parent="."]\n',
    )
    _write(
        tmp_path,
        "parent.tscn",
        '[gd_scene format=3]\n'
        '[ext_resource type="PackedScene" path="res://child.tscn" id="1"]\n'
        '[node name="Root" type="Node3D"]\n'
        '[node name="One" parent="." instance=ExtResource("1")]\n'
        '[node name="Two" parent="." instance=ExtResource("1")]\n',
    )
    _write(
        tmp_path,
        "grandparent.tscn",
        '[gd_scene format=3]\n'
        '[ext_resource type="PackedScene" path="res://parent.tscn" id="1"]\n'
        '[node name="Root" type="Node3D"]\n'
        '[node name="One" parent="." instance=ExtResource("1")]\n'
        '[node name="Two" parent="." instance=ExtResource("1")]\n',
    )
    scenes = audit.scan(tmp_path)["scenes"]
    parent = next(scene for scene in scenes if scene["path"].endswith("/parent.tscn"))
    assert parent["local_lights"] == parent["local_particles"] == 0
    assert parent["serialized_lights"] == parent["serialized_particles"] == 2
    grandparent = next(scene for scene in scenes if scene["path"].endswith("/grandparent.tscn"))
    assert grandparent["serialized_lights"] == grandparent["serialized_particles"] == 4


def test_standalone_text_material_uses_declared_resource_type(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "glass.tres",
        '[gd_resource type="StandardMaterial3D" format=3]\n\n[resource]\ntransparency = 1\n',
    )
    result = audit.scan(tmp_path)
    assert len(result["materials"]) == 1
    assert result["materials"][0]["transparency"] == 1
    assert any(finding["category"] == "transparency" for finding in result["findings"])


def test_standalone_array_mesh_counts_surfaces_once_with_godot_primitive_modes(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "mixed_mesh.tres",
        '''[gd_resource type="ArrayMesh" load_steps=5 format=3]

[sub_resource type="StandardMaterial3D" id="Mat0"]
[sub_resource type="StandardMaterial3D" id="Mat1"]
[sub_resource type="StandardMaterial3D" id="Mat2"]
[sub_resource type="StandardMaterial3D" id="Mat3"]

[resource]
_surfaces = [{
"primitive": 3,
"vertex_count": 3,
"index_count": 60000,
"material": SubResource("Mat0"),
"lods": {}
}, {
"primitive": 3,
"vertex_count": 600,
"index_count": 0,
"material": SubResource("Mat1")
}, {
"primitive": 4,
"vertex_count": 3,
"index_count": 102,
"material": SubResource("Mat2"),
"lods": {10.0: PackedInt32Array(0, 1, 2)}
}, {
"primitive": 1,
"vertex_count": 500,
"index_count": 500,
"material": SubResource("Mat3"),
"lods": {10.0: PackedInt32Array(0, 1)}
}]
''',
    )
    result = audit.scan(tmp_path)
    assert len(result["meshes"]) == 1  # The gd_resource header is not a second mesh.
    mesh = result["meshes"][0]
    assert mesh["triangles"] == 20000 + 200 + 100  # Godot lines add no triangles.
    assert mesh["surfaces"] == 4
    assert mesh["material_count"] == 4
    assert mesh["lod"] == "missing_on_some_surfaces"
    mesh_findings = [finding for finding in result["findings"] if finding["category"] == "mesh"]
    assert len(mesh_findings) == 1
    assert "2/4 surfaces without serialized LODs" in mesh_findings[0]["evidence"]
    assert any(finding["category"] == "materials" for finding in result["findings"])


def test_scene_array_mesh_nested_lod_dictionaries_do_not_create_extra_surfaces(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "mesh_scene.tscn",
        '''[gd_scene load_steps=2 format=3]

[sub_resource type="ArrayMesh" id="Mesh"]
_surfaces = [{
"primitive": 3,
"vertex_count": 90,
"lods": {5.0: PackedInt32Array(0, 1, 2), 10.0: PackedInt32Array(0, 1, 2)},
"name": "braces { are } part of this string"
}, {
"primitive": 4,
"vertex_count": 12,
"lods": {5.0: PackedInt32Array(0, 1, 2)}
}]

[node name="Root" type="MeshInstance3D"]
mesh = SubResource("Mesh")
''',
    )
    result = audit.scan(tmp_path)
    assert len(result["meshes"]) == 1
    mesh = result["meshes"][0]
    assert mesh["name"] == "Mesh"
    assert mesh["surfaces"] == 2
    assert mesh["triangles"] == 30 + 10
    assert mesh["lod"] == "serialized_lods_unverified"


def test_scene_comments_do_not_enable_shadows(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "light.tscn",
        '[gd_scene format=3]\n[node name="Root" type="DirectionalLight3D"]\n'
        '# shadow_enabled = true\nshadow_enabled = false\n',
    )
    assert not any(finding["category"] == "light_shadows" for finding in audit.scan(tmp_path)["findings"])


def test_broken_assets_warn_without_losing_valid_results(tmp_path: Path) -> None:
    _write(tmp_path, "bad.glb", b"glTF\x02\0\0\0")
    _write(tmp_path, "bad.png", b"\x89PNG\r\n\x1a\n")
    _write(tmp_path, "good.png", _png(16, 8))
    result = audit.scan(tmp_path)
    warnings = json.dumps(result["warnings"], ensure_ascii=False)
    assert "bad.glb" in warnings
    assert "bad.png" in warnings
    assert any(texture["path"] == f"{tmp_path.name}/good.png" for texture in result["textures"])


def test_scan_is_deterministic_and_findings_are_ranked(tmp_path: Path) -> None:
    _write(tmp_path, "z.gd", 'extends Node\nfunc _process(_delta):\n    find_children("*")\n')
    _write(tmp_path, "a.gd", 'extends Node\nfunc _physics_process(_delta):\n    var values = []\n')
    first = audit.scan(tmp_path)
    assert first == audit.scan(tmp_path)
    assert first["findings"]
    scores = [finding["score"] for finding in first["findings"]]
    assert scores == sorted(scores, reverse=True)
    for finding in first["findings"]:
        assert {"category", "path", "line", "score", "evidence", "recommendation"} <= finding.keys()
        assert finding["evidence"] and finding["recommendation"]


def test_cli_writes_json_and_limits_console_ranked_results(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    game_root = tmp_path / "game"
    _write(
        game_root,
        "tick.gd",
        'extends Node\nfunc _process(_delta):\n'
        '    for child in get_children():\n        get_node("Target").visible = true\n',
    )
    destination = tmp_path / "results" / "audit.json"
    assert audit.main(["--root", str(game_root), "--json", str(destination), "--top", "1"]) == 0
    saved = json.loads(destination.read_text(encoding="utf-8"))
    output = capsys.readouterr().out.splitlines()
    assert len(saved["findings"]) >= 2
    assert len(output) == 2
    assert json.loads(output[0]) == saved["summary"]
    assert output[1].lstrip().startswith("1.")
    assert saved["findings"][0]["path"] in output[1]
    assert saved == audit.scan(game_root)
