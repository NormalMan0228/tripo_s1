extends RefCounted
## Village build mode (main.gd keeps only the hook lines):
## * right click on one of your placed objects: the placed menu (move, turn, paint, put away);
## * putting a piece on top of another one (item 74): the ghost sits on the top under the pointer;
## * the ways kept open (item 76): doors, bridges, and roads for big pieces;
## * the walker's 물건 통과 toggle (pass_through.gd, key V).
const PlacedMenu = preload("res://scripts/build/placed_menu.gd")
const BuildRules = preload("res://scripts/build/build_rules.gd")
const LoadRing = preload("res://scripts/build/load_ring.gd")
const PassThrough = preload("res://scripts/build/pass_through.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Fx = preload("res://scripts/fx.gd")
const Town = preload("res://scripts/town.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
## Crafted objects' collision layer (model_loader.gd add_collision).
const CRAFTED := 16

# ------------------------------------------------------------------ where placed objects stand

## The map point of a placed object: on the ground, or on the piece it stands on (y above the
## ground under the bottom piece of its stack, as the server keeps it).
static func spot(obj: Dictionary, objects: Array) -> Vector3:
	var at := Town.furniture_point(float(obj.x),float(obj.z))
	if str(obj.get("surface","floor"))!="top" or obj.get("parent")==null: return at
	var base := root_of(obj,objects)
	if base.is_empty(): return at
	at.y=Town.furniture_point(float(base.x),float(base.z)).y+float(obj.get("y",0.0))
	return at

## The floor piece at the bottom of an object's stack ({} when its support is not placed).
static func root_of(obj: Dictionary, objects: Array) -> Dictionary:
	var here := obj
	for step in 6:
		if str(here.get("surface","floor"))!="top" or here.get("parent")==null: return here
		var below := {}
		for other in objects:
			if str(other.id)==str(here.parent): below=other
		if below.is_empty() or str(below.get("state","placed"))!="placed": return {}
		here=below
	return {}

static func find(app, id: String) -> Dictionary:
	for obj in app.me.get("objects",[]):
		if str(obj.id)==id: return obj
	return {}

# ------------------------------------------------------------------ the placed menu

## Right click in the village: the menu of the own object under the pointer.
static func right_click(app, at: Vector2) -> void:
	if app.screen!="village" or app.social.visiting() or is_instance_valid(app.preview) or app.busy or app.refreshing: return
	if not app.world_movement_allowed(): return
	var id := pick(app,at)
	if id.is_empty(): return
	var obj := find(app,id)
	var item: Node3D=app.loaded.get(id)
	if obj.is_empty() or not is_instance_valid(item): return
	var old: Node=app.ui.get_node_or_null("PlacedMenu")
	if old: old.free()
	RpgUi.sfx("click",-8.0)
	Fx.squash(item,0.05,0.22)
	PlacedMenu.open(app.ui,app.camera,item,str(obj.name),func(action: String): act(app,id,action),{"walker":app.player})

## The own placed object under the pointer: its collision first, else the nearest one drawn there.
static func pick(app, at: Vector2) -> String:
	var origin: Vector3=app.camera.project_ray_origin(at)
	var hit: Dictionary=app.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(origin,origin+app.camera.project_ray_normal(at)*400,CRAFTED))
	if not hit.is_empty():
		for id in app.loaded:
			var node = app.loaded[id]
			if is_instance_valid(node) and node.is_ancestor_of(hit.collider): return str(id)
	var best := ""
	var gap := 70.0
	for id in app.loaded:
		var node = app.loaded[id]
		if not is_instance_valid(node) or not node.visible: continue
		var tall: Vector3=node.get_meta("size",Vector3.ONE)
		var middle: Vector3=node.global_position+Vector3(0,tall.y*0.5,0)
		if app.camera.is_position_behind(middle): continue
		var d: float=app.camera.unproject_position(middle).distance_to(at)
		if d<maxf(gap,tall.y*40.0) and d<gap*2.0: gap=d;best=str(id)
	return best

static func act(app, id: String, action: String) -> void:
	var obj := find(app,id)
	if obj.is_empty() or app.busy or app.refreshing: return
	match action:
		"move":
			app.selected=obj
			await app.begin_place()
		"turn": await turn(app,obj)
		"paint": await paint(app,obj)
		"store": await store(app,obj)

## 90° more in place: the standing piece eases round at once; the server confirms (or it turns back).
static func turn(app, obj: Dictionary) -> void:
	var item: Node3D=app.loaded.get(str(obj.id))
	var before := int(obj.get("rotation",0))
	var after := ObjectTransform.wrap_degrees(before+90)
	if is_instance_valid(item):
		var t := item.create_tween()
		t.tween_property(item,"rotation:y",item.rotation.y+PI*0.5,0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	RpgUi.sfx("rotate",-6.0)
	app.selected=obj
	if not await post_pose(app,obj,{"rotation":after}):
		if is_instance_valid(item): item.rotation_degrees.y=before
		return
	if is_instance_valid(item): Fx.arrive(app.object_root,item,app,false)
	await app.refresh_inventory()

## The painting workspace for this piece (the bag's own painter, on its preview copy).
static func paint(app, obj: Dictionary) -> void:
	var index := -1
	for i in app.me.objects.size():
		if str(app.me.objects[i].id)==str(obj.id): index=i
	if index<0: return
	if is_instance_valid(app.objects_list) and index<app.objects_list.item_count: app.objects_list.select(index)
	app.select_object(index)
	var ring := LoadRing.start(app.ui)
	# The bag's preview copy loads on its own (inspect_object); the painter works on it.
	for frame in 600:
		if is_instance_valid(app.inspect_model) and str(app.inspect_model.get_meta("inspect_id",""))==str(obj.id): break
		if str(app.selected.get("id",""))!=str(obj.id): break
		await app.get_tree().process_frame
	LoadRing.finish(ring)
	if str(app.selected.get("id",""))!=str(obj.id): return
	app.open_painter()

## Back to the bag: the piece shrinks away with a puff, then the server takes it back (anything
## standing on it comes along to the bag).
static func store(app, obj: Dictionary) -> void:
	var item: Node3D=app.loaded.get(str(obj.id))
	var rest := Vector3.ONE
	if is_instance_valid(item):
		rest=item.scale
		var span: Vector3=item.get_meta("size",Vector3.ONE)
		Fx.burst(app.object_root,item.global_position+Vector3(0,span.y*0.5,0),"dust",10,Color(0,0,0,0),maxf(0.4,span.x*0.4))
		var t := item.create_tween()
		t.tween_property(item,"scale",rest*Vector3(1.08,0.9,1.08),0.08)
		t.tween_property(item,"scale",rest*0.05,0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
	app.selected=obj
	var ok: bool=await app.edit_object({"action":"retrieve"})
	if not ok:
		if is_instance_valid(item): item.scale=rest
		return
	RpgUi.sfx("lift",-6.0)
	app.cancel_preview()
	await app.refresh_inventory()

## Asks the server for a new pose of a placed object, keeping what it does not change (its stand,
## height and support). False on refusal (the reason is shown).
static func post_pose(app, obj: Dictionary, change: Dictionary) -> bool:
	if app.busy: return false
	var body := {"version":obj.version,"room":"village","x":float(obj.x),"z":float(obj.z),"rotation":int(obj.get("rotation",0))}
	if str(obj.get("surface","floor"))=="top" and obj.get("parent")!=null:
		body.merge({"surface":"top","parent":str(obj.parent),"y":float(obj.get("y",0.0))},true)
	body.merge(change,true)
	app.busy=true
	var reply: Dictionary=await app.api.post("/v1/objects/"+str(obj.id)+"/placement",app.api.mutation(body))
	app.busy=false
	return app.check(reply)

# ------------------------------------------------------------------ placing on top (item 74)

## The ghost follows a hit on the top of one of the own placed pieces: it sits there and remembers
## its support. False when the hit is no top to stand on (the caller keeps its ground logic).
static func follow(app, hit: Dictionary) -> bool:
	var preview: Node3D=app.preview
	if hit.is_empty() or not (hit.collider is CollisionObject3D) or not (hit.collider.collision_layer&CRAFTED):
		clear_stack(preview)
		return false
	if hit.normal.y<0.6 or app.social.visiting():
		# A piece's side: the ghost goes to the ground behind it instead of sticking where it was.
		clear_stack(preview)
		ground(app)
		return true
	var id := ""
	for key in app.loaded:
		var node = app.loaded[key]
		if is_instance_valid(node) and node.is_ancestor_of(hit.collider): id=str(key)
	# Not on itself, nor on anything standing on it.
	if id.is_empty() or id==app.preview_moving or carried_by(app,id,app.preview_moving): return true
	var parent: Node3D=app.loaded[id]
	var at: Vector3=hit.position
	var snapped := Vector3(snappedf(at.x,0.25),0,snappedf(at.z,0.25))
	if BuildRules.on_footprint(parent,snapped,0.05): at=Vector3(snapped.x,at.y,snapped.z)
	var top := BuildRules.top_at(parent,at)
	if top==-INF: return true
	at.y=top
	if not preview.position.is_equal_approx(at) and Time.get_ticks_msec()-int(preview.get_meta("snap_at",0))>90:
		preview.set_meta("snap_at",Time.get_ticks_msec())
		RpgUi.sfx("snap",-15.0)
	preview.position=at
	preview.set_meta("ghost_spot",true)
	preview.set_meta("stack_parent",id)
	return true

## A stacked piece picked up to move or turn keeps its support until the pointer takes it elsewhere.
static func resume_stack(app) -> void:
	var obj: Dictionary=app.selected
	if str(obj.get("surface","floor"))=="top" and obj.get("parent")!=null and is_instance_valid(app.loaded.get(str(obj.parent))):
		app.preview.set_meta("stack_parent",str(obj.parent))

static func clear_stack(preview: Node3D) -> void:
	if is_instance_valid(preview) and preview.has_meta("stack_parent"): preview.remove_meta("stack_parent")

## The ghost on the open ground under the pointer, past any crafted piece (as main.gd places it).
static func ground(app) -> void:
	var mouse: Vector2=app.get_viewport().get_mouse_position()
	var origin: Vector3=app.camera.project_ray_origin(mouse)
	var hit: Dictionary=app.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(origin,origin+app.camera.project_ray_normal(mouse)*400,1|2|8))
	if hit.is_empty() or not (hit.collider is CollisionObject3D) or not (hit.collider.collision_layer&1): return
	var local := Town.furniture_local(hit.position).snapped(Vector2(0.5,0.5))
	app.preview.position=Town.furniture_point(local.x,local.y)
	app.preview.set_meta("ghost_spot",true)

static func stacking(app) -> bool:
	return is_instance_valid(app.preview) and app.preview.has_meta("stack_parent")

## Whether `id` stands (directly or higher up) on `below`.
static func carried_by(app, id: String, below: String) -> bool:
	if below.is_empty(): return false
	var obj := find(app,id)
	for step in 6:
		if obj.is_empty() or str(obj.get("surface","floor"))!="top" or obj.get("parent")==null: return false
		if str(obj.parent)==below: return true
		obj=find(app,str(obj.parent))
	return false

## The stack depth under a piece (0 for a floor piece).
static func depth_of(app, id: String) -> int:
	var obj := find(app,id)
	var depth := 0
	for step in 6:
		if obj.is_empty() or str(obj.get("surface","floor"))!="top" or obj.get("parent")==null: return depth
		depth+=1
		obj=find(app,str(obj.parent))
	return depth

## Extra reasons the ghost's spot is refused (main.gd placement_problem asks first).
static func placement_problem(app) -> String:
	var preview: Node3D=app.preview
	var span: Vector3=preview.get_meta("size",Vector3.ONE)
	if stacking(app):
		var parent_id: String=preview.get_meta("stack_parent")
		var parent: Node3D=app.loaded.get(parent_id)
		if not is_instance_valid(parent): return TranslationServer.translate("받칠 물건을 찾지 못했어요.")
		var stack := BuildRules.stack_problem(span,parent.get_meta("size",Vector3.ONE),depth_of(app,parent_id)+1)
		if not stack.is_empty(): return stack
		if not BuildRules.on_footprint(parent,preview.position,0.05): return TranslationServer.translate("아래 물건 위에 올려 주세요.")
		return box_problem(app)
	var ways := BuildRules.village_problem(preview.position,span,float(app.preview_rotation))
	return ways if not ways.is_empty() else box_problem(app)

## The server's own rule (server/build_rules.py): turned footprints that meet and height bands that
## overlap. Fitted collision lets a chair slip between a table's legs; the server's boxes do not.
static func box_problem(app) -> String:
	var preview: Node3D=app.preview
	var span: Vector3=preview.get_meta("size",Vector3.ONE)
	var moving: String=app.preview_moving
	var support: String=str(preview.get_meta("stack_parent","")) if stacking(app) else ""
	var here := Vector2(preview.position.x,preview.position.z)
	var bottom: float=preview.position.y
	for id in app.loaded:
		var item = app.loaded[id]
		if str(id)==moving or str(id)==support or not is_instance_valid(item) or not item.visible: continue
		if carried_by(app,str(id),moving) or carried_by(app,support,str(id)): continue
		var size: Vector3=item.get_meta("size",Vector3.ONE)
		var low: float=item.global_position.y
		if minf(bottom+span.y,low+size.y)-maxf(bottom,low)<=0.02: continue
		if ObjectTransform.footprints_overlap(here,Vector2(span.x,span.z),float(app.preview_rotation),Vector2(item.global_position.x,item.global_position.z),Vector2(size.x,size.z),item.rotation_degrees.y):
			return TranslationServer.translate("다른 물건과 겹쳐요.")
	return ""

## Puts the ghost down on its support (new or moved): one placement step on the server.
static func place_stacked(app) -> void:
	var preview: Node3D=app.preview
	var parent_id: String=preview.get_meta("stack_parent")
	var parent: Node3D=app.loaded.get(parent_id)
	var support := find(app,parent_id)
	if not is_instance_valid(parent) or support.is_empty(): return
	var p := Town.furniture_local(preview.position)
	# Height above the ground under the stack's bottom piece (server: y of the support + its top).
	var base := root_of(support,app.me.objects)
	if base.is_empty(): return
	var ground := Town.furniture_point(float(base.x),float(base.z)).y
	var y := maxf(0.0,preview.position.y-ground)
	var moving: String=app.preview_moving
	var obj: Dictionary=find(app,moving) if not moving.is_empty() else app.selected
	if obj.is_empty(): return
	app.busy=true
	var reply: Dictionary=await app.api.post("/v1/objects/"+str(obj.id)+"/placement",app.api.mutation({"version":obj.version,"room":"village","surface":"top","parent":parent_id,
		"x":p.x,"z":p.y,"y":y,"rotation":int(app.preview_rotation)}))
	app.busy=false
	if not app.check(reply): return
	var key: String=app.object_key(obj)
	var at: Vector3=preview.position
	if not moving.is_empty():
		var standing: Node3D=app.loaded.get(moving)
		if is_instance_valid(standing):
			standing.position=at;standing.rotation_degrees.y=app.preview_rotation;standing.visible=true
			Fx.arrive(app.object_root,standing,app,false)
		app.cancel_preview()
	else:
		app.adopt_preview(str(obj.id),key,at)
		app.cancel_preview()
	Fx.squash(parent,0.05,0.25)
	RpgUi.sfx("place",-6.0)
	await app.refresh_inventory()

# ------------------------------------------------------------------ 물건 통과 (item 76)

static func toggle_pass(app) -> void:
	if not is_instance_valid(app.player): return
	var helper = PassThrough.for_walker(app.player)
	if helper: helper.toggle()

## The collision bodies of a placed piece (left out of the ghost's ray while it is moved).
static func rids(item) -> Array[RID]:
	var out: Array[RID]=[]
	if not (item is Node3D) or not is_instance_valid(item): return out
	for body in item.get_children():
		if body is CollisionObject3D: out.append(body.get_rid())
	return out
