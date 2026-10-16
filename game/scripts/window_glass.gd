extends RefCounted
## Window glass drawn whole (item 9): every pane of a building is one material, so all its panes
## brighten and darken together with the time of day. The panes are the building's own glass faces
## cut along the window outlines (tools/window_panes.py finds them on the facade renders, the user
## may draw them; tools/door_cutter.gd copies the faces: windows/<model>_glass.res). Each building
## gets a "WindowGlass" mesh over its panes (a few millimetres out along the normals, no collision)
## drawn by PANE_SHADER: by day the sky gradient of the hour (sky_top over sky_horizon, from
## Daylight.sample) reflected over a little of the painted glass, at night dark, or glowing warm while
## someone inside is awake (building_dressing.gd's room lights). Off unless ENABLED or --window-glass.
const DIR := "res://maps/archipelago/windows/"
const ENABLED := false
const NODE := "WindowGlass"
const DAY_ZENITH := Color("5f9fd6")
const PANE_SHADER := """
shader_type spatial;
render_mode cull_back;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float night = 0.0;
uniform float lit = 1.0;
uniform vec3 sky_top : source_color = vec3(0.45, 0.70, 0.86);
uniform vec3 sky_horizon : source_color = vec3(0.72, 0.89, 0.93);
uniform vec3 glow_color : source_color = vec3(1.0, 0.70, 0.36);
uniform float glow_energy = 1.6;
uniform float fade = 0.0;
const float BAYER[16] = {0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0};
void vertex() {
	VERTEX += NORMAL*0.004;
}
void fragment() {
	if (fade > 0.001) {
		int cell = (int(FRAGCOORD.y) % 4)*4+int(FRAGCOORD.x) % 4;
		if ((BAYER[cell]+0.5)/16.0 < fade*0.6) discard;
	}
	vec3 base = texture(albedo_tex, UV).rgb;
	vec3 bounce = mat3(INV_VIEW_MATRIX)*reflect(-VIEW, NORMAL);
	vec3 sky = mix(sky_horizon, sky_top, smoothstep(-0.45, 0.55, bounce.y));
	// One look for the whole pane: the sky over it, a little of the painted glass under it.
	vec3 pane = mix(sky, base, 0.3);
	float glow = night*lit;
	ALBEDO = pane*(1.0-0.75*night);
	ROUGHNESS = 0.15;
	METALLIC = 0.0;
	SPECULAR = 0.6;
	EMISSION = glow_color*glow_energy*glow*(0.85+0.3*(1.0-dot(base, vec3(0.333)))) + sky*0.2*(1.0-night);
}
"""
static var _shader: Shader

static func enabled() -> bool:
	return ENABLED or "--window-glass" in OS.get_cmdline_user_args()

## Puts the glass on every building whose model has panes; returns {building id: ShaderMaterial}.
static func install(buildings: Node, manifest: Dictionary, tuning: Dictionary) -> Dictionary:
	var panes := {}
	if buildings == null or not enabled(): return panes
	for spec: Dictionary in manifest.buildings:
		var building := buildings.get_node_or_null(String(spec.id)) as Node3D
		var path := DIR+String(spec.model).get_file().get_basename()+"_glass.res"
		if building == null or not ResourceLoader.exists(path): continue
		var mesh := load(path) as ArrayMesh
		if mesh == null or mesh.get_surface_count() == 0: continue
		if _shader == null:
			_shader = Shader.new()
			_shader.code = PANE_SHADER
		var material := ShaderMaterial.new()
		material.shader = _shader
		var source := mesh.surface_get_material(0) as BaseMaterial3D
		if source and source.albedo_texture: material.set_shader_parameter("albedo_tex", source.albedo_texture)
		var tune: Dictionary = tuning.get(String(spec.id), {})
		if tune.has("glow_energy"): material.set_shader_parameter("glow_energy", float(tune.glow_energy))
		var node := MeshInstance3D.new()
		node.name = NODE
		node.mesh = mesh
		node.material_override = material
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		building.add_child(node)
		panes[String(spec.id)] = material
	return panes

## {top, horizon} sky colours for a Daylight.sample() dictionary.
static func sky(values: Dictionary) -> Dictionary:
	var night := float(values.get("night", 0.0))
	var day := float(values.get("daylight", 1.0))
	var background: Color = values.get("background_color", Color("b8e3ee"))
	var haze: Color = values.get("fog_color", background)
	var sun: Color = values.get("sun_color", Color.WHITE)
	var low := (1.0-smoothstep(0.0, 0.45, day))*(1.0-night)
	return {"top": background.lerp(DAY_ZENITH, 0.5*day*(1.0-night)).darkened(0.18*night), "horizon": haze.lerp(sun, 0.5*low)}

static func update(panes: Dictionary, values: Dictionary) -> void:
	var colours := sky(values)
	for id in panes:
		var material: ShaderMaterial = panes[id]
		material.set_shader_parameter("night", float(values.get("night", 0.0)))
		material.set_shader_parameter("sky_top", colours.top)
		material.set_shader_parameter("sky_horizon", colours.horizon)
