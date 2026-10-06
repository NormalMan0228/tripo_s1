extends Node
## Fishing from any shore: cast arc, bobber and ripples, nibbles, the bite, a reel
## fight on a bar, and the catch card. The server (homestead.py) picks the fish,
## the bite time and checks the hook window and the fight's minimum length; this
## script only stages it. village_life owns the HUD slot (app.village_modal) so the
## game's E (life.reel) and Esc keys reach us.
const Art=preload("res://scripts/life_art.gd")
const Icon=preload("res://scripts/life_icon.gd")
const Town=preload("res://scripts/town.gd")
const RpgUi=preload("res://scripts/rpg_ui.gd")
## Ponds: centre, radii, surface height. Everything else wet is the sea at 0 m;
## the sea under the north waterfall counts as the stream ("river").
const PONDS := [[Vector2(51,-42.5),Vector2(12.5,9.5),1.35],[Vector2(-47,44.8),Vector2(16.5,12),1.18]]
const FALLS := Vector2(-0.5,-9.0)
const SPOT_NAMES := {"pond":"연못","sea":"바다","river":"폭포 웅덩이"}
var life: Node
var app: Node
var phase := ""
var spot := "sea"
var cast_at := Vector3.ZERO
var hud: Control
var status: Label
var keys: Label
var meter: Control
var bobber: Node3D
var line: MeshInstance3D
var pivot: Node3D
var rod_axis := Vector3.RIGHT
var rod_sign := 1.0
var rod_angle := 0.0
var flight := -1.0
var nibbles_seen := {}
var bite_shown := false
var ripple_clock := 0.0
var alert: Label3D
var trophy: Node3D
var card: Control
var card_clock := 0.0
var auto_reel := false
# reel fight
var fish_x := 0.5
var fish_goal := 0.5
var fish_clock := 0.0
var fish_speed := 0.3
var zone_x := 0.3
var zone_v := 0.0
var zone_w := 0.22
var progress := 0.3
var fill := 0.3
var drain := 0.15
var fight_min := 2.0
var fight_time := 0.0
var tick_clock := 0.0
var splash_clock := 0.0
var shadow_kind := "small"

static func water_level(p: Vector2) -> float:
	for pond in PONDS:
		if ((p-pond[0])/pond[1]).length()<1.0: return pond[2]
	return 0.0

static func water_kind(p: Vector2) -> String:
	for pond in PONDS:
		if ((p-pond[0])/pond[1]).length()<1.0: return "pond"
	return "river" if p.distance_to(FALLS)<9.0 else "sea"

func wet(space: PhysicsDirectSpaceState3D, p: Vector2) -> bool:
	var level := water_level(p)
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,40,p.y),Vector3(p.x,-20,p.y),1|2|8))
	if hit.is_empty(): return true
	if hit.collider is CollisionObject3D and not hit.collider.collision_layer&1: return false
	return hit.position.y<level-0.12

## Where a cast from `pos` toward `facing` lands, or {} when no water is ahead.
func find_cast(pos: Vector3, facing: Vector3) -> Dictionary:
	if not is_instance_valid(app.town) or Town.space==null: return {}
	var space: PhysicsDirectSpaceState3D=Town.space
	var f := Vector2(facing.x,facing.z)
	if f.length()<0.1: return {}
	f=f.normalized()
	var p0 := Vector2(pos.x,pos.z)
	if wet(space,p0): return {}
	for d in [1.4,2.0,2.6,3.2,3.8,4.4]:
		var p: Vector2=p0+f*d
		if wet(space,p) and wet(space,p+f*1.0):
			var at: Vector2=p0+f*minf(d+2.0,6.5)
			if not wet(space,at): at=p+f*0.8
			return {"at":Vector3(at.x,water_level(at),at.y),"spot":water_kind(at)}
	return {}

# ------------------------------------------------------------------ session

func begin(target: Dictionary) -> void:
	spot=target.spot
	cast_at=target.at
	app.player.face_point(cast_at)
	app.player.equip("rod")
	rig_rod()
	build_hud()
	phase="ready"
	refresh_hud()

func end() -> void:
	phase=""
	flight=-1
	if is_instance_valid(bobber): bobber.visible=false
	if is_instance_valid(line): line.visible=false
	if is_instance_valid(alert): alert.queue_free()
	if is_instance_valid(trophy): trophy.queue_free()
	if is_instance_valid(pivot): pivot.basis=Basis.IDENTITY
	hud=null

