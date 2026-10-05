shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;
uniform float seed = 0.0;
void vertex(){
    float t=UV.y;
    VERTEX.x+=sin(TIME*3.8+seed+t*3.0)*.09*t*t;
    VERTEX.z+=cos(TIME*3.1+seed+t*4.0)*.07*t*t;
    VERTEX.y*=.94+.07*sin(TIME*4.7+seed);
}
void fragment(){
    float t=UV.y;
    vec3 color=mix(vec3(1.0,.78,.12),vec3(1.0,.12,.015),smoothstep(.1,.92,t));
    ALBEDO=color;
    EMISSION=color*1.5;
    ALPHA=1.0;
}
