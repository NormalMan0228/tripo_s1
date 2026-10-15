extends Node
## Fishing from any shore: cast arc, bobber and ripples, nibbles, the bite, a reel
## fight on a bar or a ring, and the catch card. The server (homestead.py) picks the fish,
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
## Ring meter: panel centre on the 1280-wide HUD (beside the angler), panel size, channel
## radius and width. The vertical gauge stands at the same spot.
const RING_AT := Vector2(905,280)
const GAUGE_SIZE := Vector2(120,300)
const RING_SIZE := 260.0
const RING_R := 88.0
const RING_TRACK := 30.0
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
## Move keys end fishing in the ready/card phases, but only once they were let go after it began
## (the walk up to the shore usually still holds one when E is pressed).
var move_armed := false
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
## Meter shape (shape_for): "lane", "gauge" (the lane stood upright: same physics) or "ring". On
## the ring fish_x, fish_goal, zone_x and zone_v are in turns (1.0 = once round) and never wrap;
## fish_gap() measures the short way round. Holding the reel pushes the zone right (lane), up
## (gauge) or clockwise (ring).
var meter_shape := "lane"
var push := 2.4
var pull := 2.0
var zone_vmax := 1.3
var fish_dir := -1.0
var zone_inside := false
var reel_held := false

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
	life.sfx.play("rod_equip",1.0,-3)
	rig_rod()
	build_hud()
	move_armed=false
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
		# The deny stamps the toast dedupe, so the message's chime stays quiet (one sound).
		life.deny()
		app.message(tr("미끼가 없어요. 씨앗 노점에서 미끼를 사 오세요."))
		return
	phase="casting"
	refresh_hud()
	app.player.face_point(cast_at)
	life.sfx.play("windup",1.0,-4)
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
	life.sfx.play("whiz",randf_range(0.94,1.06),-5)
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
	life.sfx.play("strike")
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
		life.sfx.play("reel_back",1.0,-3)
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

## The server sends only the difficulty and shadow at the hook (not the species), so the shape
## follows the difficulty alone: the same fish always fights on the same meter. 1 lane, 2 the
## upright gauge, 3-5 the ring.
static func shape_for(difficulty: int) -> String:
	if difficulty>=3: return "ring"
	return "gauge" if difficulty==2 else "lane"

## The fight's numbers for a hooked fish, without effects (fishing_shapes_check drives step()).
func setup_fight(fish: Dictionary) -> void:
	var difficulty: int=int(fish.get("difficulty",1))
	fight_min=float(fish.get("fight_min",2.0))
	fill=0.7/(fight_min+0.45)
	drain=0.09+0.035*difficulty
	meter_shape=shape_for(difficulty)
	if meter_shape=="ring":
		# Arc 72°/65°/58° for difficulty 3/4/5. Tuned with a reaction-delay player model so a ring
		# fight lands about as often as the lane would at the same difficulty (a bit kinder at 3-4).
		zone_w=0.26-0.02*difficulty
		fish_speed=(0.22+0.11*difficulty)*0.7
		push=2.0
		pull=1.7
		zone_vmax=0.9
	else:
		zone_w=0.28-0.025*difficulty
		fish_speed=0.22+0.11*difficulty
		push=2.4
		pull=2.0
		zone_vmax=1.3
	shadow_kind=str(fish.get("shadow","small"))
	progress=0.3
	fight_time=0.0
	fish_x=0.5
	fish_goal=0.5
	fish_dir=-1.0
	zone_x=0.5-zone_w*0.5
	zone_v=0.0
	zone_inside=true
	reel_held=false

func start_fight(fish: Dictionary) -> void:
	phase="fight"
	setup_fight(fish)
	if is_instance_valid(alert): alert.queue_free()
	life.sfx.play("bite",1.2)
	Art.burst(app.world,cast_at,"splash",18)
	build_meter()
	refresh_hud()

func land() -> void:
	phase="landing"
	life.sfx.play("strike",0.86,-2)
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
	if phase in ["ready","card"] and walked_away(): return
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
			ripple_clock=randf_range(-0.6,0.4)
			Art.ripple(app.world,cast_at,0.6,1.4,Color(1,1,1,0.28))
			life.sfx.play("ripple",randf_range(0.92,1.08),-11)
		stretch_line(0.18 if not bite else 0.0)
		if is_instance_valid(status) and phase=="waiting":
			status.text=tr("입질! 지금 E!") if bite else tr("찌를 지켜보세요…")
			status.modulate=Color("ffe07a") if bite else Color.WHITE
	if phase=="fight": fight(delta)
	if phase=="card":
		card_clock+=delta
		if is_instance_valid(trophy): trophy.rotation=Vector3(0,sin(card_clock*2.2)*0.35,sin(card_clock*3.1)*0.12)
		if card_clock>7.0: dismiss_card()

