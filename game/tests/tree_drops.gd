extends SceneTree
## Tree shaking harness without a network server: builds the archipelago town, a real
## walker and village_life.gd, and answers /v1/homestead through tools/life_bridge.py
## (the server's own rules). Shakes several trees and checks that fruit falls out of the
## crown, comes to rest on open ground within reach, is picked up by walking over it or
## pressing E (one server pickup each), that every tree keeps its own state (a bare tree
## gives nothing until it regrows) and that fruit left lying is restored after a revisit.
## Then uses the other field props once each and captures their effects.
##   godot --headless --path game --script res://tests/tree_drops.gd
## Windowed (no --headless) it also writes artifacts/tree-drop-*.png and artifacts/fx-*.png.
const Town=preload("res://scripts/town.gd")
const Player=preload("res://scripts/player.gd")
const Profile=preload("res://scripts/controller_profile.gd")
const Map=preload("res://maps/archipelago/archipelago.gd")
const Fx=preload("res://scripts/fx.gd")
const LifeLoop=preload("res://tests/life_loop.gd")
var app
var failures := 0
var trees: Node3D

func _initialize() -> void: call_deferred("run")

func expect(ok: bool, what: String) -> void:
	print("PASS " if ok else "FAIL ",what)
	if not ok: failures+=1

func capture(name: String) -> void:
	if DisplayServer.get_name()=="headless": return
	await RenderingServer.frame_post_draw
	var path := ProjectSettings.globalize_path("res://../artifacts/"+name+".png")
	root.get_texture().get_image().save_png(path)
	print("CAPTURE ",path)

func frames(n: int) -> void:
	for i in n: await process_frame

func seconds(s: float) -> void:
	var until := Time.get_ticks_msec()+int(s*1000.0)
	while Time.get_ticks_msec()<until:
		follow()
		await process_frame

