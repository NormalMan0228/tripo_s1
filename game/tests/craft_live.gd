extends SceneTree
## PAID: spends real Tripo credits (one static H3 mesh, about 10) on the server given
## by --server (default the PC server). Runs the player flow end to end: login,
## craft request, quote, confirm, finished object in the bag, placement on a free
## village spot and a check that the server kept it.
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
var failed := false
var app: Node3D

func _initialize() -> void:
	call_deferred("run")
	create_timer(900).timeout.connect(func():
		push_error("Live craft exceeded 900 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func capture(name: String) -> void:
	for i in 6: await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/craft-live-"+name+".png"))

func job_state() -> Dictionary:
	if app.craft_job.is_empty(): return {}
	var response: Dictionary = await app.api.request("/v1/studio/jobs/"+app.craft_job)
	return response.data if response.ok else {}

func run() -> void:
	var server := "http://127.0.0.1:8765"
	var idea := "small wooden mushroom stool"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): server = arg.trim_prefix("--server=")
		if arg.begins_with("--idea="): idea = arg.trim_prefix("--idea=")
	app = Main.new()
	root.add_child(app)
	await create_timer(1.5).timeout
	await app.authenticate(true,server,"crafter_"+str(Time.get_unix_time_from_system()).replace(".","_"),"craft-live-password-1","")
	await create_timer(1.0).timeout
	expect(app.screen=="village","logged in to the village")
	expect(app.me.get("studio_tripo_enabled",false),"server offers Tripo crafting")
	if app.screen!="village" or not app.me.get("studio_tripo_enabled",false):
		quit(1)
		return
	var shards_before: int = int(app.me.shards)
	await app.open_craft()
	await capture("form")
	await app.request_craft(idea)
	expect(not app.craft_job.is_empty(),"craft request accepted")
	var job := {}
	for i in 120:
		job = await job_state()
		if job.get("state","") in ["awaiting_confirmation","failed","cancelled"]: break
		await create_timer(2).timeout
	expect(job.get("state","")=="awaiting_confirmation","design finished and quote shown")
	var quote: Dictionary = job.get("provenance",{})
	print("QUOTE ",JSON.stringify({"tripo_credits":quote.get("estimated_tripo_credits"),"starseeds":quote.get("quoted_game_cost"),"model":quote.get("tripo_model"),"parts":job.get("parts",{}).size()}))
	expect(int(quote.get("estimated_tripo_credits",999))<=10,"cheapest generation (10 Tripo credits or less)")
	app.render_craft(job)
	await capture("quote")
	if job.get("state","")!="awaiting_confirmation" or int(quote.get("estimated_tripo_credits",999))>10:
		quit(1)
		return
	await app.confirm_craft()
	for i in 200:
		job = await job_state()
		if job.is_empty() or job.get("state","") in ["ready","failed","cancelled","unknown"]: break
		await create_timer(3).timeout
	await create_timer(4).timeout
	var finished: Dictionary = app.craft_done
	expect(finished.get("state","")=="ready","Tripo object finished")
	print("BILLING ",JSON.stringify(finished.get("provenance",{})))
	await app.open_craft()
	await capture("ready")
	var object_id: String = finished.get("object_id","")
	expect(app.me.objects.any(func(o): return o.id==object_id and o.state=="inventory"),"new object waits in the bag")
	expect(int(app.me.shards)<shards_before,"starseeds paid for the craft")
	await app.place_crafted(object_id)
	expect(is_instance_valid(app.preview),"placement preview opened")
	# Try free spots around the walker until one is clear.
	var placed := false
	for offset in [Vector2(3,2),Vector2(-3,3),Vector2(4,-2),Vector2(0,4),Vector2(-4,-1),Vector2(5,5)]:
		if not is_instance_valid(app.preview): break
		var spot: Vector2 = Town.furniture_local(app.player.position)+offset
		# The preview follows the mouse every frame, so check and place in the same frame.
		app.preview.position = Town.furniture_point(spot.x,spot.y)
		if not app.placement_problem().is_empty(): continue
		await app.place_preview()
		placed = app.me.objects.any(func(o): return o.id==object_id and o.state=="placed")
		if placed: break
	expect(placed,"crafted object placed on a free village spot")
	await create_timer(1.5).timeout
	app.camera.size = 7.0
	await capture("placed")
	quit(1 if failed else 0)
