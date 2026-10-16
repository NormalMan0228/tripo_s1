extends SceneTree
## Windowed shots of the bags (6) from recorded replies (no port): the village bag drawer and the
## expedition bag, artifacts/bag-*.png.
##   godot --path game --script res://tests/bag_shot.gd
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")

func _initialize() -> void:
	call_deferred("run")
	create_timer(150).timeout.connect(func(): quit(2))

func capture(name: String) -> void:
	for i in 6: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/bag-%s.png" % name))
	print("SHOT bag-", name)

func run() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	var objects: Array = fixture["/v1/me"].get("objects", [])
	if not objects.is_empty():
		var names := ["나무 의자", "등불 화분", "조개 램프", "작은 책장", "별빛 러그", "고양이 쿠션", "꽃무늬 찻잔", "돌 화덕"]
		var states := ["inventory", "placed", "inventory", "listed", "inventory", "placed", "inventory", "inventory"]
		for i in names.size():
			var copy: Dictionary = objects[0].duplicate(true)
			copy.id = "%s-%d" % [str(objects[0].id), i]
			copy.name = names[i]
			copy.state = states[i]
			copy.color = ["#f4e3c1", "#e9c46a", "#e07a6f", "#5fa8a0", "#7a9bd9", "#d98477", "#f4e3c1", "#a0a0a0"][i]
			objects.append(copy)
	# Stand-in models for the slot pictures (no server): a coloured chair-ish block per object.
	var thumbs = preload("res://scripts/bag_thumbs.gd")
	thumbs.loader = func(obj: Dictionary) -> Node3D:
		var root3d := Node3D.new()
		var seat := MeshInstance3D.new()
		seat.mesh = BoxMesh.new()
		seat.mesh.size = Vector3(0.6, 0.12, 0.6)
		seat.position.y = 0.45
		var back := MeshInstance3D.new()
		back.mesh = BoxMesh.new()
		back.mesh.size = Vector3(0.6, 0.6, 0.1)
		back.position = Vector3(0, 0.8, -0.25)
		for part in [seat, back]:
			var m := StandardMaterial3D.new()
			m.albedo_color = Color(str(obj.get("color", "#c08050"))) if Color.html_is_valid(str(obj.get("color", ""))) else Color("c08050")
			part.material_override = m
			root3d.add_child(part)
		return root3d
	var app := Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(1.2).timeout
	app.toggle_drawer()
	await create_timer(2.5).timeout
	await capture("village")
	app.toggle_drawer()
	await app.start_run("forest", "standard")
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(1.5).timeout
	app.toggle_drawer()
	await create_timer(0.8).timeout
	await capture("expedition")
	quit(0)
