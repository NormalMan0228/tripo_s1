"""Prepare/capture each downloaded asset; never submit generation jobs."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/maps/archipelago_objects_v1'
BLENDER=ROOT/'.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe'
GODOT=ROOT/'.tools/godot/Godot_v4.7.2-stable_win64_console.exe'
PYTHON=ROOT/'.tools/art-venv/Scripts/python.exe'
LAB=ROOT/'labs/archipelago_object_lab'
queue=json.loads((BASE/'queue.json').read_text(encoding='utf-8'))
assets=queue['active_batch']['assets']
start=time.monotonic()

def execute(command,log):
    with log.open('w',encoding='utf-8') as output:
        result=subprocess.run([str(value) for value in command],cwd=ROOT,stdout=output,
                    stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('local_review_command_failed:'+log.name)

for asset in assets:
    out=BASE/asset
    mesh_report = json.loads((out/'mesh_verification.json').read_text(encoding='utf-8')) if (out/'mesh_verification.json').exists() else {}
    review_report = json.loads((out/'review_verification.json').read_text(encoding='utf-8')) if (out/'review_verification.json').exists() else {}
    requires_calibration = next(item for item in queue['items'] if item['id']==asset)['category'] != 'building'
    prepared=bool(mesh_report) and (not requires_calibration or mesh_report.get('material_calibration_version')==1)
    if asset=='28_beach_umbrella' and mesh_report.get('cloth_sector_geometry_version')!=1:
        prepared=False
    if asset=='20_pier' and mesh_report.get('open_approaches_version')!=2:
        prepared=False
    if (out/'review_verification.json').exists() and prepared and review_report.get('review_camera_version')==2:
        print('REVIEW_PRESERVED',asset,flush=True)
        continue
    while not (out/'generation-result.json').exists():
        if time.monotonic()-start>3600:
            raise RuntimeError('waiting_for_batch_generation')
        time.sleep(3)
    result=json.loads((out/'generation-result.json').read_text(encoding='utf-8'))
    if result['status']!='success':
        print('REVIEW_SKIPPED_FAILED_GENERATION',asset,flush=True)
        continue
    print('PREPARING_REVIEW',asset,flush=True)
    if not prepared:
        execute([BLENDER,'--background','--python-exit-code','1','--python','tools/prepare_archipelago_building_review.py','--','--asset',asset],out/'blender_prepare.log')
        execute([GODOT,'--headless','--path',LAB,'--editor','--import','--quit'],out/'godot_import.log')
    execute([GODOT,'--path',LAB,'--','--capture-review','--asset',asset],out/'godot_capture.log')
    execute([PYTHON,'tools/finalize_archipelago_object_review.py','--asset',asset],out/'review_finalize.log')
    print('REVIEW_READY',asset,flush=True)
print('BATCH_LOCAL_REVIEWS_COMPLETE',flush=True)
