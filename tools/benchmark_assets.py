"""Reproducible developer-only Codex subscription experiment, never a player backend.

No API key, no tools, no external writes by the model. Each trial uses identical
contract and case text. Results retain failures; one trial is not a reliability claim.
"""
import argparse, json, os, pathlib, shutil, subprocess, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.asset_contract import prompt_for, parse_design
from server.asset_vm import AssetVM

CASES={
 'chest':'Cozy wooden chest. Separate body and lid. Clicking smoothly opens lid to -95 degrees around its rear edge; clicking again closes it. Use a generated hinge API.',
 'flower':'Flower lamp. Stem, center and exactly six petals. Nearby player opens all six petals smoothly, leaving closes them. Clicking cycles three center light hues. Write reusable easing and flower APIs.',
 'clock':'Mantel clock with a body and two independent hands. Minute hand does one revolution every 60 seconds, hour hand every 720 seconds. Clicking pauses BOTH hands and clicking again resumes from that angle; no jump while paused. Generate a clock API.',
 'static_vase':'Static cozy ceramic vase for a wooden shelf. Exactly one part with id vase. No movement, light or hue changes on any event. Preserve a muted sage green material. A numeric utility function is optional.',
 'windmill':'Small decorative windmill with exactly two rigid parts: body and rotor. Body has NO blades. Rotor has all four blades centered on its hub and parent body. Rotor spins about local Z, one revolution every FOUR seconds. Click pauses, click again resumes without a jump. Body must never rotate. Generate a reusable rotor API; wrap rotate_z into -180..180.',
 'lantern':'Cozy lantern with exactly two parts named base and lamp. Player approaching smoothly raises lamp emission from 0 to 2 within two seconds; leaving smoothly brings it back to 0 within two seconds. Click cycles exactly three lamp hue values. Keep all geometry still. Generate reusable brightness/easing APIs.',
 'mobile':'Kinetic table ornament. A stationary beam and exactly three pendants named pendant_1, pendant_2, pendant_3 with parent beam. Each pendant gently sways about local Z between -20 and +20 degrees with different phases, never all equal. Their pivots are at their top normalized Y=0.5. Click freezes all three angles; click again resumes without a jump. Generate reusable sway APIs.'}
MODELS=['gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra']
EFFORTS=['low','medium','high','xhigh']

def check_behavior(plan,program,case):
    vm=AssetVM(program,[p['id'] for p in plan['parts']]); poses={}
    def event(e,**kw):
        for c in vm.run(e,kw): poses[(c['target'],c['op'])]=c['value']
    event('spawn'); snapshots=[]
    for i in range(600):
        if i==20:event('click')
        if i==60:event('near',near=1)
        if i==300:event('leave')
        if i==400:event('click')
        event('tick',dt=1/60,time=i/60,near=int(60<=i<300))
        if i in (0,19,60,299,399,599):snapshots.append(dict((str(k),v) for k,v in poses.items()))
    # Objective bounded execution metric, not a visual/style score.
    return {'long_run_valid':True,'distinct_pose_snapshots':len({json.dumps(s,sort_keys=True) for s in snapshots}),
            'parts':len(plan['parts']),'functions':len(program['functions']),'snapshots':snapshots}

def run_trial(model,effort,case,out):
    key=model+'_'+effort+'_'+case; dest=out/key; dest.mkdir(exist_ok=True)
    resultfile=dest/'result.json'
    if resultfile.exists():return json.loads(resultfile.read_text())
    cli=pathlib.Path(os.environ['APPDATA'])/'npm/node_modules/@openai/codex/bin/codex.js'
    args=[shutil.which('node'),str(cli),'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
          '-s','read-only','--disable','shell_tool','--disable','multi_agent','--disable','tool_suggest',
          '-c','web_search="disabled"','-c',f'model_reasoning_effort="{effort}"','-m',model,
          '--json','-o',str(dest/'output.json'),'-']
    prompt=prompt_for(CASES[case]);(dest/'prompt.txt').write_text(prompt,encoding='utf-8')
    started=time.monotonic();result={'model':model,'effort':effort,'case':case,'billing':'Codex subscription; not API charge'}
    try:
        proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',cwd=out,creationflags=0x08000000 if os.name=='nt' else 0)
        stdout,_=proc.communicate(prompt,timeout=600)
        (dest/'events.jsonl').write_text(stdout,encoding='utf-8')
        result['exit_code']=proc.returncode
        for line in stdout.splitlines():
            try:ev=json.loads(line)
            except ValueError:continue
            if ev.get('type')=='turn.completed':result['usage']=ev.get('usage')
            if ev.get('type') in ('error','turn.failed'):result['provider_error']=str(ev)[:1000]
        if proc.returncode:result['status']='provider_failed'
        else:
            plan,program,report=parse_design((dest/'output.json').read_text(encoding='utf-8'))
            result.update(status='validated',validation=report,behavior=check_behavior(plan,program,case))
    except subprocess.TimeoutExpired:
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,creationflags=0x08000000)
        elif proc.poll() is None:proc.kill()
        stdout,_=proc.communicate();(dest/'events.jsonl').write_text(stdout,encoding='utf-8')
        result['status']='timeout'
    except Exception as exc:result.update(status='invalid_design',validation_error=type(exc).__name__+': '+str(exc)[:250])
    result['seconds']=round(time.monotonic()-started,2)
    resultfile.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('model','effort','case','status','seconds','usage')},ensure_ascii=True),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--models',nargs='+',default=MODELS);ap.add_argument('--efforts',nargs='+',default=EFFORTS);ap.add_argument('--cases',nargs='+',choices=list(CASES),default=['chest','flower','clock']);ap.add_argument('--out',type=pathlib.Path,default=ROOT/'artifacts/model-benchmark');args=ap.parse_args()
    out=args.out.resolve();out.mkdir(exist_ok=True)
    # Deliberately sequential: bounded account use; STOP file is checked before every call.
    for effort in args.efforts:
        for model in args.models:
            for case in args.cases:
                if (out/'STOP').exists():sys.exit(0)
                run_trial(model,effort,case,out)
