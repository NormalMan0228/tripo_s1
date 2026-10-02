extends SceneTree
const Art=preload("res://scripts/art.gd")
const Assembly=preload("res://scripts/asset_assembly.gd")
var models: Array[Node3D]=[]
func _initialize() -> void:call_deferred("run")
func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps=0
	root.size=Vector2i(1280,800)
	var stage := Node3D.new();root.add_child(stage)
	var env := WorldEnvironment.new();env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("bcc5af");env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_color=Color.WHITE;env.environment.ambient_light_energy=.5;stage.add_child(env)
	var light := DirectionalLight3D.new();light.rotation_degrees=Vector3(-48,-25,0);light.shadow_enabled=true;stage.add_child(light)
	Art.box(stage,Vector3(0,-.08,0),Vector3(20,.15,20),Color("bcc5af"))
	var camera := Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=17;camera.position=Vector3(10,14,20);stage.add_child(camera);camera.look_at(Vector3.ZERO);camera.current=true
	var label := Label.new();label.position=Vector2(24,20);label.add_theme_font_size_override("font_size",24);root.add_child(label)
	var value: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://../artifacts/furniture-stress.json"));var blobs := {}
	for id in value.blobs:blobs[id]=Marshalls.base64_to_raw(value.blobs[id])
	var rows: Array=[]
	for count in [5,15,30]:
		while models.size()<count:
			var item := Assembly.new()
			if not item.build(value,blobs):item.free();quit(1);return
			var index := models.size();stage.add_child(item);item.position=Vector3((index%6-2.5)*2,0,(index/6-2)*2);models.append(item)
			item.nearby=true;item.apply_commands(item.vm.run("near",{"near":1}).commands)
		label.text="SYNTHETIC LOAD / %d FLOWERS / %d MOVING PARTS\n1280 × 800 · no API calls · not a full-game benchmark"%[count,count*8]
		await create_timer(2).timeout
		var samples: Array[float]=[];var start := Time.get_ticks_usec();var last := start
		while Time.get_ticks_usec()-start<10000000:
			await RenderingServer.frame_post_draw
			var current := Time.get_ticks_usec();samples.append((current-last)/1000.0);last=current
		samples.sort();var mean := 0.0
		for sample in samples:mean+=sample
		mean/=samples.size()
		var healthy := true
		for item in models:healthy=healthy and item.healthy
		var row := {"objects":count,"parts":count*8,"mean_frame_ms":mean,"p95_frame_ms":samples[int(samples.size()*.95)],"p99_frame_ms":samples[int(samples.size()*.99)],"mean_fps":1000.0/mean,"frames":samples.size(),"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"healthy":healthy}
		rows.append(row);print("FURNITURE_STRESS ",JSON.stringify(row))
		if not healthy:quit(1);return
	await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("res://../artifacts/furniture-stress.png")
	var report := {"synthetic":true,"resolution":[1280,800],"gpu":RenderingServer.get_video_adapter_name(),"measurement_seconds_per_count":10,"rows":rows}
	var file := FileAccess.open("res://../artifacts/furniture-stress-results.json",FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
	quit(0)
