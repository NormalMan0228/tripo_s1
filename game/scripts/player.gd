extends CharacterBody3D

const Profile=preload("res://scripts/controller_profile.gd")
const Roster=preload("res://scripts/character_roster.gd")
const ActorSize=preload("res://scripts/actor_size.gd")
const ContextMotions=preload("res://scripts/context_motions.gd")
const SPEED := Profile.VILLAGE_WALK
const MODERN_HEROES = Roster.IDS
var controls_enabled := true
var visual_only := false
var facing := Vector3.FORWARD
var visual: Node3D
var external_motion := Vector2.ZERO
var external_velocity := Vector2.ZERO
var locomotion_velocity := Vector2.ZERO
var locomotion_pose: SkeletonModifier3D
var gait_phase := 0.0
var stride := 0.0
## Body lean: x leans into acceleration, y banks into turns (radians, eased).
var lean := Vector2.ZERO
var lean_speed := 0.0
var lean_yaw := 0.0
## The body moves in 60 Hz physics ticks but frames come faster, so the visual is
## drawn between the last two tick positions (render_position()); the camera
## follows the same point. Without it the walker and the view shuddered.
var tick_from := Vector3.ZERO
var tick_to := Vector3.ZERO
var visual_lift := 0.0
var reveal_pending := false
var left_leg: Node3D
var right_leg: Node3D
var equipment: Node3D
var tool_node: Node3D
var equipped := ""
var animation_player: AnimationPlayer
var current_clip := ""
var hand_skeleton: Skeleton3D
var hand_index := -1
var reaction_tween: Tween
var action_pose: SkeletonModifier3D
var finger_pose: SkeletonModifier3D
var sprinting := false
var action_facing := Vector3.ZERO
var facing_until := 0.0
var avatar: Dictionary={}
## The profile version of the look on this body (avatar_look.gd wear()); -1 when unknown.
var look_version := -1
## How many times the character was built, for checks that a look is not rebuilt on every poll.
var look_builds := 0
## Character models stay loaded once used: a model nothing showed any more was read from disk
## again (about 0.3 s) at the next change of look, in the wardrobe preview at every click.
static var models := {}
## Reads the weapon models into `models` ahead of their first swing (an expedition's start, under its
## card): the first equip of the axe read its GLB from disk in the swing's frame.
static func warm_tools() -> void:
	for item in ["axe", "spear"]:
		var path: String = "res://assets/authored_"+item+"_v1.glb"
		if not models.has(path) and ResourceLoader.exists(path): models[path]=load(path)
var action_until := 0.0
var action_clip := ""
var action_kind := ""
var action_rate := 1.0
var action_start := 0.0
var idle_seconds := 0.0
var animation_clock := 0.0
var animation_frame := 0
var tool_grip := Basis.IDENTITY
var ambient_clip := "idle"
var greeting_until := 0.0
## The island village keeps walkers out of the sea: below this height the body
## returns to its last grounded spot. Rooms and survival leave it unset.
var min_ground_y := -INF
## Walkers ease into and out of their pace instead of snapping, and climb low
## ledges such as steps and the floors of open pavilions.
const ACCELERATION := 14.0
const DECELERATION := 18.0
const STEP_HEIGHT := 0.36
## Where and until which physics frame a step up was refused (step_up()).
var step_refused_at := Vector3.INF
var step_refused_until := 0
var safe_position := Vector3.ZERO
var has_safe_position := false
## A step up or a drop off a ledge moves the body in one tick; the drawn body (and the camera,
## through render_position()) catches up at CLIMB_SPEED instead of hopping. Metres below
## (negative) or above the body, eased to 0; from/to are its last two tick values.
const CLIMB_SPEED := 2.8
var step_lag := 0.0
var step_lag_from := 0.0
## Boxed in on every side while walking (a placed object, props closing in): back to the
## last spot it walked freely from. trapped_escapes counts them (tests).
var trapped_time := 0.0
var free_position := Vector3.INF
var free_clock := 0.0
var trapped_escapes := 0
## The interaction driver (ix/ix_driver.gd) while one is attached; inert when null or idle. While it
## runs it moves the body inside this tick: steer is the walking input of an approach, face_override
## the exact visual yaw (NAN: the usual facing lerp), clip_override a clip it plays (v1: none).
var ix: Node
var steer := Vector2.ZERO
var face_override := NAN
var clip_override := ""
var clip_blend := -1.0
const Art = preload("res://scripts/art.gd")
const LifeArt = preload("res://scripts/life_art.gd")

