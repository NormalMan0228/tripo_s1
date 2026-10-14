shader_type spatial;
uniform vec4 timber_color : source_color = vec4(.55,.30,.12,1.0);
varying vec3 p;
float hash(vec3 v) { return fract(sin(dot(v,vec3(17.73,91.17,41.13)))*43758.5453); }
float noise(vec3 v) {
 vec3 i=floor(v),f=fract(v); f=f*f*(3.0-2.0*f);
 return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
void vertex() { p=VERTEX; }
void fragment() {
 float fibres=noise(p*vec3(.65,24.0,19.0));
 float broad=noise(p*vec3(.25,3.0,2.6));
 ALBEDO=timber_color.rgb*(.89+.15* broad+.12*fibres);
 ROUGHNESS=.79; SPECULAR=.24;
}
