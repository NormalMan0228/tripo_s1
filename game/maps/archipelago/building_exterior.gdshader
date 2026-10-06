shader_type spatial;
// Exterior look for the Tripo building GLBs (scripts/building_dressing.gd swaps it in
// for each building's baked StandardMaterial3D):
//  - anisotropic filtering on the baked atlas so walls and roofs stay crisp at the
//    follow camera's grazing angle;
//  - metallic noise from the ORM bake damped and a roughness floor, so plaster and
//    shingles do not turn grey-metallic under the flat Compatibility ambient;
//  - soft contact shading over the bottom metre where walls meet the ground;
//  - back faces: thin open sheets seen from behind (windmill sails, awnings, the
//    undersides of roof rows) keep their texture, a little shaded, like a two-sided
//    material. Deep cracks into the hollow shell no longer show back faces: the GLBs
//    carry patch quads behind them (tools/patch_building_holes.py);
//  - window glass (dark teal/blue texels on upright faces) glows warm at night;
//  - screen-door fade (scripts/occluder_fade.gd) when the building hides the walker:
//    a 4x4 dither drops pixels, so it stays in the opaque pass with no sorting cost.
render_mode cull_disabled;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_orm = true;
uniform bool has_normal = true;
uniform float metallic_scale = 0.3;
uniform float roughness_floor = 0.55;
uniform float normal_depth = 1.0;
uniform float base_shade = 0.32;
uniform float base_height = 0.9;
// Back faces: texture times this (no specular), lit with the flipped normal.
uniform float backface_shade = 0.8;
// 0 by day, 1 at night (Daylight.sample().night).
uniform float night = 0.0;
uniform vec3 glow_color : source_color = vec3(1.0, 0.70, 0.36);
uniform float glow_energy = 1.6;
// Glass texels: bluish/teal and darker than this luma (blue walls are brighter).
uniform float glass_max_luma = 0.40;
uniform float glass_min_tint = 0.07;
// Local heights between which windows can glow (keeps roofs and plinths dark).
uniform vec2 glow_band = vec2(0.6, 7.5);
// 0 = solid, 1 = as see-through as the dither allows (about 60% of pixels dropped).
uniform float fade = 0.0;
const float BAYER[16] = {0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0};

varying vec3 local_pos;
varying vec3 local_normal;

void vertex() {
	local_pos = VERTEX;
	local_normal = NORMAL;
}

void fragment() {
	if (fade > 0.001) {
		int cell = (int(FRAGCOORD.y) % 4)*4+int(FRAGCOORD.x) % 4;
		if ((BAYER[cell]+0.5)/16.0 < fade*0.6) discard;
	}
	vec3 base = texture(albedo_tex, UV).rgb;
	float contact = mix(1.0-base_shade, 1.0, smoothstep(0.0, base_height, local_pos.y));
	ALBEDO = base*contact;
	vec3 orm = has_orm ? texture(orm_tex, UV).rgb : vec3(1.0, 1.0, 0.0);
	ROUGHNESS = max(orm.g, roughness_floor);
	METALLIC = orm.b*metallic_scale;
	if (has_normal) {
		NORMAL_MAP = texture(normal_tex, UV).rgb;
		NORMAL_MAP_DEPTH = normal_depth;
	}
	if (!FRONT_FACING) {
		ALBEDO *= backface_shade;
		ROUGHNESS = 1.0;
		METALLIC = 0.0;
		SPECULAR = 0.0;
	} else if (night > 0.001) {
		float luma = dot(base, vec3(0.299, 0.587, 0.114));
		float tint = max(base.g, base.b)-base.r;
		float glass = smoothstep(glass_min_tint, glass_min_tint+0.08, tint);
		// Teal or blue panes, not green awnings, shutters or roof tiles.
		glass *= smoothstep(0.62, 0.85, base.b/max(base.g, 0.01));
		glass *= 1.0-smoothstep(glass_max_luma-0.1, glass_max_luma, luma);
		glass *= 1.0-smoothstep(0.35, 0.6, abs(normalize(local_normal).y));
		glass *= smoothstep(glow_band.x, glow_band.x+0.25, local_pos.y)*(1.0-smoothstep(glow_band.y-0.4, glow_band.y, local_pos.y));
		// Darker glass reads as deeper room light; keep a little texture variation.
		float warmth = glass*(0.75+0.5*(1.0-luma/max(glass_max_luma, 0.01)));
		EMISSION = glow_color*glow_energy*warmth*night;
		ALBEDO = mix(ALBEDO, ALBEDO*0.35, glass*night);
	}
}
