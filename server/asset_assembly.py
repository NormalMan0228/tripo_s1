"""Blender-free assembly contracts and procedural GLB fixtures.

Live generated parts use the same normalized bounding-box binding contract.
Pivot placement is a proposal, never evidence that semantic auto-rigging succeeded.
"""
import json
import math
import struct
import zlib
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .asset_vm import ProgramError, name


class Part(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    id: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_]{0,47}$')
    parent: str = ''
    prompt: str = Field(min_length=3, max_length=800)
    shape: Literal['box', 'ellipsoid', 'petal'] = 'box'
    size: list[float] = Field(min_length=3, max_length=3)
    position: list[float] = Field(min_length=3, max_length=3)
    rotation: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    pivot: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    color: str = Field(default='#eadab8', pattern=r'^#[0-9a-fA-F]{6}$')

    @field_validator('size')
    @classmethod
    def dimensions(cls, v):
        if any(not .02 <= x <= 3 for x in v): raise ValueError('invalid_size')
        return v

    @field_validator('position')
    @classmethod
    def positions(cls, v):
        if any(abs(x) > 3 for x in v): raise ValueError('invalid_position')
        return v

    @field_validator('rotation')
    @classmethod
    def rotations(cls, v):
        if any(abs(x) > 360 for x in v): raise ValueError('invalid_rotation')
        return v

    @field_validator('pivot')
    @classmethod
    def pivots(cls, v):
        if any(abs(x) > .5 for x in v): raise ValueError('pivot_outside_bounds')
        return v


class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=60)
    category: str = Field(min_length=1, max_length=40)
    parts: list[Part] = Field(min_length=1, max_length=8)


def validate_plan(data):
    plan = Plan.model_validate(data).model_dump()
    ids = [p['id'] for p in plan['parts']]
    if len(ids) != len(set(ids)): raise ProgramError('duplicate_part')
    parents = {p['id']: p['parent'] for p in plan['parts']}
    for part in ids:
        visited = set()
        while part:
            if part not in parents or part in visited: raise ProgramError('invalid_part_hierarchy')
            visited.add(part); part = parents[part]
    # Binding keys are object-local, never arbitrary paths into the Godot scene.
    return plan


def simple_plan(request):
    """The cheapest craft: the player's words go straight to Tripo as one static
    mesh. No LLM design step, no moving parts."""
    words=' '.join(request.split())[:300]
    return validate_plan({'title':words[:60] or 'object','category':'decoration','parts':[{
        'id':'whole','parent':'','prompt':('A single simple stylized game prop, clean silhouette, no base plate: '+words)[:800],
        'shape':'box','size':[1.2,1.2,1.2],'position':[0,.6,0],'color':'#c9a46e'}]})


def static_plan(plan,request):
    """Static furniture is one complete mesh, never separately billed hidden parts."""
    if len(plan['parts'])==1:return plan
    first=plan['parts'][0]
    prompt=('Complete assembled static furniture. '+request+' Visual components: '+
            '; '.join(p['prompt'] for p in plan['parts']))[:800]
    return validate_plan({'title':plan['title'],'category':plan['category'],'parts':[{
        'id':'whole','parent':'','prompt':prompt,'shape':first['shape'],
        'size':[1.5,1.5,1.5],'position':[0,.75,0],'color':first['color']}]})


def _png():
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw = b''.join(b'\0'+b''.join(bytes((210,180,140) if (x+y)%2 else (245,226,194)) for x in range(4)) for y in range(4))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',4,4,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


def fixture_glb(shape, textured=False):
    """Small, UV-mapped procedural test part, not a claimed AI generation."""
    vertices, normals, uv, indices = [], [], [], []
    if shape == 'box':
        for n,u,v in [((1,0,0),(0,0,-1),(0,1,0)),((-1,0,0),(0,0,1),(0,1,0)),
                      ((0,1,0),(1,0,0),(0,0,-1)),((0,-1,0),(1,0,0),(0,0,1)),
                      ((0,0,1),(1,0,0),(0,1,0)),((0,0,-1),(-1,0,0),(0,1,0))]:
            start=len(vertices)
            for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]:
                vertices.append(tuple((n[k]+a*u[k]+b*v[k])*.5 for k in range(3)))
                normals.append(n);uv.append(((a+1)/2,(b+1)/2))
            indices.extend(start+i for i in [0,1,2,0,2,3])
    else:
        for y in range(13):
            phi=math.pi*y/12
            for x in range(25):
                theta=2*math.pi*x/24
                p=(math.sin(phi)*math.cos(theta),math.cos(phi),math.sin(phi)*math.sin(theta))
                vertices.append(tuple(t*.5 for t in p));normals.append(p);uv.append((x/24,y/12))
        for y in range(12):
            for x in range(24):
                a=y*25+x;b=a+25;indices.extend([a,a+1,b,a+1,b+1,b])
    blob=bytearray();views=[];access=[]
    def data(raw):
        while len(blob)%4:blob.append(0)
        index=len(views);views.append({'buffer':0,'byteOffset':len(blob),'byteLength':len(raw)});blob.extend(raw);return index
    def attr(values,fmt,typ,component):
        raw=b''.join(struct.pack('<'+fmt,*v) for v in values)
        access.append({'bufferView':data(raw),'componentType':component,'count':len(values),'type':typ})
        return len(access)-1
    pos=attr(vertices,'fff','VEC3',5126);access[pos].update(min=[min(v[k] for v in vertices) for k in range(3)],max=[max(v[k] for v in vertices) for k in range(3)])
    nor=attr(normals,'fff','VEC3',5126);tex=attr(uv,'ff','VEC2',5126);idx=attr([(i,) for i in indices],'H','SCALAR',5123)
    mat={'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':.8}}
    doc={'asset':{'version':'2.0','generator':'Tripothon procedural fixture; no AI'},'scene':0,'scenes':[{'nodes':[0]}],
         'nodes':[{'name':'Surface','mesh':0}], 'meshes':[{'primitives':[{'attributes':{'POSITION':pos,'NORMAL':nor,'TEXCOORD_0':tex},'indices':idx,'material':0}]}],
         'materials':[mat],'bufferViews':views,'accessors':access}
    if textured:
        doc['images']=[{'bufferView':data(_png()),'mimeType':'image/png'}];doc['textures']=[{'source':0}]
        mat['pbrMetallicRoughness']['baseColorTexture']={'index':0}
    doc['buffers']=[{'byteLength':len(blob)}]
    while len(blob)%4:blob.append(0)
    js=json.dumps(doc,separators=(',',':')).encode();js+=b' '*((-len(js))%4)
    return struct.pack('<III',0x46546c67,2,28+len(js)+len(blob))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(blob),0x004e4942)+blob


