extends SceneTree
## Build mode without a server: the placement rules (walls, ceilings, stacks, ways kept open in
## the village), the placed-object menu (entries, follow, choose, Esc), 물건 통과 (the walker's
## collision mask and the off-while-inside wait) and the loading ring.
##   godot --path game --script res://tests/build_mode_check.gd -- --mute [--capture]
const BuildRules = preload("res://scripts/build/build_rules.gd")
const PlacedMenu = preload("res://scripts/build/placed_menu.gd")
const PassThrough = preload("res://scripts/build/pass_through.gd")
const LoadRing = preload("res://scripts/build/load_ring.gd")
const VillageBuild = preload("res://scripts/build/village_build.gd")
const Town = preload("res://scripts/town.gd")
const Roads = preload("res://scripts/roads.gd")
var failures: Array[String] = []

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void: call_deferred("run")

func run() -> void:
	rules()
	await menu()
	await pass_through()
	await ring()
	await houses()
	print("build_mode_check: %d failure(s)" % failures.size())
	quit(0 if failures.is_empty() else 1)

func rules() -> void:
	# Walls: a picture frame hangs, a chair does not.
	check(BuildRules.wall_problem(Vector3(0.8,0.6,0.05)).is_empty(),"a flat frame hangs on a wall")
	check(not BuildRules.wall_problem(Vector3(0.5,0.9,0.5)).is_empty(),"a chair does not hang on a wall")
	# Ceilings: by size and by what it is.
	check(BuildRules.ceiling_problem(Vector3(0.6,0.5,0.6),"별빛 샹들리에").is_empty(),"a chandelier hangs from the ceiling")
	check(BuildRules.ceiling_problem(Vector3(0.4,0.4,0.4),"Paper lantern").is_empty(),"an English lantern name counts")
	check(not BuildRules.ceiling_problem(Vector3(0.6,0.5,0.6),"나무 의자").is_empty(),"a chair does not hang from the ceiling")
	check(not BuildRules.ceiling_problem(Vector3(2.5,0.5,0.6),"조명").is_empty(),"a huge light is refused")
	# Stacks: smaller on bigger, three high at most.
	check(BuildRules.stack_problem(Vector3(0.3,0.3,0.3),Vector3(1.2,0.8,0.8),1).is_empty(),"a cup goes on a table")
	check(not BuildRules.stack_problem(Vector3(1.5,0.5,1.5),Vector3(1.2,0.8,0.8),1).is_empty(),"a bigger piece does not go on a table")
	check(not BuildRules.stack_problem(Vector3(0.2,0.2,0.2),Vector3(1.2,0.8,0.8),3).is_empty(),"no fourth level")
	# Wall poses snap to the wall and face into the room.
	var back := BuildRules.wall_pose("back",Vector3(1.13,1.6,-5),Vector3(0.8,0.6,0.06),Vector2(10,10),3.4)
	check(back.rotation==0 and is_equal_approx(back.z,-5+0.03+0.02) and is_equal_approx(back.x,1.25) and is_equal_approx(back.y,1.3),"back wall pose %s" % str(back))
	var left := BuildRules.wall_pose("left",Vector3(-5,3.3,0.4),Vector3(0.8,0.6,0.06),Vector2(10,10),3.4)
	check(left.rotation==90 and is_equal_approx(left.x,-5+0.03+0.02) and left.y+0.6<=3.4-0.05+0.001,"left wall pose stays under the ceiling %s" % str(left))
	var right := BuildRules.wall_pose("right",Vector3(5,1,4.9),Vector3(1.0,0.6,0.06),Vector2(10,10),3.4)
	check(right.rotation==270 and right.z+0.5<=5-0.05+0.001,"right wall pose stays inside the room %s" % str(right))
	# A ray at the back wall meets it; one at the floor does not.
	var hit := BuildRules.wall_hit(Vector3(0,6,8),Vector3(0,-0.2,-1).normalized(),Vector2(10,10),3.4)
	check(str(hit.get("wall",""))=="back","a ray at the back wall meets it")
	check(BuildRules.wall_hit(Vector3(0,6,8),Vector3(0,-1,-0.4).normalized(),Vector2(10,10),3.4).is_empty(),"a ray at the floor meets no wall")
	check(BuildRules.nearest_wall(Vector3(-4.6,0,1),Vector2(10,10))=="left","the nearest wall to a floor point")
	# Village ways: a door, a bridge and the road for big pieces only.
	var door: Vector2=Town.DOORS[0].at
	var small := Vector3(0.4,0.5,0.4)
	var big := Vector3(1.6,1.6,1.6)
	check(not BuildRules.village_problem(Vector3(door.x,0,door.y),small,0).is_empty(),"nothing in front of a door")
	var road: Vector2=Roads.ROADS[1][2][1]
	check(not BuildRules.village_problem(Vector3(road.x,0,road.y),big,0).is_empty(),"a big piece may not stand on a road")
	check(BuildRules.village_problem(Vector3(road.x,0,road.y),small,0).is_empty(),"a small piece may stand on a road")
	var meadow := Vector3(-40,0,60)
	check(not Roads.on_road(Vector2(meadow.x,meadow.z)) and BuildRules.village_problem(meadow,big,0).is_empty(),"a big piece off the roads is fine")
	var lines := BuildRules.bridge_lines()
	if not lines.is_empty() and lines[0][0]!=Vector2.INF:
		var middle: Vector2=(lines[0][0]+lines[0][1])*0.5
		check(not BuildRules.village_problem(Vector3(middle.x,0,middle.y),small,0).is_empty(),"nothing on a bridge")
	# Stacked village pieces stand on the ground under their stack's bottom piece.
	var table := {"id":"t","x":10.0,"z":5.0,"state":"placed","surface":"floor"}
	var cup := {"id":"c","x":10.3,"z":5.1,"state":"placed","surface":"top","parent":"t","y":0.8}
	check(is_equal_approx(VillageBuild.spot(cup,[table,cup]).y,Town.furniture_point(10.0,5.0).y+0.8),"a stacked piece stands at its support's ground + y")
	check(VillageBuild.root_of(cup,[cup]).is_empty(),"a piece whose support is gone has no root")

