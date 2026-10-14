#!/bin/bash
# t2 full shape chain: wrap+DT -> lids -> lash flap -> parts -> groups -> review colours
cd "$(dirname "$0")/.."
B=/c/lsm26/triphthonS1/.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe; W=$(cygpath -w $PWD)
export CAV_ZC=${CAV_ZC:-0.442} CAV_AX=${CAV_AX:-0.095} CAV_AZ=${CAV_AZ:-0.046} CAV_DEPTH=${CAV_DEPTH:-0.22} EYE_PIN=${EYE_PIN:-contact}
bash scripts/build_t2.sh | tail -1
OVERLAP=${OVERLAP:-0.22} N_UP=7 N_LO=5 FALL_UP=6 FALL_LO=4 "$B" --background t2/face_keys.blend --python-exit-code 1 --python scripts/build_lids.py -- "$W/t2/face_lids.blend" t2/lids_report.json 2>&1 | grep -E "Error|line [0-9]"
"$B" --background t2/face_lids.blend --python-exit-code 1 --python scripts/check_blink.py 2>&1 | grep "eyeBlinkLeft "
if [ "${FLAP:-0}" = "1" ]; then ROOT=${ROOT:-margin} LIFT=${LIFT:-0.2} CURL=${CURL:-1.6} "$B" --background t2/face_lids.blend --python-exit-code 1 --python scripts/lash_flap.py -- "$W/t2/face_flap.blend" t2/flap_report.json 2>&1 | grep -E "Error|Trace"; IN=t2/face_flap.blend; else IN=t2/face_lids.blend; fi
CAV_IT=0 "$B" --background $IN --python-exit-code 1 --python scripts/assemble_t2.py -- "$W/open/closed.blend" "$W/t2/face_parts.blend" 2>&1 | grep -E "Error|line [0-9]"
"$B" --background t2/face_parts.blend --python-exit-code 1 --python scripts/part_groups.py -- "$W/t2/face_parts.blend" 2>&1 | grep -E "Error|line [0-9]"
"$B" --background t2/face_parts.blend --python-exit-code 1 --python scripts/matcolor.py -- "$W/t2/face_parts.blend" 2>&1 | grep Error
echo ALL_DONE
