extends SceneTree
## How full every interior is: the default pieces per building and floor (interiors.gd layout()),
## printed as one DENSITY line per floor and a DENSITY_TOTAL line. Headless is enough for the counts.
## Windowed with --capture it also saves each building's ground floor from the studio's own camera
## (13:00, a fixed day, so every run frames the same room) as <out>/<tag>-<room>.png.
##   godot --path game -s res://tests/interior_density.gd [-- --capture --tag=after --out=DIR --max=PIECES]
## --max fails when any public floor holds more than that many pieces (the sparse default rooms).
const Interiors = preload("res://scripts/interiors.gd")
const ROOMS := ["home","workshop","01_cafe","02_timber_house","03_teal_cottage","04_windmill","05_observatory","06_orange_cottage","07_greenhouse","11_purple_house","12_blue_house","13_shop","16_blue_cottage","17_lighthouse"]

func _initialize() -> void:
	call_deferred("run")

func arg(name: String, fallback := "") -> String:
	for a in OS.get_cmdline_user_args():
		if a == "--"+name: return "1"
		if a.begins_with("--%s=" % name): return a.get_slice("=",1)
	return fallback

func run() -> void:
	var rooms: Array = ROOMS.duplicate()
	for extra in Interiors.ROOMS:
		if not rooms.has(extra) and not Interiors.PRIVATE.values().has(extra): rooms.append(extra)
	var limit := int(arg("max","0"))
	var failures: Array[String] = []
	var total := 0
	for room in rooms:
		var building: Dictionary = Interiors.spec(room)
		for index in building.floors.size():
			var pieces: Array = building.floors[index].furniture
			total += pieces.size()
			var kinds := {}
			for entry in pieces: kinds[str(entry.kind)] = int(kinds.get(str(entry.kind),0))+1
			print("DENSITY ",JSON.stringify({"room":room,"floor":index,"pieces":pieces.size(),"kinds":kinds}))
			if limit > 0 and building.public and pieces.size() > limit: failures.append("%s/%d has %d pieces" % [room,index,pieces.size()])
	print("DENSITY_TOTAL ",total)
	if arg("capture") == "1":
		var out := arg("out",ProjectSettings.globalize_path("res://").path_join("../artifacts/mapinterior").simplify_path())
		DirAccess.make_dir_recursive_absolute(out)
		var tag := arg("tag","now")
		Engine.set_meta("interior_hour",13.0)
		Engine.set_meta("interior_day",20000)
		for room in rooms:
			Engine.set_meta("studio_session",{"token":"","url":"http://127.0.0.1:9","room":room})
			var app: Control = load("res://scenes/studio.tscn").instantiate()
			root.add_child(app)
			await create_timer(1.6).timeout
			await RenderingServer.frame_post_draw
			var image: Image = root.get_texture().get_image()
			image.convert(Image.FORMAT_RGBA8)
			image.save_png(out.path_join("%s-%s.png" % [tag,room]))
			app.queue_free()
			await process_frame
			await process_frame
		print("DENSITY_CAPTURED ",out)
	for f in failures: print("FAIL ",f)
	quit(1 if not failures.is_empty() else 0)