func _ready() -> void:
	avatar["character"]=Roster.canonical(str(avatar.get("character",Roster.DEFAULT)))
	Profile.ensure_input()
	floor_snap_length = 0.3
	# Characters stand on layer 4 so ground probes (layers 1, 2 and 8) never hit them.
	# Island buildings, bridges and piers use layer 2, props and trees layer 8 and
	# placed furniture layer 16.
	collision_layer = 4
	collision_mask = 1|2|4|8|16|32
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = Profile.BODY_RADIUS
	capsule.height = Profile.BODY_HEIGHT
	shape.shape = capsule
	shape.position.y = Profile.BODY_HEIGHT*.5
	add_child(shape)
	visual = Node3D.new()
	add_child(visual)
	_build_character()
	apply_colors()
	look_builds+=1
	visual.rotation.y=PI
	return

func _build_character() -> void:
	var hero_path: String=Roster.model_path(str(avatar.character))
	if not ResourceLoader.exists(hero_path): hero_path=Roster.model_path(Roster.DEFAULT)
	if ResourceLoader.exists(hero_path):
		if not models.has(hero_path): models[hero_path]=load(hero_path)
		var packed := models[hero_path] as PackedScene
		if packed:
			var hero := packed.instantiate() as Node3D
			if hero:
				var meshes: Array[MeshInstance3D]=[]
				var loader = preload("res://scripts/model_loader.gd")
				loader._collect_meshes(hero,meshes)
				var bounds := AABB()
				var first := true
				for instance in meshes:
					var b: AABB=loader._local_transform(instance,hero)*instance.get_aabb()
					bounds=b if first else bounds.merge(b)
					first=false
				if bounds.size.y>0.001:
					var pivot := Node3D.new()
					visual.add_child(pivot)
					pivot.add_child(hero)
					pivot.scale=Vector3.ONE*(ActorSize.HUMAN_HEIGHT/bounds.size.y)
					hero.position-=Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)
					# The artisan GLB was exported facing the opposite direction to the
					# other seven heroes. Align its model, skeleton and hand tools together.
					pivot.rotation.y=0.0 if str(avatar.get("character", "")) == "m2" else PI
					var controllers := hero.find_children("*","AnimationPlayer",true,false)
					var skeletons := hero.find_children("*","Skeleton3D",true,false)
					if not skeletons.is_empty():
						hand_skeleton=skeletons[0]
						hand_index=hand_skeleton.find_bone("R_Hand")
						action_pose=preload("res://scripts/action_pose.gd").new()
						hand_skeleton.add_child(action_pose)
						if str(avatar.get("character", "")) in MODERN_HEROES:
							var style := preload("res://scripts/hero_style.gd").new()
							style.actor = self
							style.character = str(avatar.character)
							hand_skeleton.add_child(style)
						action_pose.modification_processed.connect(update_tool_pose)
					if not controllers.is_empty():
						animation_player=controllers[0]
						ContextMotions.configure(animation_player)
						animation_player.callback_mode_process=AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
					return
	push_error("No modern player model available: "+hero_path)

func equip(item: String) -> void:
	if item==equipped: return
	var previous := equipped
	equipped=item
	if is_instance_valid(finger_pose):finger_pose.holding=not item.is_empty()
	# A tool out puts the carried thing away until it goes back (held_items.gd).
	var held_node := get_node_or_null("Held")
	if held_node: held_node.call_deferred("refresh", false)
	if uses_sockets():
		equip_socketed(previous, item)
		return
	if is_instance_valid(equipment):
		if equipment.get_parent(): equipment.get_parent().remove_child(equipment)
		equipment.queue_free()
	equipment=null
	tool_node=null
	if item.is_empty(): return
	var tool: Node3D
	if is_instance_valid(hand_skeleton) and hand_index>=0:
		var attachment := BoneAttachment3D.new()
		attachment.bone_name="R_Hand"
		hand_skeleton.add_child(attachment)
		equipment=attachment
		tool=Node3D.new()
		equipment.add_child(tool)
		var hand_transform: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_pose(hand_index)
		tool.basis=hand_transform.basis.inverse()*visual.global_basis.orthonormalized()
		if item=="axe": tool.basis=tool.basis*Basis(Vector3.FORWARD,PI)
		tool_grip=tool.basis
	else:
		equipment=Node3D.new()
		visual.add_child(equipment)
		equipment.position=Vector3(0.43,0.77,-0.12)
		tool=equipment
	tool_node=tool
	build_tool(item, tool)

