#!/bin/bash
# Wrap + deformation transfer onto target dir $T (default t2): no texture stage

cd "$(dirname "$0")/.."
B=/c/lsm26/triphthonS1/.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe
PY=/c/lsm26/triphthonS1/.tools/art-venv/Scripts/python.exe
T=${T:-t2}; W=$(cygpath -w $PWD); TW="$W/$T"; TAG=W
export EYE_PIN=${EYE_PIN:-contact}
WRAP_STAGE=export "$B" --background template_head.blend --python-exit-code 1 --python scripts/wrap_template.py -- template_features.json "$TW/target.blend" "$TW/target_features.json" "$TW" $TAG 2>&1 | grep -E "EXPORTED|Error"
$PY scripts/nricp.py $T/nricp_in_$TAG.npz $T/nricp_out_$TAG.npz 100,50,25,12,6,3,1.5,0.8,0.4 3 | tail -1
LIP_RINGS=${LIP_RINGS:-2} LIP_ITERS=${LIP_ITERS:-12} MC_ITERS=0 EAR_KEEP=1 WRAP_STAGE=import WRAP_FINAL_ITERS=30 WRAP_FINAL_RELAX=0.3 "$B" --background template_head.blend --python-exit-code 1 --python scripts/wrap_template.py -- template_features.json "$TW/target.blend" "$TW/target_features.json" "$TW" $TAG 2>&1 | grep -oE '"fit_surface[^}]*}|Error.*'
"$B" --background template_head.blend --python-exit-code 1 --python scripts/dt_io.py -- export "$TW/wrapped_$TAG.blend" "$TW/dt_in.npz" 2>&1 | grep -E "EXPORTED|Error"
$PY scripts/deform_transfer.py $T/dt_in.npz $T/dt_out.npz | tail -1
"$B" --background $T/wrapped_$TAG.blend --python-exit-code 1 --python scripts/dt_io.py -- import "$TW/dt_out.npz" "$TW/face_keys.blend" 2>&1 | grep -E "IMPORTED|Error"
echo T2_DONE
