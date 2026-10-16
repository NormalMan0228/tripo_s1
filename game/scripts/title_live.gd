extends RefCounted
## Quiet life on a still painting (the title art): soft cloud shadows drift across it and the sea
## glints where the painting is bright and blue, all in one canvas shader on the TextureRect (no
## resampling of the picture, so nothing shimmers like the old slow zoom did). Off with calm().
const RpgUi = preload("res://scripts/rpg_ui.gd")

const SHADER := """
shader_type canvas_item;
uniform float shadow_strength = 0.06;
uniform float glint_strength = 0.22;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
void fragment() {
	vec4 c = texture(TEXTURE, UV);
	float t = TIME;
	// Cloud shadows: two slow noise layers drifting right, a few percent darker in their cores.
	float cloud = noise(UV * vec2(3.0, 2.0) + vec2(t * 0.012, 0.0)) * 0.6 + noise(UV * vec2(6.0, 4.0) + vec2(t * 0.02, t * 0.004)) * 0.4;
	c.rgb *= 1.0 - shadow_strength * smoothstep(0.55, 0.85, cloud);
	// Glints: bright, blue-leaning pixels (the sea under the sun) twinkle in small cells.
	float lum = dot(c.rgb, vec3(0.299, 0.587, 0.114));
	float water = smoothstep(0.02, 0.12, c.b - c.r) * smoothstep(0.45, 0.8, lum);
	vec2 cell = floor(UV * vec2(420.0, 260.0));
	float spark = pow(max(0.0, sin(t * (1.2 + hash(cell) * 2.0) + hash(cell + 3.1) * 6.283)), 24.0) * step(0.86, hash(cell + 7.7));
	c.rgb += vec3(1.0, 0.97, 0.9) * glint_strength * spark * water;
	COLOR = c;
}
"""
static var _shader: Shader

static func apply(art: TextureRect) -> void:
	if not is_instance_valid(art) or RpgUi.calm(): return
	if _shader == null:
		_shader = Shader.new()
		_shader.code = SHADER
	var m := ShaderMaterial.new()
	m.shader = _shader
	art.material = m
