shader_type spatial;
render_mode cull_disabled;
// Living water for the ponds and the spring pool. A drop-in replacement for
// water_surface.gdshader: the same uniforms, the ocean path (water_kind 0) is
// unchanged, and water_kind 1 (pond) / 2 (spring pool) gain motion.
// The pond meshes are 128-triangle fans, so the visible waves are per-pixel
// normals; the vertex swell only shows on a subdivided mesh and stays tiny.
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
group_uniforms motion;
// Every motion control is optional; the defaults are the reviewed look.
uniform float motion_speed : hint_range(0.0, 3.0) = 1.0;
uniform float wave_height : hint_range(0.0, 0.1) = 0.02;
uniform float swell_strength : hint_range(0.0, 1.0) = 0.30;
uniform float ripple_strength : hint_range(0.0, 1.5) = 0.55;
uniform float ring_strength : hint_range(0.0, 2.0) = 1.0;
uniform float sparkle_strength : hint_range(0.0, 2.0) = 1.0;
uniform float caustic_strength : hint_range(0.0, 2.0) = 1.0;
uniform float sheen_strength : hint_range(0.0, 2.0) = 1.0;
uniform float edge_foam_strength : hint_range(0.0, 2.0) = 1.0;
group_uniforms;
varying vec3 world_position;
const float TWO_PI=6.28318530718;
const vec2 SPRING=vec2(.2,-8.7);

// One directional swell: height and slope direction (scaled by the slope gain later).
vec3 swell_wave(vec2 p,float t,vec2 d,float wavelength,float amplitude,float phase){
    float k=TWO_PI/wavelength;
    float x=dot(d,p)*k-t*sqrt(9.81*k)*.42+phase;
    return vec3(amplitude*sin(x),amplitude*cos(x)*d);
}
vec3 swell(vec2 p,float t){
    return swell_wave(p,t,vec2(.857,.514),3.3,.40,0.0)
        +swell_wave(p,t,vec2(.39,-.921),2.35,.28,1.7)
        +swell_wave(p,t,vec2(-.731,.682),1.62,.19,4.1)
        +swell_wave(p,t,vec2(.966,-.259),1.13,.13,2.6);
}
vec2 hash22(vec2 p){
    vec3 p3=fract(vec3(p.xyx)*vec3(.1031,.1030,.0973));
    p3+=dot(p3,p3.yzx+33.33);
    return fract((p3.xx+p3.yz)*p3.zy);
}
// Normalised radius of the pond's jewel ellipse (1 is roughly the deep rim).
float pool_radius(vec2 p){
    vec2 q=(p-pool_center)/pool_radii;
    float angle=atan(q.y,q.x);
    return length(q)/(1.0+.09*sin(3.0*angle+.7)+.05*cos(5.0*angle));
}

void vertex(){
    world_position=(MODEL_MATRIX*vec4(VERTEX,1)).xyz;
    vec2 uv=(world_position.xz+vec2(130,110))/vec2(260,225);
    float d=texture(coast_field,uv).b*16.0;
    if(water_kind==0){
        float amplitude=.025*smoothstep(.4,5.0,d);
        VERTEX.y+=amplitude*(sin(world_position.x*.68+world_position.z*.35-TIME*1.35)+.43*sin(world_position.x*1.1-world_position.z*.75-TIME*1.83));
    }else{
        // The rim stays put so the shoreline never pumps against the banks.
        float hold=water_kind==1 ? 1.0-smoothstep(.75,1.15,pool_radius(world_position.xz)) : 1.0-smoothstep(1.0,4.0,length(world_position.xz-SPRING));
        VERTEX.y+=wave_height*hold*swell(world_position.xz,TIME*motion_speed).x;
    }
}

