shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;
uniform float phase = 0.0;
void vertex() {
    float h = 1.0 - UV.y;
    VERTEX.x += sin(TIME * 4.2 + h * 6.0 + phase) * h * h * 0.10;
    VERTEX.y += sin(TIME * 5.0 + phase) * h * 0.07;
}
void fragment() {
    float h = 1.0 - UV.y;
    float x = abs(UV.x - 0.5) * 2.0;
    float wave = sin(h * 13.0 - TIME * 6.0 + phase) * 0.075;
    float width = pow(max(0.0, 1.0 - h), 0.70) * (0.85 + wave);
    float edge = 1.0 - smoothstep(width - 0.12, width, x);
    float base = smoothstep(0.0, 0.08, h);
    float tip = 1.0 - smoothstep(0.90, 1.0, h);
    float core = (1.0 - smoothstep(0.08, 0.48, x)) * (1.0 - smoothstep(0.1, 0.72, h));
    ALBEDO = mix(vec3(1.0,0.34,0.055),vec3(1.0,0.90,0.47),core);
    ALPHA = edge * base * tip * 0.90;
    if (ALPHA < 0.02) discard;
}
