extends Node3D
## A village NPC from the authored cast (res://assets/npc). Plays contextual
## job/idle/greeting/conversation clips and turns toward a nearby player
## and stands on the terrain. Without the local cast files it shows nothing and
## the caller falls back to a stand-in walker.
## follow_schedule() makes it keep residents.gd hours: it stands at its outdoor spot
## (work spot, a leisure spot, or just outside its own door for a stroll) while the
## plan says "outside" and is indoors otherwise. With only an idle clip it cannot
## walk, so it swaps places while the walker is more than SWAP_DISTANCE away (or,
## after a while, with a short shrink/grow fade).
const Residents = preload("res://scripts/residents.gd")
const Town = preload("res://scripts/town.gd")
const LoadPace = preload("res://scripts/load_pace.gd")
const ActorSize = preload("res://scripts/actor_size.gd")
const HEIGHT := ActorSize.HUMAN_HEIGHT
const SWAP_DISTANCE := 14.0
## Longest wait (s) for the walker to look away before swapping in plain sight.
const SWAP_PATIENCE := 45.0
## Tests: keep every cast villager at its work spot whatever the clock says.
static var pinned := false
var model: Node3D
var turn_target := 0.0
## How fast it turns toward its target (per second, eased); talking turns it quicker (main.gd talk_after_turn).
var talk_rate := 5.0
var player: Node3D
var anim_player: AnimationPlayer
var motion: Node
var talk_window: WeakRef
var app: Node
var cast := ""
## Where it works (main.gd TownLayout.VILLAGERS[role]) and the spot key of that work.
var work_point := Vector3.ZERO
var block_key := ""
var pending: Dictionary = {}
var pending_for := 0.0
var schedule_clock := 0.0
var outside := true
var swapping := false

## The cast models, read once per session: the village is rebuilt after every room and expedition,
## and reading the four models again held that frame for over a second.
static var scenes := {}

static func available(cast: String) -> bool:
	return ResourceLoader.exists("res://assets/npc/%s.glb" % cast)

## The model files of these casts, for LoadPace.want().
static func resource_paths(casts: Array) -> Array:
	return casts.map(func(cast): return "res://assets/npc/%s.glb" % cast)

func setup(cast: String, facing_yaw: float) -> void:
	var path := "res://assets/npc/%s.glb" % cast
	if not scenes.has(path): scenes[path] = LoadPace.take(path)
	model = (scenes[path] as PackedScene).instantiate()
	add_child(model)
	ActorSize.fit(model,ActorSize.human_height(cast))
	var animation := model.find_children("*", "AnimationPlayer", true, false)
	if not animation.is_empty():
		anim_player = animation[0] as AnimationPlayer
		motion=preload("res://scripts/resident_motion.gd").new();add_child(motion)
		motion.setup(self,model,anim_player,cast)
		# This actor owns the schedule and animation clock; stopping its process also stops the rig.
		motion.set_process(false)
		var rigs := model.find_children("*","Skeleton3D",true,false)
		if not rigs.is_empty():
			var work_pose := preload("res://scripts/npc_work_pose.gd").new()
			work_pose.actor=self;work_pose.motion=motion;rigs[0].add_child(work_pose)
		var idle := preload("res://scripts/context_motions.gd").fallback(anim_player,"idle")
		if not idle.is_empty():
			anim_player.play(idle);anim_player.advance(0)
	turn_target = facing_yaw
	rotation.y = facing_yaw

## Keeps residents.gd hours from now on (main.gd spawn_villagers).
func follow_schedule(owner_app: Node, cast_id: String) -> void:
	app = owner_app
	cast = cast_id
	work_point = position
	schedule_clock = 0.0
	refresh(true)

func face_point(point: Vector3) -> void:
	var to := point - global_position
	if Vector2(to.x, to.z).length() > 0.05: turn_target = atan2(to.x, to.z)

func begin_talk(window: Control) -> void:
	talk_window=weakref(window)
	if is_instance_valid(motion): motion.set_talking(true)