func menu() -> void:
	var ui := Control.new()
	ui.size=Vector2(1280,720)
	root.add_child(ui)
	var world := Node3D.new()
	root.add_child(world)
	var camera := Camera3D.new()
	world.add_child(camera)
	camera.position=Vector3(0,6,8);camera.look_at(Vector3.ZERO)
	camera.current=true
	var item := Node3D.new()
	item.set_meta("size",Vector3(1,1,1))
	world.add_child(item)
	var picked: Array=[]
	var m: Control=PlacedMenu.open(ui,camera,item,"테스트 의자",func(id: String): picked.append(id),{"disabled":{"paint":"칠할 수 없어요"}})
	await process_frame
	await process_frame
	check(m.get_parent()==ui,"the menu opens on the UI")
	var buttons := m.find_children("*","Button",true,false)
	check(buttons.size()==4,"four entries (%d)" % buttons.size())
	var paint: Button=m.find_child("Paint",true,false)
	check(paint!=null and paint.disabled and paint.tooltip_text.contains("칠할"),"a disabled entry shows its reason")
	var spot: Vector2=camera.unproject_position(Vector3(0,1.25,0))
	check(m.position.y<spot.y and absf(m.position.x+m.size.x*0.5-spot.x)<2.0,"the menu floats above the object (%s vs %s)" % [str(m.position),str(spot)])
	(m.find_child("Turn",true,false) as Button).pressed.emit()
	check(picked==["turn"],"choosing answers with the entry id")
	await create_timer(0.3).timeout
	check(not is_instance_valid(m),"the menu closes after a choice")
	var second: Control=PlacedMenu.open(ui,camera,item,"테스트 의자",func(id: String): picked.append(id))
	await process_frame
	item.queue_free()
	await create_timer(0.3).timeout
	check(not is_instance_valid(second),"the menu closes when its object goes away")
	ui.queue_free();world.queue_free()

