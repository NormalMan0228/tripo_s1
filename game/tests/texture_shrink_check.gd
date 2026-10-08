extends SceneTree
## Crafted models are shrunk on load: a Tripo-coloured GLB (three 2048 px maps) loaded through
## model_loader.load_bytes comes out with maps of at most 1024 px, colour maps block-compressed when the
## renderer allows it, and far less texture memory. Run rendered (textures need a real renderer).
const Loader = preload("res://scripts/model_loader.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var warm_started := Time.get_ticks_msec()
	Loader.warm_up_compression()
	print("TEXTURE_WARMUP_MS ", Time.get_ticks_msec() - warm_started)
	# --glb=<file> and --out=<file> let the exported game (no source GLBs inside) run this check too.
	var glb := "res://assets/interior/barrel.glb"
	var out := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--glb="): glb = argument.trim_prefix("--glb=")
		if argument.begins_with("--out="): out = argument.trim_prefix("--out=")
	var bytes := FileAccess.get_file_as_bytes(glb)
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var ok := document.append_from_buffer(bytes, "", state) == OK
	var raw := document.generate_scene(state) as Node3D if ok else null
	var started := Time.get_ticks_msec()
	var stats: Dictionary = Loader.shrink_textures(raw) if raw else {}
	var took := Time.get_ticks_msec() - started
	var largest := 0
	var meshes: Array[MeshInstance3D] = []
	if raw: Loader._collect_meshes(raw, meshes)
	for m in meshes:
		for s in m.mesh.get_surface_count():
			var mat = m.mesh.surface_get_material(s)
			if mat is BaseMaterial3D:
				for p in BaseMaterial3D.TEXTURE_MAX:
					var t: Texture2D = mat.get_texture(p)
					if t: largest = maxi(largest, maxi(t.get_width(), t.get_height()))
	var model := Loader.load_bytes(bytes)
	print("TEXTURE_SHRINK stats=%s largest=%d took_ms=%d load_bytes=%s s3tc=%s" % [stats, largest, took, model != null, RenderingServer.has_os_feature("s3tc")])
	var good: bool = ok and stats.get("textures", 0) >= 3 and largest <= 1024 and stats.get("bytes_after", 1) * 4 < stats.get("bytes_before", 0) and model != null and took < 400
	print("TEXTURE_SHRINK_" + ("OK" if good else "FAIL"))
	if not out.is_empty():
		var file := FileAccess.open(out, FileAccess.WRITE)
		if file: file.store_string("%s %s took_ms=%d
" % ["OK" if good else "FAIL", stats, took])
	if raw: raw.free()
	if model: model.free()
	quit(0 if good else 1)
