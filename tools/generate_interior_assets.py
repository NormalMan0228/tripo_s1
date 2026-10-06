"""Generate the cozy interior furniture set with Tripo text-to-model (user-approved, capped).

Safety rules (same as tools/generate_archipelago_prop.py):
- An intent file is written before every paid POST; an item with an intent but no task id is
  never resubmitted automatically (ambiguous state). Certain rejections are marked so that an
  operator may retry them explicitly with --retry-rejected.
- Any provider error during submission stops all further submissions (in-flight tasks are still
  polled and downloaded; polling is a free GET).
- A credit ledger (actual credits for finished tasks, reservations for in-flight/uncertain ones)
  must stay within --max-credits before a new task is submitted.
- The API key is read only via server.config.read_tripo_key and never logged.

Outputs: game/assets/interior/<id>.glb + manifest.json, artifacts/interior-assets/ (log.jsonl,
per-item job folders, provider preview renders, contact_sheet.png).
"""
import argparse
import asyncio
import hashlib
import io
import json
import math
import re
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.config import Settings, read_tripo_key  # noqa: E402
from server.provider import TripoProvider, ProviderError, validate_glb  # noqa: E402

OUT_GAME = ROOT / 'game/assets/interior'
OUT_ART = ROOT / 'artifacts/interior-assets'
JOBS = OUT_ART / 'jobs'
PREVIEWS = OUT_ART / 'previews'
LOG = OUT_ART / 'log.jsonl'
MANIFEST = OUT_GAME / 'manifest.json'
TARGET_BYTES = 6 * 1024 * 1024

H3 = 'v3.1-20260211'
P2 = 'P2-20260801'
MODEL_LABEL = {H3: 'Tripo H3 (v3.1) textured', P2: 'Tripo P2 textured'}
# Measured on this account: H3 text textured = 20, P2 text textured (standard texture) = 110.
EXPECTED = {H3: 20, P2: 110}
RESERVE = {H3: 30, P2: 130}

STYLE = ('Single isolated game-ready 3D interior prop for a cozy colorful storybook island village game '
         'with adult 1.70m cartoon people. Smooth stylized 3D cartoon sculpt like Animal Crossing furniture: '
         'soft rounded bevels, chunky friendly proportions, clean solid geometry, warm hand-painted '
         'materials with subtle grain, matte surfaces. One complete object, centered and upright. '
         'No ground plane, floor, walls or room, no background, no people, no text, letters, numbers or logos. ')
NEGATIVE = ('ground plane, floor, room, walls, scenery, humans, text, letters, numbers, logos, '
            'thin paper surfaces, jagged low poly, holes, floating parts, multiple separate objects')

