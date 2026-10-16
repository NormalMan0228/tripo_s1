"""Offline, dependency-free Godot source audit; never imports assets or runs Godot.

Scores are review priorities, NOT milliseconds or FPS predictions. Source texture
sizes and glTF topology are measurable; residency, generated LODs, visibility,
script branch frequency and procedural instance counts are not. See JSON limits.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import re
import struct


MIB = 1024 * 1024
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
TEXT_EXTS = {".gd", ".tscn", ".tres", ".godot", ".gdshader", ".json"}
LIGHT_TYPES = {"DirectionalLight3D", "OmniLight3D", "SpotLight3D"}
PARTICLE_TYPES = {"GPUParticles3D", "CPUParticles3D", "GPUParticles2D", "CPUParticles2D"}
COMPRESS = {0: "Lossless (not GPU block compression)", 1: "Lossy (not GPU block compression)",
            2: "VRAM Compressed", 3: "VRAM Uncompressed", 4: "Basis Universal"}
LIMITS = [
    "Static review priorities, not measured FPS/ms. No Godot or network calls.",
    "RGBA8 and BC1/BC3-style 4/8 bpp estimates exclude driver padding and residency; do not sum duplicate/embedded texture budgets.",
    "Texture size suggestions (2048 maximum) are review candidates, not proof of excessive screen texel density.",
    "Importer LOD enabled is intent, not proof of generated usable LODs. Binary .res/.scn and .godot caches are not decoded.",
    "Scene counts cover serialized nodes including local instances; script constructor sites are separate, not runtime instance counts.",
    "Same-file script call graph is conservative; dynamic calls, other classes and branch/timer frequency require manual review.",
    "Inner-class methods with the same name may be connected conservatively; caller loop multiplicity is not propagated. Anonymous function bodies are excluded (including synchronous map/filter lambdas).",
    "Direct references do not prove reachability or non-use; constructed paths, class_name and downloaded/generated assets may be missing.",
    "glTF bounds are mesh-local; small-prop shadow candidates require instance scale and lighting review.",
    "Procedural shadow assignments do not prove branch coverage or final caller overrides; explicit OFF sightings are not unconditional runtime guarantees.",
    "No texture, scene, import setting or game script is modified by this tool.",
]


def read_image_size(data: bytes) -> tuple[int, int] | None:
    """Read dimensions without decompressing pixel data (PNG, JPEG, WebP, SVG)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack_from(">II", data, 16)
    if data[:2] == b"\xff\xd8":
        pos = 2
        while pos + 4 <= len(data):
            if data[pos] != 255:
                pos += 1
                continue
            while pos < len(data) and data[pos] == 255:
                pos += 1
            if pos >= len(data):
                break
            marker = data[pos]
            pos += 1
            if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
                continue
            if pos + 2 > len(data):
                break
            length = struct.unpack_from(">H", data, pos)[0]
            if length < 2 or pos + length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and length >= 7:
                height, width = struct.unpack_from(">HH", data, pos + 3)
                return width, height
            pos += length
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X" and len(data) >= 30:
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if data[12:16] == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            return struct.unpack_from("<H", data, 26)[0] & 0x3FFF, struct.unpack_from("<H", data, 28)[0] & 0x3FFF
        if data[12:16] == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if b"<svg" in data[:4096]:
        tag = re.search(r"<svg\b[^>]*>", data[:16384].decode("utf-8", errors="replace"))
        if tag:
            dims = [re.search(rf'\b{key}=[\"\']([\d.]+)(?:px)?[\"\']', tag[0]) for key in ("width", "height")]
            if all(dims):
                return tuple(math.ceil(float(m[1])) for m in dims)
            view = re.search(r'viewBox=[\"\']([\d.,\s+-]+)[\"\']', tag[0])
            if view:
                values = re.split(r"[,\s]+", view[1].strip())
                if len(values) == 4:
                    return math.ceil(float(values[2])), math.ceil(float(values[3]))
    return None


