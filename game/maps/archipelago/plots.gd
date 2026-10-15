extends RefCounted
## Building plots that story code fills per player (MAP 40, story 43 move-ins): an empty lot with
## stakes, a string and a small wooden sign until a resident moves in, then a house. The house is
## NOT part of the island bake: a separate node, hidden until set_plot_built(), so each player's
## village can show it or not. Static, no autoload: town.gd builds the plots (install) and story
## code asks and toggles them.
##
##   Plots.plot_info("danbi_plot") -> {id, center (Vector3 on the ground), center_2d (Vector2 x,z),
##       radius (m), yaw (degrees), door (Vector2: where to stand in front of the house door),
##       door_at (Vector3), room ("danbi_house", interiors.gd), built, sign (the sign's Node3D),
##       sign_label (its Label3D; set .text, or use set_sign_text)}
##   Plots.set_plot_built("danbi_plot", true)   shows the house and its collision, hides the lot
##   Plots.set_sign_text("danbi_plot", "...")  the sign's text (kept when the town is built again)
##   Plots.doors() / Plots.door_for(room)      door entries like town.gd DOORS, built plots only
## The state is per session (static); story code sets it for whichever village is shown.
const LoadPace = preload("res://scripts/load_pace.gd")

## center/door are village x,z. The lot is LOT x LOT metres around the centre (empty ground within
## radius, clear of roads, doors, signposts and the other map points by 3 m or more). door is the
## standing point before the door of the model at this yaw and scale (teal_cottage.glb's door step
## is at local (-3.15, 3.96)); sign is the lot sign's spot in plot-local metres (x right, z front):
## at the front, west of the tree at (-20, 15.2) so its crown never hides the board. No road leads
## here: a path between the town hall and the lamp at (-24, 29) would cut the fountain off from its
## road (tests/field_objects_check.gd); the lot is seen across the grass from the green.
const PLOTS := {
	"danbi_plot":{"center":Vector2(-23.5,9.0),"radius":5.0,"yaw":12.0,"room":"danbi_house","title":"단비네 집",
		"model":"res://maps/archipelago/assets/buildings/teal_cottage.glb","scale":0.9,"tint":Color(1.0,0.84,0.72),
		"door_local":Vector2(-3.15,3.96),"sign_local":Vector2(-1.0,4.9),"sign_text":"곧 새 이웃이 이사 와요"},
}
const LOT := 8.0
const STAKE_HEIGHT := 0.7
const STRING_HEIGHT := 0.5
## The house's walls block like the baked buildings (building_layout.gd: layer 2, no mask).
const BUILDING_LAYER := 2
const NODE_PREFIX := "Plot_"

static var built := {}
static var sign_texts := {}
static var _roots := {}

static func ids() -> Array:
	return PLOTS.keys()

## Plot-local x,z (metres, x right, z toward the front) to village x,z.
static func to_world(id: String, local: Vector2) -> Vector2:
	var spec: Dictionary = PLOTS[id]
	var a := deg_to_rad(float(spec.yaw))
	return Vector2(spec.center)+Vector2(local.x*cos(a)+local.y*sin(a), -local.x*sin(a)+local.y*cos(a))

static func door_point(id: String) -> Vector2:
	var spec: Dictionary = PLOTS[id]
	return to_world(id, Vector2(spec.door_local)*float(spec.scale))

static func is_built(id: String) -> bool:
	return bool(built.get(id, false))

static func plot_info(id: String) -> Dictionary:
	if not PLOTS.has(id): return {}
	var spec: Dictionary = PLOTS[id]
	var root := _root(id)
	var center := Vector2(spec.center)
	var ground: float = float(root.get_meta("ground", 2.3)) if root else 2.3
	var door := door_point(id)
	var info := {"id":id,"center":Vector3(center.x, ground, center.y),"center_2d":center,"radius":float(spec.radius),
		"yaw":float(spec.yaw),"door":door,"door_at":Vector3(door.x, ground, door.y),"room":str(spec.room),"built":is_built(id),
		"sign":null,"sign_label":null}
	if root:
		info.sign = root.get_node_or_null("Lot/Sign")
		info.sign_label = root.get_node_or_null("Lot/Sign/Text")
	return info

## Door entries of the built plots, shaped like town.gd DOORS (id, room, title, at, center).
static func doors() -> Array:
	var out: Array = []
	for id in PLOTS:
		if is_built(id): out.append(_door(id))
	return out

