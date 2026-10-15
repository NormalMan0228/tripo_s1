extends RefCounted
## Where a piece may go: the client's mirror of server/build_rules.py, so the ghost shows green or
## red (with the reason) before the server is asked. The server stays the judge.
##
## Surfaces: "floor" (the ground or a room floor), "top" (on another piece: its top under the
## pointer), "wall" (rooms: back, left or right wall, the piece's back to the wall), "ceiling"
## (rooms: hanging, its top just under the ceiling). Heights (y) are the piece's bottom above the
## floor (rooms) or above the ground at its support (village).
const Roads = preload("res://scripts/roads.gd")
const Town = preload("res://scripts/town.gd")
const HousePlots = preload("res://scripts/house_plots.gd")

## Hangs on a wall: thin for its size (server: d <= 0.5 and 2d <= max(w, h)).
const WALL_DEPTH := 0.5
## Hangs from the ceiling: small, and reads as a hanging thing (light, mobile, fan, chime...).
const CEILING_MAX := Vector3(2.0, 1.5, 2.0)
const HANGING_WORDS := ["조명","전등","램프","등불","랜턴","샹들리에","펜던트","모빌","선풍기","실링팬","풍경","행잉","매달","걸이","별",
	"lamp","light","lantern","chandelier","pendant","mobile","fan","chime","hanging"]
## A stack is at most this many pieces high above the floor piece.
const STACK_DEPTH := 3
## Gaps the server keeps: wall pieces stand off the wall, ceiling pieces under the ceiling.
const WALL_GAP := 0.02
const CEILING_GAP := 0.02
const WALL_MARGIN := 0.05

## Village ways kept walkable (item 76): pieces at least this big may not stand on a road.
const BIG_SIDE := 0.9
const BIG_HEIGHT := 1.3
## Nothing at all this close (m) to a building door, nor on a bridge's deck.
const DOOR_CLEAR := 1.8
const BRIDGE_CLEAR := 1.3

## The server's build-mode refusals (server/build_rules.py) in the player's words.
static func server_words() -> Dictionary:
	var t := func(text: String) -> String: return TranslationServer.translate(text)
	return {"not_on_parent":t.call("아래 물건 위에 올려 주세요."),"stack_too_high":t.call("더 높이 쌓을 수 없어요."),
		"too_big_to_stack":t.call("아래 물건보다 커서 올릴 수 없어요."),"stack_cycle":t.call("자기 위에 있는 물건 위로는 올릴 수 없어요."),
		"not_wall_piece":t.call("얇고 납작한 물건만 벽에 걸 수 있어요."),"wall_too_tall":t.call("벽에 걸기에는 너무 높아요. 조금 아래로 내려 주세요."),
		"not_ceiling_piece":t.call("조명·모빌처럼 매다는 물건만 천장에 달 수 있어요."),"surface_not_here":t.call("여기서는 벽이나 천장에 걸 수 없어요."),
		"parent_only_on_top":t.call("아래 물건 위에 올려 주세요."),"wall_required":t.call("걸 벽을 골라 주세요."),
		"outside_room":t.call("벽에서 한 칸 안쪽에 놓아 주세요."),"room_full":t.call("이 방에는 더 놓을 수 없어요. 일부를 가방에 넣어 주세요."),
		"village_full":t.call("마을에는 더 놓을 수 없어요. 일부를 가방에 넣어 주세요."),"door_area_reserved":t.call("출입문 앞은 비워 주세요."),
		"workbench_area_reserved":t.call("고정 작업대와 겹쳐요.")}

static func surface_name(surface: String) -> String:
	return {"floor":TranslationServer.translate("바닥"),"top":TranslationServer.translate("물건 위"),"wall":TranslationServer.translate("벽"),"ceiling":TranslationServer.translate("천장")}.get(surface,surface)

## "" when the piece can hang on a wall, else why not.
static func wall_problem(size: Vector3) -> String:
	if size.z>WALL_DEPTH or size.z*2.0>maxf(size.x,size.y): return TranslationServer.translate("얇고 납작한 물건만 벽에 걸 수 있어요.")
	return ""

## "" when the piece can hang from the ceiling, else why not.
static func ceiling_problem(size: Vector3, words: String) -> String:
	if size.x>CEILING_MAX.x or size.y>CEILING_MAX.y or size.z>CEILING_MAX.z: return TranslationServer.translate("천장에 달기에는 너무 커요.")
	var low := words.to_lower()
	for word in HANGING_WORDS:
		if low.contains(word): return ""
	return TranslationServer.translate("조명·모빌처럼 매다는 물건만 천장에 달 수 있어요.")

