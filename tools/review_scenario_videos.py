"""Sample requested generated videos, preserving original downloads."""
import json, shutil, subprocess
from pathlib import Path
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/production-lab-20261003'
VIDEOS=OUT/'videos';VIDEOS.mkdir(exist_ok=True)
assets=[('seedance2','Seedance 2.0', 'asset_9GdR1TRafJCjGtyMh9ZCLyFK',182,[720,1280]),
        ('pixverse6','PixVerse V6 I2V','asset_E7sDDK4HW2SLxndccQYtPeo4',50,[800,1200]),
        ('kling3','Kling V3 I2V Pro','asset_7GfVx9hx8ZtkbfTHaRmUbFEv',53,[1176,1764])]
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
times=[0,.4,1,1.8,2.8,3.8,4.8]
rows=[]
for name,label,asset,cost,size in assets:
 source=Path.home()/'Downloads'/(asset+'.mp4')
 dest=VIDEOS/(name+'.mp4')
 if not dest.exists():shutil.copyfile(source,dest)
 row=Image.new('RGB',(7*230,410),'#f4f1e9');d=ImageDraw.Draw(row)
 d.text((12,7),f'{label} | {cost} CU | native {size[0]}x{size[1]} | 5.04s',font=font,fill='#253b3a')
 for i,t in enumerate(times):
  frame=VIDEOS/f'{name}-{i}.png'
  subprocess.run([ffmpeg,'-y','-ss',str(t),'-i',str(dest),'-frames:v','1',str(frame)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  im=Image.open(frame);im.thumbnail((228,342))
  row.paste(im,(i*230+(230-im.width)//2,34))
  d.text((i*230+8,384),f'{t:.1f}s',font=font,fill='#253b3a')
 row.save(VIDEOS/(name+'-sheet.jpg'));rows.append(row)
sheet=Image.new('RGB',(1610,1230),'white')
for i,row in enumerate(rows):sheet.paste(row,(0,i*410))
sheet.save(OUT/'video-comparison.jpg')
p=OUT/'experiment.json';data=json.loads(p.read_text(encoding='utf-8'))
for run,(_,label,asset,cost,size) in zip(data['scenario_runs'],assets):
 run.update(asset_id=asset,actual_credits=cost,status='success',native_resolution=size,duration_s=5.04)
data['scenario_actual_spent']=sum(a[3] for a in assets)
data['tripo_actual_spent']=195;data['tripo_balance_after']=23110
p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('VIDEOS_REVIEW_READY',data['scenario_actual_spent'])