static func door_for(room: String) -> Dictionary:
	for id in PLOTS:
		if str(PLOTS[id].room) == room: return _door(id)
	return {}

static func _door(id: String) -> Dictionary:
	var spec: Dictionary = PLOTS[id]
	return {"id":id,"room":str(spec.room),"title":str(spec.title),"at":door_point(id),"center":Vector2(spec.center),"plot":id}

static func set_sign_text(id: String, text: String) -> void:
	sign_texts[id] = text
	var label := plot_info(id).get("sign_label") as Label3D
	if label: label.text = TranslationServer.translate(text)

## Shows the house (and its walls' collision) and hides the stakes, or the other way round.
## The house model is fetched the first time it is shown (a worker thread, no hitch).
static func set_plot_built(id: String, on: bool) -> void:
	if not PLOTS.has(id): return
	built[id] = on
	var root := _root(id)
	if root == null: return
	_apply(root, id)
	if on and root.get_node_or_null("House/Model") == null: await _add_model(root, id)

static func _root(id: String) -> Node3D:
	var ref: WeakRef = _roots.get(id)
	var node = ref.get_ref() if ref else null
	return node as Node3D if is_instance_valid(node) else null

## Builds every plot under `parent` (town.gd, every time the village is built). `space` finds the ground.
static func install(parent: Node3D, space: PhysicsDirectSpaceState3D) -> void:
	for id in PLOTS:
		var spec: Dictionary = PLOTS[id]
		var root := Node3D.new()
		root.name = NODE_PREFIX+id
		parent.add_child(root)
		_roots[id] = weakref(root)
		var ground := _ground(space, Vector2(spec.center), 2.3)
		root.set_meta("ground", ground)
		root.position = Vector3(float(spec.center.x), 0.0, float(spec.center.y))
		root.rotation.y = deg_to_rad(float(spec.yaw))
		_build_lot(root, id, space)
		_build_house(root, id, space)
		_apply(root, id)
		if is_built(id): await _add_model(root, id)

static func _apply(root: Node3D, id: String) -> void:
	var on := is_built(id)
	var lot := root.get_node_or_null("Lot") as Node3D
	var house := root.get_node_or_null("House") as Node3D
	if lot: lot.visible = not on
	if house: house.visible = on
	var body := root.get_node_or_null("House/Walls") as StaticBody3D
	if body: body.collision_layer = BUILDING_LAYER if on else 0

static func _ground(space: PhysicsDirectSpaceState3D, at: Vector2, fallback: float) -> float:
	if space == null: return fallback
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(at.x, 60, at.y), Vector3(at.x, -20, at.y), 1))
	return float(hit.position.y) if not hit.is_empty() else fallback

