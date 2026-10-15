extends RefCounted
## Room build mode (studio.gd keeps only the hook lines): right click on one of your placed
## pieces opens the placed menu (move, turn, paint, put away), the same as in the village.
const PlacedMenu = preload("res://scripts/build/placed_menu.gd")
const PassThrough = preload("res://scripts/build/pass_through.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Fx = preload("res://scripts/fx.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
const BuildRules = preload("res://scripts/build/build_rules.gd")

static func find(studio, id: String) -> Dictionary:
	for obj in studio.data.get("objects",[]):
		if str(obj.id)==id: return obj
	return {}

static func index_of(studio, id: String) -> int:
	var objects: Array=studio.data.get("objects",[])
	for i in objects.size():
		if str(objects[i].id)==id: return i
	return -1

## Right click in the room view (container pixels): the menu of the own piece under the pointer.
static func right_click(studio, at: Vector2) -> void:
	if studio.placement_mode or studio.pending or not studio.visit_host.is_empty() or studio.public_room: return
	if not studio.resting.is_empty() or not is_instance_valid(studio.camera): return
	var id := pick(studio,at)
	if id.is_empty(): return
	var obj := find(studio,id)
	var item: Node3D=studio.placed.get(id)
	if obj.is_empty() or not is_instance_valid(item): return
	var old: Node=studio.view_container.get_node_or_null("PlacedMenu")
	if old: old.free()
	Fx.squash(item,0.05,0.22)
	PlacedMenu.open(studio.view_container,studio.camera,item,str(obj.name),func(action: String): act(studio,id,action),{"walker":studio.hero})

## The placed piece drawn nearest the pointer (rooms have no collision bodies for furniture).
static func pick(studio, at: Vector2) -> String:
	var ratio: Vector2=Vector2(studio.viewport.size)/studio.view_container.size.max(Vector2.ONE)
	var best := ""
	var gap := INF
	for id in studio.placed:
		var item: Node3D=studio.placed[id]
		if not is_instance_valid(item) or not item.visible: continue
		var tall: Vector3=item.get_meta("size",Vector3.ONE)
		var middle: Vector3=item.global_position+Vector3(0,tall.y*0.5,0)
		if studio.camera.is_position_behind(middle): continue
		var d: float=(studio.camera.unproject_position(middle)/ratio).distance_to(at)
		if d<maxf(70.0,tall.y*60.0) and d<gap: gap=d;best=str(id)
	return best

static func act(studio, id: String, action: String) -> void:
	if studio.pending or find(studio,id).is_empty(): return
	match action:
		"move":
			if not await select(studio,id): return
			await studio.begin_place()
		"turn": await turn(studio,id)
		"paint":
			if not await select(studio,id): return
			studio.open_painter()
		"store":
			if not await select(studio,id): return
			var item: Node3D=studio.placed.get(id)
			if is_instance_valid(item):
				var span: Vector3=item.get_meta("size",Vector3.ONE)
				Fx.burst(studio.furniture,item.global_position+Vector3(0,span.y*0.5,0),"dust",10,Color(0,0,0,0),maxf(0.4,span.x*0.4))
				var t := item.create_tween()
				t.tween_property(item,"scale",item.scale*0.05,0.24).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
			await studio.retrieve()

## The piece becomes the bag's selection (its preview loads too), as a click in the bag would.
static func select(studio, id: String) -> bool:
	var index := index_of(studio,id)
	if index<0: return false
	if is_instance_valid(studio.inventory) and index<studio.inventory.item_count: studio.inventory.select(index)
	await studio.select_item(index)
	return str(studio.selected.get("id",""))==id

## 90° more where it stands: it eases round at once and the server confirms (or it turns back).
static func turn(studio, id: String) -> void:
	var obj := find(studio,id)
	var item: Node3D=studio.placed.get(id)
	var before := int(obj.get("rotation",0))
	if is_instance_valid(item):
		var t := item.create_tween()
		t.tween_property(item,"rotation:y",item.rotation.y+PI*0.5,0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	RpgUi.sfx("rotate",-6.0)
	var body := {"version":obj.version,"room":studio.room,"x":float(obj.x),"z":float(obj.z),"rotation":ObjectTransform.wrap_degrees(before+90)}
	for key in ["surface","y","parent","wall"]:
		if obj.get(key)!=null and not (key=="surface" and str(obj[key])=="floor"): body[key]=obj[key]
	studio.pending=true
	var reply: Dictionary=await studio.api.post("/v1/objects/"+id+"/placement",studio.api.mutation(body))
	studio.pending=false
	if not reply.ok:
		if is_instance_valid(item): item.rotation_degrees.y=before
		studio.refuse(str(reply.error))
	elif is_instance_valid(item): Fx.arrive(studio.furniture,item,null,false)
	await studio.refresh()

## Rooms: V turns 물건 통과 on or off (movement_blocked skips placed pieces while it is on).
static func toggle_pass(studio) -> void:
	PassThrough.load_pref()
	PassThrough.on=not PassThrough.on
	PassThrough.save_pref()
	RpgUi.sfx("unlock" if PassThrough.on else "cancel",-8.0)
	if is_instance_valid(studio.hero) and is_instance_valid(studio.furniture):
		Fx.ring(studio.furniture,studio.hero.global_position+Vector3(0,0.06,0),1.1,Color(0.7,0.88,1.0,0.85) if PassThrough.on else Color(1,1,1,0.5),0.7)

# ------------------------------------------------------------------ surfaces (items 70, 74)
# The ghost's surface lives on it as metas: build_surface (floor, top, wall, ceiling), build_y
# (bottom above the floor), build_parent (top), build_wall (wall). Floor pieces keep studio.gd's
# own logic; everything else is placed here. Rooms keep their floor at FLOOR_Y.
const FLOOR_Y := 0.07
const MODES := [["floor","바닥"],["wall","벽"],["ceiling","천장"]]

static func surface(studio) -> String:
	return str(studio.ghost.get_meta("build_surface","floor")) if is_instance_valid(studio.ghost) else "floor"

static func ghost_y(studio) -> float:
	return float(studio.ghost.get_meta("build_y",0.0)) if is_instance_valid(studio.ghost) else 0.0

## Placed pieces off the floor (on another piece, on a wall, from the ceiling) do not block the
## floor: neither the walker nor floor pieces' footprints.
static func off_floor(studio, id: String) -> bool:
	return str(find(studio,id).get("surface","floor"))!="floor"

## The surface choice on the placing panel (바닥 / 벽 / 천장); a piece that cannot go somewhere
## has that button greyed with the reason.
static func surface_row(studio, parent: Control) -> void:
	var row := HBoxContainer.new()
	row.name="SurfaceRow"
	row.add_theme_constant_override("separation",6)
	parent.add_child(row)
	var group := ButtonGroup.new()
	for mode in MODES:
		var b := Button.new()
		b.name="Surface_"+str(mode[0])
		b.text=TranslationServer.translate(str(mode[1]))
		b.toggle_mode=true;b.button_group=group;b.focus_mode=Control.FOCUS_NONE
		b.theme_type_variation="NightButton"
		b.custom_minimum_size=Vector2(72,32)
		b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		var id: String=mode[0]
		b.pressed.connect(func(): choose_mode(studio,id))
		RpgUi.hover_motion(b,1.04)
		row.add_child(b)
	studio.set_meta("surface_row",row)

static func choose_mode(studio, mode: String) -> void:
	if not studio.placement_mode or not is_instance_valid(studio.ghost): return
	studio.ghost.set_meta("build_mode",mode)
	RpgUi.sfx("click",-8.0)
	if not follow(studio,studio.get_meta("build_pointer",Vector2.ZERO)):
		clear_pose(studio)

## A ghost is up: which surfaces this piece may take, and the one it starts on (where it stands now).
static func begin(studio) -> void:
	var ghost: Node3D=studio.ghost
	if not is_instance_valid(ghost): return
	var size: Vector3=ghost.get_meta("size",Vector3.ONE)
	var reasons := {"floor":"","wall":BuildRules.wall_problem(size),"ceiling":BuildRules.ceiling_problem(size,BuildRules.words_for(studio.selected,ghost))}
	var current := str(studio.selected.get("surface","floor")) if str(studio.selected.get("state",""))=="placed" else "floor"
	var mode := "floor" if current=="top" else current
	if not str(reasons.get(mode,"")).is_empty(): mode="floor"
	ghost.set_meta("build_mode",mode)
	ghost.set_meta("build_surface",current if current=="top" or mode!="floor" else "floor")
	ghost.set_meta("build_y",float(studio.selected.get("y",0.0)) if ghost.get_meta("build_surface")!="floor" else 0.0)
	if current=="top" and studio.selected.get("parent")!=null: ghost.set_meta("build_parent",str(studio.selected.parent))
	if current=="wall": ghost.set_meta("build_wall",str(studio.selected.get("wall","back")))
	ghost.position.y=FLOOR_Y+ghost_y(studio)
	var row: Control=studio.get_meta("surface_row") if studio.has_meta("surface_row") else null
	if is_instance_valid(row):
		for entry in MODES:
			var b: Button=row.get_node_or_null("Surface_"+str(entry[0]))
			if not b: continue
			var reason: String=reasons[entry[0]]
			b.disabled=not reason.is_empty()
			b.tooltip_text=reason
			b.set_pressed_no_signal(entry[0]==mode)

static func clear_pose(studio) -> void:
	var ghost: Node3D=studio.ghost
	if not is_instance_valid(ghost): return
	ghost.set_meta("build_surface","floor")
	ghost.set_meta("build_y",0.0)
	if ghost.has_meta("build_parent"): ghost.remove_meta("build_parent")
	ghost.position=Vector3(studio.place_at.x,0.08,studio.place_at.z)

## The ghost follows the pointer on its surface. False for a plain floor spot (studio.gd keeps
## its floor logic then); true when this placed it (on a piece, a wall or the ceiling).
static func follow(studio, pointer: Vector2) -> bool:
	studio.set_meta("build_pointer",pointer)
	var ghost: Node3D=studio.ghost
	if not is_instance_valid(ghost) or not is_instance_valid(studio.camera): return false
	# Container pixels to the 3D view's own (the view may render at another size).
	var view: Vector2=pointer*Vector2(studio.viewport.size)/studio.view_container.size.max(Vector2.ONE)
	var origin: Vector3=studio.camera.project_ray_origin(view)
	var direction: Vector3=studio.camera.project_ray_normal(view)
	if absf(direction.y)<0.001: return false
	var size: Vector3=ghost.get_meta("size",Vector3.ONE)
	var room_size: Vector2=Vector2(studio.room_spec.get("size",Vector2(10,10)))
	var height: float=float(studio.room_spec.get("height",3.4))
	var floor_point: Vector3=origin+direction*((FLOOR_Y-origin.y)/direction.y)
	var mode: String=ghost.get_meta("build_mode","floor")
	var before: Vector3=studio.place_at
	match mode:
		"wall":
			var hit := BuildRules.wall_hit(origin,direction,room_size,height)
			if hit.is_empty(): hit={"wall":BuildRules.nearest_wall(floor_point,room_size),"at":Vector3(floor_point.x,1.2+size.y*0.5,floor_point.z)}
			var pose := BuildRules.wall_pose(hit.wall,hit.at,size,room_size,height)
			set_pose(studio,"wall",Vector3(pose.x,0,pose.z),pose.y)
			ghost.set_meta("build_wall",pose.wall)
			studio.placement_rotation=int(pose.rotation)
		"ceiling":
			var at := Vector3(snappedf(floor_point.x,0.5),0,snappedf(floor_point.z,0.5))
			set_pose(studio,"ceiling",at,maxf(0.0,height-size.y-BuildRules.CEILING_GAP))
		_:
			# On top of a piece under the pointer (its top where the pointer is), else the floor.
			var best := ""
			var best_top := -INF
			var aim := Vector3.ZERO
			var moving := str(studio.selected.get("id",""))
			for id in studio.placed:
				var item: Node3D=studio.placed[id]
				if str(id)==moving or not is_instance_valid(item) or not item.visible: continue
				if str(find(studio,str(id)).get("surface","floor")) in ["wall","ceiling"] or carries(studio,moving,str(id)): continue
				var span: Vector3=item.get_meta("size",Vector3.ONE)
				# Where the pointer ray crosses the height of this piece's top.
				var cross: Vector3=origin+direction*((item.global_position.y+span.y-origin.y)/direction.y)
				if not BuildRules.on_footprint(item,cross,0.0): continue
				var top := BuildRules.top_at(item,cross)
				if top>best_top: best_top=top;best=str(id);aim=cross
			if best.is_empty():
				if str(ghost.get_meta("build_surface","floor"))!="floor": clear_pose(studio)
				return false
			var parent: Node3D=studio.placed[best]
			var snapped := Vector3(snappedf(aim.x,0.25),0,snappedf(aim.z,0.25))
			if BuildRules.on_footprint(parent,snapped,0.05): aim=Vector3(snapped.x,aim.y,snapped.z)
			best_top=maxf(best_top,BuildRules.top_at(parent,aim))
			set_pose(studio,"top",Vector3(aim.x,0,aim.z),best_top-FLOOR_Y)
			ghost.set_meta("build_parent",best)
	if not studio.place_at.is_equal_approx(before): studio.soft_tick("snap",-14.0,0.09)
	return true

static func set_pose(studio, kind: String, at: Vector3, y: float) -> void:
	var ghost: Node3D=studio.ghost
	ghost.set_meta("build_surface",kind)
	ghost.set_meta("build_y",y)
	if kind!="top" and ghost.has_meta("build_parent"): ghost.remove_meta("build_parent")
	studio.place_at=Vector3(at.x,0.08,at.z)
	ghost.position=Vector3(at.x,FLOOR_Y+y,at.z)

## Whether `id` (the piece being placed) carries `other` (directly or higher up).
static func carries(studio, id: String, other: String) -> bool:
	if id.is_empty(): return false
	var obj := find(studio,other)
	for step in 6:
		if obj.is_empty() or str(obj.get("surface","floor"))!="top" or obj.get("parent")==null: return false
		if str(obj.parent)==id: return true
		obj=find(studio,str(obj.parent))
	return false

static func depth_of(studio, id: String) -> int:
	var obj := find(studio,id)
	var depth := 0
	for step in 6:
		if obj.is_empty() or str(obj.get("surface","floor"))!="top" or obj.get("parent")==null: return depth
		depth+=1
		obj=find(studio,str(obj.parent))
	return depth

## Why the ghost's spot is refused off the floor ("" when free). Floor spots use studio.gd's checks.
static func problem(studio, at: Vector3) -> String:
	var ghost: Node3D=studio.ghost
	var kind := surface(studio)
	var size: Vector3=ghost.get_meta("size",Vector3.ONE)
	var y := ghost_y(studio)
	match kind:
		"wall":
			var reason := BuildRules.wall_problem(size)
			if not reason.is_empty(): return reason
			var covered := wall_fixture(studio,at,size,y)
			if not covered.is_empty(): return covered
		"ceiling":
			var reason := BuildRules.ceiling_problem(size,BuildRules.words_for(studio.selected,ghost))
			if not reason.is_empty(): return reason
			var half := ObjectTransform.footprint_half(size,studio.placement_rotation)
			var walls: Vector2=Vector2(studio.room_spec.get("size",Vector2(10,10)))*0.5
			if absf(at.x)+half.x>walls.x-BuildRules.WALL_MARGIN or absf(at.z)+half.y>walls.y-BuildRules.WALL_MARGIN: return TranslationServer.translate("벽에 닿아요. 조금 안쪽으로 옮기거나 돌려 보세요.")
		"top":
			var parent_id := str(ghost.get_meta("build_parent",""))
			var parent: Node3D=studio.placed.get(parent_id)
			if not is_instance_valid(parent): return TranslationServer.translate("받칠 물건을 찾지 못했어요.")
			var reason := BuildRules.stack_problem(size,parent.get_meta("size",Vector3.ONE),depth_of(studio,parent_id)+1)
			if not reason.is_empty(): return reason
			if not BuildRules.on_footprint(parent,Vector3(at.x,0,at.z),0.05): return TranslationServer.translate("아래 물건 위에 올려 주세요.")
	# Other pieces whose box this one would cut into (their height bands meet and footprints overlap).
	var moving := str(studio.selected.get("id",""))
	for id in studio.placed:
		var item: Node3D=studio.placed[id]
		if str(id)==moving or not is_instance_valid(item) or not item.visible: continue
		if str(id)==str(ghost.get_meta("build_parent","")) or carries(studio,moving,str(id)): continue
		var span: Vector3=item.get_meta("size",Vector3.ONE)
		var bottom: float=item.position.y-FLOOR_Y
		if minf(y+size.y,bottom+span.y)-maxf(y,bottom)<=0.02: continue
		if ObjectTransform.footprints_overlap(Vector2(at.x,at.z),Vector2(size.x,size.z),studio.placement_rotation,Vector2(item.position.x,item.position.z),Vector2(span.x,span.z),item.rotation_degrees.y):
			return TranslationServer.translate("다른 가구와 겹쳐요.")
	return ""

## The placement request with the ghost's surface (floor pieces send what they always sent).
static func placement_body(studio, body: Dictionary) -> Dictionary:
	var kind := surface(studio)
	if kind=="floor": return body
	body["surface"]=kind
	body["y"]=snappedf(ghost_y(studio),0.001)
	if kind=="top": body["parent"]=str(studio.ghost.get_meta("build_parent",""))
	if kind=="wall": body["wall"]=str(studio.ghost.get_meta("build_wall","back"))
	return body

## The server's own pose (it snaps walls and sets ceiling heights) becomes the ghost's.
static func adopt_reply(studio, reply: Dictionary) -> void:
	if not is_instance_valid(studio.ghost) or not reply.has("x"): return
	studio.place_at=Vector3(float(reply.x),0.08,float(reply.z))
	studio.placement_rotation=int(reply.get("rotation",studio.placement_rotation))
	studio.ghost.set_meta("build_y",float(reply.get("y",0.0)))

## A wall piece over the room's own windows or wall pieces (clock, shelf, pictures) is refused.
## Windows: interiors.gd windows() gives the wall, the spot along it (u), size and centre height.
static func wall_fixture(studio, at: Vector3, size: Vector3, y: float) -> String:
	var wall := str(studio.ghost.get_meta("build_wall","back"))
	var along: float=at.x if wall=="back" else at.z
	var middle: float=y+size.y*0.5
	for window in studio.room_spec.get("windows",[]):
		if str(window.get("wall",""))!=wall: continue
		if absf(float(window.u)-along)<(float(window.width)+size.x)*0.5+0.12 and absf(float(window.y)-middle)<(float(window.height)+size.y)*0.5+0.08:
			return TranslationServer.translate("창문을 가려요. 옆으로 옮겨 주세요.")
	var half := ObjectTransform.footprint_half(size,studio.placement_rotation)
	for record in studio.decor:
		# The room's own wall pieces, and tall floor pieces standing against the wall (a wardrobe).
		if not (record.get("mounted",false) or record.get("solid",false)) or not is_instance_valid(record.get("node")): continue
		var centre: Vector3=record.center
		var reach: Vector2=record.world_half
		if absf(centre.x-at.x)>=half.x+reach.x or absf(centre.z-at.z)>=half.y+reach.y: continue
		var bottom: float=(record.node as Node3D).global_position.y-FLOOR_Y
		var tall: float=Vector3(record.get("size",Vector3.ONE)).y
		if minf(y+size.y,bottom+tall)-maxf(y,bottom)>0.02: return TranslationServer.translate("벽에 걸린 다른 물건과 겹쳐요.")
	return ""
