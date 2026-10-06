shader_type spatial;
// Flat near-black body for the shadow folk (scripts/shadow_figure.gd), in the spirit
// of the classic mystery-cartoon culprit: no lighting, a faint smoky grain so the
// black reads as cloth rather than a hole, and a dark navy rim so the outline still
// separates from the ground at night. `fade` dithers the figure in and out.
render_mode unshaded, cull_back, depth_draw_opaque;

uniform vec4 body_color : source_color = vec4(0.07, 0.075, 0.105, 1.0);
uniform vec4 rim_color : source_color = vec4(0.22, 0.30, 0.56, 1.0);
uniform float rim_strength = 0.3;
uniform float rim_power = 3.6;
uniform float grain = 0.22;
uniform float fade : hint_range(0.0, 1.0) = 1.0;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)))*43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f*f*(3.0-2.0*f);
	return mix(mix(hash(i), hash(i+vec2(1.0, 0.0)), f.x), mix(hash(i+vec2(0.0, 1.0)), hash(i+vec2(1.0, 1.0)), f.x), f.y);
}

void fragment() {
	if (fade < 0.999 && hash(floor(FRAGCOORD.xy)) > fade) {
		discard;
	}
	float facing = clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0);
	float rim = pow(1.0-facing, rim_power);
	float smoke = noise(UV*36.0)*0.65+noise(UV*121.0)*0.35;
	vec3 colour = body_color.rgb*(1.0+(smoke-0.5)*grain);
	colour += rim_color.rgb*rim*rim_strength;
	ALBEDO = colour;
}
