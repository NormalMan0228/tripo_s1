from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'labs/terrain_lab'
SHADERS={
'ground_surface.gdshader': '''shader_type spatial;
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
''',
'waterfall.gdshader': '''shader_type spatial;
render_mode cull_back, blend_mix, depth_draw_never;
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
    ALPHA=mix(.96,.89,fall);
    if(stream_layer>.5){ALPHA*=smoothstep(.02,.17,UV.y)*mix(.24,.93,smoothstep(.29,.68,organic.r+fine.g*.13));}
}
''',
'waterfall_splash.gdshader': '''shader_type spatial;
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
''',
'water_surface.gdshader': '''shader_type spatial;
render_mode cull_disabled;
uniform sampler2D surface_color : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D surface_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D current_field : filter_linear, repeat_disable;
uniform sampler2D coast_field : filter_linear, repeat_disable;
uniform sampler2D shore_distance : filter_linear, repeat_disable;
uniform sampler2D organic_foam : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D depth_texture : hint_depth_texture, filter_nearest, repeat_disable;
uniform int water_kind=0;
uniform int debug_view=0;
uniform vec2 pool_center=vec2(0);
uniform vec2 pool_radii=vec2(12,9);
varying vec3 world_position;
void vertex(){
    world_position=(MODEL_MATRIX*vec4(VERTEX,1)).xyz;
    vec2 uv=(world_position.xz+vec2(130,110))/vec2(260,225);
    float d=texture(coast_field,uv).b*16.0;
    float amplitude=water_kind==0 ? .025*smoothstep(.4,5.0,d) : (water_kind==1 ? 0.0 : .007);
    VERTEX.y+=amplitude*(sin(world_position.x*.68+world_position.z*.35-TIME*1.35)+.43*sin(world_position.x*1.1-world_position.z*.75-TIME*1.83));
}
void fragment(){
    vec2 p=world_position.xz,field_uv=(p+vec2(130,110))/vec2(260,225);
    vec4 field=texture(current_field,field_uv);
    vec2 direction=normalize(field.rg*2.0-1.0+vec2(.001));float speed=field.b*2.0;
    if(water_kind==1){direction=vec2(1,0);speed=0.0;}
    if(water_kind==2){direction=normalize(vec2(.2,-8.7)-p+vec2(.001));speed=mix(.12,1.35,1.0-smoothstep(.2,4.5,length(p-vec2(.2,-8.7))));}
    float phase_a=fract(TIME*.09),phase_b=fract(TIME*.09+.5);
    vec3 n1=texture(surface_normal,(p-direction*speed*phase_a/.09)/18.0).rgb;
    vec3 n2=texture(surface_normal,(p-direction*speed*phase_b/.09)/18.0+vec2(.11,.27)).rgb;
    vec3 detail=mix(n1,n2,abs(phase_a-.5)*2.0);
    float scene_depth=texture(depth_texture,SCREEN_UV).r;
    vec4 opaque_view=INV_PROJECTION_MATRIX*vec4(SCREEN_UV*2.0-1.0,scene_depth,1);opaque_view/=opaque_view.w;
    float depth=max(world_position.y-(INV_VIEW_MATRIX*opaque_view).y,0.0);
    vec4 shore=texture(shore_distance,field_uv);
    float bank=((shore.r*256.0+shore.g)/257.0)*48.0-24.0;
    // These fields belong to this archipelago only. Outside the sampled domain
    // the sea stays deep; the old painted island masks must never repeat.
    bool in_map=all(greaterThanEqual(field_uv,vec2(0)))&&all(lessThanEqual(field_uv,vec2(1)));
    if(!in_map){bank=24.0;}
    vec2 inward=normalize(shore.ba*2.0-1.0+vec2(.0001));
    float shallow=water_kind==0 ? 1.0-smoothstep(.2,8.0,bank) : 1.0-smoothstep(.12,3.5,depth);
    vec3 organic=texture(organic_foam,p/3.5-inward*TIME*.13).rgb;
    float subtle=texture(organic_foam,(p-direction*TIME*speed)/14.0).r;
    vec3 color=mix(vec3(.006,.21,.40),vec3(.022,.43,.46),shallow)*(.94+.12*subtle);
    if(water_kind==1){
        vec2 q=(p-pool_center)/pool_radii;
        float angle=atan(q.y,q.x);
        float radius=length(q)/(1.0+.09*sin(3.0*angle+.7)+.05*cos(5.0*angle));
        float jewel_depth=1.0-smoothstep(.35,1.08,radius);
        vec3 still=texture(organic_foam,p/9.0+vec2(.37,.16)).rgb;
        float caustic=(1.0-smoothstep(.018,.075,abs(still.r-.52)))*.07;
        color=mix(vec3(.026,.48,.47),vec3(.004,.22,.39),jewel_depth);
        color*=.95+.10*still.g;
        color+=vec3(.05,.22,.22)*caustic*(.40+.60*jewel_depth);
    }
    if(water_kind==2)color=vec3(.006,.26,.40)*(.94+.13*subtle);
    float coast_zone=water_kind==0 ? (1.0-smoothstep(.25,2.5,bank))*smoothstep(-.18,.20,bank) : 1.0-smoothstep(.08,.65,depth);
    // Project onto the shoreline, so a region's timing stays coherent across
    // the incoming wave. Smooth texture fields avoid visible sector borders.
    vec2 coast_anchor=p+inward*max(bank,0.0);
    vec3 region=textureLod(organic_foam,coast_anchor/144.0+vec2(.173,.417),4.0).rgb;
    vec3 region_slow=textureLod(organic_foam,coast_anchor/207.0+vec2(.619,.281),4.0).rgb;
    float offset=region.r*23.0+region.g*11.0;
    float offset_slow=region_slow.r*21.0+region_slow.g*9.0;
    float modulation=sin(TIME*.211+offset_slow)*.75;
    float leading=.5+.5*sin(bank*3.8+TIME*1.43+offset+modulation);
    float following=.5+.5*sin(bank*3.2+TIME*.9174+offset_slow);
    float activity=smoothstep(-.42,.58,sin(TIME*.2269+offset_slow)*.65+sin(TIME*.1382+offset)*.35);
    float strength=mix(.045,1.10,activity)*mix(.72,1.0,region.g);
    float surge=smoothstep(.56,.93,leading*.82+following*.18)*strength;
    float breakup=smoothstep(.33,.70,organic.r);
    float foam=coast_zone*surge*(breakup*.49+organic.b*.50);
    if(water_kind==0){foam*=smoothstep(.01,.13,depth);}
    if(water_kind!=0){foam=0.0;}
    ALBEDO=mix(color,vec3(.83,.96,.94),clamp(foam,0.0,.80));
    vec3 normal_world=normalize(vec3((detail.r-.5)*.34*(1.0-foam*.7),1.0,(detail.g-.5)*.34*(1.0-foam*.7)));
    if(water_kind==1){normal_world=vec3(0,1,0);}
    NORMAL=normalize((VIEW_MATRIX*vec4(normal_world,0)).xyz);
    ROUGHNESS=mix(.23,.68,foam);SPECULAR=.32;
    if(water_kind==1){
        float fresnel=pow(1.0-clamp(dot(NORMAL,VIEW),0.0,1.0),4.0);
        ALBEDO=mix(color,vec3(.22,.61,.67),fresnel*.40);
        ROUGHNESS=.17;SPECULAR=.48;
    }
    if(debug_view==1){ALBEDO=vec3(0);EMISSION=vec3(depth/8.0);}
}
'''}
body=SHADERS['waterfall.gdshader'].replace('render_mode cull_back, blend_mix, depth_draw_never;','render_mode cull_back;')
body=body.replace('    ALPHA=mix(.96,.89,fall);\n','').replace('    if(stream_layer>.5){ALPHA*=smoothstep(.02,.17,UV.y)*mix(.24,.93,smoothstep(.29,.68,organic.r+fine.g*.13));}\n','')
SHADERS['waterfall_body.gdshader']=body
for name,content in SHADERS.items():
    (OUT/name).write_text(content,encoding='utf-8')
print('V6_SHADERS_WRITTEN')
