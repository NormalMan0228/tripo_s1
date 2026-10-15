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
	check_tokens()
	check_themes()
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
