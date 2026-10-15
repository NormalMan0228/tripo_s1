extends SceneTree
## Windowed look at the chat bubble card and the owner's crown over the walker, from recorded replies
## (no port): artifacts/bubble-*.png. Headless runs only check that the pieces are built.
##   godot --path game --script res://tests/ui_bubble_shot.gd
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
var failures: Array[String] = []
var app: Node

func expect(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")
	create_timer(120).timeout.connect(func():
		push_error("ui_bubble_shot exceeded 120 seconds")
		quit(2))

func capture(name: String) -> void:
	for i in 6: await process_frame
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/bubble-%s.png" % name))
	print("SHOT bubble-", name)

func run() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(1.0).timeout
	SocialHud.bubble(app.player, "안녕하세요! 오늘 바닷가에서 같이 낚시할래요?")
	await create_timer(0.5).timeout
	var bubble: Node3D = app.player.get_node_or_null("ChatBubble")
	expect(bubble != null and bubble.get_node_or_null("Card") is MeshInstance3D and bubble.get_node_or_null("Words") is Label3D, "the bubble is a card with its words")
	var plain_y: float = bubble.position.y if bubble else 0.0
	await capture("plain")
	SocialHud.host_crown(app.player, true)
	SocialHud.bubble(app.player, "안녕하세요! 오늘 바닷가에서 같이 낚시할래요?")
	await create_timer(0.5).timeout
	var crown := app.player.get_node_or_null("HostCrown") as Sprite3D
	var raised: Node3D = app.player.get_node_or_null("ChatBubble")
	expect(crown != null and crown.texture != null and raised != null and raised.position.y > plain_y + 0.1, "the crown sits over the name and the bubble rises above it")
	await capture("crown")
	SocialHud.host_crown(app.player, false)
	expect(app.player.get_node_or_null("HostCrown") == null, "the crown comes off")
	print("UI_BUBBLE ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)
