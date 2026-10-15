extends SceneTree
## Video memory and load time of crafted objects (model_loader.load_bytes + paint, the village path):
## loads one Tripo-coloured GLB --count times (default 10) into a lit scene and reads the renderer's
## texture memory before and after. --no-compress runs it as the exported game does (release
## templates have no block compressor, model_loader.compressor_ok). Run rendered (real renderer).
const Loader = preload("res://scripts/model_loader.gd")

func _initialize() -> void:
	call_deferred("run")

func texture_mb() -> float:
	return RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED) / 1048576.0

func video_mb() -> float:
	return RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED) / 1048576.0

func run() -> void:
	var glb := "res://assets/interior/barrel.glb"
	var count := 10
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--glb="): glb = argument.trim_prefix("--glb=")
		if argument.begins_with("--count="): count = int(argument.trim_prefix("--count="))
	if "--no-compress" in OS.get_cmdline_user_args(): Loader.compressor_ok = false
	Loader.warm_up_compression()
	var stage := Node3D.new()
	root.add_child(stage)
	var camera := Camera3D.new()
	camera.position = Vector3(0, 3, 9)
	stage.add_child(camera)
	camera.look_at(Vector3(0, 0.8, 0))
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-50, 30, 0)
	stage.add_child(light)
	var bytes := FileAccess.get_file_as_bytes(glb)
	for i in 10: await process_frame
	var tex_before := texture_mb()
	var vid_before := video_mb()
	var times: Array[float] = []
	for i in count:
		var started := Time.get_ticks_usec()
		var model := Loader.load_bytes(bytes)
		Loader.paint(model, Color("d9b98a"))
		times.append((Time.get_ticks_usec() - started) / 1000.0)
		model.position = Vector3((i % 5 - 2) * 1.9, 0, -(i / 5) * 1.9)
		stage.add_child(model)
		await process_frame
	for i in 10: await process_frame
	var tex_after := texture_mb()
	var vid_after := video_mb()
	var total := 0.0
	for t in times: total += t
	times.sort()
	print("CRAFT_VRAM count=%d compress=%s texture_mb_per_object=%.2f video_mb_per_object=%.2f load_ms_avg=%.1f load_ms_max=%.1f texture_mb_total=%.1f" % [count, Loader.compressor_ok, (tex_after - tex_before) / count, (vid_after - vid_before) / count, total / count, times[-1], tex_after - tex_before])
	# --shot=<png>: the ten objects as drawn (flat colour either way).
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--shot="):
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(argument.trim_prefix("--shot="))
	quit(0)
