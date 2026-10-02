"""Create our own untextured stool fixture, without services or third-party assets."""
import json
import struct
from pathlib import Path

vertices, normals, indices = [], [], []
faces = [
    ((1, 0, 0), [(0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5)]),
    ((-1, 0, 0), [(-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5)]),
    ((0, 1, 0), [(-0.5, 0.5, -0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5)]),
    ((0, -1, 0), [(-0.5, -0.5, 0.5), (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5)]),
    ((0, 0, 1), [(-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]),
    ((0, 0, -1), [(0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5)]),
]
for normal, points in faces:
    start = len(vertices)
    vertices.extend(points)
    normals.extend([normal] * 4)
    indices.extend(start + i for i in (0, 1, 2, 0, 2, 3))
positions = b''.join(struct.pack('<3f', *p) for p in vertices)
normal_bytes = b''.join(struct.pack('<3f', *p) for p in normals)
index_bytes = struct.pack('<36H', *indices)
binary = positions + normal_bytes + index_bytes
nodes = [{'name': 'Stool', 'children': list(range(1, 6))},
         {'name': 'Seat', 'mesh': 0, 'translation': [0, 1.0, 0], 'scale': [1.3, 0.2, 1.3]}]
for x, z in ((-0.45, -0.45), (0.45, -0.45), (-0.45, 0.45), (0.45, 0.45)):
    nodes.append({'name': 'Leg', 'mesh': 0, 'translation': [x, 0.45, z], 'scale': [0.18, 0.9, 0.18]})
gltf = {
    'asset': {'version': '2.0', 'generator': 'Tripothon local sample builder'},
    'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': nodes,
    'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1}, 'indices': 2}]}],
    'buffers': [{'byteLength': len(binary)}],
    'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(positions), 'target': 34962},
                    {'buffer': 0, 'byteOffset': len(positions), 'byteLength': len(normal_bytes), 'target': 34962},
                    {'buffer': 0, 'byteOffset': len(positions) + len(normal_bytes), 'byteLength': len(index_bytes), 'target': 34963}],
    'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 24, 'type': 'VEC3', 'min': [-0.5] * 3, 'max': [0.5] * 3},
                  {'bufferView': 1, 'componentType': 5126, 'count': 24, 'type': 'VEC3'},
                  {'bufferView': 2, 'componentType': 5123, 'count': 36, 'type': 'SCALAR'}],
}
encoded = json.dumps(gltf, separators=(',', ':')).encode()
encoded += b' ' * (-len(encoded) % 4)
binary += b'\0' * (-len(binary) % 4)
output = struct.pack('<III', 0x46546C67, 2, 28 + len(encoded) + len(binary))
output += struct.pack('<II', len(encoded), 0x4E4F534A) + encoded
output += struct.pack('<II', len(binary), 0x004E4942) + binary
path = Path(__file__).resolve().parents[1] / 'game' / 'assets' / 'sample_stool.glb'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(output)
print(f'Created sample_stool.glb ({len(output)} bytes)')
