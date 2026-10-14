extends SceneTree
## Every object type of the archetype library (server/archetype_library.py) that has an offline
## fixture, crafted on the demo server (proxy shapes, no paid call) and loaded the way any crafted
## object is (Assembly.fetch): each arrives with its parts and its type's behaviour (or its rest), runs
## its program after someone comes near and presses E, moves, and stays healthy (no VM error, finite
## poses). --capture lays them out in a labelled grid and saves artifacts/archetype-gallery.png (run it
## windowed). --part=K/N checks only the K-th of N slices (the demo server crafts 100 a day).
##   godot --path game --script res://tests/archetype_gallery.gd -- --server=URL [--capture] [--part=1/2]
const Assembly = preload("res://scripts/asset_assembly.gd")
const Api = preload("res://scripts/api.gd")
const COLUMNS := 12
const SPACING := Vector2(2.5, 3.1)

var server: String = preload("res://tests/qa_server.gd").url()
var failures: Array[String] = []
var passes := 0
var api: Node
var capture := false
const BATCH := 6

func check(value: bool, label: String) -> void:
	if not value: print("FAIL " + label)
	if value: passes += 1
	else: failures.append(label)

func _initialize() -> void:
	call_deferred("run")

func finish() -> void:
	print("ARCHETYPE_GALLERY ", JSON.stringify({"ok": failures.is_empty(), "passed": passes, "failures": failures}))
	quit(0 if failures.is_empty() else 1)

## A signed-in client with crafts left: a new demo account has 80 starseeds, two moving mesh crafts
## (30 each). One client per craft in flight (an account crafts one thing at a time).
## Sign-ups are limited to 20 a minute per address: a refused one waits and tries again.
func client() -> Node:
	var login: Dictionary = {}
	for attempt in 30:
		login = await api.post("/v1/auth/register", {"username": "arc_" + str(Time.get_ticks_usec() % 1000000000), "password": "Gallery-check-password"})
		if login.ok: break
		await create_timer(3.0).timeout
	if not login.ok: return null
	var other := Api.new()
	root.add_child(other)
	other.base_url = server
	other.token = str(login.data.get("token", ""))
	other.set_meta("left", 2)
	return other

## Fixture crafts of these types, BATCH at a time (the demo server's worker takes a few jobs every two
## seconds): [{type, client, object id or ""}].
func craft_all(types: Array) -> Array:
	var pool := []
	var done := []
	for start in range(0, types.size(), BATCH):
		var batch := []
		pool = pool.filter(func(c): return int(c.get_meta("left")) > 0)
		while pool.size() < BATCH:
			var fresh := await client()
			if fresh == null: return done
			pool.append(fresh)
		for t in types.slice(start, start + BATCH):
			var who: Node = pool[batch.size()]
			who.set_meta("left", int(who.get_meta("left")) - 1)
			var queued: Dictionary = await who.post("/v1/studio/jobs", who.mutation({"prompt": str(t.id), "geometry": "proxy", "designer": "fixture", "motion": "dynamic", "material": "mesh"}))
			if not queued.ok: print("craft refused: ", t.id, " ", queued.get("error", ""))
			batch.append({"type": t, "client": who, "job": str(queued.data.id) if queued.ok else "", "object": ""})
		var deadline := Time.get_ticks_msec() + 60000
		while Time.get_ticks_msec() < deadline and batch.any(func(b): return b.job != "" and b.object == ""):
			await create_timer(0.3).timeout
			for b in batch:
				if b.job == "" or b.object != "": continue
				var job: Dictionary = await b.client.request("/v1/studio/jobs/" + b.job)
				if job.ok and job.data.state == "ready": b.object = str(job.data.object_id)
				elif job.ok and job.data.state == "failed": b.job = ""
		done.append_array(batch)
	return done

