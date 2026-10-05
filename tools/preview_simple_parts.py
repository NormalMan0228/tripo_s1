"""Lay out six existing reference images; retain the old plan as history."""
from pathlib import Path
import hashlib
import json
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "art/references/explorer_b_modular_v1/02_parts_simple_v2"
MANIFEST = BASE / "generation-manifest-v2.json"
PLAN = ROOT / "art/characters/explorer_b_modular_v1/production-plan.json"


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("presentation") == "individual_images_only":
        raise RuntimeError("The user requested individual images only. Do not rebuild the historical contact sheet; use the PNG paths in generation-manifest-v2.json.")
    canvas = Image.new("RGB", (1560, 1275), "#f4f4ee")
    draw = ImageDraw.Draw(canvas)
    font = "C:/Windows/Fonts/malgun.ttf"
    title = ImageFont.truetype(font, 30)
    label = ImageFont.truetype(font, 24)
    small = ImageFont.truetype(font, 17)
    draw.text((30, 19), "B형 탐험가 · 간소화한 부품 이미지", font=title, fill="#203635")
    draw.text((30, 66), "신체: 머리 / 몸 / 손 · 재킷: 소매 포함 · 바지: 주머니 포함 · 벨트: 버클 포함", font=small, fill="#63746d")
    labels = {"head":"머리", "body":"몸（목·팔·다리·발 포함）", "hand":"손（한쪽 기준）",
              "jacket":"재킷（소매 포함）", "pants":"바지（주머니 포함）", "belt":"벨트（버클 포함）"}
    for i, asset in enumerate(manifest["assets"]):
        path = BASE / asset["file"]
        with Image.open(path) as image:
            asset["pixels"] = list(image.size)
            # Document thumbnail layout only. Original assets are left untouched.
            thumb = ImageOps.contain(image.convert("RGB"), (470, 460), Image.Resampling.LANCZOS)
        asset["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        x, y = 30 + (i % 3) * 510, 106 + (i // 3) * 558
        draw.rounded_rectangle((x, y, x + 480, y + 540), radius=12, fill="white", outline="#dfe5db")
        canvas.paste(thumb, (x + (480 - thumb.width) // 2, y + 12 + (460 - thumb.height) // 2))
        draw.text((x + 16, y + 487), labels[asset["id"]], font=label, fill="#203635")
    draw.text((30, 1231), "2D 수정안 · 실제 조립 비율이나 리깅 검증 결과를 뜻하지 않습니다", font=small, fill="#63746d")
    preview = BASE / "simple-parts-v2.jpg"
    canvas.save(preview, quality=95, subsampling=0)
    manifest["preview"] = preview.name
    write_json(MANIFEST, manifest)

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    old_plan = PLAN.with_name("production-plan-detailed-v1.json")
    if not old_plan.exists():
        old_plan.write_bytes(PLAN.read_bytes())
    plan.update(revision="simple_v2_20261003", state="simple_part_references_awaiting_user_review",
                active_stage="references", reference_revision="simple_v2",
                superseded_plan=str(old_plan.relative_to(ROOT)).replace("\\", "/"),
                body_part_count=4, body_reference_groups=["head", "body", "hands"], authoring_part_count=11)
    specs = [
        ("head_skin","body","머리 피부","head"), ("body","body","목·몸통·팔·다리·발 일체","body"),
        ("hand_R","body","오른손","hand"), ("hand_L","body","왼손（대칭 제작）","hand"),
        ("hair","hair","헤어",None), ("jacket","clothing","재킷（소매·소매단 포함）","jacket"),
        ("shirt","clothing","안쪽 셔츠",None), ("pants","clothing","바지（주머니·밑단 포함）","pants"),
        ("boot_R","clothing","오른쪽 부츠",None), ("boot_L","clothing","왼쪽 부츠",None),
        ("belt","accessory","벨트（버클 포함）","belt"),
    ]
    retained = {"hair":"hair-v1.png", "shirt":"shirt-v1.png", "boot_R":"boot-r-v1.png", "boot_L":"boot-r-v1.png"}
    plan["parts"] = []
    for part_id, category, name, reference in specs:
        ref = str((BASE / (reference + "-v2.png")).relative_to(ROOT)).replace("\\", "/") if reference else "art/references/explorer_b_modular_v1/02_parts/" + retained[part_id]
        plan["parts"].append({"id":part_id,"category":category,"label":name,"state":"not_created",
                              "mesh_path":None,"reference_images":[ref],"reference_status":"awaiting_user_review",
                              "generation_strategy":"mirror_validated_right_side" if part_id in ["hand_L","boot_L"] else "whole_component"})
    plan["geometry_rules"] = {
        "complete_body_exists_under_hidden_clothing":True,
        "head_body_hands_are_independent_authoring_meshes":True,
        "body_is_continuous_from_neck_to_wrists_and_feet":True,
        "body_limbs_are_not_separate_mesh_units":True,
        "clothing_and_accessories_are_independent_authoring_meshes":True,
        "jacket_includes_connected_sleeves_and_cuffs":True,
        "pants_include_attached_cargo_pockets":True,
        "belt_and_buckle_are_one_authoring_unit":True,
        "skin_material_uses_shared_base_color":True,
        "joint_deformation_requires_topology_and_weights":True,
        "facial_shapes_keep_same_vertex_structure":True,
    }
    plan["reference_coverage_note"] = "Latest user revision replaces the detailed 60-slot split with head/body/hands and complete garments. Four body mesh units count both hands; three body reference groups. No meshes yet."
    for stage in plan["stages"]:
        if stage["id"] == "references":
            stage.update(state="awaiting_user_review", evidence=[str(MANIFEST.relative_to(ROOT)).replace("\\", "/")],
                         outputs=[str((BASE / a["file"]).relative_to(ROOT)).replace("\\", "/") for a in manifest["assets"]])
            stage["review"].update(approved=False, approval_evidence=None)
    write_json(PLAN, plan)
    print(json.dumps({"images":6,"preview":str(preview),"plan_revision":plan["revision"],"new_meshes":0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
