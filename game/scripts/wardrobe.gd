extends HBoxContainer
var avatar: Dictionary={}
## The server takes avatar_v2 (accent, straw hat, any skin): main.gd hands it over from /health.
var v2 := false
var preview: Node3D
var actor: CharacterBody3D
var preview_motion := "idle"
const RpgUi=preload("res://scripts/rpg_ui.gd")
## The preview is the same walker (player.gd through avatar_look.gd) that wears the look everywhere.
const AvatarLook=preload("res://scripts/avatar_look.gd")
const Roster=preload("res://scripts/character_roster.gd")
const DEFAULTS=AvatarLook.DEFAULTS

func _ready() -> void:
	avatar=AvatarLook.normalize(avatar)
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
	actor=AvatarLook.walker(avatar)
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
	for id in Roster.IDS:
		var b := Button.new()
		b.text=id
		b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		b.set_meta("character",id)
		b.toggle_mode=true
		b.button_pressed=avatar.character==id
		b.pressed.connect(func():
			RpgUi.sfx("tab",-8.0)
			avatar.character=id
			avatar.merge(Roster.PRESETS[id],true)
			refresh())
		row.add_child(b)
	for key in ["hair","coat","pants","boots","skin"]+(["accent"] if v2 else []):
		var colors := ["#30595b","#774f3d","#d5a250","#c47b50","#ab789f","#e6dfce","#526552","#6889a1"]
		if key=="skin": colors=["#e4b587","#f0cdb1","#bc865c","#895b43","#604431"]
		if key=="accent": colors=["#c94f3d","#e9c46a","#5fa8a0","#7a9bd9","#ab789f","#f4e3c1","#3c2e1e","#4a7536"]
		var label := Label.new()
		label.text={"hair":tr("머리"),"coat":tr("상의"),"pants":tr("하의"),"boots":tr("신발"),"skin":tr("피부"),"accent":tr("장식")}[key]
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
			swatch.pressed.connect(func(): avatar[key]=color; RpgUi.sfx("swatch",-8.0); refresh())
			palette.add_child(swatch)
		# Any colour (58): the server takes any #hex (skin only with avatar_v2), so a picker follows.
		if key=="skin" and not v2: continue
		var free := ColorPickerButton.new()
		free.name="Free_"+key
		free.custom_minimum_size=Vector2(36,32)
		free.edit_alpha=false
		free.color=Color(str(avatar[key]))
		free.set_meta("free_part",key)
		RpgUi.name_tip(free,label.text+" · "+tr("직접 고르기"))
		# Dragging in the picker sends a colour per mouse move; rebuilding the body each time stalled
		# weak laptops for seconds, so the look is rebuilt once when the picker closes.
		free.color_changed.connect(func(value: Color): avatar[key]="#"+value.to_html(false))
		free.popup_closed.connect(func(): RpgUi.sfx("swatch",-8.0); refresh())
		palette.add_child(free)
	var hat := OptionButton.new()
	var hats := ["none","cap","beret"]+(["straw"] if v2 else [])
	for id in hats: hat.add_item({"none":tr("모자 없음"),"cap":tr("여행 모자"),"beret":tr("베레모"),"straw":tr("밀짚모자")}[id])
	hat.select(maxi(0,hats.find(avatar.headwear)))
	hat.item_selected.connect(func(index): avatar.headwear=hats[index]; RpgUi.sfx("select",-8.0); refresh())
	controls.add_child(hat)
	var pack := CheckButton.new()
	pack.text=tr("여행 배낭")
	pack.button_pressed=avatar.backpack
	pack.toggled.connect(func(value): avatar.backpack=value; RpgUi.sfx("lift" if value else "place",-9.0); refresh())
	controls.add_child(pack)
	var turn := HSlider.new()
	turn.min_value=-180
	turn.max_value=180
	turn.tooltip_text=tr("미리보기 회전")
	turn.value_changed.connect(func(value):
		actor.facing=Vector3(sin(deg_to_rad(value)),0,cos(deg_to_rad(value)))
		# A ratchet tick per 30 degrees of turn.
		var notch := int(round(value/30.0))
		if notch!=int(turn.get_meta("notch",0)):
			turn.set_meta("notch",notch)
			RpgUi.sfx("rotate",-12.0))
	controls.add_child(turn)
	var motion := OptionButton.new()
	motion.name = "MotionPreview"
	for label in [tr("동작 확인 · 대기"), tr("동작 확인 · 걷기"), tr("동작 확인 · 달리기")]: motion.add_item(label)
	motion.item_selected.connect(func(index):
		preview_motion = ["idle", "walk", "run"][index]
		actor.clip_override = preview_motion)
	controls.add_child(motion)
	refresh()

func refresh() -> void:
	AvatarLook.wear(actor,avatar)
	actor.clip_override = preview_motion
	for b in find_children("*","Button",true,false):
		if b.has_meta("character"): b.button_pressed=b.get_meta("character")==avatar.character
		if b.has_meta("free_part"):
			(b as ColorPickerButton).color=Color(str(avatar.get(b.get_meta("free_part"),DEFAULTS.get(b.get_meta("free_part"),"#ffffff"))))
		if b.has_meta("part"):
			b.text="◆" if avatar.get(b.get_meta("part"),"")==b.get_meta("color") else "●"
			b.tooltip_text=str(b.get_meta("name",""))
	if actor.animation_player and actor.animation_player.has_animation("idle"): actor.animation_player.play("idle",0.18)
