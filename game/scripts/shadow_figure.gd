extends CharacterBody3D
## One of the shadow folk: the Explorer B rig in a flat near-black silhouette
## (shaders/shadow_silhouette.gdshader) with white eyes, a white grin for happy
## moments and a few silhouette props, walking with the rig's own gait clips.
## The brain follows the shadow_paths.gd graph with move_and_slide: keeps to the
## right of the path, slows for other shadows, stops and turns when the walker
## comes close, steps aside when the walker blocks the way, and works itself free
## (side-step, turn back, a last-resort "slip" to the next node) if it ever stalls.
## shadow_folk.gd drives it from residents.gd: "travel" follows a route, "door"
## walks onto a door step and fades in, "emerge" steps out of a door, and a task
## ("fish", "sweep", "hoe", "write", "lamp", "deliver", "play") shows a hand prop
## while the shadow pauses at work.
##
## ---------------------------------------------------------------- still figures
## For rooms (interiors.gd): a fully dressed silhouette with no physics, brain or
## path graph. Animation is advanced only while it is visible (and slower when the
## camera is far), so a room full of them stays cheap.
##   const ShadowFigure = preload("res://scripts/shadow_figure.gd")
##   var who: Node3D = ShadowFigure.create_still("miller")  # any shadow resident id
##   room.add_child(who)            # dresses itself on _ready (bones need the tree)
##   who.position = seat_point      # see set_pose for where the origin goes
##   who.face(yaw)                  # radians, 0 = facing +Z (atan2(dir.x, dir.z))
##   who.set_pose("sit")            # "stand" (origin = feet)
##                                  # "sit" (origin = seat surface under the hips, knees toward face())
##                                  # "sit_ground" (origin = floor under the hips, legs forward)
##                                  # "lie" (on its back, origin = mattress top at the body's middle,
##                                  #        head toward face(); eyes close, animation stops)
##   who.play_clip("idle")          # "idle" | "walk" | "run" (walk/run in place; move it yourself)
##   who.set_night(0.0..1.0)        # rim light, eye glints, lantern glow
##   who.smile(3.0); who.pop("♪", 1.8); who.close_eyes(true)
##   who.task = "write"             # optional hand prop: fish/sweep/hoe/write (shown while still)
##   who.title / who.nameplate (Label3D, hide it if the room has its own labels)
## Cast villagers (naru/sora/moru/haeru) are not silhouettes: create_still() returns
## null for them; use npc.gd (idle clip only).
const SILHOUETTE := preload("res://shaders/shadow_silhouette.gdshader")
const MODEL := "res://assets/explorer_b_wardrobe.glb"
const MOTION := "res://assets/explorer_b_motion.glb"
const WALK := "shadow/walk"
const IDLE := "shadow/idle"
const BASE_SCALE := 1.7
const STEP_HEIGHT := 0.36
## Ground probes: terrain/rocks and decks/floors, never props or tree canopies.
const GROUND_MASK := 1|2
## Pond surfaces sit above the sea's shore line, so their beds count as water too.
const Fishing = preload("res://scripts/fishing.gd")
const GLINT_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;
uniform float strength = 0.0;
void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX*mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}
void fragment() {
	float d = length(UV-vec2(0.5))*2.0;
	float star = max(1.0-abs(UV.x-0.5)*28.0, 0.0)*max(1.0-d, 0.0)+max(1.0-abs(UV.y-0.5)*28.0, 0.0)*max(1.0-d, 0.0);
	float glow = pow(max(1.0-d, 0.0), 3.0)*0.55+star*0.5;
	ALBEDO = vec3(0.86, 0.92, 1.0)*glow*strength;
}
"""
const GRIN_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;
uniform float open = 1.0;
void fragment() {
	vec2 p = UV*2.0-1.0;
	float outer = length(vec2(p.x, (p.y+0.55)*1.25));
	float inner = length(vec2(p.x*0.98, (p.y+1.05-0.35*open)*1.35));
	if (outer > 1.0 || inner < 1.0 || open < 0.02) discard;
	ALBEDO = vec3(1.0);
}
"""
static var _library: AnimationLibrary

var spec: Dictionary = {}
var folk: Node
var paths: RefCounted
var title := ""
var height_scale := 1.0
var width_scale := 1.0
var pace := 1.25
var visual: Node3D
var figure: Node3D
var animator: AnimationPlayer
var skeleton: Skeleton3D
var walk_length := 1.0
var current_clip := ""
var materials: Array[ShaderMaterial] = []
var eyes: Array[MeshInstance3D] = []
var glints: Array[MeshInstance3D] = []
var grin: MeshInstance3D
var lantern: Node3D
## No real light: an emissive bulb plus an additive pool on the ground under the figure.
var lantern_glow: MeshInstance3D
var lantern_pool: MeshInstance3D
var bubble: Label3D
var nameplate: Label3D
## Brain.
var state := "pause"
var at_node := -1
var from_node := -1
var target_node := -1
var pause_left := 1.0
var look_clock := 0.0
var look_base := 0.0
var look_side := 1.0
var face_yaw := 0.0
var has_face := false
var horizontal := Vector2.ZERO
var greet_ready := true
var greet_left := 0.0
var talk_left := 0.0
var yield_time := 0.0
var sidestep_left := 0.0
var sidestep_side := 1.0
var stall_clock := 0.0
var stall_time := 0.0
var stall_anchor := Vector2.ZERO
var reversed_once := false
## Progress toward the steer point at the last stall check; pushes and jitter that
## do not bring the shadow closer count as stalling.
var stall_gap := INF
var stall_target := -1
## Off the path for this long -> walk straight back to the nearest path point.
var off_time := 0.0
var rejoining := false
var rejoin_point := Vector2.ZERO
var lead_route: Array[int] = []
var lead_waiting := false
var grin_left := 0.0
var bubble_left := 0.0
## Presence (night-only / day-only shadows fade out instead of walking).
var present := true
var fade := 1.0
var night := 0.0
var safe_position := Vector3.ZERO
var has_safe_position := false
var min_ground_y := 0.45
var settle_frames := 4
var just_placed := false
## On the floor with no motion last step: skip the ground probe until it walks again.
var resting := false
var ground_y := 0.0
var ground_clock := 0
static var _body_probe: PhysicsShapeQueryParameters3D
var body_probe: PhysicsShapeQueryParameters3D:
	get:
		if _body_probe == null:
			var ball := SphereShape3D.new()
			ball.radius = 0.16
			_body_probe = PhysicsShapeQueryParameters3D.new()
			_body_probe.shape = ball
			_body_probe.collision_mask = 2|8|16
		return _body_probe
## Step-ups in a row; reset after a metre of level walking, so a shadow can take
## a stair or a pavilion floor but never climb a rock or a post like a ladder.
var steps_in_row := 0
var since_step := 0.0
## Animation level of detail: advance the rig every anim_stride physics frames.
var anim_stride := 1
var anim_clock := 0.0
var anim_frame := 0
var step_clock := 0.0
## Room figure (create_still): no collider, no brain; _process animates while visible.
var still := false
## "stand", "sit", "sit_ground", "lie"
var pose := "stand"
var pose_dirty := true
## Hip height above the feet in visual space (metres), measured from the rig.
var hip_local := 0.9
var eyes_closed := false
var clip_speed := 1.0
## Current work prop ("" none) and its holder under visual; back gear by name.
var task := ""
var task_node: Node3D
var task_shown := ""
var task_clock := 0.0
var task_swing := 0.0
var gear_nodes := {}
## Schedule state (shadow_folk.gd): the place the walker has adopted from residents.gd,
## the block key, the building it is in or heading for, routes and door targets.
var place := ""
var block_key := ""
var building := ""
var activity := ""
var spot := ""
var transit := false
var roam_center := Vector2.ZERO
var roam_radius := 0.0
var stay := false
var travel_route: Array[int] = []
var door_point := Vector2.ZERO
var door_building := ""
var last_vanish := Vector2.INF
var last_appear := Vector2.INF
var vanish_building := ""
var appear_building := ""
var stops: Array = []
var current_stop: Dictionary = {}
## Why the current route was taken: "activity", "stop", "door" (shadow_folk.gd).
var travel_purpose := ""
## Counters the walk test reads.
var stats := {"rejoins":0,"overspeed":0,"distance":0.0,"sidesteps":0,"reversals":0,"slips":0,"water_resets":0,"yields":0,"greets":0,"arrivals":0,"pauses":0}

