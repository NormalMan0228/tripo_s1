"""Check offline review links and package only its explicitly public file types."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib, json

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'artifacts/review'
ALLOWED={'.html','.json','.csv','.png','.jpg','.mp4'}

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('src','href','poster') and value:self.links.append(value)

files=[p for p in REVIEW.rglob('*') if p.is_file()]
issues=[];checked=0
for path in files:
    if path.suffix.lower() not in ALLOWED:issues.append({'file':str(path.relative_to(REVIEW)),'reason':'unexpected_type'})
    if path.suffix!='.html':continue
    parser=Links();parser.feed(path.read_text(encoding='utf-8'))
    for link in parser.links:
        url=urlsplit(link)
        if url.scheme or url.netloc or not url.path:continue
        target=(path.parent/unquote(url.path)).resolve();checked+=1
        if not target.is_relative_to(REVIEW.resolve()) or not target.is_file():
            issues.append({'file':str(path.relative_to(REVIEW)),'link':link,'reason':'missing_or_external_file'})
result={'files':len(files),'local_links_checked':checked,'issues':issues}
if not issues:
    archive=ROOT/'artifacts/Tripothon_Review_20261002.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED) as bundle:
        for path in sorted(files):bundle.write(path,Path('Tripothon_Review')/path.relative_to(REVIEW))
    with archive.open('rb') as stream:result['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    result['archive']=str(archive);result['bytes']=archive.stat().st_size
(ROOT/'artifacts/review-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True));raise SystemExit(bool(issues))
