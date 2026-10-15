extends SceneTree
## Baked static data for the survival maps (game/maps/survival/generated/, git-ignored; what it holds
## and when it counts: game/maps/survival/survival_bake.gd). Run through tools/bake_survival.py, or:
##   .tools/godot/Godot_v4.7.2-stable_win64_console.exe --headless --path game --script res://../tools/bake_survival.gd
## Builds each map once without baked data from its layout (the layout's obstacles and hazards, no
## resource nodes), the way the game builds it, and saves the ground mesh, the water sheets, the rim
## block's instances with the rng state before and after it, and the fingerprints of the map's code
## (bake_probe, rim_probe). Prints BAKE_SURVIVAL <map> {...} and BAKE_DONE.
## --check: only says whether every map's bake is fresh (exit 0) or not (exit 3).
const Map = preload("res://maps/survival/survival_map.gd")
const SurvivalBake = preload("res://maps/survival/survival_bake.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	SurvivalBake.uncached = true
	SurvivalBake.reset()
	if "--check" in OS.get_cmdline_user_args():
		var stale := []
		for map_id in SurvivalBake.MAPS:
			var why := SurvivalBake.problem(map_id)
			if not why.is_empty(): stale.append("%s: %s" % [map_id, why])
		print("BAKE_SURVIVAL_CHECK ", "fresh" if stale.is_empty() else "stale (%s)" % ", ".join(stale))
		quit(0 if stale.is_empty() else 3)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SurvivalBake.DIR))
	SurvivalBake.disabled = true
	var total := 0
	for map_id in SurvivalBake.MAPS:
		var started := Time.get_ticks_msec()
		var all := Map.layouts()
		var spec: Dictionary = all.maps[map_id]
		var state := {"map_id":map_id,"obstacles":spec.obstacles,"hazards":spec.hazards,"nodes":[]}
		var map: Node3D = Map.new()
		map.bake_record = true
		root.add_child(map)
		await map.build(state)
		map.set_process(false)
		var ground := (map.get_node("Ground") as MeshInstance3D).mesh as ArrayMesh
		var water := []
		for water_name in ["Pond","Lake"]:
			var sheet := map.get_node_or_null(water_name) as MeshInstance3D
			if sheet: water.append([water_name, sheet.mesh])
		var data := Resource.new()
		data.set_meta("format", SurvivalBake.FORMAT)
		data.set_meta("engine", SurvivalBake.engine())
		data.set_meta("key", SurvivalBake.key())
		data.set_meta("export_key", SurvivalBake.export_key())
		data.set_meta("map_id", map_id)
		data.set_meta("layout_sig", SurvivalBake.layout_sig(state, spec, float(all.bounds)))
		data.set_meta("ground", ground)
		data.set_meta("water", water)
		data.set_meta("rim", map.rim_record)
		data.set_meta("rng_before_rim", map.rng_before_rim)
		data.set_meta("rng_after_rim", map.rng_after_rim)
		# The fingerprints an exported game compares (it cannot read the scripts' text).
		data.set_meta("probe", map.bake_probe())
		data.set_meta("rim_probe", map.rim_probe())
		var file := SurvivalBake.path(map_id)
		var error := ResourceSaver.save(data, file, ResourceSaver.FLAG_COMPRESS)
		if error != OK:
			print("BAKE_SURVIVAL %s failed to save (%s)" % [map_id, error_string(error)])
			quit(1)
			return
		var rim_instances := 0
		for record in map.rim_record: rim_instances += (record[4] as PackedFloat32Array).size()/12
		var bytes := FileAccess.get_file_as_bytes(file).size()
		total += bytes
		print("BAKE_SURVIVAL %s %s" % [map_id, JSON.stringify({"bytes":bytes,"ms":Time.get_ticks_msec()-started,
			"ground_vertices":ground.surface_get_array_len(0),"water":water.map(func(w): return w[0]),
			"rim_batches":map.rim_record.size(),"rim_instances":rim_instances})])
		map.queue_free()
		await process_frame
	SurvivalBake.disabled = false
	SurvivalBake.reset()
	var stale := []
	for map_id in SurvivalBake.MAPS:
		var why := SurvivalBake.problem(map_id)
		if not why.is_empty(): stale.append("%s: %s" % [map_id, why])
	print("BAKE_DONE %d bytes, %s" % [total, "fresh" if stale.is_empty() else "stale after baking (%s)" % ", ".join(stale)])
	quit(0 if stale.is_empty() else 1)