func configure(entry: Dictionary, owner_folk: Node, graph: RefCounted) -> void:
	spec = entry
	folk = owner_folk
	paths = graph
	title = TranslationServer.translate(str(entry.title))
	var build: Array = entry.get("build", [1.0, 1.0])
	height_scale = float(build[0])
	width_scale = float(build[1])
	pace = float(entry.get("speed", 1.25))
	roam_center = entry.get("home", Vector2.ZERO)
	roam_radius = float(entry.get("radius", 0.0))
	name = ("Still_" if still else "Shadow_")+str(entry.id)

## A dressed room figure for a shadow resident id, or null for unknown / cast ids.
static func create_still(id: String) -> Node3D:
	var entry := look(id)
	if entry.is_empty(): return null
	var figure_node = load("res://scripts/shadow_figure.gd").new()
	figure_node.still = true
	figure_node.configure(entry, null, null)
	return figure_node

## Appearance spec for a shadow id (shadow_folk.gd FOLK, loaded lazily: no cycle).
static func look(id: String) -> Dictionary:
	var folk_script: GDScript = load("res://scripts/shadow_folk.gd")
	for entry in folk_script.FOLK:
		if str(entry.id) == id: return entry
	return {}

func _ready() -> void:
	if still:
		collision_layer = 0
		collision_mask = 0
		set_physics_process(false)
	else:
		collision_layer = 4
		collision_mask = 1|2|4|8|16
		floor_snap_length = 0.45
		floor_max_angle = deg_to_rad(50.0)
		var shape := CollisionShape3D.new()
		var capsule := CapsuleShape3D.new()
		capsule.radius = 0.28*clampf(width_scale, 0.9, 1.25)
		capsule.height = maxf(1.5*height_scale, capsule.radius*2.0+0.1)
		shape.shape = capsule
		shape.position.y = capsule.height*0.5
		add_child(shape)
	set_process(still)
	visual = Node3D.new()
	add_child(visual)
	figure = Node3D.new()
	figure.scale = Vector3(width_scale, 1.0, width_scale)*BASE_SCALE*height_scale
	figure.scale.y = BASE_SCALE*height_scale
	visual.add_child(figure)
	build_body()
	nameplate = Label3D.new()
	nameplate.text = title
	nameplate.position.y = 1.88*height_scale+0.22
	preload("res://scripts/art.gd").style_nameplate(nameplate, 19)
	nameplate.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	nameplate.no_depth_test = false
	nameplate.modulate = Color("d4cdf2")
	nameplate.add_to_group("npc_nameplates")
	add_child(nameplate)
	bubble = Label3D.new()
	bubble.position.y = 1.88*height_scale+0.62
	bubble.pixel_size = 0.008
	bubble.font_size = 54
	bubble.outline_size = 10
	bubble.outline_modulate = Color(0.05, 0.06, 0.1, 0.95)
	bubble.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	bubble.visible = false
	add_child(bubble)
	set_meta("title", title)
	set_meta("shadow_id", spec.get("id", ""))
	if still:
		dress()
		apply_layout()

## Shared gait clips, retargeted once onto the wardrobe rig (as style_character.gd does).
static func library_for(target_animator: AnimationPlayer, target_skeleton: Skeleton3D) -> AnimationLibrary:
	if _library != null: return _library
	_library = AnimationLibrary.new()
	var reference := (load(MOTION) as PackedScene).instantiate()
	var sources := reference.find_children("*", "AnimationPlayer", true, false)
	if not sources.is_empty():
		var root: Node = target_animator.get_node(target_animator.root_node)
		var prefix := str(root.get_path_to(target_skeleton))
		for pair in [["walk", "B_TrailWalk"], ["idle", "B_Scout"]]:
			if not sources[0].has_animation(pair[1]): continue
			var clip: Animation = sources[0].get_animation(pair[1]).duplicate(true)
			for track in range(clip.get_track_count()-1, -1, -1):
				var path := clip.track_get_path(track)
				if path.get_subname_count() != 1 or target_skeleton.find_bone(str(path.get_subname(0))) < 0:
					clip.remove_track(track)
					continue
				clip.track_set_path(track, NodePath(prefix+":"+str(path.get_subname(0))))
			clip.loop_mode = Animation.LOOP_LINEAR
			_library.add_animation(pair[0], clip)
	reference.free()
	return _library

func build_body() -> void:
	var actor := (load(MODEL) as PackedScene).instantiate() as Node3D
	# The wardrobe GLB is X-forward; this turns its face to the figure's +Z.
	actor.rotation.y = -PI*0.5
	figure.add_child(actor)
	var silhouette := ShaderMaterial.new()
	silhouette.shader = SILHOUETTE
	materials.append(silhouette)
	for node in actor.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		mesh.material_override = silhouette
		mesh.visibility_range_end = 90.0
	var skeletons := actor.find_children("*", "Skeleton3D", true, false)
	var players := actor.find_children("*", "AnimationPlayer", true, false)
	if skeletons.is_empty() or players.is_empty(): return
	skeleton = skeletons[0]
	animator = players[0]
	animator.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	animator.add_animation_library("shadow", library_for(animator, skeleton))
	if animator.has_animation(WALK): walk_length = animator.get_animation(WALK).length
	play_clip(IDLE)
	animator.seek(randf()*maxf(0.1, animator.get_animation(IDLE).length if animator.has_animation(IDLE) else 0.1), true)

## "idle", "walk", "run" (the walk clip, faster) or a full "shadow/..." name.
func play_clip(clip: String) -> void:
	match clip:
		"idle": clip = IDLE
		"walk":
			clip = WALK
			clip_speed = 1.0
		"run":
			clip = WALK
			clip_speed = 1.75
	if clip == IDLE: clip_speed = 1.0
	if clip == current_clip or not is_instance_valid(animator) or not animator.has_animation(clip): return
	current_clip = clip
	animator.play(clip, 0.25)
	pose_dirty = true

var last_attach: Node3D
## Places a holder at `offset` (figure units, +Z = face) that follows `bone`.
func attach(bone: String, offset: Vector3, basis := Basis.IDENTITY) -> Node3D:
	var holder := Node3D.new()
	var index := skeleton.find_bone(bone) if is_instance_valid(skeleton) else -1
	if index < 0:
		figure.add_child(holder)
		holder.transform = Transform3D(basis, offset)
		last_attach = holder
		return holder
	var socket := BoneAttachment3D.new()
	last_attach = socket
	socket.bone_name = bone
	skeleton.add_child(socket)
	socket.add_child(holder)
	var rest: Transform3D = skeleton.global_transform*skeleton.get_bone_global_rest(index)
	holder.transform = rest.affine_inverse()*(figure.global_transform*Transform3D(basis, offset))
	return holder

