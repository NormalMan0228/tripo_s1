extends Node3D
## Route guide (길 안내), a village module (main.gd VILLAGE_MODULES). Click a line of
## the objective tracker, a place or a spot on the Tab map, or ask Naru, and the way
## shows itself without words: gold chevrons glow along the roads (shadow_paths.gd,
## the graph the shadow folk walk) and shimmer toward the goal, a soft light pillar
## with a bobbing gem and the place name stands at the goal, the minimap draws the
## route, a flag and a rim arrow, and the tracker line counts the metres down. Within
## ARRIVE metres a sparkle and a chime clear it. The first objective is guided when the
## village opens unless the player turned the guide off. The goal outlives rooms and
## the field (static `kept`). "route_guide" (game_settings.gd) hides the trail and the
## pillar but keeps the minimap flag; reduced motion keeps everything still.
##   guide_to(at: Vector3, title: String, key := "")   stop(by_player := true)
##   active() -> bool   signal arrived(key: String)   Guide.current (the live guide)
## The trail is one MultiMesh redrawn every REFRESH seconds; the shimmer, the fade
## around the walker and the pillar run in shaders, so a frame only moves the gem.
const Paths := preload("res://scripts/shadow_paths.gd")
const Roads := preload("res://scripts/roads.gd")
const Town := preload("res://scripts/town.gd")
const Folk := preload("res://scripts/shadow_folk.gd")
const Farm := preload("res://scripts/farm.gd")
const Forage := preload("res://scripts/forage.gd")
const Daylight := preload("res://scripts/daylight.gd")
const Fx := preload("res://scripts/fx.gd")
const Art := preload("res://scripts/art.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")
const GameSettings := preload("res://scripts/game_settings.gd")

signal arrived(key: String)

## Chevrons: spacing along the route, how far ahead of the walker they reach.
const SPACING := 1.4
const AHEAD := 40.0
const MOTES := 32
const LIFT := 0.13
const ARRIVE := 3.0
const REFRESH := 0.3
## Straight to the goal (off the roads) when it is this close over dry land.
const DIRECT := 14.0
const PILLAR := 9.0
## Objective lines (Korean source; compared after tr, first line only) -> goal kind.
const LINES := [["다 자란 작물 %d칸 수확하기","ripe"],["마른 밭 %d칸에 물 주기","dry"],["풍차 들판 텃밭에 씨앗 심기","farm"],
	["텃밭 작물 돌보기","farm"],["물가를 바라보고 E로 낚시하기","fish"],["바닷가 조개·숲 그늘 버섯 모으기","forage"],
	["돌아갈 탐험이 있어요\n%d일째 · 체력 %d\n하단의 이어하기 또는 돌문 앞 E\n\n마을에서는 생존 시간이 멈춥니다.","gate"]]

