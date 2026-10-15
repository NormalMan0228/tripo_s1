extends Node
## The room's front door swings (items 32/49/51). interiors.gd front() builds the half-height leaf
## "FrontDoor" hinged on the right post; it used to stand open at 108° for good. Here it is shut
## while nobody passes and swings open for whoever walks through: the walker coming in as the card
## lifts (walk_in) and going out (studio leave), visitors walking in from outside and back out
## (arrive / depart), with DoorAudio's latch, creak and thud at the door.
##   front_door = RoomDoor.bind(studio, front_door, floor_roots[0], room)  # after each build_room
##   front_door.walk_in(hero)            # as the card lifts: in through the doorway, the door shuts
##   front_door.guiding(delta) -> bool   # studio _process: true while it steers the walker
##   front_door.hold(key, seconds)       # open now, shut once every hold ran out
##   front_door.arrive(entry) / walk_peer_in(entry, delta) / depart(entry)   # visitors (peers)
const DoorAudio=preload("res://scripts/door_audio.gd")
const Interiors=preload("res://scripts/interiors.gd")

## The leaf moves through interiors.gd set_front_door_open (0 shut .. 1 open): which side it hangs on,
## one leaf or two, and which way it opens are the room's (the map session's) to say. Swing times:
const OPEN_SECONDS := 0.42
const CLOSE_SECONDS := 0.5
## Walking pace through the door (a little under the room's own 2.8 m/s: a step in, not a dash).
const PACE := 2.3
## Where outside the door someone stands before stepping in (m past the front wall).
const OUTSIDE := 0.9
## Within this of the doorway a walker keeps the door open.
const NEAR := 1.4
## A frame counts at most this long for the walks here: after a hitch the walker carries on from
## where it was instead of hopping ahead.
const MAX_DELTA := 0.05

var studio: Node
var hinge: Node3D
## The floor the door is on (interiors.gd front_door / set_front_door_open take it), and how open.
var ground: Node3D
var amount := 0.0
var room := ""
var spec: Dictionary = {}
var holds := {}
var opened := false
var swing_tween: Tween
var steer: Node3D
var steer_to := Vector3.INF
var departing: Array = []

## The door of this build (re-bound after every rebuild of the room); null without a front door.
static func bind(owner_room: Node, door: Node, ground: Node3D, room_id: String) -> Node:
	var leaf: Node3D=ground.find_child("FrontDoor",true,false) as Node3D if is_instance_valid(ground) else null
	if leaf==null:
		if is_instance_valid(door): door.hinge=null
		return door
	if not is_instance_valid(door):
		door=load("res://scripts/room_door.gd").new()
		door.name="RoomDoor"
		owner_room.add_child(door)
	door.studio=owner_room
	door.hinge=leaf
	door.ground=ground
	door.room=room_id
	door.spec=owner_room.building_spec.floors[0] if not owner_room.building_spec.is_empty() else {}
	door.holds.clear()
	door.opened=false
	door.pose(0.0)
	return door

func door_at() -> Vector3:
	return hinge.global_position if is_instance_valid(hinge) else Vector3.INF

## The doorway on the floor: x of the door, z of the front wall.
func doorway() -> Vector3:
	return Vector3(float(spec.get("door_x",0.0)),0,float(spec.size.y)*0.5+Interiors.WALL*0.5) if spec.has("size") else Vector3.ZERO

## A spot just outside the door, on the path in.
func outside() -> Vector3:
	return doorway()+Vector3(0,0,OUTSIDE)

## Opens the door (if shut) and keeps it open `seconds` for `key`; it shuts once every hold ran out.
func hold(key: String, seconds: float) -> void:
	if not is_instance_valid(hinge): return
	holds[key]=Time.get_ticks_msec()+int(seconds*1000.0)
	if not opened: swing(true)

func release(key: String) -> void:
	holds.erase(key)

func pose(value: float) -> void:
	amount=value
	if is_instance_valid(ground): Interiors.set_front_door_open(ground,value)

## The leaf swings open (fast, slowing as it opens, like a door pushed) or shut (a small bounce off
## the frame), with the door's sounds where it is.
func swing(open: bool, sound := true) -> void:
	if not is_instance_valid(hinge): return
	opened=open
	if swing_tween and swing_tween.is_valid(): swing_tween.kill()
	swing_tween=create_tween()
	if open:
		swing_tween.tween_method(pose,amount,1.0,OPEN_SECONDS).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		if sound: DoorAudio.door_open(studio,room,door_at(),OPEN_SECONDS)
	else:
		swing_tween.tween_method(pose,amount,0.0,CLOSE_SECONDS).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		swing_tween.tween_method(pose,0.0,0.04,0.07).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		swing_tween.tween_method(pose,0.04,0.0,0.12).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
		if sound: DoorAudio.door_close(studio,room,door_at(),CLOSE_SECONDS)

## Stands open at once, silently (someone has just opened it from the other side).
func set_open() -> void:
	if not is_instance_valid(hinge): return
	if swing_tween and swing_tween.is_valid(): swing_tween.kill()
	opened=true
	pose(1.0)