## A move key while ready to cast (or on the catch card) walks away: fishing ends as with Esc.
func walked_away() -> bool:
	# Typing in chat (WASD are letters there) never walks away.
	if app.has_method("text_input_active") and app.text_input_active(): return false
	if Input.get_vector("move_left","move_right","move_forward","move_back").length()<0.5:
		move_armed=true
		return false
	if not move_armed: return false
	if phase=="card": dismiss_card()
	app.close_village_modal()
	return true

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

## One frame of the reel fight's physics on either meter: the fish swims, the zone answers the
## reel (auto_reel decides instead when set) and the line tension fills or drains. Returns whether
## the reel was held.
func step(delta: float, hold: bool) -> bool:
	fish_clock-=delta
	if fish_clock<=0:
		fish_clock=randf_range(0.45,1.5)/(0.7+fish_speed)
		if meter_shape=="ring": fish_goal=fish_x+randf_range(-0.4,0.4)
		else: fish_goal=clampf(fish_x+randf_range(-0.55,0.55),0.03,0.97)
	if absf(fish_goal-fish_x)>0.004: fish_dir=signf(fish_goal-fish_x)
	fish_x=move_toward(fish_x,fish_goal,fish_speed*delta*(1.6 if absf(fish_goal-fish_x)>0.3 else 1.0))
	if auto_reel: hold=auto_hold()
	zone_v=clampf(zone_v+(push if hold else -pull)*delta,-zone_vmax,zone_vmax)
	zone_x+=zone_v*delta
	if meter_shape=="ring":
		zone_inside=absf(fish_gap())<=zone_w*0.5
	else:
		if zone_x<0:
			zone_x=0
			zone_v=absf(zone_v)*0.25
		if zone_x>1.0-zone_w:
			zone_x=1.0-zone_w
			zone_v=-absf(zone_v)*0.25
		zone_inside=fish_x>=zone_x and fish_x<=zone_x+zone_w
	progress=clampf(progress+(fill if zone_inside else -drain)*delta,0.0,1.0)
	reel_held=hold
	return hold

## How far the fish is ahead of the zone's centre (minus `lead`), in the hold direction: along
## the lane, or the short way round the ring (-0.5..0.5 turns).
func fish_gap(lead := 0.0) -> float:
	var gap := fish_x-(zone_x+zone_w*0.5)-lead
	return wrapf(gap,-0.5,0.5) if meter_shape=="ring" else gap

## auto_reel (tests, demo): hold while the fish is ahead of where the zone is heading.
func auto_hold() -> bool:
	return fish_gap(zone_v*0.15)>0

func fight(delta: float) -> void:
	fight_time+=delta
	var hold := Input.is_action_pressed("interact") or Input.is_action_pressed("attack") or Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
	hold=step(delta,hold)
	var inside := zone_inside
	if hold:
		tick_clock-=delta
		if tick_clock<=0:
			# Reel ratchet: uneven pawl spacing, brighter and quicker as the line tightens.
			tick_clock=0.075*randf_range(0.8,1.2)*(1.0-0.2*progress)
			life.sfx.play("tick",lerpf(0.93,1.08,progress),0.0+2.0*progress+randf_range(-1.0,1.0))
	splash_clock-=delta
	if splash_clock<=0:
		splash_clock=randf_range(0.35,0.8)
		var jitter := Vector3(randf_range(-0.5,0.5),0,randf_range(-0.5,0.5))
		Art.burst(app.world,cast_at+jitter,"splash",6 if shadow_kind=="small" else 10)
		Art.ripple(app.world,cast_at+jitter,0.6,0.7,Color(1,1,1,0.4))
		if shadow_kind=="small": life.sfx.play("thrash",randf_range(1.08,1.2),-7)
		else: life.sfx.play("thrash",randf_range(0.84,0.96),-2)
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
	life.sfx.play("fish_out")
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
	get_tree().create_timer(0.22).timeout.connect(func(): if is_instance_valid(card): life.sfx.play("card",1.0,-7))
	refresh_hud()

