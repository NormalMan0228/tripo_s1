extends SceneTree
## One visual language (docs/design/UI_UNIFICATION.md): headless checks that grow with each
## work package.
##   tokens   the design tokens hold the spec's values
##   themes   RpgUi.theme() (parchment) and RpgUi.night_theme() both style every listed control
##            type themselves, so neither surface leaks into the other (U-WP-01)
##   static   colour literals that have a token are not written outside rpg_ui.gd and the painter;
##            files still waiting for their migration are in ALLOWLIST (U-WP-17)
##   runtime  every village window has one shade and a close key whose tooltip ends with its key
##            (U-WP-03)
##   godot --headless --path game --script res://tests/ui_consistency_check.gd -- --qa
const RpgUi = preload("res://scripts/rpg_ui.gd")
const Main = preload("res://scripts/main.gd")
const I18n = preload("res://scripts/i18n.gd")
const Stub = preload("res://tests/ui_stub_api.gd")
var failures := 0
var checks := 0

func _initialize() -> void:
	call_deferred("run")
	create_timer(240).timeout.connect(func():
		push_error("UI consistency check exceeded 240 seconds")
		quit(2))

func expect(ok: bool, what: String) -> void:
	checks += 1
	print(("PASS " if ok else "FAIL ") + what)
	if not ok: failures += 1

func run() -> void:
	I18n.setup()
	check_tokens()
	check_themes()
	check_static()
	await check_stack()
	await check_village_windows()
	print("UI_CONSISTENCY ", JSON.stringify({"checks":checks, "failures":failures}))
	quit(1 if failures else 0)

# ------------------------------------------------------------------ tokens

func check_tokens() -> void:
	var want := {"INK":"fff4d6","GOLD":"e9d29b","PAPER_INK":"3c2e1e","PAPER_MUTED":"7a6446","ACCENT":"b0452f","LEAF":"4a7536",
		"SOFT":"d8e3d4","HOVER":"ffe08a","TEAL":"70afa3","PAPER_LINE":"c9a46a","ONLINE":"8fd16a","AWAY":"e9b552"}
	var constants: Dictionary = (load("res://scripts/rpg_ui.gd") as Script).get_script_constant_map()
	var wrong := []
	for key in want:
		if not constants.has(key) or (constants[key] as Color).to_html(false) != want[key]: wrong.append(key)
	expect(wrong.is_empty(), "colour tokens hold the spec values %s" % [wrong])
	expect(RpgUi.OFFLINE.is_equal_approx(Color(1,1,1,.35)) and RpgUi.SHADE_IN.is_equal_approx(Color(0.03,0.05,0.06,.55))
		and RpgUi.SHADE_OUT.is_equal_approx(Color(0.02,0.03,0.04,.86)), "OFFLINE and the shade tokens")
	expect([RpgUi.T_WINDOW, RpgUi.T_SECTION, RpgUi.T_BODY, RpgUi.T_CAPTION, RpgUi.T_SMALL] == [26, 17, 15, 13, 12], "type scale 26/17/15/13/12")
	expect([RpgUi.BTN_SM, RpgUi.BTN_MD, RpgUi.BTN_LG, RpgUi.BTN_MENU, RpgUi.SLOT, RpgUi.KEY, RpgUi.CLOSE] == [32, 40, 44, 52, 70, 22, 34], "button, slot, key and close sizes")
	expect(RpgUi.WINDOW_W == {"small":560, "standard":760, "wide":1040} and RpgUi.DRAWER_W == 308 and RpgUi.WINDOW_TOP == 92, "window widths, drawer width and window top")
	var l := Label.new()
	RpgUi.text_style(l, "window", "night")
	var night_ok := l.get_theme_color("font_color") == RpgUi.GOLD and l.get_theme_font_size("font_size") == 26
	RpgUi.text_style(l, "caption", "paper")
	expect(night_ok and l.get_theme_color("font_color") == RpgUi.PAPER_MUTED and l.get_theme_font_size("font_size") == 13, "text_style gives the role's font, size and surface colour")
	l.free()

# ------------------------------------------------------------------ themes

