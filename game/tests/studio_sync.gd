extends SceneTree
var failures: Array[String]=[]
func check(value: bool,message: String) -> void:
	if not value:failures.append(message);printerr(message)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var api=load("res://scripts/api.gd").new();root.add_child(api);api.base_url="http://127.0.0.1:8766"
	var login: Dictionary=await api.post("/v1/auth/register",{"username":"sync"+str(Time.get_ticks_msec()),"password":"private-local-test"})
	if not login.ok:quit(1);return
	api.token=login.data.token
	var me: Dictionary=await api.request("/v1/me")
	var avatar: Dictionary=me.data.profile.avatar.duplicate(true);avatar.coat="#2674ab"
	check((await api.post("/v1/profile",api.mutation({"version":me.data.profile.version,"avatar":avatar}))).ok,"wardrobe saved before entering home")
	var queued: Dictionary=await api.post("/v1/studio/jobs",api.mutation({"prompt":"wooden chest"}))
	if not queued.ok:quit(1);return
	var oid := ""
	for attempt in 50:
		var status: Dictionary=await api.request("/v1/studio/jobs/"+queued.data.id)
		if status.ok and status.data.state=="ready":oid=status.data.object_id;break
		await create_timer(.15).timeout
	if oid.is_empty():quit(1);return
	var place: Dictionary=await api.post("/v1/objects/"+oid+"/placement",api.mutation({"version":1,"room":"home","x":2,"z":0}))
	check(place.ok,"server placement")
	Engine.set_meta("studio_session",{"token":api.token,"url":api.base_url,"room":"home"})
	var app=load("res://scenes/studio.tscn").instantiate();root.add_child(app);await create_timer(2).timeout
	check(app.hero.avatar==avatar and app.hero.animation_player.current_animation=="idle","home uses the saved character and active idle animation")
	check(app.placed.has(oid),"placed furniture loaded")
	var patch: Dictionary=await api.post("/v1/objects/"+oid+"/bindings",api.mutation({"version":1,"part":"lid","position":[0,.9,0]}))
	check(patch.ok,"second client binding changed")
	await app.refresh()
	var edited: Array=app.placed[oid].manifest.plan.parts[1].position
	check(absf(edited[0])<.001 and absf(edited[1]-.9)<.001 and absf(edited[2])<.001,"background refresh rebuilds corrected assembly: "+str(edited))
	for i in app.data.objects.size():
		if app.data.objects[i].id==oid:await app.select_item(i);break
	await app.paint("#2674ab")
	check(app.inspected.colors.size()==2,"custom hex paint applies to all parts")
	app.part_choice.select(2);await app.paint("#ffffff",true)
	check(app.inspected.colors.size()==1 and not app.inspected.colors.has("lid"),"one part restores its original color")
	app.part_choice.select(0);await app.paint("#ffffff",true)
	check(app.inspected.colors.is_empty() and app.placed[oid].colors.is_empty(),"all original colors restored")
	await app.refresh()
	check(app.placed[oid].colors.is_empty(),"restored colors survive refresh")
	check(app.function_fields.size()==1 and app.function_signature.text.begins_with("hinge_angle(amount)"),"generated API has signature-derived numeric field")
	app.function_fields[0].value=.5
	await app.invoke_generated()
	check(app.function_result.text.contains("-47.5"),"numeric control invokes server function with actual return value")
	check(app.inspected.runtime_version==app.placed[oid].runtime_version,"function invocation synchronizes placed and preview versions")
	var external_color: Dictionary=await api.post("/v1/objects/"+oid+"/colors",api.mutation({"version":app.inspected.runtime_version,"part":"all","color":"#aabbcc"}))
	check(external_color.ok,"second client paints selected furniture")
	await app.refresh()
	check(app.inspected.colors.get("lid")=="#aabbcc" and app.inspected.runtime_version==external_color.data.version,"active preview receives other client color and version")
	app.binding_part.select(1);app.load_binding_fields(1)
	app.binding_fields.position[1].value=.95
	check(app.binding_dirty,"unsaved binding change recorded")
	var external_binding: Dictionary=await api.post("/v1/objects/"+oid+"/bindings",api.mutation({"version":app.inspected.runtime_version,"part":"lid","position":[0,1.1,0]}))
	check(external_binding.ok,"second client changes binding during local preview")
	await app.refresh()
	check(app.binding_dirty and absf(app.binding_fields.position[1].value-.95)<.001 and app.status_label.text.contains("편집값은 보존"),"conflict preserves unsaved local fields")
	for i in app.data.objects.size():
		if app.data.objects[i].id==oid:await app.select_item(i);break
	check(not app.binding_dirty and absf(app.inspected.manifest.plan.parts[1].position[1]-1.1)<.001,"explicit reselect adopts latest binding")
	check(not app.status_label.text.contains("편집값은 보존"),"resolved binding conflict clears stale warning")
	app.function_fields[0].value=.5
	await app.invoke_generated()
	check(app.function_result.text.contains("-47.5"),"generated function remains callable after remote binding refresh")
	var tabs=app.find_children("*","TabContainer",true,false);tabs[0].current_tab=2
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw;root.get_texture().get_image().save_png("res://../artifacts/generated-controls.png")
	print("STUDIO_SYNC ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