func dismiss_card() -> void:
	if is_instance_valid(card):
		life.sfx.play("card",1.12,-6)
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
	row.add_child(RpgUi.name_tip(Icon.make("bait",40),tr("미끼")))
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
			if meter_shape=="ring": hint=tr("%s·Space·클릭을 누르고 있으면 초록 호가 시계 방향으로, 떼면 반대로") % RpgUi.key_text("interact")
			elif meter_shape=="gauge": hint=tr("%s·Space·클릭을 누르고 있으면 칸이 위로, 떼면 아래로") % RpgUi.key_text("interact")
			else: hint=tr("%s·Space·클릭을 누르고 있으면 칸이 오른쪽으로, 떼면 왼쪽으로") % preload("res://scripts/rpg_ui.gd").key_text("interact")
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
	if meter_shape=="ring":
		# Beside the angler (right of centre) so the ring never covers them.
		meter.position=Vector2(RING_AT.x-RING_SIZE*0.5,RING_AT.y-RING_SIZE*0.5)
		meter.size=Vector2(RING_SIZE,RING_SIZE)
	elif meter_shape=="gauge":
		meter.position=RING_AT-GAUGE_SIZE*0.5
		meter.size=GAUGE_SIZE
	meter.mouse_filter=Control.MOUSE_FILTER_IGNORE
	meter.draw.connect(draw_meter)
	if is_instance_valid(hud): hud.add_child(meter)
	if meter_shape!="lane":
		meter.pivot_offset=meter.size*0.5
		meter.scale=Vector2(0.7,0.7)
		meter.modulate.a=0.0
		var t := meter.create_tween().set_parallel(true)
		t.tween_property(meter,"scale",Vector2.ONE,0.3).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		t.tween_property(meter,"modulate:a",1.0,0.18)

func draw_meter() -> void:
	if meter_shape=="ring":
		draw_ring()
		return
	if meter_shape=="gauge":
		draw_gauge()
		return
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

## Where `turns` sits on the ring: 0.5 (the start) at the top, growing clockwise.
static func ring_angle(turns: float) -> float:
	return (turns-0.5)*TAU-PI*0.5

## A band along a circle from angle a0 to a1 (clockwise) with rounded ends that stay inside it.
static func arc_band(c: Vector2, r: float, hw: float, a0: float, a1: float) -> PackedVector2Array:
	var k := minf(hw*0.6/r,(a1-a0)*0.4)
	var depth := k*r
	var pts := PackedVector2Array()
	for i in 25: pts.append(c+Vector2.from_angle(lerpf(a0+k,a1-k,i/24.0))*(r+hw))
	var u := Vector2.from_angle(a1-k)
	for i in range(1,8): pts.append(c+u*r+u*hw*cos(PI*i/8.0)+Vector2(-u.y,u.x)*depth*sin(PI*i/8.0))
	for i in 25: pts.append(c+Vector2.from_angle(lerpf(a1-k,a0+k,i/24.0))*(r-hw))
	u=Vector2.from_angle(a0+k)
	for i in range(1,8): pts.append(c+u*r-u*hw*cos(PI*i/8.0)-Vector2(-u.y,u.x)*depth*sin(PI*i/8.0))
	return pts

