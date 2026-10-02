"""Validate local furniture exports without contacting Tripo."""
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.provider import validate_glb

folder = ROOT / "artifacts/furniture/paint-test-01"
report_path = folder / "test-results.json"
report = json.loads(report_path.read_text(encoding="utf-8-sig"))
for name in ("chair", "table", "bookshelf"):
    for kind in ("original", "paintable"):
        data = (folder / f"{name}-{kind}.glb").read_bytes()
        doc = validate_glb(data)
        json_size = struct.unpack_from("<I", data, 12)[0]
        binary = data[28 + json_size:]

        def accessor(index):
            acc = doc["accessors"][index]
            view = doc["bufferViews"][acc["bufferView"]]
            fmt = "<" + {5126: "f", 5125: "I", 5123: "H", 5121: "B"}[acc["componentType"]] * {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[acc["type"]]
            start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
            stride = view.get("byteStride", struct.calcsize(fmt))
            return [struct.unpack_from(fmt, binary, start + i * stride) for i in range(acc["count"])]

        triangles = uv_count = valid = 0
        for mesh in doc["meshes"]:
            for primitive in mesh["primitives"]:
                uv = accessor(primitive["attributes"]["TEXCOORD_0"])
                assert all(math.isfinite(v) for pair in uv for v in pair)
                indices = [v[0] for v in accessor(primitive["indices"])]
                uv_count += len(uv)
                for i in range(0, len(indices), 3):
                    a, b, c = [uv[j] for j in indices[i:i + 3]]
                    area = abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])) / 2
                    valid += area > 1e-12
                    triangles += 1
        assert valid == triangles
        assert not doc.get("images")
        report["items"][name][kind] = {
            "server_static_glb_validator": "passed", "bytes": len(data),
            "triangles": triangles, "uv_entries": uv_count, "finite_uv": True,
            "nondegenerate_uv_triangle_ratio": valid / triangles, "embedded_images": 0,
        }
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("PASS: six GLBs; server validator; finite and nondegenerate UVs; no embedded textures")
