"""Check original HAR caption bodies without displaying request URLs or headers."""
import base64
import io
import json
import re
import zipfile
from pathlib import Path

CUE = re.compile(r'(?m)^\s*(\d{1,2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3})')
def seconds(s):
    h,m,v=s.split(':')
    return int(h)*3600+int(m)*60+float(v)
result=[]
for group in ('character','environment'):
    with zipfile.ZipFile(Path('C:/Users/dd/Desktop')/f'stefan_{group}_files.zip') as archive:
        for name in archive.namelist():
            if not name.lower().endswith('.har'):
                continue
            har=json.loads(archive.read(name))
            spans=[]
            bodies=0
            other_timestamp_bodies=0
            caption_responses=0
            caption_empty=0
            playlist_durations=[]
            for item in har.get('log',{}).get('entries',[]):
                content=item.get('response',{}).get('content',{})
                mime=content.get('mimeType','')
                txt=content.get('text','')
                if 'vtt' in mime:
                    caption_responses+=1
                    caption_empty+=not bool(txt)
                if not txt:
                    continue
                if content.get('encoding')=='base64':
                    try: txt=base64.b64decode(txt).decode('utf-8',errors='replace')
                    except Exception: continue
                found=CUE.findall(txt)
                if found:
                    bodies+=1
                    other_timestamp_bodies+=('vtt' not in mime)
                    spans.extend(found)
                if '#EXTM3U' in txt and '#EXTINF:' in txt:
                    durations=re.findall(r'#EXTINF:([\d.]+)',txt)
                    playlist_durations.append(round(sum(map(float,durations)),3))
            unique=sorted(set(spans),key=lambda x:seconds(x[0]))
            gaps=[]
            if unique:
                cursor=seconds(unique[0][1])
                for a,b in unique[1:]:
                    start,end=seconds(a),seconds(b)
                    if start-cursor>=10: gaps.append([round(cursor,3),round(start,3)])
                    cursor=max(cursor,end)
            row={'course':group,'file':Path(name).name,
                 'caption_responses':caption_responses,'empty_caption_responses':caption_empty,
                 'bodies_with_cues':bodies,'non_vtt_bodies_with_cues':other_timestamp_bodies,
                 'unique_cues':len(unique),'first':unique[0][0] if unique else None,
                 'last_cue_start':unique[-1][0] if unique else None,
                 'last_cue_end':unique[-1][1] if unique else None,
                 'gaps_at_least_10_seconds':gaps,
                 'playlist_duration_totals':sorted(set(playlist_durations))}
            result.append(row)
            print(json.dumps(row,ensure_ascii=False))
folder=Path(__file__).resolve().parents[1]/'artifacts/stefan-course-audit-20261004'
(folder/'original-har-caption-coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
