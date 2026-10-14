#!/bin/bash
# Full base chain: wrap export -> NRICP -> import/final fit -> UV pack + bake -> deformation transfer of template keys
set -e
cd "$(dirname "$0")/.."
B=/c/lsm26/triphthonS1/.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe
PY=/c/lsm26/triphthonS1/.tools/art-venv/Scripts/python.exe
W=$(cygpath -w $PWD); TAG=${1:-K}
WRAP_STAGE=export "$B" --background template_head.blend --python-exit-code 1 --python scripts/wrap_template.py -- template_features.json "$W/target.blend" "$W/target_features.json" "$W" $TAG 2>&1 | grep -E "EXPORTED|Error"
$PY scripts/nricp.py nricp_in_$TAG.npz nricp_out_$TAG.npz 100,50,25,12,6,3,1.5,0.8,0.4 3 | tail -1
LIP_RINGS=${LIP_RINGS:-2} LIP_ITERS=${LIP_ITERS:-12} MC_ITERS=${MC_ITERS:-0} EAR_KEEP=1 WRAP_STAGE=import WRAP_FINAL_ITERS=30 WRAP_FINAL_RELAX=0.3 "$B" --background template_head.blend --python-exit-code 1 --python scripts/wrap_template.py -- template_features.json "$W/target.blend" "$W/target_features.json" "$W" $TAG 2>&1 | grep -oE '"fit_surface[^}]*}|Error.*'
"$B" --background wrapped_$TAG.blend --python-exit-code 1 --python scripts/bake_texture.py -- "$W/face_base.blend" "$W/textures" 2048 2>&1 | grep -E "BAKED|Error"
"$B" --background template_head.blend --python-exit-code 1 --python scripts/dt_io.py -- export "$W/face_base.blend" "$W/dt_in.npz" 2>&1 | grep -E "EXPORTED|Error"
$PY scripts/deform_transfer.py dt_in.npz dt_out.npz | tail -1
"$B" --background face_base.blend --python-exit-code 1 --python scripts/dt_io.py -- import "$W/dt_out.npz" "$W/face_keys.blend" 2>&1 | grep -E "IMPORTED|Error"