## Everything a viewer sees move: part and whole poses, glow and colour.
func pose(item: Node3D) -> String:
	var out := [item.whole_root.transform]
	for id in item.pivots: out.append(item.pivots[id].transform)
	for id in item.surfaces:
		for mesh in item.surfaces[id]:
			for i in mesh.mesh.get_surface_count():
				var mat := mesh.get_surface_override_material(i) as StandardMaterial3D
				if mat: out.append([mat.emission_enabled, snappedf(mat.emission_energy_multiplier, 0.001), mat.albedo_color])
	return var_to_str(out)

## A part glows (a lamp that is lit from the start does not change, but shows).
func lit(item: Node3D) -> bool:
	for id in item.surfaces:
		for mesh in item.surfaces[id]:
			for i in mesh.mesh.get_surface_count():
				var mat := mesh.get_surface_override_material(i) as StandardMaterial3D
				if mat and mat.emission_enabled and mat.emission_energy_multiplier > 0.05: return true
	return false

func finite(item: Node3D) -> bool:
	for node in [item.whole_root] + item.pivots.values():
		var t: Transform3D = node.transform
		for v in [t.origin, t.basis.x, t.basis.y, t.basis.z]:
			if not (is_finite(v.x) and is_finite(v.y) and is_finite(v.z)): return false
	return true

## The stage: in a large SubViewport when capturing (a sharp picture whatever the window), else the root.
func stage(rows: int) -> Node:
	var holder: Node = root
	var view: SubViewport
	if capture:
		view = SubViewport.new()
		view.size = Vector2i(2400, 1500)
		view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		view.msaa_3d = Viewport.MSAA_4X
		root.add_child(view)
		holder = view
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("eee7da")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color(0.82, 0.82, 0.86)
	environment.environment.ambient_light_energy = 0.9
	holder.add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.light_energy = 0.9
	holder.add_child(sun)
	var ground_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(COLUMNS * SPACING.x + 2, rows * SPACING.y + 2)
	ground_mesh.mesh = plane
	var ground := StandardMaterial3D.new()
	ground.albedo_color = Color("ddd3c2")
	ground_mesh.material_override = ground
	ground_mesh.position = Vector3(0, -0.01, (rows - 1) * SPACING.y * 0.5 - 0.3)
	holder.add_child(ground_mesh)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	# Wide enough for every column, tall enough for every row seen from 45° above.
	var aspect := 2400.0 / 1500.0
	camera.size = maxf((COLUMNS * SPACING.x + 0.6) / aspect, rows * SPACING.y * 0.71 + 2.4)
	camera.rotation_degrees = Vector3(-45, 0, 0)
	var middle := Vector3(0, 0.6, (rows - 1) * SPACING.y * 0.5)
	holder.add_child(camera)
	camera.position = middle + Basis.from_euler(Vector3(deg_to_rad(-45), 0, 0)).z * 40.0
	camera.far = 200
	camera.current = true
	return holder

func label(holder: Node, at: Vector3, text: String) -> void:
	var l := Label3D.new()
	l.text = text
	l.font = load("res://assets/fonts/ui_body.tres")
	l.font_size = 64
	l.pixel_size = 0.0046
	l.outline_size = 14
	l.outline_modulate = Color("fffaf0")
	l.modulate = Color("2d2a26")
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.position = at
	holder.add_child(l)