func rig_rod() -> void:
	var tool: Node3D=app.player.tool_node
	if not is_instance_valid(tool): return
	pivot=tool.get_node_or_null("RodPivot")
	if not pivot:
		pivot=Node3D.new()
		pivot.name="RodPivot"
		var kids := tool.get_children()
		tool.add_child(pivot)
		for kid in kids: kid.reparent(pivot,false)
	# Swing about the walker's right axis; pick the sign that tips the rod backwards.
	var right: Vector3=app.player.visual.global_basis.x.normalized()
	rod_axis=(tool.global_basis.inverse()*right).normalized()
	var base := tip()
	pivot.basis=Basis(rod_axis,0.6)
	var facing: Vector3=(cast_at-app.player.position)*Vector3(1,0,1)
	rod_sign=-1.0 if (tip()-base).dot(facing)>0 else 1.0
	pivot.basis=Basis.IDENTITY

func set_rod(angle: float) -> void:
	rod_angle=angle
	if is_instance_valid(pivot): pivot.basis=Basis(rod_axis,angle*rod_sign)

func tip() -> Vector3:
	var tool: Node3D=app.player.tool_node
	var local: Vector3=tool.get_meta("line_tip",Vector3(0,2.3,0)) if is_instance_valid(tool) else Vector3.ZERO
	if is_instance_valid(pivot): return pivot.to_global(local)
	if is_instance_valid(tool): return tool.to_global(local)
	return app.player.position+Vector3(0.35,2.2,0.7)

func press() -> void:
	match phase:
		"ready": cast()
		"waiting": hook()
		"card": dismiss_card()

func cast() -> void:
	if int(life.state.bag.get("bait",0))<1:
		app.message(tr("미끼가 없어요. 씨앗 노점에서 미끼를 사 오세요."))
		life.sfx.play("escape")
		return
	phase="casting"
	refresh_hud()
	app.player.face_point(cast_at)
	var t := create_tween()
	t.tween_method(set_rod,0.0,1.15,0.28).set_ease(Tween.EASE_OUT)
	await t.finished
	life.sfx.play("cast")
	app.player.react("gather")
	var data: Dictionary=await life.request("cast",{"spot":spot})
	if phase!="casting": return
	if data.is_empty():
		set_rod(0)
		phase="ready"
		refresh_hud()
		return
	nibbles_seen={}
	bite_shown=false
	var swing := create_tween()
	swing.tween_method(set_rod,1.15,-0.55,0.16).set_ease(Tween.EASE_IN)
	swing.tween_method(set_rod,-0.55,-0.25,0.4)
	ensure_bobber()
	flight=0.0
	phase="flying"
	refresh_hud()

func ensure_bobber() -> void:
	if not is_instance_valid(bobber):
		bobber=Node3D.new()
		app.world.add_child(bobber)
		Art.part(bobber,"dome",Vector3(0,0.0,0),Vector3(0.24,0.26,0.24),Color("e2493b"),Vector3.ZERO,0.4)
		Art.part(bobber,"dome",Vector3(0,0.0,0),Vector3(0.24,0.2,0.24),Color("f8f4ea"),Vector3(PI,0,0),0.4)
		Art.part(bobber,"rod",Vector3(0,0.13,0),Vector3(0.025,0.14,0.025),Color("f3d36a"))
	if not is_instance_valid(line):
		line=MeshInstance3D.new()
		line.material_override=Art.mat(Color("f2ead2"),1.0,0.0,true)
		line.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		app.world.add_child(line)
	bobber.visible=true
	line.visible=true

func stretch_line(sag: float) -> void:
	if not is_instance_valid(line) or not is_instance_valid(bobber): return
	var a := tip()
	var b := bobber.global_position+Vector3(0,0.12,0)
	var im := ImmediateMesh.new()
	im.surface_begin(Mesh.PRIMITIVE_LINE_STRIP)
	for i in 13:
		var v := i/12.0
		im.surface_add_vertex(a.lerp(b,v)-Vector3(0,sin(v*PI)*sag,0))
	im.surface_end()
	line.mesh=im

func land_bobber() -> void:
	life.sfx.play("plop")
	Art.burst(app.world,cast_at,"splash",14)
	Art.ripple(app.world,cast_at,1.1,1.2)
	get_tree().create_timer(0.25).timeout.connect(func(): if phase=="waiting": Art.ripple(app.world,cast_at,0.8,1.0,Color(1,1,1,0.45)))
	phase="waiting"
	refresh_hud()

