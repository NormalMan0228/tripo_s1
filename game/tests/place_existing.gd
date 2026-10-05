extends SceneTree
## Places an account's first bag object on a free village spot, printing why spots fail.
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var user := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--user="): user = arg.trim_prefix("--user=")
	var app = Main.new()
	root.add_child(app)
	await create_timer(1.5).timeout
	await app.authenticate(false,"http://127.0.0.1:8765",user,"craft-live-password-1","")
	await create_timer(2).timeout
	var target := ""
	for obj in app.me.objects:
		if obj.state=="inventory" and obj.get("studio",false): target=obj.id
	print("TARGET ",target," player=",app.player.position)
	await app.place_crafted(target)
	print("PREVIEW ",is_instance_valid(app.preview)," size=",app.preview.get_meta("size",Vector3.ZERO) if is_instance_valid(app.preview) else null)
	for offset in [Vector2(3,2),Vector2(-3,3),Vector2(4,-2),Vector2(0,4),Vector2(-4,-1),Vector2(5,5),Vector2(6,0),Vector2(0,6)]:
		if not is_instance_valid(app.preview): break
		var spot: Vector2 = Town.furniture_local(app.player.position)+offset
		# The preview follows the mouse every frame, so check and place in the same frame.
		app.preview.position = Town.furniture_point(spot.x,spot.y)
		var problem: String = app.placement_problem()
		print("SPOT ",spot," y=",app.preview.position.y," problem=",problem)
		if problem.is_empty():
			await app.place_preview()
			print("PLACED ",app.me.objects.any(func(o): return o.id==target and o.state=="placed"))
			break
	quit()