## [type, [styleboxes], [colours], [icons]] that each theme must define itself.
const COVERAGE := [
	["Button", ["normal","hover","pressed","disabled"], ["font_color"], []],
	["LineEdit", ["normal","focus"], ["font_color","caret_color"], []],
	["ItemList", ["panel","selected","hovered"], ["font_color","font_selected_color"], []],
	["TabBar", ["tab_selected","tab_unselected","tab_hovered"], ["font_selected_color","font_unselected_color"], []],
	["TabContainer", ["panel","tab_selected","tab_unselected"], ["font_selected_color","font_unselected_color"], []],
	["OptionButton", [], [], ["arrow"]],
	["PopupMenu", ["panel","hover"], ["font_color","font_hover_color"], []],
	["ScrollContainer", ["panel"], [], []],
	["VScrollBar", ["scroll","grabber"], [], []],
	["HSlider", ["slider","grabber_area"], [], ["grabber"]],
	["ProgressBar", ["background","fill"], [], []],
	["CheckBox", [], ["font_color"], ["checked","unchecked"]],
	["TooltipPanel", ["panel"], [], []],
	["TooltipLabel", [], ["font_color"], []],
]

func check_themes() -> void:
	var paper: Theme = RpgUi.theme()
	var night: Theme = RpgUi.night_theme()
	for name in ["paper", "night"]:
		var t: Theme = paper if name == "paper" else night
		var missing := []
		for spec in COVERAGE:
			for item in spec[1]: if not t.has_stylebox(item, spec[0]): missing.append("%s.%s" % [spec[0], item])
			for item in spec[2]: if not t.has_color(item, spec[0]): missing.append("%s.%s" % [spec[0], item])
			for item in spec[3]: if not t.has_icon(item, spec[0]): missing.append("%s.%s" % [spec[0], item])
		expect(missing.is_empty(), "%s theme styles every listed type itself %s" % [name, missing])
	# The two surfaces read differently: no parchment ink or wells in night lists, tabs and menus.
	var leaks := []
	for pair in [["ItemList","font_color"],["PopupMenu","font_color"],["TabBar","font_unselected_color"],["TabContainer","font_unselected_color"]]:
		if night.has_color(pair[1], pair[0]) and night.get_color(pair[1], pair[0]) == RpgUi.PAPER_INK: leaks.append(pair[0])
	for pair in [["ItemList","panel"],["PopupMenu","panel"],["TabContainer","panel"]]:
		if night.get_stylebox(pair[1], pair[0]) == paper.get_stylebox(pair[1], pair[0]): leaks.append(pair[0] + " box")
		var box := night.get_stylebox(pair[1], pair[0]) as StyleBoxTexture
		if box and box.texture and box.texture.resource_path.contains("paper"): leaks.append(pair[0] + " paper frame")
	expect(leaks.is_empty(), "night lists, tabs and menus use night colours and frames %s" % [leaks])
	expect(night.get_icon("arrow", "OptionButton") != paper.get_icon("arrow", "OptionButton"), "night drop-downs use the light arrow")
	# A night panel inside a parchment root resolves the night look, not the root's.
	var host := Control.new()
	host.theme = paper
	root.add_child(host)
	var glass := PanelContainer.new()
	glass.theme = night
	host.add_child(glass)
	var probes := {"ItemList":ItemList.new(), "TabBar":TabBar.new(), "OptionButton":OptionButton.new(), "PopupMenu":PopupMenu.new(), "ScrollContainer":ScrollContainer.new()}
	for key in probes: glass.add_child(probes[key])
	var resolved := (probes.ItemList as ItemList).get_theme_color("font_color") == RpgUi.INK \
		and (probes.TabBar as TabBar).get_theme_color("font_unselected_color") == RpgUi.INK \
		and (probes.OptionButton as OptionButton).get_theme_icon("arrow") == night.get_icon("arrow", "OptionButton") \
		and (probes.PopupMenu as PopupMenu).get_theme_color("font_color") == RpgUi.INK
	expect(resolved, "controls under a night panel in a parchment root resolve night styles")
	host.free()

# ------------------------------------------------------------------ static lint

## Colours that have a token (RpgUi): writing them as literals outside rpg_ui.gd and the painter fails.
const TOKEN_HEXES := ["ffe08a","e9b552","fff2cf","c9d3c6","3b2a1c","2f2a1f","5d4a35","7a5a2c","8a5a1c","fff4d6","e9d29b",
	"3c2e1e","7a6446","b0452f","d8e3d4","c9a46a","ffd9a0","c8ec9f"]