def mip_bytes(width: int, height: int, bytes_per_pixel: float = 4, mipmaps: bool = False) -> int:
    """Exact full mip chain pixel count, including NPOT/one-dimensional tails."""
    if width <= 0 or height <= 0:
        return 0
    total = 0
    while True:
        total += math.ceil(width * height * bytes_per_pixel)
        if not mipmaps or (width == 1 and height == 1):
            return total
        width, height = max(1, width // 2), max(1, height // 2)


def block_bytes(width: int, height: int, block_size: int, mipmaps: bool) -> int:
    total = 0
    while True:
        total += math.ceil(width / 4) * math.ceil(height / 4) * block_size
        if not mipmaps or (width == 1 and height == 1):
            return total
        width, height = max(1, width // 2), max(1, height // 2)


def settings(text: str) -> dict[str, str]:
    return dict(re.findall(r"^\s*([\w/]+)\s*=\s*([^\r\n]+)", text, re.M))


def clean_line(line: str, mask_strings: bool = False) -> str:
    # Keep comments/quoted examples from becoming code matches.
    result, quote, escaped = [], None, False
    for char in line:
        if quote:
            result.append(" " if mask_strings else char)
            if char == quote and not escaped:
                quote = None
            escaped = char == "\\" and not escaped
        elif char in "\"'":
            quote = char
            result.append(" " if mask_strings else char)
        elif char == "#":
            break
        else:
            result.append(char)
    return "".join(result)


def read_glb(data: bytes) -> tuple[dict, bytes]:
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError("invalid GLB header")
    _, version, length = struct.unpack_from("<4sII", data)
    if version != 2 or length != len(data):
        raise ValueError("invalid GLB version/length")
    pos, document, binary = 12, None, b""
    while pos + 8 <= length:
        size, kind = struct.unpack_from("<I4s", data, pos)
        pos += 8
        if pos + size > length:
            raise ValueError("truncated GLB chunk")
        chunk = data[pos:pos + size]
        if kind == b"JSON":
            document = json.loads(chunk)
        elif kind == b"BIN\x00":
            binary = chunk
        pos += size
    if document is None or pos != length:
        raise ValueError("missing JSON or invalid trailing GLB data")
    return document, binary


def surface_dicts(text: str) -> list[str]:
    """Extract top-level dictionaries from Godot's textual _surfaces array."""
    records, depth, start, quote, escaped = [], 0, 0, None, False
    for index, char in enumerate(text):
        if quote:
            if char == quote and not escaped:
                quote = None
            escaped = char == "\\" and not escaped
        elif char in "\"'":
            quote = char
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0:
                records.append(text[start:index + 1])
    return records


class Audit:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.files = sorted(p for p in self.root.rglob("*") if p.is_file() and not p.is_symlink()
                            and not any(part in {".godot", ".git"} for part in p.relative_to(self.root).parts))
        self.report = {key: [] for key in ("findings", "textures", "meshes", "models", "materials", "scenes", "scripts", "duplicates", "warnings")}
        self.report.update(schema_version=1, root=self.root.name, limitations=LIMITS)
        self.texts, self.refs = {}, defaultdict(list)
        self.blobs = defaultdict(list)
        for path in self.files:
            if path.suffix in TEXT_EXTS:
                try:
                    text = path.read_text(encoding="utf-8-sig")
                    self.texts[path] = text
                    for number, line in enumerate(text.splitlines(), 1):
                        line = clean_line(line) if path.suffix == ".gd" else line
                        for ref in re.findall(r'res://[^\s\"\')\]]+', line):
                            self.refs[ref].append(f"{self.rel(path)}:{number}")
                except (OSError, UnicodeError) as exc:
                    self.warn(path, str(exc))

    def rel(self, path: Path) -> str:
        return f"{self.root.name}/{path.relative_to(self.root).as_posix()}"

    def warn(self, path: Path, message: str):
        self.report["warnings"].append({"path": self.rel(path), "message": message})

    def add(self, category, path, line, score, evidence, recommendation, **extra):
        self.report["findings"].append(dict(category=category, path=self.rel(path), line=line,
                                            score=round(score, 2), evidence=evidence,
                                            recommendation=recommendation, **extra))

    def importer(self, path: Path) -> tuple[dict, str]:
        sidecar = Path(str(path) + ".import")
        if not sidecar.exists():
            return {}, ""
        text = sidecar.read_text(encoding="utf-8-sig")
        return settings(text), text

    def texture(self, path, data, *, label=None, imported=None):
        dims = read_image_size(data)
        if not dims or min(dims) < 1:
            self.warn(path, f"image dimensions unavailable: {label or path.name}")
            return
        params, _ = self.importer(path) if imported is None else (imported, "")
        width, height = dims
        size_limit = int(params.get("process/size_limit", "0"))
        svg_scale = float(params.get("svg/scale", "1")) if path.suffix == ".svg" else 1
        width, height = max(1, round(width * svg_scale)), max(1, round(height * svg_scale))
        if size_limit > 0 and max(width, height) > size_limit:
            ratio = size_limit / max(width, height)
            width, height = max(1, round(width * ratio)), max(1, round(height * ratio))
        mip = params.get("mipmaps/generate") == "true"
        mode = int(params["compress/mode"]) if "compress/mode" in params else None
        rgba = mip_bytes(width, height, mipmaps=mip)
        record = dict(path=label or self.rel(path), source_width=dims[0], source_height=dims[1],
                      width=width, height=height, size_limit=size_limit, mipmaps=mip if params else None,
                      mip_limit=params.get("mipmaps/limit", "unknown"), compression_mode=mode,
                      compression=COMPRESS.get(mode, "unknown: no texture importer settings"),
                      rgba8_bytes=rgba, block_4bpp_bytes=block_bytes(width, height, 8, mip),
                      block_8bpp_bytes=block_bytes(width, height, 16, mip),
                      direct_references=self.refs.get("res://" + path.relative_to(self.root).as_posix(), []))
        self.report["textures"].append(record)
        reasons = []
        if max(width, height) > 2048:
            reasons.append(f"{width}x{height}; review 2048-pixel maximum against actual screen use")
        if rgba >= 4 * MIB and mode in {0, 1, 3}:
            reasons.append(f"{rgba / MIB:.2f} MiB RGBA8 estimate, compression mode {mode} is not GPU block compression")
        if not mip and params and max(width, height) >= 1024:
            reasons.append("mipmaps disabled (valid for UI; review only if minified in 3D)")
        if reasons:
            target = 2048 if max(width, height) > 2048 else max(width, height)
            recommendation = (f"{self.rel(path)}.import: review process/size_limit={target}; for 3D textures set compress/mode=2 and mipmaps/generate=true, then reimport. Preserve UI readability and normal-map channels."
                              if label is None else f"{label}: locate the extracted/shared image importer first, then review a {target}-pixel cap and GPU compression there. Do not add this estimate to extracted texture VRAM.")
            self.add("texture", path, 1, min(95, 25 + rgba / MIB) * (0.5 if label else 1), "; ".join(reasons), recommendation,
                     texture=record["path"], estimated_rgba8_mib=round(rgba / MIB, 3), confidence="candidate")

    def gltf(self, path: Path, doc: dict, binary: bytes):
        params, import_text = self.importer(path)
        accessors = doc.get("accessors", [])
        mats = doc.get("materials", [])
        global_lod = params.get("meshes/generate_lods")
        overrides = bool(re.search(r'[\"\']generate/lods[\"\']\s*:', import_text))
        has_lod = any("MSFT_lod" in n.get("extensions", {}) for n in doc.get("nodes", []))
        lod = "source_extension" if has_lod else ("import_enabled_unverified" if global_lod == "true" else "disabled" if global_lod == "false" else "unknown")
        if overrides:
            lod = "per_mesh_overrides_review"
        model_triangles, model_surfaces = 0, 0
        for index, mesh in enumerate(doc.get("meshes", [])):
            triangles, slots, bounds = 0, set(), []
            for primitive in mesh.get("primitives", []):
                accessor = primitive.get("indices", primitive.get("attributes", {}).get("POSITION"))
                count = int(accessors[accessor]["count"]) if accessor is not None else 0
                mode = primitive.get("mode", 4)
                triangles += count // 3 if mode == 4 else max(0, count - 2) if mode in {5, 6} else 0
                slots.add(primitive.get("material", -1))
                position = primitive.get("attributes", {}).get("POSITION")
                if position is not None:
                    a = accessors[position]
                    if "min" in a and "max" in a:
                        bounds.append((a["min"], a["max"]))
            extent = max((max(b[1][axis] for b in bounds) - min(b[0][axis] for b in bounds) for axis in range(3)), default=None) if bounds else None
            transparent = [slot for slot in sorted(slots) if slot >= 0 and mats[slot].get("alphaMode", "OPAQUE") == "BLEND"]
            surfaces = len(mesh.get("primitives", []))
            model_triangles += triangles
            model_surfaces += surfaces
            record = dict(path=self.rel(path), mesh=index, name=mesh.get("name", str(index)), triangles=triangles,
                          surfaces=surfaces, material_count=len(slots), material_slots=sorted(slots),
                          transparent_materials=transparent, lod=lod, local_max_extent=extent)
            self.report["meshes"].append(record)
            name = f"mesh[{index}] {record['name']}"
            if triangles >= 20000:
                self.add("mesh", path, 1, min(98, 35 + triangles / 4000 + (20 if lod == "disabled" else 0)),
                         f"{name}: {triangles:,} triangles; LOD={lod}",
                         f"{name}: {'set meshes/generate_lods=true in .import; ' if lod == 'disabled' else ''}inspect generated LODs; target distant LOD at <=25% base triangles, preserve silhouette/skinning.", mesh=index, confidence="measured topology; LOD intent only")
            if surfaces >= 4:
                self.add("materials", path, 1, min(90, 30 + surfaces * 2),
                         f"{name}: {surfaces} surfaces, {len(slots)} material slots; separate surfaces can add draw submissions",
                         f"{name}: merge compatible opaque surfaces and atlas shared textures; aim <=4 visible surfaces per distant instance; preserve transparent sorting.", mesh=index)
            if transparent:
                self.add("transparency", path, 1, min(85, 25 + len(transparent) * 5 + triangles / 10000),
                         f"{name}: BLEND materials {transparent}; overdraw depends on projected coverage",
                         f"{name}: inspect material slots {transparent}; use OPAQUE for opaque pixels or MASK only for binary alpha; retain BLEND for glass/fades.", mesh=index)
            if extent is not None and extent <= 0.5 and triangles > 500:
                self.add("small_prop_shadow", path, 1, 20 + min(20, triangles / 2000),
                         f"{name}: local extent {extent:.3f}; imported MeshInstance3D shadow defaults need instance review",
                         f"{name}: if world extent <=0.5 m and shadow is visually dispensable, set its instance cast_shadow=0 (SHADOW_CASTING_SETTING_OFF); do not change global shadows.", mesh=index, confidence="candidate; scale/runtime overrides unknown")
        refs = self.refs.get("res://" + path.relative_to(self.root).as_posix(), [])
        self.report["models"].append(dict(path=self.rel(path), triangles=model_triangles,
                                          surfaces=model_surfaces, mesh_count=len(doc.get("meshes", [])),
                                          lod=lod, direct_references=refs))
        if model_triangles >= 20000 or model_surfaces >= 6:
            self.add("model_budget", path, 1, min(90, 25 + model_triangles / 4000 + model_surfaces * 2),
                     f"model total: {model_triangles:,} triangles, {model_surfaces} surfaces; LOD={lod}; {len(refs)} direct source references (not a use count)",
                     f"{self.rel(path)}: verify active use before optimizing; inspect generated LODs and consolidate compatible surfaces for distant instances. Import LOD enablement alone does not verify LOD quality.")
        for index, mat in enumerate(mats):
            self.report["materials"].append(dict(path=self.rel(path), material=index, name=mat.get("name", str(index)),
                                                  alpha_mode=mat.get("alphaMode", "OPAQUE"), double_sided=mat.get("doubleSided", False)))
        for index, item in enumerate(doc.get("images", [])):
            if "bufferView" in item:
                view = doc["bufferViews"][item["bufferView"]]
                if view.get("buffer", 0) != 0:
                    self.warn(path, f"image[{index}] external buffer not read")
                    continue
                start = view.get("byteOffset", 0)
                data = binary[start:start + view["byteLength"]]
                label = f"{self.rel(path)}#image[{index}]"
                self.texture(path, data, label=label, imported={})
                self.remember_blob(label, data)
            elif "uri" in item:
                self.report.setdefault("external_gltf_images", []).append(dict(path=self.rel(path), image=index, uri=item["uri"]))

    def remember_blob(self, label: str, data: bytes):
        if len(data) >= 256 * 1024:
            self.blobs[(len(data), hashlib.sha256(data).hexdigest())].append(label)

    def script(self, path, text):
        lines = text.splitlines()
        functions, current = {}, None
        for number, raw in enumerate(lines, 1):
            line = clean_line(raw)
            match = re.match(r"(\s*)(?:static\s+)?func\s+(\w+)\s*\(", line)
            if match:
                # Key by source line to retain inner classes with duplicate method names.
                current = dict(name=match[2], line=number, indent=len(match[1].expandtabs(4)), body=[])
                functions[number] = current
                inline = re.search(r"\)\s*(?:->\s*[\w\[\]]+)?\s*:\s*(.+)$", line)
                if inline:
                    current["body"].append((number, inline[1], current["indent"] + 4))
            elif current and line.strip():
                indent = len(line) - len(line.lstrip())
                indent = len(line[:indent].expandtabs(4))
                if indent <= current["indent"]:
                    current = None
                else:
                    current["body"].append((number, line, indent))
        for fn in functions.values():
            immediate, lambda_indent = [], None
            for number, line, indent in fn["body"]:
                if lambda_indent is not None:
                    if indent > lambda_indent:
                        continue
                    lambda_indent = None
                deferred = re.search(r"\bfunc\s*\(", clean_line(line, True))
                if deferred:
                    lambda_indent = indent
                    line = line[:deferred.start()]
                immediate.append((number, line, indent))
            fn["body"] = immediate
        by_name = defaultdict(list)
        for key, fn in functions.items():
            by_name[fn["name"]].append(key)
        roots = {key for key, fn in functions.items() if fn["name"] in {"_process", "_physics_process", "_process_modification_with_delta"}}
        reached, todo = set(roots), deque(sorted(roots))
        depth = {key: 0 for key in roots}
        while todo:
            key = todo.popleft()
            body = "\n".join(clean_line(line, True) for _, line, _ in functions[key]["body"])
            for call in re.findall(r"(?<![\w.])(?:self\.)?(\w+)\s*\(", body):
                for target in by_name.get(call, []):
                    if target not in reached:
                        reached.add(target)
                        depth[target] = depth[key] + 1
                        todo.append(target)
        constructors = []
        for number, raw in enumerate(lines, 1):
            code = clean_line(raw, True)
            for kind in sorted(LIGHT_TYPES | PARTICLE_TYPES):
                if re.search(rf"\b{kind}\.new\s*\(", code):
                    constructors.append(dict(line=number, type=kind))
            if re.search(r"\.transparency\s*=.*TRANSPARENCY_ALPHA\b", code):
                self.add("transparency", path, number, 20, clean_line(raw).strip(),
                         "Review this material's projected coverage; retain required fades/glass, use opaque or alpha scissor only where appearance is equivalent.", confidence="script assignment; runtime use unknown")
        self.report["scripts"].append(dict(path=self.rel(path), frame_functions=len(roots),
                                            reachable_functions=len(reached), constructor_sites=constructors))
        for key in sorted(reached):
            fn, loops = functions[key], []
            for number, line, indent in fn["body"]:
                while loops and indent <= loops[-1]:
                    loops.pop()
                code = clean_line(line, True)
                if re.match(r"\s*(for|while)\b", code):
                    loops.append(indent)
                rules = []
                if re.search(r"\b(find_children|find_child|get_children)\s*\(", code):
                    rules.append(("tree_search", 65, "Cache node lists with explicit add/remove invalidation; avoid rebuilding them in frame paths."))
                if re.search(r"\bget_node(?:_or_null)?\s*\(|\$", code):
                    rules.append(("node_lookup", 40, "Cache stable nodes after creation/@onready; invalidate on replacement or free."))
                if re.search(r"\bawait\b", code):
                    rules.append(("await", 60, "Check re-entry: start one coroutine from an event or guard pending work; preserve timing."))
                if re.search(r"(?:=|,|\(|\bin\b|\breturn\b)\s*[\[{]|\b(?:Array|Dictionary|Packed\w+Array)\s*\(|\.(?:keys|values|duplicate|filter|map)\s*\(", code):
                    rules.append(("allocation", 35, "Hoist immutable arrays/dictionaries or reuse scratch storage only if values/ownership remain identical."))
                if re.search(r"\b(?:str|String|StringName)\s*\(|\.(?:format|join)\s*\(", code) or re.search(r'[\"\'][^\n]*[\"\']\s*[%+]', line):
                    rules.append(("string_build", 25, "Cache stable strings and update UI text only when its value changes; retain localization/settings invalidation."))
                if re.search(r"\b(?:load|instantiate|intersect_ray|intersect_shape)\s*\(|\.new\s*\(", code):
                    rules.append(("heavy_call", 55, "Review frequency and gating; cache resources or reuse queries where lifetime permits."))
                for kind, base, recommendation in rules:
                    score = max(1, base + (15 if loops else 0) - min(30, depth[key] * 10))
                    if "/tests/" in self.rel(path):
                        score *= .25
                    self.add("script_" + kind, path, number, score,
                             f"{fn['name']} ({'callback' if key in roots else 'same-file reachable helper'}, {'loop' if loops else 'no local loop'}): {line.strip()}",
                             recommendation, function=fn["name"], in_loop=bool(loops), call_depth=depth[key],
                             confidence="syntactic candidate; guards and call frequency require review")

        # A constructor site may run in a loop or a factory many times. Report
        # those sites separately from serialized scene instance counts.
        for fn in functions.values():
            body = "\n".join(line for _, line, _ in fn["body"])
            for number, line, _ in fn["body"]:
                match = re.search(r"\b(\w+)\s*(?::=|=)\s*(MeshInstance3D|CPUParticles3D|GPUParticles3D)\.new\(", clean_line(line, True))
                if not match:
                    continue
                var, kind = match.groups()
                shadow = re.findall(rf"\b{var}\.cast_shadow\s*=\s*([^;\n]+)", body)
                disabled = shadow and all(v.strip().split(".")[-1] in {"SHADOW_CASTING_SETTING_OFF", "0"} for v in shadow)
                if kind in PARTICLE_TYPES:
                    amount = re.findall(rf"\b{var}\.amount\s*=\s*([^;\n]+)", body)
                    self.add("particles", path, number, 35 if not disabled else 20,
                             f"{fn['name']}: {var} {kind}, amount={amount or ['engine default']}, shadow={'OFF assignment found; branch coverage unverified' if disabled else 'default/conditional; review'}; constructor site only",
                             f"{var}: review amount against particle quality, stop emission when invisible; " + ("retain existing shadow OFF." if disabled else "set cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if no visible particle shadow is required."), confidence="procedural candidate")
                elif not disabled:
                    self.add("prop_shadow_review", path, number, 12,
                             f"{fn['name']}: {var} MeshInstance3D has no detected OFF-only assignments in its function; world size and control flow require review",
                             f"Inspect {var}'s mesh and instance extent; only if a small decorative prop has a dispensable shadow, set cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF. Keep structural/character shadows.", confidence="low: size, aliases and callers require review")

    def shader(self, path, text):
        for number, raw in enumerate(text.splitlines(), 1):
            line = raw.split("//", 1)[0]
            match = re.search(r"\bALPHA\s*=\s*([^;]+)", line)
            if match:
                constant = match[1].strip() in {"1", "1.0"}
                self.add("shader_alpha", path, number, 45 if constant else 25,
                         f"ALPHA assignment: {match[1]}; {'constant opaque value may still select transparency' if constant else 'alpha overdraw depends on coverage'}",
                         "If all shader paths are opaque, remove the ALPHA write and visually verify sorting/lighting; preserve alpha for intentional edges, glass or fading." if constant else "Inspect projected overdraw and layer count; retain intentional alpha, review alpha-scissor only for binary cutouts.")

    def scene(self, path, text):
        text = "\n".join(clean_line(line) for line in text.splitlines())
        sections = list(re.finditer(r"^\[([^\n]+)\]\s*$", text, re.M))
        counts = Counter()
        ext = {}
        instances, materials = [], []
        resource_type = ""
        for index, section in enumerate(sections):
            header = section[1]
            body = text[section.end():sections[index + 1].start() if index + 1 < len(sections) else len(text)]
            line = text.count("\n", 0, section.start()) + 1
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', header))
            kind = attrs.get("type", "")
            if header.startswith("gd_resource"):
                resource_type = kind
            if header == "resource":
                kind = resource_type
            if header.startswith("ext_resource"):
                ext[attrs.get("id")] = attrs.get("path", "")
            if header.startswith("node"):
                counts[kind or "instanced"] += 1
                match = re.search(r'instance=ExtResource\("([^\"]+)"\)', header)
                if match:
                    instances.append(ext.get(match[1], ""))
                if kind in LIGHT_TYPES and re.search(r"shadow_enabled\s*=\s*true", body):
                    self.add("light_shadows", path, line, 45, f"{attrs.get('name')}: {kind} with shadows",
                             f"Node {attrs.get('name')}: review shadow_enabled=false for fill/decorative light; retain key light shadows.")
                if kind in PARTICLE_TYPES:
                    amount = re.search(r"^amount\s*=\s*(\d+)", body, re.M)
                    self.add("particles", path, line, 25, f"{attrs.get('name')}: {kind}, amount={amount[1] if amount else 'default'}",
                             f"Node {attrs.get('name')}: review emission visibility/distance and reduce amount only after visual comparison.")
            if header.startswith(("sub_resource", "resource")) and kind in {"StandardMaterial3D", "ORMMaterial3D"}:
                params = settings(body)
                record = dict(path=self.rel(path), line=line, material=attrs.get("id"), transparency=int(params.get("transparency", "0")))
                materials.append(record)
                if record["transparency"]:
                    self.add("transparency", path, line, 30, f"material {record['material']}: transparency={record['transparency']}",
                             "Set transparency=0 only for opaque content; review alpha-scissor for binary cutouts; keep glass/fades.")
            if kind == "ArrayMesh" and header.startswith(("sub_resource", "resource")):
                surfaces = [s for s in surface_dicts(body) if '"vertex_count"' in s or '"index_count"' in s]
                triangles, no_lod, slots = 0, 0, set()
                for surface in surfaces:
                    values = dict(re.findall(r'"(index_count|vertex_count|primitive)"\s*:\s*(\d+)', surface))
                    count = int(values.get("index_count", "0")) or int(values.get("vertex_count", "0"))
                    # Godot Mesh primitive enums differ from glTF: triangles=3,
                    # triangle strip=4; points/lines must contribute no triangles.
                    mode = int(values.get("primitive", "3"))
                    triangles += count // 3 if mode == 3 else max(0, count - 2) if mode == 4 else 0
                    no_lod += int('"lods"' not in surface or bool(re.search(r'"lods"\s*:\s*(?:\{\s*\}|\[\s*\])', surface)))
                    material = re.search(r'"material"\s*:\s*((?:SubResource|ExtResource)\("[^"]+"\))', surface)
                    slots.add(material[1] if material else "default")
                record = dict(path=self.rel(path), line=line, name=attrs.get("id", "resource"),
                              triangles=triangles if surfaces else None, surfaces=len(surfaces), material_count=len(slots),
                              lod="missing_on_some_surfaces" if no_lod else "serialized_lods_unverified" if surfaces else "unknown")
                self.report["meshes"].append(record)
                if triangles >= 20000:
                    self.add("mesh", path, line, min(98, 35 + triangles / 4000 + (20 if no_lod else 0)),
                             f"{record['name']}: {triangles:,} triangles, {no_lod}/{len(surfaces)} surfaces without serialized LODs",
                             "Generate LODs from the source mesh and resave this resource; verify distant silhouette and material assignments before replacing it.")
                if len(surfaces) >= 4:
                    self.add("materials", path, line, min(90, 30 + len(surfaces) * 2),
                             f"{record['name']}: {len(surfaces)} serialized surfaces, {len(slots)} material references",
                             "Merge compatible surfaces sharing a material; preserve transparency ordering and overrides.")
        self.report["materials"].extend(materials)
        if path.suffix == ".tscn":
            self.report["scenes"].append(dict(path=self.rel(path), local_node_counts=dict(sorted(counts.items())),
                local_lights=sum(counts[k] for k in LIGHT_TYPES), local_particles=sum(counts[k] for k in PARTICLE_TYPES),
                scene_instances=instances))

    def finish_scenes(self):
        scenes = {"res://" + s["path"].split("/", 1)[1]: s for s in self.report["scenes"]}
        script_sites = {s["path"]: s["constructor_sites"] for s in self.report["scripts"]}
        def total(ref, seen):
            if ref in seen or ref not in scenes:
                return 0, 0
            item = scenes[ref]
            lights, particles = item["local_lights"], item["local_particles"]
            for child in item["scene_instances"]:
                a, b = total(child, seen | {ref})
                lights, particles = lights + a, particles + b
            return lights, particles
        for ref, scene in scenes.items():
            scene["serialized_lights"], scene["serialized_particles"] = total(ref, set())
            seen, todo = set(), [self.root / ref[6:]]
            sites = []
            while todo:
                path = todo.pop()
                if path in seen:
                    continue
                seen.add(path)
                sites.extend(dict(path=self.rel(path), **site) for site in script_sites.get(self.rel(path), []))
                text = self.texts.get(path, "")
                for target in re.findall(r'res://[^\s\"\')\]]+', text):
                    resolved = self.root / target[6:]
                    if resolved in self.texts:
                        todo.append(resolved)
            scene["reachable_script_constructor_sites"] = sorted(sites, key=lambda x: (x["path"], x["line"], x["type"]))
            self.add("scene_budget", self.root / ref[6:], 1,
                     min(85, 10 + scene["serialized_lights"] * 3 + scene["serialized_particles"] * 3 + len(sites)),
                     f"serialized lights={scene['serialized_lights']}, particles={scene['serialized_particles']}; {len(sites)} reachable constructor sites (NOT instance counts)",
                     "Count live instances per active scene with the existing performance overlay; inspect listed constructor sites for loop multiplicity, visibility and distance gating.")

    def run(self):
        suffixes = Counter(p.suffix.lower() for p in self.files)
        binary_resources = []
        for path in self.files:
            try:
                suffix = path.suffix.lower()
                if path.stat().st_size >= 256 * 1024 and suffix != ".import":
                    self.remember_blob(self.rel(path), path.read_bytes())
                if suffix in IMAGE_EXTS:
                    self.texture(path, path.read_bytes())
                elif suffix == ".glb":
                    self.gltf(path, *read_glb(path.read_bytes()))
                elif suffix == ".gltf":
                    self.gltf(path, json.loads(path.read_text(encoding="utf-8")), b"")
                elif suffix == ".gd":
                    self.script(path, self.texts.get(path, ""))
                elif suffix == ".gdshader":
                    self.shader(path, self.texts.get(path, ""))
                elif suffix in {".tscn", ".tres"}:
                    self.scene(path, self.texts.get(path, ""))
                elif suffix in {".res", ".scn"}:
                    binary_resources.append(self.rel(path))
            except (OSError, ValueError, KeyError, IndexError, TypeError, struct.error) as exc:
                self.warn(path, f"{type(exc).__name__}: {exc}")
        self.finish_scenes()
        for (size, digest), paths in sorted(self.blobs.items(), key=lambda pair: (-pair[0][0] * (len(pair[1]) - 1), pair[1])):
            if len(paths) < 2:
                continue
            record = dict(paths=paths, bytes_each=size, redundant_source_bytes=size * (len(paths) - 1), sha256=digest)
            self.report["duplicates"].append(record)
            path = self.root / paths[0].split("/", 1)[1].split("#", 1)[0]
            self.add("duplicate", path, 1, min(80, 15 + record["redundant_source_bytes"] / MIB * 3),
                     f"{len(paths)} byte-identical blobs, {record['redundant_source_bytes'] / MIB:.2f} MiB redundant source storage: {', '.join(paths)}",
                     "Consolidate references to one canonical resource only after verifying importer settings/normal-vs-color usage; embedded+extracted copies do not prove duplicate runtime VRAM.", duplicate_paths=paths)
        missing = sorted(ref for ref in self.refs if not (self.root / ref[6:]).exists() and "/.godot/" not in ref)
        self.report["coverage"] = dict(files=len(self.files), extensions=dict(sorted(suffixes.items())),
                                       opaque_binary_resources=binary_resources, missing_literal_references=missing)
        self.report["findings"].sort(key=lambda f: (-f["score"], f["path"], f["line"], f["category"]))
        for rank, finding in enumerate(self.report["findings"], 1):
            finding["rank"] = rank
        self.report["summary"] = dict(findings=len(self.report["findings"]), categories=dict(sorted(Counter(f["category"] for f in self.report["findings"]).items())),
                                      textures=len(self.report["textures"]), meshes=len(self.report["meshes"]), scenes=len(self.report["scenes"]),
                                      duplicate_groups=len(self.report["duplicates"]), warnings=len(self.report["warnings"]))
        return self.report


def scan(game_root: Path) -> dict:
    root = Path(game_root)
    if not root.is_dir():
        raise ValueError(f"Game root is not a directory: {root}")
    return Audit(root).run()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2] / "game")
    parser.add_argument("--json", type=Path, help="Write complete deterministic inventory and ranked findings")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    report = scan(args.root)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=True))
    for finding in report["findings"][:max(0, args.top)]:
        print(f"{finding['rank']:3}. [{finding['score']:5.1f}] {finding['category']} {finding['path']}:{finding['line']} {finding['evidence']}".encode("ascii", errors="backslashreplace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
