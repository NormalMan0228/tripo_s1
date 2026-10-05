"""Install official MPFB in the isolated face-v3 Blender profile."""
import bpy
import addon_utils
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'.tools/blender-profiles/face-v3'
assert Path(bpy.utils.user_resource('CONFIG')).resolve()==(PROFILE/'config').resolve()
if 'bl_ext.user_default.mpfb' not in bpy.context.preferences.addons:
    result=bpy.ops.extensions.package_install_files(filepath=str(ROOT/'.tools/face-tools/mpfb-2.0.17.zip'),repo='user_default',enable_on_install=True)
    assert 'FINISHED' in result, result
addon_utils.enable('rigify',default_set=True,persistent=True)
assert addon_utils.check('rigify')[1]
bpy.ops.wm.save_userpref()
report={'blender':bpy.app.version_string,'profile':str(PROFILE),'addons':list(bpy.context.preferences.addons.keys())}
(ROOT/'.tools/face-tools/install.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FACE_STACK_INSTALLED',json.dumps(report),flush=True)
