extends SceneTree
const Assembly=preload("res://scripts/asset_assembly.gd")
const Art=preload("res://scripts/art.gd")
const BASE="res://../artifacts/picture-furniture-20261002/"
var items: Array[Node3D]=[]
var failures: Array[String]=[]
func _initialize() -> void:call_deferred("run")
func label(parent: Node,text: String,size: int=18) -> Label:
	var l:=Label.new();l.text=text;l.add_theme_font_size_override("font_size",size);l.add_theme_color_override("font_color",Color("f1ead6"));parent.add_child(l);return l
func card(parent: Node,row: Dictionary,minimum: Vector2) -> SubViewport:
	var column:=VBoxContainer.new();column.size_flags_horizontal=Control.SIZE_EXPAND_FILL;column.size_flags_vertical=Control.SIZE_EXPAND_FILL;parent.add_child(column)
	label(column,row.title,20)
	var container:=SubViewportContainer.new();container.stretch=true;container.custom_minimum_size=minimum;container.size_flags_vertical=Control.SIZE_EXPAND_FILL;column.add_child(container)
	var viewport:=SubViewport.new();viewport.size=Vector2i(minimum);viewport.own_world_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.msaa_3d=Viewport.MSAA_4X;container.add_child(viewport)
	var stage:=Node3D.new();viewport.add_child(stage)
	var env:=WorldEnvironment.new();env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("c4cdb8");env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_color=Color.WHITE;env.environment.ambient_light_energy=.35;stage.add_child(env)
	env.environment.ambient_light_energy=.16
	var sun:=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-40,-30,0);sun.light_energy=.48;sun.shadow_enabled=true;stage.add_child(sun)
	var blobs: Dictionary={}
	for id in row.blobs:blobs[id]=Marshalls.base64_to_raw(row.blobs[id])
	var item:=Assembly.new()
	if not item.build(row.manifest,blobs):failures.append(row.id);item.free();return viewport
	stage.add_child(item);items.append(item);item.set_process(false)
	Art.box(stage,Vector3(0,-.09,0),Vector3(12,.12,12),Color("c4cdb8"))
	var size: Vector3=item.get_meta("size",Vector3.ONE)
	var camera:=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.keep_aspect=Camera3D.KEEP_WIDTH;camera.size=maxf(2.05,maxf(size.x,size.y)*1.65);camera.position=Vector3(2.5,2,4);stage.add_child(camera);camera.look_at(Vector3(0,size.y*.6,0));camera.current=true
	label(column,str(row.spec.llm)+" / "+str(row.spec.effort),15)
	label(column,str(row.spec.tripo_model)+" · %d 부품"%row.spec.part_count,15)
	label(column,"실측 %d 크레딧 · %d 삼각형"%[int(row.spec.tripo_credits),int(row.spec.stats.triangles)],15)
	return viewport
func click_items() -> void:
	for item in items:
		var result: Dictionary=item.vm.run("click",{"dt":0,"time":item.elapsed,"near":0})
		if result.ok:item.apply_commands(result.commands)
		else:failures.append("click")
func run() -> void:
	root.size=Vector2i(1440,900);root.content_scale_size=Vector2i(1440,900)
	var rows: Array=JSON.parse_string(FileAccess.get_file_as_string(BASE+"render-input.json"))
	var layer:=CanvasLayer.new();root.add_child(layer)
	var background:=ColorRect.new();background.color=Color("17332f");background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);layer.add_child(background)
	var holder:=VBoxContainer.new();holder.position=Vector2(24,20);holder.size=Vector2(1392,858);layer.add_child(holder)
	var heading:=label(holder,"참고 그림 → 실제 Tripo 가구",30)
	var note:=label(holder,"같은 그림 · 정적 1메시 / 동적 2부품 · 색·문양·닫힘 상태를 비교하세요.",18)
	var grid:=HBoxContainer.new();grid.add_theme_constant_override("separation",20);grid.size_flags_vertical=Control.SIZE_EXPAND_FILL;holder.add_child(grid)
	var interactive: bool="--interactive" in OS.get_cmdline_user_args()
	if not interactive:
		for row in rows:
			var view:=card(grid,row,Vector2(720,570));await process_frame;await RenderingServer.frame_post_draw
			view.get_texture().get_image().save_png(BASE+"public/"+row.id+".png")
			for child in grid.get_children():grid.remove_child(child);child.queue_free()
			items.clear();await process_frame
	var reference:=VBoxContainer.new();reference.size_flags_horizontal=Control.SIZE_EXPAND_FILL;grid.add_child(reference)
	label(reference,"입력 그림",20)
	var image:=TextureRect.new();image.texture=ImageTexture.create_from_image(Image.load_from_file(BASE+"reference.jpg"));image.expand_mode=TextureRect.EXPAND_IGNORE_SIZE;image.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED;image.custom_minimum_size=Vector2(450,560);image.size_flags_vertical=Control.SIZE_EXPAND_FILL;reference.add_child(image)
	label(reference,"내장 imagegen으로 준비한 참고 그림",15);label(reference,"같은 JPEG를 두 생성 경로에 전달",15)
	for row in rows:
		if row.id.begins_with("picture-"):card(grid,row,Vector2(450,560))
	if items.size()!=2:failures.append("two new results required")
	var phase:=label(holder,"닫힌 상태",19)
	if interactive:
		var button:=Button.new();button.text="뚜껑 열기 / 닫기";button.pressed.connect(click_items);holder.add_child(button)
		for item in items:item.set_process(true)
		print("PICTURE_VIEWER_READY items=",items.size());return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(BASE+"frames"))
	for frame in 300:
		if frame in [45,190]:click_items();phase.text="뚜껑 열기" if frame==45 else "뚜껑 닫기"
		for item in items:
			item._process(1.0/30)
			if not item.healthy:failures.append("unhealthy animation")
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_jpg(BASE+"frames/frame_%04d.jpg"%frame,.92)
		if frame in [25,140,280]:root.get_texture().get_image().save_png(BASE+"public/"+({25:"closed",140:"open",280:"closed-again"}[frame])+".png")
	print("PICTURE_RENDER ",JSON.stringify({"models":items.size(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