void fragment(){
    vec2 p=world_position.xz,field_uv=(p+vec2(130,110))/vec2(260,225);
    vec4 field=texture(current_field,field_uv);
    vec2 direction=normalize(field.rg*2.0-1.0+vec2(.001));float speed=field.b*2.0;
    if(water_kind==1){direction=vec2(1,0);speed=0.0;}
    if(water_kind==2){direction=normalize(SPRING-p+vec2(.001));speed=mix(.12,1.35,1.0-smoothstep(.2,4.5,length(p-SPRING)));}
    float phase_a=fract(TIME*.09),phase_b=fract(TIME*.09+.5);
    vec3 n1=texture(surface_normal,(p-direction*speed*phase_a/.09)/18.0).rgb;
    vec3 n2=texture(surface_normal,(p-direction*speed*phase_b/.09)/18.0+vec2(.11,.27)).rgb;
    vec3 detail=mix(n1,n2,abs(phase_a-.5)*2.0);
    float scene_depth=texture(depth_texture,SCREEN_UV).r;
    // Water depth above the opaque bed. OpenGL (Compatibility) keeps depth NDC in
    // -1..1; water_surface.gdshader skips that remap, so its depth reads 0 there.
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
    vec4 opaque_view=INV_PROJECTION_MATRIX*vec4(vec3(SCREEN_UV,scene_depth)*2.0-1.0,1);
#else
    vec4 opaque_view=INV_PROJECTION_MATRIX*vec4(SCREEN_UV*2.0-1.0,scene_depth,1);
#endif
    opaque_view/=opaque_view.w;
    float depth=max(world_position.y-(INV_VIEW_MATRIX*opaque_view).y,0.0);
    vec4 shore=texture(shore_distance,field_uv);
    float bank=((shore.r*256.0+shore.g)/257.0)*48.0-24.0;
    bool in_map=all(greaterThanEqual(field_uv,vec2(0)))&&all(lessThanEqual(field_uv,vec2(1)));
    if(!in_map){bank=24.0;}
    vec2 inward=normalize(shore.ba*2.0-1.0+vec2(.0001));
    if(water_kind==0){
        // The open sea, exactly as water_surface.gdshader draws it, including its
        // depth term (no NDC remap), so swapping shaders never changes the ocean.
        vec4 legacy_view=INV_PROJECTION_MATRIX*vec4(SCREEN_UV*2.0-1.0,scene_depth,1);legacy_view/=legacy_view.w;
        depth=max(world_position.y-(INV_VIEW_MATRIX*legacy_view).y,0.0);
        float shallow=1.0-smoothstep(.2,8.0,bank);
        vec3 organic=texture(organic_foam,p/3.5-inward*TIME*.13).rgb;
        float subtle=texture(organic_foam,(p-direction*TIME*speed)/14.0).r;
        vec3 color=mix(vec3(.006,.21,.40),vec3(.022,.43,.46),shallow)*(.94+.12*subtle);
        float coast_zone=(1.0-smoothstep(.25,2.5,bank))*smoothstep(-.18,.20,bank);
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
        foam*=smoothstep(.01,.13,depth);
        ALBEDO=mix(color,vec3(.83,.96,.94),clamp(foam,0.0,.80));
        vec3 normal_world=normalize(vec3((detail.r-.5)*.34*(1.0-foam*.7),1.0,(detail.g-.5)*.34*(1.0-foam*.7)));
        NORMAL=normalize((VIEW_MATRIX*vec4(normal_world,0)).xyz);
        ROUGHNESS=mix(.23,.68,foam);SPECULAR=.32;
        if(debug_view==1){ALBEDO=vec3(0);EMISSION=vec3(depth/8.0);}
    }else{
        float t=TIME*motion_speed;
        vec3 view_world=normalize((INV_VIEW_MATRIX*vec4(VIEW,0)).xyz);
        bool pond=water_kind==1;
        float radius=pond ? pool_radius(p) : length(p-SPRING)/3.0;
        // Shallow margin: the measured depth to the bed when the opaque depth is
        // valid, otherwise the jewel ellipse.
        float margin=depth<40.0 ? 1.0-smoothstep(.06,1.4,depth) : smoothstep(.85,1.3,radius);
        // Wind gusts drift across as slow patches ("cat's paws") that roughen the surface.
        vec2 wind=normalize(vec2(.82,-.36));
        float gust=texture(organic_foam,p/26.0-wind*t*.016+vec2(.21,.63)).g;
        gust=.30+.70*smoothstep(.30,.72,gust);
        // 1. Gentle swell that matches the vertex displacement.
        vec3 s=swell(p,t);
        vec2 swell_slope=s.yz*swell_strength*.30;
        vec2 slope=vec2(0);
        // 2. Two wind-ripple normal layers at different scales, angles and speeds.
        mat2 r1=mat2(vec2(.940,.342),vec2(-.342,.940));
        mat2 r2=mat2(vec2(-.454,.891),vec2(-.891,-.454));
        vec2 w1=(texture(surface_normal,(r1*p)/6.3+vec2(.013,.047)*t).rg-.5)*r1;
        vec2 w2=(texture(surface_normal,(r2*p)/3.9+vec2(-.051,.019)*t+vec2(.37,.11)).rg-.5)*r2;
        slope+=(w1*.62+w2*.48)*ripple_strength*gust;
        if(!pond){
            // The spring keeps its current toward the waterfall as well.
            slope+=(detail.rg-.5)*.30;
        }
        // 3. Expanding ripple rings from a few random points (fish, falling leaves).
        vec2 ring_slope=vec2(0);float crest=0.0;
        for(int i=0;i<5;i++){
            float fi=float(i);
            float period=pond ? 3.7+fi*1.13 : 1.6+fi*.37;
            float cycle_time=t/period+fi*.618;
            float cycle=floor(cycle_time),age=fract(cycle_time);
            vec2 pick=hash22(vec2(fi*17.31+3.7,cycle*1.731+fi));
            float live=step(.18,hash22(vec2(cycle*7.13,fi*3.3)).x);
            vec2 spot=vec2(cos(pick.x*TWO_PI),sin(pick.x*TWO_PI))*sqrt(pick.y);
            vec2 source=pond ? pool_center+pool_radii*spot*.62 : SPRING+spot*1.6;
            vec2 offset=p-source;
            float dist=length(offset);
            float reach=pond ? 2.6 : 1.4;
            float x=dist-age*reach;
            float width=.12+.34*age;
            float envelope=exp(-x*x/(width*width));
            float fade=(1.0-age)*(1.0-age)*smoothstep(0.0,.06,age)*live;
            float k=TWO_PI/.46;
            float wave=sin(k*x);
            float radial=fade*envelope*(cos(k*x)-wave*2.0*x/(k*width*width));
            ring_slope+=radial*offset/max(dist,.001);
            crest+=fade*envelope*max(wave,0.0);
        }
        slope+=ring_slope*.24*ring_strength;
        // The shallows stay calmer; the rim does not shimmer against the bank.
        slope*=mix(1.0,.55,margin);
        swell_slope*=mix(1.0,.55,margin);
        vec3 normal_world=normalize(vec3(-slope.x-swell_slope.x,1.0,-slope.y-swell_slope.y));
        // Glints come from the fine ripples, so they scatter instead of pooling on swells.
        vec3 glint_normal=normalize(vec3(-slope.x-swell_slope.x*.3,1.0,-slope.y-swell_slope.y*.3));
        // Colour: the reviewed jewel pond, with its pattern drifting slowly.
        vec3 color;
        float deep;
        vec3 still=texture(organic_foam,p/9.0+vec2(.37,.16)+vec2(.0041,-.0027)*t).rgb;
        if(pond){
            deep=1.0-smoothstep(.35,1.08,radius);
            color=mix(vec3(.026,.48,.47),vec3(.004,.22,.39),deep);
            color*=.95+.10*still.g;
        }else{
            deep=1.0-margin;
            float subtle=texture(organic_foam,(p-direction*TIME*speed)/14.0).r;
            color=vec3(.006,.26,.40)*(.94+.13*subtle);
        }
        // 4. Caustic veins: two drifting fields cross, light gathers where they agree.
        float ca=texture(organic_foam,p/5.3+vec2(.031,.012)*t).r;
        float cb=texture(organic_foam,p/4.1+vec2(-.022,.027)*t+vec2(.5,.29)).r;
        float caustic=1.0-smoothstep(.012,.085,abs(ca-cb));
        caustic*=.06+.10*(1.0-deep);
        color+=vec3(.06,.24,.22)*caustic*caustic_strength;
        // Sky sheen: the reflected view sweeps between the bright horizon and the
        // deeper sky as the normals move, plus the original pond's fresnel tint.
        vec3 reflected=reflect(-view_world,normal_world);
        float facing=clamp(dot(normal_world,view_world),0.0,1.0);
        float fresnel=pow(1.0-facing,4.0);
        float sheen=smoothstep(.66,.26,reflected.y);
        color=mix(color,vec3(.24,.63,.69),clamp(fresnel*.62+sheen*.20*sheen_strength,0.0,.5));
        // Ring crests catch a little light.
        color+=vec3(.05,.12,.11)*clamp(crest,0.0,1.0)*ring_strength;
        // 5. Sparkle: glints where a wave tilts the reflected view onto a bright patch of sky.
        vec3 glint_dir=normalize(vec3(.10,.70,-1.0));
        float glint=pow(max(dot(reflect(-view_world,glint_normal),glint_dir),0.0),240.0);
        float twinkle=texture(organic_foam,p/1.9+vec2(.11,-.08)*t).g;
        glint*=smoothstep(.54,.64,twinkle)*gust;
        color+=vec3(1.0,.97,.88)*glint*.65*sparkle_strength;
        // 6. Edge foam: a thin rim that laps in and out, with froth patches behind it.
        float lap=.5+.5*sin(t*1.05+still.r*7.0+p.x*.35-p.y*.21);
        float froth=texture(organic_foam,p/2.4+vec2(.017,-.013)*t).g;
        float rim=depth<40.0 ? 1.0-smoothstep(.004,.020+.030*lap,depth) : 0.0;
        float band=depth<40.0 ? 1.0-smoothstep(.02,.09+.06*lap,depth) : 0.0;
        float foam=max(rim*(.40+.30*froth),band*smoothstep(.48,.64,froth+(lap-.5)*.18)*.45)*edge_foam_strength;
        foam=clamp(foam,0.0,.6);
        ALBEDO=mix(clamp(color,0.0,1.0),vec3(.80,.93,.90),foam);
        NORMAL=normalize((VIEW_MATRIX*vec4(normalize(mix(normal_world,vec3(0,1,0),foam)),0)).xyz);
        ROUGHNESS=mix(.17,.6,foam);SPECULAR=.48;
        if(debug_view==1){ALBEDO=vec3(0);EMISSION=vec3(depth/8.0);}
        if(debug_view==2){ALBEDO=vec3(0);EMISSION=normal_world*.5+.5;}
        if(debug_view==3){ALBEDO=vec3(0);EMISSION=vec3(margin,foam,glint);}
    }
}
