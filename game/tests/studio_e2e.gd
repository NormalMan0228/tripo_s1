extends SceneTree
## Actual Codex design -> server VM/DB -> Godot placement, paint, API and reload.
var failures: Array[String]=[]
var app: Control
func check(ok: bool,text: String) -> void:
	print(("PASS " if ok else "FAIL ")+text)
	if not ok:failures.append(text)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var credentials := {"username":"studioqa_"+str(Time.get_ticks_usec()),"password":"Local-studio-qa-password"}
	var login: Dictionary=await api.post("/v1/auth/register",credentials)
	check(login.ok,"new independent account")
	if not login.ok:quit(1);return
	api.token=login.data.token
	Engine.set_meta("studio_session",{"token":api.token,"url":api.base_url,"room":"home"})
	app=load("res://scenes/studio.tscn").instantiate();root.add_child(app)
	await create_timer(2).timeout
	app.designer.select(1);app.geometry.select(0);app.motion.select(1)
	app.prompt.text="Make a cozy two-part music box: body and hinged lid. Clicking smoothly opens the lid to -95 degrees around X and clicks again to close. Include a named numeric API set_open(x) that clamps x to 0..1, stores the desired open amount and returns it. Lid rear pivot is z=-0.5. Keep a rounded honey-wood and sage appearance."
	await app.generate()
	check(not app.job_id.is_empty(),"game queued actual local LLM design")
	var deadline := Time.get_ticks_msec()+180000
	while not app.job_id.is_empty() and Time.get_ticks_msec()<deadline:
		await create_timer(1).timeout;await app.poll_job()
	await app.refresh()
	check(app.data.objects.filter(func(o):return bool(o.studio)).size()==1,"one generated private object published")
	if app.data.objects.is_empty():quit(1);return
	await app.select_item(0)
	var id: String=app.selected.id
	check(app.inspected.manifest.provenance.provider=="codex_subscription_development","actual Codex provenance")
	check(app.inspected.manifest.program.functions.has("set_open"),"new named API registered")
	app.place_at=Vector3(-2,0.08,-1);app.placement_rotation=90
	await app.commit_place()
	check(app.placed.has(id),"placed inside own home")
	check(app.selected.rotation==90,"placement rotation saved")
	await app.paint("#a8bcad")
	check(not app.inspected.colors.is_empty(),"paint persisted through server")
	var version: int=app.inspected.runtime_version
	var invoked: Dictionary=await api.post("/v1/objects/"+id+"/invoke",api.mutation({"version":version,"function":"set_open","args":[1]}))
	check(invoked.ok,"generated API called with ownership and version")
	if invoked.ok:
		app.inspected.accept_event(invoked.data);app.placed[id].accept_event(invoked.data)
		await create_timer(2).timeout
		check(absf(app.inspected.pivots.lid.rotation_degrees.x)>80,"generated lid movement rendered")
	app.hero.position=Vector3(-2,0,0.5);await app.proximity()
	app.hero.position=Vector3(3,0,3);await app.proximity()
	app.place_at=Vector3(2,0.08,-1);app.placement_rotation=180
	await app.commit_place()
	check(app.placed[id].position.x==2,"existing furniture moved")
	await app.change_room("workshop")
	check(not app.placed.has(id),"home furniture isolated from workshop")
	await app.change_room("home")
	check(app.placed.has(id),"home furniture reloaded")
	await app.select_item(0)
	check(app.inspected.colors.get("body")=="#a8bcad","paint survives room reentry")
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://../artifacts/studio-e2e.png")
	await app.retrieve()
	check(not app.placed.has(id) and app.selected.state=="inventory","retrieve preserves inventory")
	var other=load("res://scripts/api.gd").new();root.add_child(other);other.base_url=api.base_url
	var stranger: Dictionary=await other.post("/v1/auth/register",{"username":"stranger_"+str(Time.get_ticks_usec()),"password":"Local-stranger-password"})
	other.token=stranger.data.token
	var denied: Dictionary=await other.request("/v1/objects/"+id+"/assembly")
	check(not denied.ok,"other account cannot load assembly")
	var report := {"ok":failures.is_empty(),"failures":failures,"object_id":id,"provenance":app.inspected.manifest.provenance}
	var file := FileAccess.open("res://../artifacts/studio-e2e.json",FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
	print("STUDIO_E2E ",JSON.stringify(report))
	quit(0 if failures.is_empty() else 1)
