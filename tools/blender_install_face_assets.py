import bpy
import json
import zipfile
from pathlib import Path
from bl_ext.user_default.mpfb.services.locationservice import LocationService
from bl_ext.user_default.mpfb.services.assetservice import AssetService
from bl_ext.user_default.mpfb.services.faceservice import FaceService

ROOT=Path(__file__).resolve().parents[1]
data=Path(LocationService.get_user_data()).resolve()
assert data.is_relative_to((ROOT/'.tools/blender-profiles/face-v3').resolve())
for name in ['makehuman_system_assets_cc0.zip','faceunits01.zip','visemes01.zip','visemes02.zip']:
    path=ROOT/'.tools/face-tools'/name
    with zipfile.ZipFile(path) as archive:
        assert all((data/n).resolve().is_relative_to(data) for n in archive.namelist())
    result=bpy.ops.mpfb.load_pack(filepath=str(path))
    assert 'FINISHED' in result
    print('INSTALLED_PACK',name,flush=True)
AssetService.rescan_pack_metadata()
assert AssetService.system_assets_pack_is_installed()
assert FaceService.is_faceunits01_installed(force_recheck=True)
report={'data':str(data),'packs':AssetService.get_pack_names(),'bodyparts':{name:[str(p.relative_to(data)) for p in (data/name).rglob('*.mhclo')] for name in ['eyes','eyebrows','eyelashes','teeth','tongue']}}
(ROOT/'.tools/face-tools/assets.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ASSETS',json.dumps(report),flush=True)
bpy.ops.wm.save_userpref()