func silhouette_mesh(parent: Node3D, mesh: Mesh, at: Vector3, rotation_degrees_value := Vector3.ZERO, size := Vector3.ONE) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.position = at
	instance.rotation_degrees = rotation_degrees_value
	instance.scale = size
	instance.material_override = materials[0]
	instance.visibility_range_end = 90.0
	parent.add_child(instance)
	return instance

func cylinder(top: float, bottom: float, height: float) -> CylinderMesh:
	var mesh := CylinderMesh.new()
	mesh.top_radius = top
	mesh.bottom_radius = bottom
	mesh.height = height
	mesh.radial_segments = 20
	mesh.rings = 1
	return mesh

func sphere(radius: float, height: float) -> SphereMesh:
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = height
	mesh.radial_segments = 16
	mesh.rings = 8
	return mesh

## Eyes, grin, glints and the silhouette props named in spec.gear. Called after
## the figure is in the tree (bone rests are read in world space).
func dress() -> void:
	var head := attach("Head", Vector3(0, 0.855, 0.0))
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color(1, 1, 1)
	var glint_material := ShaderMaterial.new()
	glint_material.shader = Shader.new()
	glint_material.shader.code = GLINT_SHADER
	var eye_shape: Array = spec.get("eyes", [0.033, 0.02])
	for side in [-1.0, 1.0]:
		var eye := MeshInstance3D.new()
		eye.mesh = sphere(0.5, 1.0)
		eye.scale = Vector3(float(eye_shape[0])*2.0, float(eye_shape[1])*2.0, 0.018)
		eye.position = Vector3(side*0.046, 0.002, 0.068)
		# Almond eyes tilt up toward the temples, the cartoon culprit's signature look.
		eye.rotation.z = side*deg_to_rad(float(spec.get("eye_tilt", 12.0)))
		eye.rotation.y = side*0.28
		eye.material_override = white
		eye.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		head.add_child(eye)
		eyes.append(eye)
		var glint := MeshInstance3D.new()
		var quad := QuadMesh.new()
		quad.size = Vector2(0.16, 0.16)
		glint.mesh = quad
		glint.position = Vector3(side*0.046, 0.006, 0.09)
		glint.material_override = glint_material
		glint.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		glint.visible = false
		head.add_child(glint)
		glints.append(glint)
	grin = MeshInstance3D.new()
	var mouth := QuadMesh.new()
	mouth.size = Vector2(0.105, 0.05)
	grin.mesh = mouth
	grin.position = Vector3(0, -0.042, 0.072)
	var grin_material := ShaderMaterial.new()
	grin_material.shader = Shader.new()
	grin_material.shader.code = GRIN_SHADER
	grin.material_override = grin_material
	grin.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	grin.visible = bool(spec.get("always_grin", false))
	head.add_child(grin)
	for gear in spec.get("gear", []):
		add_gear(str(gear))
	if is_instance_valid(skeleton):
		var thigh := skeleton.find_bone("L_Thigh")
		if thigh >= 0:
			var hip_world: Vector3 = skeleton.global_transform*skeleton.get_bone_global_rest(thigh).origin
			hip_local = (visual.global_transform.affine_inverse()*hip_world).y

func add_gear(gear: String) -> void:
	last_attach = null
	_add_gear(gear)
	# Remember the holder so a work prop can stand in for the carried tool.
	if is_instance_valid(last_attach): gear_nodes[gear] = last_attach

