extends SceneTree
## Picked kinds end to end, no credits: a QA server with the fake Tripo (run with -Rig: TRIPOTHON_FAKE_TRIPO,
## TRIPO_ENABLE_PAID) crafts from the room's window with a kind picked in the "기능" row and words that do
## not name it; each object is quoted with its kind, built, placed in the room and does what the kind does:
## a chair seats the walker, a lamp lights up when clicked, a chest opens its lid.
const Main = preload("res://scripts/main.gd")
const CraftPanel = preload("res://scripts/craft_panel.gd")
var failed := false

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func wait_state(panel: CraftPanel, states: Array, seconds := 60.0) -> Dictionary:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while Time.get_ticks_msec() < deadline:
		if str(panel.job.get("state", "")) in states: return panel.job
		await create_timer(0.25).timeout
	return panel.job

func labels(node: Node) -> String:
	var out := []
	for l in node.find_children("*", "Label", true, false): out.append(l.text)
	return "\n".join(out)

## The crafted object's assembly (asset_assembly.gd) under a placed piece.
func assembly_of(node: Node) -> Node:
	if node == null: return null
	if node.has_method("local_event"): return node
	for child in node.find_children("*", "", true, false):
		if child.has_method("local_event"): return child
	return null

## The brightest glow on the object (0 when nothing glows).
func glow(asm) -> float:
	var most := 0.0
	for id in asm.surfaces:
		for mesh in asm.surfaces[id]:
			for i in mesh.mesh.get_surface_count():
				var mat := mesh.get_surface_override_material(i) as StandardMaterial3D
				if mat and mat.emission_enabled: most = maxf(most, mat.emission_energy_multiplier)
	return most

## How far a part has turned from its design pose, in degrees.
func turned(asm, part: String) -> float:
	var pivot: Node3D = asm.pivots.get(part)
	return pivot.rotation_degrees.length() if pivot != null else 0.0

## Crafts `words` as the picked `kind` (still or moving), confirms the quote and places it in the room.
func craft(studio: Node, words: String, kind: String, moving: bool) -> Node:
	# Placing closes the window: each craft opens it again (on the form).
	await studio.open_craft()
	var panel: CraftPanel = studio.craft
	await create_timer(0.4).timeout
	var again: Array = panel.status.find_children("*", "Button", true, false).filter(func(b) -> bool: return b.text == tr("새로 만들기"))
	if not again.is_empty():
		again[0].pressed.emit()
		await process_frame
	panel.prompt.text = words
	panel.picture_first.button_pressed = false
	panel.surface.select(1)
	panel.kinds_row.buttons[kind].pressed.emit()
	panel.motion.select(1 if moving else 0)
	panel._update_options()
	var body := panel._body()
	expect(body.get("archetype") == kind and body.get("geometry") == "tripo", "%s: '%s' goes out picked as %s" % [kind, words, kind])
	await studio.generate()
	var job := await wait_state(panel, ["awaiting_confirmation", "failed"])
	var name := str(panel.kinds_row.entry(kind).get("names", {}).get("ko", kind))
	expect(str(job.get("state")) == "awaiting_confirmation" and str(job.get("provenance", {}).get("archetype")) == kind and labels(panel.status).contains("기능: " + name),
		"%s: quoted as %s (%s, %s)" % [kind, name, job.get("state"), job.get("error")])
	await studio.confirm_job()
	job = await wait_state(panel, ["ready", "failed"], 120.0)
	expect(str(job.get("state")) == "ready" and str(job.get("provenance", {}).get("behaviour", {}).get("archetype")) == kind,
		"%s: built with the kind's behaviour (%s, %s)" % [kind, job.get("state"), job.get("provenance", {}).get("behaviour")])
	var crafted := str(job.get("object_id", ""))
	await create_timer(0.8).timeout
	await studio.place_crafted(crafted)
	for spot in [Vector3(-2.5, 0, -2.5), Vector3(2.5, 0, -2.5), Vector3(-2.5, 0, 0.5), Vector3(2.5, 0, 0.5), Vector3(0, 0, -2.5), Vector3(0, 0, 1.5)]:
		if studio.placement_problem(spot).is_empty():
			studio.place_at = spot
			break
	await studio.commit_place()
	await create_timer(0.6).timeout
	var asm = assembly_of(studio.placed.get(crafted))
	expect(asm != null, "%s: placed in the room" % kind)
	return asm

func run() -> void:
	var app: Node = Main.new()
	root.add_child(app)
	await create_timer(0.4).timeout
	var server := preload("res://tests/qa_server.gd").url()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
	await app.authenticate(true, server, "kinds_" + str(Time.get_ticks_msec()), "Kinds-check-password-1", "")
	expect(app.screen == "village", "logged in")
	Engine.set_meta("studio_session", {"token": app.api.token, "url": app.api.base_url, "room": "home"})
	var studio: Node = load("res://scenes/studio.tscn").instantiate()
	app.queue_free()
	root.add_child(studio)
	await create_timer(2.5).timeout
	await studio.open_craft()
	var panel: CraftPanel = studio.craft
	await create_timer(0.5).timeout
	expect(panel._tripo() and panel.kinds_row.offered() and panel.kinds_row.buttons.has("seat"), "the room window builds with (fake) Tripo and offers kinds")
	# 80 demo starseeds: two still pieces (20 each) and one moving chest (30).
	var chair = await craft(studio, "버섯 모양 물건", "seat", false)
	if chair != null: expect(str(chair.rest) == "sit", "seat: the walker can sit on it (rest %s)" % chair.rest)
	var lamp = await craft(studio, "작은 나무 상자", "lamp", false)
	if lamp != null:
		var before := glow(lamp)
		lamp.local_event("click")
		await create_timer(1.2).timeout
		var lit := glow(lamp)
		lamp.local_event("click")
		await create_timer(1.2).timeout
		expect(lit > before + 0.2 and glow(lamp) < lit, "lamp: a click lights it and another puts it out (%.2f -> %.2f -> %.2f)" % [before, lit, glow(lamp)])
	var chest = await craft(studio, "둥근 바위", "chest", true)
	if chest != null:
		expect(chest.pivots.has("lid"), "chest: built with a separate lid")
		var shut := turned(chest, "lid")
		chest.local_event("click")
		await create_timer(1.5).timeout
		expect(turned(chest, "lid") > shut + 30.0, "chest: a click opens the lid (%.0f -> %.0f degrees)" % [shut, turned(chest, "lid")])
	print("CRAFT_KINDS_E2E " + ("FAILED" if failed else "OK"))
	studio.queue_free()
	await process_frame
	quit(1 if failed else 0)
