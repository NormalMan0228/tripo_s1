extends SceneTree
## Village-life harness without a network server: builds the archipelago town, a
## real walker and village_life.gd, and answers /v1/homestead through
## tools/life_bridge.py (the server's own rules). Plays till -> plant -> water ->
## harvest, a forage pick-up and a full fishing catch, and saves artifacts/life-*.png.
## Run windowed for captures:  godot --path game --script res://tests/life_loop.gd
const Town=preload("res://scripts/town.gd")
const Player=preload("res://scripts/player.gd")
const Profile=preload("res://scripts/controller_profile.gd")
const Map=preload("res://maps/archipelago/archipelago.gd")
const Farm=preload("res://scripts/farm.gd")
var app: StubApp
var failures := 0

class MockApi extends Node:
	var token := "harness"
	var offset := 0.0
	var dir := OS.get_user_data_dir()
	func clock() -> float: return 1000000.0+Time.get_ticks_msec()*0.001+offset
	func mutation(body: Dictionary) -> Dictionary: return body
	func call_bridge(body: Dictionary) -> Dictionary:
		var file := FileAccess.open(dir+"/life_body.json",FileAccess.WRITE)
		file.store_string(JSON.stringify(body))
		file.close()
		var out: Array=[]
		var python := ProjectSettings.globalize_path("res://../.tools/server-venv/Scripts/python.exe")
		OS.execute(python,[ProjectSettings.globalize_path("res://../tools/life_bridge.py"),dir+"/life_state.json",dir+"/life_body.json",str(clock())],out,true)
		var reply=JSON.parse_string(str(out[0]).strip_edges().split("\n")[-1])
		await get_tree().process_frame
		if not reply is Dictionary: return {"ok":false,"error":"bridge_failed"}
		return reply
	func request(_path: String) -> Dictionary: return await call_bridge({"action":"__get"})
	func post(_path: String, body: Dictionary) -> Dictionary: return await call_bridge(body)

class StubSocial extends Node:
	var data := {}
	func visiting() -> bool: return false
	func accept_crops() -> void: pass
	func open_menu() -> void: pass

class StubSound extends Node:
	func effect(_kind: String) -> void: pass

class StubApp extends Node3D:
	var screen := "village"
	var town: Node3D
	var player: CharacterBody3D
	var camera: Camera3D
	var api: MockApi
	var sound: StubSound
	var social: StubSocial
	var world: Node3D
	var ui: Control
	var village_modal: Control
	var world_epoch := 0
	var expedition_button: Button
	var life: Node
	var last_message := ""
	func message(v: String) -> void:
		last_message=v
		print("MESSAGE ",v)
	func error_message(code: String) -> String: return code
	func open_studio(_room := "") -> void: pass
	func floating_feedback(value: String, at: Vector3, color: Color) -> void:
		var label := Label3D.new()
		label.text=value; label.font_size=32; label.pixel_size=0.007; label.outline_size=5
		label.position=at+Vector3(0,2.1,0); label.billboard=BaseMaterial3D.BILLBOARD_ENABLED; label.modulate=color
		world.add_child(label)
		var t := label.create_tween()
		t.tween_property(label,"position:y",label.position.y+0.85,1.5)
		t.tween_callback(label.queue_free)
	func text(parent: Node, value: String, size := 15) -> Label:
		var l := Label.new(); l.text=value; l.add_theme_font_size_override("font_size",size); parent.add_child(l); return l
	func button(parent: Node, value: String, callback: Callable, _variant := "default") -> Button:
		var b := Button.new(); b.text=value; b.pressed.connect(callback); parent.add_child(b); return b
	func close_village_modal() -> void:
		if is_instance_valid(life): life.closed()
		if is_instance_valid(village_modal): village_modal.queue_free()
		village_modal=null
	func modal_card(title: String) -> VBoxContainer:
		close_village_modal()
		village_modal=Control.new()
		village_modal.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		ui.add_child(village_modal)
		var shade := ColorRect.new(); shade.color=Color(0.03,0.05,0.06,0.7); shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		village_modal.add_child(shade)
		var p := PanelContainer.new(); p.position=Vector2(265,60); p.custom_minimum_size=Vector2(750,0)
		var style := StyleBoxFlat.new(); style.bg_color=Color("2a3436"); style.set_corner_radius_all(14); style.set_content_margin_all(18)
		p.add_theme_stylebox_override("panel",style)
		village_modal.add_child(p)
		var v := VBoxContainer.new(); p.add_child(v)
		text(v,title,25)
		return v

func _initialize() -> void: call_deferred("run")

func expect(ok: bool, what: String) -> void:
	print("PASS " if ok else "FAIL ",what)
	if not ok: failures+=1

func capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	if DisplayServer.get_name()=="headless": return
	var path := ProjectSettings.globalize_path("res://../artifacts/life-"+name+".png")
	root.get_texture().get_image().save_png(path)
	print("CAPTURE ",path)

func frames(n: int) -> void:
	for i in n: await process_frame

func run() -> void:
	var seed_state := FileAccess.open(OS.get_user_data_dir()+"/life_state.json",FileAccess.WRITE)
	seed_state.store_string(JSON.stringify({"version":0,"coins":90,"bag":{"turnip_seed":3,"pumpkin_seed":1,"carrot_seed":2,"bait":5},"plots":[{},{},{},{},{},{}],"fishing":null,"cooldowns":{},"harvested":0,"caught":0,"collection":{},"order_day":-1}))
	seed_state.close()
	app=StubApp.new()
	root.add_child(app)
	var e := WorldEnvironment.new(); var env := Environment.new()
	env.background_mode=Environment.BG_COLOR; env.background_color=Color("88bcb9")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR; env.ambient_light_color=Color.WHITE; env.ambient_light_energy=0.35
	e.environment=env; app.add_child(e)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees=Vector3(-48,-32,0); sun.shadow_enabled=true; app.add_child(sun)
	Map.apply_lighting(env,sun)
	app.camera=Camera3D.new(); app.camera.projection=Camera3D.PROJECTION_ORTHOGONAL; app.camera.size=Profile.VILLAGE_CAMERA_DEFAULT; app.camera.current=true
	app.add_child(app.camera)
	var layer := CanvasLayer.new(); app.add_child(layer)
	app.ui=Control.new(); app.ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); app.ui.mouse_filter=Control.MOUSE_FILTER_IGNORE; layer.add_child(app.ui)
	var bar := HBoxContainer.new(); bar.position=Vector2(400,710); app.ui.add_child(bar)
	for i in 6:
		var slot := Button.new(); slot.custom_minimum_size=Vector2(78,78); slot.text=["I","C","Tab","B","O",""][i]; bar.add_child(slot)
	app.expedition_button=bar.get_child(5)
	app.api=MockApi.new(); app.add_child(app.api)
	app.sound=StubSound.new(); app.add_child(app.sound)
	app.social=StubSocial.new(); app.add_child(app.social)
	app.world=Node3D.new(); app.add_child(app.world)
	var town: Node3D=Town.new(); town.camera=app.camera; app.town=town; app.world.add_child(town)
	app.player=Player.new(); app.world.add_child(app.player)
	app.player.controls_enabled=false
	app.life=preload("res://scripts/village_life.gd").new(); app.life.app=app; app.add_child(app.life)
	await frames(4)
	await app.life.enter()
	expect(not app.life.state.is_empty() and app.life.state.plots.size()==6,"life state loads through the bridge with six starter beds")
	await walk_to(Vector2(-20.2,-31.4),Vector3(0,0,-1))
	# Farming: water a seeded starter bed so all stages are visible together.
	var life: Node=app.life
	expect(life.closest().get("kind","")=="plot","starter bed in reach")
	life.open_plot(life.closest().index)
	await frames(3)
	await capture("seed-picker")
	life.plant(life.closest().index,"turnip")
	await wait_idle()
	for pair in [[1,"carrot"],[2,"pumpkin"],[3,"strawberry"],[4,"sunflower"],[5,"turnip"]]:
		await buy(pair[1]+"_seed")
		await life.request("plant",{"plot":pair[0],"item":pair[1]})
	for i in 6:
		if i!=5: await life.request("water",{"plot":i})
	expect(life.state.plots.all(func(p): return p.get("crop")),"six starter beds planted")
	# Till two new beds east of the starter block.
	await walk_to(Vector2(-22.0,-29.7),Vector3(0,0,-1))
	await frames(4)
	var focus: Dictionary=life.closest()
	expect(focus.get("kind","")=="till","hoe prompt on open meadow: %s" % str(focus.get("prompt","")))
	await capture("till-ghost")
	if focus.get("kind","")=="till":
		life.interact()
		await frames(12)
		await capture("till-swing")
		await wait_idle()
	expect(life.state.plots.size()==7,"tilling adds a server plot")
	expect(Farm.new().till_problem(Vector2(-16,-29.4),life.state.plots,18)!="","road cell is refused by the client")
	# Fast-forward growth for a stage line-up.
	app.api.offset+=100
	await life.refresh()
	await frames(6)
	await walk_to(Vector2(-18.4,-30.6),Vector3(0,0,-1))
	await frames(10)
	await capture("farm-stages")
	app.api.offset+=200
	await life.refresh()
	await frames(20)
	await capture("farm-ripe")
	await walk_to(Vector2(-20.2,-31.4),Vector3(0,0,-1))
	focus=life.closest()
	expect(focus.get("kind","")=="plot" and focus.get("stage",0)==5,"ripe bed prompt: %s" % str(focus.get("prompt","")))
	var before: int=int(life.state.bag.get("turnip",0))
	life.interact()
	await frames(14)
	await capture("harvest-pop")
	await wait_idle()
	expect(int(life.state.bag.get("turnip",0))==before+2,"harvest adds two turnips")
	# Foraging.
	var shell: Array=preload("res://scripts/forage.gd").NODES[6]
	await walk_to(Vector2(shell[2],shell[3])+Vector2(0,1.1),Vector3(0,0,-1))
	focus=life.closest()
	expect(focus.get("kind","")=="forage","shell prompt: %s" % str(focus.get("prompt","")))
	await capture("forage-shell")
	life.interact()
	await frames(8)
	await capture("forage-pick")
	await wait_idle()
	expect(int(life.state.bag.get("shell",0))+int(life.state.bag.get("conch",0))+int(life.state.bag.get("pearl",0))>0,"shell spot gives a shell find")
	expect(life.state.nodes.has(shell[0]),"spot respawn is tracked by the server")
	for id in ["rock_02","mushroom_06","flower_06","herb_06","branch_05"]:
		for row in preload("res://scripts/forage.gd").NODES:
			if row[0]==id:
				await walk_to(Vector2(row[2],row[3])+Vector2(1.6,1.9),Vector3(-0.6,0,-1).normalized())
				await capture("forage-"+row[1])
	# Shore detection: a few banks around the pond and the sea.
	for probe in [[Vector2(-47,31.5),Vector3(0,0,1)],[Vector2(-31,44),Vector3(-1,0,0)],[Vector2(4.1,85.4),Vector3(0,0,1)],[Vector2(27.6,6.6),Vector3(0,0,1)],[Vector2(-1,-13.5),Vector3(0,0,1)]]:
		await walk_to(probe[0],probe[1])
		print("SHORE ",probe[0]," -> ",life.fishing.find_cast(app.player.position,probe[1]))
	# Fishing on the pier side of the sea.
	await walk_to(Vector2(-6.8,79.0),Vector3(0,0,1))
	await frames(4)
	focus=life.closest()
	print("FISH_FOCUS ",focus.get("prompt",""))
	if focus.get("kind","")!="fish":
		await walk_to(Vector2(-4,82.6),Vector3(0,0,1))
		focus=life.closest()
	expect(focus.get("kind","")=="fish","fishing prompt near the sea")
	life.interact()
	await frames(4)
	expect(life.mode=="fish","fishing HUD opens")
	life.reel()
	await frames(20)
	await capture("fish-cast")
	var fish: Dictionary={}
	var started := Time.get_ticks_msec()
	while Time.get_ticks_msec()-started<20000:
		await frames(1)
		fish=life.state.get("fishing") if life.state.get("fishing") is Dictionary else {}
		if life.fishing.phase=="waiting" and not fish.is_empty() and life.now()>=float(fish.bite_at)+0.25: break
	await capture("fish-bite")
	life.reel()
	for i in 200:
		await frames(1)
		if life.fishing.phase=="fight": break
	expect(life.fishing.phase=="fight","hook starts the reel fight")
	life.fishing.auto_reel=true
	await frames(50)
	await capture("fish-fight")
	for i in 900:
		await frames(1)
		if life.fishing.phase in ["card","ready"]: break
	await frames(30)
	await capture("fish-catch")
	expect(int(life.state.caught)==1,"fight lands a fish on the server")
	life.reel()
	await frames(30)
	app.close_village_modal()
	life.open_log()
	await frames(4)
	await capture("fish-log")
	life.open_storage()
	await frames(4)
	await capture("storage")
	app.close_village_modal()
	print("LIFE_LOOP failures=",failures)
	quit(1 if failures else 0)

func buy(item: String) -> void:
	await app.life.request("buy",{"item":item})

func wait_idle() -> void:
	for i in 300:
		await frames(1)
		if not app.life.pending: break
	await frames(6)

func walk_to(at: Vector2, facing: Vector3) -> void:
	app.player.position=Town.point(at,0.1)
	app.player.velocity=Vector3.ZERO
	app.player.facing=facing
	app.player.visual.rotation.y=atan2(facing.x,facing.z)
	for i in 3: await physics_frame
	follow()
	await frames(3)

func follow() -> void:
	var focus: Vector3=app.player.position+Profile.CAMERA_FOCUS_OFFSET
	app.camera.position=focus+Profile.CAMERA_OFFSET
	app.camera.look_at(focus)
