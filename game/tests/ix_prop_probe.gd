extends SceneTree
## Measures the map's seat props for ISS-1 (ix_data.gd PROP_MODELS): each model's own collision-like
## boxes (craft_collision voxels over its real triangles) go through the crafted derivation, and the
## result is printed in the model's frame (pos in metres, yaw in degrees) with the mesh-snapped height.
##   godot --headless --path game --script res://tests/ix_prop_probe.gd
const CraftCollision = preload("res://scripts/craft_collision.gd")
const Sources = preload("res://scripts/ix/ix_sources.gd")

const MODELS := {"26_bench": "res://maps/archipelago/assets/environment/bench.glb", "25_picnic_table": "res://maps/archipelago/assets/environment/picnic_table.glb",
	"32_cafe_chair": "res://maps/archipelago/assets/environment/cafe_chair.glb", "29_beach_lounger": "res://maps/archipelago/assets/environment/beach_lounger.glb"}
const HINTS := {"26_bench": "sit", "25_picnic_table": "sit", "32_cafe_chair": "sit", "29_beach_lounger": "lie"}

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var out := {}
	for id in MODELS:
		if not ResourceLoader.exists(MODELS[id]):
			out[id] = "missing"
			continue
		var model := (load(MODELS[id]) as PackedScene).instantiate() as Node3D
		root.add_child(model)
		var boxes: Array = []
		for b in CraftCollision.boxes_for(model): boxes.append({"box": b, "part": ""})
		var bounds := AABB()
		for i in boxes.size(): bounds = boxes[i].box if i == 0 else bounds.merge(boxes[i].box)
		var recs := Sources.derive(boxes, HINTS[id], Vector3.ONE)
		var tris := Sources.triangles(model)
		var listed: Array = []
		for r in recs:
			var p: Vector3 = r.pos
			var hit := Sources.ray_down(tris, p.x, p.z, p.y + 0.25, p.y - 0.25)
			listed.append({"id": r.id, "type": r.type, "variant": r.variant, "pos": [snappedf(p.x, 0.001), snappedf(hit if not is_nan(hit) else p.y, 0.001), snappedf(p.z, 0.001)],
				"yaw": r.yaw, "params": r.params})
		var tops: Array = []
		for top in Sources.exposed_tops(boxes): tops.append([snappedf(top.t, 0.01), str(top.rect), snappedf(top.free, 0.01)])
		var raw: Array = []
		if "--boxes" in OS.get_cmdline_user_args():
			for b in boxes: raw.append([str(b.box.position.snapped(Vector3.ONE * 0.01)), str(b.box.size.snapped(Vector3.ONE * 0.01))])
		var rays := {}
		for x in [-0.6, -0.3, 0.0, 0.1, 0.3, 0.6]:
			for z in [-0.7, -0.4, -0.2, 0.0, 0.05, 0.2, 0.4, 0.7]:
				var h := Sources.ray_down(tris, x, z, 1.2, 0.05)
				if not is_nan(h): rays["%.1f,%.2f" % [x, z]] = snappedf(h, 0.01)
		out[id] = {"rays": rays, "bounds": [str(bounds.position), str(bounds.size)], "boxes": boxes.size(), "sockets": listed, "tops": tops, "raw": raw}
		model.queue_free()
	print("IX_PROP_PROBE ", JSON.stringify(out))
	quit(0)
