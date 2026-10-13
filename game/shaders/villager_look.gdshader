shader_type spatial;
// The daytime face of a shadow-folk resident (scripts/shadow_figure.gd with
// scripts/day_folk.gd): the rig's own texture with this villager's colours, lit like
// everyone else. Cloth surfaces are recoloured from their reference colour to `tint`
// (as shaders/avatar_tint.gdshader does for the player); the detail surface keeps the
// face and recolours only hair (dark browns) and skin (peach tones); props are a flat
// colour. `day` dissolves to the night silhouette pixel by pixel with the opposite
// pattern of shaders/shadow_silhouette.gdshader, so the two never overlap or leave a
// hole; `fade` dithers the figure in and out at doors.
render_mode cull_back, depth_draw_opaque;

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap, repeat_enable;
// 0 cloth, 1 detail (face, hair, skin), 2 flat colour
uniform int part = 0;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec4 reference_color : source_color = vec4(1.0);
uniform bool gold_cloth_only = false;
// sRGB, converted here (no source_color hint: the Compatibility renderer passes it as is).
uniform vec4 hair = vec4(0.25, 0.17, 0.14, 1.0);
uniform vec4 skin = vec4(0.85, 0.66, 0.55, 1.0);
uniform float day : hint_range(0.0, 1.0) = 1.0;
uniform float fade : hint_range(0.0, 1.0) = 1.0;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);
// The rig texture's own hair and skin, in sRGB.
const vec3 HAIR_SOURCE = vec3(0.25, 0.17, 0.14);
const vec3 SKIN_SOURCE = vec3(0.85, 0.66, 0.55);

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)))*43758.5453);
}

vec3 to_srgb(vec3 c) {
	return pow(max(c, vec3(0.0)), vec3(1.0/2.2));
}

vec3 to_linear(vec3 c) {
	return pow(max(c, vec3(0.0)), vec3(2.2));
}

void fragment() {
	vec2 cell = floor(FRAGCOORD.xy);
	if (fade < 0.999 && hash(cell) > fade) {
		discard;
	}
	if (day < 0.999 && hash(cell+vec2(37.0, 11.0)) >= day) {
		discard;
	}
	vec3 colour = tint.rgb;
	if (part == 0) {
		vec3 original = texture(albedo_texture, UV).rgb;
		float lightness = dot(original, LUMA);
		float reference_lightness = max(dot(reference_color.rgb, LUMA), 0.08);
		vec3 recoloured = tint.rgb*clamp(lightness/reference_lightness, 0.12, 1.35)*0.6;
		colour = recoloured;
		if (gold_cloth_only) {
			float warm = smoothstep(1.18, 1.40, original.r/max(original.g, 0.005));
			float yellow = smoothstep(1.35, 1.70, original.g/max(original.b, 0.005));
			colour = mix(original, recoloured, warm*yellow);
		}
	} else if (part == 1) {
		vec3 original = texture(albedo_texture, UV).rgb;
		vec3 s = to_srgb(original);
		float top = max(s.r, max(s.g, s.b));
		// Hair: dark and brown-to-neutral. Scaled so its shading carries over.
		float hair_weight = (1.0-smoothstep(0.30, 0.40, top))*step(s.b, s.r+0.02);
		vec3 hair_colour = to_linear(hair.rgb)*clamp(dot(original, LUMA)/max(dot(to_linear(HAIR_SOURCE), LUMA), 0.002), 0.2, 2.2);
		// Skin: warm peach, light. Multiplied toward this villager's tone.
		float skin_weight = smoothstep(0.62, 0.72, s.r)*smoothstep(0.06, 0.12, s.r-s.g)*smoothstep(0.03, 0.08, s.g-s.b)*(1.0-smoothstep(0.30, 0.40, s.r-s.b));
		vec3 skin_colour = original*(to_linear(skin.rgb)/max(to_linear(SKIN_SOURCE), vec3(0.02)));
		colour = mix(mix(original, hair_colour, hair_weight), skin_colour, skin_weight);
	}
	ALBEDO = colour;
	ROUGHNESS = 0.88;
}
