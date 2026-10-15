extends SceneTree
## Painted loading art: the place card shows its kind of place behind the name (read on a
## worker thread, never on the main thread), a card without one stays the dark glow card,
## the first card and the title use the painted logo, and the title art is widescreen.
const Main = preload("res://scripts/main.gd")
const Brand = preload("res://scripts/brand.gd")
var failures: Array[String] = []

func check(value: bool, message: String) -> void:
	print(("PASS " if value else "FAIL ") + message)
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var Transition = load("res://scripts/transition.gd")
	for key in Transition.BACKDROPS:
		var texture: Texture2D = load(Transition.BACKDROPS[key])
		check(texture != null and texture.get_width() >= 1280, "backdrop %s loads (%d px)" % [key, texture.get_width() if texture else 0])
	for path in ["res://assets/title_morning.jpg", "res://assets/title_golden.jpg", "res://assets/title_evening.jpg", Transition.COVER_ART]:
		var art: Texture2D = load(path)
		check(art.get_width() >= 1920 and float(art.get_width())/art.get_height() > 1.7, "%s is widescreen (%dx%d)" % [path.get_file(), art.get_width(), art.get_height()])
	var veil = Transition.of(self)
	await process_frame
	await process_frame
	# A place with a painting: the dark glow gives way to the picture and the name's shade.
	veil.loading("다섯 섬 마을", "", "village")
	check(veil.backdrop.visible and veil.name_shade.visible and not veil.glow.visible, "village card: backdrop and name shade on, glow off")
	await veil.fade_out()
	var waited := 0
	while veil.backdrop.texture == null and waited < 120:
		await process_frame
		waited += 1
	check(veil.backdrop.texture != null, "village card: the painting arrives under the veil (%d frames)" % waited)
	check(veil.backdrop.texture != null and veil.backdrop.texture.resource_path == Transition.BACKDROPS.village, "village card: it is the village painting")
	await create_timer(0.4).timeout
	check(veil.backdrop.modulate.a > 0.99, "village card: the painting has faded in (%.2f)" % veil.backdrop.modulate.a)
	await veil.fade_in()
	check(not veil.card.visible and veil.backdrop.texture == null, "village card: cleared with the veil")
	# Back again: the painting is cached and shows at once.
	veil.loading("다섯 섬 마을", "", "village")
	check(veil.backdrop.texture != null and veil.backdrop.modulate.a > 0.99, "village card again: shown at once from the cache")
	await veil.fade_out()
	await veil.fade_in()
	# The cache keeps two paintings at most.
	for key in ["room", "forest", "frost"]:
		veil.loading(key, "run", key)
		await veil.fade_out()
		var frames := 0
		while veil.backdrop.texture == null and frames < 120:
			await process_frame
			frames += 1
		await veil.fade_in()
	check(Transition.backdrop_cache.size() <= 2, "cache holds %d paintings (at most 2)" % Transition.backdrop_cache.size())
	# No painting named: the plain dark card with its warm glow.
	veil.loading("계단")
	check(not veil.backdrop.visible and not veil.name_shade.visible and veil.glow.visible, "plain card: no backdrop, warm glow")
	veil.loading("어딘가", "", "nowhere")
	check(not veil.backdrop.visible and veil.glow.visible, "unknown backdrop key: plain card")
	await veil.fade_out()
	await veil.fade_in()
	# The first card: cover art and the painted logo.
	veil.loading("", "start")
	var logos: Array = veil.wordmark.find_children("*", "TextureRect", true, false).filter(func(r) -> bool: return r.texture != null and r.texture.resource_path == Brand.LOGO)
	check(veil.art.visible and not veil.backdrop.visible and logos.size() == 1, "start card: cover art and the logo, no backdrop")
	veil.clear_card()
	# The title screen: the logo top left over the art, no text wordmark.
	var app: Node = Main.new()
	root.add_child(app)
	await create_timer(0.6).timeout
	app.login_ui()
	for i in 6: await process_frame
	var on_title: Array = app.ui.find_children("*", "TextureRect", true, false).filter(func(r) -> bool: return r.texture != null and r.texture.resource_path == Brand.LOGO)
	check(on_title.size() == 1, "title: one painted logo")
	if on_title.size() == 1:
		var rect: Rect2 = on_title[0].get_global_rect()
		check(rect.position.x < 120 and rect.position.y < 120 and rect.size.x > 300, "title: logo top left (%s)" % rect)
	var words: Array = app.ui.find_children("*", "Label", true, false).filter(func(l) -> bool: return l.text == "Villagen")
	check(words.is_empty(), "title: no text wordmark next to the logo")
	print("LOADING_BACKDROP ", "PASS" if failures.is_empty() else "FAIL %d" % failures.size())
	quit(0 if failures.is_empty() else 1)