# id, category, model, face_limit, size (x width, y height, z depth in metres), scale measure, description
ITEMS = [
    dict(id='bed', category='bedroom', model=P2, faces=16000, size=(1.45, 1.1, 2.05), measure=('longest_horizontal', 2.05),
         text='A cozy single wooden bed for one adult, 2.0m long, 1.4m wide, mattress top 0.55m high. Warm honey-oak '
              'frame with a tall softly arched headboard, a lower footboard and four short turned corner posts with round '
              'knob finials. Plump cream mattress, a thick sage-green quilted patchwork blanket neatly folded back, two '
              'fluffy white pillows. Short sturdy legs. No canopy, no rug, no nightstand.'),
    dict(id='wardrobe_closet', category='bedroom', model=H3, faces=8000, size=(1.1, 1.9, 0.6), measure=('height', 1.9),
         text='A tall two-door wooden wardrobe closet, 1.9m tall, 1.1m wide, 0.6m deep. Warm honey wood body with a '
              'rounded crown moulding on top, two closed panelled doors with small round brass knobs, one wide drawer '
              'at the bottom with two knobs, four short bun feet. Doors closed.'),
    dict(id='bookshelf', category='general', model=H3, faces=10000, size=(1.0, 1.8, 0.35), measure=('height', 1.8),
         text='A tall open wooden bookshelf, 1.8m tall, 1.0m wide, 0.35m deep, honey wood with rounded top. Four shelves '
              'filled with chunky colorful books in soft red, teal, mustard and cream, some leaning, one small potted '
              'plant and a round ceramic jar on the top shelf. Plain book spines without any lettering.'),
    dict(id='dining_table', category='kitchen', model=H3, faces=6000, size=(1.4, 0.76, 0.85), measure=('longest_horizontal', 1.4),
         text='A rectangular wooden dining table for four, 1.4m long, 0.85m wide, 0.76m tall. Thick warm honey plank '
              'top with softly rounded edges and corners, four chunky turned legs with a simple apron underneath. '
              'Empty tabletop, no tablecloth, no dishes, no chairs.'),
    dict(id='wooden_chair', category='kitchen', model=H3, faces=6000, size=(0.45, 0.9, 0.5), measure=('height', 0.9),
         text='A single wooden dining chair, 0.9m tall, seat height 0.45m. Honey wood spindle back with a curved top '
              'rail, a thick rounded seat with a small sage-green tie-on cushion, four slightly splayed sturdy legs '
              'with stretchers. No armrests, no table.'),
    dict(id='sofa', category='general', model=H3, faces=8000, size=(1.9, 0.85, 0.9), measure=('longest_horizontal', 1.9),
         text='A plump cozy three-seat sofa, 1.9m wide, 0.85m tall, 0.9m deep. Soft dusty terracotta-rose fabric '
              'upholstery with rounded rolled arms, three puffy seat cushions, a tufted back, two small cream throw '
              'pillows, short round honey wood feet. Soft fabric folds and stitched seams.'),
    dict(id='kitchen_counter', category='kitchen', model=H3, faces=10000, size=(1.6, 1.0, 0.65), measure=('longest_horizontal', 1.6),
         text='A kitchen counter cabinet with a sink, 1.6m wide, 0.92m tall, 0.65m deep. Cream painted base cabinet '
              'with mint-green panel doors and two drawers with round wooden knobs, a thick butcher-block wooden '
              'countertop, a white ceramic farmhouse sink basin set into the top and a curved brass faucet. Free '
              'standing, no wall, no shelves above.'),
    dict(id='cooking_stove', category='kitchen', model=H3, faces=8000, size=(0.8, 0.95, 0.65), measure=('height', 0.95),
         text='A cozy vintage kitchen cooking stove range, 0.8m wide, 0.92m tall. Rounded enamel body in warm cream '
              'with a dark charcoal cooktop, four round black burners, a front oven door with a small dark window and '
              'a brass bar handle, a row of round brass control knobs, short stubby legs. Nothing on top.'),
    dict(id='potted_plant', category='general', model=H3, faces=10000, size=(0.55, 1.1, 0.55), measure=('height', 1.1),
         text='A leafy indoor potted house plant, 1.1m tall overall. A round glazed terracotta pot with a broad rim and '
              'dark soil, holding a lush plant of broad glossy split monstera leaves in fresh greens on curved stems. '
              'Thick volumetric sculpted leaves, no flat leaf cards, no saucer spill.'),
    dict(id='floor_lamp', category='general', model=H3, faces=6000, size=(0.45, 1.6, 0.45), measure=('height', 1.6),
         text='A standing floor lamp, 1.6m tall. A slim honey wood pole with small brass rings, a round weighted '
              'wooden base, and a warm cream fabric drum lampshade with a scalloped mustard trim on top. Solid '
              'lampshade, no cable, no glow.'),
    dict(id='shop_counter', category='shop', model=H3, faces=10000, size=(1.6, 1.25, 0.7), measure=('longest_horizontal', 1.6),
         text='A village general store shop counter with a cash register, counter 1.6m wide, 1.0m tall, 0.7m deep. '
              'Front of vertical honey wood planks with mint-green trim and a cream top border, a thick polished '
              'wooden countertop, an old-fashioned brass cash register with round blank keys sitting on one end, and '
              'a small brass service bell. Blank register, no numbers.'),
    dict(id='display_shelf', category='shop', model=H3, faces=10000, size=(1.4, 1.7, 0.45), measure=('height', 1.7),
         text='An open wooden shop display shelf unit, 1.7m tall, 1.4m wide, 0.45m deep, honey wood with a rounded top. '
              'Three shelves stocked with goods: glass jars of colorful candies, small burlap sacks, wrapped brown '
              'paper parcels tied with string, a basket of red apples and rows of little bottles. No labels.'),
    dict(id='crate_stack', category='shop', model=H3, faces=6000, size=(1.0, 1.1, 0.7), measure=('height', 1.1),
         text='A stack of three wooden storage crates, about 1.1m tall overall: two crates side by side on the bottom '
              'and one crate on top slightly rotated. Chunky honey and light pine slats with darker corner posts, '
              'visible wood grain, sturdy and solid, closed tops. No stencils or labels.'),
    dict(id='barrel', category='general', model=H3, faces=5000, size=(0.6, 0.85, 0.6), measure=('height', 0.85),
         text='A single wooden storage barrel, 0.85m tall, 0.6m diameter. Bulging warm oak staves with visible grain, '
              'two dark iron hoops near top and bottom, a closed round wooden lid. Solid, upright.'),
    dict(id='workbench', category='workshop', model=P2, faces=20000, size=(1.8, 1.5, 0.8), measure=('longest_horizontal', 1.8),
         text="A big sturdy carpenter's workbench with tools, 1.8m long, 0.8m deep, work surface 0.9m high. Thick "
              'butcher-block honey wood top with a wooden bench vise at one end, chunky square legs and a lower shelf '
              'holding a red toolbox and short planks. On top: a hammer, a hand saw, a wood plane, two clamps and a '
              'few curly wood shavings. A pegboard panel rising 0.6m at the back with hanging wrench, screwdriver and '
              'pliers.'),
    dict(id='telescope', category='observatory', model=P2, faces=16000, size=(0.9, 1.8, 1.2), measure=('height', 1.8),
         text='A large antique brass telescope on a sturdy wooden tripod, 1.8m tall overall. A long polished brass '
              'tube with decorative rings and an eyepiece, pointing diagonally up at the sky, a small finder scope on '
              'top, an adjustable brass mount with round knobs, three honey wood tripod legs with brass feet joined by '
              'a small round accessory tray.'),
    dict(id='seedling_bench', category='greenhouse', model=H3, faces=10000, size=(1.5, 0.9, 0.6), measure=('longest_horizontal', 1.5),
         text='A wooden greenhouse potting bench, 1.5m long, 0.9m tall, 0.6m deep. A slatted weathered wood top holding '
              'rows of small terracotta pots with bright green seedlings and a tray of sprouts, a little watering can, '
              'and a lower slatted shelf with stacked empty pots and a soil sack.'),
    dict(id='cafe_counter', category='cafe', model=H3, faces=10000, size=(1.8, 1.45, 0.7), measure=('longest_horizontal', 1.8),
         text='A cozy cafe counter, 1.8m long, 1.05m tall, 0.7m deep. Front of rounded pastel mint wooden panels with '
              'cream trim, a honey wood countertop, a chunky retro chrome and cream espresso machine with two '
              'portafilters and a pressure gauge on one end, and a small glass pastry display case with cakes on the '
              'other end. Two cups beside the machine. No menu board.'),
    dict(id='round_cafe_table', category='cafe', model=H3, faces=5000, size=(0.7, 0.75, 0.7), measure=('height', 0.75),
         text='A small round bistro cafe table for two, 0.75m tall, 0.7m diameter. A creamy white marble-look round top '
              'with a thin brass rim, a single curved dark wrought-iron pedestal column and three scrolled feet. '
              'Empty top, no chairs.'),
    dict(id='piano', category='general', model=H3, faces=10000, size=(1.5, 1.3, 0.65), measure=('longest_horizontal', 1.5),
         text='An upright piano, 1.5m wide, 1.3m tall, 0.65m deep. Warm reddish-brown mahogany wood case with a rounded '
              'top and softly carved side cheeks, the key lid open showing a row of white and black keys, a small '
              'music rest, two brass pedals at the bottom. No bench, no sheet music.'),
    dict(id='fireplace', category='general', model=H3, faces=10000, size=(1.6, 1.3, 0.6), measure=('longest_horizontal', 1.6),
         text='A cozy free-standing stone fireplace with a wooden mantel, 1.6m wide, 1.3m tall, 0.6m deep, flat back. '
              'Rounded cream and soft gray river stones, a thick honey wood mantel shelf on top, a dark arched firebox '
              'opening with three stacked logs inside, a small stone hearth step in front. No flames, no glow, no '
              'chimney.'),
    dict(id='lighthouse_lens', category='lighthouse', model=H3, faces=10000, size=(1.1, 1.7, 1.1), measure=('height', 1.7),
         text='A big lighthouse Fresnel lamp lens, 1.7m tall. A beehive-shaped barrel lens made of stacked concentric '
              'ribbed glass prism rings in pale aqua-tinted glass, held by polished brass frame bands, with a domed '
              'brass top cap and vent, mounted on a round brass and dark green iron pedestal base. Solid glass, no '
              'light beam.'),
    dict(id='rug', category='general', model=H3, faces=3000, size=(1.8, 0.03, 1.8), measure=('longest_horizontal', 1.8),
         flatten=0.015,  # Tripo returns a tilted, domed disc; bake it flat locally
         text='A round woven braided rag rug lying perfectly flat, 1.8m diameter and only 2cm thick, a thin flat disc. '
              'Concentric braided rings in warm terracotta, mustard yellow, sage green and cream, soft woven fabric '
              'texture, gently rounded edge. Flat, no fringe, nothing on it.'),
    dict(id='wall_clock', category='general', model=H3, faces=5000, size=(0.32, 0.65, 0.12), measure=('height', 0.65),
         text='A cozy wooden pendulum wall clock, 0.65m tall, 0.32m wide, 0.12m deep, flat back for hanging on a wall. '
              'A round cream clock face with simple dot hour markers and two dark hands set in a honey wood case with '
              'a small peaked top, and below it a narrow glass-front case showing a round brass pendulum. No numbers.'),
]
BY_ID = {item['id']: item for item in ITEMS}
TERMINAL = ('success', 'failed', 'cancelled', 'banned', 'expired')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def log(event, **fields):
    OUT_ART.mkdir(parents=True, exist_ok=True)
    entry = {'time': now(), 'event': event, **fields}
    with LOG.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(json.dumps(entry, ensure_ascii=False), flush=True)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def prompt_for(item):
    prompt = STYLE + item['text']
    if len(prompt) > 1024:
        raise ValueError('prompt_too_long:' + item['id'])
    return prompt


