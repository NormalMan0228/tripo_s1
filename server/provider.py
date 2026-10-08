"""Tripo v3 adapter: no credentials or upstream response bodies in errors/logs."""
import hashlib
import json
import math
import struct
from urllib.parse import urlparse
import httpx

MAX_GLB = 20 * 1024 * 1024

class ProviderError(Exception):
    def __init__(self, code, uncertain=False):
        self.code, self.uncertain = code, uncertain
        super().__init__(code)

def validate_glb(blob, allow_textures=False, stats=None):
    """Accept bounded static, embedded GLB only. Reject remote/local URI references."""
    def reject():
        raise ProviderError('invalid_model')
    def reference(items, value):
        if type(value) is not int or not 0 <= value < len(items): reject()
        return items[value]
    def integer(value, minimum=0):
        if type(value) is not int or value < minimum: reject()
        return value
    if len(blob) < 28 or len(blob) > MAX_GLB:
        reject()
    magic, version, length = struct.unpack_from('<III', blob)
    if magic != 0x46546C67 or version != 2 or length != len(blob):
        reject()
    parts, offset = {}, 12
    while offset < len(blob):
        if offset+8 > len(blob): reject()
        size, kind = struct.unpack_from('<II', blob, offset)
        offset += 8
        if size % 4 or offset+size > len(blob) or kind in parts: reject()
        parts[kind] = blob[offset:offset+size]
        offset += size
    if set(parts) != {0x4E4F534A, 0x004E4942}: reject()
    try:
        doc = json.loads(parts[0x4E4F534A])
        if not isinstance(doc,dict): reject()
        for field in ('buffers','bufferViews','accessors','meshes','nodes','scenes','materials'):
            if not isinstance(doc.get(field,[]),list): reject()
        if doc.get('asset', {}).get('version') != '2.0': reject()
        if doc.get('extensionsRequired') or doc.get('animations') or doc.get('skins'): reject()
        def walk(v, depth=0):
            if depth > 32: reject()
            if isinstance(v, dict):
                if 'uri' in v or 'extensions' in v: reject()
                for item in v.values(): walk(item, depth+1)
            elif isinstance(v, list):
                for item in v: walk(item, depth+1)
            elif isinstance(v, float) and not math.isfinite(v): reject()
        walk(doc)
        buffers = doc.get('buffers', [])
        if len(buffers) != 1 or buffers[0]['byteLength'] > len(parts[0x004E4942]): reject()
        if len(parts[0x004E4942])-integer(buffers[0]['byteLength'],1)>3: reject()
        if len(doc.get('bufferViews',[]))>2048: reject()
        for view in doc.get('bufferViews', []):
            integer(view.get('byteOffset',0)); integer(view['byteLength'],1)
            if view.get('buffer',0) != 0 or view.get('byteOffset',0) < 0 or view['byteLength'] < 0: reject()
            if view.get('byteOffset',0)+view['byteLength'] > buffers[0]['byteLength']: reject()
        accessors = doc.get('accessors', [])
        if len(accessors) > 2048 or sum(a.get('count',0) for a in accessors) > 600000: reject()
        for a in accessors:
            integer(a['count'],1); integer(a.get('byteOffset',0))
            if 'sparse' in a: reject()
            view = reference(doc['bufferViews'],a['bufferView'])
            components = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
            width = {5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}[a['componentType']]*components
            stride = view.get('byteStride',width)
            integer(stride,1)
            if stride < width or stride > 252 or a.get('byteOffset',0) < 0: reject()
            if a.get('byteOffset',0)+max(0,a['count']-1)*stride+width > view['byteLength']: reject()
            if a['componentType']==5126:
                start=view.get('byteOffset',0)+a.get('byteOffset',0)
                for i in range(a['count']):
                    values=struct.unpack_from('<'+'f'*components,parts[0x004E4942],start+i*stride)
                    if any(not math.isfinite(v) or abs(v)>1000000 for v in values):reject()
        nodes = doc.get('nodes', [])
        if not nodes or len(nodes) > 256 or len(doc.get('meshes', [])) > 128: reject()
        # Reused accessors and mesh instances still consume GPU/CPU work.
        if sum(len(m.get('primitives',[])) for m in doc.get('meshes',[]))>64:reject()
        if len(doc.get('materials',[]))>64:reject()
        instanced_vertices=0
        instanced_primitives=0
        for node in nodes:
            if 'mesh' in node:
                for primitive in reference(doc.get('meshes',[]),node['mesh']).get('primitives',[]):
                    instanced_primitives+=1
                    instanced_vertices+=reference(accessors,primitive['attributes']['POSITION'])['count']
        if instanced_vertices>250000 or instanced_primitives>128:reject()
        parent_count = [0]*len(nodes)
        for node in nodes:
            if 'mesh' in node: reference(doc.get('meshes',[]),node['mesh'])
            if 'skin' in node or 'camera' in node or 'weights' in node: reject()
            for field,length in (('translation',3),('rotation',4),('scale',3),('matrix',16)):
                if field in node:
                    values=node[field]
                    if not isinstance(values,list) or len(values)!=length or any(type(v) not in (int,float) or abs(v)>1000000 for v in values): reject()
            for child in node.get('children',[]):
                reference(nodes,child)
                parent_count[child]+=1
                if parent_count[child]>1: reject()
        seen, stack = set(), set()
        def visit(i, depth=0):
            if depth > 32 or i in stack or not 0 <= i < len(nodes): reject()
            if i in seen: return
            stack.add(i)
            for child in nodes[i].get('children',[]): visit(child,depth+1)
            stack.remove(i); seen.add(i)
        for i in range(len(nodes)): visit(i)
        if not any('mesh' in node for node in nodes): reject()
        for scene in doc.get('scenes',[]):
            for root in scene.get('nodes',[]):
                reference(nodes,root)
                if parent_count[root]: reject()
        if 'scene' in doc: reference(doc.get('scenes',[]),doc['scene'])
        pixels=0
        # Paint-only props have no textures; textured props have a bounded decode budget.
        if doc.get('images') or doc.get('textures'):
            if not allow_textures: reject()
            import io
            from PIL import Image
            images=doc.get('images',[]);textures=doc.get('textures',[])
            if not isinstance(images,list) or not isinstance(textures,list) or len(images)>8 or len(textures)>8:reject()
            for image in images:
                if image.get('mimeType') not in ('image/png','image/jpeg'):reject()
                v=reference(doc['bufferViews'],image['bufferView'])
                raw=parts[0x004E4942][v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']]
                if len(raw)>8*1024*1024:reject()
                try:
                    with Image.open(io.BytesIO(raw)) as im:
                        pixels+=im.width*im.height
                        if im.format not in ('PNG','JPEG') or im.width>4096 or im.height>4096 or pixels>24000000:reject()
                        im.verify()
                except ProviderError:raise
                except Exception:reject()
            for texture in textures:reference(images,texture['source'])
            def texture_refs(v):
                if isinstance(v,dict):
                    for k,x in v.items():
                        if k.endswith('Texture'):
                            reference(textures,x['index'])
                            if x.get('texCoord',0)!=0:reject()
                        texture_refs(x)
                elif isinstance(v,list):
                    for x in v:texture_refs(x)
            texture_refs(doc.get('materials',[]))
        for mesh in doc['meshes']:
            if not mesh['primitives'] or len(mesh['primitives'])>128: reject()
            for p in mesh['primitives']:
                if p.get('mode',4) != 4 or 'targets' in p: reject()
                if set(p['attributes'])-{'POSITION','NORMAL','TANGENT','TEXCOORD_0','COLOR_0'}:reject()
                position = reference(accessors,p['attributes']['POSITION'])
                for name,index in p['attributes'].items():
                    attribute=reference(accessors,index)
                    valid_types={'POSITION':('VEC3',),'NORMAL':('VEC3',),'TANGENT':('VEC4',),'TEXCOORD_0':('VEC2',),'COLOR_0':('VEC3','VEC4')}
                    if attribute['type'] not in valid_types[name]:reject()
                    if name in ('NORMAL','TANGENT') and attribute['componentType']!=5126:reject()
                    if name in ('TEXCOORD_0','COLOR_0') and attribute['componentType'] not in (5121,5123,5126):reject()
                    if name in ('TEXCOORD_0','COLOR_0') and attribute['componentType']!=5126 and attribute.get('normalized') is not True:reject()
                for attribute in p['attributes'].values():
                    if reference(accessors,attribute)['count']!=position['count']: reject()
                if 'material' in p: reference(doc.get('materials',[]),p['material'])
                if position['count'] > 100000 or position['componentType']!=5126 or position['type']!='VEC3': reject()
                view = doc['bufferViews'][position['bufferView']]
                start = view.get('byteOffset',0)+position.get('byteOffset',0)
                for i in range(position['count']):
                    xyz = struct.unpack_from('<fff',parts[0x004E4942],start+i*view.get('byteStride',12))
                    if any(not math.isfinite(v) or abs(v)>1000000 for v in xyz): reject()
                if 'indices' in p:
                    indices = reference(accessors,p['indices'])
                    fmt = {5121:'B',5123:'H',5125:'I'}[indices['componentType']]
                    size = struct.calcsize(fmt)
                    v = doc['bufferViews'][indices['bufferView']]
                    start = v.get('byteOffset',0)+indices.get('byteOffset',0)
                    if indices['type']!='SCALAR' or indices['count']%3: reject()
                    for i in range(indices['count']):
                        if struct.unpack_from('<'+fmt,parts[0x004E4942],start+i*v.get('byteStride',size))[0]>=position['count']: reject()
        if stats is not None:stats.update(texture_pixels=pixels,vertices=instanced_vertices,draw_calls=instanced_primitives,bytes=len(blob))
        return doc
    except (KeyError, ValueError, TypeError, IndexError, AttributeError, RecursionError, OverflowError, struct.error):
        reject()

def key_fingerprint(key):
    """A short one-way label for a key, safe to store with tasks and show in logs."""
    return hashlib.sha256(key.encode()).hexdigest()[:12] if key else ''

def jpeg_preview(blob):
    """PNG/JPEG/WEBP bytes -> JPEG of at most 1024 px; anything else is refused."""
    import io
    from PIL import Image
    try:
        image = Image.open(io.BytesIO(blob))
        if image.format not in ('PNG','JPEG','WEBP') or image.width*image.height > 4096*4096: raise ProviderError('invalid_image')
        image.load()
    except ProviderError: raise
    except Exception: raise ProviderError('invalid_image') from None
    image = image.convert('RGB')
    image.thumbnail((1024,1024))
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=88)
    return out.getvalue()


