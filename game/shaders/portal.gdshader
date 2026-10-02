shader_type spatial;
render_mode unshaded,cull_disabled;
void fragment() {
	float x=(UV.x-.5)*1.94;
	float height=(1.0-UV.y)*3.26;
	float ceiling=2.29+sqrt(max(0.0,1.0-x*x));
	if (height>ceiling) discard;
	float depth=1.0-UV.y;
	vec3 forest=mix(vec3(.12,.23,.23),vec3(.40,.58,.47),depth);
	// Layered tree silhouettes remain legible without a bright rectangular slab.
	for (int i=0;i<6;i++) {
		float center=.06+float(i)*.18;
		float top=.08+mod(float(i)*.17,.26);
		float width=.12*(UV.y-top);
		float tree=step(top,UV.y)*step(abs(UV.x-center),max(width,.014));
		forest=mix(forest,vec3(.13,.30,.28),tree*.7);
	}
	float mist=sin(UV.x*8.0+TIME*.35+UV.y*5.0)*.035;
	float border=smoothstep(.08,0.0,min(.97-abs(x),ceiling-height));
	ALBEDO=forest+vec3(.08,.12,.08)*mist+vec3(.22,.27,.14)*border;
	EMISSION=ALBEDO*.12;
}