## The item's model under `tool` (its origin is the grip, +Y toward the tool head).
func build_tool(item: String, tool: Node3D) -> void:
	if item=="rod":
		if ResourceLoader.exists("res://assets/fishing_rod.glb"):
			tool.add_child((load("res://assets/fishing_rod.glb") as PackedScene).instantiate())
			tool.set_meta("line_tip",Vector3(0,1.63,0))
			return
		Art.box(tool,Vector3(0,0.85,0),Vector3(0.045,2.9,0.045),Color("ac8758"))
		Art.sphere(tool,Vector3(0.1,0.03,0),Vector3(0.18,0.18,0.12),Color("819f9d"))
		return
	if item in ["pickaxe","broom","umbrella","lantern"] and ResourceLoader.exists("res://assets/tools/"+item+".glb"):
		# Low-poly hand tools (05, tools/body_gen/build_hand_tools.py): origin on the grip, +Y to the head.
		var model := (load("res://assets/tools/"+item+".glb") as PackedScene).instantiate() as Node3D
		tool.add_child(model)
		if item=="umbrella":
			var canopy := model.find_child("Canopy", true, false) as Node3D
			if canopy: canopy.visible=false
		return
	if item=="hoe":
		# The flat-bladed hoe (was dressed afterwards by village_life.gd dress_hoe(), which now sees the meta).
		tool.set_meta("hoe",true)
		LifeArt.part(tool,"rod",Vector3(0,0.2,0),Vector3(0.05,1.25,0.05),Color("9a744c"))
		LifeArt.part(tool,"box",Vector3(0,0.82,0.11),Vector3(0.24,0.05,0.24),Color("b9c3c4"),Vector3(0.25,0,0),0.4)
		LifeArt.part(tool,"box",Vector3(0,0.82,0.0),Vector3(0.07,0.08,0.07),Color("6b6f70"))
		return
	if item=="watering_can":
		Art.sphere(tool,Vector3(0,-0.05,0),Vector3(0.45,0.45,0.4),Color("76acb0"))
		Art.box(tool,Vector3(0.3,0.1,0),Vector3(0.5,0.09,0.09),Color("b1d1cd"))
		return
	if item in ["axe","spear"]:
		var path: String = "res://assets/authored_"+item+"_v1.glb"
		if not models.has(path) and ResourceLoader.exists(path): models[path]=load(path)
		var source := models.get(path) as PackedScene
		if source:
			tool.add_child(source.instantiate())
			return
	Art.box(tool,Vector3.ZERO,Vector3(0.035,1.0,0.035),Color("80634b"))
	if item=="spear":
		Art.cone(tool,Vector3(0,0.73,0),0.12,0.3,Color("cad2cb"))
	else:
		Art.box(tool,Vector3(0.07,0.43,0),Vector3(0.32,0.23,0.12),Color("a8b8ae"))

## ------------------------------------------------------------------ sockets
## Equipment can carry items on shared sockets (equip_sockets.gd): the item in use on
## hand_r, the ones put down on their stow socket (an axe or a rod on the back) until used again.
## Moving between the hand and a stow socket eases over SOCKET_MOVE s instead of jumping.
const EquipSockets = preload("res://scripts/equip_sockets.gd")
const SOCKET_MOVE := 0.22
## Items carried on a stow socket: name -> the item node.
var stowed := {}

func uses_sockets() -> bool:
	return false # Modern heroes currently use the bone-relative grip below.

## The socket frame `name` (hand_r, hand_l, back, hip_r, hip_l, head) on this body, or null.
func socket(name: String) -> Node3D:
	return EquipSockets.socket(hand_skeleton, name) if is_instance_valid(hand_skeleton) else null

func equip_socketed(previous: String, item: String) -> void:
	# The item in hand goes to its stow socket, or away.
	if not previous.is_empty() and is_instance_valid(tool_node):
		var record := EquipSockets.item(previous)
		var stow: Node3D = socket(str(record.get("stow",""))) if not str(record.get("stow","")).is_empty() else null
		if stow:
			# One item per stow socket: the one already there is put away.
			for name in stowed.keys():
				if is_instance_valid(stowed[name]) and stowed[name].get_parent() == stow:
					drop_item(stowed[name])
					stowed.erase(name)
			move_item(tool_node, stow, EquipSockets.placement(record, true))
			stowed[previous]=tool_node
		else: drop_item(tool_node)
	equipment=null
	tool_node=null
	if item.is_empty(): return
	var record := EquipSockets.item(item)
	var hold: Node3D = socket(str(record.get("hold","hand_r")))
	if hold == null: hold = socket("hand_r")
	var node: Node3D
	if stowed.has(item) and is_instance_valid(stowed[item]):
		node=stowed[item]
		stowed.erase(item)
		move_item(node, hold, EquipSockets.placement(record))
	else:
		node=Node3D.new()
		node.name="Item_"+item
		hold.add_child(node)
		build_tool(item, node)
		node.transform=EquipSockets.placement(record)
	# The working end (blade edge, spout) for the tool-contact effects (tool_contact.gd).
	var tip: Array = record.get("tip", [])
	if tip.size() == 3: node.set_meta("tip", Vector3(float(tip[0]), float(tip[1]), float(tip[2])))
	tool_node=node
	equipment=node
	tool_grip=node.basis

