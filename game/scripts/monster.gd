extends Node3D
## Tripo creature body for one survival monster (see game/assets/monsters/manifest.json).
## res://assets/monsters/<species>_<variant>.glb: faces +Z, feet on y=0, already in metres, clips
## idle/walk/run (loop), attack (strike lands at the server wind-up), hurt, death (+ roar for brute).
## shadow_beast.gd owns one of these and falls back to its procedural body when setup() fails.
## Night readability: a per-instance additive overlay adds a soft variant-coloured rim, re-lights the
## GLB's emission map (eyes, embers, ice, spores) and carries the hit flash, so the shared imported
## materials are never duplicated.
const DIR := "res://assets/monsters/"
const VARIANTS := ["forest", "quarry", "frost"]
const LOOPS := ["idle", "walk", "run"]
## Ground speed (m/s) matching speed_scale 1.0 of the walk / run clips.
## Mon_v3 species (Tripo P2, AI in-place clips): first estimate from height (1.1 / 2.6 m/s at 1.7 m),
## to be replaced by the stride measured in tools/body_gen/build_game_monster.py (ground_speed_mps).
const WALK_REF := {"wolf": 1.1, "boar": 0.9, "brute": 0.75, "wisp": 1.0, "shroom": 0.8,
	"goblin": 0.92, "werewolf": 1.16, "troll": 1.41, "cyclops": 1.56, "treant": 1.89, "skeleton": 1.1, "lizardman": 1.1, "minotaur": 1.44, "mummy_king": 1.28, "ghoul": 1.07, "ice_shardling": 1.0, "draugr": 1.16, "yeti": 1.36, "wendigo": 1.25, "frost_hag": 1.13, "frost_knight": 1.22, "ice_golem": 1.51, "glacier_giant": 1.6, "chimera": 1.46, "dragon": 1.89}
const RUN_REF := {"wolf": 2.4, "boar": 2.6, "brute": 1.3, "wisp": 2.0, "shroom": 1.5,
	"goblin": 2.18, "werewolf": 2.75, "troll": 3.34, "cyclops": 3.68, "treant": 4.46, "skeleton": 2.6, "lizardman": 2.6, "minotaur": 3.4, "mummy_king": 3.02, "ghoul": 2.52, "ice_shardling": 2.36, "draugr": 2.75, "yeti": 3.22, "wendigo": 2.96, "frost_hag": 2.68, "frost_knight": 2.89, "ice_golem": 3.57, "glacier_giant": 3.78, "chimera": 3.45, "dragon": 4.46}
