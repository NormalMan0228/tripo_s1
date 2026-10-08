// The painter's live view of one surface: the backdrop (the unpainted look) with up to eight
// layers on top, blended like paint_core.gd composite() (sRGB values, normal / multiply /
// screen / overlay / add, layer opacity), then lit. tile maps the surface's own UVs into its
// square of the paint atlas.
shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D backdrop : filter_linear, repeat_disable;
uniform sampler2D layer0 : filter_linear, repeat_disable;
uniform sampler2D layer1 : filter_linear, repeat_disable;
uniform sampler2D layer2 : filter_linear, repeat_disable;
uniform sampler2D layer3 : filter_linear, repeat_disable;
uniform sampler2D layer4 : filter_linear, repeat_disable;
uniform sampler2D layer5 : filter_linear, repeat_disable;
uniform sampler2D layer6 : filter_linear, repeat_disable;
uniform sampler2D layer7 : filter_linear, repeat_disable;
// Per layer: opacity (0 = hidden) and blend mode.
uniform float opacity[8];
uniform int modes[8];
uniform int layer_count = 1;
uniform vec4 tile = vec4(1.0, 1.0, 0.0, 0.0);
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap;
uniform float normal_amount = 0.0;
uniform float roughness_value = 0.85;

vec3 mode_mix(vec3 base, vec3 top, int mode) {
	if (mode == 1) return base * top;
	if (mode == 2) return base + top - base * top;
	if (mode == 3) return mix(2.0 * base * top, 1.0 - 2.0 * (1.0 - base) * (1.0 - top), step(0.5, base));
	if (mode == 4) return min(vec3(1.0), base + top);
	return top;
}

vec3 over(vec3 base, vec4 paint, int index) {
	float a = paint.a * opacity[index];
	if (a <= 0.0) return base;
	return mix(base, mode_mix(base, paint.rgb, modes[index]), a);
}

vec3 to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c));
}

void fragment() {
	vec2 own = UV;
	if (own.x < 0.0 || own.x > 1.0 || own.y < 0.0 || own.y > 1.0) own = fract(own);
	vec2 uv = own * tile.xy + tile.zw;
	vec3 c = texture(backdrop, uv).rgb;
	if (layer_count > 0) c = over(c, texture(layer0, uv), 0);
	if (layer_count > 1) c = over(c, texture(layer1, uv), 1);
	if (layer_count > 2) c = over(c, texture(layer2, uv), 2);
	if (layer_count > 3) c = over(c, texture(layer3, uv), 3);
	if (layer_count > 4) c = over(c, texture(layer4, uv), 4);
	if (layer_count > 5) c = over(c, texture(layer5, uv), 5);
	if (layer_count > 6) c = over(c, texture(layer6, uv), 6);
	if (layer_count > 7) c = over(c, texture(layer7, uv), 7);
	ALBEDO = to_linear(clamp(c, 0.0, 1.0));
	ROUGHNESS = roughness_value;
	if (normal_amount > 0.0) {
		NORMAL_MAP = texture(normal_texture, UV).rgb;
		NORMAL_MAP_DEPTH = normal_amount;
	}
}
