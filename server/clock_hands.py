"""Clock hands (and a pendulum) the game makes itself: small procedural meshes, no Tripo credits.

Each hand is built from a few convex pieces, extruded with a bevelled front: a spade tip (hour),
an arrow tip (minute), a thin needle with a counterweight (second), a rod and bob (pendulum), and
a hub cap standing proud at the turning point. The mesh fills the part's design box exactly, so
the game's box fit keeps it undistorted, with the hub where the plan's pivot is. Colours follow
the craft style and stand out against the dial (dial_colour samples the body's texture).
"""
import io
import json
import math
import struct
from .asset_assembly import mesh_glb

# Per craft style (server/craft_styles.py): hands for a light dial, hands for a dark dial, the second
# hand's accent, the pendulum's metal; glow: the accent glows (an 'always' glow preset added by
# server/archetypes.py).
PALETTES = {
    'rpg': {'dark': '#2a2522', 'light': '#d9c08a', 'accent': '#9c2f22', 'metal': '#b8893c'},
    'cozy': {'dark': '#5a3b26', 'light': '#f3e6c8', 'accent': '#d9644a', 'metal': '#c9a46e'},
    'realistic': {'dark': '#18181a', 'light': '#e8e8e8', 'accent': '#c0392b', 'metal': '#9aa0a6'},
    'anime': {'dark': '#24304a', 'light': '#fff6e0', 'accent': '#ff5a5f', 'metal': '#ffcf4a'},
    'antique': {'dark': '#2b2622', 'light': '#c9a55c', 'accent': '#b08d57', 'metal': '#b08d57'},
    'hanok': {'dark': '#1e1a17', 'light': '#d8b46a', 'accent': '#b8924a', 'metal': '#b8924a'},
    'scifi': {'dark': '#3a4048', 'light': '#e6eef5', 'accent': '#42d9ff', 'metal': '#7f8a96', 'glow': True},
}
DEFAULT = 'rpg'
SEGMENTS = 20


def palette(style):
    return PALETTES.get(style, PALETTES[DEFAULT])


def rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hexed(colour):
    return '#' + ''.join('%02x' % max(0, min(255, round(c * 255))) for c in colour)


def luminance(colour):
    def linear(c):
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in colour)
    return .2126 * r + .7152 * g + .0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + .05) / (lb + .05)


def colours(style, dial):
    """{'hour', 'minute', 'second', 'pendulum': '#rrggbb'} for this style on a dial of this colour
    (r, g, b in 0..1): the hand colour that stands out more, and the accent unless it would vanish."""
    pal = palette(style)
    main = max((pal['dark'], pal['light']), key=lambda c: contrast(rgb(c), dial))
    # A glowing accent shows on any dial.
    accent = pal['accent'] if pal.get('glow') or contrast(rgb(pal['accent']), dial) >= 2.2 else main
    return {'hour': main, 'minute': main, 'second': accent, 'pendulum': pal['metal']}


def dial_colour(blob, fallback):
    """The average colour of a model's base-colour texture (a Tripo body), or the plan colour."""
    try:
        from PIL import Image, ImageStat
        if blob[:4] != b'glTF':
            return rgb(fallback)
        size = struct.unpack_from('<I', blob, 12)[0]
        doc = json.loads(blob[20:20 + size])
        binary = blob[20 + size + 8:]
        material = (doc.get('materials') or [{}])[0].get('pbrMetallicRoughness', {})
        factor = material.get('baseColorFactor', [1, 1, 1, 1])[:3]
        texture = material.get('baseColorTexture')
        if texture is None:
            return tuple(factor) if doc.get('materials') else rgb(fallback)
        image = doc['images'][doc['textures'][texture['index']]['source']]
        view = doc['bufferViews'][image['bufferView']]
        start = view.get('byteOffset', 0)
        with Image.open(io.BytesIO(binary[start:start + view['byteLength']])) as picture:
            # A whole-atlas average: close enough to the dial for choosing light or dark hands.
            mean = [m / 255 for m in ImageStat.Stat(picture.convert('RGB').resize((32, 32))).mean]
        return tuple(m * f for m, f in zip(mean, factor))
    except Exception:
        return rgb(fallback)


# ---------------------------------------------------------------- geometry

def circle(cx, cy, r, segments=SEGMENTS):
    return [(cx + r * math.cos(2 * math.pi * i / segments), cy + r * math.sin(2 * math.pi * i / segments)) for i in range(segments)]


def inset(polygon, amount):
    """A convex counter-clockwise polygon moved inward by amount (edge offset)."""
    n = len(polygon)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = polygon[i], polygon[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length  # inward for counter-clockwise
        lines.append(((x0 + nx * amount, y0 + ny * amount), (dx, dy)))
    out = []
    for i in range(n):
        (p, d), (q, e) = lines[i - 1], lines[i]
        cross = d[0] * e[1] - d[1] * e[0]
        if abs(cross) < 1e-12:
            out.append(q)
            continue
        t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / cross
        out.append((p[0] + d[0] * t, p[1] + d[1] * t))
    return out


def width(polygon):
    """Smallest extent across the polygon (for a bevel that fits)."""
    best = float('inf')
    n = len(polygon)
    for i in range(n):
        (x0, y0), (x1, y1) = polygon[i], polygon[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length
        best = min(best, max((x - x0) * nx + (y - y0) * ny for x, y in polygon))
    return best


def ccw(polygon):
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]))
    return polygon if area > 0 else polygon[::-1]


