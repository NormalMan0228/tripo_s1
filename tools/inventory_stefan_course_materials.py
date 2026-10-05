"""Inspect user-supplied course archives; never emit HAR credentials or headers."""
import io,json,zipfile
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/stefan-course-audit-20261004'
OUT.mkdir(exist_ok=True)
inventory={}
for course in ['character','environment']:
 path=Path('C:/Users/dd/Desktop')/f'stefan_{course}_files.zip'
 records=[]
 with zipfile.ZipFile(path) as outer:
  for info in outer.infolist():
   if info.is_dir():continue
   record={'path':info.filename,'bytes':info.file_size}
   if info.filename.lower().endswith('.zip'):
    with zipfile.ZipFile(io.BytesIO(outer.read(info))) as inner:
     files=[{'path':x.filename,'bytes':x.file_size} for x in inner.infolist() if not x.is_dir()]
     record['files']=files
     record['types']=dict(Counter(Path(x['path']).suffix.lower() for x in files))
     # Save only prose source materials. Filenames are contained in a unique
     # per-archive folder; no archive paths are used as filesystem targets.
     dest=OUT/'supplied-materials'/course/Path(info.filename).stem
     for x in inner.infolist():
      if x.is_dir():continue
      if Path(x.filename).suffix.lower() in ['.pdf','.txt','.md','.srt','.vtt','.docx','.html']:
       dest.mkdir(parents=True,exist_ok=True)
       safe=Path(x.filename.replace('\\','/')).name
       (dest/safe).write_bytes(inner.read(x))
   records.append(record)
 inventory[course]=records
 print(course,json.dumps([{'archive':x['path'],'files':len(x.get('files',[])),'types':x.get('types',{})} for x in records if 'files' in x],ensure_ascii=False),flush=True)
(OUT/'nested-archive-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