const RIM := {"forest": Color("86d39a"), "quarry": Color("ff9a52"), "frost": Color("a8dcff")}
const OVERLAY_CODE := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back, shadows_disabled;
uniform sampler2D glow_map : source_color, filter_linear_mipmap;
uniform vec3 rim_color : source_color = vec3(0.5, 0.8, 0.6);
uniform float rim = 0.22;
uniform float glow = 0.6;
uniform float flash = 0.0;
void fragment() {
	float edge = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0);
	ALBEDO = rim_color * edge * rim + texture(glow_map, UV).rgb * glow + vec3(1.0, 0.88, 0.72) * flash * (0.35 + edge);
}
"""
static var overlay_shader: Shader

var species := "wolf"
var variant := "forest"
var model: Node3D
var player: AnimationPlayer
var clip := ""
var height := 1.0
var overlay: ShaderMaterial
var glow := 0.6
var rim := 0.22
var flash := 0.0
## Scale a stand-in is drawn at (shadow_beast.gd): the walk and run clips cover that much more ground.
var stride := 1.0

static func path_for(p_species: String, p_variant: String) -> String:
	return DIR + p_species + "_" + (p_variant if p_variant in VARIANTS else "forest") + ".glb"

static func available(p_species: String, p_variant := "") -> bool:
	for v in ([p_variant] if p_variant in VARIANTS else []) + VARIANTS:
		if ResourceLoader.exists(path_for(p_species, v)): return true
	return false

## The species whose model shows a creature: its own when it has one (any variant), else the
## stand-in the server names for it (server/catalog.py ENEMIES stand_in: today's art until the species
## gets a model), else the species (setup() then fails and the procedural body stands in).
static func art_species(p_species: String, p_stand_in: String, p_variant := "") -> String:
	if p_species != "" and available(p_species, p_variant): return p_species
	return p_stand_in if p_stand_in != "" else p_species

## The variant whose GLB setup() loads for species/variant: that one, else any other variant of the
## species that exists ("" when none does).
static func resolved_variant(p_species: String, p_variant: String) -> String:
	for v in ([p_variant] if p_variant in VARIANTS else []) + VARIANTS:
		if ResourceLoader.exists(path_for(p_species, v)): return v
	return ""

## The GLB setup() loads for species/variant ("" when there is none): the survival map reads it on
## a worker thread before the first night, so the spawn finds it in the resource cache.
static func resolved_path(p_species: String, p_variant: String) -> String:
	var v := resolved_variant(p_species, p_variant)
	return "" if v == "" else path_for(p_species, v)

## Loads the GLB for species/variant (any other variant of the species if that one is missing).
func setup(p_species: String, p_variant: String) -> bool:
	species = p_species
	var found := resolved_variant(species, p_variant)
	if found == "": return false
	variant = found
	var path := path_for(species, found)
	var scene := load(path) as PackedScene
	if scene == null: return false
	model = scene.instantiate() as Node3D
	if model == null: return false
	add_child(model)
	var players := model.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		model.queue_free()
		model = null
		return false
	player = players[0]
	for loop_name in LOOPS:
		if player.has_animation(loop_name): player.get_animation(loop_name).loop_mode = Animation.LOOP_LINEAR
	if overlay_shader == null:
		overlay_shader = Shader.new()
		overlay_shader.code = OVERLAY_CODE
	overlay = ShaderMaterial.new()
	overlay.shader = overlay_shader
	overlay.set_shader_parameter("rim_color", RIM[variant])
	var bounds := AABB()
	var first := true
	for mesh in model.find_children("*", "MeshInstance3D", true, false):
		var instance := mesh as MeshInstance3D
		instance.material_overlay = overlay
		for surface in instance.mesh.get_surface_count():
			var material := instance.get_active_material(surface) as StandardMaterial3D
			if material and material.emission_enabled and material.emission_texture:
				overlay.set_shader_parameter("glow_map", material.emission_texture)
		# Skinned GLB meshes are exported in the model root space (metres); the armature node's scale
		# only applies to the skeleton, so the rest AABB is already the in-game size.
		var box := instance.get_aabb() if instance.skin else relative_transform(instance, model) * instance.get_aabb()
		bounds = box if first else bounds.merge(box)
		first = false
	height = maxf(0.3, bounds.end.y) if not first else 1.0
	return true

func _ready() -> void:
	if player and has("idle"):
		play("idle", 0.0)
		player.seek(randf() * length("idle"), true)  # packs do not breathe in sync

static func relative_transform(node: Node3D, root: Node3D) -> Transform3D:
	var result := Transform3D.IDENTITY
	var current: Node = node
	while current and current != root:
		if current is Node3D: result = (current as Node3D).transform * result
		current = current.get_parent()
	return result

func has(clip_name: String) -> bool:
	return player != null and player.has_animation(clip_name)

func length(clip_name: String) -> float:
	return player.get_animation(clip_name).length if has(clip_name) else 0.0

func play(clip_name: String, blend := 0.15, speed := 1.0, restart := false) -> void:
	if not has(clip_name): return
	player.speed_scale = speed
	if clip == clip_name and not restart and player.is_playing(): return
	clip = clip_name
	player.play(clip_name, blend)
	if restart: player.seek(0.0, true)

func finished() -> bool:
	return player == null or not player.is_playing() or (clip not in LOOPS and player.current_animation_position >= length(clip) - 0.02)

## Locomotion clip and speed for a measured ground speed.
func locomote(ground_speed: float) -> void:
	var walk_ref: float = WALK_REF.get(species, 1.0)*stride
	var run_ref: float = RUN_REF.get(species, 2.0)*stride
	if ground_speed < 0.12:
		play("idle", 0.25)
	elif ground_speed > walk_ref * 1.55 and has("run"):
		play("run", 0.2, clampf(ground_speed / run_ref, 0.7, 2.2))
	else:
		play("walk", 0.2, clampf(ground_speed / walk_ref, 0.6, 1.6))

func hit_flash() -> void:
	flash = 1.0

func _process(delta: float) -> void:
	if overlay == null: return
	flash = maxf(0.0, flash - delta * 5.0)
	overlay.set_shader_parameter("glow", glow)
	overlay.set_shader_parameter("rim", rim)
	overlay.set_shader_parameter("flash", flash)
