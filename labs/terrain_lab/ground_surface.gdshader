shader_type spatial;
uniform sampler2D macro_color : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D macro_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D grass_detail : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_detail : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_detail : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D headland_normals : filter_linear, repeat_disable;
varying vec3 world_position;
varying vec3 world_normal;
void vertex(){world_position=(MODEL_MATRIX*vec4(VERTEX,1)).xyz;world_normal=MODEL_NORMAL_MATRIX*NORMAL;}
void fragment(){
    vec3 macro=texture(macro_color,UV).rgb;
    vec2 detail_uv=world_position.xz/4.0;
    float grass=smoothstep(.10,.32,macro.g-macro.r);
    vec3 grain=mix(texture(sand_detail,detail_uv).rgb,texture(grass_detail,detail_uv).rgb,grass);
    vec3 color=macro*(.86+grain*.30);
    float headland_radius=length((world_position.xz-vec2(-2.6,-10.3))/vec2(4.8,3.6));
    float headland=1.0-smoothstep(1.65,2.15,headland_radius);
    vec2 normal_uv=(world_position.xz+vec2(14,20))/21.0;
    vec3 sampled=normalize(texture(headland_normals,normal_uv).rgb*2.0-1.0);
    vec3 canonical=normalize(mix(normalize(world_normal),sampled,headland));
    // Continuous height bands and a shared height normal field keep the
    // cliff independent of individual triangles and projected UV tangents.
    float slope=1.0-abs(canonical.y);
    float cliff=smoothstep(.24,.51,slope)*headland;
    float cap=smoothstep(2.72,3.50,world_position.y);
    vec3 weights=pow(abs(canonical),vec3(4));weights/=dot(weights,vec3(1));
    vec3 stone=texture(rock_detail,world_position.yz/3.0).rgb*weights.x+texture(rock_detail,world_position.xz/3.0).rgb*weights.y+texture(rock_detail,world_position.xy/3.0).rgb*weights.z;
    vec3 earth=vec3(.27,.26,.12)*(grain*.18+.92);
    vec3 turf=vec3(.20,.40,.045)*(.90+grain*.22);
    vec3 band=mix(stone,earth,smoothstep(2.10,2.82,world_position.y));
    band=mix(band,turf,cap);
    // A smooth height band also covers the slope's base, where slope gates
    // otherwise expose the triangulated intersection with the surrounding sand.
    band=mix(macro*(.86+grain*.30),band,smoothstep(.12,.60,world_position.y));
    color=mix(color,band,headland);
    float wet=1.0-smoothstep(.08,.42,world_position.y);
    ALBEDO=color*mix(1.0,.78,wet);
    vec3 detail=mix(texture(sand_normal,detail_uv).rgb,texture(grass_normal,detail_uv).rgb,grass)*2.0-1.0;
    canonical=normalize(canonical+vec3(detail.r,0,detail.g)*.045*smoothstep(.70,.95,canonical.y));
    NORMAL=normalize((VIEW_MATRIX*vec4(canonical,0)).xyz);
    ROUGHNESS=mix(.91,.57,wet);SPECULAR=.20;
}
