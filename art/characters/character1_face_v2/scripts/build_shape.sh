#!/bin/bash
# Shape-stage chain (no texture): base wrap + DT keys -> lid rig -> lash flap -> review colours
set -e
cd "$(dirname "$0")/.."
B=/c/lsm26/triphthonS1/.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe; W=$(cygpath -w $PWD)
EYE_PIN=${EYE_PIN:-opening} bash scripts/build_base.sh K | grep -E "Error|IMPORTED"
OVERLAP=${OVERLAP:-0.22} N_UP=7 N_LO=5 FALL_UP=6 FALL_LO=4 "$B" --background face_keys.blend --python-exit-code 1 --python scripts/build_lids.py -- "$W/face_lids.blend" lids_report.json 2>&1 | grep -E "Error|line [0-9]" || true
ROOT=margin LIFT=${LIFT:-0.2} CURL=${CURL:-1.6} "$B" --background face_lids.blend --python-exit-code 1 --python scripts/lash_flap.py -- "$W/face_flap.blend" flap_report.json 2>&1 | grep -E "Error|Trace" || true
"$B" --background face_flap.blend --python-exit-code 1 --python scripts/matcolor.py -- "$W/face_flap.blend" 2>&1 | grep Error || true
echo SHAPE_DONE
