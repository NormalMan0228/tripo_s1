shader_type spatial;
// Village paths (scripts/roads.gd). One draped ribbon mesh for every road, plaza and
// door apron. UV.x runs across a ribbon (-1..1 at the drawn edge, the nominal road
// edge sits at about +-0.77) or out from a plaza centre (0..1); UV.y is metres along.
// COLOR.r = 1 for cobbled main roads and plazas, 0 for packed-earth side paths.
// Edges fray into the meadow with world-space noise instead of a hard ribbon border.
render_mode blend_mix, depth_draw_never, cull_disabled;

uniform vec3 earth_light : source_color = vec3(0.80, 0.70, 0.52);
uniform vec3 earth_dark : source_color = vec3(0.62, 0.52, 0.37);
uniform vec3 stone_light : source_color = vec3(0.83, 0.79, 0.71);
uniform vec3 stone_dark : source_color = vec3(0.60, 0.57, 0.52);
uniform float cobble_size = 0.34;
uniform float bump = 0.9;

varying vec3 world;

void vertex() {
	world = (MODEL_MATRIX*vec4(VERTEX, 1.0)).xyz;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)))*43758.5453);
}

vec2 hash2(vec2 p) {
	return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3))))*43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f*f*(3.0-2.0*f);
	return mix(mix(hash(i), hash(i+vec2(1.0, 0.0)), u.x), mix(hash(i+vec2(0.0, 1.0)), hash(i+vec2(1.0, 1.0)), u.x), u.y);
}

// Voronoi: x = distance to the nearest centre, y = gap to the second, zw = cell id.
vec4 cells(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float d1 = 8.0;
	float d2 = 8.0;
	vec2 id = vec2(0.0);
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = 0.15+0.7*hash2(i+g);
			float d = length(g+o-f);
			if (d < d1) {
				d2 = d1;
				d1 = d;
				id = i+g;
			} else if (d < d2) {
				d2 = d;
			}
		}
	}
	return vec4(d1, d2-d1, id);
}

void fragment() {
	vec2 p = world.xz;
	float across = abs(UV.x);
	float cobbled = COLOR.r;
	// Ragged, soft edge.
	float fray = (noise(p*2.3)-0.5)*0.32+(noise(p*8.0)-0.5)*0.14;
	float a = across+fray;
	float alpha = 1.0-smoothstep(0.6, 0.95, a);
	// Packed earth: broad blotches, a lighter trodden centre, gravel specks.
	float blotch = noise(p*0.9)*0.6+noise(p*3.1)*0.4;
	vec3 dirt = mix(earth_dark, earth_light, smoothstep(0.2, 0.8, blotch));
	dirt *= mix(1.04, 0.9, smoothstep(0.15, 0.8, across));
	float speck = hash(floor(p*24.0));
	dirt = mix(dirt, dirt*vec3(1.16, 1.13, 1.08), step(0.92, speck)*0.85);
	dirt = mix(dirt, dirt*0.74, step(speck, 0.045));
	// Cobbles on main roads and plazas, worn into the earth towards the edges.
	vec4 c = cells(p/cobble_size);
	float mortar = 1.0-smoothstep(0.05, 0.17, c.y);
	float tone = hash(c.zw);
	vec3 stone = mix(stone_dark, stone_light, tone)*(0.92+0.16*noise(p*5.0));
	stone = mix(stone, stone*vec3(1.02, 0.97, 0.9), step(0.8, hash(c.zw+3.1)));
	float lay = cobbled*(1.0-smoothstep(0.42, 0.7, a));
	// A few stones missing in the middle too, so it reads hand-laid.
	lay *= 1.0-step(0.94, hash(c.zw+7.7))*0.85;
	vec3 surface = mix(dirt, mix(stone*(1.0-0.1*c.x), dirt*0.72, mortar), lay);
	ALBEDO = surface;
	// Bevelled stone tops (bump from the cell gap) catch the low sun and the lamps.
	float height = smoothstep(0.0, 0.28, c.y)*lay;
	vec3 dpdx = dFdx(VERTEX);
	vec3 dpdy = dFdy(VERTEX);
	vec3 r1 = cross(dpdy, NORMAL);
	vec3 r2 = cross(NORMAL, dpdx);
	float det = dot(dpdx, r1);
	vec3 grad = sign(det)*(dFdx(height)*r1+dFdy(height)*r2);
	NORMAL = normalize(abs(det)*NORMAL-grad*bump*0.03);
	ROUGHNESS = mix(0.95, 0.8, lay);
	SPECULAR = 0.25;
	ALPHA = alpha*COLOR.a;
}