def payload_for(item):
    payload = {'model': item['model'], 'prompt': prompt_for(item), 'face_limit': item['faces'],
               'quad': False, 'texture': True, 'pbr': True, 'export_uv': True}
    if item['model'] == P2:
        payload['negative_prompt'] = NEGATIVE
    return payload


# ---------------------------------------------------------------- credit ledger
def recorded_spend(item_id):
    """Credits committed by an item on disk: actual when known, reservation when in flight/uncertain."""
    job = JOBS / item_id
    total = 0.0
    for folder in [job, *sorted(job.glob('attempt-*'))] if job.exists() else []:
        result, intent = folder / 'result.json', folder / 'intent.json'
        if result.exists():
            credits = load(result).get('credits_consumed')
            total += float(credits) if isinstance(credits, (int, float)) else 0.0
        elif intent.exists():
            data = load(intent)
            if not data.get('certain_rejection'):
                total += float(data.get('reservation', RESERVE[P2]))
    return total


class Ledger:
    def __init__(self, cap):
        self.cap = cap
        self.committed = sum(recorded_spend(item['id']) for item in ITEMS)

    def try_reserve(self, amount):
        if self.committed + amount > self.cap:
            return False
        self.committed += amount
        return True

    def settle(self, reservation, actual):
        self.committed += (actual if isinstance(actual, (int, float)) else reservation) - reservation

    def release(self, reservation):
        self.committed -= reservation