func run() -> void:
	Profile.ensure_input()
	var seed_state := FileAccess.open(OS.get_user_data_dir()+"/life_state.json",FileAccess.WRITE)
	seed_state.store_string(JSON.stringify({"version":0,"coins":10,"bag":{"bait":1},"plots":[{},{},{},{},{},{}],"fishing":null,"cooldowns":{},"harvested":0,"caught":0,"collection":{},"order_day":-1}))
	seed_state.close()
	app=LifeLoop.StubApp.new()
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
	app.api=LifeLoop.MockApi.new(); app.add_child(app.api)
	app.sound=LifeLoop.StubSound.new(); app.add_child(app.sound)
	app.social=LifeLoop.StubSocial.new(); app.add_child(app.social)
	app.world=Node3D.new(); app.add_child(app.world)
	var town: Node3D=Town.new(); town.camera=app.camera; app.town=town; app.world.add_child(town)
	app.player=Player.new(); app.world.add_child(app.player)
	app.player.controls_enabled=false
	app.life=preload("res://scripts/village_life.gd").new(); app.life.app=app; app.add_child(app.life)
	await frames(4)
	await app.life.enter()
	trees=town.trees
	expect(not app.life.state.is_empty(),"life state loads through the bridge")
	# Index: every map tree is one server node, numbered per kind in layout order.
	var counts := {}
	var ids := {}
	for tree in trees.trees:
		counts[tree.kind]=int(counts.get(tree.kind,0))+1
		ids[tree.id]=true
	expect(counts=={"apple":38,"pine":13,"palm":4},"trees indexed per kind: %s" % str(counts))
	expect(ids.size()==trees.trees.size(),"tree ids are unique")
	var a: Dictionary=pick_tree("apple",Vector2(-44,10))
	var b: Dictionary=pick_tree("apple",Vector2(-20,15))
	var pine: Dictionary=pick_tree("pine",Vector2(-12.9,19.4))
	var palm: Dictionary=pick_tree("palm",Vector2(0,60))
	print("TREES a=%s b=%s pine=%s palm=%s" % [a.id,b.id,pine.id,palm.id])
	# --- tree A: ripe, shaken, fruit falls and rests within reach.
	await stand_at(a)
	await seconds(0.6)
	expect(a.built and is_instance_valid(a.fruit) and a.fruit.visible and a.slots.size()==trees.hang_count(a),"ripe tree shows %d hanging fruit" % trees.hang_count(a))
	app.camera.size=7.0
	await seconds(0.1)
	await capture("tree-drop-hanging")
	app.camera.size=Profile.VILLAGE_CAMERA_DEFAULT
	var entry: Dictionary=town.nearest_prop(xz(app.player.global_position))
	expect(entry.get("id","")=="37_round_tree" and entry.get("node")==a.node,"tree is the E target: %s" % str(entry.get("id","")))
	var bag_before: int=int(app.life.state.bag.get("apple",0))
	town.use_prop(app,entry)
	await seconds(0.5)
	await capture("tree-drop-shake")
	await seconds(0.25)
	await capture("tree-drop-falling")
	await settle()
	var mine: Array=trees.drops.filter(func(d): return d.tree==a)
	var server_items: Array=app.life.state.get("drops",{}).get(a.id,{}).get("items",[])
	expect(mine.size()>=trees.hang_count(a) and mine.size()==server_items.size(),"shake drops %d items (server %s)" % [mine.size(),str(server_items)])
	expect(int(app.life.state.bag.get("apple",0))==bag_before,"fallen fruit is not in the bag yet")
	expect(not a.ready and not a.fruit.visible,"shaken tree shows no fruit")
	check_resting(a,mine)
	await capture("tree-drop-rest")
	# --- a second shake on the bare tree gives nothing.
	var version: int=int(app.life.state.version)
	await seconds(0.7)
	town.use_prop(app,{"id":"37_round_tree","node":a.node,"at":a.at})
	await seconds(1.2)
	expect(trees.drops.filter(func(d): return d.tree==a).size()==mine.size(),"bare tree drops nothing more")
	expect(int(app.life.state.version)==version,"bare tree does not even ask the server")
	# --- pick up: walk over the first, E for the second, walk over the rest.
	var first: Dictionary=mine[0]
	var item0: String=first.item
	var have0: int=int(app.life.state.bag.get(item0,0))
	await walk_to(xz(first.pos),Vector3(0,0,-1))
	await seconds(0.25)
	await capture("tree-drop-pickup")
	await wait_idle()
	expect(int(app.life.state.bag.get(item0,0))==have0+1,"walking over a %s picks it up" % item0)
	if mine.size()>1:
		var second: Dictionary=mine[1]
		var item1: String=second.item
		var have1: int=int(app.life.state.bag.get(item1,0))
		await walk_to(xz(second.pos)+Vector2(0,1.1),Vector3(0,0,-1))
		var near: Dictionary=town.nearest_prop(xz(app.player.global_position))
		expect(near.get("id","")=="fruit" and near.drop==second,"fallen fruit is the E target: %s" % str(near.get("id","")))
		print("PROMPT ",town.prop_prompt(near))
		town.use_prop(app,near)
		await wait_idle()
		expect(int(app.life.state.bag.get(item1,0))==have1+1,"E picks up a %s" % item1)
	for d in mine.slice(2):
		await walk_to(xz(d.pos),Vector3(0,0,-1))
		await wait_idle()
	await seconds(0.3)
	expect(trees.drops.filter(func(d): return d.tree==a).is_empty(),"all of tree A's fruit picked up")
	expect(not app.life.state.get("drops",{}).has(a.id),"server has nothing left under tree A")
	expect(int(app.life.state.bag.get("apple",0))==bag_before+server_items.count("apple"),"bag gained exactly the fallen apples")
	# --- tree B is independent of A.
	await seconds(0.7)
	await stand_at(b)
	await seconds(0.4)
	expect(b.ready and b.fruit.visible,"tree B is still ripe while A regrows")
	town.use_prop(app,{"id":"37_round_tree","node":b.node,"at":b.at})
	await settle()
	var under_b: Array=trees.drops.filter(func(d): return d.tree==b)
	expect(under_b.size()>=trees.hang_count(b),"tree B drops its own fruit (%d)" % under_b.size())
	check_resting(b,under_b)
	# --- revisit: local fruit is gone, the server list brings it back where it lies.
	for d in under_b.duplicate(): trees.remove(d,false)
	await seconds(0.6)
	var restored: Array=trees.drops.filter(func(d): return d.tree==b)
	expect(restored.size()==under_b.size() and restored.all(func(d): return d.state=="rest"),"fruit left lying is restored from the server (%d)" % restored.size())
	check_resting(b,restored)
	await capture("tree-drop-restored")
	# --- conifer and palm.
	for tree in [pine,palm]:
		await seconds(0.7)
		await stand_at(tree)
		await seconds(0.5)
		app.camera.size=7.0
		await seconds(0.1)
		await capture("tree-drop-%s-hanging" % tree.kind)
		app.camera.size=Profile.VILLAGE_CAMERA_DEFAULT
		town.use_prop(app,{"id":tree.prop,"node":tree.node,"at":tree.at})
		await settle()
		var fallen: Array=trees.drops.filter(func(d): return d.tree==tree)
		expect(fallen.size()>=trees.hang_count(tree) and fallen.any(func(d): return d.item==trees.FRUIT[tree.kind]),"%s drops %s" % [tree.id,str(fallen.map(func(d): return d.item))])
		check_resting(tree,fallen)
		await capture("tree-drop-%s-rest" % tree.kind)
	# --- regrowth: A comes back on its own timer and can be shaken again.
	app.api.offset+=float(app.life.state.catalog.trees.apple.respawn)+5.0
	for i in 600:
		if not app.life.reading and not app.life.pending: break
		await process_frame
	await app.life.refresh()
	await stand_at(a)
	await seconds(0.9)
	expect(a.ready and a.fruit.visible,"tree A regrew its fruit")
	town.use_prop(app,{"id":"37_round_tree","node":a.node,"at":a.at})
	await settle()
	expect(trees.drops.filter(func(d): return d.tree==a).size()>=trees.hang_count(a),"regrown tree A drops again")
	# --- the other props: effects instead of sentences.
	await fx_tour(town)
	print("TREE_DROPS failures=",failures)
	quit(1 if failures else 0)