## The ring meter: a round water channel the fish swims along, the green arc the reel turns
## (a chevron shows which way it is moving) and the line tension filling the gauge inside.
func draw_ring() -> void:
	var c := Vector2(RING_SIZE,RING_SIZE)*0.5
	var ms := Time.get_ticks_msec()*0.001
	var half := RING_TRACK*0.5
	meter.draw_style_box(RpgUi.panel_style("night_plain"),Rect2(0,0,RING_SIZE,RING_SIZE))
	# Channel: dark rim, water, a shaded inner lip and a light outer lip.
	meter.draw_arc(c,RING_R,0,TAU,96,Color("1d4f61"),RING_TRACK+4,true)
	meter.draw_arc(c,RING_R,0,TAU,96,Color("2f7f9a"),RING_TRACK,true)
	meter.draw_arc(c,RING_R-half+3,0,TAU,96,Color(0,0,0,0.16),4,true)
	meter.draw_arc(c,RING_R+half-2,0,TAU,96,Color(1,1,1,0.1),2,true)
	# Ripple marks drift the way the arc goes when the reel is let go (anticlockwise).
	for i in 7:
		var a := fposmod(i*0.9-ms*0.55,TAU)
		meter.draw_arc(c,RING_R-8+(i%3)*8,a,a+0.16,6,Color(1,1,1,0.18),2,true)
	var inside: bool=meter.get_meta("inside",false)
	var mid := ring_angle(zone_x+zone_w*0.5)
	var span := zone_w*TAU*0.5
	if inside: meter.draw_colored_polygon(arc_band(c,RING_R,half+10,mid-span-0.03,mid+span+0.03),Color(0.6,1.0,0.5,0.14))
	var band := arc_band(c,RING_R,half+5,mid-span,mid+span)
	meter.draw_colored_polygon(band,Color(0.55,0.95,0.55,0.38 if inside else 0.22))
	band.append(band[0])
	meter.draw_polyline(band,Color("b8f59a") if inside else Color("8ccf7a"),3,true)
	var speed := clampf(absf(zone_v)/zone_vmax,0.0,1.0)
	if speed>0.15:
		var way := signf(zone_v)
		for k in 2:
			var eu := Vector2.from_angle(mid+way*(span+0.1+k*0.09))
			var ev := Vector2(-eu.y,eu.x)*way
			var tip_at := c+eu*RING_R+ev*4
			meter.draw_polyline(PackedVector2Array([tip_at-ev*6+eu*8,tip_at,tip_at-ev*6-eu*8]),Color(0.86,1.0,0.76,(0.35+0.6*speed)*(1.0-k*0.45)),3,true)
	# The fish swims along the channel.
	var u := Vector2.from_angle(ring_angle(fish_x))
	draw_fish(c+u*(RING_R+sin(ms*25.0)*2.0),Vector2(-u.y,u.x)*fish_dir,10.0 if shadow_kind=="small" else 13.0,ms)
	# Tension gauge round a little reel that turns with the arc.
	var gauge := RING_R-half-17
	meter.draw_arc(c,gauge,0,TAU,64,Color(0,0,0,0.35),9,true)
	if progress>0.01:
		var tint := Color("f3c552").lerp(Color("9de07a"),progress)
		var a1 := -PI*0.5+TAU*progress
		meter.draw_arc(c,gauge,-PI*0.5,a1,maxi(6,int(64*progress)),tint,9,true)
		meter.draw_circle(c+Vector2(0,-gauge),4.5,tint,true,-1.0,true)
		meter.draw_circle(c+Vector2.from_angle(a1)*gauge,4.5,tint,true,-1.0,true)
	meter.draw_circle(c,22,Color("152634"),true,-1.0,true)
	meter.draw_arc(c,22,0,TAU,40,Color(RpgUi.GOLD,0.85),2,true)
	var spin := zone_x*TAU*1.5
	for k in 3:
		var d := Vector2.from_angle(spin+k*TAU/3)
		meter.draw_line(c+d*6,c+d*17,Color(RpgUi.GOLD,0.7),3,true)
	meter.draw_circle(c,5,RpgUi.GOLD,true,-1.0,true)
	meter.draw_string(RpgUi.FONT_STRONG,Vector2(c.x-40,c.y+41),tr("긴장도"),HORIZONTAL_ALIGNMENT_CENTER,80,12,Color(RpgUi.GOLD,0.85))

## A fish silhouette heading `ahead` (unit), tail wagging, a couple of bubbles behind it.
func draw_fish(fc: Vector2, ahead: Vector2, r: float, ms: float) -> void:
	var side := Vector2(-ahead.y,ahead.x)
	var body := PackedVector2Array()
	for i in 16: body.append(fc+ahead*cos(TAU*i/16)*r*1.4+side*sin(TAU*i/16)*r*0.7)
	meter.draw_colored_polygon(body,Color("17313b"))
	body.append(body[0])
	meter.draw_polyline(body,Color("17313b"),1.2,true)
	var tail_at := fc-ahead*r*1.2
	var back := (-ahead).rotated(sin(ms*16.0)*0.3)
	var fin := Vector2(-back.y,back.x)
	var tail := PackedVector2Array([tail_at,tail_at+back*r+fin*r*0.8,tail_at+back*r-fin*r*0.8])
	meter.draw_colored_polygon(tail,Color("17313b"))
	tail.append(tail[0])
	meter.draw_polyline(tail,Color("17313b"),1.2,true)
	for k in 2:
		var bubble := tail_at+back*r*(1.8+k*0.9)+side*sin(ms*6.0+k*2.0)*3.0
		meter.draw_circle(bubble,2.6-k*0.8,Color(1,1,1,0.32-k*0.1),true,-1.0,true)

