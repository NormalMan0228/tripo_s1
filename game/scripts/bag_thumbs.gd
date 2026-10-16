extends RefCounted
## 3D thumbnails for the village bag's slots (6, village_bag.gd): each object drawn once into a
## 128 px picture in a small world of its own (a SubViewport: an orthographic camera fitted to the
## model's bounds from the inspector's angle, the inspector's light, a clear background), one at a
## time so the bag never hitches. Pictures stay in memory and in user://bag_thumbs/ under the
## object's id and look (main.gd object_key: colour, paint version), so they show at once next time
## and a repaint draws a new one. Without a renderer (headless tests) nothing is drawn or stored.
const SIZE := 128
const FOLDER := "user://bag_thumbs"

static var cache: Dictionary = {}
## Looks that could not be drawn this session (the model did not load): not asked for again.
static var failed: Dictionary = {}
static var queue: Array = []
static var running := false
## Tests hand in their own model maker (obj -> Node3D); the game loads the object (main.gd).
static var loader: Callable

static func key_of(app: Node, obj: Dictionary) -> String:
	return ("%s|%s" % [str(obj.get("id", "")), app.object_key(obj)]).md5_text()

## The picture for `obj` if there is one; otherwise asks for it and calls `done(texture)` later.
static func lookup(app: Node, obj: Dictionary, done: Callable) -> Texture2D:
	if DisplayServer.get_name() == "headless": return null
	var key := key_of(app, obj)
	if cache.has(key): return cache[key]
	if failed.has(key): return null
	var path := "%s/%s.png" % [FOLDER, key]
	if FileAccess.file_exists(path):
		var image := Image.load_from_file(path)
		if image and not image.is_empty():
			cache[key] = ImageTexture.create_from_image(image)
			return cache[key]
	for job in queue:
		if job.key == key:
			job.waiting.append(done)
			return null
	queue.append({"obj":obj.duplicate(true), "key":key, "path":path, "waiting":[done]})
	if not running: _run(app)
	return null

static func _run(app: Node) -> void:
	running = true
	while not queue.is_empty() and is_instance_valid(app) and app.is_inside_tree():
		var job: Dictionary = queue.pop_front()
		var model: Node3D = null
		if loader.is_valid(): model = loader.call(job.obj)
		else: model = await app.load_object(job.obj)
		if not is_instance_valid(app) or not app.is_inside_tree():
			if model: model.queue_free()
			break
		if model == null:
			failed[job.key] = true
			continue
		var texture := await _draw(app, model)
		if texture == null:
			failed[job.key] = true
			continue
		cache[job.key] = texture
		DirAccess.make_dir_recursive_absolute(FOLDER)
		texture.get_image().save_png(job.path)
		for done in job.waiting:
			if done.is_valid(): done.call(texture)
		# One picture a frame or two apart: the bag stays smooth while they come in.
		await app.get_tree().process_frame
	running = false

static func _draw(app: Node, model: Node3D) -> Texture2D:
	var view := SubViewport.new()
	view.size = Vector2i(SIZE, SIZE)
	view.transparent_bg = true
	view.own_world_3d = true
	view.msaa_3d = Viewport.MSAA_4X
	view.render_target_update_mode = SubViewport.UPDATE_DISABLED
	app.add_child(view)
	var stage := Node3D.new()
	view.add_child(stage)
	stage.add_child(model)
	var bounds := _bounds(model)
	var centre := bounds.get_center()
	var reach := maxf(bounds.size.length(), 0.2)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = reach * 0.92
	camera.far = reach * 10.0
	stage.add_child(camera)
	camera.position = centre + Vector3(2, 1.75, 3).normalized() * reach * 3.0
	camera.look_at(centre)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-45, -30, 0)
	light.light_energy = 0.55
	stage.add_child(light)
	var world := WorldEnvironment.new()
	world.environment = Environment.new()
	world.environment.background_mode = Environment.BG_CLEAR_COLOR
	world.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	world.environment.ambient_light_color = Color.WHITE
	world.environment.ambient_light_energy = 0.55
	stage.add_child(world)
	view.render_target_update_mode = SubViewport.UPDATE_ONCE
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var image := view.get_texture().get_image() if is_instance_valid(view) else null
	if is_instance_valid(view): view.queue_free()
	if image == null or image.is_empty(): return null
	return ImageTexture.create_from_image(image)

static func _bounds(root: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for node in root.find_children("*", "VisualInstance3D", true, false) + ([root] if root is VisualInstance3D else []):
		var part := node as VisualInstance3D
		var shape: AABB = part.global_transform * part.get_aabb()
		box = shape if first else box.merge(shape)
		first = false
	return box if not first else AABB(Vector3(-0.5, 0, -0.5), Vector3.ONE)
