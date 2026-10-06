shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;
// Tripo props in the survival maps (also used through MultiMesh). One material per prop and map:
// per-map tint, settled snow, wind sway for foliage, a screen-door see-through around the walker
// (main camera pass only, so shadows stay whole), dark backfaces where a crack shows the inside,
// a moonlit rim and optional glow (embers, crystals) at night, and the same distance haze as the ground.
uniform sampler2D albedo_texture : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic;
uniform bool use_normal = true;
uniform vec4 base_color : source_color = vec4(1.0);
uniform vec3 tint : source_color = vec3(1.0);
uniform float saturation = 1.0;
uniform float brightness = 1.0;
uniform float snow = 0.0;
uniform float wind = 0.0;          // sway amplitude (metres at 4 m height)
uniform float wind_height = 4.0;
uniform int glow_mode = 0;         // 0 none, 1 warm cracks, 2 cool crystal, 3 whole surface
uniform vec3 glow_color : source_color = vec3(1.0, 0.55, 0.2);
uniform float glow = 0.0;
uniform float night = 0.0;
uniform vec3 rim_color : source_color = vec3(0.45, 0.58, 0.85);
uniform vec3 focus = vec3(0.0);
uniform vec3 camera_world = vec3(0.0, 1000.0, 0.0);
uniform float see_through = 1.0;
uniform float see_radius = 1.7;
uniform vec3 haze_color : source_color = vec3(0.55, 0.66, 0.62);
uniform float haze_start = 30.0;
uniform float haze_end = 58.0;
varying vec3 world_position;
varying vec3 world_normal;

void vertex(){
    vec3 world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
    if(wind>0.0){
        float h=max(VERTEX.y,0.0)/wind_height;
        float sway=sin(TIME*1.3+world.x*0.37+world.z*0.29)+0.45*sin(TIME*2.7+world.x*0.9);
        vec3 push=vec3(sway,0.0,sway*0.6)*wind*h*h;
        VERTEX+=(inverse(mat3(MODEL_MATRIX))*push);
        world+=push;
    }
    world_position=world;
    world_normal=normalize((MODEL_MATRIX*vec4(NORMAL,0.0)).xyz);
}

float bayer(vec2 p){
    ivec2 q=ivec2(mod(p,4.0));
    int i=q.x+q.y*4;
    float m[16]=float[](0.0,8.0,2.0,10.0,12.0,4.0,14.0,6.0,3.0,11.0,1.0,9.0,15.0,7.0,13.0,5.0);
    return (m[i]+0.5)/16.0;
}

void fragment(){
    // Screen-door see-through: only fragments between the main camera and the walker.
    bool main_pass=distance(INV_VIEW_MATRIX[3].xyz,camera_world)<1.0;
    if(main_pass && see_through>0.0){
        vec3 eye=(VIEW_MATRIX*vec4(focus+vec3(0.0,0.9,0.0),1.0)).xyz;
        float across=length(VERTEX.xy-eye.xy);
        float front=smoothstep(0.4,1.2,VERTEX.z-eye.z);
        float fade=front*(1.0-smoothstep(see_radius*0.55,see_radius,across))*see_through*0.82;
        if(fade>bayer(FRAGCOORD.xy)) discard;
    }
    vec4 tex=texture(albedo_texture,UV)*base_color;
    vec3 color=tex.rgb;
    float grey=dot(color,vec3(0.299,0.587,0.114));
    color=mix(vec3(grey),color,saturation)*tint*brightness;
    vec3 n=normalize(world_normal);
    if(!FRONT_FACING){n=-n;color*=0.32;}
    float snowy=snow*smoothstep(0.25,0.75,n.y);
    color=mix(color,vec3(0.93,0.96,1.0),snowy);
    color=mix(color,vec3(dot(color,vec3(0.3,0.59,0.11)))*vec3(0.80,0.88,1.06),night*0.35);
    float far=smoothstep(haze_start,haze_end,length(world_position.xz-focus.xz));
    ALBEDO=mix(color,haze_color,far);
    if(use_normal && FRONT_FACING){
        NORMAL_MAP=texture(normal_texture,UV).rgb;
        NORMAL_MAP_DEPTH=0.8;
    }
    ROUGHNESS=mix(0.86,0.45,snowy*0.5);
    SPECULAR=0.25;
    vec3 emit=vec3(0.0);
    if(glow>0.0){
        float mask=1.0;
        if(glow_mode==1) mask=smoothstep(0.18,0.42,tex.r-tex.b)*smoothstep(0.45,0.8,tex.r);
        else if(glow_mode==2) mask=smoothstep(0.42,0.75,tex.b)*smoothstep(0.0,0.2,tex.b-tex.r);
        emit+=glow_color*mask*glow;
    }
    float rim=pow(1.0-clamp(dot(NORMAL,VIEW),0.0,1.0),3.0);
    emit+=rim_color*rim*night*0.55;
    EMISSION=emit*(1.0-far);
}
