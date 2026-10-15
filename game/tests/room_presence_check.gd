extends SceneTree
## The room's presence follows the room the owner walks into (studio.gd change_room): the workshop
## keeps the owner present as away, the home shares the walk as scene 'home' at once, so a friend at
## the door is let in only while the owner is really home (server/home_access.py). Reads the owner's
## live presence back through GET /v1/social/resume (its spot is null while away).
var failures: Array[String]=[]
func check(ok: bool, text: String) -> void:
	print(("PASS " if ok else "FAIL ")+text)
	if not ok: failures.append(text)
func _initialize() -> void: call_deferred("run")
func scene_now(api) -> String:
	var reply: Dictionary=await api.request("/v1/social/resume")
	if not reply.ok or not reply.data.get("resume") is Dictionary: return "?"
	var spot = reply.data.resume.get("spot")
	return str(spot.scene) if spot is Dictionary else "away"
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url=preload("res://tests/qa_server.gd").url()
	var login: Dictionary=await api.post("/v1/auth/register",{"username":"roomqa_"+str(Time.get_ticks_usec()),"password":"Local-room-qa-password"})
	check(login.ok,"new account")
	if not login.ok: quit(1); return
	api.token=login.data.token
	Engine.set_meta("studio_session",{"token":api.token,"url":api.base_url,"room":"workshop","multiplayer":true})
	var app=load("res://scenes/studio.tscn").instantiate();root.add_child(app)
	await create_timer(4).timeout
	check(not app.shared_presence,"the workshop does not share the walk")
	check(await scene_now(api)=="away","in the workshop the owner is present as away")
	await app.change_room("home")
	check(app.shared_presence,"walking into the home shares the walk")
	await create_timer(1.5).timeout
	check(await scene_now(api)=="home","at home the server sees the owner inside at once")
	await app.change_room("workshop")
	check(not app.shared_presence,"back in the workshop the walk is not shared")
	await create_timer(1.5).timeout
	check(await scene_now(api)=="away","back in the workshop the owner is away from the home again")
	print("ROOM_PRESENCE_RESULT ",JSON.stringify({"failures":failures}))
	quit(0 if failures.is_empty() else 1)
