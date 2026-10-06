extends SceneTree
## Headless check: every survival monster GLB (5 species x 3 variants) imports, instantiates through
## monster.gd, carries every expected clip with a sane length, loops the locomotion clips, stands at the
## manifest height, faces +Z and has an emission map for its glowing eyes. Missing GLBs are reported
## (the game falls back to procedural bodies), so the check fails only on broken assets unless
## --require-all is passed.
## Run: Godot --headless --path game --script res://tests/monster_assets_check.gd [-- --require-all]
const Monster = preload("res://scripts/monster.gd")
const SPECIES := ["wolf", "boar", "brute", "wisp", "shroom"]
const VARIANTS := ["forest", "quarry", "frost"]
const CLIPS := ["idle", "walk", "run", "attack", "hurt", "death"]
const EXTRA := {"brute": ["roar"]}

func _initialize() -> void:
	call_deferred("go")

func go() -> void:
	var require_all := "--require-all" in OS.get_cmdline_user_args()
	var manifest := {}
	if FileAccess.file_exists("res://assets/monsters/manifest.json"):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://assets/monsters/manifest.json"))
		if parsed is Dictionary:
			for entry in parsed.get("monsters", []): manifest[entry.id] = entry
	var failures: Array[String] = []
	var found := 0
	var holder := Node3D.new()
	root.add_child(holder)
	for species in SPECIES:
		for variant in VARIANTS:
			var id: String = species + "_" + variant
			var path := Monster.path_for(species, variant)
			if not ResourceLoader.exists(path):
				if require_all: failures.append(id + ": missing " + path)
				print("MONSTER_MISSING ", id)
				continue
			found += 1
			var creature := Monster.new()
			if not creature.setup(species, variant) or creature.variant != variant:
				failures.append(id + ": setup failed")
				creature.free()
				continue
			holder.add_child(creature)
			var clips: Array = CLIPS + EXTRA.get(species, [])
			var lengths := {}
			for clip in clips:
				if not creature.has(clip):
					failures.append(id + ": missing clip " + clip)
					continue
				var animation: Animation = creature.player.get_animation(clip)
				lengths[clip] = snappedf(animation.length, 0.01)
				if animation.length < 0.3 or animation.length > 6.0: failures.append(id + ": odd length " + clip)
				if clip in Monster.LOOPS and animation.loop_mode != Animation.LOOP_LINEAR: failures.append(id + ": not looping " + clip)
			var expected: float = manifest.get(id, {}).get("scale_reference", {}).get("metres", 0.0)
			if expected > 0 and absf(creature.height - expected) > expected * 0.2:
				failures.append(id + ": height %.2f, manifest %.2f" % [creature.height, expected])
			var glow = creature.overlay.get_shader_parameter("glow_map")
			if glow == null: failures.append(id + ": no emission map for the eyes")
			if manifest.has(id) and manifest[id].get("facing", {}).get("gltf_forward", "") != "+Z":
				failures.append(id + ": manifest facing is not +Z")
			print("MONSTER_OK ", id, " height=%.2f " % creature.height, lengths)
			creature.queue_free()
	await process_frame
	holder.queue_free()
	for failure in failures: print("MONSTER_FAIL ", failure)
	var ok := failures.is_empty() and found > 0
	print("MONSTER_ASSETS_COMPLETE ", ok, " found=", found, "/15")
	quit(0 if ok else 1)