func hook() -> void:
	phase="hooking"
	app.player.react("gather")
	var t := create_tween()
	t.tween_method(set_rod,rod_angle,0.9,0.12)
	var data: Dictionary=await life.request("reel")
	if phase!="hooking": return
	var reward: Dictionary=data.get("reward",{})
	if reward.get("kind","")=="hooked":
		start_fight(data.fishing)
		return
	if not data.is_empty(): app.message(data.message)
	life.sfx.play("escape")
	reel_back()

## Bobber skips back to the rod tip after a miss or a lost fish.
func reel_back() -> void:
	if is_instance_valid(alert): alert.queue_free()
	if is_instance_valid(meter): meter.queue_free()
	phase="reeling"
	refresh_hud()
	if is_instance_valid(bobber):
		var from := bobber.global_position
		var t := create_tween()
		t.tween_method(func(v: float):
			if is_instance_valid(bobber): bobber.global_position=from.lerp(tip(),v)+Vector3(0,sin(v*PI)*0.8,0)
			stretch_line(0.0),0.0,1.0,0.45)
		await t.finished
	if is_instance_valid(bobber): bobber.visible=false
	if is_instance_valid(line): line.visible=false
	set_rod(0)
	if phase=="reeling":
		phase="ready"
		refresh_hud()

func start_fight(fish: Dictionary) -> void:
	phase="fight"
	var difficulty: int=int(fish.get("difficulty",1))
	fight_min=float(fish.get("fight_min",2.0))
	fill=0.7/(fight_min+0.45)
	drain=0.09+0.035*difficulty
	zone_w=0.28-0.025*difficulty
	fish_speed=0.22+0.11*difficulty
	shadow_kind=str(fish.get("shadow","small"))
	progress=0.3
	fight_time=0.0
	fish_x=0.5
	fish_goal=0.5
	zone_x=0.5-zone_w*0.5
	zone_v=0.0
	if is_instance_valid(alert): alert.queue_free()
	life.sfx.play("bite",1.2)
	Art.burst(app.world,cast_at,"splash",18)
	build_meter()
	refresh_hud()

func land() -> void:
	phase="landing"
	refresh_hud()
	var data: Dictionary=await life.request("reel",{"outcome":"landed"})
	if phase!="landing": return
	if is_instance_valid(meter): meter.queue_free()
	var reward: Dictionary=data.get("reward",{})
	if reward.get("kind","")!="fish":
		if not data.is_empty(): app.message(data.message)
		reel_back()
		return
	show_catch(reward)

func lose() -> void:
	phase="landing"
	var data: Dictionary=await life.request("reel",{"outcome":"lost"})
	if not data.is_empty(): app.message(data.message)
	life.sfx.play("escape")
	if phase=="landing": reel_back()

# ------------------------------------------------------------------ frame

func update(delta: float) -> void:
	if phase.is_empty(): return
	var now: float=life.now()
	var fish=life.state.get("fishing")
	if is_instance_valid(app.player): app.player.controls_enabled=false
	if phase=="flying":
		flight=minf(1.0,flight+delta/0.62)
		var from := tip()
		var p := from.lerp(cast_at,flight)
		p.y+=sin(flight*PI)*2.4
		bobber.global_position=p
		stretch_line(0.05)
		if flight>=1.0: land_bobber()
		return
	if phase in ["waiting","hooking"] and is_instance_valid(bobber):
		var t := Time.get_ticks_msec()*0.001
		var y := cast_at.y+0.02+sin(t*2.4)*0.015
		var bite: bool=fish is Dictionary and now>=float(fish.bite_at) and now<=float(fish.ends_at)
		if fish is Dictionary:
			for at in fish.get("nibbles",[]):
				var key := str(at)
				if now>=float(at) and now<float(at)+0.35:
					y-=0.07*sin((now-float(at))/0.35*PI)
					if not nibbles_seen.has(key):
						nibbles_seen[key]=true
						life.sfx.play("nibble",randf_range(0.9,1.15))
						Art.ripple(app.world,cast_at,0.5,0.7,Color(1,1,1,0.5))
			if bite:
				y=cast_at.y-0.24+sin(t*31)*0.03
				if not bite_shown:
					bite_shown=true
					show_bite()
			elif phase=="waiting" and now>float(fish.ends_at):
				app.message(tr("물고기가 미끼만 먹고 달아났어요. E로 다시 던져 보세요."))
				reel_back()
				return
		bobber.global_position=Vector3(cast_at.x,y,cast_at.z)
		ripple_clock+=delta
		if ripple_clock>2.3:
			ripple_clock=0
			Art.ripple(app.world,cast_at,0.6,1.4,Color(1,1,1,0.28))
		stretch_line(0.18 if not bite else 0.0)
		if is_instance_valid(status) and phase=="waiting":
			status.text=tr("입질! 지금 E!") if bite else tr("찌를 지켜보세요…")
			status.modulate=Color("ffe07a") if bite else Color.WHITE
	if phase=="fight": fight(delta)
	if phase=="card":
		card_clock+=delta
		if is_instance_valid(trophy): trophy.rotation=Vector3(0,sin(card_clock*2.2)*0.35,sin(card_clock*3.1)*0.12)
		if card_clock>7.0: dismiss_card()