## The text the hanging test reads: the object's name and its design's title and category.
static func words_for(obj: Dictionary, model: Node3D = null) -> String:
	var text := str(obj.get("name",""))
	if is_instance_valid(model) and model.get_meta("studio",false) and "manifest" in model and model.manifest is Dictionary:
		var plan: Dictionary=model.manifest.get("plan",{})
		text+=" "+str(plan.get("title",""))+" "+str(plan.get("category",""))
	return text

## "" when `child` may stand on `parent`, else why not.
static func stack_problem(child: Vector3, parent: Vector3, depth: int) -> String:
	if depth>=STACK_DEPTH: return TranslationServer.translate("더 높이 쌓을 수 없어요.")
	if child.x*child.z>parent.x*parent.z+0.0001: return TranslationServer.translate("아래 물건보다 커서 올릴 수 없어요.")
	return ""

## Rooms: the snapped pose of a wall piece whose pointer hit the wall at `hit` (room space).
## Returns {"wall","x","z","y","rotation"}; `wall` is back, left or right.
static func wall_pose(wall: String, hit: Vector3, size: Vector3, room_size: Vector2, height: float) -> Dictionary:
	var half := room_size*0.5
	var y := clampf(snappedf(hit.y-size.y*0.5,0.1),0.0,maxf(0.0,height-WALL_MARGIN-size.y))
	match wall:
		"left":
			return {"wall":"left","x":-half.x+size.z*0.5+WALL_GAP,"z":clampf(snappedf(hit.z,0.25),-half.y+size.x*0.5+WALL_MARGIN,half.y-size.x*0.5-WALL_MARGIN),"y":y,"rotation":90}
		"right":
			return {"wall":"right","x":half.x-size.z*0.5-WALL_GAP,"z":clampf(snappedf(hit.z,0.25),-half.y+size.x*0.5+WALL_MARGIN,half.y-size.x*0.5-WALL_MARGIN),"y":y,"rotation":270}
	return {"wall":"back","x":clampf(snappedf(hit.x,0.25),-half.x+size.x*0.5+WALL_MARGIN,half.x-size.x*0.5-WALL_MARGIN),"z":-half.y+size.z*0.5+WALL_GAP,"y":y,"rotation":0}

## Which wall a camera ray meets first (room space, floor at y=0), or {} when it meets none.
## {"wall","at"}; only the back and side walls (the front one holds the door and is cut away).
static func wall_hit(origin: Vector3, direction: Vector3, room_size: Vector2, height: float) -> Dictionary:
	var half := room_size*0.5
	var best := {}
	var best_t := INF
	for wall in [["back",Vector3(0,0,1),-half.y],["left",Vector3(1,0,0),-half.x],["right",Vector3(1,0,0),half.x]]:
		var normal: Vector3=wall[1]
		var denominator := direction.dot(normal)
		if absf(denominator)<0.0001: continue
		var t: float=(float(wall[2])-origin.dot(normal))/denominator
		if t<=0.0 or t>=best_t: continue
		var at := origin+direction*t
		if at.y<0.0 or at.y>height or absf(at.x)>half.x+0.01 or absf(at.z)>half.y+0.01: continue
		best_t=t
		best={"wall":wall[0],"at":at}
	# The floor in front of the wall comes first: the pointer is on the floor, not the wall.
	if not best.is_empty() and absf(direction.y)>0.0001:
		var floor_t := -origin.y/direction.y
		if floor_t>0.0 and floor_t<best_t: return {}
	return best

## The wall nearest a floor point (pointer on the floor while hanging something on a wall).
static func nearest_wall(at: Vector3, room_size: Vector2) -> String:
	var half := room_size*0.5
	var gaps := {"back":at.z+half.y,"left":at.x+half.x,"right":half.x-at.x}
	var best := "back"
	for wall in gaps:
		if gaps[wall]<gaps[best]: best=wall
	return best