## Files still waiting for their migration, with the most literals each may keep (the list only
## shrinks). They are on the presentation's object-creation path or hot files other tracks edit now:
## main.gd/studio.gd (U-WP-04/09/11), craft_panel.gd (the finished-craft accent 8a5a1c, kept for the talk).
const LITERAL_ALLOWLIST := {"main.gd":4, "studio.gd":12, "craft_panel.gd":1}
## Files already on the shared windows and tokens: no flat boxes or colour rects of their own.
const MIGRATED := ["craft_window.gd", "village_life.gd", "life_icon.gd", "minimap.gd", "interaction_panel.gd", "shape_panel.gd"]

func check_static() -> void:
	var literal := RegEx.new()
	literal.compile(r'(?i)Color\("#?(' + "|".join(TOKEN_HEXES) + ')"')
	var hotbar_key := RegEx.new()
	hotbar_key.compile(r'"key"\s*:\s*"([A-Z]|Tab|F[0-9]+)"')
	var over := []
	var shrunk := []
	var flat := []
	var keys := []
	for name in DirAccess.get_files_at("res://scripts"):
		if not name.ends_with(".gd") or name == "rpg_ui.gd": continue
		var code := FileAccess.get_file_as_string("res://scripts/" + name)
		var count := literal.search_all(code).size()
		var allowed: int = LITERAL_ALLOWLIST.get(name, 0)
		if count > allowed: over.append("%s %d>%d" % [name, count, allowed])
		elif count < allowed: shrunk.append("%s %d<%d" % [name, count, allowed])
		if name in MIGRATED and (code.contains("StyleBoxFlat.new()") or code.contains("ColorRect.new()")): flat.append(name)
		for found in hotbar_key.search_all(code): keys.append("%s %s" % [name, found.get_string()])
	expect(over.is_empty(), "no token colours written as literals outside rpg_ui.gd, the painter and the allowlist %s" % [over])
	if not shrunk.is_empty(): print("NOTE the literal allowlist can shrink: ", shrunk)
	expect(flat.is_empty(), "migrated files build no StyleBoxFlat or ColorRect of their own %s" % [flat])
	expect(keys.is_empty(), "hotbar specs name actions, not key letters %s" % [keys])

# ------------------------------------------------------------------ window stack

var heard: Array = []

func _on_windows(count: int, top_kind: String) -> void:
	heard.append([count, top_kind])

func shades_under(node: Node) -> int:
	return node.find_children("Shade", "TextureRect", true, false).size()

func check_stack() -> void:
	var host := Control.new()
	host.size = Vector2(1280, 800)
	host.theme = RpgUi.theme()
	root.add_child(host)
	RpgUi.listen_windows(_on_windows)
	expect(RpgUi.window_listeners.has(_on_windows), "a plain method listens to the window stack")
	heard.clear()
	var first := RpgUi.window(host, "첫 창", {"action":"craft", "id":"first"})
	expect(RpgUi.top_window().get("id") == "first" and heard.back() == [1, "paper"], "a window joins the stack and listeners hear it")
	expect(first.root.get_parent() == host and first.card.custom_minimum_size.x == 760.0 and first.title.get_theme_font_size("font_size") == RpgUi.T_WINDOW
		and first.title.get_theme_color("font_color") == RpgUi.PAPER_INK, "a paper window: 760 wide, T_WINDOW title in paper ink")
	expect(first.close.get_meta("rpg_close", false) and first.close.tooltip_text.ends_with("C") and first.close.get_parent() == first.head, "its close key sits in the head and names its key (C)")
	var second := RpgUi.window(host, "둘째 창", {"kind":"night", "width":440, "place":"centre", "id":"second"})
	expect(shades_under(host) == 1 and second.shade == first.shade, "a window opened over another reuses its shade (one shade on screen)")
	expect(second.card.theme == RpgUi.night_theme() and second.title.get_theme_color("font_color") == RpgUi.GOLD, "a night window: night theme and a gold title")
	var side := RpgUi.drawer(host, "가방", {"id":"bag"})
	expect(RpgUi.top_window().get("kind") == "drawer" and side.shade == null and side.root.mouse_filter == Control.MOUSE_FILTER_IGNORE and RpgUi.windows().size() == 3, "a drawer joins the stack without a shade and lets the world take clicks")
	second.close.pressed.emit()
	await process_frame
	expect(RpgUi.windows().map(func(w): return w.id) == ["first", "bag"], "the close key closes its own window: %s" % [RpgUi.windows().map(func(w): return w.id)])
	var called := [0]
	var custom := RpgUi.window(host, "셋째 창", {"modal":false, "on_close":func(): called[0] += 1, "id":"custom"})
	custom.close.pressed.emit()
	expect(called[0] == 1 and RpgUi.top_window().get("id") == "custom", "on_close replaces the default close (the owner closes it)")
	RpgUi.close_window(custom, false)
	expect(not is_instance_valid(custom.root) or custom.root.is_queued_for_deletion(), "close_window without animation frees at once")
	first.root.queue_free()
	await process_frame
	expect(RpgUi.windows().map(func(w): return w.id) == ["bag"], "a window freed by its scene is pruned from the stack")
	host.free()
	await process_frame
	expect(RpgUi.windows().is_empty() and RpgUi.top_window().is_empty() and heard.back() == [0, ""], "the stack is empty after the host left; listeners heard it")
	await check_stack_bottom_first()
	RpgUi.unlisten_windows(_on_windows)