## Stakes at the corners and edge middles, a string between them at knee height, and a small
## wooden sign at the front facing the road (south). Two meshes (wood, string) plus the label.
static func _build_lot(root: Node3D, id: String, space: PhysicsDirectSpaceState3D) -> void:
	var spec: Dictionary = PLOTS[id]
	var lot := Node3D.new()
	lot.name = "Lot"
	root.add_child(lot)
	var half := LOT*0.5
	var ring: Array[Vector2] = []
	for p in [Vector2(-1,-1),Vector2(0,-1),Vector2(1,-1),Vector2(1,0),Vector2(1,1),Vector2(0,1),Vector2(-1,1),Vector2(-1,0)]:
		ring.append(p*half)
	var wood := SurfaceTool.new()
	wood.begin(Mesh.PRIMITIVE_TRIANGLES)
	var string := SurfaceTool.new()
	string.begin(Mesh.PRIMITIVE_TRIANGLES)
	var heights: Array[float] = []
	for p in ring:
		var h := _ground(space, to_world(id, p), float(root.get_meta("ground"))) - float(root.get_meta("ground"))
		heights.append(h)
		var stake := BoxMesh.new()
		stake.size = Vector3(0.09, STAKE_HEIGHT+0.15, 0.09)
		wood.append_from(stake, 0, Transform3D(Basis(Vector3.UP, 0.2*p.x), Vector3(p.x, float(root.get_meta("ground"))+h+STAKE_HEIGHT*0.5-0.07, p.y)))
	for i in ring.size():
		var a := ring[i]
		var b := ring[(i+1)%ring.size()]
		var ya := float(root.get_meta("ground"))+heights[i]+STRING_HEIGHT
		var yb := float(root.get_meta("ground"))+heights[(i+1)%ring.size()]+STRING_HEIGHT
		var from := Vector3(a.x, ya, a.y)
		var to := Vector3(b.x, yb, b.y)
		var cord := BoxMesh.new()
		cord.size = Vector3(0.025, 0.025, from.distance_to(to))
		var basis := Basis.looking_at(to-from, Vector3.UP)
		string.append_from(cord, 0, Transform3D(basis, (from+to)*0.5))
	# The sign: a post and a board facing the front (+z), the text on the board.
	var sign_at := Vector2(spec.sign_local)
	var sign_ground := _ground(space, to_world(id, sign_at), float(root.get_meta("ground")))
	var post := BoxMesh.new()
	post.size = Vector3(0.1, 1.2, 0.1)
	wood.append_from(post, 0, Transform3D(Basis.IDENTITY, Vector3(sign_at.x, sign_ground+0.5, sign_at.y)))
	var board := BoxMesh.new()
	board.size = Vector3(1.5, 0.72, 0.06)
	wood.append_from(board, 0, Transform3D(Basis.IDENTITY, Vector3(sign_at.x, sign_ground+1.05, sign_at.y+0.06)))
	var wood_mesh := MeshInstance3D.new()
	wood_mesh.name = "Stakes"
	wood_mesh.mesh = wood.commit()
	var wood_mat := StandardMaterial3D.new()
	wood_mat.albedo_color = Color("a07a52")
	wood_mat.roughness = 0.9
	wood_mesh.material_override = wood_mat
	lot.add_child(wood_mesh)
	var string_mesh := MeshInstance3D.new()
	string_mesh.name = "String"
	string_mesh.mesh = string.commit()
	var string_mat := StandardMaterial3D.new()
	string_mat.albedo_color = Color("f2ead2")
	string_mat.roughness = 1.0
	string_mesh.material_override = string_mat
	string_mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	lot.add_child(string_mesh)
	var sign := Node3D.new()
	sign.name = "Sign"
	sign.position = Vector3(sign_at.x, sign_ground+1.05, sign_at.y+0.11)
	lot.add_child(sign)
	var label := Label3D.new()
	label.name = "Text"
	label.text = TranslationServer.translate(str(sign_texts.get(id, spec.sign_text)))
	label.pixel_size = 0.0045
	label.font_size = 52
	label.outline_size = 0
	label.modulate = Color("4a3524")
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.width = 1.4/label.pixel_size
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.double_sided = false
	sign.add_child(label)

## The house node (hidden until built): its walls' box on the buildings layer; the model is
## added by _add_model the first time the house is shown.
static func _build_house(root: Node3D, id: String, _space: PhysicsDirectSpaceState3D) -> void:
	var spec: Dictionary = PLOTS[id]
	var house := Node3D.new()
	house.name = "House"
	root.add_child(house)
	var s := float(spec.scale)
	var size := Vector3(7.65, 3.2, 7.75)*s*0.9
	var body := StaticBody3D.new()
	body.name = "Walls"
	body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = size
	shape.shape = box
	shape.position = Vector3(0, float(root.get_meta("ground"))+size.y*0.5, 0)
	body.add_child(shape)
	house.add_child(body)

static func _add_model(root: Node3D, id: String) -> void:
	var spec: Dictionary = PLOTS[id]
	var path := str(spec.model)
	var scene: PackedScene
	if LoadPace.covered:
		scene = await LoadPace.fetch(path)
	else:
		ResourceLoader.load_threaded_request(path)
		while ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			await (Engine.get_main_loop() as SceneTree).process_frame
		scene = ResourceLoader.load_threaded_get(path) as PackedScene
	var house := root.get_node_or_null("House") as Node3D
	if scene == null or house == null or house.get_node_or_null("Model"): return
	var model := scene.instantiate() as Node3D
	model.name = "Model"
	model.scale = Vector3.ONE*float(spec.scale)
	model.position.y = float(root.get_meta("ground"))-0.04
	house.add_child(model)
	# Its own warmer colours, so it does not read as the seed shop's twin.
	var tint: Color = spec.tint
	for item in model.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		for i in mesh.mesh.get_surface_count():
			var source := mesh.get_active_material(i) as StandardMaterial3D
			if source == null: continue
			var tinted := source.duplicate() as StandardMaterial3D
			tinted.albedo_color = source.albedo_color*tint
			mesh.set_surface_override_material(i, tinted)
