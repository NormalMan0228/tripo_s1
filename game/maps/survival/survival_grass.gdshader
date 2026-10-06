shader_type spatial;
render_mode cull_disabled, shadows_disabled;
// Ground-cover tufts (MultiMesh): vertex colour = base (dark) to tip (light) blend, INSTANCE_CUSTOM.r
// picks a tone between the map's two grass colours, .g a flower tint flag. Wind bends the tips.
uniform vec3 low_color : source_color = vec3(0.30, 0.45, 0.17);
uniform vec3 high_color : source_color = vec3(0.62, 0.70, 0.30);
uniform vec3 flower_a : source_color = vec3(0.98, 0.88, 0.55);
uniform vec3 flower_b : source_color = vec3(0.95, 0.70, 0.75);
uniform float wind = 0.12;
uniform vec3 focus = vec3(0.0);
uniform vec3 haze_color : source_color = vec3(0.55, 0.66, 0.62);
uniform float haze_start = 30.0;
uniform float haze_end = 58.0;
uniform float frost = 0.0;
varying vec3 tone;
varying float tip;
varying float far;
void vertex(){
    vec3 world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
    tip=COLOR.r;
    float sway=sin(TIME*1.6+world.x*0.7+world.z*0.5)*wind*VERTEX.y*VERTEX.y*4.0;
    VERTEX.x+=sway; VERTEX.z+=sway*0.5;
    vec3 base=mix(low_color,high_color,INSTANCE_CUSTOM.r);
    tone=COLOR.g>0.5 ? mix(flower_a,flower_b,INSTANCE_CUSTOM.g) : base;
    far=smoothstep(haze_start,haze_end,length(world.xz-focus.xz));
}
void fragment(){
    vec3 c=tone*mix(0.62,1.12,tip);
    c=mix(c,vec3(0.90,0.95,1.0),frost*tip*0.6);
    ALBEDO=mix(c,haze_color,far);
    ROUGHNESS=0.95;
    SPECULAR=0.1;
}
