extends "res://scripts/action_pose.gd"
## Small role-specific upper-body accents over the retargeted clips. Feet, root
## motion and combat timing stay with the original animation. No mesh is edited.
## lean, shoulder opening, head turn, breathing period (seconds).
const STYLES := {
	"m1": [0.015, 0.035, 0.025, 3.4],
	"m2": [0.045, 0.065, -0.025, 4.5],
	"m3": [-0.015, 0.025, 0.065, 4.0],
	"m4": [0.025, 0.12, -0.015, 5.2],
	"f1": [0.01, 0.025, -0.035, 3.2],
	"f2": [-0.025, 0.045, 0.04, 4.8],
	"f3": [0.04, 0.075, 0.02, 2.9],
	"f4": [-0.01, 0.085, -0.055, 3.8],
}
var actor: CharacterBody3D
var character := ""
var clock := 0.0
var weight := 0.0

func _process_modification_with_delta(delta: float) -> void:
	if not is_instance_valid(actor) or not STYLES.has(character): return
	var skeleton := get_skeleton()
	if not skeleton or not is_instance_valid(actor.animation_player): return
	clock += delta
	var clip := str(actor.animation_player.current_animation)
	var quiet := clip in ["idle", "walk", "run"]
	if is_instance_valid(actor.action_pose) and actor.action_pose.elapsed < actor.action_pose.duration: quiet = false
	weight = move_toward(weight, 1.0 if quiet else 0.0, delta * 8.0)
	if weight < .001: return
	var style: Array = STYLES[character]
	var breath := sin(clock * TAU / float(style[3]))
	var moving := clip != "idle"
	var amount := weight * (0.35 if moving else 1.0)
	body_basis = actor.visual.global_basis.orthonormalized()
	rotate_bone(skeleton, "Spine02", Vector3(float(style[0]) + breath * .008, 0, 0) * amount)
	rotate_bone(skeleton, "Head", Vector3(0, float(style[2]) * (.65 + .35 * sin(clock * .6)), 0) * amount)
	rotate_bone(skeleton, "L_Upperarm", Vector3(0, 0, float(style[1])) * amount)
	rotate_bone(skeleton, "R_Upperarm", Vector3(0, 0, -float(style[1])) * amount)