## The upright gauge: the lane stood on end (hold lifts the zone, letting go lets it sink), with
## bubbles rising in the water and the tension bar filling upward beside it.
func draw_gauge() -> void:
	var ms := Time.get_ticks_msec()*0.001
	meter.draw_style_box(RpgUi.panel_style("night_plain"),Rect2(Vector2.ZERO,GAUGE_SIZE))
	var tube := Rect2(22,34,46,GAUGE_SIZE.y-58)
	var water := StyleBoxFlat.new()
	water.bg_color=Color("2f7f9a")
	water.set_corner_radius_all(14)
	water.border_color=Color("1d4f61")
	water.set_border_width_all(2)
	meter.draw_style_box(water,tube)
	for i in 6:
		var y := tube.end.y-8-fmod(i*41.0+ms*28.0,tube.size.y-16)
		meter.draw_circle(Vector2(tube.position.x+11+(i%3)*12,y),1.6+(i%2),Color(1,1,1,0.2),true,-1.0,true)
	var inside: bool=meter.get_meta("inside",false)
	var zone := Rect2(tube.position.x-4,tube.end.y-(zone_x+zone_w)*tube.size.y,tube.size.x+8,zone_w*tube.size.y)
	var box := StyleBoxFlat.new()
	box.bg_color=Color(0.55,0.95,0.55,0.38 if inside else 0.22)
	box.border_color=Color("b8f59a") if inside else Color("8ccf7a")
	box.set_border_width_all(3)
	box.set_corner_radius_all(10)
	meter.draw_style_box(box,zone)
	var fc := Vector2(tube.get_center().x+sin(ms*25.0)*2.0,tube.end.y-fish_x*tube.size.y)
	draw_fish(fc,Vector2(0,-fish_dir),9.0 if shadow_kind=="small" else 11.0,ms)
	var bar := Rect2(tube.end.x+14,tube.position.y,14,tube.size.y)
	var back := StyleBoxFlat.new()
	back.bg_color=Color(0,0,0,0.35)
	back.set_corner_radius_all(7)
	meter.draw_style_box(back,bar)
	var front := StyleBoxFlat.new()
	front.bg_color=Color("f3c552").lerp(Color("9de07a"),progress)
	front.set_corner_radius_all(7)
	if progress>0.02: meter.draw_style_box(front,Rect2(bar.position.x,bar.end.y-bar.size.y*progress,bar.size.x,bar.size.y*progress))
	meter.draw_string(RpgUi.FONT_STRONG,Vector2(0,24),tr("긴장도"),HORIZONTAL_ALIGNMENT_CENTER,GAUGE_SIZE.x,12,Color(RpgUi.GOLD,0.85))

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
		var r := RpgUi.label(v,ribbon,15,RpgUi.ACCENT,false)
		r.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var art := Icon.make(reward.item,150)
	art.size_flags_horizontal=Control.SIZE_SHRINK_CENTER
	art.custom_minimum_size=Vector2(260,130)
	v.add_child(art)
	var name := RpgUi.label(v,tr(str(data.get("name",reward.item))),26,RpgUi.PAPER_INK,false)
	name.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var stars := "★".repeat(int(data.get("rarity",1)))+"☆".repeat(3-int(data.get("rarity",1)))
	var line1 := RpgUi.label(v,"%s   %.1f cm" % [stars,float(reward.size)],18,RpgUi.PAPER_MUTED,false)
	line1.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var hint := RpgUi.label(v,tr("%s · 판매가 %d잎전") % [tr(SPOT_NAMES.get(str(reward.get("spot","sea")),"바다")),int(data.get("price",0))],14,RpgUi.PAPER_MUTED,false)
	hint.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	if is_instance_valid(hud): hud.add_child(card)
	card.pivot_offset=Vector2(165,160)
	card.scale=Vector2(0.6,0.6)
	card.modulate.a=0
	var t := card.create_tween().set_parallel(true)
	t.tween_property(card,"scale",Vector2.ONE,0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(card,"modulate:a",1.0,0.2)
