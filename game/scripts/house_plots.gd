extends RefCounted
## 주민 이사 (43), the building side: a resident's house going up on (or coming down from) its
## plot, as story code (move_in.gd, 06) decides from the server's residency brief.
##
##   HousePlots.show_house("danbi_plot", true, fresh, app)   the house; fresh plays its arrival
##   HousePlots.show_house("danbi_plot", false, fresh, app)  back to the empty lot (moved out)
##   HousePlots.building("danbi_plot", app)                   dust on the lot: someone is on the way
##   HousePlots.set_sign("danbi_plot", "곧 새 이웃이 이사 와요")
##   HousePlots.door_at("danbi_plot") -> Vector2              where to stand before the door
##
## The plot itself (stakes, string, sign, the house model and its walls) is the map's
## (maps/archipelago/plots.gd); this adds what the player sees and feels when it changes:
## effects instead of sentences (dust, a ring of light, sparkles, a warm glow, a pop and a chime)
## and nobody left standing inside the new walls. `app` is the village (main.gd: world, player);
## without one the state changes quietly.
const Plots = preload("res://maps/archipelago/plots.gd")
const Fx = preload("res://scripts/fx.gd")

static func show_house(plot_id: String, built: bool, fresh := false, app = null) -> void:
	if not Plots.PLOTS.has(plot_id): return
	var was := Plots.is_built(plot_id)
	if built and not was: step_out(plot_id,app)
	if fresh and built!=was: _effect(plot_id,app,built)
	await Plots.set_plot_built(plot_id,built)

## Someone is on the way: a little dust over the lot (call once when the state turns 'building').
static func building(plot_id: String, app = null) -> void:
	var parent := _world(app)
	var info := Plots.plot_info(plot_id)
	if parent==null or info.is_empty(): return
	Fx.burst(parent,Vector3(info.center)+Vector3(0,0.4,0),"dust",8,Color(0,0,0,0),float(info.radius)*0.6)

static func set_sign(plot_id: String, text: String) -> void:
	Plots.set_sign_text(plot_id,text)

static func door_at(plot_id: String) -> Vector2:
	return Plots.door_point(plot_id) if Plots.PLOTS.has(plot_id) else Vector2.INF

## Whether a village point (map x,z) is on a plot: no furniture goes there (server: plot_reserved,
## the same radius), so a house can always go up.
static func on_plot(at: Vector2) -> String:
	for id in Plots.PLOTS:
		if at.distance_to(Vector2(Plots.PLOTS[id].center))<float(Plots.PLOTS[id].radius): return str(id)
	return ""

## The walker standing where the house goes up is set down before its door instead.
static func step_out(plot_id: String, app) -> void:
	if app==null or not is_instance_valid(app) or not ("player" in app) or not is_instance_valid(app.player): return
	var walker: Node3D=app.player
	var spec: Dictionary=Plots.PLOTS[plot_id]
	if Vector2(walker.global_position.x,walker.global_position.z).distance_to(Vector2(spec.center))>=float(spec.radius): return
	var door := door_at(plot_id)
	var info := Plots.plot_info(plot_id)
	walker.global_position=Vector3(door.x,float(Vector3(info.center).y)+0.3,door.y)

static func _effect(plot_id: String, app, built: bool) -> void:
	var parent := _world(app)
	var info := Plots.plot_info(plot_id)
	if parent==null or info.is_empty(): return
	var at: Vector3=info.center
	var reach: float=float(info.radius)
	Fx.burst(parent,at+Vector3(0,0.4,0),"dust",20,Color(0,0,0,0),reach*0.7)
	Fx.ring(parent,at+Vector3(0,0.06,0),reach*1.2,Color(1.0,0.9,0.6,0.8) if built else Color(0.9,0.86,0.76,0.5),1.0)
	var voiced := DisplayServer.get_name()!="headless"
	if built:
		Fx.burst(parent,at+Vector3(0,3.0,0),"sparkle",22,Color(0,0,0,0),reach*0.6)
		Fx.glow(parent,at+Vector3(0,2.2,0),Color("ffd27a"),4.0,1.4)
		if voiced:
			Fx.sound(app,"pop",at)
			Fx.sound(app,"twinkle",at,1.1,-3.0)
	elif voiced: Fx.sound(app,"thud",at,0.9,-2.0)

static func _world(app) -> Node3D:
	if app==null or not is_instance_valid(app) or not ("world" in app): return null
	var world = app.world
	return world if world is Node3D and world.is_inside_tree() else null