func run() -> void:
	var part := [1, 1]
	for arg in OS.get_cmdline_user_args():
		if arg == "--capture": capture = true
		if arg.begins_with("--part="):
			var bits := arg.trim_prefix("--part=").split("/")
			part = [maxi(1, int(bits[0])), maxi(1, int(bits[1]))]
	api = Api.new()
	root.add_child(api)
	api.base_url = server
	var first := await client()
	check(first != null, "an account on the demo server")
	if first == null: finish(); return
	api.token = first.token
	var listed: Dictionary = await api.request("/v1/studio/library")
	check(listed.ok, "the server lists its object library")
	if not listed.ok: finish(); return
	var types: Array = listed.data.archetypes.filter(func(t): return bool(t.fixture))
	var size := ceili(types.size() / float(part[1]))
	types = types.slice((part[0] - 1) * size, part[0] * size)
	print("library v%d: %d types, %d with fixtures; this run %d" % [int(listed.data.version), listed.data.archetypes.size(), listed.data.archetypes.filter(func(t): return bool(t.fixture)).size(), types.size()])
	var rows := ceili(types.size() / float(COLUMNS))
	var holder := stage(rows)
	var items := []
	var started := Time.get_ticks_msec()
	var crafted := await craft_all(types)
	for i in crafted.size():
		var t: Dictionary = crafted[i].type
		var id: String = crafted[i].object
		check(not id.is_empty(), "%s is crafted" % t.id)
		if id.is_empty(): continue
		var item: Node3D = await Assembly.fetch(crafted[i].client, id)
		check(item != null, "%s loads like a crafted object" % t.id)
		if item == null: continue
		var parts: Array = item.manifest.plan.parts.map(func(p): return str(p.id))
		var moving: bool = (t.behaviours.size() > 0) if parts.size() > 1 else (t.single.size() > 0)
		var interaction: Dictionary = item.manifest.get("interaction", {})
		check(str(item.manifest.plan.category) == str(t.id), "%s keeps its type (%s)" % [t.id, item.manifest.plan.category])
		check(str(interaction.get("mode", "")) == ("presets" if moving else ("original" if str(t.rest) != "" else "")),
			"%s arrives with its type's behaviour (%s)" % [t.id, interaction.get("mode", "none")])
		check(item.rest == str(t.rest), "%s: rest '%s'" % [t.id, item.rest])
		for role in t.roles:
			# Optional roles may be missing from a fixture; a required one that moves may not.
			if role != "whole" and parts.size() > 1 and not role in t.get("optional", []) and not item.pivots.has(role):
				check(false, "%s has its %s part" % [t.id, role])
		var cell := Vector3((i % COLUMNS - (COLUMNS - 1) * 0.5) * SPACING.x, 0, (i / COLUMNS) * SPACING.y)
		item.position = cell
		holder.add_child(item)
		item.set_meta("type", t)
		item.set_meta("moving", moving)
		label(holder, cell + Vector3(0, 0.02, 0.95), "%s
%s" % [t.names.ko, t.id])
		items.append(item)
	print("crafted and loaded %d objects in %.1f s" % [items.size(), (Time.get_ticks_msec() - started) / 1000.0])
	await process_frame
	for item in items:
		item.set_meta("before", pose(item))
		item.local_event("near")
		item.local_event("click")
	var changed := {}
	for wait in [0.3, 0.7, 1.0]:
		await create_timer(wait).timeout
		for item in items:
			if pose(item) != item.get_meta("before") or lit(item): changed[item.get_meta("type").id] = true
	var still := []
	for item in items:
		var t: Dictionary = item.get_meta("type")
		check(item.healthy, "%s runs its program without a VM error" % t.id)
		check(finite(item), "%s keeps finite poses" % t.id)
		if item.get_meta("moving") and not changed.has(t.id): still.append(t.id)
	check(still.is_empty(), "every moving type moved after near + E: still %s" % str(still))
	print("checked %d objects: %d moving, %d resting or still" % [items.size(), items.filter(func(i): return i.get_meta("moving")).size(), items.filter(func(i): return not i.get_meta("moving")).size()])
	if capture:
		await create_timer(1.0).timeout
		await RenderingServer.frame_post_draw
		var image: Image = (holder as SubViewport).get_texture().get_image()
		image.resize(1800, int(1800.0 * image.get_height() / image.get_width()), Image.INTERPOLATE_LANCZOS)
		var path := "res://../artifacts/archetype-gallery.png"
		image.save_png(path)
		print("CAPTURE ", ProjectSettings.globalize_path(path))
	finish()