## The item in hand turns to its use direction (equip_sockets.json items.<item>.use.<kind>.rot) for
## the action and back after it: the hoe's blade comes down onto the ground, the can tips its spout.
func use_pose(kind: String) -> void:
	if not uses_sockets() or not is_instance_valid(tool_node) or equipped.is_empty(): return
	var record := EquipSockets.item(equipped)
	var uses: Dictionary = record.get("use", {})
	if not uses.has(kind): return
	var turned := record.duplicate()
	turned["rot"] = uses[kind].get("rot", record.get("rot", [0, 0, 0]))
	if tool_node.has_meta("socket_tween"):
		var running = tool_node.get_meta("socket_tween")
		if running is Tween and running.is_valid(): running.kill()
	var length: float = action_pose.duration if is_instance_valid(action_pose) else 0.4
	var tween := tool_node.create_tween()
	tween.tween_property(tool_node,"transform",EquipSockets.placement(turned),minf(0.18,length*0.4)).set_trans(Tween.TRANS_SINE)
	tween.tween_interval(maxf(0.0,length*0.4))
	tween.tween_property(tool_node,"transform",EquipSockets.placement(record),0.16).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tool_node.set_meta("socket_tween",tween)

## Puts a fresh copy of `item` straight onto its stow socket (a rebuilt body, a loaded save).
func stow_new(item: String) -> void:
	if not uses_sockets() or stowed.has(item) or item==equipped: return
	var record := EquipSockets.item(item)
	var stow: Node3D = socket(str(record.get("stow",""))) if not str(record.get("stow","")).is_empty() else null
	if stow == null: return
	var node := Node3D.new()
	node.name="Item_"+item
	stow.add_child(node)
	build_tool(item, node)
	node.transform=EquipSockets.placement(record, true)
	stowed[item]=node

## Moves an item onto another socket: it keeps where it is drawn, then eases into place.
func move_item(node: Node3D, to: Node3D, target: Transform3D) -> void:
	if node.has_meta("socket_tween"):
		var running = node.get_meta("socket_tween")
		if running is Tween and running.is_valid(): running.kill()
	node.reparent(to, true)
	if not node.is_inside_tree() or not is_inside_tree():
		node.transform=target
		return
	var tween := node.create_tween()
	tween.tween_property(node,"transform",target,SOCKET_MOVE).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	node.set_meta("socket_tween",tween)

## Put away for good (no stow socket): shrinks out instead of vanishing in one frame.
func drop_item(node: Node3D) -> void:
	if not node.is_inside_tree():
		node.queue_free()
		return
	var tween := node.create_tween()
	tween.tween_property(node,"scale",Vector3.ONE*0.01,0.12)
	tween.tween_callback(node.queue_free)

func update_tool_pose() -> void:
	if not is_instance_valid(tool_node) or not is_instance_valid(hand_skeleton): return
	if uses_sockets(): return
	if current_clip=="slash":
		tool_node.basis=tool_grip
		return
	var hand_world: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_pose(hand_index)
	var angle := 0.0
	if is_instance_valid(action_pose) and action_pose.kind in ["attack","gather"]:
		angle=-1.6*action_pose.applied_amount
	# Keep the blade ahead of the hand while the imported wrist turns.
	tool_node.basis=hand_world.basis.inverse()*visual.global_basis.orthonormalized()*Basis(Vector3.RIGHT,angle)
	if equipped=="axe": tool_node.basis=tool_node.basis*Basis(Vector3.FORWARD,PI)

## A few degrees of lean sells weight: forward when speeding up, back when stopping,
## and inward on a turn. Kept small so tools and the camera never notice.
func lean_body(delta: float) -> void:
	var speed_now := locomotion_velocity.length()
	var accel := (speed_now-lean_speed)/maxf(delta,0.001)
	var yaw_rate := angle_difference(lean_yaw,visual.rotation.y)/maxf(delta,0.001)
	lean_speed=speed_now
	lean_yaw=visual.rotation.y
	var pace := minf(speed_now/SPEED,1.0)
	var target := Vector2(clampf(0.008*accel+0.03*pace,-0.07,0.1),clampf(0.03*yaw_rate*pace,-0.09,0.09))
	if visual_only: target=Vector2.ZERO
	lean=lean.lerp(target,1.0-exp(-7.0*delta))
	visual.rotation.x=-lean.x
	visual.rotation.z=lean.y

