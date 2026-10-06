shader_type spatial;
// Survival terrain: world-space detail textures (shared with the village ground) blended by
// per-vertex weights (COLOR.r trail, COLOR.g bare soil, COLOR.b rock face, COLOR.a map accent:
// moss / scorch / deep snow) plus slope, height and macro noise. Edge haze hides the map end.
uniform sampler2D grass_detail : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_detail : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_detail : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 turf_low : source_color = vec3(0.29, 0.43, 0.16);
uniform vec3 turf_high : source_color = vec3(0.47, 0.58, 0.24);
uniform vec3 soil_color : source_color = vec3(0.45, 0.35, 0.22);
uniform vec3 trail_color : source_color = vec3(0.66, 0.56, 0.40);
uniform vec3 rock_color : source_color = vec3(0.55, 0.53, 0.48);
uniform vec3 accent_color : source_color = vec3(0.24, 0.36, 0.12);
uniform vec3 haze_color : source_color = vec3(0.55, 0.66, 0.62);
uniform float snow = 0.0;          // 1 = snow replaces turf on flat ground
uniform float strata = 0.0;        // quarry: horizontal banding on rock faces
uniform float grain_strength = 0.34;
uniform vec3 focus = vec3(0.0);    // follow-camera focus (the walker)
uniform float haze_start = 30.0;
uniform float haze_end = 58.0;
uniform float wet_level = -0.25;   // shore darkening below this height
uniform float night = 0.0;
// Trails as analytic segments (ax, az, bx, bz) + half widths: crisp, ragged edges at any zoom.
uniform vec4 path_segments[32];
uniform float path_half_widths[32];
uniform int path_count = 0;
uniform float camp_radius = 3.4;
varying vec3 world_position;
varying vec3 world_normal;

float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float v=0.0;float a=0.5;for(int i=0;i<4;i++){v+=a*noise(p);p*=2.03;a*=0.5;}return v;}

void vertex(){
    world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
    world_normal=normalize((MODEL_MATRIX*vec4(NORMAL,0.0)).xyz);
}

void fragment(){
    vec2 uv=world_position.xz/4.0;
    vec3 grass=texture(grass_detail,uv).rgb;
    vec3 sand=texture(sand_detail,uv*1.3).rgb;
    vec3 n=normalize(world_normal);
    vec3 w=pow(abs(n),vec3(4.0));w/=dot(w,vec3(1.0));
    vec3 rock=texture(rock_detail,world_position.zy/3.2).rgb*w.x+texture(rock_detail,world_position.xz/3.2).rgb*w.y+texture(rock_detail,world_position.xy/3.2).rgb*w.z;
    float macro=fbm(world_position.xz*0.07);
    // Ragged trail edges: high-frequency noise hides the 0.5 m vertex interpolation.
    float edge_noise=fbm(world_position.xz*1.9)-0.5;
    float fine=fbm(world_position.xz*0.55);
    // Turf: two tones broken up by large soft patches, with grain from the village grass texture.
    vec3 turf=mix(turf_low,turf_high,smoothstep(0.30,0.72,macro+fine*0.25));
    turf*=0.80+grass*grain_strength*1.2;
    vec3 soil=soil_color*(0.78+sand*0.42);
    vec3 trail=trail_color*(0.80+sand*0.38);
    float pebbles=smoothstep(0.62,0.70,noise(world_position.xz*6.0))*0.10;
    trail=mix(trail,trail*1.18,pebbles);
    float slope=1.0-n.y;
    float cliff=clamp(COLOR.b+smoothstep(0.30,0.55,slope),0.0,1.0);
    float band=strata*(0.5+0.5*sin(world_position.y*5.2+fbm(world_position.xz*0.3)*3.0));
    vec3 stone=rock_color*(0.70+rock*0.55)*(1.0-band*0.12);
    vec3 accent=accent_color*(0.80+grass*0.40);
    vec3 color=turf;
    color=mix(color,soil,clamp(COLOR.g+smoothstep(0.55,0.85,fine)*0.25*(1.0-snow),0.0,1.0));
    color=mix(color,accent,COLOR.a);
    float d=length(world_position.xz)-camp_radius;
    for(int i=0;i<32;i++){
        if(i>=path_count) break;
        vec2 a=path_segments[i].xy; vec2 b=path_segments[i].zw; vec2 p=world_position.xz;
        vec2 ab=b-a; float h=clamp(dot(p-a,ab)/max(dot(ab,ab),1e-4),0.0,1.0);
        d=min(d,length(p-a-ab*h)-path_half_widths[i]);
    }
    float trail_mask=1.0-smoothstep(-0.12,0.12,d+edge_noise*0.55+(fine-0.5)*0.25);
    trail_mask=max(trail_mask,clamp(COLOR.r-0.999,0.0,1.0));
    color=mix(color,trail,trail_mask);
    // Snow settles on flat ground and on the tops of rock shelves, thinning on trails.
    // Wind-packed drifts: broad blue hollows, brighter crests, a fine sugar-snow grain.
    float drift=smoothstep(0.25,0.85,macro*0.8+fbm(world_position.xz*0.22+vec2(7.0,3.0))*0.5);
    vec3 snow_tone=mix(vec3(0.60,0.69,0.81),vec3(0.86,0.90,0.95),drift)*(0.94+sand.r*0.10);
    float trodden=trail_mask;
    snow_tone=mix(snow_tone,snow_tone*vec3(0.86,0.90,0.95)+vec3(0.0,0.01,0.03)*(fine-0.5),trodden*0.85);
    float snowy=snow*smoothstep(0.35+0.3*snow,0.12+0.2*snow,slope)*(1.0-trodden*0.25);
    color=mix(color,snow_tone,snowy);
    color=mix(color,stone,cliff*(1.0-snowy*0.6));
    float wet=1.0-smoothstep(wet_level-0.35,wet_level+0.05,world_position.y);
    color*=mix(1.0,0.62,wet);
    // Distance haze from the walker hides the end of the world and gives depth.
    float far=smoothstep(haze_start,haze_end,length(world_position.xz-focus.xz));
    // Moonlight drains saturation and cools the ground at night.
    color=mix(color,vec3(dot(color,vec3(0.3,0.59,0.11)))*vec3(0.78,0.88,1.08),night*0.5);
    ALBEDO=mix(color,haze_color,far);
    vec2 nd=(mix(texture(grass_normal,uv).rg,texture(sand_normal,uv*1.3).rg,clamp(COLOR.r+COLOR.g,0.0,1.0))*2.0-1.0);
    vec2 nr=texture(rock_normal,world_position.xz/3.2).rg*2.0-1.0;
    nd=mix(nd,nr,cliff);
    vec3 bent=normalize(n+vec3(nd.x,0.0,nd.y)*mix(0.10,0.22,cliff)*(1.0-far));
    NORMAL=normalize((VIEW_MATRIX*vec4(bent,0.0)).xyz);
    ROUGHNESS=mix(0.92,0.55,snowy*0.4+wet*0.6);
    SPECULAR=mix(0.18,0.35,snowy);
}
