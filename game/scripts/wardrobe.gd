extends HBoxContainer
var avatar: Dictionary={}
var preview: Node3D
var actor: CharacterBody3D
const RpgUi=preload("res://scripts/rpg_ui.gd")
const DEFAULTS={"character":"explorer_b","hair":"#30595b","coat":"#dba448","pants":"#526552","boots":"#765744","skin":"#e4b587","headwear":"none","backpack":true}

func _ready() -> void:
	avatar=DEFAULTS.merged(avatar,true)
	add_theme_constant_override("separation",24)
	var container := SubViewportContainer.new()
	container.custom_minimum_size=Vector2(280,350)
	container.stretch=true
	add_child(container)
	var viewport := SubViewport.new()
	viewport.size=Vector2i(280,350)
	viewport.own_world_3d=true
	viewport.transparent_bg=true
	container.add_child(viewport)
	preview=Node3D.new()
	viewport.add_child(preview)
	var light := DirectionalLight3D.new()
	light.rotation_degrees=Vector3(-35,-25,0)
	light.light_energy=1.5
	preview.add_child(light)
	var env := WorldEnvironment.new()
	env.environment=Environment.new()
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color=Color.WHITE
	env.environment.ambient_light_energy=0.65
	preview.add_child(env)
	var camera := Camera3D.new()
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=2.3
	camera.position=Vector3(0,1.15,4)
	preview.add_child(camera)
	camera.look_at(Vector3(0,0.9,0))
	actor=preload("res://scripts/player.gd").new()
	actor.avatar=avatar.duplicate(true)
	actor.controls_enabled=false
	# visual_only keeps the idle animation ticking without moving the body.
	actor.visual_only=true
	# Face the preview camera; the walker turns its model toward `facing`.
	actor.facing=Vector3(0,0,1)
	preview.add_child(actor)
	actor.visual.rotation.y=PI
	if actor.animation_player and actor.animation_player.has_animation("idle"): actor.animation_player.play("idle")
	var controls := VBoxContainer.new()
	controls.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	add_child(controls)
	var row := HBoxContainer.new()
	controls.add_child(row)
	for id in ["explorer_b","explorer","ranger","tinker"]:
		var b := Button.new()
		b.text={"explorer_b":tr("여행자"),"explorer":tr("루"),"ranger":tr("미라"),"tinker":tr("테오")}[id]
		b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		b.set_meta("character",id)
		b.toggle_mode=true
		b.button_pressed=avatar.character==id
		b.pressed.connect(func():
			avatar.character=id
			var presets: Dictionary={"explorer":{"hair":"#30595b","coat":"#dba448","pants":"#526552","boots":"#765744"},"ranger":{"hair":"#a64e2c","coat":"#68765a","pants":"#45433f","boots":"#754b38"},"tinker":{"hair":"#343b53","coat":"#ad5545","pants":"#51566c","boots":"#b48b4b"}}
			avatar.merge(presets.get(id,presets.explorer),true)
			refresh())
		row.add_child(b)
	for key in ["hair","coat","pants","boots","skin"]:
		var colors := ["#30595b","#774f3d","#d5a250","#c47b50","#ab789f","#e6dfce","#526552","#6889a1"]
		if key=="skin": colors=["#e4b587","#f0cdb1","#bc865c","#895b43","#604431"]
		var label := Label.new()
		label.text={"hair":tr("머리"),"coat":tr("상의"),"pants":tr("하의"),"boots":tr("신발"),"skin":tr("피부")}[key]
		controls.add_child(label)
		var palette := HBoxContainer.new()
		controls.add_child(palette)
		for color in colors:
			var swatch := Button.new()
			swatch.text="●"
			swatch.custom_minimum_size=Vector2(36,32)
			swatch.add_theme_color_override("font_color",Color(color))
			RpgUi.name_tip(swatch,label.text+" · "+RpgUi.color_name(color))
			swatch.set_meta("name",swatch.tooltip_text)
			swatch.set_meta("part",key)
			swatch.set_meta("color",color)
			swatch.text="◆" if avatar[key]==color else "●"
			swatch.pressed.connect(func(): avatar[key]=color; refresh())
			palette.add_child(swatch)
	var hat := OptionButton.new()
	for title in [tr("모자 없음"),tr("여행 모자"),tr("베레모")]: hat.add_item(title)
	hat.select(["none","cap","beret"].find(avatar.headwear))
	hat.item_selected.connect(func(index): avatar.headwear=["none","cap","beret"][index]; refresh())
	controls.add_child(hat)
	var pack := CheckButton.new()
	pack.text=tr("여행 배낭")
	pack.button_pressed=avatar.backpack
	pack.toggled.connect(func(value): avatar.backpack=value; refresh())
	controls.add_child(pack)
	var turn := HSlider.new()
	turn.min_value=-180
	turn.max_value=180
	turn.tooltip_text=tr("미리보기 회전")
	turn.value_changed.connect(func(value): actor.facing=Vector3(sin(deg_to_rad(value)),0,cos(deg_to_rad(value))))
	controls.add_child(turn)
	refresh()

func refresh() -> void:
	actor.apply_avatar(avatar)
	for b in find_children("*","Button",true,false):
		if b.has_meta("character"): b.button_pressed=b.get_meta("character")==avatar.character
		if b.has_meta("part"):
			b.text="◆" if avatar[b.get_meta("part")]==b.get_meta("color") else "●"
			b.disabled=avatar.character=="explorer_b" and b.get_meta("part") in ["hair","skin"]
			b.tooltip_text=tr("이 여행자의 머리와 피부는 고유한 모습으로 유지돼요. 옷과 소품을 바꿔 보세요.") if b.disabled else str(b.get_meta("name",""))
	if actor.animation_player and actor.animation_player.has_animation("idle"): actor.animation_player.play("idle",0.18)
