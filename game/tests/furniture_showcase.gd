extends SceneTree
const Art=preload("res://scripts/art.gd")
const Assembly=preload("res://scripts/asset_assembly.gd")
var models: Array[Node3D]=[]
var api: Node
var h3 := false
var repair := false
func _initialize() -> void:call_deferred("run")
func run() -> void:
	h3="--h3" in OS.get_cmdline_user_args()
	repair="--repair" in OS.get_cmdline_user_args()
	api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var login: Dictionary=await api.post("/v1/auth/login",{"username":"workshop","password":"tripothon-local-demo"})
	if not login.ok:quit(1);return
	api.token=login.data.token
	var listing: Dictionary=await api.request("/v1/studio")
	if not listing.ok:quit(1);return
	var layer := CanvasLayer.new();root.add_child(layer)
	var background := ColorRect.new();background.color=Color("183331");background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);layer.add_child(background)
	var grid := GridContainer.new();grid.columns=2 if h3 or repair else 3;grid.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);grid.offset_left=26;grid.offset_right=-26;grid.offset_top=110;grid.offset_bottom=-24;grid.add_theme_constant_override("h_separation",14);grid.add_theme_constant_override("v_separation",14);layer.add_child(grid)
	var slot := 0
	for obj in listing.data.objects:
		if repair:
			if obj.name not in ["H3 열리는 상자 · 직접 색칠","H3 보정 상자 · 직접 색칠"]:continue
		else:
			if "보정" in obj.name:continue
			if obj.name.begins_with("H3 ")!=h3:continue
		if not ("상자" in obj.name or "Vase" in obj.name or "Windmill" in obj.name):continue
		var model: Node3D=await Assembly.fetch(api,obj.id)
		if not model:continue
		var card := VBoxContainer.new();card.size_flags_horizontal=Control.SIZE_EXPAND_FILL;card.size_flags_vertical=Control.SIZE_EXPAND_FILL;grid.add_child(card)
		var stage := card_stage(card,model)
		stage.add_child(model);model.position=Vector3.ZERO
		model.set_process(false);model.set_meta("object_id",obj.id);models.append(model)
		model.set_meta("showcase_slot",slot)
		Art.box(stage,Vector3(0,-.08,0),Vector3(12,.12,12),Color("aab8a2"))
		var caption: String=obj.name
		if "Windmill" in caption:caption="LLM 설계 + Tripo · 회전 풍차"
		if "Vase" in caption:caption="LLM 설계 + Tripo · 정적 화병"
		caption+="\n실측 %s Tripo 크레딧"%str(model.manifest.provenance.tripo_credits_consumed)
		var label := Label.new();label.text=caption;label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;label.add_theme_font_size_override("font_size",18);label.add_theme_color_override("font_color",Color("eee4ca"));card.add_child(label)
		slot+=1
	var heading := Label.new();heading.text="TRIPOTHON  /  STATIC & DYNAMIC FURNITURE";heading.position=Vector2(30,22);heading.add_theme_font_size_override("font_size",25);heading.add_theme_color_override("font_color",Color("ead6a4"));layer.add_child(heading)
	var note := Label.new();note.text=("H3 v3.1 · 같은 프롬프트로 P2와 비교 · 텍스트→3D · 2026-10-02 실제 차감" if h3 else "실제 Tripo 생성 메시 · 서버에서 소유권 확인 후 로드 · 동작은 검증된 생성 코드로 실행");note.position=Vector2(30,62);note.add_theme_font_size_override("font_size",16);note.add_theme_color_override("font_color",Color("c4d7c0"));layer.add_child(note)
	var prefix := "h3-furniture" if h3 else "furniture"
	if repair:
		prefix="repaired-furniture"
		note.text="왼쪽: 텍스트만 요청 / 오른쪽: 참고 이미지 수정 후 본체 재생성 · 실패한 최초 생성비도 포함"
	var frames := "res://../artifacts/"+prefix+"-review-frames"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(frames))
	for frame in 240:
		if frame in [60,180]:
			for model in models:
				if model.pivots.has("lid"):
					var reply: Dictionary=await api.post("/v1/objects/"+str(model.get_meta("object_id"))+"/event",api.mutation({"version":model.runtime_version,"event":"click"}))
					if reply.ok:model.accept_event(reply.data)
		for model in models:model._process(1.0/30)
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_jpg(frames+"/frame_%04d.jpg"%frame,.9)
		if frame==100:
			root.get_texture().get_image().save_png("res://../artifacts/"+prefix+"-showcase.png")
			for model in models:model.get_viewport().get_texture().get_image().save_png(frames+"/reference-%d.png"%model.get_meta("showcase_slot"))
	print("FURNITURE_SHOWCASE models=",models.size()," frames=240")
	quit(0 if models.size()==(2 if repair else (4 if h3 else 6)) else 1)

func card_stage(card: VBoxContainer,model: Node3D) -> Node3D:
	var container := SubViewportContainer.new();container.stretch=true;container.custom_minimum_size=Vector2(350,230);container.size_flags_vertical=Control.SIZE_EXPAND_FILL;card.add_child(container)
	var viewport := SubViewport.new();viewport.size=Vector2i(400,250);viewport.own_world_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.msaa_3d=Viewport.MSAA_4X;container.add_child(viewport)
	var stage := Node3D.new();viewport.add_child(stage)
	var env := WorldEnvironment.new();env.environment=Environment.new();env.environment.background_mode=Environment.BG_COLOR;env.environment.background_color=Color("aab8a2");env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.environment.ambient_light_color=Color.WHITE;env.environment.ambient_light_energy=.16;stage.add_child(env)
	var sun := DirectionalLight3D.new();sun.rotation_degrees=Vector3(-40,-30,0);sun.light_energy=.48;sun.shadow_enabled=true;stage.add_child(sun)
	var size: Vector3=model.get_meta("size",Vector3.ONE)
	if model.pivots.has("lid"):size.y=maxf(size.y,1.6)
	var camera := Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.size=maxf(1.55,size.y*1.4);camera.position=Vector3(2.5,2.1,4);stage.add_child(camera);camera.look_at(Vector3(0,size.y*.45,0));camera.current=true
	return stage