## The walker comes in from outside: it stands past the open door facing in, walks to the room's
## spawn spot as the card lifts, and the door shuts behind it.
func walk_in(hero: Node3D) -> void:
	if not is_instance_valid(hinge) or not is_instance_valid(hero) or studio.floor_index!=0: return
	set_open()
	hold("walker",10.0)
	hero.position=outside()
	hero.facing=Vector3.FORWARD
	if "visual" in hero and is_instance_valid(hero.visual): hero.visual.rotation.y=0.0
	steer=hero
	steer_to=Interiors.spawn_point(spec)
	studio.update_camera(0.0,true)

## Moves the walker on toward its spot (studio _process, instead of the keys): true while it does.
func guiding(delta: float) -> bool:
	if steer==null or steer_to==Vector3.INF: return false
	if not is_instance_valid(steer):
		steer=null;steer_to=Vector3.INF
		return false
	var before: Vector3=steer.position
	steer.position=steer.position.move_toward(steer_to,PACE*minf(delta,MAX_DELTA))
	studio.report_motion(before,minf(delta,MAX_DELTA))
	if steer.position.distance_to(steer_to)<0.02:
		steer=null;steer_to=Vector3.INF
		# In: the door swings shut behind (a beat later, once clear of the leaf).
		holds["walker"]=Time.get_ticks_msec()+150
	return true

# ---------------------------------------------------------------- visitors

## A visitor who just came into the home: drawn outside the door, walking in to where they are.
func arrive(entry: Dictionary) -> void:
	if not is_instance_valid(hinge): return
	var node: Node3D=entry.node
	node.position=outside()
	entry["arrive"]=true
	hold("peer%d" % node.get_instance_id(),2.0)

## While a visitor walks in from the door: their walk toward where the motion says they are (the
## motion keeps updating meanwhile). False once arrived; the motion takes over from there.
func walk_peer_in(entry: Dictionary, delta: float) -> bool:
	if not entry.get("arrive",false): return false
	var node: Node3D=entry.node
	if not is_instance_valid(node) or not is_instance_valid(hinge):
		entry["arrive"]=false
		return false
	var goal: Vector3=entry.motion.position if entry.motion.started else entry.get("goal",node.position)
	goal.y=node.position.y
	var step: Vector3=goal-node.position
	var walk: float=minf(step.length(),PACE*1.15*minf(delta,MAX_DELTA))
	if step.length()<0.06:
		entry["arrive"]=false
		return false
	node.position+=step.normalized()*walk
	var flat := Vector2(step.x,step.z).normalized()
	node.external_velocity=flat*PACE
	node.external_motion=flat
	if node.position.distance_to(doorway())<NEAR: hold("peer%d" % node.get_instance_id(),0.6)
	return true

## A visitor who left the home (on the ground floor, seen): they walk out through the door, which
## opens for them and shuts behind, then fade. False when the door cannot take them (freed at once).
func depart(entry: Dictionary) -> bool:
	var node: Node3D=entry.get("node")
	if not is_instance_valid(hinge) or not is_instance_valid(node) or not node.visible: return false
	departing.append({"node":node,"time":0.0})
	return true

## Residents walking in from the door or out of it (studio.gd place_resident / remove_resident walk
## them; walking ones are in studio.stepping): the door opens as they reach it. Checked 10 times a
## second, not every frame.
var resident_time := 0.0
func residents_through(delta: float) -> void:
	resident_time+=delta
	if resident_time<0.1 or not is_instance_valid(hinge) or not is_instance_valid(studio): return
	resident_time=0.0
	for entry in studio.stepping:
		if not entry.get("walking",false) or int(entry.get("floor",-1))!=0 or not is_instance_valid(entry.get("holder")): continue
		if (entry.holder as Node3D).position.distance_to(doorway())<NEAR: hold("resident:"+str(entry.id),0.7)

func _process(delta: float) -> void:
	for i in range(departing.size()-1,-1,-1):
		var leaving: Dictionary=departing[i]
		var node: Node3D=leaving.node
		leaving.time+=delta
		if not is_instance_valid(node):
			departing.remove_at(i);continue
		var target: Vector3=outside()+Vector3(0,0,0.6) if node.position.distance_to(doorway())<0.5 or node.position.z>doorway().z else doorway()
		var step: Vector3=target-node.position
		step.y=0
		if node.position.distance_to(doorway())<NEAR: hold("peer%d" % node.get_instance_id(),0.6)
		if step.length()<0.06 or leaving.time>6.0:
			departing.remove_at(i)
			var fade := node.create_tween()
			fade.tween_property(node,"scale",Vector3(0.9,0.05,0.9),0.3)
			fade.tween_callback(node.queue_free)
			continue
		node.position+=step.normalized()*minf(step.length(),PACE*minf(delta,MAX_DELTA))
		var flat := Vector2(step.x,step.z).normalized()
		node.external_velocity=flat*PACE
		node.external_motion=flat
	residents_through(delta)
	if not opened or holds.is_empty(): return
	var now := Time.get_ticks_msec()
	for key in holds.keys():
		if int(holds[key])<now: holds.erase(key)
	if holds.is_empty(): swing(false)
