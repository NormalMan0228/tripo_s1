extends SceneTree
## Opens the wardrobe, changes character and colours, saves, and checks that the
## walker and the server profile both changed. Captures before/after.
const Main = preload("res://scripts/main.gd")
var failed := false
func expect(value: bool, label: String) -> void:
	print(("PASS " if value else "FAIL ")+label)
	if not value: failed = true
func shot(name: String) -> void:
	for i in 8: await process_frame
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/wardrobe-"+name+".png"))
func find_buttons(node: Node, out: Array) -> void:
	if node is Button: out.append(node)
	for child in node.get_children(): find_buttons(child, out)
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var app = Main.new()
	root.add_child(app)
	await create_timer(1.5).timeout
	await app.authenticate(true,"http://127.0.0.1:8766","dress_"+str(Time.get_ticks_msec()),"Wardrobe-check-1","")
	await create_timer(1.0).timeout
	expect(app.screen=="village","village")
	app.open_wardrobe()
	await create_timer(1.0).timeout
	await shot("open")
	var editor: Node = app.village_modal.find_children("*","HBoxContainer",true,false).filter(func(n): return n.get_script()==preload("res://scripts/wardrobe.gd"))[0]
	expect(editor.actor!=null and is_instance_valid(editor.actor),"wardrobe preview character")
	var buttons: Array=[]
	find_buttons(editor,buttons)
	var ranger: Button
	for b in buttons:
		if b.has_meta("character") and b.get_meta("character")=="ranger": ranger=b
	expect(ranger!=null,"character buttons present")
	if ranger: ranger.emit_signal("pressed")
	await create_timer(0.6).timeout
	expect(editor.avatar.character=="ranger","character changed in editor")
	editor.avatar.coat="#4a7fb5"
	editor.avatar.headwear="cap"
	if editor.has_method("refresh"): editor.refresh()
	await create_timer(0.6).timeout
	await shot("ranger")
	var saves: Array=[]
	find_buttons(app.village_modal,saves)
	for b in saves:
		if b.text==app.tr("이 모습으로 저장"): b.emit_signal("pressed")
	await create_timer(1.5).timeout
	expect(app.me.get("profile",{}).get("avatar",{}).get("character","")=="ranger","server profile saved")
	expect(app.player.avatar.get("character","")=="ranger","walker wears the new look")
	await shot("saved")
	quit(1 if failed else 0)