# ---------------------------------------------------------------- downloads
def approved(url):
    parsed = urlparse(url or '')
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and parsed.port in (None, 443) and not parsed.username and not parsed.password
            and (host == 'tripo3d.ai' or host.endswith('.tripo3d.ai') or host == 'tripo-data.rg1.data.tripo3d.com'))


async def fetch(url, limit):
    """GET an asset from an approved Tripo host without forwarding the API key."""
    if not approved(url):
        raise ProviderError('unapproved_asset_host')
    chunks, size = [], 0
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            async with client.stream('GET', url) as response:
                if response.status_code != 200:
                    raise ProviderError('asset_download_failed')
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ProviderError('asset_too_large')
                    chunks.append(chunk)
    except httpx.HTTPError:
        raise ProviderError('asset_download_failed') from None
    return b''.join(chunks)


# ---------------------------------------------------------------- GLB helpers
def glb_parts(blob):
    parts, offset = {}, 12
    while offset < len(blob):
        size, kind = struct.unpack_from('<II', blob, offset)
        parts[kind] = blob[offset + 8:offset + 8 + size]
        offset += 8 + size
    return json.loads(parts[0x4E4F534A]), parts[0x004E4942]


def build_glb(doc, views):
    """Rebuild a single-buffer GLB from a document and its (possibly replaced) bufferView bytes."""
    binary = bytearray()
    for index, data in enumerate(views):
        binary.extend(b'\0' * (-len(binary) % 4))
        doc['bufferViews'][index]['byteOffset'] = len(binary)
        doc['bufferViews'][index]['byteLength'] = len(data)
        binary.extend(data)
    binary.extend(b'\0' * (-len(binary) % 4))
    doc['buffers'] = [{'byteLength': len(binary)}]
    text = json.dumps(doc, separators=(',', ':')).encode('utf-8')
    text += b' ' * (-len(text) % 4)
    total = 12 + 8 + len(text) + 8 + len(binary)
    return (struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<II', len(text), 0x4E4F534A) + text
            + struct.pack('<II', len(binary), 0x004E4942) + bytes(binary))


def shrink_glb(blob, max_side):
    """Re-encode embedded textures as JPEG (and optionally downscale) to meet the size target."""
    from PIL import Image
    doc, binary = glb_parts(blob)
    views = [binary[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']] for v in doc['bufferViews']]
    for image in doc.get('images', []):
        index = image['bufferView']
        with Image.open(io.BytesIO(views[index])) as source:
            picture = source.convert('RGBA' if source.mode in ('RGBA', 'LA', 'P') else 'RGB')
        if max_side and max(picture.size) > max_side:
            factor = max_side / max(picture.size)
            picture = picture.resize((max(1, round(picture.width * factor)), max(1, round(picture.height * factor))),
                                     Image.LANCZOS)
        out = io.BytesIO()
        if picture.mode == 'RGBA' and picture.getextrema()[3][0] < 255:
            picture.save(out, format='PNG', optimize=True)
            image['mimeType'] = 'image/png'
        else:
            picture.convert('RGB').save(out, format='JPEG', quality=90, optimize=True)
            image['mimeType'] = 'image/jpeg'
        views[index] = out.getvalue()
    return build_glb(doc, views)


def matmul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def node_matrix(node):
    if 'matrix' in node:
        m = node['matrix']  # column-major
        return [m[c * 4 + r] for r in range(4) for c in range(4)]
    tx, ty, tz = node.get('translation', [0, 0, 0])
    qx, qy, qz, qw = node.get('rotation', [0, 0, 0, 1])
    sx, sy, sz = node.get('scale', [1, 1, 1])
    rot = [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw),
           2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw),
           2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]
    return [rot[0] * sx, rot[1] * sy, rot[2] * sz, tx,
            rot[3] * sx, rot[4] * sy, rot[5] * sz, ty,
            rot[6] * sx, rot[7] * sy, rot[8] * sz, tz,
            0, 0, 0, 1]


def scene_bounds(doc):
    """World-space AABB of the default scene from POSITION accessor min/max and node transforms."""
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    triangles = 0
    scenes = doc.get('scenes') or [{'nodes': list(range(len(doc['nodes'])))}]
    roots = scenes[doc.get('scene', 0)].get('nodes', [])

    def visit(index, parent):
        nonlocal triangles
        node = doc['nodes'][index]
        world = matmul(parent, node_matrix(node))
        if 'mesh' in node:
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                accessor = doc['accessors'][primitive['attributes']['POSITION']]
                if 'indices' in primitive:
                    triangles += doc['accessors'][primitive['indices']]['count'] // 3
                else:
                    triangles += accessor['count'] // 3
                amin, amax = accessor.get('min'), accessor.get('max')
                if not amin or not amax:
                    continue
                for corner in range(8):
                    p = [amax[i] if corner >> i & 1 else amin[i] for i in range(3)]
                    w = [sum(world[r * 4 + c] * (p[c] if c < 3 else 1) for c in range(4)) for r in range(3)]
                    for i in range(3):
                        lo[i], hi[i] = min(lo[i], w[i]), max(hi[i], w[i])
        for child in node.get('children', []):
            visit(child, world)

    for root in roots:
        visit(root, identity)
    if not all(math.isfinite(v) for v in lo + hi):
        return None, triangles
    return [round(h - l, 5) for l, h in zip(lo, hi)], triangles