## Two modal windows sharing one shade; the bottom one (the shade's owner) closes first: the shade
## moves to the window left open, and the next modal on that host reuses it without a script error.
func check_stack_bottom_first() -> void:
	var host := Control.new()
	host.size = Vector2(1280, 800)
	host.theme = RpgUi.theme()
	root.add_child(host)
	var low := RpgUi.window(host, "아래 창", {"id":"low"})
	var high := RpgUi.window(host, "위 창", {"id":"high", "place":"centre"})
	var veil: TextureRect = low.shade
	expect(high.shade == veil and veil.get_parent() == low.root, "the second modal shares the first one's shade")
	low.close.pressed.emit()
	await create_timer(0.35).timeout
	expect(not is_instance_valid(low.root) and is_instance_valid(veil) and veil.get_parent() == high.root and veil.get_index() == 0
		and is_instance_valid(high.shade) and shades_under(host) == 1, "closing the bottom window first hands its shade to the one still open, under its card")
	var third := RpgUi.window(host, "셋째 창", {"id":"third"})
	expect(third.shade == veil and shades_under(host) == 1 and RpgUi.windows().map(func(w): return w.id) == ["high", "third"], "the next modal on that host reuses the handed-over shade")
	RpgUi.close_window(third, false)
	RpgUi.close_window(high, false)
	await process_frame
	expect(RpgUi.windows().is_empty() and shades_under(host) == 0, "closing the rest clears the shade")
	host.free()
	await process_frame

# ------------------------------------------------------------------ village windows

func check_village_windows() -> void:
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/ui_gallery.json"))
	var app = Main.new()
	root.add_child(app)
	await create_timer(1.6).timeout
	app.api.queue_free()
	var stub := Stub.new()
	stub.data = fixture
	app.api = stub
	app.add_child(stub)
	app.social.enabled = false
	await app.enter_village()
	await create_timer(0.8).timeout
	var openers := [["expedition", func(): await app.open_expedition(), "Esc"], ["story", func(): app.open_story(), "Esc"],
		["wardrobe", func(): app.open_wardrobe(), "O"], ["map", func(): app.life.open_map(), "Tab"], ["storage", func(): app.life.open_storage(), "B"],
		["shop", func(): app.life.open_shop(), "Esc"], ["log", func(): app.life.open_log(), "Esc"], ["admin", func(): app.open_admin(), "Esc"]]
	for entry in openers:
		await (entry[1] as Callable).call()
		await process_frame
		var modal: Control = app.village_modal
		var ok := is_instance_valid(modal) and modal.has_meta("rpg_window")
		var closes := modal.find_children("*", "Button", true, false).filter(func(b): return b.get_meta("rpg_close", false)) if ok else []
		var shades := shades_under(app.ui)
		ok = ok and closes.size() == 1 and str(closes[0].tooltip_text).ends_with(entry[2]) and shades == 1 and RpgUi.top_window().get("root") == modal
		expect(ok, "%s: one shade (%d), one close key named '…%s' (%s), on the window stack" % [entry[0], shades, entry[2], closes.map(func(b): return b.tooltip_text)])
		var w: Dictionary = modal.get_meta("rpg_window", {}) if is_instance_valid(modal) else {}
		if w.has("close"): (w.close as Button).pressed.emit()
		await process_frame
		expect(not is_instance_valid(app.village_modal) and RpgUi.windows().is_empty() and shades_under(app.ui) == 0, "%s: its close key closes it and clears the shade" % entry[0])
	app.queue_free()
	await create_timer(0.5).timeout
