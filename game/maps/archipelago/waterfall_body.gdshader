shader_type spatial;
render_mode cull_back;
uniform sampler2D surface_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D organic_foam : filter_linear_mipmap_anisotropic, repeat_enable;
uniform float stream_layer=0.0;
uniform float stream_seed=0.0;
uniform float flight_duration=.81712;
varying vec3 world_position;
void vertex(){
    float falling=smoothstep(.02,.25,UV.y);
    float ripple=texture(organic_foam,vec2(UV.x*1.7+stream_seed,UV.y-TIME)).r-.5;
    VERTEX+=NORMAL*ripple*.035*falling;
    float drift=texture(organic_foam,vec2(stream_seed+.37,(UV.y-TIME)*.43)).r-.5;
    VERTEX+=vec3(.692,0,-.722)*drift*.15*falling*stream_layer;
    float upstream=1.0-smoothstep(-.25,0.0,UV.y);
    VERTEX.y+=upstream*(sin(UV.y*3.1-TIME*3.1+UV.x*2.2)*.009+sin(UV.y*5.3-TIME*5.3-UV.x*3.7)*.004);
    world_position=(MODEL_MATRIX*vec4(VERTEX,1)).xyz;
}
void fragment(){
    float fall=smoothstep(-.03,.28,UV.y),lower=smoothstep(.36,flight_duration,UV.y);
    // Travel-time coordinates advect continuously and accelerate with gravity.
    float travel=UV.y-TIME;
    vec3 organic=texture(organic_foam,vec2(UV.x*1.45+stream_seed,travel*.68)).rgb;
    vec3 fine=texture(organic_foam,vec2(UV.x*2.6+stream_seed+.31,travel*1.7)).rgb;
    float aeration=smoothstep(.40,.76,organic.r+.12*fine.g);
    float foam=clamp(fall*(aeration*.50+lower*(fine.g*.26+fine.b*.30))+stream_layer*.17*fall,0.0,.84);
    vec2 direction=normalize(mix(vec2(.93,.36),vec2(.722,.692),smoothstep(-1.3,0.0,UV.y)));
    float source_speed=mix(.12,1.35,1.0-smoothstep(.2,4.5,length(world_position.xz-vec2(.2,-8.7))));
    vec3 source_flow=texture(organic_foam,vec2(UV.x*1.1,travel*.48)).rgb;
    float upstream=source_flow.r;
    float tracer=smoothstep(.52,.77,source_flow.r+source_flow.g*.15)*(.09+.08*smoothstep(-1.8,0.0,UV.y));
    vec3 headwater_tint=mix(vec3(.006,.26,.40)*(.92+.18*upstream),vec3(.17,.64,.66),tracer);
    ALBEDO=mix(mix(headwater_tint,vec3(.006,.26,.40)*(.94+.13*organic.r),fall),vec3(.85,.97,.96),foam);
    ROUGHNESS=mix(.28,.46,fall)+foam*.14;SPECULAR=mix(.26,.20,fall);
    float phase_a=fract(TIME*.09),phase_b=fract(TIME*.09+.5);
    vec3 normal_a=texture(surface_normal,(world_position.xz-direction*source_speed*phase_a/.09)/18.0).rgb;
    vec3 normal_b=texture(surface_normal,(world_position.xz-direction*source_speed*phase_b/.09)/18.0+vec2(.11,.27)).rgb;
    vec3 detail=mix(normal_a,normal_b,abs(phase_a-.5)*2.0);
    float drift_x=texture(organic_foam,vec2(UV.x*1.1+.009,travel*.48)).r-source_flow.r;
    float drift_y=texture(organic_foam,vec2(UV.x*1.1,travel*.48+.009)).r-source_flow.r;
    vec2 moving_slope=vec2(drift_x,drift_y)*.28;
    vec3 up_world=normalize(vec3((detail.r-.5)*.34+moving_slope.x,1.0,(detail.g-.5)*.34+moving_slope.y));
    vec3 source_view=normalize((VIEW_MATRIX*vec4(up_world,0)).xyz);
    vec3 perturb=(VIEW_MATRIX*vec4(vec3((fine.r-.5)*.065,(organic.g-.5)*.03,(fine.g-.5)*.065),0)).xyz;
    NORMAL=normalize(mix(source_view,NORMAL+perturb,max(fall,stream_layer)));
}
