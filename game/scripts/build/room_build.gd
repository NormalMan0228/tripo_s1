extends RefCounted
## Room build mode (studio.gd keeps only the hook lines): right click on one of your placed
## pieces opens the placed menu (move, turn, paint, put away), the same as in the village.
const PlacedMenu = preload("res://scripts/build/placed_menu.gd")
const PassThrough = preload("res://scripts/build/pass_through.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Fx = preload("res://scripts/fx.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")

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
		RpgUi.sfx("deny",-6.0)
		studio.message(TranslationServer.translate("여기서는 돌릴 수 없어요 · ")+str(reply.error))
	elif is_instance_valid(item): Fx.arrive(studio.furniture,item,null,false)
	await studio.refresh()

## Rooms: V turns 물건 통과 on or off (movement_blocked skips placed pieces while it is on).
static func toggle_pass(studio) -> void:
	PassThrough.load_pref()
	PassThrough.on=not PassThrough.on
	PassThrough.save_pref()
	RpgUi.sfx("twinkle" if PassThrough.on else "click",-8.0)
	if is_instance_valid(studio.hero) and is_instance_valid(studio.furniture):
		Fx.ring(studio.furniture,studio.hero.global_position+Vector3(0,0.06,0),1.1,Color(0.7,0.88,1.0,0.85) if PassThrough.on else Color(1,1,1,0.5),0.7)
