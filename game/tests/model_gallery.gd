extends SceneTree
const Assembly=preload("res://scripts/asset_assembly.gd")
const Art=preload("res://scripts/art.gd")
var models: Array[Node3D]=[]
var failures: Array[String]=[]
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var reference := "--reference" in OS.get_cmdline_user_args()
	var name := "reference-model-gallery" if reference else "model-gallery"
	root.size=Vector2i(1600,1000);root.content_scale_size=Vector2i(1600,1000)
	var layer := CanvasLayer.new();root.add_child(layer)
	var background := ColorRect.new();background.color=Color("183331");background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);layer.add_child(background)
	var heading := Label.new();heading.position=Vector2(25,18);heading.text="실제 LLM 출력 비교 · 상자 / 꽃 / 시계";heading.add_theme_font_size_override("font_size",28);layer.add_child(heading)
	if reference:heading.text="참고 이미지 → 실제 LLM 설계 · 화병 / 풍차 / 상자"
	var note := Label.new();note.position=Vector2(25,58);note.text="외형은 설계 검토용 도형입니다. Tripo 생성 품질 비교가 아닙니다. 같은 이벤트를 같은 시간에 입력합니다.";layer.add_child(note)
	var timeline := Label.new();timeline.position=Vector2(25,85);timeline.add_theme_color_override("font_color",Color("efce89"));layer.add_child(timeline)
	var grid := GridContainer.new();grid.columns=4;grid.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);grid.offset_left=25;grid.offset_right=-25;grid.offset_top=118;grid.offset_bottom=-15;grid.add_theme_constant_override("h_separation",12);grid.add_theme_constant_override("v_separation",12);layer.add_child(grid)
	var rows: Array=JSON.parse_string(FileAccess.get_file_as_string("res://../artifacts/"+name+".json"))
	for row in rows:
		var card := VBoxContainer.new();card.size_flags_horizontal=Control.SIZE_EXPAND_FILL;card.size_flags_vertical=Control.SIZE_EXPAND_FILL;grid.add_child(card)
		var caption := Label.new();caption.text=row.model+" · "+row.effort+" / "+row.case;caption.add_theme_font_size_override("font_size",16);caption.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;card.add_child(caption)
		if not row.has("payload"):failures.append(row.model+row.case);continue
		var container := SubViewportContainer.new();container.stretch=true;container.custom_minimum_size=Vector2(360,230);container.size_flags_vertical=Control.SIZE_EXPAND_FILL;card.add_child(container)
		var view := SubViewport.new();view.size=Vector2i(360,230);view.own_world_3d=true;view.render_target_update_mode=SubViewport.UPDATE_ALWAYS;container.add_child(view)
		var stage := Node3D.new();view.add_child(stage)
		var env := WorldEnvironment.new();env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("a9b6a2");env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_color=Color.WHITE;env.environment.ambient_light_energy=.55;stage.add_child(env)
		var light := DirectionalLight3D.new();light.rotation_degrees=Vector3(-40,-30,0);stage.add_child(light)
		var item := Assembly.new();var blobs := {}
		for id in row.payload.blobs:blobs[id]=Marshalls.base64_to_raw(row.payload.blobs[id])
		if not item.build(row.payload,blobs):failures.append(row.model+row.case);item.free();continue
		stage.add_child(item);item.set_process(false);models.append(item)
		Art.box(stage,Vector3(0,-.07,0),Vector3(20,.1,20),Color("a9b6a2"))
		var camera := Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=2.7;camera.position=Vector3(2,1.9,4);stage.add_child(camera);camera.look_at(Vector3(0,.75,0));camera.current=true
	var folder := "res://../artifacts/"+name+"-frames";DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(folder))
	for frame in 360:
		var event := ""
		if frame==30:event="click"
		if frame==90:event="near"
		if frame==180:event="click"
		if frame==270:event="leave"
		if not event.is_empty():timeline.text="%.1f초 · 모든 설계에 %s 이벤트"%[frame/30.0,event]
		for item in models:
			if not event.is_empty():
				if event=="near":item.nearby=true
				if event=="leave":item.nearby=false
				var result: Dictionary=item.vm.run(event,{"dt":0,"time":item.elapsed,"near":int(item.nearby)})
				if result.ok:item.apply_commands(result.commands)
				else:failures.append("event failed")
			item._process(1.0/30)
			if not item.healthy:failures.append("tick failed")
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_jpg(folder+"/frame_%04d.jpg"%frame,.9)
		if frame==145:root.get_texture().get_image().save_png("res://../artifacts/"+name+".png")
	print("MODEL_GALLERY ",JSON.stringify({"models":models.size(),"failures":failures}))
	quit(0 if failures.is_empty() and models.size()==12 else 1)
