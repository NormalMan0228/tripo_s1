shader_type spatial;
render_mode cull_back;
uniform sampler2D albedo_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec4 reference_color : source_color = vec4(1.0);
uniform bool skin_part = false;
uniform bool gold_cloth_only = false;
void fragment() {
	vec4 original = texture(albedo_texture, UV);
	float lightness = dot(original.rgb,vec3(0.2126,0.7152,0.0722));
	float reference_lightness = max(dot(reference_color.rgb,vec3(0.2126,0.7152,0.0722)),0.08);
	vec3 recolored = tint.rgb * clamp(lightness/reference_lightness,0.12,1.35) * 0.6;
	// Dark facial features remain intact; cloth keeps texture light and shade.
	ALBEDO = skin_part ? original.rgb * (tint.rgb/max(reference_color.rgb,vec3(0.08))) : recolored;
	if (gold_cloth_only) {
		float warm = smoothstep(1.18,1.40,original.r/max(original.g,0.005));
		float yellow = smoothstep(1.35,1.70,original.g/max(original.b,0.005));
		ALBEDO = mix(original.rgb,recolored,warm*yellow);
	}
	ROUGHNESS = 0.88;
}