func _process(_delta: float) -> void:
	if not is_instance_valid(visual): return
	# Moved outside the physics tick (spawn, door, teleport): no blending across it.
	if global_position.distance_squared_to(tick_to) > 0.000001:
		tick_from = global_position
		tick_to = global_position
		step_lag = 0.0
		step_lag_from = 0.0
		# A new room or map: the last free spot belongs to the old one.
		free_position = Vector3.INF
		free_clock = 0.0
		trapped_time = 0.0
	var offset := render_position()-global_position
	visual.position = Vector3(offset.x, visual_lift+offset.y, offset.z)

func render_position() -> Vector3:
	var fraction := clampf(Engine.get_physics_interpolation_fraction(), 0.0, 1.0)
	return tick_from.lerp(tick_to, fraction)+Vector3(0, lerpf(step_lag_from, step_lag, fraction), 0)

## Profiling (tests/perf_scenes.gd): microseconds in move_and_slide and step_up, and slide contacts.
static var profile := false
static var profile_slide_us := 0
static var profile_step_us := 0
static var profile_slides := 0

func _physics_process(delta: float) -> void:
	tick_from = global_position
	step_lag_from = step_lag
	var grounded := is_on_floor()
	var driven: bool = ix != null and is_instance_valid(ix) and ix.busy()
	if driven: ix.drive(self, delta)
	var movement := Vector2.ZERO
	if driven: movement = steer
	elif controls_enabled:
		movement = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var speed := Profile.VILLAGE_RUN if sprinting and not driven else SPEED
	var wanted := Vector2(movement.x,movement.y)*speed
	var current := Vector2(velocity.x,velocity.z)
	# Turning sharply sheds a little speed so direction changes read as weight.
	if wanted.length()>0.1 and current.length()>0.5 and wanted.normalized().dot(current.normalized())<0.2: current*=0.82
	current=current.move_toward(wanted,(ACCELERATION if wanted.length()>current.length() else DECELERATION)*delta)
	velocity.x = current.x
	velocity.z = current.y
	if visual_only:
		velocity=Vector3.ZERO
	elif not is_on_floor():
		velocity.y -= 20.0 * delta
	else:
		velocity.y = 0.0
	if not visual_only:
		var t0 := Time.get_ticks_usec() if profile else 0
		move_and_slide()
		var t1 := Time.get_ticks_usec() if profile else 0
		step_up(delta)
		if profile:
			profile_slide_us += t1-t0
			profile_step_us += Time.get_ticks_usec()-t1
			profile_slides += get_slide_collision_count()
		if position.y < min_ground_y and has_safe_position:
			position = safe_position
			velocity = Vector3.ZERO
		elif is_on_floor() and position.y >= min_ground_y:
			safe_position = position
			has_safe_position = true
		watch_trapped(delta, movement.length() > 0.1 and controls_enabled and not driven)
	# A ledge climbed or dropped from the ground (not a fall, not a jump back to safety).
	var rise := global_position.y-tick_from.y
	if grounded and absf(rise) > 0.06 and absf(rise) < 0.8: step_lag -= rise
	elif absf(rise) >= 0.8: step_lag = 0.0
	step_lag = move_toward(step_lag, 0.0, maxf(CLIMB_SPEED, absf(step_lag)*6.0)*delta)
	locomotion_velocity=Vector2(get_real_velocity().x,get_real_velocity().z) if (controls_enabled or driven) and not visual_only else external_velocity
	var look_motion := locomotion_velocity.normalized() if controls_enabled or driven else external_motion
	if not is_nan(face_override):
		visual.rotation.y = face_override
	elif Time.get_ticks_msec()*0.001<facing_until:
		facing=action_facing
	elif look_motion.length_squared() > 0.01:
		facing = Vector3(look_motion.x, 0.0, look_motion.y)
	if is_nan(face_override) and facing.length_squared()>0.01:
		var turned := lerp_angle(visual.rotation.y, atan2(-facing.x, -facing.z), Profile.damping(Profile.TURN_RESPONSE,delta))
		# Walking up to a seat turns at most 0.3 rad a tick (the ISS-1 continuity bound).
		visual.rotation.y = rotate_toward(visual.rotation.y, turned, 0.3) if driven else turned
	lean_body(delta)
	if is_instance_valid(action_pose): action_pose.body_basis=visual.global_basis.orthonormalized()
	var moving := minf(1.0,locomotion_velocity.length()/SPEED)
	stride+=delta*11*moving
	idle_seconds=idle_seconds+delta if moving<=.1 else 0.0
	if is_instance_valid(animation_player) and animation_player.has_animation("walk") and animation_player.has_animation("idle") and visual.is_visible_in_tree():
		var desired := ("run" if (sprinting or locomotion_velocity.length()>3.4) and animation_player.has_animation("run") else "walk") if moving>0.1 else "idle"
		var interacting: bool=is_instance_valid(ix) and ix.busy()
		if moving>.1 and action_kind in ["greet","bow","clap","cheer"]: action_until=0.0
		if desired=="idle" and idle_seconds>2.0 and not interacting:
			desired=ContextMotions.idle(animation_player,str(avatar.get("character",Roster.DEFAULT)))
		var acting: bool=Time.get_ticks_msec()*0.001<action_until and not action_clip.is_empty() and not interacting
		if acting: desired=action_clip
		if not clip_override.is_empty() and animation_player.has_animation(clip_override): desired=clip_override
		if current_clip!=desired:
			var preserve_gait: bool=desired in ["walk","run"] and is_instance_valid(locomotion_pose)
			current_clip=desired
			animation_player.play(desired,0.08 if acting else 0.18)
			if preserve_gait:
				animation_player.seek(gait_phase*animation_player.get_animation(desired).length,false)
			if acting and desired==action_clip: animation_player.seek(action_start,true)
		if is_instance_valid(locomotion_pose) and desired in ["walk","run"]:
			var seconds: float=locomotion_pose.cycle_for_speed(locomotion_velocity.length())
			animation_player.speed_scale=animation_player.get_animation(desired).length/seconds
		else:
			animation_player.speed_scale=action_rate if acting and desired==action_clip else (1.0 if desired=="run" else (1.5 if moving>0.1 else 1.0))
		if animation_player.callback_mode_process==AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL:
			animation_clock+=delta;animation_frame+=1
			var lod := preload("res://scripts/anim_lod.gd")
			var gap: int=1 if controls_enabled or acting or interacting else lod.stride(lod.planes(get_viewport().get_camera_3d()),global_position,global_position)
			if animation_frame%gap==0:
				animation_player.advance(animation_clock);animation_clock=0.0
			if desired in ["walk","run"]:
				gait_phase=fposmod(animation_player.current_animation_position/animation_player.get_animation(desired).length,1.0)
		visual_lift=0.0
	else:
		visual_lift=absf(sin(stride))*0.045*moving
	if is_instance_valid(left_leg):
		left_leg.rotation.x=sin(stride)*0.5*moving
		right_leg.rotation.x=-sin(stride)*0.5*moving
	if position.y < -10.0:
		position = safe_position if has_safe_position else Vector3(0, 0.2, 4)
	tick_to = global_position
	if reveal_pending:
		reveal_pending=false
		visual.visible=true

