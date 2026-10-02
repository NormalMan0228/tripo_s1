shader_type spatial;
uniform vec4 shallow : source_color = vec4(0.25,0.65,0.66,1.0);
uniform vec4 deep : source_color = vec4(0.12,0.37,0.45,1.0);
varying vec3 world;
void vertex(){world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz; VERTEX.y+=sin(world.x*0.4+TIME*0.6)*0.05+sin(world.z*0.6+TIME*0.7)*0.025;}
void fragment(){float swell=sin(world.x*0.65+world.z*0.42+sin(world.z*0.65+TIME*0.4)+TIME*0.55); float line=pow(max(0.0,sin(world.x*1.4-world.z*1.8+sin(world.x*0.7)+TIME*0.7)),26.0)*smoothstep(0.1,0.8,sin(world.z*2.0+world.x)); ALBEDO=mix(deep.rgb,shallow.rgb,0.45+swell*0.13)+vec3(0.015,0.025,0.025)*line; ROUGHNESS=0.5;SPECULAR=0.3;}
