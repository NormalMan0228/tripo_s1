shader_type spatial;
uniform sampler2D rock_detail : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
varying vec3 world_position;
varying vec3 world_normal;
void vertex(){world_position=(MODEL_MATRIX*vec4(VERTEX,1)).xyz;world_normal=MODEL_NORMAL_MATRIX*NORMAL;}
void fragment(){
    vec3 w=pow(abs(normalize(world_normal)),vec3(4));w/=dot(w,vec3(1));
    vec3 color=texture(rock_detail,world_position.yz/3.0).rgb*w.x+texture(rock_detail,world_position.xz/3.0).rgb*w.y+texture(rock_detail,world_position.xy/3.0).rgb*w.z;
    float wet=1.0-smoothstep(.06,.62,world_position.y);
    ALBEDO=color*mix(1.08,.63,wet);ROUGHNESS=mix(.84,.43,wet);SPECULAR=.25;
}