## Walking but not moving with every side blocked (overlapping something): after 0.8 s the body
## goes back to where it last walked freely. Against a wall it can still turn away, so it stays.
func watch_trapped(delta: float, wants: bool) -> void:
	var speed_now := get_real_velocity().length()
	if not wants or not controls_enabled or speed_now > 0.3:
		trapped_time = 0.0
		if speed_now > 0.5 and is_on_floor() and position.y >= min_ground_y:
			free_clock += delta
			if free_clock > 0.5:
				free_clock = 0.0
				free_position = global_position
		return
	trapped_time += delta
	if trapped_time < 0.8: return
	trapped_time = 0.0
	for i in 8:
		var angle := TAU*i/8.0
		if not test_move(global_transform, Vector3(cos(angle), 0.0, sin(angle))*0.15): return
	# Only a short step back to a spot just walked from, and only when walking on the ground:
	# never a long jump (a stale spot from another place).
	if free_position == Vector3.INF or not is_on_floor(): return
	var back := free_position.distance_to(global_position)
	if back < 0.05 or back > 4.0: return
	global_position = free_position
	velocity = Vector3.ZERO
	trapped_escapes += 1

## Lifts the walker onto a ledge up to STEP_HEIGHT when it walks into one.
func step_up(delta: float) -> void:
	if not controls_enabled or not is_on_floor() or not is_on_wall(): return
	# Walking up to a seat never climbs the furniture it walks along.
	if ix != null and is_instance_valid(ix) and ix.busy(): return
	var motion := Vector3(velocity.x,0,velocity.z)*delta
	if motion.length()<0.001: return
	# Pressed against the same wall as a moment ago: that step was already refused. The two
	# test_moves against a dense collider (the pond pier's 11,687-face mesh) cost ~10 ms a tick.
	if Engine.get_physics_frames()<step_refused_until and global_position.distance_squared_to(step_refused_at)<0.01: return
	var lift := Vector3(0,STEP_HEIGHT,0)
	# Only a real ledge: terrain or a building floor under the new spot, no higher than a step.
	# Without it the walker hopped onto prop bases (a signboard) and slid off again. The ray is the
	# cheap test, so it goes first.
	var spot := global_position+lift+motion*2.0
	var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(spot+Vector3.UP*0.05, spot+Vector3.DOWN*(STEP_HEIGHT+0.2), 1|2))
	if hit.is_empty() or hit.position.y < global_position.y+0.08 or hit.position.y > global_position.y+STEP_HEIGHT+0.02 or test_move(global_transform,lift) or test_move(global_transform.translated(lift),motion*2.0):
		step_refused_at=global_position
		step_refused_until=Engine.get_physics_frames()+12
		return
	global_position+=lift+motion*2.0
	apply_floor_snap()