## The top of a piece under a point (world xz): the highest of its fitted collision boxes that
## covers the point, or -INF when none does. Boxes are cached on the piece (CraftCollision).
static func top_at(item: Node3D, world: Vector3) -> float:
	if not is_instance_valid(item): return -INF
	# The map session's fitted shapes answer this themselves (craft_collision.gd top_at, cached).
	var Collision: Script=preload("res://scripts/craft_collision.gd")
	if fitted_tops(Collision):
		var at := item.global_transform.affine_inverse()*world
		var top: float=Collision.call("top_at",item,Vector2(at.x,at.z))
		return top if top==-INF else (item.global_transform*Vector3(at.x,top,at.z)).y
	# Boxes follow the shown shape (they are fitted to the scaled frame): a shape edit refits them.
	var shape_key := str(item.get_meta("shape",{}))
	var boxes: Array
	if item.has_meta("build_boxes") and str(item.get_meta("build_boxes_shape",""))==shape_key: boxes=item.get_meta("build_boxes")
	else:
		boxes=preload("res://scripts/craft_collision.gd").boxes_for(item)
		item.set_meta("build_boxes",boxes)
		item.set_meta("build_boxes_shape",shape_key)
	var local := item.global_transform.affine_inverse()*world
	var best := -INF
	for box: AABB in boxes:
		if local.x>=box.position.x and local.x<=box.end.x and local.z>=box.position.z and local.z<=box.end.z: best=maxf(best,box.end.y)
	if best==-INF:
		# No boxes (an unreadable model): the whole footprint at its full height.
		var span: Vector3=item.get_meta("size",Vector3.ONE)
		if absf(local.x)<=span.x*0.5 and absf(local.z)<=span.z*0.5: best=span.y
	return best if best==-INF else item.global_position.y+best*item.scale.y

static var _fitted := -1
static func fitted_tops(Collision: Script) -> bool:
	if _fitted<0:
		_fitted=0
		for method in Collision.get_script_method_list():
			if str(method.name)=="top_at": _fitted=1
	return _fitted==1

## Whether the point (world xz) lies on the piece's turned footprint, shrunk by `inset`.
static func on_footprint(item: Node3D, world: Vector3, inset := 0.05) -> bool:
	var span: Vector3=item.get_meta("size",Vector3.ONE)
	var local := (world-item.global_position).rotated(Vector3.UP,-item.global_rotation.y)
	return absf(local.x)<=span.x*0.5-inset and absf(local.z)<=span.z*0.5-inset

## Village: "" when this spot keeps the ways open, else why not (item 76). `world` is the map
## point, `size` the piece's box, `degrees` its turn.
static func village_problem(world: Vector3, size: Vector3, degrees: float) -> String:
	var here := Vector2(world.x,world.z)
	var reach := maxf(size.x,size.z)*0.5
	# A plot waiting for a resident's house (house_plots.gd; server plot_reserved).
	if not HousePlots.on_plot(here).is_empty(): return TranslationServer.translate("새 이웃의 집터예요. 다른 곳에 놓아 주세요.")
	for door: Dictionary in Town.DOORS:
		if here.distance_to(door.at)<DOOR_CLEAR+reach*0.6: return TranslationServer.translate("문 앞은 비워 두세요.")
	for line in bridge_lines():
		if Geometry2D.get_closest_point_to_segment(here,line[0],line[1]).distance_to(here)<BRIDGE_CLEAR+reach*0.5: return TranslationServer.translate("다리 위에는 놓을 수 없어요.")
	if maxf(size.x,size.z)>=BIG_SIDE or size.y>=BIG_HEIGHT:
		# A big piece may not stand on the road: its turned footprint's middle and corners stay off it.
		for p in footprint_points(here,size,degrees):
			if Roads.on_road(p): return TranslationServer.translate("큰 물건은 길 위에 놓을 수 없어요. 길가로 옮겨 주세요.")
	return ""

## The footprint's centre, corners and edge midpoints (shrunk a little so a piece may touch the verge).
static func footprint_points(centre: Vector2, size: Vector3, degrees: float) -> Array:
	var half := Vector2(size.x,size.z)*0.5*0.8
	var out: Array=[centre]
	for p in [Vector2(-1,-1),Vector2(1,-1),Vector2(1,1),Vector2(-1,1),Vector2(0,-1),Vector2(1,0),Vector2(0,1),Vector2(-1,0)]:
		out.append(centre+(p*half).rotated(-deg_to_rad(degrees)))
	return out

static var _bridges: Array=[]
static func bridge_lines() -> Array:
	if _bridges.is_empty():
		var lines: Array=preload("res://scripts/guide.gd").bridge_lines()
		_bridges=lines if not lines.is_empty() else [[Vector2.INF,Vector2.INF]]
	return _bridges