func _add_gear(gear: String) -> void:
	match gear:
		"fedora":
			var hat := attach("Head", Vector3(0, 0.965, -0.025), Basis(Vector3.RIGHT, deg_to_rad(-6)))
			silhouette_mesh(hat, cylinder(0.16, 0.165, 0.012), Vector3.ZERO)
			silhouette_mesh(hat, cylinder(0.095, 0.112, 0.09), Vector3(0, 0.045, 0))
		"tophat":
			var hat := attach("Head", Vector3(0, 0.975, -0.02))
			silhouette_mesh(hat, cylinder(0.13, 0.13, 0.012), Vector3.ZERO)
			silhouette_mesh(hat, cylinder(0.082, 0.082, 0.15), Vector3(0, 0.075, 0))
		"cap":
			var hat := attach("Head", Vector3(0, 0.93, -0.02))
			silhouette_mesh(hat, sphere(0.128, 0.16), Vector3(0, 0.0, 0))
			silhouette_mesh(hat, cylinder(0.09, 0.09, 0.012), Vector3(0, -0.012, 0.13), Vector3.ZERO, Vector3(1.0, 1.0, 0.75))
		"straw":
			var hat := attach("Head", Vector3(0, 0.96, -0.02), Basis(Vector3.RIGHT, deg_to_rad(-8)))
			silhouette_mesh(hat, cylinder(0.2, 0.21, 0.012), Vector3.ZERO)
			silhouette_mesh(hat, cylinder(0.09, 0.11, 0.06), Vector3(0, 0.032, 0))
		"bucket":
			var hat := attach("Head", Vector3(0, 0.955, -0.02))
			silhouette_mesh(hat, cylinder(0.1, 0.14, 0.07), Vector3(0, 0.015, 0))
		"beanie":
			var hat := attach("Head", Vector3(0, 0.94, -0.025))
			silhouette_mesh(hat, sphere(0.13, 0.2), Vector3.ZERO)
			silhouette_mesh(hat, sphere(0.035, 0.07), Vector3(0, 0.1, 0))
		"beret":
			var hat := attach("Head", Vector3(0.015, 0.955, -0.02), Basis(Vector3.BACK, deg_to_rad(-14)))
			silhouette_mesh(hat, sphere(0.15, 0.08), Vector3.ZERO)
			silhouette_mesh(hat, cylinder(0.006, 0.01, 0.04), Vector3(0, 0.045, 0))
		"satchel":
			var bag := attach("Pelvis", Vector3(-0.115, 0.43, 0.02))
			silhouette_mesh(bag, BoxMesh.new(), Vector3.ZERO, Vector3.ZERO, Vector3(0.05, 0.11, 0.13))
		"backpack":
			var pack := attach("Spine02", Vector3(0, 0.6, -0.12))
			silhouette_mesh(pack, BoxMesh.new(), Vector3.ZERO, Vector3.ZERO, Vector3(0.2, 0.24, 0.11))
			silhouette_mesh(pack, cylinder(0.045, 0.045, 0.2), Vector3(0, 0.15, 0.0), Vector3(0, 0, 90))
		"umbrella":
			# Carried over the right shoulder, canopy tilted back above the hat.
			var holder := attach("Spine02", Vector3(0.13, 0.62, -0.06), Basis(Vector3.RIGHT, deg_to_rad(-16))*Basis(Vector3.BACK, deg_to_rad(-10)))
			silhouette_mesh(holder, cylinder(0.007, 0.007, 0.66), Vector3(0, 0.33, 0))
			silhouette_mesh(holder, cylinder(0.0, 0.36, 0.14), Vector3(0, 0.66, 0))
			silhouette_mesh(holder, cylinder(0.012, 0.012, 0.05), Vector3(0, 0.75, 0))
		"rod":
			var holder := attach("Spine02", Vector3(0.09, 0.66, -0.06), Basis(Vector3.RIGHT, deg_to_rad(-38))*Basis(Vector3.BACK, deg_to_rad(-12)))
			silhouette_mesh(holder, cylinder(0.004, 0.009, 1.15), Vector3(0, 0.3, 0))
			silhouette_mesh(holder, cylinder(0.025, 0.025, 0.03), Vector3(0, -0.12, 0.02), Vector3(90, 0, 0))
		"broom":
			var holder := attach("Spine02", Vector3(-0.08, 0.64, -0.07), Basis(Vector3.RIGHT, deg_to_rad(-30))*Basis(Vector3.BACK, deg_to_rad(18)))
			silhouette_mesh(holder, cylinder(0.008, 0.008, 0.8), Vector3(0, 0.1, 0))
			silhouette_mesh(holder, BoxMesh.new(), Vector3(0, 0.6, 0), Vector3.ZERO, Vector3(0.14, 0.2, 0.035))
			silhouette_mesh(holder, BoxMesh.new(), Vector3(0, 0.49, 0), Vector3.ZERO, Vector3(0.08, 0.04, 0.04))
		"hoe":
			var holder := attach("Spine02", Vector3(0.08, 0.64, -0.07), Basis(Vector3.RIGHT, deg_to_rad(-30))*Basis(Vector3.BACK, deg_to_rad(-18)))
			silhouette_mesh(holder, cylinder(0.008, 0.008, 0.78), Vector3(0, 0.1, 0))
			silhouette_mesh(holder, BoxMesh.new(), Vector3(0, 0.5, 0.04), Vector3.ZERO, Vector3(0.09, 0.012, 0.08))
		"scarf":
			var holder := attach("Spine02", Vector3(0, 0.74, 0))
			silhouette_mesh(holder, cylinder(0.085, 0.1, 0.05), Vector3.ZERO)
			silhouette_mesh(holder, BoxMesh.new(), Vector3(0.05, -0.08, -0.08), Vector3.ZERO, Vector3(0.04, 0.14, 0.015))
		"lantern":
			lantern = attach("R_Hand", Vector3(-0.27, 0.66, 0.02))
			var cage := Node3D.new()
			lantern.add_child(cage)
			silhouette_mesh(cage, cylinder(0.002, 0.002, 0.06), Vector3(0, -0.03, 0))
			silhouette_mesh(cage, cylinder(0.02, 0.035, 0.025), Vector3(0, -0.07, 0))
			silhouette_mesh(cage, cylinder(0.035, 0.035, 0.012), Vector3(0, -0.15, 0))
			lantern_glow = MeshInstance3D.new()
			lantern_glow.mesh = sphere(0.032, 0.06)
			lantern_glow.position = Vector3(0, -0.11, 0)
			var glow := StandardMaterial3D.new()
			glow.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			glow.albedo_color = Color("ffd38a")
			lantern_glow.material_override = glow
			lantern_glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			cage.add_child(lantern_glow)
			# A warm pool on the ground instead of an OmniLight3D (one extra pass per lit
			# mesh in the Compatibility renderer); it follows the body, not the swinging hand.
			lantern_pool = MeshInstance3D.new()
			var quad := QuadMesh.new()
			quad.size = Vector2(3.4, 3.4)
			quad.orientation = PlaneMesh.FACE_Y
			lantern_pool.mesh = quad
			lantern_pool.position = Vector3(0.25, 0.06, 0.1)
			lantern_pool.material_override = pool_material()
			lantern_pool.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			lantern_pool.visible = false
			add_child(lantern_pool)
		"flourcap":
			# A baker's puffy cap over a band: the miller's flour-dusted silhouette.
			var hat := attach("Head", Vector3(0, 0.95, -0.025), Basis(Vector3.RIGHT, deg_to_rad(-5)))
			silhouette_mesh(hat, cylinder(0.112, 0.112, 0.07), Vector3.ZERO)
			silhouette_mesh(hat, sphere(0.135, 0.24), Vector3(0, 0.12, -0.01), Vector3.ZERO, Vector3(1.0, 1.0, 0.95))
			silhouette_mesh(hat, sphere(0.06, 0.1), Vector3(0.05, 0.2, 0.02))
		"apron":
			# Bib and a flared skirt standing a little off the body so the outline shows it.
			var bib := attach("Spine02", Vector3(0, 0.64, 0.085))
			silhouette_mesh(bib, BoxMesh.new(), Vector3.ZERO, Vector3(-6, 0, 0), Vector3(0.12, 0.1, 0.012))
			var skirt := attach("Pelvis", Vector3(0, 0.44, 0.075))
			silhouette_mesh(skirt, BoxMesh.new(), Vector3(0, -0.07, 0.0), Vector3(-10, 0, 0), Vector3(0.17, 0.17, 0.012))
			silhouette_mesh(skirt, cylinder(0.006, 0.006, 0.24), Vector3(0, 0.02, -0.05), Vector3(0, 0, 90))
		"glasses":
			# Round rims cut a dark ring through the white eyes; arms poke out at the temples.
			var frame_holder := attach("Head", Vector3(0, 0.857, 0.0))
			for side in [-1.0, 1.0]:
				var rim := MeshInstance3D.new()
				var ring := TorusMesh.new()
				ring.inner_radius = 0.026
				ring.outer_radius = 0.034
				ring.rings = 16
				ring.ring_segments = 6
				rim.mesh = ring
				rim.position = Vector3(side*0.047, 0.0, 0.083)
				rim.rotation = Vector3(PI*0.5, 0, 0)
				rim.material_override = materials[0]
				frame_holder.add_child(rim)
				silhouette_mesh(frame_holder, cylinder(0.004, 0.004, 0.11), Vector3(side*0.083, 0.004, 0.035), Vector3(90, 0, 0))
			silhouette_mesh(frame_holder, cylinder(0.004, 0.004, 0.026), Vector3(0, 0.006, 0.086), Vector3(0, 0, 90))

## ------------------------------------------------------------------ appearance

func set_night(value: float) -> void:
	night = value
	for material in materials:
		material.set_shader_parameter("rim_strength", lerpf(0.28, 0.8, night))
	for glint in glints:
		glint.visible = night > 0.3
		(glint.material_override as ShaderMaterial).set_shader_parameter("strength", night*0.9)
	if is_instance_valid(lantern):
		var lit: bool = night > 0.35 or bool(spec.get("lantern_always", false))
		lantern_glow.visible = lit
		lantern_pool.visible = lit and not still
		(lantern_pool.material_override as ShaderMaterial).set_shader_parameter("strength", 0.42*maxf(night, 0.35)*fade if lit else 0.0)