class TripoProvider:
    BASE = 'https://openapi.tripo3d.ai/v3'
    def __init__(self, settings, transport=None, key=None):
        self.settings, self.transport = settings, transport
        self.key = key if key is not None else settings.tripo_key
        self.fingerprint = key_fingerprint(self.key)

    def keys(self):
        """Every configured key in priority order (tripo_keys, else the single tripo_key)."""
        configured = tuple(getattr(self.settings, 'tripo_keys', ()) or ())
        return configured or ((self.settings.tripo_key,) if self.settings.tripo_key else ())

    def pool(self):
        """One provider per key, first choice first."""
        return [TripoProvider(self.settings, self.transport, key) for key in self.keys()]

    def for_key(self, fingerprint):
        """The provider for a task's key; tasks without a label belong to the first key."""
        if not fingerprint:
            return self
        for key in self.keys():
            if key_fingerprint(key) == fingerprint:
                return TripoProvider(self.settings, self.transport, key)
        raise ProviderError('key_not_configured')

    async def request(self, method, route, payload=None):
        if not self.key:
            raise ProviderError('key_not_configured')
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=25, follow_redirects=False) as client:
                response = await client.request(method, self.BASE+route,
                    headers={'Authorization':'Bearer '+self.key}, json=payload)
        except httpx.HTTPError:
            raise ProviderError('upstream_unreachable', uncertain=method=='POST') from None
        if response.status_code == 401: raise ProviderError('upstream_authentication')
        if response.status_code == 429: raise ProviderError('upstream_rate_limit')
        if len(response.content)>1024*1024: raise ProviderError('upstream_response_too_large',uncertain=method=='POST')
        if 'application/json' not in response.headers.get('content-type',''):
            raise ProviderError('upstream_non_json', uncertain=method=='POST')
        try: data = response.json()
        except ValueError: raise ProviderError('upstream_invalid_json', uncertain=method=='POST') from None
        if not isinstance(data,dict): raise ProviderError('upstream_schema',uncertain=method=='POST')
        if response.status_code >= 500: raise ProviderError('upstream_unavailable', uncertain=method=='POST')
        if response.status_code >= 400 or data.get('code') != 0:
            raise ProviderError('upstream_rejected')
        if not isinstance(data.get('data'),dict): raise ProviderError('upstream_schema', uncertain=method=='POST')
        return data['data']

    async def balance(self):
        data = await self.request('GET','/account/balance')
        value = data.get('balance')
        if not isinstance(value,(int,float)) or not math.isfinite(value): raise ProviderError('upstream_schema')
        return value

    async def upload_image(self, data_url):
        import base64
        try:
            header,encoded=data_url.split(',',1)
            if header not in ('data:image/png;base64','data:image/jpeg;base64'):raise ValueError()
            blob=base64.b64decode(encoded,validate=True)
            if len(blob)>1024*1024:raise ValueError()
        except Exception:raise ProviderError('invalid_reference_image') from None
        mime='image/png' if 'png' in header else 'image/jpeg'
        try:
            async with httpx.AsyncClient(transport=self.transport,timeout=45,follow_redirects=False) as client:
                response=await client.post(self.BASE+'/files',headers={'Authorization':'Bearer '+self.key},
                    files={'file':('reference.png' if mime=='image/png' else 'reference.jpg',blob,mime)})
            if response.status_code!=200 or len(response.content)>1024*1024:raise ProviderError('reference_upload_failed')
            value=response.json()
            token=value.get('data',{}).get('file_token')
            if value.get('code')!=0 or not isinstance(token,str) or not token or len(token)>1000:raise ProviderError('reference_upload_failed')
            return token
        except ProviderError:raise
        except Exception:raise ProviderError('reference_upload_failed') from None

    async def submit(self, prompt):
        data = await self.request('POST','/generation/text-to-model', {
            'model':self.settings.tripo_model, 'prompt':prompt, 'face_limit':3000,
            'quad':False, 'texture':False, 'pbr':False, 'export_uv':False})
        task = data.get('task_id')
        if not isinstance(task,str) or not task or len(task)>200 or '/' in task:
            raise ProviderError('upstream_schema', uncertain=True)
        return task

    async def task(self, task_id):
        return await self.request('GET','/tasks/'+task_id)

    async def fetch_image(self, url):
        """A picture made by a Tripo image task, from Tripo's asset hosts only, re-encoded as a JPEG of
        at most 1024 px (strips metadata, bounds the size the game downloads)."""
        import io
        from PIL import Image
        parsed = urlparse(url)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or parsed.port not in (None,443) or parsed.username or parsed.password:
            raise ProviderError('unsafe_asset_url')
        if host != 'tripo3d.ai' and not host.endswith('.tripo3d.ai') and not host.endswith('.tripo3d.com'):
            raise ProviderError('unapproved_asset_host')
        chunks, size = [], 0
        try:
            async with httpx.AsyncClient(transport=self.transport,timeout=60,follow_redirects=False) as client:
                async with client.stream('GET',url) as response:
                    if response.status_code != 200: raise ProviderError('asset_download_failed')
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 16*1024*1024: raise ProviderError('asset_too_large')
                        chunks.append(chunk)
        except httpx.HTTPError: raise ProviderError('asset_download_failed') from None
        return jpeg_preview(b''.join(chunks))

    async def download(self, url, allow_textures=False):
        parsed = urlparse(url)
        host = parsed.hostname or ''
        if parsed.scheme != 'https' or parsed.port not in (None,443) or parsed.username or parsed.password:
            raise ProviderError('unsafe_asset_url')
        if host != 'tripo3d.ai' and not host.endswith('.tripo3d.ai') and host!='tripo-data.rg1.data.tripo3d.com':
            raise ProviderError('unapproved_asset_host')
        chunks, size = [], 0
        try:
            # Separate client: never forward the Tripo Authorization header to asset hosts.
            async with httpx.AsyncClient(transport=self.transport,timeout=60,follow_redirects=False) as client:
                async with client.stream('GET',url) as response:
                    if response.status_code != 200: raise ProviderError('asset_download_failed')
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_GLB: raise ProviderError('asset_too_large')
                        chunks.append(chunk)
        except httpx.HTTPError: raise ProviderError('asset_download_failed') from None
        blob = b''.join(chunks)
        validate_glb(blob,allow_textures=allow_textures)
        return blob
