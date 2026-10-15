extends Node
## Waking up in bed (items 54/56): a session that starts at home after signing in (main.gd login sets
## "wake" on the studio session) opens with the walker already lying in the attic bed, laid there
## under the loading card. The card lifts on closed eyes, the eyes open with a slow blink, and the
## walker sits up and gets out of bed the seat driver's own way (ix/ix_driver.gd exit). Any move key
## gets up at once (the driver hands the walker back), and the eyes then open quickly.
## Only the owner's own home (a visit or a building starts at the door as before).
##   var wake := BedWake.new(); studio.add_child(wake)
##   wake.lie_down(studio) -> bool   # in build_stage, after the walker stands at the door
##   wake.open_eyes()                # as the card lifts (studio _ready, after veil.fade_in())
const GameSettings = preload("res://scripts/game_settings.gd")

## Under the card (layer 100, transition.gd), over the room's HUD.
const LAYER := 95
## Seconds: the card's lift to the first glimpse, the eyes half open, the blink, open, then up.
const FIRST_LOOK := 0.55
const HALF_OPEN := 0.7
const BLINK := 0.16
const OPEN := 0.55
const GET_UP := 0.6

var studio: Node
var record: Dictionary = {}
var lids: CanvasLayer
var top: ColorRect
var bottom: ColorRect
var tween: Tween
var hurried := false

## The bed of the attic (interiors.gd 10_red_house/1), else any bed in the home; {} when none.
static func bed_of(decor_by_floor: Array) -> Dictionary:
	for level in range(decor_by_floor.size()-1,-1,-1):
		for entry in decor_by_floor[level]:
			if str(entry.get("kind",""))=="bed" and entry.get("node") is Node3D: return {"floor":level,"record":entry}
	return {}

## Lays the walker in the bed at once (no walk up, no lying down, no bed sound): false when there
## is no bed or the driver cannot take the walker, and the walker stays at the door.
func lie_down(owner_room: Node) -> bool:
	studio=owner_room
	var found := bed_of(studio.decor_by_floor)
	if found.is_empty() or not is_instance_valid(studio.hero) or not is_instance_valid(studio.seat): return false
	record=found.record
	studio.set_floor(int(found.floor))
	var hero: Node3D=studio.hero
	# In front of the bed (beds stand against the back wall), facing it: the driver picks the bed's
	# own lie socket from there.
	hero.position=Vector3(record.center.x,0,record.center.z)+Vector3.BACK*1.1
	hero.facing=Vector3.FORWARD
	studio.lie_on(record)
	var driver = studio.seat.driver
	if not is_instance_valid(driver) or not driver.busy() or not driver.has_method("settle_now"):
		studio.stand_up(false)
		studio.place_hero_at_door()
		return false
	# Laid down under the card: the bed's "lie" sound would give it away.
	var sound: Callable=driver.sound
	driver.sound=Callable()
	driver.settle_now()
	for i in 4: await get_tree().physics_frame
	if is_instance_valid(driver): driver.sound=sound
	studio.update_camera(0.0,true)
	build_lids()
	return true

## Closed eyes over the room until open_eyes(): two dark lids meeting in the middle.
func build_lids() -> void:
	lids=CanvasLayer.new();lids.layer=LAYER;add_child(lids)
	for side in 2:
		var lid := ColorRect.new()
		lid.color=Color("0c0907")
		lid.mouse_filter=Control.MOUSE_FILTER_IGNORE
		lid.anchor_right=1.0
		lid.anchor_top=0.0 if side==0 else 0.5
		lid.anchor_bottom=0.5 if side==0 else 1.0
		# A soft edge where the lids meet.
		var edge := ColorRect.new()
		edge.mouse_filter=Control.MOUSE_FILTER_IGNORE
		edge.color=Color(lid.color,0.55)
		edge.anchor_right=1.0
		edge.custom_minimum_size.y=26
		if side==0:
			edge.anchor_top=1.0;edge.anchor_bottom=1.0;edge.offset_bottom=26
		else:
			edge.anchor_top=0.0;edge.anchor_bottom=0.0;edge.offset_top=-26
		lid.add_child(edge)
		lids.add_child(lid)
		if side==0: top=lid
		else: bottom=lid

## How far the lids are open: 0 shut, 1 out of sight.
func set_open(amount: float) -> void:
	if not is_instance_valid(top): return
	var h: float=get_viewport().get_visible_rect().size.y*0.5+30.0
	top.position.y=-amount*h
	bottom.position.y=get_viewport().get_visible_rect().size.y*0.5+amount*h

## The eyes open as the card lifts, then the walker gets up.
func open_eyes() -> void:
	if not is_instance_valid(lids): return
	set_open(0.0)
	tween=create_tween()
	tween.tween_interval(FIRST_LOOK)
	tween.tween_method(set_open,0.0,0.32,HALF_OPEN).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	tween.tween_method(set_open,0.32,0.0,BLINK).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tween.tween_method(set_open,0.0,1.0,OPEN).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.tween_interval(GET_UP)
	tween.tween_callback(get_up)

## Out of bed the driver's way (sit up on the edge, feet down, stand), the lids gone.
func get_up() -> void:
	if is_instance_valid(lids): lids.queue_free()
	if is_instance_valid(studio) and is_instance_valid(studio.seat) and studio.resting!="": studio.stand_up(true)
	queue_free()

## A move key while the eyes are still opening: the driver already gets up (its HOLD exits on
## input), so the eyes open at once.
func _process(_delta: float) -> void:
	if hurried or not is_instance_valid(studio) or not is_instance_valid(lids) or tween==null: return
	if studio.resting=="":
		hurried=true
		tween.kill()
		tween=create_tween()
		var now: float=-top.position.y/(get_viewport().get_visible_rect().size.y*0.5+30.0)
		tween.tween_method(set_open,clampf(now,0.0,1.0),1.0,0.25).set_ease(Tween.EASE_OUT)
		tween.tween_callback(get_up)

# ---------------------------------------------------------------- picking up in the village (55)

## Signing in again soon after leaving the own village: the walker stands where it was (the sign-in's
## resume spot, server/last_spot.py), facing the same way, when that spot is still open ground;
## otherwise on the home's doorstep.
static func resume_spot(main: Node, spot: Dictionary) -> void:
	var player: Node3D=main.player
	if not is_instance_valid(player): return
	var at := Vector3(float(spot.get("x",0.0)),float(spot.get("y",0.0)),float(spot.get("z",0.0)))
	var ground := ground_at(player,at)
	if ground==Vector3.INF:
		player.position=preload("res://scripts/town.gd").door_return("home")
	else:
		player.position=ground+Vector3(0,0.3,0)
		var yaw := float(spot.get("yaw",0.0))
		player.facing=Vector3(-sin(yaw),0,-cos(yaw))
		if "visual" in player and is_instance_valid(player.visual): player.visual.rotation.y=yaw
	main.follow_camera(1)

## The open ground under a spot (flat enough, near its height, not a roof), else INF.
static func ground_at(node: Node3D, at: Vector3) -> Vector3:
	var space := node.get_world_3d().direct_space_state
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(at+Vector3(0,2.0,0),at-Vector3(0,3.0,0),1|2))
	if hit.is_empty() or hit.normal.y<0.7 or absf(hit.position.y-at.y)>1.0: return Vector3.INF
	return hit.position
