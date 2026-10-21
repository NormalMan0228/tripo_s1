extends SubViewport
## The HUD medallion's face: the player's own character (player.gd through avatar_look.gd, the
## same builder as the walker) drawn from the head, lit like the authored portraits
## (tests/render_portraits.gd). It draws once per look and then stops: the body's animation is
## paused and the viewport does not redraw until the look changes again.

const AvatarLook = preload("res://scripts/avatar_look.gd")

signal rendered
var actor: CharacterBody3D
var camera: Camera3D
var stage: Node3D
var look_key := ""
var drawn_key := ""
var generation := 0

func _init() -> void:
	size = Vector2i(160,160)
	transparent_bg = true
	own_world_3d = true
	msaa_3d = Viewport.MSAA_4X
	render_target_update_mode = SubViewport.UPDATE_DISABLED
	stage = Node3D.new()
	add_child(stage)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_CLEAR_COLOR
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color.WHITE
	env.environment.ambient_light_energy = 0.75
	stage.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-25,-35,0)
	light.light_energy = 0.9
	stage.add_child(light)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 0.62
	camera.current = true
	stage.add_child(camera)

## True once the current look has been drawn (the texture is the face, not an empty frame).
func ready_for(look) -> bool:
	return not drawn_key.is_empty() and drawn_key==AvatarLook.signature(look)

func show_look(look, version := -1) -> void:
	var key := AvatarLook.signature(look)
	if key==look_key: return
	look_key = key
	generation += 1
	var mine := generation
	if not is_instance_valid(actor):
		actor = AvatarLook.walker(look, version)
		actor.controls_enabled = false
		actor.visual_only = true
		actor.facing = Vector3(0,0,1)
		stage.add_child(actor)
		actor.visual.rotation.y = PI
	else:
		actor.process_mode = Node.PROCESS_MODE_INHERIT
		AvatarLook.wear(actor, look, version)
	if not is_inside_tree():
		look_key = ""
		return
	# The rig shows its pose after its first physics tick (player.gd reveal_pending).
	for i in 3:
		await get_tree().physics_frame
		if mine!=generation or not is_instance_valid(actor): return
	frame_head()
	for pass_index in 2:
		render_target_update_mode = SubViewport.UPDATE_ONCE
		for i in 2:
			await get_tree().process_frame
			if mine!=generation or not is_instance_valid(actor): return
		# The bounds are the body at rest; the drawn head can sit a little aside (the idle pose).
		# One look at the drawing centres it, and the second pass draws it centred.
		if pass_index==0:
			var shift := head_shift()
			if absf(shift)<camera.size*0.01: break
			camera.position.x += shift
	# Drawn: the body stops animating until the next change.
	actor.process_mode = Node.PROCESS_MODE_DISABLED
	drawn_key = key
	rendered.emit()

## How much of each character the medallion shows, from the top of the head down, as a share of
## its height (the big-headed characters need more to reach the shoulders), tuned to match the
## authored portraits (assets/ui/portrait_*.png).
const SPAN := {}

## Frames head and shoulders like the authored portraits: from just above the head (or the hat)
## down to the shoulders. The body's bounds (as drawn, skinning included) give the head's top and
## middle; a hat or a bag does not move them.
## How far (world units, along x) the drawn head's middle is from the frame's middle, read from
## the top rows of the drawing; 0 when nothing was drawn (no renderer, as in headless runs).
func head_shift() -> float:
	if DisplayServer.get_name()=="headless": return 0.0
	var image := get_texture().get_image()
	if image==null or image.is_empty(): return 0.0
	var top := -1
	for y in image.get_height():
		for x in range(0, image.get_width(), 2):
			if image.get_pixel(x, y).a>0.5:
				top = y
				break
		if top>=0: break
	if top<0: return 0.0
	var left := image.get_width()
	var right := -1
	for y in range(top, mini(image.get_height(), top+int(image.get_height()*0.4))):
		for x in image.get_width():
			if image.get_pixel(x, y).a>0.5:
				left = mini(left, x)
				break
		for x in range(image.get_width()-1, -1, -1):
			if image.get_pixel(x, y).a>0.5:
				right = maxi(right, x)
				break
	if right<left: return 0.0
	return ((left+right)*0.5/image.get_width()-0.5)*camera.size

func frame_head() -> void:
	var body := AABB()
	var hat_top := -INF
	var first := true
	for node in actor.visual.find_children("*","MeshInstance3D",true,false):
		if not node.mesh or "/Backpack" in str(node.get_path()): continue
		var box: AABB = node.global_transform*node.get_aabb()
		if "Headwear_" in str(node.get_path()):
			hat_top = maxf(hat_top, box.end.y)
			continue
		body = box if first else body.merge(box)
		first = false
	if first: return
	var span: float = SPAN.get(str(actor.avatar.get("character","f1")), 0.32)
	var top := maxf(body.end.y, hat_top)+body.size.y*0.02
	var bottom := body.end.y-body.size.y*span
	var middle := Vector3(body.get_center().x, (top+bottom)*0.5, 0)
	camera.size = top-bottom
	camera.position = middle+Vector3(0,0,2)
	camera.look_at(middle)
