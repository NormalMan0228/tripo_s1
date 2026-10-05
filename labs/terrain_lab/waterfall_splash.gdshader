shader_type spatial;
render_mode cull_disabled, blend_mix, depth_draw_never;
uniform sampler2D depth_texture : hint_depth_texture, filter_nearest, repeat_disable;
uniform sampler2D organic_foam : filter_linear_mipmap_anisotropic, repeat_enable;
varying vec3 world_position;
void vertex(){world_position=(MODEL_MATRIX*vec4(VERTEX,1)).xyz;}
void fragment(){
    vec2 p=(UV-.5)*2.0;float r=length(p),angle=atan(p.y,p.x);
    float phase_a=fract(TIME*.31),phase_b=fract(TIME*.31+.5);
    vec3 a=texture(organic_foam,p/(.62+phase_a*.8)+vec2(.23,.51)).rgb;
    vec3 b=texture(organic_foam,p/(.62+phase_b*.8)+vec2(.23,.51)).rgb;
    vec3 organic=mix(a,b,abs(phase_a-.5)*2.0);
    float core=1.0-smoothstep(.05,.94,r);
    float density=smoothstep(.29,.70,organic.r)+organic.b*.55;
    float wave=.5+.5*sin(r*17.0-TIME*5.4+sin(angle*3.0)*.55+organic.g*.8);
    float skirt=pow(wave,5.0)*.15*(1.0-smoothstep(.48,.97,r));
    float scene_depth=texture(depth_texture,SCREEN_UV).r;
    vec4 view=INV_PROJECTION_MATRIX*vec4(SCREEN_UV*2.0-1.0,scene_depth,1);view/=view.w;
    float under_depth=world_position.y-(INV_VIEW_MATRIX*view).y;
    ALBEDO=mix(vec3(.13,.52,.55),vec3(.82,.94,.93),clamp(density,0.0,1.0));
    ROUGHNESS=.65;SPECULAR=.22;
    ALPHA=(core*(.25+density*.60)+skirt)*smoothstep(.015,.15,under_depth);
}
