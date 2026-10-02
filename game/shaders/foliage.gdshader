shader_type spatial;
render_mode cull_disabled;
uniform float wind = 0.08;
void vertex(){vec3 world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz; VERTEX.x+=sin(TIME*1.5+world.x*0.8+world.z)*wind*max(VERTEX.y,0.0);}
void fragment(){ALBEDO=pow(COLOR.rgb,vec3(2.2));ROUGHNESS=1.0;}
