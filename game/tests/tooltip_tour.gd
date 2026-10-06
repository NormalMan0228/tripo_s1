extends SceneTree
## Rendered look of the hover names: logs into the QA server, rests the mouse on the
## hotbar's bag slot and on the star coins, and saves artifacts/tooltip-hover.png and
## artifacts/tooltip-coins.png once the tooltip is up. Run through tools/test.ps1:
##   -SkipServerTests -ClientScript tooltip_tour -Capture -Hour 12
const Main = preload("res://scripts/main.gd")
const I18n = preload("res://scripts/i18n.gd")
var failed := false
var app: Node3D

func _initialize() -> void:
	call_deferred("run")
	create_timer(180).timeout.connect(func():
		push_error("Tooltip tour exceeded 180 seconds")
		quit(2))

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func capture(name: String) -> void:
	for i in 4: await process_frame
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/tooltip-"+name+".png"))

## The tooltip label the viewport made for a hovered control.
func tooltip_label(node: Node) -> Label:
	for child in node.get_children(true):
		if child is Label and String(child.theme_type_variation) == "TooltipLabel": return child
		var found := tooltip_label(child)
		if found: return found
	return null

## Rests the mouse on c (pushed through the viewport; the OS cursor follows when a
## window is open) and waits past the tooltip delay. Returns the tooltip's text.
func rest_on(c: Control) -> String:
	var at: Vector2 = root.get_final_transform() * (c.get_global_transform_with_canvas() * (c.size * 0.5))
	if DisplayServer.get_name() != "headless": Input.warp_mouse(at)
	var motion := InputEventMouseMotion.new()
	motion.position = at
	motion.global_position = at
	root.push_input(motion)
	await create_timer(0.6).timeout
	var label := tooltip_label(c)
	return label.text if label else ""

func run() -> void:
	I18n.setup()
	I18n.set_language("ko")
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	await app.authenticate(true,"http://127.0.0.1:8766","tip_"+str(Time.get_ticks_msec()),"Tooltip-tour-password-123","")
	await create_timer(1.5).timeout
	expect(app.screen=="village","village after login")
	var bag: Control = app.expedition_button.get_parent().get_child(0)
	var shown := await rest_on(bag)
	expect(shown==tr("가방")+"  ·  I","bag slot tooltip shown: "+shown)
	await capture("hover")
	shown = await rest_on(app.frame.stars)
	expect(shown==tr("별씨"),"star coins tooltip shown: "+shown)
	await capture("coins")
	app.queue_free()
	await create_timer(.5).timeout
	quit(1 if failed else 0)
