from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'art/characters/npc_cast_idle_v11'
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
for key,frame,left,right in [('sora',15,40,165),('moru',1,195,308),('naru',25,335,451),('haeru',1,467,610)]:
 ref=Image.open(O/'reference'/f'frame-{frame:02}.png').convert('RGB').crop((left,0,right,345))
 actual=Image.open(O/key/'key-pose-front.png').convert('RGB').crop((75,0,525,800))
 canvas=Image.new('RGB',(900,850),(40,49,58));draw=ImageDraw.Draw(canvas)
 for im,x,label in [(ref,0,'참고 영상'),(actual,450,'수정한 게임 모델')]:
  scale=min(450/im.width,800/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS);canvas.paste(im,(x+(450-im.width)//2,50+(800-im.height)//2));draw.text((x+20,12),label,font=font,fill='white')
 canvas.save(O/key/'pose-comparison.png')
print('POSE_COMPARISONS_READY')
