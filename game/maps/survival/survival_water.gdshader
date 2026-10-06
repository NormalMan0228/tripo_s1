shader_type spatial;
render_mode cull_back, depth_draw_opaque;
// Pond, lake and frozen river surfaces. COLOR.r = 0 at the shore, 1 in deep water (baked by the
// map builder from the distance to the bank). Two scrolling copies of the village pond normal map.
uniform sampler2D surface_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 shallow_color : source_color = vec3(0.28, 0.62, 0.60);
uniform vec3 deep_color : source_color = vec3(0.07, 0.25, 0.33);
uniform vec3 foam_color : source_color = vec3(0.86, 0.94, 0.90);
uniform float frozen = 0.0;
uniform float flow_speed = 0.035;
uniform vec3 focus = vec3(0.0);
uniform vec3 haze_color : source_color = vec3(0.55, 0.66, 0.62);
uniform float haze_start = 30.0;
uniform float haze_end = 58.0;
uniform float night = 0.0;
varying vec3 world_position;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
void vertex(){world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){
    float depth=clamp(COLOR.r,0.0,1.0);
    float t=TIME*flow_speed*(1.0-frozen);
    vec2 uv=world_position.xz/7.0;
    vec3 n1=texture(surface_normal,uv+vec2(t,t*0.6)).rgb;
    vec3 n2=texture(surface_normal,uv*1.7+vec2(-t*0.8,t*0.4)).rgb;
    vec3 nm=normalize(n1+n2-1.0);
    vec3 water=mix(shallow_color,deep_color,smoothstep(0.0,0.85,depth));
    float edge=1.0-smoothstep(0.0,0.16,depth);
    float wobble=noise(world_position.xz*3.0+vec2(TIME*0.4,0.0));
    float foam=smoothstep(0.35,0.75,edge+wobble*0.35-0.25)*(1.0-frozen);
    vec3 ice=mix(vec3(0.70,0.84,0.90),vec3(0.50,0.70,0.82),depth)*(0.92+noise(world_position.xz*0.8)*0.16);
    float crack=smoothstep(0.03,0.0,abs(noise(world_position.xz*0.9)-0.5))*frozen;
    vec3 color=mix(water,ice,frozen);
    color=mix(color,foam_color,foam*0.85+edge*frozen*0.5);
    color=mix(color,vec3(0.95,0.98,1.0),crack*0.5);
    float far=smoothstep(haze_start,haze_end,length(world_position.xz-focus.xz));
    ALBEDO=mix(color,haze_color,far);
    NORMAL_MAP=mix(nm*0.5+0.5,vec3(0.5,0.5,1.0),frozen*0.6);
    NORMAL_MAP_DEPTH=0.6;
    ROUGHNESS=mix(0.08,0.22,frozen);
    METALLIC=0.0;
    SPECULAR=0.65;
    EMISSION=water*0.06*night*(1.0-frozen);
}
