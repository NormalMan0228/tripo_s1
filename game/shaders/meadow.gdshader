shader_type spatial;
render_mode cull_disabled;
uniform vec4 base_color : source_color = vec4(0.36,0.49,0.25,1.0);
uniform vec4 light_color : source_color = vec4(0.53,0.63,0.33,1.0);
varying vec3 world;
float hash(vec2 p) {return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
void vertex(){world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){float n=noise(world.xz*0.45)*0.65+noise(world.xz*2.5)*0.25+noise(world.xz*20.0)*0.1; ALBEDO=mix(base_color.rgb,light_color.rgb,smoothstep(0.1,0.85,n));ROUGHNESS=1.0;}
