extends SceneTree
## Gifts to residents (npc_gifts.gd, server/npc_homes.py), end to end on a QA server started with
## short resident timings (TRIPOTHON_NPC_PLACE_MIN=1, TRIPOTHON_NPC_PLACE_MAX=2):
## talk to Naru in the village -> 선물하기 -> pick the crafted chest -> it leaves the bag ->
## after the delay it stands in Naru's house (02_timber_house) -> a second gift appears while the
## owner is inside -> a visiting friend sees the same pieces, without a gift choice of their own.
## --capture saves artifacts/npc-gift-*.png (needs a window).
const Main = preload("res://scripts/main.gd")
const Town = preload("res://scripts/town.gd")
const NpcGifts = preload("res://scripts/npc_gifts.gd")
const HOME := "02_timber_house"
var failed := false
var url := "http://127.0.0.1:8816"

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("NPC gift check exceeded 240 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func craft(api: Node, prompt: String) -> String:
	var queued: Dictionary = await api.post("/v1/studio/jobs",api.mutation({"prompt":prompt,"geometry":"proxy","designer":"fixture"}))
	for i in 80:
		var job: Dictionary = await api.request("/v1/studio/jobs/"+str(queued.get("data",{}).get("id","")))
		if job.ok and job.data.state=="ready": return str(job.data.object_id)
		await create_timer(0.5).timeout
	return ""

func choice_button(modal: Node, label: String) -> Button:
	if not is_instance_valid(modal): return null
	for b in modal.find_children("*","Button",true,false):
		if (b as Button).text.strip_edges()==label and (b as Button).is_visible_in_tree(): return b
	return null

## Advances the open village dialogue until a choice with this label shows.
func reach_choice(app: Node, label: String) -> Button:
	for i in 40:
		var button := choice_button(app.village_modal,label)
		if button: return button
		if is_instance_valid(app.village_modal) and app.village_modal.has_meta("advance"): app.village_modal.get_meta("advance").call()
		await create_timer(0.25).timeout
	return null

func press_choice(app: Node, label: String) -> bool:
	var button := await reach_choice(app,label)
	if button: button.pressed.emit()
	return button!=null

func open_room(token: String, extra: Dictionary) -> Control:
	var session := {"token":token,"url":url,"room":HOME,"multiplayer":true}
	session.merge(extra,true)
	Engine.set_meta("studio_session",session)
	var room: Control = load("res://scenes/studio.tscn").instantiate()
	root.add_child(room)
	return room

func wait_gift(room: Node, id: String, seconds := 12.0) -> bool:
	for i in int(seconds/0.25):
		if room.gift_nodes.has(id) and is_instance_valid(room.gift_nodes[id].node): return true
		await create_timer(0.25).timeout
	return false

func shot(name: String) -> void:
	if not "--capture" in OS.get_cmdline_user_args(): return
	await create_timer(0.8).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/npc-gift-"+name+".png"))

func run() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): url = arg.trim_prefix("--server=")
	preload("res://scripts/npc.gd").pinned = true  # cast at their work spots whatever the clock
	var stamp := str(Time.get_ticks_msec())
	var app = Main.new()
	root.add_child(app)
	await create_timer(1.2).timeout
	await app.authenticate(true,url,"giver_"+stamp,"Npc-gift-check-1","")
	await create_timer(1.0).timeout
	expect(not app.api.token.is_empty(),"host signed in to the village")
	var chest := await craft(app.api,"wooden chest")
	var lamp := await craft(app.api,"flower lamp")
	expect(not chest.is_empty() and not lamp.is_empty(),"host crafted a chest and a lamp")
	await app.refresh_inventory()
	# Talk to Naru, 선물하기, pick the chest.
	var naru: Node3D
	for npc in app.npcs:
		if str(npc.get_meta("cast",""))=="naru": naru=npc
	var spot: Vector3=naru.position+Vector3(0,0,1.6)
	app.player.position=Town.point(Vector2(spot.x,spot.z),.3)
	for i in 20: await physics_frame
	app.talk_to(naru)
	expect(await press_choice(app,tr("선물하기")),"Naru's conversation offers 선물하기")
	var chest_name := ""
	for obj in app.me.objects:
		if str(obj.id)==chest: chest_name=str(obj.name)
	expect(await press_choice(app,chest_name),"the bag's crafted chest is a choice")
	var gone := false
	for i in 40:
		await create_timer(0.25).timeout
		gone=true
		for obj in app.me.objects:
			if str(obj.id)==chest: gone=false
		if gone: break
	expect(gone,"the chest left the bag")
	expect(await reach_choice(app,tr("천만에요"))!=null,"Naru reacts to the gift")
	await shot("thanks")
	app.close_village_modal()
	var options: Dictionary = await app.api.request("/v1/npcs/naru/gift")
	expect(options.ok and options.data.friendship.gifts==1,"friendship counts the gift")
	var token: String = app.api.token
	# Leave the village (its scene is heavy) and open Naru's house after the resident's delay.
	app.queue_free()
	await create_timer(3.0).timeout
	Engine.set_meta("interior_hour",20.0)  # residents are home in the evening
	var host_room := open_room(token,{})
	expect(await wait_gift(host_room,chest),"the chest stands in Naru's house after the delay")
	if host_room.gift_nodes.has(chest):
		var entry: Dictionary=host_room.gift_nodes[chest]
		var level: int=entry.record.floor
		expect(host_room.decor_by_floor[level].has(entry.record) and entry.node.get_parent()==host_room.floor_roots[level],"the chest is room furniture on its floor (blocks the walker, E works)")
		expect(entry.node.find_children("*","StaticBody3D",true,false).size()>0,"the chest has collision")
	await shot("host")
	# Inside, a resident at home takes the lamp through the room's own dialogue box; it appears
	# while the owner is still inside.
	var api: Node = load("res://scripts/api.gd").new(); root.add_child(api); api.base_url=url; api.token=token
	var lamp_name := ""
	for obj in (await api.request("/v1/me")).data.objects:
		if str(obj.id)==lamp: lamp_name=str(obj.name)
	var resident := ""
	for id in host_room.npcs:
		if NpcGifts.can_receive(id) and not host_room.npcs[id].state.get("asleep",false): resident=id
	expect(not resident.is_empty(),"a resident is at home in the evening")
	host_room.open_talk(resident)
	var offered: Array = []
	for choice in host_room.talk_choices:
		if str(choice[1])=="gift": offered=choice
	expect(not offered.is_empty(),"the resident offers 선물하기 inside the house")
	host_room.pick_talk(offered)
	var lamp_choice: Array = []
	for i in 40:
		await create_timer(0.25).timeout
		for choice in host_room.talk_choices:
			if choice[1] is Callable and str(choice[0])==lamp_name: lamp_choice=choice
		if not lamp_choice.is_empty(): break
	expect(not lamp_choice.is_empty(),"the bag's lamp is a choice inside the house")
	if not lamp_choice.is_empty(): host_room.pick_talk(lamp_choice)
	var thanked := false
	for i in 40:
		await create_timer(0.25).timeout
		for choice in host_room.talk_choices:
			if str(choice[0])==tr("천만에요"): thanked=true
		if thanked: break
	expect(thanked,"the resident thanks the player inside the house")
	await shot("inside-thanks")
	host_room.close_talk()
	expect(await wait_gift(host_room,lamp,15.0),"the lamp appears while the owner is inside")
	# A friend visits: same house, same pieces, no gift choice for the host's residents.
	var guest_api: Node = load("res://scripts/api.gd").new(); root.add_child(guest_api); guest_api.base_url=url
	var guest_login: Dictionary = await guest_api.post("/v1/auth/register",{"username":"visitor_"+stamp,"password":"Npc-gift-check-1"})
	guest_api.token=str(guest_login.get("data",{}).get("token",""))
	var invite: Dictionary = await api.post("/v1/social/invites",api.mutation({"username":"visitor_"+stamp,"kind":"village"}))
	var accepted: Dictionary = await guest_api.post("/v1/social/invites/"+str(invite.get("data",{}).get("id",""))+"/accept",guest_api.mutation())
	expect(accepted.ok and accepted.data.visiting,"friend is visiting the host's village")
	host_room.visible=false
	var guest_room := open_room(guest_api.token,{"visiting":true})
	expect(await wait_gift(guest_room,chest) and await wait_gift(guest_room,lamp),"the visitor sees both gifts in Naru's house")
	expect(guest_room.gift_version==host_room.gift_version,"visitor and owner see the same home version")
	await shot("guest")
	if guest_room.npcs.has(resident):
		guest_room.open_talk(resident)
		var guest_offered := false
		for choice in guest_room.talk_choices:
			if str(choice[1])=="gift": guest_offered=true
		expect(not guest_offered,"a visitor gets no 선물하기 for the host's residents")
		guest_room.close_talk()
	var none: Dictionary = await guest_api.request("/v1/npcs/naru/gift")
	expect(none.ok and not none.data.can_gift,"the visitor cannot give to the host's residents")
	var veil = load("res://scripts/transition.gd").instance
	if is_instance_valid(veil): veil.door.stop()
	OS.delay_msec(100)
	print("NPC_GIFT_CHECK ", "FAILED" if failed else "OK")
	quit(1 if failed else 0)