func react(kind: String) -> void:
	# Visual response only. The collision body and server position never change.
	if kind!="hurt" and action_kind=="hurt" and Time.get_ticks_msec()*.001<action_until: return
	var played := play_context_action(kind)
	if not played and is_instance_valid(action_pose): action_pose.trigger("thrust" if kind=="attack" and equipped=="spear" else kind)
	use_pose(kind)
	if reaction_tween and reaction_tween.is_valid(): reaction_tween.kill()
	visual.scale=Vector3.ONE
	if played: return
	# Seated or lying, the whole-body squash would bob the seat contact: the gesture alone plays.
	if is_instance_valid(ix) and ix.seated(): return
	reaction_tween=create_tween()
	reaction_tween.tween_property(visual,"scale",Vector3(1.06,0.91,1.06) if kind=="hurt" else Vector3(0.97,1.035,0.97),0.07)
	reaction_tween.tween_property(visual,"scale",Vector3.ONE,0.17).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	if not is_instance_valid(action_pose) and kind in ["attack","gather"] and is_instance_valid(equipment) and equipment.get_child_count()>0:
		var tool := equipment.get_child(0) as Node3D
		if tool and not tool.has_meta("swing"):
			tool.set_meta("swing",true)
			var rest := tool.rotation
			var swing := tool.create_tween()
			swing.tween_property(tool,"rotation",rest+Vector3(0.25,0,-0.9),0.08)
			swing.tween_property(tool,"rotation",rest,0.2)
			swing.tween_callback(func(): tool.remove_meta("swing"))

func play_context_action(kind: String) -> bool:
	if not is_instance_valid(animation_player) or (is_instance_valid(ix) and ix.busy()): return false
	var held := get_node_or_null("Held")
	if kind in ["greet","clap","bow","cheer"] and held!=null and bool(held.get("shown")): return false
	var spec := ContextMotions.action(kind,equipped)
	if spec.is_empty() or not animation_player.has_animation(str(spec.clip)): return false
	action_kind=kind;action_clip=str(spec.clip)
	action_start=float(spec.from)
	action_rate=float(spec.span)/float(spec.seconds)
	action_until=Time.get_ticks_msec()*.001+float(spec.seconds)
	current_clip="";idle_seconds=0.0
	if is_instance_valid(action_pose): action_pose.elapsed=action_pose.duration
	return true

func face_point(point: Vector3) -> void:
	var direction := point-position
	direction.y=0
	if direction.length_squared()<0.001: return
	action_facing=direction.normalized()
	facing=action_facing
	facing_until=Time.get_ticks_msec()*0.001+0.4

## Rebuilds the character in a new look; returns false when the look is unchanged (or the body
## is not built yet: _ready builds it in `avatar`).
func apply_avatar(value: Dictionary) -> bool:
	var next := value.duplicate(true)
	next["character"]=Roster.canonical(str(next.get("character",Roster.DEFAULT)))
	if next==avatar: return false
	avatar=next
	if not is_instance_valid(visual): return false
	var old_tool := equipped
	equipped=""
	for child in visual.get_children():
		visual.remove_child(child)
		child.queue_free()
	animation_player=null
	hand_skeleton=null
	action_pose=null
	finger_pose=null
	locomotion_pose=null
	equipment=null
	tool_node=null
	current_clip=""
	action_clip="";action_kind="";action_until=0.0;idle_seconds=0.0;animation_clock=0.0
	left_leg=null
	right_leg=null
	var was_stowed: Array=stowed.keys()
	stowed.clear()
	_build_character()
	apply_colors()
	look_builds+=1
	equip(old_tool)
	# The carried thing goes into the new hands (held_items.gd).
	var held_node := get_node_or_null("Held")
	if held_node:
		held_node.rebuild()
		held_node.refresh(false)
	for name in was_stowed: stow_new(name)
	return true