func pass_through() -> void:
	var world := Node3D.new()
	root.add_child(world)
	var walker := CharacterBody3D.new()
	walker.collision_mask=1|2|4|8|16|32
	world.add_child(walker)
	PassThrough.persist=false
	PassThrough._loaded=true
	PassThrough.on=false
	var helper = PassThrough.for_walker(walker)
	check(helper!=null and walker.collision_mask&16,"crafted objects block by default")
	helper.toggle()
	check(PassThrough.on and not (walker.collision_mask&16),"통과 on: the walker ignores crafted objects")
	check(walker.collision_mask&1 and walker.collision_mask&2,"…and still walks on the ground and into buildings")
	# A crafted block around the walker: switching off waits until the walker is out.
	var block := StaticBody3D.new()
	block.collision_layer=16
	var shape := CollisionShape3D.new();var box := BoxShape3D.new();box.size=Vector3(2,2,2);shape.shape=box;shape.position.y=1
	block.add_child(shape);world.add_child(block)
	await physics_frame
	await physics_frame
	helper.toggle()
	check(PassThrough.on and helper.waiting_off,"off inside an object waits")
	walker.position=Vector3(5,0,0)
	for i in 30: await physics_frame
	await create_timer(0.4).timeout
	check(not PassThrough.on and walker.collision_mask&16,"…and takes hold once the walker is out")
	check(PassThrough.for_walker(walker)==helper,"one helper per walker")
	world.queue_free()

## 주민 이사 (43): the house on its plot, the walker set down at the door, no furniture on a plot.
func houses() -> void:
	var HousePlots = load("res://scripts/house_plots.gd")
	var Plots = load("res://maps/archipelago/plots.gd")
	var plot: String=Plots.ids()[0]
	var centre: Vector2=Plots.PLOTS[plot].center
	check(HousePlots.on_plot(centre)==plot and HousePlots.on_plot(centre+Vector2(20,0)).is_empty(),"the plot covers its own ground only")
	check(not BuildRules.village_problem(Vector3(centre.x,0,centre.y),Vector3(0.3,0.3,0.3),0).is_empty(),"no furniture on a plot")
	check(HousePlots.door_at(plot)==Plots.door_point(plot),"door_at is the plot's door")
	var app := Node3D.new()
	app.set_script(load("res://tests/house_app.gd"))
	root.add_child(app)
	app.player.global_position=Vector3(centre.x,2.3,centre.y)
	await HousePlots.show_house(plot,true,true,app)
	check(Plots.is_built(plot),"show_house builds the house")
	var stood := Vector2(app.player.global_position.x,app.player.global_position.z)
	check(stood.distance_to(HousePlots.door_at(plot))<0.01,"the walker inside the new walls is set down at the door")
	await HousePlots.show_house(plot,false,true,app)
	check(not Plots.is_built(plot),"show_house(false) clears the plot again")
	HousePlots.set_sign(plot,"곧 새 이웃이 이사 와요")
	check(str(Plots.sign_texts.get(plot,""))=="곧 새 이웃이 이사 와요","set_sign keeps the sign's text")
	app.queue_free()

func ring() -> void:
	var ui := Control.new()
	root.add_child(ui)
	var r: Control=LoadRing.start(ui)
	await process_frame
	check(r.modulate.a<0.05,"the ring stays hidden for quick loads")
	await create_timer(0.4).timeout
	check(r.modulate.a>0.5,"the ring shows for slow loads")
	LoadRing.finish(r)
	await create_timer(0.3).timeout
	check(not is_instance_valid(r),"the ring goes away when the load ends")
	LoadRing.finish(null)
	ui.queue_free()