func show_bite() -> void:
	life.sfx.play("bite")
	Art.burst(app.world,cast_at,"splash",20)
	Art.ripple(app.world,cast_at,1.3,0.9)
	Art.ripple(app.world,cast_at,0.9,0.7,Color(1,1,1,0.5))
	alert=Label3D.new()
	alert.text="!"
	alert.font_size=150
	alert.outline_size=26
	alert.modulate=Color("ffd34d")
	alert.outline_modulate=Color("5a3a12")
	alert.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	alert.no_depth_test=true
	alert.pixel_size=0.006
	alert.position=app.player.position+Vector3(0,2.9,0)
	alert.scale=Vector3.ONE*0.2
	app.world.add_child(alert)
	alert.create_tween().tween_property(alert,"scale",Vector3.ONE,0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

func fight(delta: float) -> void:
	fight_time+=delta
	var hold := Input.is_action_pressed("interact") or Input.is_action_pressed("attack") or Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
	fish_clock-=delta
	if fish_clock<=0:
		fish_clock=randf_range(0.45,1.5)/(0.7+fish_speed)
		fish_goal=clampf(fish_x+randf_range(-0.55,0.55),0.03,0.97)
	fish_x=move_toward(fish_x,fish_goal,fish_speed*delta*(1.6 if absf(fish_goal-fish_x)>0.3 else 1.0))
	if auto_reel: hold=fish_x>zone_x+zone_w*0.5+zone_v*0.15
	zone_v=clampf(zone_v+(2.4 if hold else -2.0)*delta,-1.3,1.3)
	zone_x+=zone_v*delta
	if zone_x<0:
		zone_x=0
		zone_v=absf(zone_v)*0.25
	if zone_x>1.0-zone_w:
		zone_x=1.0-zone_w
		zone_v=-absf(zone_v)*0.25
	var inside := fish_x>=zone_x and fish_x<=zone_x+zone_w
	progress=clampf(progress+(fill if inside else -drain)*delta,0.0,1.0)
	if hold:
		tick_clock-=delta
		if tick_clock<=0:
			tick_clock=0.075
			life.sfx.play("tick",randf_range(0.95,1.1),-6)
	splash_clock-=delta
	if splash_clock<=0:
		splash_clock=randf_range(0.35,0.8)
		var jitter := Vector3(randf_range(-0.5,0.5),0,randf_range(-0.5,0.5))
		Art.burst(app.world,cast_at+jitter,"splash",6 if shadow_kind=="small" else 10)
		Art.ripple(app.world,cast_at+jitter,0.6,0.7,Color(1,1,1,0.4))
	if is_instance_valid(bobber):
		var t := Time.get_ticks_msec()*0.001
		bobber.global_position=cast_at+Vector3(sin(t*7)*0.35,-0.12+sin(t*23)*0.05,cos(t*5)*0.3)
		stretch_line(0.0)
	set_rod(lerpf(rod_angle,0.55+sin(Time.get_ticks_msec()*0.03)*0.06*(1.0 if inside else 2.0),0.2))
	if is_instance_valid(meter):
		meter.set_meta("inside",inside)
		meter.queue_redraw()
	if progress>=1.0 and fight_time>=fight_min+0.2: land()
	elif progress<=0.0: lose()

# ------------------------------------------------------------------ catch

func show_catch(reward: Dictionary) -> void:
	phase="card"
	card_clock=0.0
	life.sfx.play("catch")
	var kind: String=reward.item
	var length := clampf(0.45+float(reward.size)/100.0*1.1,0.6,1.8)
	trophy=Node3D.new()
	app.world.add_child(trophy)
	var model := Art.fish(kind,length)
	model.rotation=Vector3(-0.2,PI/2,0)
	trophy.add_child(model)
	Art.sparkles(trophy,0.0)
	var head: Vector3=app.player.position+Vector3(0,2.75,0)
	var from: Vector3=bobber.global_position if is_instance_valid(bobber) else cast_at
	if is_instance_valid(bobber): bobber.visible=false
	if is_instance_valid(line): line.visible=false
	set_rod(0)
	trophy.global_position=from
	var t := trophy.create_tween()
	t.tween_method(func(v: float): trophy.global_position=from.lerp(head,v)+Vector3(0,sin(v*PI)*1.5,0),0.0,1.0,0.55).set_ease(Tween.EASE_OUT)
	Art.burst(app.world,cast_at,"splash",22)
	app.player.react("craft")
	build_card(reward)
	refresh_hud()

func dismiss_card() -> void:
	if is_instance_valid(card):
		var c := card
		var t := c.create_tween()
		t.tween_property(c,"modulate:a",0.0,0.2)
		t.tween_callback(c.queue_free)
	if is_instance_valid(trophy):
		life.fly_items({str(life.last_reward.get("item","")):1},trophy.global_position)
		trophy.queue_free()
	phase="ready"
	refresh_hud()

# ------------------------------------------------------------------ UI

func build_hud() -> void:
	hud=Control.new()
	hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	hud.mouse_filter=Control.MOUSE_FILTER_IGNORE
	var pill := PanelContainer.new()
	pill.add_theme_stylebox_override("panel",RpgUi.panel_style("pill"))
	pill.position=Vector2(390,18)
	pill.custom_minimum_size=Vector2(500,0)
	pill.mouse_filter=Control.MOUSE_FILTER_IGNORE
	hud.add_child(pill)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation",12)
	pill.add_child(row)
	row.add_child(Icon.make("bait",40))
	var column := VBoxContainer.new()
	column.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	row.add_child(column)
	status=RpgUi.label(column,"",18,RpgUi.INK)
	keys=RpgUi.label(column,"",13,RpgUi.GOLD,false)
	life.claim_hud(hud)

func refresh_hud() -> void:
	if not is_instance_valid(status): return
	var bait := int(life.state.get("bag",{}).get("bait",0))
	var where := tr(SPOT_NAMES.get(spot,"바다"))
	var hint := ""
	match phase:
		"ready":
			status.text=tr("%s 낚시 · 미끼 %d개") % [where,bait]
			hint=tr("E 찌 던지기   ·   Esc 그만하기")
		"casting","flying": status.text=tr("휙—!")
		"waiting":
			status.text=tr("찌를 지켜보세요…")
			hint=tr("찌가 쑥 잠기면 E   ·   톡톡 건드릴 때는 기다리기")
		"hooking": status.text=tr("챔질!")
		"fight":
			status.text=tr("걸렸다! 물고기를 초록 칸 안에 두세요")
			hint=tr("E·Space·클릭을 누르고 있으면 칸이 오른쪽으로, 떼면 왼쪽으로")
		"landing": status.text=tr("끌어올리는 중…")
		"reeling": status.text=tr("줄을 감는 중…")
		"card":
			status.text=tr("%s 낚시 · 미끼 %d개") % [where,bait]
			hint=tr("E 계속 낚시   ·   Esc 그만하기")
	status.modulate=Color.WHITE
	keys.text=hint

func build_meter() -> void:
	if is_instance_valid(meter): meter.queue_free()
	meter=Control.new()
	meter.position=Vector2(340,150)
	meter.size=Vector2(600,104)
	meter.mouse_filter=Control.MOUSE_FILTER_IGNORE
	meter.draw.connect(draw_meter)
	if is_instance_valid(hud): hud.add_child(meter)

func draw_meter() -> void:
	var w := 600.0
	var font: Font = RpgUi.FONT_STRONG
	meter.draw_style_box(RpgUi.panel_style("night_plain"),Rect2(0,0,w,104))
	var lane := Rect2(24,20,w-48,42)
	var water := StyleBoxFlat.new()
	water.bg_color=Color("2f7f9a")
	water.set_corner_radius_all(14)
	water.border_color=Color("1d4f61")
	water.set_border_width_all(2)
	meter.draw_style_box(water,lane)
	for i in 6:
		var x := lane.position.x+fmod(i*97.0+Time.get_ticks_msec()*0.03,lane.size.x)
		meter.draw_line(Vector2(x,lane.position.y+12+(i%3)*8),Vector2(x+18,lane.position.y+12+(i%3)*8),Color(1,1,1,0.18),2)
	var inside: bool=meter.get_meta("inside",false)
	var zone := Rect2(lane.position.x+zone_x*lane.size.x,lane.position.y-4,zone_w*lane.size.x,lane.size.y+8)
	var box := StyleBoxFlat.new()
	box.bg_color=Color(0.55,0.95,0.55,0.38 if inside else 0.22)
	box.border_color=Color("b8f59a") if inside else Color("8ccf7a")
	box.set_border_width_all(3)
	box.set_corner_radius_all(10)
	meter.draw_style_box(box,zone)
	var fx := lane.position.x+fish_x*lane.size.x
	var wiggle := sin(Time.get_ticks_msec()*0.025)*3
	var fish_c := Vector2(fx,lane.position.y+lane.size.y*0.5+wiggle)
	var r := 13.0 if shadow_kind=="small" else 17.0
	var body := PackedVector2Array()
	for i in 16: body.append(fish_c+Vector2(cos(TAU*i/16)*r*1.4,sin(TAU*i/16)*r*0.7))
	meter.draw_colored_polygon(body,Color("17313b"))
	meter.draw_colored_polygon(PackedVector2Array([fish_c+Vector2(r*1.2,0),fish_c+Vector2(r*2.2,-r*0.8),fish_c+Vector2(r*2.2,r*0.8)]),Color("17313b"))
	var bar := Rect2(24,74,w-48,14)
	var back := StyleBoxFlat.new()
	back.bg_color=Color(0,0,0,0.35)
	back.set_corner_radius_all(7)
	meter.draw_style_box(back,bar)
	var front := StyleBoxFlat.new()
	front.bg_color=Color("f3c552").lerp(Color("9de07a"),progress)
	front.set_corner_radius_all(7)
	if progress>0.02: meter.draw_style_box(front,Rect2(bar.position,Vector2(bar.size.x*progress,bar.size.y)))
	meter.draw_string(font,Vector2(28,16),tr("긴장도"),HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color(RpgUi.GOLD,0.85))

func build_card(reward: Dictionary) -> void:
	if is_instance_valid(card): card.queue_free()
	var data: Dictionary=life.state.get("catalog",{}).get("fish",{}).get(reward.item,{})
	card=PanelContainer.new()
	card.add_theme_stylebox_override("panel",RpgUi.panel_style("paper"))
	card.position=Vector2(860,250)
	card.custom_minimum_size=Vector2(330,0)
	card.mouse_filter=Control.MOUSE_FILTER_IGNORE
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation",4)
	card.add_child(v)
	var ribbon := ""
	if reward.get("first",false): ribbon=tr("새로운 물고기 발견!")
	elif reward.get("record",false): ribbon=tr("최고 기록 갱신!")
	if not ribbon.is_empty():
		var r := RpgUi.label(v,ribbon,15,Color("b0452f"),false)
		r.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var art := Icon.make(reward.item,150)
	art.size_flags_horizontal=Control.SIZE_SHRINK_CENTER
	art.custom_minimum_size=Vector2(260,130)
	v.add_child(art)
	var name := RpgUi.label(v,tr(str(data.get("name",reward.item))),26,Color("3b2a1c"),false)
	name.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var stars := "★".repeat(int(data.get("rarity",1)))+"☆".repeat(3-int(data.get("rarity",1)))
	var line1 := RpgUi.label(v,"%s   %.1f cm" % [stars,float(reward.size)],18,Color("8a5a1c"),false)
	line1.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var hint := RpgUi.label(v,tr("%s · 판매가 %d잎전") % [tr(SPOT_NAMES.get(str(reward.get("spot","sea")),"바다")),int(data.get("price",0))],14,Color("5d4a35"),false)
	hint.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	if is_instance_valid(hud): hud.add_child(card)
	card.pivot_offset=Vector2(165,160)
	card.scale=Vector2(0.6,0.6)
	card.modulate.a=0
	var t := card.create_tween().set_parallel(true)
	t.tween_property(card,"scale",Vector2.ONE,0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(card,"modulate:a",1.0,0.2)