def scale_hint(item, extent):
    measure, metres = item['measure']
    if not extent:
        return None
    source = extent[1] if measure == 'height' else max(extent[0], extent[2])
    return round(metres / source, 5) if source > 1e-6 else None


# ---------------------------------------------------------------- manifest + contact sheet
def write_manifest():
    entries, total = [], 0.0
    for item in ITEMS:
        result_path = JOBS / item['id'] / 'result.json'
        if not result_path.exists():
            continue
        result = load(result_path)
        if result.get('status') != 'success' or not (OUT_GAME / (item['id'] + '.glb')).exists():
            continue
        total += float(result.get('credits_consumed') or 0)
        width, height, depth = item['size']
        entries.append({
            'id': item['id'],
            'file': 'res://assets/interior/%s.glb' % item['id'],
            'category': item['category'],
            'model': item['model'],
            'model_label': MODEL_LABEL[item['model']],
            'credits_consumed': result.get('credits_consumed'),
            'task_id': result.get('task_id'),
            'size_m': {'width_x': width, 'height_y': height, 'depth_z': depth},
            'scale_reference': {'measure': item['measure'][0], 'metres': item['measure'][1]},
            'source_extent': result.get('source_extent'),
            'suggested_uniform_scale': result.get('suggested_uniform_scale'),
            'bytes': result.get('bytes'),
            'sha256': result.get('sha256'),
            'triangles': result.get('triangles'),
            'vertices': result.get('vertices'),
            'texture_pixels': result.get('texture_pixels'),
            'textures_reencoded': result.get('textures_reencoded', False),
            'post_processing': result.get('post_processing'),
            'description': item['text'],
        })
    save(MANIFEST, {
        'version': 1,
        'generated': now(),
        'source': 'Tripo text-to-model via tools/generate_interior_assets.py',
        'style_prompt': STYLE.strip(),
        'notes': ('glTF +Y up. Raw Tripo output is normalised to about one unit; scale uniformly by '
                  'suggested_uniform_scale (scale_reference.metres / source extent along scale_reference.measure). '
                  'Front-facing direction is not guaranteed; check orientation when placing. '
                  'longest_horizontal = max(X, Z) extent.'),
        'total_credits_consumed': total,
        'items': entries,
    })