func apply_colors() -> void:
	# The eight characters (m1..f4, avatar_v2): their own skin is the tint reference, and the accent
	# colour paints their detail surface (bandana, headband, belt...).
	var id := str(avatar.get("character",""))
	# Partitioned GLBs retain original weights, UVs and textures per semantic surface.
	for mesh in visual.find_children("*","MeshInstance3D",true,false):
		for index in mesh.mesh.get_surface_count():
			var source: Material=mesh.mesh.surface_get_material(index)
			if not source is StandardMaterial3D: continue
			mesh.set_surface_override_material(index,preload("res://scripts/actor_materials.gd").surface(source,avatar))
	var headwear: String=avatar.get("headwear","none")
	# f4 (the sailor) wears her own straw hat in the model: no second hat on top.
	if id=="f4": headwear="none"
	if headwear!="none":
		var holder := Node3D.new()
		holder.name="Headwear_"+headwear
		visual.add_child(holder)
		holder.position.y=1.63
		holder.scale=Vector3.ONE*0.58
		if is_instance_valid(hand_skeleton):
			var head := hand_skeleton.find_bone("Head")
			if head>=0:
				var attachment := BoneAttachment3D.new()
				attachment.bone_name="Head"
				hand_skeleton.add_child(attachment)
				var desired: Transform3D=visual.global_transform*holder.transform
				var rest: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_rest(head)
				holder.reparent(attachment,false)
				holder.transform=rest.affine_inverse()*desired
		var hat_color := Color(avatar.get("coat","#dba448")).darkened(0.15)
		if headwear=="straw":
			# A wide straw brim, a low crown and a band in the accent colour.
			var straw := Color("#d9b46a")
			Art.sphere(holder,Vector3(0,0.0,0),Vector3(1.05,0.05,1.0),straw)
			Art.sphere(holder,Vector3(0,0.07,0),Vector3(0.6,0.24,0.56),straw.darkened(0.06))
			Art.sphere(holder,Vector3(0,0.035,0),Vector3(0.62,0.07,0.58),Color(avatar.get("accent","#a84a32")))
		else:
			Art.sphere(holder,Vector3(0,0.03,0),Vector3(0.63,0.2,0.57),hat_color)
			if headwear=="cap": Art.box(holder,Vector3(0,-0.04,-0.27),Vector3(0.42,0.045,0.3),hat_color)
			else: Art.sphere(holder,Vector3(0.05,0.09,0),Vector3(0.52,0.16,0.5),hat_color)
	if avatar.get("backpack",true):
		var bag := Node3D.new()
		bag.name="Backpack"
		visual.add_child(bag)
		bag.position=Vector3(0,0.98,0.15)
		# A leather pack: rounded body, a top flap and a buckle in the accent colour.
		var leather := Color("8a6440")
		Art.box(bag,Vector3(0,-0.03,0),Vector3(0.3,0.34,0.16),leather)
		Art.sphere(bag,Vector3(0,0.13,0),Vector3(0.3,0.14,0.16),leather)
		Art.box(bag,Vector3(0,0.1,0.07),Vector3(0.31,0.16,0.05),leather.darkened(0.18))
		Art.box(bag,Vector3(0,0.03,0.1),Vector3(0.06,0.06,0.02),Color(avatar.get("accent","#c9a35a")))
		Art.box(bag,Vector3(0,-0.1,0.09),Vector3(0.22,0.12,0.04),leather.darkened(0.08))
		if hand_skeleton and hand_skeleton.find_bone("Spine02")>=0:
			var attachment := BoneAttachment3D.new()
			attachment.bone_name="Spine02"
			hand_skeleton.add_child(attachment)
			var desired: Transform3D=visual.global_transform*bag.transform
			var rest: Transform3D=hand_skeleton.global_transform*hand_skeleton.get_bone_global_rest(hand_skeleton.find_bone("Spine02"))
			bag.reparent(attachment,false)
			bag.transform=rest.affine_inverse()*desired
