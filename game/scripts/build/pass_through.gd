extends Node
## 물건 통과 (item 76): the walker passes through player-made objects (their collision layer 16)
## so a piece put down in the way never traps anyone. Only the own walker changes; everybody
## else, and the objects themselves, stay as they are. The choice is remembered on this PC.
##
## Feedback is an effect, not a sentence: a soft ring follows the walker's feet while it is on.
## Turning it off inside an object waits until the walker has stepped out, then takes hold.
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Fx = preload("res://scripts/fx.gd")
const LAYER := 16
const PREFS := "user://build_prefs.cfg"

## Read by rooms too (studio.gd movement_blocked skips placed pieces while it is on).
static var on := false
static var _loaded := false
## Tests turn this off so they never change the player's saved choice.
static var persist := true

var walker: CharacterBody3D
var ring: MeshInstance3D
var waiting_off := false
var age := 0.0

static func load_pref() -> void:
	if _loaded: return
	_loaded=true
	var cfg := ConfigFile.new()
	if cfg.load(PREFS)==OK: on=bool(cfg.get_value("build","pass_through",false))

static func save_pref() -> void:
	if not persist: return
	var cfg := ConfigFile.new()
	cfg.load(PREFS)
	cfg.set_value("build","pass_through",on)
	cfg.save(PREFS)

## The helper for this walker (made once, kept under the walker).
static func for_walker(body: CharacterBody3D) -> Node:
	load_pref()
	if not is_instance_valid(body): return null
	var found := body.get_node_or_null("PassThrough")
	if found: return found
	var helper = load("res://scripts/build/pass_through.gd").new()
	helper.name="PassThrough"
	helper.walker=body
	body.add_child(helper)
	helper.apply(false)
	return helper

func toggle() -> void:
	if on and blocked_here():
		# Off inside an object would trap the walker: it takes hold once the walker is clear.
		waiting_off=not waiting_off
		RpgUi.sfx("invalid" if waiting_off else "valid",-10.0)
		_pulse(Color(1.0,0.75,0.45,0.8) if waiting_off else Color(0.75,0.9,1.0,0.8))
		return
	on=not on
	waiting_off=false
	save_pref()
	apply(true)

func apply(animate: bool) -> void:
	if not is_instance_valid(walker): return
	walker.collision_mask=(walker.collision_mask&~LAYER) if on else (walker.collision_mask|LAYER)
	_show_ring(on)
	if animate:
		RpgUi.sfx("twinkle" if on else "click",-8.0)
		_pulse(Color(0.7,0.88,1.0,0.85) if on else Color(1,1,1,0.5))

## Whether the walker stands inside a player-made object right now.
func blocked_here() -> bool:
	if not is_instance_valid(walker) or not walker.is_inside_tree(): return false
	var probe := PhysicsShapeQueryParameters3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius=0.3;capsule.height=1.4
	probe.shape=capsule
	probe.transform=Transform3D(Basis(),walker.global_position+Vector3(0,0.75,0))
	probe.collision_mask=LAYER
	return not walker.get_world_3d().direct_space_state.intersect_shape(probe,1).is_empty()

func _process(delta: float) -> void:
	age+=delta
	if is_instance_valid(ring) and ring.visible:
		var beat := 0.5+0.5*sin(age*3.0)
		(ring.material_override as StandardMaterial3D).albedo_color.a=0.28+0.22*beat
		ring.rotation.y+=delta*0.8
	if waiting_off and age>=0.25:
		age=fmod(age,TAU)
		if not blocked_here():
			waiting_off=false
			on=false
			save_pref()
			apply(true)

func _pulse(color: Color) -> void:
	var parent := walker.get_parent() as Node3D
	if parent: Fx.ring(parent,walker.global_position+Vector3(0,0.06,0),1.1,color,0.7)

## A thin glowing ring at the feet while passing through is on.
func _show_ring(shown: bool) -> void:
	if shown and not is_instance_valid(ring):
		ring=MeshInstance3D.new()
		ring.name="PassRing"
		var torus := TorusMesh.new()
		torus.inner_radius=0.46;torus.outer_radius=0.52;torus.rings=24;torus.ring_segments=6
		ring.mesh=torus
		var glow := StandardMaterial3D.new()
		glow.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		glow.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
		glow.albedo_color=Color(0.72,0.9,1.0,0.45)
		glow.no_depth_test=false
		ring.material_override=glow
		ring.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ring.scale=Vector3(1,0.15,1)
		ring.position.y=0.05
		walker.add_child(ring)
	if is_instance_valid(ring): ring.visible=shown
