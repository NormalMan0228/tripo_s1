shader_type spatial;
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