func _process(delta: float) -> void:
	if not cast.is_empty():
		schedule_clock -= delta
		if schedule_clock <= 0.0:
			schedule_clock = 1.0
			refresh(false)
		if not pending.is_empty():
			pending_for += delta
			try_swap()
	if not visible: return
	if is_instance_valid(player) and player.global_position.distance_to(global_position) < 4.0:
		face_point(player.global_position)
	rotation.y = lerp_angle(rotation.y, turn_target, 1.0 - exp(-talk_rate * delta))
	if not is_instance_valid(motion): return
	if talk_window!=null:
		var window = talk_window.get_ref()
		if not is_instance_valid(window) or window.is_queued_for_deletion():
			motion.set_talking(false);talk_window=null
	motion.focus=player
	motion._process(delta)

func hour_now() -> float:
	var daylight = app.get("daylight") if is_instance_valid(app) else null
	if is_instance_valid(daylight) and daylight.has_method("current_hour"): return daylight.current_hour()
	return float(Residents.clock().hour)

## The plan's block for now; a change waits until the walker looks away.
func refresh(immediate: bool) -> void:
	var block := {"place":"outside","spot":"work","activity":"work","from":0.0} if pinned else Residents.now(cast, hour_now(), int(Residents.clock().day))
	var key := "%s|%s|%s|%.2f" % [block.place, block.spot, block.activity, float(block.from)]
	if key == block_key: return
	block_key = key
	pending = block
	pending_for = 0.0
	if immediate: apply(block)
	else: try_swap()

func try_swap() -> void:
	if pending.is_empty() or swapping: return
	var goal := spot_point(pending)
	var here := player_gap(global_position)
	var there := player_gap(goal) if pending.place == "outside" else INF
	var talking: bool = is_instance_valid(app) and is_instance_valid(app.get("village_modal")) and here < 4.0
	if talking: return
	if (here > SWAP_DISTANCE or not visible) and there > SWAP_DISTANCE:
		apply(pending)
	elif pending_for > SWAP_PATIENCE:
		fade_swap(pending)

func player_gap(at: Vector3) -> float:
	if not is_instance_valid(player): return INF
	return Vector2(player.global_position.x-at.x, player.global_position.z-at.z).length()

func apply(block: Dictionary) -> void:
	pending = {}
	if is_instance_valid(motion): motion.activity=str(block.get("activity","idle"))
	outside = block.place == "outside"
	visible = outside
	if outside:
		position = spot_point(block)
		scale = Vector3.ONE

## A quick shrink into the ground / grow out of it when it must happen in view.
func fade_swap(block: Dictionary) -> void:
	swapping = true
	var tween := create_tween()
	if visible:
		tween.tween_property(self, "scale", Vector3(0.05, 0.05, 0.05), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
	tween.tween_callback(func():
		apply(block)
		if visible: scale = Vector3(0.05, 0.05, 0.05))
	tween.tween_property(self, "scale", Vector3.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_callback(func(): swapping = false)

## Work spot, a leisure spot (offset per villager so two never stack), or a step
## outside the own door for a stroll.
func spot_point(block: Dictionary) -> Vector3:
	if block.place != "outside": return position
	if pinned or block.activity in ["guide", "tailor", "camp", "fish"]: return work_point
	var spot: String = block.spot
	var lean := Vector2(cos(cast.hash()%628/100.0), sin(cast.hash()%628/100.0))*1.8
	if Residents.OUTSIDE_SPOTS.has(spot):
		return Town.point(Residents.OUTSIDE_SPOTS[spot]+lean, 0.02)
	var door := Town.door_for(str(Residents.resident(cast).get("home", "")))
	if door.is_empty(): return work_point
	var out: Vector2 = (Vector2(door.at)-Vector2(door.center)).normalized()
	return Town.point(Vector2(door.at)+out*3.2+out.orthogonal()*1.2, 0.02)