const POOL_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;
uniform float strength = 0.0;
void fragment() {
	float d = length(UV-vec2(0.5))*2.0;
	ALBEDO = vec3(1.0, 0.72, 0.42)*pow(max(1.0-d, 0.0), 2.0)*strength;
}
"""
static var _pool_shader: Shader
func pool_material() -> ShaderMaterial:
	if _pool_shader == null:
		_pool_shader = Shader.new()
		_pool_shader.code = POOL_SHADER
	var material := ShaderMaterial.new()
	material.shader = _pool_shader
	material.render_priority = 2
	return material

func set_present(value: bool) -> void:
	if value == present: return
	present = value
	if present:
		visible = true
		set_physics_process(true)
		collision_layer = 4
		collision_mask = 1|2|4|8|16
		state = "pause"
		pause_left = 1.0
		has_safe_position = false
		settle_frames = 4

func update_fade(delta: float) -> void:
	var goal := 1.0 if present else 0.0
	if is_equal_approx(fade, goal) and (present or not visible): return
	fade = move_toward(fade, goal, delta/1.2)
	for material in materials: material.set_shader_parameter("fade", fade)
	for eye in eyes: eye.visible = fade > 0.35
	if is_instance_valid(nameplate): nameplate.modulate.a = fade
	if fade <= 0.0 and not present:
		visible = false
		collision_layer = 0
		collision_mask = 0
		state = "hidden"
		transit = false
		# Indoors: no physics at all until the schedule brings it out again.
		set_physics_process(false)

func smile(seconds: float) -> void:
	grin_left = maxf(grin_left, seconds)
	if is_instance_valid(grin): grin.visible = true

func pop(text: String, seconds := 1.8) -> void:
	if not is_instance_valid(bubble): return
	bubble.text = text
	bubble.visible = true
	bubble_left = seconds
	bubble.scale = Vector3.ONE*0.3
	var tween := bubble.create_tween()
	tween.tween_property(bubble, "scale", Vector3.ONE, 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

## ------------------------------------------------------------------ poses

## "stand", "sit", "sit_ground" or "lie" (see the header for where the origin goes).
func set_pose(kind: String) -> void:
	if not kind in ["stand", "sit", "sit_ground", "lie"]: kind = "stand"
	if kind == pose and not pose_dirty: return
	pose = kind
	pose_dirty = true
	if kind == "lie": close_eyes(true)
	elif eyes_closed: close_eyes(false)
	if is_instance_valid(visual): apply_layout()

## Turns the figure to `yaw` at once (radians, 0 = facing +Z).
func face(yaw: float) -> void:
	face_yaw = yaw
	has_face = true
	if is_instance_valid(visual): apply_layout()

func close_eyes(value: bool) -> void:
	eyes_closed = value
	var shape: Array = spec.get("eyes", [0.033, 0.02])
	for eye in eyes:
		eye.scale.y = 0.004 if value else float(shape[1])*2.0

## Places the visual for the pose: seated hips on the origin, a lying body centred on it.
func apply_layout() -> void:
	var length := 1.88*height_scale
	match pose:
		"lie":
			var dir := Vector3(sin(face_yaw), 0, cos(face_yaw))
			visual.rotation = Vector3(-PI*0.5, face_yaw+PI, 0)
			visual.position = -dir*length*0.5+Vector3(0, 0.16*width_scale, 0)
		"sit":
			visual.rotation = Vector3(0, face_yaw, 0)
			visual.position = Vector3(0, -hip_local+0.04, 0)
		"sit_ground":
			visual.rotation = Vector3(0, face_yaw, 0)
			visual.position = Vector3(0, -hip_local+0.11, 0)
		_:
			if still: visual.rotation = Vector3(0, face_yaw, 0)
			else: visual.rotation.x = 0.0
			visual.position = Vector3.ZERO
	if is_instance_valid(nameplate):
		nameplate.position.y = (0.75 if pose == "lie" else (1.3 if pose.begins_with("sit") else 1.88))*height_scale+0.22
		bubble.position.y = nameplate.position.y+0.4

## Bends the legs after each animation step (the clip rewrites them every advance).
func apply_bone_pose() -> void:
	if not is_instance_valid(skeleton) or not pose.begins_with("sit"): return
	var body: Basis = visual.global_basis.orthonormalized()
	var hip := -1.45 if pose == "sit" else -1.5
	var knee := 1.45 if pose == "sit" else 0.12
	for side in ["L", "R"]:
		bend(side+"_Thigh", hip, body)
		bend(side+"_Calf", knee, body)
	bend("Spine02", 0.05, body)

## Rotates a bone about the body's sideways axis, in world space (field_objects SeatPose).
func bend(bone: String, angle: float, body: Basis) -> void:
	var index := skeleton.find_bone(bone)
	if index < 0: return
	var world_axis := body*Vector3.RIGHT
	var bone_world := skeleton.global_basis*skeleton.get_bone_global_pose(index).basis
	var local_axis := (bone_world.inverse()*world_axis).normalized()
	skeleton.set_bone_pose_rotation(index, skeleton.get_bone_pose_rotation(index)*Quaternion(local_axis, angle))

## ------------------------------------------------------------------ work props

## Shows the hand prop for `kind` (and hides the carried tool) or clears it.
func show_task(kind: String) -> void:
	if kind == task_shown: return
	task_shown = kind
	if is_instance_valid(task_node):
		task_node.queue_free()
		task_node = null
	for gear in gear_nodes: gear_nodes[gear].visible = true
	if kind.is_empty() or not is_instance_valid(visual) or materials.is_empty(): return
	task_node = Node3D.new()
	task_node.name = "Task"
	visual.add_child(task_node)
	var h := height_scale
	match kind:
		"fish":
			# Rod held out over the water, the line dropping from its tip.
			task_node.position = Vector3(0.08, 1.0*h, 0.22)
			task_node.rotation_degrees = Vector3(52, 0, 0)
			silhouette_mesh(task_node, cylinder(0.006, 0.014, 2.1), Vector3(0, 1.0, 0))
			var tip := Node3D.new()
			tip.position = Vector3(0, 2.05, 0)
			tip.rotation_degrees = Vector3(-52, 0, 0)
			task_node.add_child(tip)
			silhouette_mesh(tip, cylinder(0.003, 0.003, 1.7), Vector3(0, -0.85, 0))
			hide_gear("rod")
		"sweep":
			task_node.position = Vector3(0.0, 0.95*h, 0.18)
			var handle := Node3D.new()
			handle.rotation_degrees = Vector3(152, 0, 0)
			task_node.add_child(handle)
			silhouette_mesh(handle, cylinder(0.009, 0.009, 1.1), Vector3(0, 0.55, 0))
			silhouette_mesh(handle, BoxMesh.new(), Vector3(0, 1.12, 0), Vector3.ZERO, Vector3(0.24, 0.16, 0.05))
			hide_gear("broom")
		"hoe":
			task_node.position = Vector3(0.05, 1.0*h, 0.15)
			var handle := Node3D.new()
			handle.rotation_degrees = Vector3(120, 0, 0)
			task_node.add_child(handle)
			silhouette_mesh(handle, cylinder(0.009, 0.009, 1.15), Vector3(0, 0.5, 0))
			silhouette_mesh(handle, BoxMesh.new(), Vector3(0, 1.08, -0.05), Vector3.ZERO, Vector3(0.12, 0.016, 0.14))
			hide_gear("hoe")
		"write":
			# A notebook on the lap and a pencil.
			task_node.position = Vector3(0, hip_local+0.06, 0.34)
			silhouette_mesh(task_node, BoxMesh.new(), Vector3.ZERO, Vector3(-28, 0, 0), Vector3(0.2, 0.02, 0.15))
			silhouette_mesh(task_node, cylinder(0.004, 0.004, 0.13), Vector3(0.07, 0.06, 0.02), Vector3(-30, 0, 30))
		"deliver":
			task_node.position = Vector3(0.12, 1.05*h, 0.3)
			silhouette_mesh(task_node, BoxMesh.new(), Vector3.ZERO, Vector3(10, 0, 0), Vector3(0.16, 0.11, 0.012))
	task_clock = randf()*3.0

func hide_gear(gear: String) -> void:
	if gear_nodes.has(gear): gear_nodes[gear].visible = false

## Small loops on the prop: sweep sway, hoe chops, a rod twitch now and then.
func animate_task(delta: float) -> void:
	if not is_instance_valid(task_node): return
	task_clock += delta
	match task_shown:
		"sweep":
			task_node.rotation.y = sin(task_clock*3.1)*0.55
			task_node.rotation.z = sin(task_clock*3.1)*0.08
		"hoe":
			var chop := pow(maxf(sin(task_clock*2.2), 0.0), 3.0)
			task_node.rotation.x = -chop*0.75
		"fish":
			task_swing = maxf(task_swing-delta, 0.0)
			# A cast: the rod swings back over the shoulder and forward again.
			var back := sin((1.0-task_swing/1.2)*PI)*-1.1 if task_swing > 0.0 else sin(task_clock*0.9)*0.02
			task_node.rotation.x = deg_to_rad(52.0)+back
		"write":
			task_node.rotation.y = sin(task_clock*1.3)*0.05

func cast_rod() -> void:
	if task_shown == "fish": task_swing = 1.2

## ------------------------------------------------------------------ still figures

func _process(delta: float) -> void:
	if not still:
		set_process(false)
		return
	if grin_left > 0.0:
		grin_left -= delta
		if grin_left <= 0.0 and is_instance_valid(grin): grin.visible = bool(spec.get("always_grin", false))
	if bubble_left > 0.0:
		bubble_left -= delta
		if bubble_left <= 0.0: bubble.visible = false
	if not is_visible_in_tree() or not is_instance_valid(animator): return
	if task != task_shown: show_task(task)
	animate_task(delta)
	anim_clock += delta
	anim_frame += 1
	# Lying figures hold one frame; others step slower when the camera is far.
	if pose == "lie" and not pose_dirty: return
	var stride := 1
	var camera := get_viewport().get_camera_3d()
	if camera:
		var d := camera.global_position.distance_to(global_position)
		stride = 1 if d < 14.0 else (2 if d < 30.0 else 4)
	if anim_frame % stride != 0 and not pose_dirty: return
	animator.speed_scale = clip_speed
	animator.advance(anim_clock)
	anim_clock = 0.0
	pose_dirty = false
	apply_bone_pose()

## ------------------------------------------------------------------ brain

func place_at(node: int, toward: int) -> void:
	at_node = node
	from_node = toward
	var p: Vector2 = paths.points[node]
	if toward >= 0: p = p.lerp(paths.points[toward], randf_range(0.1, 0.6))
	position = ground_point(p, 0.05)
	velocity = Vector3.ZERO
	has_safe_position = false
	just_placed = true
	resting = false
	ground_y = position.y
	ground_clock = 0
	target_node = toward if toward >= 0 else node
	state = "walk" if toward >= 0 else "pause"
	stall_anchor = p

## A door step under an eave: probe down from just above the path node's ground
## instead of from the sky, so the porch roof is never mistaken for the floor.
func step_point(step: Vector2, node: int, lift: float) -> Vector3:
	var base := ground_point(paths.points[node], 0.0).y if node >= 0 else 60.0
	return ground_point(step, lift, base+1.8)

func ground_point(p: Vector2, lift: float, from_y := 60.0) -> Vector3:
	var space := get_world_3d().direct_space_state if is_inside_tree() else null
	if space:
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x, from_y, p.y), Vector3(p.x, -20, p.y), GROUND_MASK))
		if not hit.is_empty(): return Vector3(p.x, hit.position.y+lift, p.y)
	return Vector3(p.x, 2.3+lift, p.y)

func xz() -> Vector2:
	return Vector2(position.x, position.z)

func talk_to_player(at: Vector3) -> void:
	state = "talk"
	talk_left = 30.0
	face_toward(Vector2(at.x, at.z)-xz())
	smile(4.0)

func end_talk() -> void:
	if state == "talk":
		talk_left = 0.0

func face_toward(direction: Vector2) -> void:
	if direction.length_squared() < 0.0004: return
	face_yaw = atan2(direction.x, direction.y)
	has_face = true

func begin_pause(seconds: float, look_yaw := INF) -> void:
	state = "pause"
	pause_left = seconds
	look_clock = randf_range(0.8, 1.6)
	look_side = 1.0 if randf() < 0.5 else -1.0
	if look_yaw != INF:
		face_yaw = look_yaw
		has_face = true
	look_base = face_yaw if has_face else visual.rotation.y
	stats.pauses += 1

func begin_lead(route: Array[int]) -> void:
	lead_route = route.duplicate()
	while not lead_route.is_empty() and lead_route[0] == at_node: lead_route.remove_at(0)
	if lead_route.is_empty():
		folk.lead_arrived(self)
		return
	state = "lead"
	target_node = lead_route[0]
	lead_waiting = false

## Walks a node route (no waiting for the walker); folk.travel_arrived() at the end.
func begin_travel(route: Array[int]) -> void:
	travel_route = route.duplicate()
	# Drop the start node only when actually standing on it (not after a sidestep or
	# on a door step), so the first leg never cuts across a corner.
	while not travel_route.is_empty() and travel_route[0] == at_node and xz().distance_to(paths.points[at_node]) < 1.0: travel_route.remove_at(0)
	has_face = false
	show_task("")
	if pose != "stand": set_pose("stand")
	if travel_route.is_empty():
		state = "pause"
		pause_left = 0.2
		folk.travel_arrived(self)
		return
	state = "travel"
	target_node = travel_route[0]
	reversed_once = false

## Walks straight onto a door step (off the path); folk.door_reached() there.
func begin_door(step: Vector2) -> void:
	door_point = step
	state = "door"
	has_face = false
	show_task("")
	if pose != "stand": set_pose("stand")

## Steps out of a door toward its path node; folk.emerged() there.
func begin_emerge(step: Vector2, node: int) -> void:
	at_node = node
	from_node = node
	target_node = node
	door_point = paths.points[node]
	position = step_point(step, node, 0.05)
	ground_y = position.y
	ground_clock = 0
	velocity = Vector3.ZERO
	horizontal = Vector2.ZERO
	has_safe_position = false
	just_placed = true
	settle_frames = 4
	state = "emerge"
	resting = false
	show_task("")
	face_toward(paths.points[node]-step)
	visual.rotation.y = face_yaw

func cancel_lead() -> void:
	lead_route.clear()
	if state == "lead":
		state = "pause"
		pause_left = 1.5

## Picks the next node from at_node. Wanderers avoid going straight back; homebodies
## stay inside their radius; spurs and porches are only taken now and then.
func choose_next() -> void:
	var options: Array = []
	var home: Vector2 = roam_center
	var radius := roam_radius
	for next in paths.links[at_node]:
		if next == from_node and paths.links[at_node].size() > 1: continue
		if radius > 0.0 and paths.points[next].distance_to(home) > radius: continue
		var weight := 1.0
		match paths.kinds[next]:
			"spot", "spur": weight = float(spec.get("spot_bias", 0.35))
			"porch": weight = float(spec.get("porch_bias", 0.3))
			"bridge": weight = float(spec.get("bridge_bias", 0.5))
		options.append([next, weight])
	if options.is_empty():
		options.append([from_node if from_node >= 0 else paths.links[at_node][0], 1.0])
	var total := 0.0
	for option in options: total += float(option[1])
	var roll := randf()*total
	var chosen: int = options[0][0]
	for option in options:
		roll -= float(option[1])
		if roll <= 0.0:
			chosen = option[0]
			break
	target_node = chosen
	state = "walk"
	reversed_once = false

func arrive() -> void:
	from_node = at_node
	at_node = target_node
	stats.arrivals += 1
	var kind: String = paths.kinds[at_node]
	if state == "travel":
		if not travel_route.is_empty() and travel_route[0] == at_node: travel_route.remove_at(0)
		if travel_route.is_empty():
			state = "pause"
			pause_left = 0.5
			folk.travel_arrived(self)
			return
		target_node = travel_route[0]
		return
	if state == "lead":
		if not lead_route.is_empty() and lead_route[0] == at_node: lead_route.remove_at(0)
		if lead_route.is_empty():
			folk.lead_arrived(self)
			var view: Vector2 = paths.points[at_node]-paths.points[from_node]
			begin_pause(6.0, atan2(view.x, view.y))
			return
		target_node = lead_route[0]
		return
	if folk.has_method("walker_arrived") and folk.walker_arrived(self): return
	var degree: int = paths.links[at_node].size()
	if kind == "spot":
		var view: Vector2 = paths.points[at_node]-paths.points[from_node]
		begin_pause(randf_range(6.0, 12.0), atan2(view.x, view.y))
	elif kind == "porch":
		var door: Vector2 = paths.faces.get(at_node, paths.points[at_node])-paths.points[at_node]
		begin_pause(randf_range(2.5, 5.0), atan2(door.x, door.y))
	elif degree >= 3 and randf() < 0.35:
		begin_pause(randf_range(1.5, 4.0))
	elif degree == 1:
		begin_pause(randf_range(1.0, 3.0))
	elif randf() < 0.08:
		begin_pause(randf_range(1.0, 2.5))
	else:
		choose_next()

## Where to steer: the target node, shifted to the right of the segment so two
## shadows meeting on a path pass each other.
func steer_point() -> Vector2:
	if state in ["door", "emerge"]: return door_point
	if rejoining: return rejoin_point
	var to: Vector2 = paths.points[target_node]
	if at_node < 0 or at_node == target_node: return to
	var from: Vector2 = paths.points[at_node]
	var along := to-from
	if along.length() < 0.01: return to
	var kind: String = paths.kinds[target_node]
	if kind in ["spot", "porch"] or paths.links[target_node].size() == 1: return to
	return to+Vector2(-along.y, along.x).normalized()*paths.lane(at_node, target_node)

## Profiling (tests): microseconds all walkers spent in their physics step.
static var profile := false
static var profile_us := 0

func _physics_process(delta: float) -> void:
	if not profile:
		step(delta)
		return
	var started := Time.get_ticks_usec()
	step(delta)
	profile_us += Time.get_ticks_usec()-started

func step(delta: float) -> void:
	update_fade(delta)
	if state == "hidden" or not is_instance_valid(folk): return
	if settle_frames > 0:
		settle_frames -= 1
		if settle_frames == 0:
			var ground := ground_point(xz(), 0.05)
			if position.y < ground.y-0.05 or position.y > ground.y+1.5: position = ground
			ground_y = position.y
			ground_clock = 0
	var me := xz()
	var player_xz: Vector2 = folk.player_xz()
	var to_player := player_xz-me
	var player_gap := to_player.length()
	var wish := Vector2.ZERO
	var speed := 0.0
	var walking := false
	if player_gap > 6.0: greet_ready = true
	if greet_ready and player_gap < 2.6 and present and state in ["walk", "pause", "travel"]:
		greet_ready = false
		greet_left = randf_range(2.2, 3.4)
		stats.greets += 1
		var heading := Vector2(sin(visual.rotation.y), cos(visual.rotation.y))
		pop("!?" if heading.dot(to_player.normalized()) < -0.2 else "…", 1.6)
	if greet_left > 0.0 and state in ["walk", "pause", "travel"]:
		greet_left -= delta
		face_toward(to_player)
	elif state == "talk":
		talk_left -= delta
		face_toward(to_player)
		if talk_left <= 0.0 or player_gap > 4.5:
			begin_pause(randf_range(1.0, 2.0), atan2(to_player.x, to_player.y))
	elif state == "pause":
		pause_left -= delta
		look_clock -= delta
		if look_clock <= 0.0:
			look_clock = randf_range(1.0, 2.0)
			look_side = -look_side
			face_yaw = look_base+look_side*randf_range(0.35, 0.8)
			has_face = true
		if pause_left <= 0.0:
			has_face = false
			if not (folk.has_method("pause_over") and folk.pause_over(self)): choose_next()
	elif state in ["walk", "lead", "travel", "door", "emerge"]:
		var target := steer_point()
		var gap := target.distance_to(me)
		if state == "lead":
			# Wait for the walker to keep up; look back with a "?" now and then.
			if player_gap > 7.5 and not lead_waiting:
				lead_waiting = true
				pop("?", 1.4)
			elif player_gap < 4.5:
				lead_waiting = false
		if gap < 0.45 and rejoining:
			rejoining = false
			off_time = 0.0
		elif gap < 0.45 and state == "door":
			folk.door_reached(self)
		elif gap < 0.45 and state == "emerge":
			state = "pause"
			pause_left = 0.3
			folk.emerged(self)
		elif gap < 0.45:
			arrive()
		elif not (state == "lead" and lead_waiting):
			wish = (target-me)/gap
			speed = pace*(1.18 if state == "lead" else 1.0)
			if state in ["door", "emerge"]: speed = minf(pace, 1.1)
			walking = true
			has_face = false
		else:
			face_toward(to_player)
	# The walker standing in the way: stop and look, then step around.
	if walking and player_gap < 1.6 and wish.dot(to_player/maxf(player_gap, 0.01)) > 0.45 and sidestep_left <= 0.0:
		if yield_time == 0.0: stats.yields += 1
		yield_time += delta
		face_toward(to_player)
		if yield_time > 1.6:
			sidestep_side = 1.0 if wish.orthogonal().dot(to_player) < 0.0 else -1.0
			sidestep_left = 1.6
			yield_time = 0.0
		wish = Vector2.ZERO
		walking = false
	elif yield_time > 0.0 and (not walking or player_gap > 2.0):
		yield_time = 0.0
	if walking:
		if sidestep_left > 0.0:
			sidestep_left -= delta
			wish = (wish*0.45+wish.orthogonal()*sidestep_side).normalized()
		wish = avoid(me, wish)
	var goal := wish*speed if walking else Vector2.ZERO
	# Standing still on solid ground (work, a pause, a door fade): nothing to move.
	if not walking and horizontal == Vector2.ZERO and settle_frames == 0 and resting:
		turn(delta, Vector2.ZERO)
		animate(delta, 0.0)
		return
	horizontal = horizontal.move_toward(goal, (5.0 if goal.length() > horizontal.length() else 7.0)*delta)
	var before := position
	glide(delta)
	resting = not walking and horizontal == Vector2.ZERO and position.y >= min_ground_y
	var moved := Vector2(position.x-before.x, position.z-before.z)
	stats.distance += moved.length()
	since_step += moved.length()
	if since_step > 1.0: steps_in_row = 0
	# Never let a slide or a step-up hand the body more than its pace.
	if moved.length() > pace*2.5*delta and not just_placed:
		stats.overspeed += 1
	just_placed = false
	watch_stall(delta, walking and yield_time == 0.0)
	turn(delta, moved/maxf(delta, 0.001))
	animate(delta, moved.length()/maxf(delta, 0.001))

## Kinematic walk along the path: no move_and_slide (a capsule against the island
## trimesh cost ~0.4 ms per shadow per frame). The graph and fit_lanes() keep the
## lane clear of walls and props; a short ray from knee height finds the ground,
## a deck or a stair every few frames, and a step that would end in the water is
## refused (the stall logic then steps aside or turns back).
func glide(delta: float) -> void:
	var step_xz := horizontal*delta
	if step_xz == Vector2.ZERO and ground_clock > 0: return
	var from := position
	position.x += step_xz.x
	position.z += step_xz.y
	ground_clock -= 1
	if ground_clock <= 0 or just_placed or step_xz.length() > 0.2:
		ground_clock = 2 if anim_stride == 1 else 4
		var space := get_world_3d().direct_space_state
		# From chest height: catches a deck or stair up to 1.3 m above the feet, never
		# the eaves and roofs higher up.
		var probe := PhysicsRayQueryParameters3D.create(position+Vector3(0, 1.3, 0), position-Vector3(0, 2.6, 0), GROUND_MASK)
		var hit := space.intersect_ray(probe)
		if not hit.is_empty(): ground_y = hit.position.y
		# Water ahead, or a wall / post / prop at chest height: refuse the step.
		var blocked := hit.is_empty() or ground_y < maxf(min_ground_y, Fishing.water_level(Vector2(position.x, position.z))+0.05)
		if not blocked and not state in ["door", "emerge"]:
			body_probe.transform = Transform3D(Basis.IDENTITY, Vector3(position.x, ground_y+1.0*height_scale, position.z))
			blocked = not space.intersect_shape(body_probe, 1).is_empty()
			if blocked:
				# Already standing in a prop (placed on a node by a post): let it walk out.
				body_probe.transform = Transform3D(Basis.IDENTITY, Vector3(from.x, from.y+1.0*height_scale, from.z))
				blocked = space.intersect_shape(body_probe, 1).is_empty()
		if blocked:
			position = from
			horizontal = Vector2.ZERO
			ground_y = from.y
			return
	var gap := ground_y-position.y
	position.y = ground_y if absf(gap) > 0.5 else position.y+gap*minf(1.0, 18.0*delta)
	if position.y >= min_ground_y:
		safe_position = position
		has_safe_position = true

## Other shadows ahead push this one to its right; villagers (no colliders) push away.
func avoid(me: Vector2, wish: Vector2) -> Vector2:
	var steer := wish
	for other in folk.walkers:
		if other == self or not other.present: continue
		var rel: Vector2 = other.xz()-me
		var d := rel.length()
		if d > 2.2 or d < 0.01: continue
		if wish.dot(rel/d) > 0.2:
			steer += wish.orthogonal()*-1.0*(1.0-d/2.2)*1.3
	for spot in folk.villager_points:
		var rel: Vector2 = me-spot
		var d := rel.length()
		if d < 1.1 and d > 0.01: steer += rel/d*(1.1-d)*2.0
	return steer.normalized()

func watch_stall(delta: float, wants_motion: bool) -> void:
	stall_clock += delta
	if stall_clock < 0.5: return
	var gap := steer_point().distance_to(xz())
	if stall_target != target_node or rejoining:
		stall_gap = INF
		stall_target = target_node
	var progress := stall_gap-gap
	if wants_motion and progress < 0.12 and xz().distance_to(stall_anchor) < 0.6: stall_time += stall_clock
	elif wants_motion and progress < 0.12: stall_time += stall_clock*0.5
	else: stall_time = 0.0
	stall_gap = minf(stall_gap, gap)
	stall_anchor = xz()
	if state in ["door", "emerge"]:
		stall_clock = 0.0
		# A prop in the way of a door step: finish the leg where we are.
		if stall_time >= 2.0:
			stall_time = 0.0
			if state == "door": folk.door_reached(self)
			else:
				position = ground_point(door_point, 0.1)
				just_placed = true
				state = "pause"
				pause_left = 0.3
				folk.emerged(self)
		return
	# Pushed off the path (a bank beside a bridge, a gap between props): head back.
	if state in ["walk", "lead", "travel"] and paths.distance_to_network(xz()) > 1.4:
		off_time += stall_clock
		if off_time > 2.0 and not rejoining:
			rejoining = true
			rejoin_point = paths.closest_point(xz())
			stats.rejoins += 1
		if off_time > 7.0:
			off_time = 0.0
			rejoining = false
			slip()
	else:
		off_time = 0.0
	stall_clock = 0.0
	if stall_time >= 1.5 and stall_time < 2.0:
		sidestep_side = -sidestep_side
		sidestep_left = 1.2
		stats.sidesteps += 1
	elif stall_time >= 4.0 and not reversed_once and state in ["walk", "travel"]:
		reversed_once = true
		var back := at_node
		at_node = target_node
		target_node = back
		stats.reversals += 1
	elif stall_time >= 7.0:
		slip()
		if state == "travel": target_node = travel_route[0] if not travel_route.is_empty() else target_node

## Last resort: melt into the ground and rise again at the node ahead.
func slip() -> void:
	stats.slips += 1
	stall_time = 0.0
	position = ground_point(paths.points[target_node], 0.1)
	velocity = Vector3.ZERO
	horizontal = Vector2.ZERO
	fade = 0.0
	stall_anchor = xz()
	has_safe_position = false
	just_placed = true

func turn(delta: float, motion: Vector2) -> void:
	var yaw := visual.rotation.y
	if pose == "lie": return
	if has_face or greet_left > 0.0 or state in ["talk", "pause"] or (state == "lead" and lead_waiting):
		yaw = face_yaw
	elif motion.length() > 0.25:
		yaw = atan2(motion.x, motion.y)
	visual.rotation.y = lerp_angle(visual.rotation.y, yaw, 1.0-exp(-7.0*delta))

func animate(delta: float, actual_speed: float) -> void:
	if grin_left > 0.0:
		grin_left -= delta
		if grin_left <= 0.0 and is_instance_valid(grin): grin.visible = bool(spec.get("always_grin", false))
	if bubble_left > 0.0:
		bubble_left -= delta
		if bubble_left <= 0.0: bubble.visible = false
	if not is_instance_valid(animator): return
	var walking_now := actual_speed > 0.25
	# Work props come out only while the shadow stands at its work.
	var working := not walking_now and state == "pause" and not task.is_empty()
	if working != (task_shown == task and not task.is_empty()):
		show_task(task if working else "")
		set_pose("sit_ground" if working and task == "write" else "stand")
	if working: animate_task(delta)
	play_clip(WALK if walking_now else IDLE)
	if walking_now:
		# Stride matched to ground speed (locomotion_pose.cycle_for_speed's rule).
		var reach := 0.72*height_scale
		var cycle := clampf(reach*0.72/maxf(0.1, actual_speed*0.5), 0.42, 1.3)
		animator.speed_scale = walk_length/cycle
	else:
		animator.speed_scale = 1.0
	anim_clock += delta
	anim_frame += 1
	if anim_frame % maxi(1, anim_stride) == 0:
		animator.advance(anim_clock)
		anim_clock = 0.0
		apply_bone_pose()
		if is_instance_valid(lantern) and lantern_glow.visible:
			lantern.get_child(0).global_basis = Basis.IDENTITY.scaled(lantern.global_basis.get_scale())
	if walking_now and anim_stride == 1 and folk.player_xz().distance_to(xz()) < 3.5:
		step_clock += delta*actual_speed
		if step_clock > 0.62*height_scale:
			step_clock = 0.0
			folk.footstep(self, actual_speed)

func step_up(delta: float) -> void:
	if steps_in_row >= 2 or not is_on_floor() or not is_on_wall(): return
	var motion := Vector3(velocity.x, 0, velocity.z)*delta
	if motion.length() < 0.001: return
	var lift := Vector3(0, STEP_HEIGHT, 0)
	if test_move(global_transform, lift): return
	var raised := global_transform.translated(lift)
	if test_move(raised, motion*2.0): return
	# Only a real ledge: terrain or a floor right under the new spot, no higher than a step.
	var spot := global_position+lift+motion*2.0
	var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(spot+Vector3.UP*0.05, spot+Vector3.DOWN*(STEP_HEIGHT+0.2), GROUND_MASK))
	if hit.is_empty() or hit.position.y > global_position.y+STEP_HEIGHT+0.02: return
	global_position = Vector3(spot.x, hit.position.y+0.01, spot.z)
	steps_in_row += 1
	since_step = 0.0
	apply_floor_snap()
