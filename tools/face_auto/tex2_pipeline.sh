#!/bin/bash
# tex2: per-part UV + image textures for a rigged face asset (replaces the per-vertex 'ref_color' of project_texture.py).
# usage: tex2_pipeline.sh <rigged.blend> <ref_dir> <landmarks.json> <eyes.json> <out_dir> [style] [size] [--margin-fit] [--atlas]
#   rigged.blend : objects 'face' (eye_ring / eye_u / mouth_ring / mouth_u attributes, slots skin + mouth_inner),
#                  'eyes', optional 'p2_brows', 'teeth_up', 'teeth_lo', 'tongue' (any shape keys / armature kept)
#   ref_dir      : 01_front.png (+ optional 02_left.png 03_back.png 04_right.png)
#   eyes.json    : eye_fit_ref eyes_meta.json (C, r, iris_dir, iris_radius_deg used as given) or loop_organs eyes_eyes.json
#   style        : realistic | semi | cartoon | anime (iris clean-up, sclera vessels) - default realistic
#   size         : skin texture size, default 4096
#   --margin-fit : pin the photo's MediaPipe eye contour onto the mesh lid margin (older bases whose lids do not
#                  match the photo; not needed for eye-fit bases, never for cartoon / anime eyes)
#   --atlas      : also write the one-material atlas variant (asset_atlas.blend)
# out: <out_dir>/asset.blend (materials with image textures, UV map 'uv_tex'), skin.png eyes.png brows.png teeth.png
#      tongue.png, uv/ (uv.blend + per-part mesh npz + uv_qa.json), bake_qa.json, eyes_qa.json, logs
B=${BLENDER:-/c/lsm26/triphthonS1/.tools/blender-portable/blender-4.5.3-windows-x64/blender.exe}
PY=${ARTPY:-/c/lsm26/triphthonS1/.tools/art-venv/Scripts/python.exe}
T=$(cd "$(dirname "$0")" && pwd)
SRC=$1; REF=$2; LM=$3; EJ=$4; o=$5; ST=${6:-realistic}; SZ=${7:-4096}
MF=""; AT=""; for x in "$@"; do [ "$x" = --margin-fit ] && MF=--margin-fit; [ "$x" = --atlas ] && AT=1; done
for f in "$SRC" "$REF/01_front.png" "$LM" "$EJ"; do [ -e "$f" ] || { echo "tex2 FAIL missing $f"; exit 1; }; done
u=$o/uv; L=$o/log; mkdir -p "$u"; t0=$(date +%s)
"$B" -b "$SRC" -P "$T/uv_parts.py" -- "$LM" "$EJ" "$u" > "$L.uv.txt" 2>&1 || { echo "tex2 FAIL uv"; tail -5 "$L.uv.txt"; exit 1; }
"$PY" -I "$T/bake_ref_texture.py" "$u" "$REF" "$LM" "$o" --size $SZ $MF > "$L.bake.txt" 2>&1 || { echo "tex2 FAIL bake"; tail -5 "$L.bake.txt"; exit 1; }
"$PY" -I "$T/eye_iris_texture.py" "$u" "$REF" "$LM" "$o" --style $ST $MF > "$L.eye.txt" 2>&1 || { echo "tex2 FAIL eye"; tail -5 "$L.eye.txt"; exit 1; }
"$PY" -I "$T/mouth_textures.py" "$o" > "$L.mouth.txt" 2>&1 || { echo "tex2 FAIL mouth"; exit 1; }
"$B" -b "$u/uv.blend" -P "$T/tex_assign.py" -- "$o" "$o/asset.blend" > "$L.assign.txt" 2>&1 || { echo "tex2 FAIL assign"; tail -5 "$L.assign.txt"; exit 1; }
if [ -n "$AT" ]; then
  "$PY" -I "$T/atlas_pack.py" "$o" > "$L.atlas.txt" 2>&1 && \
  "$B" -b "$u/uv.blend" -P "$T/tex_assign.py" -- "$o" "$o/asset_atlas.blend" --atlas "$o/atlas.json" >> "$L.atlas.txt" 2>&1
fi
rm -f "$o"/*.blend1
echo "tex2 done $(basename "$o"): $(( $(date +%s) - t0 ))s -> $o/asset.blend | $(grep -o '"texels_filled": [0-9.]*' "$o/bake_qa.json")"
