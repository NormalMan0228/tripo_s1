extends SceneTree
## Text sharpness shots (85): the village HUD, a dialogue, nameplates (residents and a visitor)
## and the chat box on one screen, from recorded replies (no port). Run windowed at the size to
## judge; saves artifacts/font-<tag>.png (tag from `-- --tag=name`, default "shot") and prints the
## viewport's oversampling state.
##   godot --path game --resolution 1920x1200 --script res://tests/font_shots.gd -- --tag=before
const Main = preload("res://scripts/main.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
var app: Node

func _initialize() -> void:
	call_deferred("run")
	create_timer(150).timeout.connect(func():
		push_error("font_shots exceeded 150 seconds")
		quit(2))

func line(id: int, who: String, text: String) -> Dictionary:
	return {"id":id, "user_id":"u-" + who, "username":who, "channel":"local", "text":text, "at":Time.get_unix_time_from_system()}

func run() -> void:
	var tag := "shot"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--tag="): tag = arg.substr(6)
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	var presence := {"self_id":"me", "host_id":"me", "host_name":"haneul", "visiting":false, "party":null, "invites":[], "pending_rewards":[],
		"village":{"players":[{"id":"me", "username":"haneul", "x":0, "z":0}, {"id":"u-sora", "username":"sora", "x":1.6, "z":0.8, "online":true}]},
		"chat":{"cursor":12, "history":true, "more":false, "removed":[], "lines":[line(10, "sora", "어서 와요! 마을 구경하고 가요"), line(11, "jun", "광장에서 만나요"), line(12, "sora", "낚시 같이 갈 사람?")]},
		"social":{"v":3, "requests":0, "knocks":0, "friends_online":1}}
	fixture["/v1/social/presence"] = presence
	app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = true
	await app.enter_village()
	preload("res://scripts/transition.gd").of(self).fade_in()
	await create_timer(2.0).timeout
	var hub: Node = SocialHud.of(stub)
	if hub: hub.ingest(presence)
	app.prompt_wait = 1.0e9
	app.message(TranslationServer.translate("물결빛 마을에 오신 것을 환영해요! 다리를 건너 다섯 섬을 둘러보세요."))
	var d: Dictionary = RpgUi.dialogue(app.ui, "다온 · 우편배달부", "res://assets/ui/day_postman.png")
	var body = d.get("body")
	if body is RichTextLabel or body is Label:
		body.text = "오늘도 편지가 한가득이에요! 광장 게시판에 새 소식이 붙었으니 꼭 읽어 보세요."
		body.visible_ratio = 1.0
	await create_timer(1.0).timeout
	print("FONT oversampling=", root.get("oversampling"), " override=", root.get("oversampling_override"), " window=", DisplayServer.window_get_size(), " scale=", root.content_scale_factor)
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(ProjectSettings.globalize_path("res://../artifacts/font-%s.png" % tag))
		print("SHOT font-", tag)
	SocialHud.end()
	quit(0)