class Mesh:
    def __init__(self):
        self.vertices, self.normals, self.indices = [], [], []

    def face(self, points, normal):
        start = len(self.vertices)
        self.vertices.extend(points)
        self.normals.extend([normal] * len(points))
        for i in range(1, len(points) - 1):
            self.indices.extend((start, start + i, start + i + 1))

    def piece(self, polygon, back, front):
        """A convex prism from z=back to z=front with a bevelled front edge."""
        polygon = ccw(polygon)
        depth = front - back
        bevel = min(depth * .35, width(polygon) * .22)
        top = inset(polygon, bevel)
        shoulder = front - bevel
        self.face([(x, y, back) for x, y in polygon[::-1]], (0, 0, -1))
        self.face([(x, y, front) for x, y in top], (0, 0, 1))
        n = len(polygon)
        for i in range(n):
            j = (i + 1) % n
            (x0, y0), (x1, y1) = polygon[i], polygon[j]
            dx, dy = x1 - x0, y1 - y0
            length = math.hypot(dx, dy) or 1
            side = (dy / length, -dx / length, 0)
            self.face([(x0, y0, back), (x1, y1, back), (x1, y1, shoulder), (x0, y0, shoulder)], side)
            (u0, v0), (u1, v1) = top[i], top[j]
            # Inset as far as it drops: a 45 degree chamfer.
            self.face([(x0, y0, shoulder), (x1, y1, shoulder), (u1, v1, front), (u0, v0, front)], (side[0] * .7071, side[1] * .7071, .7071))


def hand_mesh(make, size, pivot):
    """(vertices, normals, indices) of a hand filling the box `size` (x width, y length, z depth),
    centred on the origin, turning at pivot (normalised box offsets, like the plan's)."""
    w, length, depth = size
    half_w, half_l, back = w / 2, length / 2, -depth / 2
    cx, cy = pivot[0] * w, pivot[1] * length
    mesh = Mesh()
    blade = back + depth * .55  # the blade sits low; the hub cap stands proud of it
    if make == 'pendulum':
        bob = half_w
        mesh.piece([(-half_w * .2, -half_l + bob), (half_w * .2, -half_l + bob), (half_w * .14, half_l - half_w * .5), (-half_w * .14, half_l - half_w * .5)], back, blade)
        mesh.piece(circle(0, -half_l + bob, bob, 24), back, back + depth)
        mesh.piece(circle(cx, min(cy, half_l - half_w * .5), half_w * .5, 12), back, back + depth * .8)
        return mesh
    hub = half_w * (.84 if make == 'hour' else 1.0)
    mesh.piece(circle(cx, cy, hub), back, back + depth)
    if make == 'second':
        weight = half_w * .86
        mesh.piece(circle(cx, -half_l + weight, weight, 16), back, back + depth * .7)
        mesh.piece([(cx - half_w * .22, -half_l + weight), (cx + half_w * .22, -half_l + weight), (cx + half_w * .2, cy), (cx - half_w * .2, cy)], back, blade)
        mesh.piece([(cx - half_w * .2, cy), (cx + half_w * .2, cy), (cx + half_w * .1, half_l - length * .06), (cx, half_l), (cx - half_w * .1, half_l - length * .06)], back, blade)
        return mesh
    # The short tail behind the hub.
    mesh.piece([(cx - half_w * .14, -half_l), (cx + half_w * .14, -half_l), (cx + half_w * .26, cy), (cx - half_w * .26, cy)], back, blade)
    if make == 'hour':
        start, wide = half_l - length * .3, half_l - length * .16
        mesh.piece([(cx - half_w * .3, cy), (cx + half_w * .3, cy), (cx + half_w * .18, start), (cx - half_w * .18, start)], back, blade)
        mesh.piece([(cx - half_w * .18, start), (cx + half_w * .18, start), (cx + half_w, wide), (cx, half_l), (cx - half_w, wide)], back, blade)
    else:
        start = half_l - length * .15
        mesh.piece([(cx - half_w * .32, cy), (cx + half_w * .32, cy), (cx + half_w * .2, start), (cx - half_w * .2, start)], back, blade)
        mesh.piece([(cx - half_w * .62, start), (cx + half_w * .62, start), (cx, half_l)], back, blade)
    return mesh


def hand_glb(make, size, pivot, tripo=False):
    """The GLB of a hand. Tripo crafts' parts are turned a quarter (Tripo models face +X and the
    game turns them back), so the hand is authored turned the other way for those."""
    mesh = hand_mesh(make, size, pivot)
    vertices, normals = mesh.vertices, mesh.normals
    if tripo:
        vertices = [(z, y, -x) for x, y, z in vertices]
        normals = [(z, y, -x) for x, y, z in normals]
    w, length = size[0], size[1]
    uv = [(x / w + .5, .5 - y / length) for x, y, _ in mesh.vertices]
    return mesh_glb(vertices, normals, uv, mesh.indices, False, 'Villagen procedural clock hand; no AI')