func xz(v: Vector3) -> Vector2: return Vector2(v.x,v.z)

## A tree of `kind` near `hint` with room for its fruit on the camera side.
func pick_tree(kind: String, hint: Vector2) -> Dictionary:
	var best: Dictionary={}
	for tree in trees.trees:
		if tree.kind!=kind: continue
		if best.is_empty() or hint.distance_to(tree.at)<hint.distance_to(best.at): best=tree
	return best

func stand_at(tree: Dictionary) -> void:
	# South of the trunk (camera side), facing it.
	var spots: Array=trees.ground_spots(tree)
	var stand: Vector2=tree.at+Vector2(0,1.7)
	var best := INF
	for s in spots:
		var p := Vector2(s.x,s.z)
		var d: float=(p-tree.at).normalized().distance_to(Vector2(0,1))
		if d<best:
			best=d
			stand=tree.at+(p-tree.at).normalized()*1.75
	await walk_to(stand,Vector3(tree.at.x-stand.x,0,tree.at.y-stand.y).normalized())
	trees.tick()

func settle() -> void:
	var start := Time.get_ticks_msec()
	await seconds(0.4)
	while Time.get_ticks_msec()-start<6000:
		await seconds(0.1)
		if trees.drops.all(func(d): return d.state=="rest") and not app.life.pending: break
	await seconds(0.2)

func check_resting(tree: Dictionary, list: Array) -> void:
	var space: PhysicsDirectSpaceState3D=trees.get_world_3d().direct_space_state
	for d in list:
		var p: Vector3=d.pos
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(p.x,60,p.z),Vector3(p.x,-20,p.z),1))
		var ground: float=hit.position.y if not hit.is_empty() else NAN
		var r: float=trees.RADIUS.get(d.item,0.12)
		var gap: float=xz(p).distance_to(tree.at)
		var ok: bool=d.state=="rest" and not is_nan(ground) and absf(p.y-r-ground)<0.1 and ground>1.45 and gap>0.45 and gap<2.7
		expect(ok,"%s %s rests on open ground %.2f m from the trunk (y %.2f, ground %.2f, %s)" % [tree.id,d.item,gap,p.y-r,ground,d.state])

func wait_idle() -> void:
	for i in 300:
		await process_frame
		if not app.life.pending and trees.queue.is_empty() and not trees.draining: break
	await seconds(0.15)

func walk_to(at: Vector2, facing: Vector3) -> void:
	app.player.position=Town.point(at,0.1)
	app.player.velocity=Vector3.ZERO
	app.player.facing=facing
	app.player.visual.rotation.y=atan2(facing.x,facing.z)
	for i in 3: await physics_frame
	follow()
	await frames(2)

func follow() -> void:
	if not is_instance_valid(app) or not is_instance_valid(app.player): return
	var focus: Vector3=app.player.position+Profile.CAMERA_FOCUS_OFFSET
	app.camera.position=focus+Profile.CAMERA_OFFSET
	app.camera.look_at(focus)

## Uses one of each other prop and captures the moment the effect plays.
func fx_tour(town: Node3D) -> void:
	var kinds := ["42_white_flowers","44_pink_flowers","45_reeds","41_planter","24_firepit","21_boat","36_speaker","26_bench","22_tent_orange","40_shrub","29_beach_lounger","31_cafe_table"]
	for id in kinds:
		var best: Dictionary={}
		for prop in town.props:
			if prop.id!=id or not prop.node.visible: continue
			if best.is_empty() or prop.at.distance_to(Town.SPAWN)<best.at.distance_to(Town.SPAWN): best=prop
		if best.is_empty():
			expect(false,"no %s on the map" % id)
			continue
		var reach: float=float(Town.PROP_ACTIONS[id][1])*0.7
		var stand: Vector2=best.at+Vector2(0,reach)
		await walk_to(stand,Vector3(0,0,-1))
		var target: Dictionary=town.nearest_prop(xz(app.player.global_position))
		var said: String=app.last_message
		var shown: int=Fx.played
		town.use_prop(app,best if target.get("id","")!="fruit" else best)
		await seconds(0.45 if id!="36_speaker" else 0.9)
		await capture("fx-"+id)
		await seconds(0.6)
		expect(Fx.played>shown,"%s plays effects (%d)" % [id,Fx.played-shown])
		expect(app.last_message==said,"%s says no sentence" % id)
		await wait_idle()
