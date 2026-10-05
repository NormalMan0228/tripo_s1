extends Node
var host: Node3D
var report := {"views":[],"viewport":[1440,1000],"vsync":false}
var tag := "before"

func run(owner_node: Node3D) -> void:
	host = owner_node
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--benchmark-tag="):
			tag = arg.get_slice("=",1)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(),true)
	_capture.call_deferred()

func _capture() -> void:
	await get_tree().create_timer(2.0).timeout
	host.free_camera = true
	host.map_tour = false
	host.get_node("CanvasLayer").visible = false
	host.camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	var views := [["overview",Vector3(0,3,3),145.0,.86,-.08],["village",Vector3(-42,4,-39),63.0,.69,-.15],["bridge",Vector3(-11,2,65),38.0,.50,.6]]
	for view in views:
		var target: Vector3 = view[1]
		var elevation: float = view[3]
		var azimuth: float = view[4]
		host.camera.size = view[2]
		host.camera.position = target+Vector3(sin(azimuth)*cos(elevation),sin(elevation),cos(azimuth)*cos(elevation))*190
		host.camera.look_at(target)
		await get_tree().create_timer(2.0).timeout
		var samples: Array[float] = []
		var gpu: Array[float] = []
		var cpu: Array[float] = []
		var previous := Time.get_ticks_usec()
		for i in range(180):
			await RenderingServer.frame_post_draw
			var now := Time.get_ticks_usec()
			samples.append(float(now-previous)/1000.0)
			previous = now
			gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(get_viewport().get_viewport_rid()))
			cpu.append(RenderingServer.viewport_get_measured_render_time_cpu(get_viewport().get_viewport_rid())+RenderingServer.get_frame_setup_time_cpu())
		var mean := _mean(samples)
		samples.sort()
		var entry := {"view":view[0],"mean_frame_ms":mean,"fps":1000.0/mean,"p95_frame_ms":samples[int(samples.size()*.95)],"gpu_ms":_mean(gpu),"render_cpu_ms":_mean(cpu),"draw_calls":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),"primitives":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),"video_memory_mb":float(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED))/1048576.0}
		report.views.append(entry)
		print("PERFORMANCE_VIEW ",JSON.stringify(entry))
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../../art/maps/archipelago_performance_v1/"+tag+"_"+String(view[0])+".png"))
	var file := FileAccess.open("res://../../art/maps/archipelago_performance_v1/"+tag+".json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	get_tree().quit()

func _mean(values: Array[float]) -> float:
	var total := 0.0
	for value in values:
		total += value
	return total/values.size()
