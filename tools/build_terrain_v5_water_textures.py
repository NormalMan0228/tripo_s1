"""Seamless isotropic foam and a smooth physical shoreline distance field."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, distance_transform_edt, map_coordinates
from scipy.interpolate import LinearNDInterpolator
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/maps/archipelago_terrain_v5'
OUT.mkdir(parents=True,exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
rng=np.random.default_rng(831)
n=1024
# Filtered random Fourier spectra have no square noise lattice and tile exactly.
freq=np.hypot(np.fft.fftfreq(n)[:,None],np.fft.rfftfreq(n)[None,:])
def spectral(scale):
    source=rng.normal(size=(n,n))
    spectrum=np.fft.rfft2(source)*np.exp(-.5*(freq*scale)**2)
    result=np.fft.irfft2(spectrum,s=(n,n)).real
    return (result-result.mean())/result.std()
broad=spectral(180);middle=spectral(70);fine=spectral(24)
warp_x=spectral(200)*20;warp_y=spectral(210)*20
yy,xx=np.meshgrid(np.arange(n),np.arange(n),indexing='ij')
field=map_coordinates(broad*.56+middle*.30+fine*.14,[yy+warp_y,xx+warp_x],order=3,mode='wrap')
field=np.clip(.5+field*.18,0,1)
# Circular bubbles of several sizes cluster around the foam field; all edges
# are antialiased. The texture stores continuous organic density, not white cells.
bubbles=Image.new('L',(n*2,n*2),0);draw=ImageDraw.Draw(bubbles)
for i in range(7600):
    x,y=rng.integers(0,n,2);radius=rng.uniform(1.2,5.8)
    if field[y,x]<.33 and rng.random()<.75:continue
    for dx in [-n,0,n]:
        for dy in [-n,0,n]:
            cx=(x+dx)*2;cy=(y+dy)*2;r=radius*2
            draw.ellipse((cx-r,cy-r,cx+r,cy+r),outline=int(rng.uniform(130,250)),width=2)
micro=np.asarray(bubbles.resize((n,n),Image.Resampling.LANCZOS),float)/255
micro=gaussian_filter(micro,.35,mode='wrap')
pixels=np.dstack((field,np.clip(.5+fine*.14,0,1),micro))
Image.fromarray(np.uint8(np.clip(pixels,0,1)*255)).save(OUT/'textures/organic_foam.png')

# Smooth world-space cliff normals sampled from the actual height function,
# independent of the rendered mesh's triangles or UV tangent frames.
source=(ROOT/'tools/prepare_archipelago_v5.py').read_text()
namespace={'__file__':str(ROOT/'tools/prepare_archipelago_v5.py')}
exec(source[:source.index('contours=[];statistics=[]')],namespace)
island=namespace['DATA']['islands'][2];c=namespace['catmull'](island['outline'])
size=768;x,z=np.meshgrid(np.linspace(-14,7,size),np.linspace(-20,1,size))
signed=namespace['distance'](x,-z,c)
h=namespace['height'](x,-z,island,signed)
hz,hx=np.gradient(gaussian_filter(h,5.0),21/(size-1),21/(size-1))
normal=np.dstack((-hx,np.ones(h.shape),-hz));normal/=np.linalg.norm(normal,axis=2)[...,None]
Image.fromarray(np.uint8(np.clip(normal*.5+.5,0,1)*255)).save(OUT/'textures/headland_normals.png')

# Compute the true sea-level land mask, including the carved waterfall channel.
# Encoding the distance in two channels retains sub-millimetre value precision.
size=2048;x,z=np.meshgrid(np.linspace(-130,130,size),np.linspace(-110,115,size))
land=np.zeros(x.shape,bool)
for path in sorted(OUT.glob('0*.npz')):
    data=np.load(path);vertices=data['vertices']
    interpolator=LinearNDInterpolator(vertices[:,:2],vertices[:,2],fill_value=-8)
    x0,y0=vertices[:,:2].min(0);x1,y1=vertices[:,:2].max(0)
    mask=(x>=x0)&(x<=x1)&(-z>=y0)&(-z<=y1)
    values=interpolator(x[mask],-z[mask]);land[mask]|=values>0.015
    print('SHORE_MASK',path.stem,flush=True)
spacing=(225/(size-1),260/(size-1))
distance=distance_transform_edt(~land,sampling=spacing)-distance_transform_edt(land,sampling=spacing)
distance=gaussian_filter(distance,1.3)
encoded=np.uint16(np.clip((distance+24)/48,0,1)*65535)
dz,dx=np.gradient(distance,*spacing)
inward=np.dstack((-dx,-dz));inward/=np.maximum(np.linalg.norm(inward,axis=2)[...,None],1e-6)
rgba=np.dstack((encoded>>8,encoded&255,np.uint8(np.clip(inward[:,:,0]*.5+.5,0,1)*255),np.uint8(np.clip(inward[:,:,1]*.5+.5,0,1)*255))).astype('uint8')
Image.fromarray(rgba,'RGBA').save(OUT/'textures/shore_distance.png')
print('V5_WATER_TEXTURES_READY',flush=True)