def demo_design(prompt):
    """Explicit offline fixtures. No claim that this is an LLM prompt interpreter."""
    low=prompt.lower()
    def part(id,shape,size,position,pivot=None,rotation=None,color='#d8ab6a',parent=''):
        return dict(id=id,parent=parent,prompt='A standalone '+id,shape=shape,size=size,position=position,pivot=pivot or [0,0,0],rotation=rotation or [0,0,0],color=color)
    empty={'version':1,'state':{},'functions':{},'events':{}}
    if any(x in low for x in ['꽃','flower']):
        parts=[part('stem','box',[.1,1,.1],[0,.5,0],color='#598779'),part('center','ellipsoid',[.3,.15,.3],[0,1.05,0],color='#f2c86d')]
        for i in range(6):
            angle=i*60
            parts.append(part('petal'+str(i),'petal',[.34,.85,.12],[0,1,0],pivot=[0,-.5,0],rotation=[0,angle,0],color='#e8a9a7'))
        body=[['emit','rotate_x','petal'+str(i),['mul',['var','a'],65]] for i in range(6)]
        functions={'open_flower':{'params':['a'],'body':body,'return':0},
                   'ease':{'params':['x'],'body':[],'return':['mul',['mul',['var','x'],['var','x']],['sub',3,['mul',2,['var','x']]]]}}
        program={'version':1,'state':{'open':0,'progress':0,'clicks':0},'functions':functions,'events':{
            'click':[['store','open',['not',['state','open']]],['store','clicks',['add',['state','clicks'],1]],['emit','hue','center',['div',['mod',['state','clicks'],6],6]]],
            'near':[['store','open',1]],'leave':[['store','open',0]],
            'tick':[['store','progress',['add',['state','progress'],['mul',['sub',['state','open'],['state','progress']],['min',1,['mul',5,['input','dt']]]]]],['do',['call','open_flower',['call','ease',['state','progress']]]]]}}
        return validate_plan({'title':'꽃 조명 · 오프라인 시연','category':'flower_lamp','parts':parts}),program
    if any(x in low for x in ['시계','clock']):
        parts=[part('body','box',[1.05,1.05,.16],[0,.65,0],color='#73998e'),part('hand','box',[.04,.4,.035],[0,.65,.12],pivot=[0,-.5,0],color='#f4db9a')]
        empty['functions']={'clock_angle':{'params':['seconds'],'body':[],'return':['mul',['mod',['var','seconds'],60],-6]}}
        empty['events']={'tick':[['emit','rotate_z','hand',['call','clock_angle',['input','time']]]]}
        # Host z rotation range is +/-180; wrap to that interval.
        empty['functions']['clock_angle']['return']=['sub',['mod',['mul',['var','seconds'],-6],360],180]
        return validate_plan({'title':'시계 · 오프라인 시연','category':'clock','parts':parts}),empty
    parts=[part('body','box',[1.2,.65,.8],[0,.325,0]),part('lid','box',[1.2,.12,.8],[0,.69,-.4],pivot=[0,0,-.5],color='#8f6244')]
    empty.update(state={'open':0,'angle':0},functions={'hinge_angle':{'params':['amount'],'body':[],'return':['mul',['var','amount'],-95]}},events={
        'click':[['store','open',['not',['state','open']]]],
        'tick':[['store','angle',['add',['state','angle'],['mul',['sub',['state','open'],['state','angle']],['min',1,['mul',5,['input','dt']]]]]],['emit','rotate_x','lid',['call','hinge_angle',['state','angle']]]]})
    return validate_plan({'title':'상자 · 오프라인 시연','category':'chest','parts':parts}),empty