const TRAIL_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, shadows_disabled;
uniform vec4 core : source_color = vec4(1.0, 0.8, 0.22, 1.0);
uniform vec4 peak : source_color = vec4(1.0, 0.97, 0.74, 1.0);
uniform vec4 glow : source_color = vec4(1.0, 0.62, 0.12, 1.0);
uniform vec4 rim : source_color = vec4(0.24, 0.12, 0.02, 1.0);
uniform float rim_amount = 0.8;
uniform vec3 walker = vec3(0.0);
uniform float calm = 0.0;
uniform float strength = 1.0;
varying float shine;
varying float fade;
float seg(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	return length(pa - ba * clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0));
}
void vertex() {
	// A bright band runs along the trail toward the goal (custom.x: metres from it).
	shine = calm > 0.5 ? 0.6 : 0.5 + 0.5 * sin(INSTANCE_CUSTOM.x * 0.8 + TIME * 4.0);
	vec3 world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float d = distance(world.xz, walker.xz);
	fade = smoothstep(0.6, 2.2, d) * (1.0 - smoothstep(30.0, 39.0, d));
	VERTEX.xz *= 0.9 + 0.14 * shine;
}
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	// An arrowhead pointing along +UV.y (the way to the goal).
	float d = min(seg(p, vec2(-0.5, -0.42), vec2(0.0, 0.36)), seg(p, vec2(0.5, -0.42), vec2(0.0, 0.36)));
	float body = 1.0 - smoothstep(0.15, 0.2, d);
	float edge = (1.0 - smoothstep(0.2, 0.31, d)) * rim_amount;
	float halo = exp(-d * d * 5.0) * 0.45;
	vec3 lit = mix(core.rgb, peak.rgb, shine * shine);
	vec4 acc = vec4(glow.rgb * halo, halo);
	acc = vec4(rim.rgb * edge, edge) + acc * (1.0 - edge);
	acc = vec4(lit * body, body) + acc * (1.0 - body);
	ALBEDO = acc.rgb / max(acc.a, 0.0001);
	ALPHA = clamp(acc.a * fade * strength * (0.78 + 0.22 * shine), 0.0, 1.0);
}
"""
const PILLAR_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled;
uniform vec4 tint : source_color = vec4(1.0, 0.78, 0.38, 1.0);
uniform float height = 9.0;
uniform float calm = 0.0;
uniform float strength = 1.0;
varying float h;
void vertex() {
	h = VERTEX.y / height + 0.5;
}
void fragment() {
	float t = calm > 0.5 ? 0.0 : TIME;
	float side = 1.0 - abs(dot(NORMAL, VIEW));
	float body = mix(0.22, 1.0, pow(side, 1.6));
	float fall = pow(clamp(1.0 - h, 0.0, 1.0), 1.5) * smoothstep(0.0, 0.05, h);
	float rise = calm > 0.5 ? 0.0 : pow(max(0.0, sin((h * 5.0 - t * 0.7) * 6.2831)), 14.0) * 0.35;
	float breathe = 0.86 + 0.14 * sin(t * 2.1);
	ALBEDO = tint.rgb;
	ALPHA = clamp((body * 0.34 + rise) * fall * breathe * strength, 0.0, 1.0);
}
"""
const RING_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, shadows_disabled;
uniform vec4 tint : source_color = vec4(1.0, 0.86, 0.5, 1.0);
uniform vec4 rim : source_color = vec4(0.3, 0.18, 0.05, 1.0);
uniform float rim_amount = 0.5;
uniform float calm = 0.0;
uniform float strength = 1.0;
void fragment() {
	float r = length(UV * 2.0 - 1.0);
	float ring = 1.0 - smoothstep(0.035, 0.07, abs(r - 0.5));
	float shade = (1.0 - smoothstep(0.07, 0.12, abs(r - 0.5))) * rim_amount;
	float t = calm > 0.5 ? 0.55 : fract(TIME * 0.5);
	float wave = (1.0 - smoothstep(0.025, 0.07, abs(r - mix(0.18, 0.96, t)))) * (1.0 - t) * (calm > 0.5 ? 0.0 : 1.0);
	float pool = (1.0 - smoothstep(0.0, 0.5, r)) * 0.22;
	float a = max(max(ring, wave * 0.85), pool);
	vec4 acc = vec4(rim.rgb * shade, shade);
	acc = vec4(tint.rgb * a, a) + acc * (1.0 - a);
	ALBEDO = acc.rgb / max(acc.a, 0.0001);
	ALPHA = clamp(acc.a * strength, 0.0, 1.0);
}
"""

static var current: Node
## The goal survives rooms and the field: {"at": Vector2, "name": String, "key": String}.
static var kept: Dictionary = {}
## Turned off by the player this session: no automatic goal on the next visit.
static var player_stopped := false
static var kept_session := ""
static var pin: Texture2D

var app: Node
var paths: Paths
var target: Dictionary = {}
## Walker -> goal, recomputed every REFRESH seconds while the walker moves.
var route := PackedVector2Array()
var remaining := 0.0
var goal_cost := PackedFloat32Array()
var goal_next := PackedInt32Array()
var goal_edge: Array = []
var goal_entry := Vector2.ZERO
var last_from := Vector2.INF
var refresh_wait := 0.0
var heights: Dictionary = {}
var trail: MultiMeshInstance3D
## Where the visible chevrons stand (the first trail.multimesh.visible_instance_count).
var spots := PackedVector3Array()
var beacon: Node3D
var gem: Node3D
var plate: Label3D
var trail_material: ShaderMaterial
var pillar_material: ShaderMaterial
var ring_material: ShaderMaterial
var shown := false
## The pieces stay drawn (invisible) for the first moments so their shaders compile
## behind the village's opening fade instead of on the first click.
var warm := 1.5
var clock := 0.0
var beacon_tween: Tween
var signs: Array = []
var sign_glow: Dictionary = {}
## Objective tracker: the label's lines as clickable rows.
var hud_label: Label
var rows_box: VBoxContainer
var rows: Array = []
var rows_text := ""
var rows_key := "-"
var rows_metres := -1
var rows_shown := false
var hud_wait := 0.0
var mini_seen := 0
var auto_wait := 10.0
var auto_done := false
var styles: Dictionary = {}
## The Tab map while it is open (village_life.open_map).
var map_view: Control
var map_list: Control

func setup(main: Node) -> void:
	app = main
	name = "Guide"
	current = self
	paths = Paths.new()
	# No door list: road ends stay on the door steps (the shadow folk's graph pulls
	# them back), so the last stretch to a door or a place is the one tests/
	# village_walk.gd walks from the nearest road.
	paths.build(Roads.ROADS, bridge_lines(), [], Folk.SPURS)
	build_pieces()
	# The arrival and signpost effects draw their textures and synthesize their chime
	# on first use; do it now, behind the village's opening fade, not mid-walk.
	Fx.tex("star")
	Fx.tex("soft")
	if not Fx.streams.has("twinkle"): Fx.streams["twinkle"] = Fx._synth("twinkle")
	# Another login in the same session starts without the last player's goal.
	if kept_session != session():
		kept = {}
		player_stopped = false
	if not kept.is_empty():
		set_target(kept.duplicate(), true)
		auto_done = true

## Before the village world is freed (rooms, the field, a rebuild).
func leave() -> void:
	release_hud()
	if current == self: current = null

func _exit_tree() -> void:
	release_hud()
	if current == self: current = null

static func bridge_lines() -> Array:
	if FileAccess.file_exists(Folk.LAYOUT):
		var manifest = JSON.parse_string(FileAccess.get_file_as_string(Folk.LAYOUT))
		if manifest is Dictionary and manifest.get("bridges") is Array and not manifest.bridges.is_empty():
			var lines: Array = []
			for bridge in manifest.bridges: lines.append([Vector2(bridge.a[0], bridge.a[1]), Vector2(bridge.b[0], bridge.b[1])])
			return lines
	return Folk.BRIDGES

# ------------------------------------------------------------------ api
func guide_to(at: Vector3, title: String, key := "") -> void:
	set_target({"at":Vector2(at.x, at.z), "name":title, "key":key if not key.is_empty() else "spot"}, false)

func stop(by_player := true) -> void:
	if target.is_empty(): return
	if by_player:
		player_stopped = true
		RpgUi.sfx("close", -10.0)
	clear(true)

func active() -> bool:
	return not target.is_empty()

func set_target(goal: Dictionary, quiet: bool) -> void:
	target = goal
	kept = goal.duplicate()
	kept_session = session()
	player_stopped = false
	heights.clear()
	plan()
	last_from = Vector2.INF
	refresh_wait = 0.0
	if is_instance_valid(app) and is_instance_valid(app.get("player")): update_route(walker_at())
	place_beacon()
	plate.text = str(goal.name)
	# Places already wear a nameplate (town.gd); a second one would stack on it.
	plate.visible = true
	for spot in Town.PLACES:
		if Vector2(spot.at).distance_to(goal.at) < 0.6: plate.visible = false
	if beacon_tween and beacon_tween.is_valid(): beacon_tween.kill()
	beacon.scale = Vector3.ONE
	if not quiet:
		RpgUi.sfx("confirm", -8.0)
		if not RpgUi.calm() and is_inside_tree():
			beacon.scale = Vector3(0.2, 0.05, 0.2)
			beacon_tween = beacon.create_tween()
			beacon_tween.tween_property(beacon, "scale", Vector3.ONE, 0.45).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	mark_map(not quiet)

func clear(animate: bool) -> void:
	target = {}
	kept = {}
	route.clear()
	remaining = 0.0
	trail.multimesh.visible_instance_count = 0
	if beacon_tween and beacon_tween.is_valid(): beacon_tween.kill()
	if animate and shown and not RpgUi.calm():
		beacon_tween = beacon.create_tween()
		beacon_tween.tween_property(beacon, "scale", Vector3(0.05, 1.4, 0.05), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
		beacon_tween.tween_callback(func(): beacon.visible = false; beacon.scale = Vector3.ONE)
	else: beacon.visible = false
	trail.visible = false
	shown = false
	push_views()
	mark_map(false)

## The login the kept goal belongs to (rooms and the field keep the same token).
func session() -> String:
	var api = app.get("api") if is_instance_valid(app) else null
	return str(api.get("token")) if is_instance_valid(api) else ""

func walker_at() -> Vector2:
	var body: Node3D = app.get("player")
	return Vector2(body.global_position.x, body.global_position.z)

# ------------------------------------------------------------------ routing
## Cheapest cost from the seeds ({node: cost}) to every node, and the neighbour one
## step closer to the seeds (-1 at a seed). Plain Dijkstra: the graph has ~150 nodes.
func field(seeds: Dictionary) -> Array:
	var n := paths.points.size()
	var cost := PackedFloat32Array()
	cost.resize(n)
	cost.fill(INF)
	var next := PackedInt32Array()
	next.resize(n)
	next.fill(-1)
	var done := PackedByteArray()
	done.resize(n)
	for node in seeds: cost[node] = float(seeds[node])
	for step in n:
		var best := -1
		var low := INF
		for k in n:
			if done[k] == 0 and cost[k] < low:
				low = cost[k]
				best = k
		if best < 0: break
		done[best] = 1
		for other in paths.links[best]:
			var c: float = low+paths.points[best].distance_to(paths.points[other])
			if c < cost[other]:
				cost[other] = c
				next[other] = best
	return [cost, next]

## Costs toward the goal for every node (rebuilt once per goal).
func plan() -> void:
	var goal: Vector2 = target.at
	goal_cost = PackedFloat32Array()
	goal_next = PackedInt32Array()
	goal_edge = paths.nearest_edge(goal)
	if goal_edge.is_empty(): return
	goal_entry = Geometry2D.get_closest_point_to_segment(goal, paths.points[goal_edge[0]], paths.points[goal_edge[1]])
	var seeds := {}
	for node in goal_edge: seeds[node] = goal_entry.distance_to(paths.points[node])
	var result := field(seeds)
	goal_cost = result[0]
	goal_next = result[1]

## Walker -> nearest road -> cheapest roads and bridges -> goal (or straight across
## dry land when the goal is close and the roads go round).
func update_route(from: Vector2) -> void:
	last_from = from
	route.clear()
	route.append(from)
	var goal: Vector2 = target.at
	var via := INF
	var first := -1
	var entry := from
	var edge := paths.nearest_edge(from)
	if not edge.is_empty() and not goal_cost.is_empty():
		entry = Geometry2D.get_closest_point_to_segment(from, paths.points[edge[0]], paths.points[edge[1]])
		if (edge[0] == goal_edge[0] and edge[1] == goal_edge[1]) or (edge[0] == goal_edge[1] and edge[1] == goal_edge[0]):
			via = from.distance_to(entry)+entry.distance_to(goal_entry)
			first = -2
		else:
			for node in edge:
				var c: float = from.distance_to(entry)+entry.distance_to(paths.points[node])+goal_cost[node]
				if c < via:
					via = c
					first = node
		via += goal_entry.distance_to(goal)
	var straight := from.distance_to(goal)
	if first == -1 or (straight < DIRECT and straight <= via+0.5 and dry_line(from, goal)):
		route.append(goal)
	else:
		if entry.distance_to(from) > 0.4: route.append(entry)
		var node := first
		var guard := 0
		while node >= 0 and guard < 512:
			if paths.points[node].distance_to(route[route.size()-1]) > 0.05: route.append(paths.points[node])
			node = goal_next[node]
			guard += 1
		if goal_entry.distance_to(route[route.size()-1]) > 0.3: route.append(goal_entry)
		if goal.distance_to(goal_entry) > 0.3: route.append(goal)
	remaining = 0.0
	for i in route.size()-1: remaining += route[i].distance_to(route[i+1])
	lay_trail()
	push_views()

## True when every metre between a and b is above the sea.
func dry_line(a: Vector2, b: Vector2) -> bool:
	var steps := int(a.distance_to(b)/1.5)
	for i in range(1, steps+1):
		var y := ground_y(a.lerp(b, float(i)/(steps+1)))
		if is_nan(y) or y < Town.SHORE_MIN_Y+0.15: return false
	return true

## Chevrons sit at fixed distances from the goal, so walking on does not slide them;
## only the ones the walker passes or that fall within AHEAD metres change.
func lay_trail() -> void:
	var multi := trail.multimesh
	var count := 0
	var n := route.size()
	var behind := 0.0
	var d := 1.9
	var i := n-2
	while i >= 0 and count < MOTES:
		var a: Vector2 = route[i]
		var b: Vector2 = route[i+1]
		var length := a.distance_to(b)
		if length > 0.01:
			var forward := (b-a)/length
			var basis := Basis(Vector3(forward.y, 0, -forward.x), Vector3.UP, Vector3(forward.x, 0, forward.y))
			while d <= behind+length and count < MOTES:
				var ahead := remaining-d
				if ahead < 0.8:
					i = -1
					break
				if ahead <= AHEAD:
					var p := b.lerp(a, (d-behind)/length)
					var y := ground_y(p)
					if is_nan(y): y = float(app.player.global_position.y) if is_instance_valid(app.get("player")) else 2.3
					spots[count] = Vector3(p.x, y+LIFT, p.y)
					multi.set_instance_transform(count, Transform3D(basis, spots[count]))
					multi.set_instance_custom_data(count, Color(d, 0, 0, 0))
					count += 1
				d += SPACING
		behind += length
		i -= 1
	multi.visible_instance_count = count

## Ground (or bridge and pier deck) height, cached on a half-metre grid; roofs over
## the point are skipped. NAN while the map's colliders are not there yet.
func ground_y(p: Vector2) -> float:
	var key := Vector2i(roundi(p.x*2.0), roundi(p.y*2.0))
	if heights.has(key): return heights[key]
	var y := probe(p)
	if not is_nan(y): heights[key] = y
	return y

func probe(p: Vector2) -> float:
	if not is_inside_tree(): return NAN
	var space := get_world_3d().direct_space_state
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x, 60, p.y), Vector3(p.x, -20, p.y), 1|2))
	if hit.is_empty(): return NAN
	var y: float = hit.position.y
	var body := hit.collider as CollisionObject3D
	if body and body.collision_layer & 2:
		var land := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x, 60, p.y), Vector3(p.x, -20, p.y), 1))
		if not land.is_empty() and land.position.y > Town.SHORE_MIN_Y and y-float(land.position.y) > 2.0: y = land.position.y
	return y

func place_beacon() -> void:
	var at: Vector2 = target.at
	var y := ground_y(at)
	if is_nan(y): y = float(app.player.global_position.y) if is_instance_valid(app) and is_instance_valid(app.get("player")) else 2.3
	beacon.global_position = Vector3(at.x, y, at.y)

## Minimap and Tab map get the route and the goal.
func push_views() -> void:
	if not is_instance_valid(app): return
	var mini = app.get("minimap")
	if is_instance_valid(mini) and mini.has_method("show_guide"):
		mini.show_guide(route, target.at if not target.is_empty() else Vector2.INF)
	if is_instance_valid(map_view) and "route" in map_view:
		map_view.route = route
		map_view.queue_redraw()

# ------------------------------------------------------------------ frame
func _process(delta: float) -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.get("player")): return
	clock += delta
	hud_wait -= delta
	if hud_wait <= 0.0:
		hud_wait = 0.1
		attach_hud()
		sync_rows()
		# A rebuilt HUD gets a fresh minimap: hand it the route at once.
		var mini = app.get("minimap")
		var mini_id: int = mini.get_instance_id() if is_instance_valid(mini) else 0
		if mini_id != mini_seen:
			mini_seen = mini_id
			push_views()
		if not auto_done: auto_guide(0.1)
	var village: bool = app.get("screen") == "village"
	if warm > 0.0:
		warm -= delta
		if target.is_empty():
			# Drawn but see-through around the walker until the shaders are compiled.
			var at: Vector3 = app.player.global_position
			beacon.global_position = at+Vector3(0, -3.0, 0)
			trail.global_position = at+Vector3(0, -3.0, 0)
			beacon.visible = warm > 0.0
			trail.visible = warm > 0.0
			if trail.multimesh.visible_instance_count == 0:
				trail.multimesh.set_instance_transform(0, Transform3D.IDENTITY)
				trail.multimesh.visible_instance_count = 1
			if warm <= 0.0:
				trail.global_position = Vector3.ZERO
				trail.multimesh.visible_instance_count = 0
			return
		# A goal arrived during the warm-up: back to normal service.
		trail.global_position = Vector3.ZERO
		trail.visible = false
		beacon.visible = false
		shown = false
		warm = 0.0
		place_beacon()
		lay_trail()
	if target.is_empty(): return
	var at := walker_at()
	if village and at.distance_to(target.at) < ARRIVE:
		arrive()
		return
	var want: bool = village and GameSettings.show_route_guide()
	if want != shown:
		shown = want
		trail.visible = want
		beacon.visible = want
		if want: lay_trail()
	refresh_wait -= delta
	if refresh_wait <= 0.0:
		refresh_wait = REFRESH
		if at.distance_to(last_from) > 0.2:
			update_route(at)
			place_beacon()
			glow_signs(at)
		tune_light()
	if shown:
		trail_material.set_shader_parameter("walker", app.player.global_position)
		if not RpgUi.calm():
			gem.rotation.y += delta*1.3
			gem.position.y = 2.1+sin(clock*2.2)*0.12

## Darker outlines by day (gold on pale cobbles), pure glow at night.
func tune_light() -> void:
	var daylight = app.get("daylight")
	var night := 0.0
	if is_instance_valid(daylight) and daylight.has_method("current_hour"): night = float(Daylight.sample(daylight.current_hour()).get("night", 0.0))
	var calm := 1.0 if RpgUi.calm() else 0.0
	trail_material.set_shader_parameter("rim_amount", lerpf(0.8, 0.15, night))
	ring_material.set_shader_parameter("rim_amount", lerpf(0.5, 0.1, night))
	pillar_material.set_shader_parameter("strength", lerpf(0.75, 1.0, night))
	for material in [trail_material, pillar_material, ring_material]: material.set_shader_parameter("calm", calm)

func arrive() -> void:
	var key := str(target.get("key", ""))
	var at := beacon.global_position
	if shown:
		Fx.burst(self, at+Vector3(0, 0.9, 0), "sparkle", 22, Color(0,0,0,0), 0.6)
		Fx.ring(self, at+Vector3(0, 0.06, 0), 2.8, Color(1.0, 0.88, 0.55, 0.85), 1.1)
		Fx.glow(self, at+Vector3(0, 1.1, 0), Color("ffd27a"), 2.4, 1.1)
	RpgUi.sfx("confirm", -4.0)
	clear(true)
	arrived.emit(key)

# ------------------------------------------------------------------ goals
## Where an objective line (or a place) leads: {"at", "name", "key"}, or {}.
func resolve(key: String) -> Dictionary:
	var here := walker_at()
	match key:
		"farm":
			var farm := place("farm")
			return {"at":farm.at, "name":tr(farm.title), "key":key}
		"ripe", "dry":
			var best: Vector2 = place("farm").at
			var life = app.get("life")
			if is_instance_valid(life) and life.state is Dictionary and life.state.get("plots") is Array:
				var gap := INF
				var stage := 5 if key == "ripe" else 1
				for plot in life.state.plots:
					if Farm.stage(plot, life.now()) != stage: continue
					var p := Vector2(float(plot.x), float(plot.z))
					if p.distance_to(here) < gap:
						gap = p.distance_to(here)
						best = p
			return {"at":best, "name":tr(place("farm").title), "key":key}
		"fish":
			var costs := walk_costs()
			var best := {}
			var low := INF
			for spot in Town.PLACES:
				if spot.kind != "fish": continue
				var c := cost_to(costs, spot.at)
				if c < low:
					low = c
					best = spot
			return {"at":best.at, "name":tr(best.title), "key":key} if not best.is_empty() else {}
		"forage":
			var life = app.get("life")
			if not is_instance_valid(life) or not is_instance_valid(life.get("forage")): return {}
			var costs := walk_costs()
			var best := {}
			var low := INF
			for spot in life.forage.spots:
				if not spot.ready or not spot.kind in ["shell", "mushroom"]: continue
				var c := cost_to(costs, spot.at)
				if c < low:
					low = c
					best = spot
			return {"at":best.at, "name":tr(Forage.PROMPTS[best.kind]), "key":key} if not best.is_empty() else {}
		"gate":
			return {"at":Town.GATE, "name":tr("캠프 초원 돌문"), "key":key}
	if key.begins_with("place:"):
		var spot := place(key.trim_prefix("place:"))
		if not spot.is_empty(): return {"at":spot.at, "name":tr(spot.title), "key":key}
	return {}

static func place(id: String) -> Dictionary:
	for spot in Town.PLACES:
		if spot.id == id: return spot
	return {}

## Costs from the walker to every node, for choosing the nearest of several spots.
func walk_costs() -> Array:
	var from := walker_at()
	var edge := paths.nearest_edge(from)
	if edge.is_empty(): return []
	var entry := Geometry2D.get_closest_point_to_segment(from, paths.points[edge[0]], paths.points[edge[1]])
	var seeds := {}
	for node in edge: seeds[node] = from.distance_to(entry)+entry.distance_to(paths.points[node])
	return field(seeds)

func cost_to(costs: Array, p: Vector2) -> float:
	if costs.is_empty(): return walker_at().distance_to(p)
	var edge := paths.nearest_edge(p)
	if edge.is_empty(): return INF
	var entry := Geometry2D.get_closest_point_to_segment(p, paths.points[edge[0]], paths.points[edge[1]])
	var low := INF
	for node in edge: low = minf(low, float(costs[0][node])+entry.distance_to(paths.points[node]))
	return low+p.distance_to(entry)

## Same islands as minimap.gd island_name, by field_objects.gd ISLANDS key.
static func island_key(at: Vector2) -> String:
	if at.y > 66: return "lighthouse"
	if at.x < -2 and at.y < -12: return "fields"
	if at.x >= -2 and at.y < 2: return "garden"
	if at.x >= 10: return "camp"
	return "square"

## Passing a signpost, the board that points to the goal's island lights up.
func glow_signs(at: Vector2) -> void:
	if not shown: return
	if signs.is_empty():
		for module in app.get("modules"):
			if is_instance_valid(module) and "objects" in module:
				for entry in module.objects:
					if entry.kind == "signpost": signs.append(entry)
		if signs.is_empty(): signs.append({})
	var island := island_key(target.at)
	for entry in signs:
		if entry.is_empty() or not is_instance_valid(entry.root) or entry.spec.island == island: continue
		if at.distance_to(entry.at) > 7.5 or clock-float(sign_glow.get(entry.id, -99.0)) < 25.0: continue
		sign_glow[entry.id] = clock
		for arm in entry.root.get_children():
			if arm.get_meta("island", "") != island: continue
			var tip: Vector3 = arm.global_transform*Vector3(0, 0, 0.75)
			Fx.glow(self, tip, Color("ffe08a"), 1.2, 1.8)
			Fx.burst(self, tip, "sparkle", 7, Color(0,0,0,0), 0.25)
			Fx.wobble(arm, 0.06, Vector3.RIGHT, 3, 0.6)
			Fx.sound(app, "twinkle", tip, 1.25, -9.0)

## The first unfinished objective is guided once the tracker shows it.
func auto_guide(step: float) -> void:
	auto_wait -= step
	if auto_wait <= 0.0 or player_stopped or not target.is_empty() or app.get("screen") != "village":
		auto_done = auto_wait <= 0.0 or player_stopped or not target.is_empty()
		return
	for i in range(1, rows.size()):
		var row: Dictionary = rows[i]
		if not row.panel.visible or str(row.key).is_empty(): continue
		auto_done = true
		var goal := resolve(row.key)
		if not goal.is_empty() and walker_at().distance_to(goal.at) > 12.0: set_target(goal, true)
		return

static func line_is(line: String, source: String) -> bool:
	var text := TranslationServer.translate(source).split("\n")[0]
	if not "%d" in text: return line == text
	var parts := text.split("%d")
	return line.length() > text.length()-2*(parts.size()-1) and line.begins_with(parts[0]) and line.ends_with(parts[parts.size()-1])

func line_key(line: String) -> String:
	for entry in LINES:
		if line_is(line, entry[0]): return entry[1]
	for spot in Town.PLACES:
		if line == tr(spot.title): return "place:"+str(spot.id)
	return ""

# ------------------------------------------------------------------ tracker rows
## The objective label stays (main.gd writes it every frame) but hides; its lines
## come back as rows: hover lights a goal, a click guides to it or stops it.
func attach_hud() -> void:
	var label = app.get("objective")
	if not is_instance_valid(label) or not label is Label or app.get("screen") != "village": return
	if label == hud_label and is_instance_valid(rows_box): return
	if not label.get_parent() is Container: return
	release_hud()
	hud_label = label
	if styles.is_empty():
		for kind in ["normal", "hover", "on"]:
			var box := StyleBoxFlat.new()
			box.bg_color = {"normal":Color(1, 1, 1, 0), "hover":Color(1.0, 0.9, 0.62, 0.12), "on":Color(1.0, 0.82, 0.4, 0.17)}[kind]
			box.set_corner_radius_all(7)
			box.content_margin_left = 3
			box.content_margin_right = 3
			box.content_margin_top = 1
			box.content_margin_bottom = 1
			if kind == "on":
				box.border_width_left = 2
				box.border_color = Color(1.0, 0.84, 0.45, 0.8)
			styles[kind] = box
	rows_box = VBoxContainer.new()
	rows_box.name = "GuideRows"
	rows_box.add_theme_constant_override("separation", 1)
	rows_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.get_parent().add_child(rows_box)
	label.get_parent().move_child(rows_box, label.get_index()+1)
	label.visible = false
	rows.clear()
	rows_text = "\u0001"
	rows_key = "-"

func release_hud() -> void:
	if is_instance_valid(hud_label): hud_label.visible = true
	if is_instance_valid(rows_box): rows_box.queue_free()
	hud_label = null
	rows_box = null
	rows.clear()

func make_row() -> Dictionary:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", styles.normal)
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 5)
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(line)
	var mark := Control.new()
	mark.custom_minimum_size = Vector2(13, 19)
	mark.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	mark.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.add_child(mark)
	var text := RpgUi.label(line, "", 14, RpgUi.INK, false)
	text.add_theme_constant_override("line_spacing", 4)
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var far := RpgUi.numbers(RpgUi.label(line, "", 13, Color("ffe39a")), 13)
	far.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	far.mouse_filter = Control.MOUSE_FILTER_IGNORE
	far.visible = false
	var close := Button.new()
	close.flat = true
	close.icon = RpgUi.icon_texture("close")
	close.expand_icon = true
	close.custom_minimum_size = Vector2(19, 19)
	close.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	close.focus_mode = Control.FOCUS_NONE
	close.tooltip_text = tr("길 안내 끄기")
	close.visible = false
	RpgUi.hover_motion(close, 1.15)
	line.add_child(close)
	var row := {"panel":panel, "mark":mark, "text":text, "far":far, "close":close, "key":"", "goal":false, "hover":false, "state":""}
	mark.draw.connect(func(): draw_mark(mark, row))
	panel.mouse_entered.connect(func():
		row.hover = true
		style_row(row)
		if not str(row.key).is_empty(): RpgUi.sfx("hover"))
	panel.mouse_exited.connect(func():
		row.hover = false
		style_row(row))
	panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			panel.accept_event()
			on_row(row))
	close.pressed.connect(func(): stop(true))
	rows_box.add_child(panel)
	rows.append(row)
	return row

## Row 0 names a goal no line names (a map pick); then one row per label line.
func sync_rows() -> void:
	if not is_instance_valid(rows_box) or not is_instance_valid(hud_label): return
	var key := str(target.get("key", ""))
	var metres := roundi(remaining) if not target.is_empty() else -1
	var text := hud_label.text
	if text == rows_text and key == rows_key and metres == rows_metres and shown == rows_shown: return
	if text == rows_text and key == rows_key and shown == rows_shown:
		# Walking: only the distance on the guided row counts down.
		rows_metres = metres
		for row in rows:
			if row.panel.visible and row.far.visible: row.far.text = "%d m" % maxi(0, metres)
		return
	if text != rows_text:
		rows_text = text
		if rows.is_empty(): make_row()
		var lines := text.split("\n")
		for i in lines.size():
			var row: Dictionary = rows[i+1] if i+1 < rows.size() else make_row()
			var line: String = lines[i]
			row.goal = line.begins_with("▸ ")
			var body := line.trim_prefix("▸ ")
			row.key = line_key(body) if not body.strip_edges().is_empty() else ""
			row.text.text = body
			row.panel.visible = true
		for i in range(lines.size()+1, rows.size()): rows[i].panel.visible = false
	rows_key = key
	rows_metres = metres
	rows_shown = shown
	var named := false
	for i in range(1, rows.size()):
		if rows[i].panel.visible and not key.is_empty() and rows[i].key == key: named = true
	var head: Dictionary = rows[0]
	head.panel.visible = not target.is_empty() and not named
	head.key = key if head.panel.visible else ""
	head.goal = true
	head.text.text = str(target.get("name", ""))
	for row in rows:
		if row.panel.visible: style_row(row)

func style_row(row: Dictionary) -> void:
	var can := not str(row.key).is_empty()
	var on: bool = can and row.key == str(target.get("key", ""))
	var lit: bool = can and row.hover and not on
	row.panel.add_theme_stylebox_override("panel", styles.on if on else (styles.hover if lit else styles.normal))
	row.text.add_theme_color_override("font_color", Color("ffe39a") if on else (Color("fff3cf") if lit else (RpgUi.INK if row.goal or can else Color(RpgUi.INK, 0.72))))
	row.far.visible = on
	if on: row.far.text = "%d m" % maxi(0, roundi(remaining))
	row.close.visible = on
	row.panel.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND if can else Control.CURSOR_ARROW
	row.panel.tooltip_text = tr("다시 누르면 길 안내를 꺼요") if on else (tr("누르면 길 안내") if can else "")
	var state := "pin" if on else ("lit" if lit else ("arrow" if row.goal else ""))
	if row.state != state:
		row.state = state
		row.mark.queue_redraw()

func draw_mark(mark: Control, row: Dictionary) -> void:
	match str(row.state):
		"pin": mark.draw_texture_rect(pin_texture(), Rect2(-1, 1, 15, 17), false)
		"arrow", "lit":
			var ink := Color("ffe39a") if row.state == "lit" else RpgUi.INK
			mark.draw_colored_polygon(PackedVector2Array([Vector2(3, 5.5), Vector2(10, 10), Vector2(3, 14.5)]), ink)

func on_row(row: Dictionary) -> void:
	var key := str(row.key)
	if key.is_empty(): return
	if key == str(target.get("key", "")):
		stop(true)
		return
	var goal := resolve(key)
	if goal.is_empty():
		RpgUi.sfx("close", -8.0)
		return
	set_target(goal, false)

# ------------------------------------------------------------------ tab map
## village_life.open_map hands over its map and place list: a click on a marker, a
## list row or open ground drops a pin there; the guided row wears a pin.
func attach_map(view: Control, list: Control) -> void:
	map_view = view
	map_list = list
	if view.has_signal("picked") and not view.picked.is_connected(pick_on_map): view.picked.connect(pick_on_map)
	mark_map(false)

func pick_place(id: String) -> void:
	var spot := place(id)
	if not spot.is_empty(): pick_on_map(spot.at, id)

func pick_on_map(at: Vector2, id: String) -> void:
	var goal := {}
	if id == "gate": goal = resolve("gate")
	elif not id.is_empty(): goal = resolve("place:"+id)
	else:
		# Open ground: the spot itself, or the nearest road when it is in the sea.
		var y := ground_y(at)
		if is_nan(y) or y < Town.SHORE_MIN_Y+0.15: at = paths.closest_point(at)
		goal = {"at":at, "name":tr("지도 표시"), "key":"pin"}
	if goal.is_empty(): return
	var same: bool = goal.key == str(target.get("key", "")) and (goal.key != "pin" or Vector2(goal.at).distance_to(target.at) < 4.0)
	if same: stop(true)
	else: set_target(goal, false)

func mark_map(dropped: bool) -> void:
	if is_instance_valid(map_view):
		if "route" in map_view: map_view.route = route
		if dropped and "pin_time" in map_view: map_view.pin_time = Time.get_ticks_msec()*0.001
		map_view.queue_redraw()
	if not is_instance_valid(map_list): return
	var key := str(target.get("key", ""))
	for i in mini(map_list.get_child_count(), Town.PLACES.size()):
		var b := map_list.get_child(i) as Button
		if b == null: continue
		var on: bool = key == "place:"+str(Town.PLACES[i].id)
		b.icon = pin_texture() if on else null
		b.add_theme_constant_override("icon_max_width", 18)
		b.text = "%d  %s" % [i+1, tr(Town.PLACES[i].title)]+("   ·  "+tr("안내 중") if on else "")
		if on: b.add_theme_color_override("font_color", Color("8a4f12"))
		else: b.remove_theme_color_override("font_color")
		b.tooltip_text = tr("다시 누르면 길 안내를 꺼요") if on else tr("누르면 길 안내")
		if on and dropped and not RpgUi.calm():
			b.pivot_offset = b.size*0.5
			var bump := b.create_tween()
			bump.tween_property(b, "scale", Vector2.ONE*1.05, 0.08)
			bump.tween_property(b, "scale", Vector2.ONE, 0.18).set_trans(Tween.TRANS_BACK)

# ------------------------------------------------------------------ pieces
func build_pieces() -> void:
	# Above the road ribbon (roads.gd, also see-through): drawn after it, not under it.
	trail_material = material_for(TRAIL_SHADER, 3)
	pillar_material = material_for(PILLAR_SHADER, 2)
	pillar_material.set_shader_parameter("height", PILLAR)
	ring_material = material_for(RING_SHADER, 3)
	var plane := PlaneMesh.new()
	plane.size = Vector2(0.92, 0.92)
	var multi := MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.use_custom_data = true
	multi.mesh = plane
	multi.instance_count = MOTES
	multi.visible_instance_count = 0
	spots.resize(MOTES)
	trail = MultiMeshInstance3D.new()
	trail.name = "GuideTrail"
	trail.multimesh = multi
	trail.material_override = trail_material
	trail.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	trail.top_level = true
	add_child(trail)
	beacon = Node3D.new()
	beacon.name = "GuideBeacon"
	beacon.top_level = true
	add_child(beacon)
	var tube := CylinderMesh.new()
	tube.top_radius = 0.36
	tube.bottom_radius = 0.6
	tube.height = PILLAR
	tube.radial_segments = 18
	tube.rings = 1
	tube.cap_top = false
	tube.cap_bottom = false
	var pillar := MeshInstance3D.new()
	pillar.mesh = tube
	pillar.position.y = PILLAR*0.5
	pillar.material_override = pillar_material
	pillar.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	beacon.add_child(pillar)
	var disc := PlaneMesh.new()
	disc.size = Vector2(3.0, 3.0)
	var ring := MeshInstance3D.new()
	ring.mesh = disc
	ring.position.y = 0.12
	ring.material_override = ring_material
	ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	beacon.add_child(ring)
	gem = Node3D.new()
	gem.position.y = 2.1
	beacon.add_child(gem)
	var shine := StandardMaterial3D.new()
	shine.albedo_color = Color("ffcf5c")
	shine.emission_enabled = true
	shine.emission = Color("ffb440")
	shine.emission_energy_multiplier = 1.0
	shine.metallic = 0.25
	shine.roughness = 0.3
	# A cut gem pointing down: short crown, long pavilion.
	for half in [[0.3, 0.0, 0.24, 0.15], [0.6, 0.24, 0.0, -0.3]]:
		var point := CylinderMesh.new()
		point.height = half[0]
		point.top_radius = half[1]
		point.bottom_radius = half[2]
		point.radial_segments = 4
		point.rings = 1
		var piece := MeshInstance3D.new()
		piece.mesh = point
		piece.material_override = shine
		piece.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		piece.position.y = half[3]
		gem.add_child(piece)
	plate = Label3D.new()
	plate.name = "GuideName"
	Art.style_nameplate(plate, 20)
	plate.position.y = 3.0
	plate.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	plate.modulate = Color("ffe9b0")
	plate.no_depth_test = true
	plate.render_priority = 6
	beacon.add_child(plate)
	beacon.visible = false
	trail.visible = false

static func material_for(code: String, priority: int) -> ShaderMaterial:
	var shader := Shader.new()
	shader.code = code
	var material := ShaderMaterial.new()
	material.shader = shader
	material.render_priority = priority
	return material

## A small gold map pin (tracker rows, map list), drawn once.
static func pin_texture() -> Texture2D:
	if pin: return pin
	var size := 40
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var ink := Color("4a2c10")
	var gold := Color("ffc94d")
	var light := Color("fff2c4")
	for y in size:
		for x in size:
			var c := Color(0, 0, 0, 0)
			for s in 4:
				var p := Vector2((x+0.25+0.5*(s%2))/size*2.0-1.0, 1.0-(y+0.25+0.5*(s/2))/size*2.0)
				var head := p.distance_to(Vector2(0, 0.3))
				var tail := Geometry2D.is_point_in_polygon(p, PackedVector2Array([Vector2(-0.46, 0.12), Vector2(0.46, 0.12), Vector2(0, -0.92)]))
				var tail_out := Geometry2D.is_point_in_polygon(p, PackedVector2Array([Vector2(-0.6, 0.16), Vector2(0.6, 0.16), Vector2(0, -1.0)]))
				var here := Color(0, 0, 0, 0)
				if head < 0.6 or tail_out: here = ink
				if head < 0.48 or tail: here = gold
				if head < 0.2: here = light
				c += here*0.25
			img.set_pixel(x, y, Color(c.r/maxf(c.a, 0.001), c.g/maxf(c.a, 0.001), c.b/maxf(c.a, 0.001), c.a) if c.a > 0.0 else c)
	img.generate_mipmaps()
	pin = ImageTexture.create_from_image(img)
	return pin