def contact_sheet():
    from PIL import Image, ImageDraw
    tiles = []
    for item in ITEMS:
        found = next((p for p in sorted(PREVIEWS.glob(item['id'] + '.*'))), None) if PREVIEWS.exists() else None
        if found:
            tiles.append((item, found))
    if not tiles:
        return None
    cell, label, columns = 256, 34, 6
    rows = math.ceil(len(tiles) / columns)
    sheet = Image.new('RGB', (columns * cell, rows * (cell + label)), (246, 242, 233))
    draw = ImageDraw.Draw(sheet)
    for index, (item, path) in enumerate(tiles):
        x, y = index % columns * cell, index // columns * (cell + label)
        try:
            with Image.open(path) as source:
                thumb = source.convert('RGBA')
            thumb.thumbnail((cell - 8, cell - 8))
            backdrop = Image.new('RGBA', thumb.size, (246, 242, 233, 255))
            backdrop.alpha_composite(thumb)
            sheet.paste(backdrop.convert('RGB'), (x + (cell - thumb.width) // 2, y + (cell - thumb.height) // 2))
        except Exception:
            draw.text((x + 10, y + 10), 'preview unreadable', fill=(160, 40, 40))
        result_path = JOBS / item['id'] / 'result.json'
        credits = load(result_path).get('credits_consumed') if result_path.exists() else '?'
        model = 'P2' if item['model'] == P2 else 'H3'
        draw.text((x + 8, y + cell + 4), item['id'], fill=(40, 34, 28))
        draw.text((x + 8, y + cell + 18), '%s  %s cr  %s' % (model, credits, item['category']), fill=(110, 96, 80))
    out = OUT_ART / 'contact_sheet.png'
    sheet.save(out)
    return out


# ---------------------------------------------------------------- local post-processing (no API calls)
def flatten_disc(blob, thickness_ratio):
    """Bake a tilted thick disc (Tripo's rug output) flat: thinnest PCA axis -> +Y, then squash Y.

    The side that faced up (+Y) in the provider output stays up, so the textured top remains visible.
    """
    import numpy as np
    doc, binary = glb_parts(blob)
    views = [bytearray(binary[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']])
             for v in doc['bufferViews']]

    def column(index, width):
        accessor = doc['accessors'][index]
        view = doc['bufferViews'][accessor['bufferView']]
        stride = view.get('byteStride', 4 * width)
        start = accessor.get('byteOffset', 0)
        data = views[accessor['bufferView']]
        rows = np.array([struct.unpack_from('<' + 'f' * width, data, start + i * stride)
                         for i in range(accessor['count'])], dtype=np.float64)

        def store(values):
            for i, row in enumerate(values):
                struct.pack_into('<' + 'f' * width, data, start + i * stride, *map(float, row))
        return rows, store

    primitives = [p for mesh in doc['meshes'] for p in mesh['primitives']]
    points = np.concatenate([column(p['attributes']['POSITION'], 3)[0] for p in primitives])
    centre = points.mean(axis=0)
    normal = np.linalg.svd(points - centre, full_matrices=False)[2][2]
    if normal[1] < 0:
        normal = -normal
    axis = np.cross(normal, [0.0, 1.0, 0.0])
    sine, cosine = np.linalg.norm(axis), float(normal[1])
    if sine < 1e-9:
        rotation = np.eye(3)
    else:
        k = axis / sine
        cross = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        rotation = np.eye(3) + sine * cross + (1 - cosine) * cross @ cross
    rotated = (points - centre) @ rotation.T
    diameter = max(np.ptp(rotated[:, 0]), np.ptp(rotated[:, 2]))
    squash = thickness_ratio * diameter / max(np.ptp(rotated[:, 1]), 1e-9)
    scale = np.diag([1.0, squash, 1.0])
    forward = scale @ rotation
    inverse_t = np.linalg.inv(scale) @ rotation  # (M^-1)^T for normals, since rotation is orthonormal
    done = set()
    for primitive in primitives:
        attributes = primitive['attributes']
        if attributes['POSITION'] not in done:
            values, store = column(attributes['POSITION'], 3)
            moved = (values - centre) @ forward.T
            moved[:, 1] -= (moved[:, 1].min() + moved[:, 1].max()) / 2  # stay centred like other Tripo outputs
            store(moved)
            accessor = doc['accessors'][attributes['POSITION']]
            accessor['min'], accessor['max'] = moved.min(axis=0).tolist(), moved.max(axis=0).tolist()
            done.add(attributes['POSITION'])
        if 'NORMAL' in attributes and attributes['NORMAL'] not in done:
            values, store = column(attributes['NORMAL'], 3)
            turned = values @ inverse_t.T
            store(turned / np.maximum(np.linalg.norm(turned, axis=1, keepdims=True), 1e-12))
            done.add(attributes['NORMAL'])
        if 'TANGENT' in attributes and attributes['TANGENT'] not in done:
            values, store = column(attributes['TANGENT'], 4)
            turned = values[:, :3] @ forward.T
            values[:, :3] = turned / np.maximum(np.linalg.norm(turned, axis=1, keepdims=True), 1e-12)
            store(values)
            done.add(attributes['TANGENT'])
    return build_glb(doc, [bytes(view) for view in views]), {
        'tilt_degrees_removed': round(math.degrees(math.acos(min(1.0, max(-1.0, cosine)))), 2),
        'thickness_ratio': thickness_ratio}


def finalize_local(item, raw, result):
    """Post-process, validate, size-check and save one downloaded GLB. Updates result in place."""
    item_id = item['id']
    source, post = raw, None
    if item.get('flatten'):
        source, post = flatten_disc(raw, item['flatten'])
        log('flattened', item=item_id, **post)
    best = None
    for attempt in (None, 0, 2048, 1024):  # as is, JPEG re-encode, then downscales
        if attempt is None:
            candidate = source
        else:
            try:
                candidate = shrink_glb(source, attempt)
            except Exception as error:
                log('shrink_error', item=item_id, error=type(error).__name__)
                break
        candidate_stats = {}
        try:
            candidate_doc = validate_glb(candidate, allow_textures=True, stats=candidate_stats)
        except ProviderError as error:
            log('validate_failed', item=item_id, code=error.code, bytes=len(candidate), reencoded=attempt is not None)
            continue
        best = (candidate, candidate_doc, candidate_stats, attempt is not None)
        if len(candidate) <= TARGET_BYTES:
            break
        log('over_size_target', item=item_id, bytes=len(candidate), target=TARGET_BYTES, reencoded=attempt is not None)
    if best is None:
        result.update(status='invalid_model', bytes=len(raw))
        return False
    blob, doc, stats, reencoded = best
    extent, triangles = scene_bounds(doc)
    OUT_GAME.mkdir(parents=True, exist_ok=True)
    (OUT_GAME / (item_id + '.glb')).write_bytes(blob)
    result.update(bytes=len(blob), raw_bytes=len(raw), sha256=hashlib.sha256(blob).hexdigest(),
                  vertices=stats.get('vertices'), draw_calls=stats.get('draw_calls'),
                  texture_pixels=stats.get('texture_pixels'), triangles=triangles,
                  source_extent=extent, suggested_uniform_scale=scale_hint(item, extent),
                  textures_reencoded=reencoded, post_processing=post,
                  saved=str((OUT_GAME / (item_id + '.glb')).relative_to(ROOT).as_posix()))
    log('validated_saved', item=item_id, bytes=len(blob), vertices=result['vertices'], triangles=triangles,
        texture_pixels=result['texture_pixels'], extent=extent, reencoded=reencoded, post_processing=post)
    return True


def reprocess(items):
    """Re-run local post-processing from saved raw downloads; never calls the provider."""
    for item in items:
        job = JOBS / item['id']
        if not (job / 'result.json').exists() or not (job / 'tripo-original.glb').exists():
            continue
        result = load(job / 'result.json')
        if result.get('status') != 'success':
            continue
        if finalize_local(item, (job / 'tripo-original.glb').read_bytes(), result):
            save(job / 'result.json', result)
    write_manifest()


# ---------------------------------------------------------------- one item
async def run_item(item, provider, ledger, stop, semaphore, args):
    item_id = item['id']
    job = JOBS / item_id
    job.mkdir(parents=True, exist_ok=True)
    intent_path, task_path, result_path = job / 'intent.json', job / 'task.json', job / 'result.json'
    if result_path.exists():
        previous = load(result_path)
        if previous.get('status') == 'success' and (OUT_GAME / (item_id + '.glb')).exists():
            return {'id': item_id, 'ok': True, 'skipped': 'already_generated'}
        if not args.retry_failed:
            return {'id': item_id, 'ok': False, 'error': 'previous_' + str(previous.get('status'))}
        archive = job / ('attempt-%d' % (len(list(job.glob('attempt-*'))) + 1))
        archive.mkdir()
        for name in ('intent.json', 'task.json', 'result.json', 'request.json'):
            if (job / name).exists():
                (job / name).rename(archive / name)
        log('archived_failed_attempt', item=item_id, folder=archive.name)
    async with semaphore:
        reservation = RESERVE[item['model']]
        if not task_path.exists():
            if intent_path.exists():
                intent = load(intent_path)
                if intent.get('certain_rejection') and args.retry_rejected:
                    archive = job / ('attempt-%d' % (len(list(job.glob('attempt-*'))) + 1))
                    archive.mkdir()
                    for name in ('intent.json', 'request.json'):
                        if (job / name).exists():
                            (job / name).rename(archive / name)
                else:
                    log('ambiguous_intent_no_resubmit', item=item_id)
                    return {'id': item_id, 'ok': False, 'error': 'ambiguous_intent_no_resubmit'}
            if stop.is_set():
                return {'id': item_id, 'ok': False, 'error': 'not_submitted_after_stop'}
            if not ledger.try_reserve(reservation):
                log('budget_cap_reached', item=item_id, committed=ledger.committed, cap=ledger.cap)
                return {'id': item_id, 'ok': False, 'error': 'budget_cap'}
            payload = payload_for(item)
            save(job / 'request.json', payload)
            with intent_path.open('x', encoding='utf-8') as handle:
                json.dump({'time': time.time(), 'model': item['model'], 'reservation': reservation,
                           'automatic_resubmit': False}, handle)
            log('submit_request', item=item_id, route='/generation/text-to-model', model=item['model'],
                face_limit=item['faces'], texture=True, pbr=True, prompt_chars=len(payload['prompt']),
                prompt_sha256=hashlib.sha256(payload['prompt'].encode()).hexdigest(),
                committed_with_reservation=ledger.committed)
            try:
                data = await provider.request('POST', '/generation/text-to-model', payload)
            except ProviderError as error:
                stop.set()
                if not error.uncertain:
                    intent = load(intent_path)
                    intent['certain_rejection'] = error.code
                    save(intent_path, intent)
                    ledger.release(reservation)
                log('submit_error_stopping', item=item_id, code=error.code, uncertain=error.uncertain)
                return {'id': item_id, 'ok': False, 'error': error.code, 'uncertain': error.uncertain}
            task_id = data.get('task_id', '')
            if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,200}', task_id):
                stop.set()
                log('submit_schema_error_stopping', item=item_id)
                return {'id': item_id, 'ok': False, 'error': 'upstream_schema', 'uncertain': True}
            save(task_path, {'task_id': task_id})
            log('submit_response', item=item_id, task_id=task_id)
        task_id = load(task_path)['task_id']
        last, failures, task = None, 0, None
        for _ in range(720):
            try:
                task = await provider.task(task_id)
                failures = 0
            except ProviderError as error:
                failures += 1
                log('poll_error', item=item_id, code=error.code, consecutive=failures)
                if failures >= 12:
                    stop.set()
                    return {'id': item_id, 'ok': False, 'error': 'poll_failed_resume_later', 'task_id': task_id}
                await asyncio.sleep(10)
                continue
            state = task.get('status')
            if (state, task.get('progress')) != last:
                last = (state, task.get('progress'))
                log('poll', item=item_id, status=state, progress=task.get('progress'))
            if state in TERMINAL:
                break
            await asyncio.sleep(5)
        else:
            log('poll_timeout_resume_later', item=item_id, task_id=task_id)
            return {'id': item_id, 'ok': False, 'error': 'poll_timeout_resume_later', 'task_id': task_id}
    # Semaphore released: the paid part is over; downloads do not count toward live jobs.
    credits = task.get('credits_consumed')
    output = task.get('output') if isinstance(task.get('output'), dict) else {}
    log('task_final', item=item_id, task_id=task_id, status=state, credits_consumed=credits,
        output_fields=sorted(output), error_code=task.get('error_code'))
    ledger.settle(reservation, credits)
    if isinstance(credits, (int, float)) and credits > reservation:
        stop.set()
        log('cost_anomaly_stopping', item=item_id, credits_consumed=credits, reservation=reservation)
    result = {'id': item_id, 'task_id': task_id, 'status': state, 'model': item['model'],
              'credits_consumed': credits}
    if state != 'success':
        save(result_path, result)
        return {'id': item_id, 'ok': False, 'error': 'task_' + str(state), 'credits_consumed': credits}
    try:
        raw = await fetch(output.get('model_url', ''), 64 * 1024 * 1024)
    except ProviderError as error:
        log('download_error_resume_safe', item=item_id, code=error.code)
        return {'id': item_id, 'ok': False, 'error': 'download_' + error.code, 'task_id': task_id}
    (job / 'tripo-original.glb').write_bytes(raw)
    log('download', item=item_id, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
        host=urlparse(output.get('model_url', '')).hostname)
    if not finalize_local(item, raw, result):
        save(result_path, result)
        return {'id': item_id, 'ok': False, 'error': 'invalid_model', 'credits_consumed': credits}
    blob_bytes = result['bytes']
    preview_url = output.get('rendered_image_url') or output.get('generated_image_url')
    if preview_url:
        try:
            image = await fetch(preview_url, 16 * 1024 * 1024)
            extension = {b'RIFF': 'webp', b'\x89PNG': 'png'}.get(image[:4], 'jpg')
            PREVIEWS.mkdir(parents=True, exist_ok=True)
            (PREVIEWS / ('%s.%s' % (item_id, extension))).write_bytes(image)
            result['preview'] = 'previews/%s.%s' % (item_id, extension)
        except ProviderError as error:
            log('preview_download_error', item=item_id, code=error.code)
    save(result_path, result)
    write_manifest()
    return {'id': item_id, 'ok': True, 'model': item['model'], 'credits_consumed': credits, 'bytes': blob_bytes}


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--key-file', type=Path, default=Path.home() / 'Desktop/tripo_key.txt')
    parser.add_argument('--only', nargs='+', choices=sorted(BY_ID))
    parser.add_argument('--max-credits', type=float, default=1200)
    parser.add_argument('--concurrency', type=int, default=3, choices=(1, 2, 3))
    parser.add_argument('--dry-run', action='store_true', help='print plan and payload sizes; no API calls')
    parser.add_argument('--retry-failed', action='store_true', help='resubmit items whose task finished as failed')
    parser.add_argument('--retry-rejected', action='store_true', help='resubmit certainly rejected (never-created) tasks')
    parser.add_argument('--sheet-only', action='store_true', help='rebuild manifest and contact sheet only')
    parser.add_argument('--reprocess', action='store_true', help='redo local post-processing from saved raw GLBs')
    args = parser.parse_args()
    selected = [BY_ID[i] for i in args.only] if args.only else ITEMS
    for item in selected:
        payload_for(item)  # validates prompt length
    if args.reprocess:
        reprocess(selected)
        return
    if args.sheet_only:
        write_manifest()
        print(json.dumps({'manifest': str(MANIFEST), 'contact_sheet': str(contact_sheet())}))
        return
    planned = sum(EXPECTED[item['model']] for item in selected)
    worst = sum(RESERVE[item['model']] for item in selected)
    if args.dry_run:
        for item in selected:
            print(json.dumps({'id': item['id'], 'model': item['model'], 'faces': item['faces'],
                              'prompt_chars': len(prompt_for(item)), 'category': item['category']}))
        print(json.dumps({'items': len(selected), 'expected_credits': planned, 'worst_case_reserved': worst,
                          'already_committed': Ledger(args.max_credits).committed, 'cap': args.max_credits}))
        return
    provider = TripoProvider(Settings(tripo_key=read_tripo_key(args.key_file)))
    ledger = Ledger(args.max_credits)
    balance_start = await provider.balance()
    log('run_start', items=[item['id'] for item in selected], expected_credits=planned, cap=args.max_credits,
        already_committed=ledger.committed, balance=balance_start, concurrency=args.concurrency)
    if balance_start < worst + 100:
        log('balance_too_low_abort', balance=balance_start, needed=worst + 100)
        return
    stop = asyncio.Event()
    semaphore = asyncio.Semaphore(args.concurrency)
    # Heroes first: they take longest.
    order = sorted(selected, key=lambda item: item['model'] != P2)
    results = await asyncio.gather(*(run_item(item, provider, ledger, stop, semaphore, args) for item in order))
    write_manifest()
    sheet = contact_sheet()
    balance_end = await provider.balance()
    spent = sum(float(r.get('credits_consumed') or 0) for r in results)
    summary = {'results': results, 'credits_consumed_this_run': spent, 'ledger_committed_total': ledger.committed,
               'balance_start': balance_start, 'balance_end': balance_end,
               'balance_delta': balance_start - balance_end, 'stopped_early': stop.is_set(),
               'contact_sheet': str(sheet.relative_to(ROOT).as_posix()) if sheet else None}
    log('run_end', **summary)
    save(OUT_ART / 'run-summary.json', summary)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (ProviderError, ValueError) as error:
        print(json.dumps({'error': error.code if isinstance(error, ProviderError) else str(error),
                          'automatic_resubmit': False}), flush=True)
        sys.exit(1)
