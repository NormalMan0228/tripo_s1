"""Publish a local-only review bundle of selected public evidence, never DBs or keys."""
import json,shutil,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/review'
OUT.mkdir(exist_ok=True)
media=['furniture-showcase.png','furniture-showcase.mp4','h3-furniture-showcase.png','h3-furniture-showcase.mp4',
       'repaired-furniture-showcase.png','repaired-furniture-showcase.mp4','home-exterior.png','home-interior.png',
       'studio-binding.png','studio-e2e.png','village-furniture.png','explorer-b-game.png','explorer-b-tool.png',
       'model-gallery.png','model-gallery.mp4','design-preview-chest.png','design-preview-flower.png','story-journal.png','generated-controls.png',
       'region-quarry.png','region-frost.png','survival-night.png','reference-model-gallery.png','reference-model-gallery.mp4']
for name in media:
    path=ROOT/'artifacts'/name
    if path.is_file():shutil.copy2(path,OUT/name)
for region in ('quiet_quarry','returning_light'):
    path=ROOT/'artifacts'/('story-'+region+'-verified')/'full-run-victory.png'
    if path.exists():shutil.copy2(path,OUT/('story-'+region+'.png'))
aggregate=ROOT/'artifacts/model-comparison'
gate=ROOT/'artifacts/publication-gate/index.html'
if gate.exists():
    target=OUT/'publication-gate';target.mkdir(exist_ok=True);shutil.copy2(gate,target/'index.html')
if (aggregate/'index.html').exists():
    target=OUT/'model-comparison';target.mkdir(exist_ok=True)
    for name in ('index.html','summary.csv'):shutil.copy2(aggregate/name,target/name)
cohorts=[]
for name in sorted(p.name for p in (ROOT/'artifacts').glob('model-benchmark*') if p.is_dir()):
    src=ROOT/'artifacts'/name
    if not (src/'summary.json').exists():continue
    raw=json.loads((src/'summary.json').read_text(encoding='utf-8'))
    cohorts.append({'name':name,'summary':raw['summary'],'trials':len(raw['results'])})
    dest=OUT/name;dest.mkdir(exist_ok=True)
    if (src/'references').is_dir():shutil.copytree(src/'references',dest/'references',dirs_exist_ok=True)
    for filename in ['index.html','summary.csv']:
        if (src/filename).exists():shutil.copy2(src/filename,dest/filename)
    for trial in src.glob('*/output.json'):
        target=dest/trial.parent.name;target.mkdir(exist_ok=True);shutil.copy2(trial,target/'output.json')
        wire=trial.parent/'wire-output.json'
        if wire.exists():shutil.copy2(wire,target/wire.name)
balance=json.loads((ROOT/'artifacts/chest-body-refinement/balance-after.json').read_text())['balance']
spent=1070
picture=ROOT/'artifacts/picture-furniture-20261002'
if (picture/'balance-after.json').exists():
    balance=json.loads((picture/'balance-after.json').read_text())['balance']
    spent+=json.loads((picture/'balance-before.json').read_text())['balance']-balance
if (picture/'public/index.html').exists():
    target=OUT/'picture-experiment';shutil.copytree(picture/'public',target,dirs_exist_ok=True)
    index=target/'index.html';index.write_text(index.read_text(encoding='utf-8').replace('../../review/index.html','../index.html'),encoding='utf-8')
value={'cohorts':cohorts,'tripo_balance':balance,'tripo_measured_spend':spent,
       'updated':datetime.datetime.now().astimezone().isoformat(timespec='minutes')}
template=(ROOT/'tools/review_site.html').read_text(encoding='utf-8')
(OUT/'index.html').write_text(template.replace('__REVIEW_DATA__',json.dumps(value,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')
print(json.dumps({'review':str(OUT/'index.html'),'media':len([p for p in OUT.iterdir() if p.is_file()]),'private_data_included':False}))
