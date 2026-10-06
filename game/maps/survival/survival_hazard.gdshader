shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back, shadows_disabled;
// Server hazards drawn on the ground. mode 0: ember fissure (scorched rim, Voronoi lava cracks that
// pulse and glow at night); mode 1: ice sheet (glossy blue, white crack lines, frosted rim).
// One quad per group of overlapping hazard circles (x, z, radius): r = 1 on the server boundary.
uniform int mode = 0;
uniform vec4 circles[4];
uniform int circle_count = 1;
uniform float night = 0.0;
uniform vec3 focus = vec3(0.0);
varying vec3 world_position;
vec2 hash2(vec2 p){p=vec2(dot(p,vec2(127.1,311.7)),dot(p,vec2(269.5,183.3)));return fract(sin(p)*43758.5453);}
float hash(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p);vec2 f=fract(p);f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
// Distance to the nearest Voronoi cell border.
float cells(vec2 p){
    vec2 i=floor(p);vec2 f=fract(p);vec2 best=vec2(8.0);vec2 mr=vec2(0.0);float md=8.0;
    for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++){vec2 g=vec2(float(x),float(y));vec2 o=hash2(i+g);vec2 r=g+o-f;float d=dot(r,r);if(d<md){md=d;mr=r;}}
    md=8.0;
    for(int y=-2;y<=2;y++)for(int x=-2;x<=2;x++){vec2 g=vec2(float(x),float(y));vec2 o=hash2(i+g);vec2 r=g+o-f;
        if(dot(mr-r,mr-r)>0.00001) md=min(md,dot(0.5*(mr+r),normalize(r-mr)));}
    return md;
}
void vertex(){world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}
void fragment(){
    float r=8.0;
    for(int i=0;i<4;i++){ if(i<circle_count) r=min(r,length(world_position.xz-circles[i].xy)/circles[i].z); }
    float wobble=noise(world_position.xz*1.3)*0.22;
    float inside=1.0-smoothstep(0.86+wobble,1.12+wobble,r);
    float halo=1.0-smoothstep(0.9,1.3,r);
    vec2 p=world_position.xz*1.15;
    float border=cells(p+noise(p*0.6)*0.6);
    if(mode==0){
        float crack=1.0-smoothstep(0.02,0.085,border);
        crack*=smoothstep(1.05,0.55,r+wobble*0.5);
        float pulse=0.75+0.25*sin(TIME*2.1+noise(p*0.4)*6.0);
        vec3 scorch=mix(vec3(0.20,0.14,0.11),vec3(0.36,0.24,0.17),noise(p*2.0));
        ALBEDO=mix(scorch,vec3(1.0,0.55,0.18),crack);
        EMISSION=vec3(1.0,0.42,0.10)*crack*pulse*(1.6+night*2.4)+vec3(0.5,0.12,0.02)*inside*(1.0-crack)*0.12*(1.0+night);
        // Scorch fades out over the rim instead of a hard dark disc.
        float scorch_alpha=inside*mix(0.95,0.35,smoothstep(0.55,1.0,r+wobble*0.4));
        ALPHA=clamp(max(scorch_alpha,crack),0.0,1.0)*halo;
        ROUGHNESS=0.9;
    }else{
        float crack=1.0-smoothstep(0.0,0.03,border);
        float frost=smoothstep(0.62,1.0,r+wobble);
        vec3 ice=mix(vec3(0.62,0.82,0.92),vec3(0.42,0.66,0.82),noise(world_position.xz*0.45));
        ice=mix(ice,vec3(0.93,0.97,1.0),max(crack*0.75,frost*0.85));
        ALBEDO=ice;
        ROUGHNESS=mix(0.06,0.5,frost);
        SPECULAR=0.8;
        EMISSION=vec3(0.30,0.55,0.75)*night*0.18*(1.0-frost);
        ALPHA=inside*0.94*halo;
    }
}
