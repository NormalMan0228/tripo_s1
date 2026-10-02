shader_type spatial;
render_mode unshaded,cull_disabled;
void fragment(){vec2 p=UV*2.0-1.0;float glow=sin(length(p)*16.0-TIME*2.0)*0.07;ALBEDO=mix(vec3(0.10,0.32,0.32),vec3(0.61,0.88,0.68),1.0-length(p)*0.6+glow);EMISSION=ALBEDO*0.3;}
