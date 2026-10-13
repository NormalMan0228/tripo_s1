extends VBoxContainer
## The one crafting window, used by the village (C) and every room's [만들기] tab, so both make
## things the same way. Flow: describe the object (optionally add a photo) and pick options ->
## the server designs it (LLM) -> with no photo the AI first draws a concept picture, shown with the
## text it will send to Tripo; the player builds from the picture, redraws it (+5 credits) or builds
## from the text -> quote confirmed -> Tripo builds -> place it. Options open only when their cheapest
## craft fits the server's per-craft cap (see /v1/studio max_tripo_credits).
##   var panel := CraftPanel.new(); parent.add_child(panel)
##   panel.setup(api, {"say": message, "explain": error_message, "place_label": tr("지금 마을에 놓기"),
##       "place": place_crafted, "dark": false, "preview": Callable()})
##   await panel.open()
const RpgUi = preload("res://scripts/rpg_ui.gd")
const BuildMode = preload("res://scripts/build_mode.gd")
const I18n = preload("res://scripts/i18n.gd")
const Fx = preload("res://scripts/fx.gd")
## The chosen look and size follow the account (cloud_prefs.gd syncs this section).
const SETTINGS_SECTION := "craft"

signal job_started(job_id: String)
signal job_finished(job: Dictionary)
## Hosts that watch the craft themselves (the village keeps polling after its window closes) set
## "self_poll": false and get this instead of the panel polling.
signal follow_requested
## The player cleared a finished craft ("새로 만들기").
signal new_craft

const CONCEPT_CREDITS := 5
## "unknown" is a submission the server could not confirm: it waits for an operator (who gives the
## starseeds back), so the window stops following it and the player can craft again.
const TERMINAL := ["ready", "failed", "cancelled", "unknown"]
## The server is still working: the window shows the steps and keeps them between polls.
const WORKING := ["queued", "planning", "building", "submitting"]
## Polls back off from 2 s to this while the server cannot be reached.
const MAX_POLL_PAUSE := 30.0

var api: Node
var say: Callable
var explain: Callable
var place_action: Callable
var preview_action: Callable
var place_label := ""
var dark := false
var self_poll := true
var info: Dictionary = {}
var cap := 0
var job_id := ""
var job: Dictionary = {}
var image_data := ""
var busy := false
var polling := false
var textures := {}
var defaults_applied := false
## The steps view while the server works (see _show_working); empty when another view shows.
var working: Dictionary = {}
## The job and picture the player was last told about ("그림이 완성됐어요").
var announced := ""

var form: VBoxContainer
var status: VBoxContainer
var prompt: TextEdit
var image_label: Label
var surface: OptionButton
var motion: OptionButton
var mesh_model: OptionButton
var refine: CheckButton
var price_label: Label
var concept_note: Label
var ask: Button
var designer: OptionButton
var geometry: OptionButton
var models: OptionButton
var efforts: OptionButton
var file_dialog: FileDialog
var photo_buttons: Array[Button] = []
var dev_box: Control
## Named styles and sizes come from the server (/v1/studio styles, sizes; server/craft_styles.py).
var style_id := "rpg"
var size_id := "auto"
var style_title: Label
var style_grid: GridContainer
var size_title: Label
var size_row: HFlowContainer
var style_buttons := {}
var size_buttons := {}
var held_note: Label
## What the server's object library makes of the words (POST /v1/studio/kind): a type always built
## moving (a clock: its hands are free) and the Tripo meshes a moving craft of it needs.
var kind_info: Dictionary = {}
var kind_supported := true
var kind_timer: Timer
## The moving option was chosen for the player (a clock), not by them.
var forced_motion := false

func setup(network: Node, options: Dictionary) -> void:
	api = network
	say = options.get("say", Callable())
	explain = options.get("explain", Callable())
	place_action = options.get("place", Callable())
	preview_action = options.get("preview", Callable())
	place_label = str(options.get("place_label", tr("지금 마을에 놓기")))
	dark = bool(options.get("dark", false))
	self_poll = bool(options.get("self_poll", true))
	add_theme_constant_override("separation", 10)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	style_id = str(config.get_value(SETTINGS_SECTION, "style", style_id))
	size_id = str(config.get_value(SETTINGS_SECTION, "size", size_id))
	_build_form()

## Reads the server's crafting settings (or uses `studio` already read) and shows the form, or follows
## a craft that is still under way.
func open(studio: Dictionary = {}) -> void:
	if studio.is_empty():
		var reply: Dictionary = await api.request("/v1/studio")
		if reply.ok: studio = reply.data
	apply_info(studio)
	if job_id.is_empty():
		for entry in studio.get("jobs", []):
			if not str(entry.get("state", "")) in TERMINAL:
				job_id = str(entry.id)
				break
	_update_options()
	if job_id.is_empty(): _show_form()
	else: follow()

func apply_info(studio: Dictionary) -> void:
	info = studio
	cap = int(studio.get("max_tripo_credits", 0))
	if studio.has("mode"):
		var live := _live()
		var llm := _llm()
		var tripo := bool(studio.get("geometry_enabled", false))
		designer.set_item_disabled(0, live)
		designer.set_item_disabled(1, not llm)
		geometry.set_item_disabled(0, live)
		geometry.set_item_disabled(1, not tripo)
		for i in models.item_count: models.set_item_disabled(i, live and i != 0)
		for i in efforts.item_count: efforts.set_item_disabled(i, live and i != 2)
		if live:
			models.select(0)
			efforts.select(2)
		# The server's own setup is the starting choice: design with its LLM and build with Tripo when it can.
		if not defaults_applied:
			defaults_applied = true
			designer.select(1 if llm else 0)
			geometry.select(1 if tripo else 0)
	_fill_styles()
	_update_options()
	# Crafts the server could not confirm wait for an operator; the form says so instead of spinning.
	var held := 0
	for entry in studio.get("jobs", []):
		if str(entry.get("state", "")) == "unknown": held += 1
	if is_instance_valid(held_note):
		held_note.visible = held > 0
		held_note.text = tr("확인을 기다리는 제작 %d건 · 운영자가 확인하면 맡긴 별씨가 돌아와요") % held

func _live() -> bool:
	return str(info.get("mode", "demo")) == "live"

func _llm() -> bool:
	return not str(info.get("llm", "fixture")) in ["fixture", ""]

# ------------------------------------------------------------------ form

func _build_form() -> void:
	form = VBoxContainer.new()
	form.add_theme_constant_override("separation", 9)
	add_child(form)
	status = VBoxContainer.new()
	status.add_theme_constant_override("separation", 9)
	add_child(status)
	_label(form, tr("어떤 물건을 만들까요?"), 20)
	prompt = TextEdit.new()
	prompt.custom_minimum_size = Vector2(0, 92)
	prompt.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	prompt.placeholder_text = tr("예: 작은 버섯 모양 의자")
	form.add_child(prompt)
	kind_timer = Timer.new()
	kind_timer.one_shot = true
	kind_timer.wait_time = 0.45
	kind_timer.timeout.connect(_ask_kind)
	add_child(kind_timer)
	prompt.text_changed.connect(func() -> void: kind_timer.start())
	var photo := _row(form)
	photo_buttons.append(_button(photo, tr("사진·그림 추가"), func() -> void: _file_dialog().popup_centered_ratio(0.7)))
	photo_buttons.append(_button(photo, tr("제거"), func() -> void:
		image_data = ""
		image_label.text = tr("참고 이미지 없음")
		_update_options()))
	image_label = _label(form, tr("참고 그림을 추가할 수 있어요"), 13, true)
	style_title = _label(form, tr("스타일"), 15)
	style_grid = GridContainer.new()
	style_grid.columns = 3
	style_grid.add_theme_constant_override("h_separation", 6)
	style_grid.add_theme_constant_override("v_separation", 6)
	form.add_child(style_grid)
	resized.connect(func() -> void: style_grid.columns = 3 if size.x > 480 else 2)
	size_title = _label(form, tr("크기"), 15)
	size_row = _row(form)
	for control in [style_title, style_grid, size_title, size_row]: control.visible = false
	var choices := GridContainer.new()
	choices.columns = 2
	# One column in a room's narrow drawer.
	resized.connect(func() -> void: choices.columns = 2 if size.x > 480 else 1)
	choices.add_theme_constant_override("h_separation", 8)
	choices.add_theme_constant_override("v_separation", 6)
	form.add_child(choices)
	surface = _option(choices, [tr("Tripo가 색까지 입히기"), tr("내가 직접 색칠하기")])
	motion = _option(choices, [tr("정적인 가구"), tr("움직이는 가구")])
	mesh_model = _option(choices, [tr("H3 · 일반 가구 / 낮은 비용"), tr("P2 · 정밀 메시 / 높은 비용")])
	refine = CheckButton.new()
	refine.text = tr("그림을 먼저 정리해서 만들기")
	refine.tooltip_text = tr("Tripo 이미지 편집: 부품당 예상 5크레딧 추가. 이후 이미지→3D 요금 적용.")
	choices.add_child(refine)
	for control in [surface, motion, mesh_model]: control.item_selected.connect(func(_i: int) -> void: _update_options())
	refine.toggled.connect(func(_on: bool) -> void: _update_options())
	concept_note = _label(form, "", 13, true)
	# Developer choices; players get the server's own setup (see apply_info).
	dev_box = VBoxContainer.new()
	dev_box.visible = BuildMode.developer()
	form.add_child(dev_box)
	_label(dev_box, tr("개발용 생성 설정"), 15)
	var dev := GridContainer.new()
	dev.columns = 2
	resized.connect(func() -> void: dev.columns = 2 if size.x > 480 else 1)
	dev_box.add_child(dev)
	designer = _option(dev, [tr("샘플 설계 · API 비용 없음"), tr("LLM 설계 · 서버 설정 사용")])
	geometry = _option(dev, [tr("검증용 도형 · Tripo 비용 없음"), tr("Tripo 실제 생성 · 크레딧 사용")])
	models = _option(dev, ["gpt-6-luna", "gpt-5.6-terra", "gpt-6-sol", "gpt-6-astra"])
	efforts = _option(dev, ["low", "medium", "high", "xhigh"])
	efforts.select(2)
	for control in [designer, geometry]: control.item_selected.connect(func(_i: int) -> void: _update_options())
	var price_row := HBoxContainer.new()
	price_row.add_theme_constant_override("separation", 8)
	form.add_child(price_row)
	price_row.add_child(RpgUi.icon("res://assets/starseed.svg", 22))
	price_label = _label(price_row, "", 14, true)
	ask = _button(form, tr("의뢰하기"), request, "gold")
	held_note = _label(form, "", 13, true)
	held_note.visible = false

func _file_dialog() -> FileDialog:
	if file_dialog == null:
		file_dialog = FileDialog.new()
		file_dialog.access = FileDialog.ACCESS_FILESYSTEM
		file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
		file_dialog.filters = PackedStringArray(["*.png,*.jpg,*.jpeg ; Reference image"])
		add_child(file_dialog)
		file_dialog.file_selected.connect(pick_image)
	return file_dialog

func pick_image(path: String) -> void:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 1024 * 1024:
		_say(tr("이미지는 1MB 이하로 준비해 주세요"))
		return
	var bytes := file.get_buffer(file.get_length())
	image_data = "data:image/" + ("png" if path.get_extension().to_lower() == "png" else "jpeg") + ";base64," + Marshalls.raw_to_base64(bytes)
	image_label.text = path.get_file()
	if _llm(): designer.select(1)
	_update_options()

func _tripo() -> bool:
	return geometry.selected == 1

## fixture = the free sample designer; live servers without an LLM send the words straight to Tripo
## ("simple": one static piece, no photo).
func _design() -> String:
	if designer.selected == 1: return "llm"
	return "simple" if _tripo() and _live() else "fixture"

func _fits(credits: int) -> bool:
	return cap == 0 or credits <= cap

## Opens each option whose cheapest craft fits the cap and shows the price and the concept note.
func _update_options() -> void:
	if surface == null: return
	var tripo := _tripo()
	surface.set_item_disabled(0, not _fits(20))
	if not _fits(20) and surface.selected == 0: surface.select(1)
	var simple := _design() == "simple"
	# Moving furniture needs two Tripo meshes, or one when the game makes every moving part (a clock).
	var moving_meshes := int(kind_info.get("moving_meshes", 2))
	motion.set_item_disabled(1, not _fits(10 * moving_meshes) or simple)
	if (not _fits(10 * moving_meshes) or simple) and motion.selected == 1: motion.select(0)
	# A photo is read by the LLM designer.
	var photos := _llm() and _fits(20)
	for b in photo_buttons: b.disabled = not photos
	if not photos and not image_data.is_empty():
		image_data = ""
		image_label.text = tr("참고 이미지 없음")
	mesh_model.set_item_disabled(1, not _fits(100))
	if not _fits(100) and mesh_model.selected == 1: mesh_model.select(0)
	refine.disabled = image_data.is_empty() or not _fits(25)
	if refine.disabled: refine.button_pressed = false
	var textured := surface.selected == 0
	var moving := motion.selected == 1
	var photo := not image_data.is_empty()
	var unit := (10 + (10 if photo else 0) + (10 if textured else 0)) if mesh_model.selected == 0 else (110 if textured else 100)
	if photo and refine.button_pressed: unit += 5
	# A clock is always made with its hands (free): the moving option is chosen for the player.
	var forced := bool(kind_info.get("always_moving", false)) and not simple and not motion.is_item_disabled(1) and (not tripo or _fits(unit * moving_meshes))
	motion.set_item_disabled(0, forced)
	if forced and motion.selected != 1:
		motion.select(1)
		forced_motion = true
	elif not forced and forced_motion:
		motion.select(0)
		forced_motion = false
	moving = motion.selected == 1
	var least := unit * (moving_meshes if moving else 1)
	var concept := not photo and not moving
	var with_concept := (unit + 10 + CONCEPT_CREDITS) if mesh_model.selected == 0 else unit + CONCEPT_CREDITS
	var stars := (40 if textured else 20) + (10 if moving else 0)
	var over := tripo and cap > 0 and least > cap
	price_label.text = tr("별씨 %d · Tripo 약 %d크레딧") % [stars, with_concept if concept and _fits(with_concept) else least] if tripo else tr("별씨 %d") % stars
	if over: price_label.text += tr(" · 한도 %d 크레딧을 넘어요") % cap
	concept_note.visible = concept or forced
	if forced:
		concept_note.text = tr("%s는 바늘이 실제 시각에 맞춰 움직이도록 만들어요. 바늘은 공방이 무료로 달아 드려요.") % tr(str(kind_info.get("names", {}).get("ko", "시계")))
	elif concept:
		concept_note.text = tr("사진이 없으면 AI가 먼저 그림을 그려 보여 드려요. 마음에 들면 그 그림으로 3D를 만들어요. (그림 1장 5크레딧)") if not tripo or _fits(with_concept) else tr("이번에는 그림 단계 없이 글로 만들어요. (1회 한도)")
	# Live servers build only with Tripo; a local world makes free sample shapes.
	var ready_to_build := tripo or not _live()
	ask.disabled = busy or over or not ready_to_build
	if not ready_to_build: price_label.text = tr("공방 장인이 자리를 비워 지금은 제작할 수 없어요.")

func _body() -> Dictionary:
	var body := _base_body()
	# Older servers do not know these fields (and refuse unknown ones).
	if not style_buttons.is_empty(): body["style"] = style_id
	if not size_buttons.is_empty(): body["size"] = size_id
	return body

func _base_body() -> Dictionary:
	var tripo := _tripo()
	return {"prompt": prompt.text.strip_edges(), "material": "textured" if surface.selected == 0 else "mesh",
		"motion": "dynamic" if motion.selected == 1 else "static", "designer": _design(), "geometry": "tripo" if tripo else "proxy",
		"mesh_model": "v3.1-20260211" if mesh_model.selected == 0 else "P2-20260801",
		"model": models.get_item_text(models.selected), "effort": efforts.get_item_text(efforts.selected),
		"image": image_data, "image_mode": "refine" if tripo and not image_data.is_empty() and refine.button_pressed else "original",
		"concept": image_data.is_empty() and motion.selected == 0}

## Asks the server what the words name (after a short pause in typing) and updates the options.
## Older servers do not know the question: the form works as before.
func _ask_kind() -> void:
	var words := prompt.text.strip_edges()
	if not kind_supported or not is_instance_valid(api): return
	if words.length() < 2:
		kind_info = {}
		_update_options()
		return
	var reply: Dictionary = await api.post("/v1/studio/kind", {"prompt": words})
	if not is_instance_valid(prompt) or prompt.text.strip_edges() != words: return
	if reply.ok and reply.data is Dictionary: kind_info = reply.data
	else:
		kind_info = {}
		if int(reply.get("status", 0)) in [404, 405]: kind_supported = false
	_update_options()

func request() -> void:
	if busy or not job_id.is_empty(): return
	var length := prompt.text.strip_edges().length()
	if length < 2 or length > 1500:
		_say(_explain("invalid_craft_request"))
		return
	busy = true
	_update_options()
	var reply: Dictionary = await api.post("/v1/studio/jobs", api.mutation(_body()))
	busy = false
	_update_options()
	if not reply.ok:
		_say(_explain(reply.error))
		return
	job_id = str(reply.data.id)
	job_started.emit(job_id)
	_say(tr("설계를 준비하고 있어요. 다른 가구를 꾸미며 기다릴 수 있어요."))
	follow()

# ------------------------------------------------------------------ the craft under way

## Polls the craft until it needs the player or finishes.
func follow() -> void:
	if not self_poll:
		follow_requested.emit()
		return
	if polling or job_id.is_empty(): return
	polling = true
	var failures := 0
	while not job_id.is_empty() and is_inside_tree():
		var asked := job_id
		var reply: Dictionary = await api.request("/v1/studio/jobs/" + job_id)
		if not is_inside_tree(): break
		if asked != job_id: continue
		if not reply.ok:
			# A craft that is gone stops; a dropped connection or a busy server is asked again, slower each time.
			if int(reply.get("status", 0)) == 404:
				job_id = ""
				_show_form()
				break
			failures += 1
			await get_tree().create_timer(poll_pause(failures)).timeout
			continue
		failures = 0
		show_job(reply.data)
		var state := str(reply.data.state)
		if state == "awaiting_confirmation":
			if announce_key(reply.data) != announced:
				announced = announce_key(reply.data)
				_say(ready_words(reply.data))
				chime("twinkle")
			break
		if state in TERMINAL:
			job_id = ""
			job_finished.emit(reply.data)
			if state == "ready": chime("tune")
			break
		await get_tree().create_timer(2.0).timeout
	polling = false

## Seconds before asking again after `failures` failed polls in a row: 4, 8, 16, then 30.
static func poll_pause(failures: int) -> float:
	return minf(MAX_POLL_PAUSE, 2.0 * pow(2.0, failures))

## Names the picture (or quote) the player is told about once: the job and its draw count.
static func announce_key(value: Dictionary) -> String:
	return str(value.get("id", "")) + ":" + str(value.get("concept", {}).get("draws", 0))

## What the toast says when the craft needs the player; `away` (the village window is closed) adds
## how to open it.
static func ready_words(value: Dictionary, away := false) -> String:
	var picture: bool = not value.get("concept", {}).is_empty()
	if away: return TranslationServer.translate("AI가 그림을 그렸어요! C를 눌러 확인해 주세요." if picture else "설계와 견적이 나왔어요! C를 눌러 확인해 주세요.")
	return TranslationServer.translate("AI가 그림을 그렸어요! 마음에 드는지 확인해 주세요." if picture else "설계와 견적이 나왔어요! 확인하고 제작을 맡겨 주세요.")

## A short sound for a craft moment (the picture is ready, the object is done).
static func chime(kind: String) -> void:
	if DisplayServer.get_name() == "headless": return
	Fx.sound(null, kind, Vector3.INF, 1.0, 4.0)

func show_job(value: Dictionary) -> void:
	job = value
	var state := str(value.get("state", ""))
	if state in WORKING:
		form.visible = false
		_show_working(value)
		return
	_clear_status()
	if state.is_empty() or state in ["failed", "cancelled"]:
		_show_form()
		if state == "failed":
			# A Tripo part that never finished stops at its deadline (asset_studio.py overdue).
			var words := tr("공방이 너무 오래 걸려 이번 제작을 멈췄어요. 맡긴 별씨는 돌려드렸어요.") if str(value.get("error", "")) == "generation_timeout" else tr("제작에 실패했어요. 맡긴 별씨는 돌려드렸어요.")
			_label(status, words, 15, false, RpgUi.ACCENT)
		return
	form.visible = false
	if state == "awaiting_confirmation":
		_label(status, tr("그림이 나왔어요!") if not value.get("concept", {}).is_empty() else tr("설계가 끝났어요!"), 20)
		_steps(status, value, "confirm")
		_show_quote(value)
	elif state == "ready":
		var title := _label(status, tr("완성했어요!"), 22, false, _accent())
		RpgUi.pop_in(title, 0.36, 0.7)
		_steps(status, value, "done")
		_label(status, tr("가방에 들어왔어요. 마을이든 집이든 비어 있는 곳에 놓을 수 있어요."), 15)
		var object_id := str(value.get("object_id", ""))
		var row := _row(status)
		if place_action.is_valid(): _button(row, place_label, func() -> void: place_action.call(object_id), "gold")
		_button(row, tr("새로 만들기"), _start_over)
	elif state == "unknown":
		# The server could not tell whether Tripo got the request; an operator checks and refunds it.
		_label(status, tr("확인이 필요해요"), 20)
		_label(status, tr("공방이 Tripo에 보낸 요청이 닿았는지 확인하지 못했어요. 운영자가 확인하면 맡긴 별씨가 돌아와요. 그동안 새 물건을 만들 수 있어요."), 15)
		_button(_row(status), tr("새로 만들기"), _start_over, "gold")
	else: _show_working(value)

func _start_over() -> void:
	job = {}
	new_craft.emit()
	_show_form()

func _show_form() -> void:
	form.visible = true
	_clear_status()
	_update_options()

func _clear_status() -> void:
	for child in status.get_children(): child.queue_free()
	working = {}

# ------------------------------------------------------------------ steps

## While the server works: a turning starseed and the step title, the steps (설계 → 그림 → 3D 부품 →
## 완성) with the current one breathing, and a bar with Tripo's own percentage once it reports one.
## Built once and updated by each poll, so the motion never restarts.
func _show_working(value: Dictionary) -> void:
	var stages := _stages(value)
	var stage := _stage(value)
	if working.is_empty() or working.stages != stages or not is_instance_valid(working.root):
		_clear_status()
		var root := VBoxContainer.new()
		root.add_theme_constant_override("separation", 10)
		status.add_child(root)
		var head := HBoxContainer.new()
		head.add_theme_constant_override("separation", 8)
		root.add_child(head)
		var seed := RpgUi.icon("res://assets/starseed.svg", 26)
		seed.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		head.add_child(seed)
		if not RpgUi.calm():
			seed.pivot_offset = Vector2(13, 13)
			seed.create_tween().set_loops().tween_property(seed, "rotation", TAU, 2.4).from(0.0)
		var title := _label(head, "", 20)
		var steps := _steps(root, value, stage)
		var meter := HBoxContainer.new()
		meter.add_theme_constant_override("separation", 8)
		root.add_child(meter)
		var bar := ProgressBar.new()
		bar.custom_minimum_size = Vector2(0, 14)
		bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		bar.show_percentage = false
		meter.add_child(bar)
		var percent := _label(meter, "", 13, true)
		percent.size_flags_horizontal = Control.SIZE_SHRINK_END
		percent.autowrap_mode = TextServer.AUTOWRAP_OFF
		_label(root, tr("창을 닫아도 계속 만들어져요. 완성되면 알려 드릴게요."), 14, true)
		working = {"root": root, "stages": stages, "title": title, "steps": steps, "bar": bar, "percent": percent}
	var titles := {"design": tr("장인이 설계도를 그리고 있어요…"), "concept": tr("AI가 그림을 그리고 있어요…"), "mesh": tr("공방에서 3D로 빚고 있어요…")}
	working.title.text = tr("주문을 접수했어요") if str(value.get("state")) == "queued" and stage == "design" else str(titles.get(stage, tr("제작 중이에요…")))
	_paint_steps(working.steps, stage, value)
	var bar: ProgressBar = working.bar
	var progress = value.get("progress")
	var known := (progress is float or progress is int) and stage == "mesh"
	bar.indeterminate = not known
	working.percent.text = ("%d%%" % roundi(float(progress) * 100.0)) if known else ""
	working.percent.visible = known
	if known: bar.create_tween().tween_property(bar, "value", clampf(float(progress) * 100.0, 0.0, 100.0), 0.8).set_trans(Tween.TRANS_SINE)

## The steps this craft goes through (server stages); older servers send none, so the state names them.
func _stages(value: Dictionary) -> Array:
	var stages: Array = value.get("stages", [])
	if stages.is_empty():
		stages = ["design", "mesh", "done"]
		if not value.get("concept", {}).is_empty(): stages.insert(1, "concept")
	return stages

func _stage(value: Dictionary) -> String:
	var stage := str(value.get("stage", ""))
	if not stage.is_empty(): return stage
	var state := str(value.get("state", ""))
	if state in ["queued", "planning"]: return "design"
	if state == "awaiting_confirmation": return "confirm"
	if state in ["building", "submitting"]: return "mesh"
	return "done" if state == "ready" else state

func _step_name(id: String) -> String:
	match id:
		"design": return tr("설계")
		"concept": return tr("그림")
		"mesh": return tr("3D 부품")
	return tr("완성")

## A row of numbered dots joined by lines; returns the pieces _paint_steps colours.
func _steps(parent: Node, value: Dictionary, stage: String) -> Array:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(row)
	var steps := []
	var stages := _stages(value)
	for i in stages.size():
		var line: ColorRect = null
		if i > 0:
			# The joining line sits at the dots' middle, not the captions'.
			var lane := VBoxContainer.new()
			lane.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			lane.add_theme_constant_override("separation", 0)
			row.add_child(lane)
			var gap := Control.new()
			gap.custom_minimum_size.y = 12.5
			lane.add_child(gap)
			line = ColorRect.new()
			line.custom_minimum_size = Vector2(10, 3)
			line.mouse_filter = Control.MOUSE_FILTER_IGNORE
			lane.add_child(line)
		var cell := VBoxContainer.new()
		cell.add_theme_constant_override("separation", 3)
		row.add_child(cell)
		var dot := Panel.new()
		dot.custom_minimum_size = Vector2(28, 28)
		dot.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		dot.pivot_offset = Vector2(14, 14)
		dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		cell.add_child(dot)
		var number := Label.new()
		number.text = str(i + 1)
		number.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		number.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		number.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		number.add_theme_font_size_override("font_size", 13)
		dot.add_child(number)
		var tick := Line2D.new()
		tick.points = PackedVector2Array([Vector2(8, 14.5), Vector2(12.5, 19), Vector2(20.5, 9.5)])
		tick.width = 3.0
		tick.default_color = RpgUi.PAPER_INK
		tick.begin_cap_mode = Line2D.LINE_CAP_ROUND
		tick.end_cap_mode = Line2D.LINE_CAP_ROUND
		tick.joint_mode = Line2D.LINE_JOINT_ROUND
		tick.antialiased = true
		dot.add_child(tick)
		var caption := Label.new()
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.add_theme_font_size_override("font_size", 12)
		cell.add_child(caption)
		steps.append({"id": str(stages[i]), "dot": dot, "number": number, "tick": tick, "caption": caption, "line": line, "mode": ""})
	_paint_steps(steps, stage, value)
	return steps

## Steps before the current one are done (gold, ticked), the current one breathes, later ones wait.
## "confirm" (the quote) leaves the 3D step outlined: it starts when the player says so.
func _paint_steps(steps: Array, stage: String, value: Dictionary) -> void:
	var target := "mesh" if stage == "confirm" else stage
	var index := -1
	if stage == "done": index = steps.size()
	for i in steps.size():
		if index < 0 and steps[i].id == target: index = i
	index = maxi(index, 0)
	var parts: Dictionary = value.get("parts", {})
	for i in steps.size():
		var step: Dictionary = steps[i]
		var mode := "done" if i < index else ("pending" if i > index else ("next" if stage == "confirm" else "active"))
		_paint_step(step, mode)
		var name := _step_name(step.id)
		if step.id == "mesh" and stage == "mesh" and parts.size() > 1:
			name += " %d/%d" % [parts.values().filter(func(s) -> bool: return s == "ready").size(), parts.size()]
		step.caption.text = name

func _paint_step(step: Dictionary, mode: String) -> void:
	var before := str(step.mode)
	if before == mode: return
	step.mode = mode
	var gold := Color("e9b552")
	var ink: Color = RpgUi.INK if dark else RpgUi.PAPER_INK
	var muted := Color(ink, 0.35)
	var lit := mode != "pending"
	var box := StyleBoxFlat.new()
	box.set_corner_radius_all(14)
	box.corner_detail = 8
	box.anti_aliasing = true
	box.set_border_width_all(3 if lit else 2)
	box.border_color = gold if lit else muted
	box.bg_color = gold if mode == "done" else (Color(gold, 0.2) if lit else Color(0, 0, 0, 0))
	var dot: Panel = step.dot
	dot.add_theme_stylebox_override("panel", box)
	step.tick.visible = mode == "done"
	step.number.visible = mode != "done"
	step.number.add_theme_color_override("font_color", _accent() if lit else muted)
	step.caption.add_theme_color_override("font_color", ink if lit else muted)
	if step.line: step.line.color = gold if lit else muted
	if step.has("pulse") and step.pulse.is_valid(): step.pulse.kill()
	dot.scale = Vector2.ONE
	if RpgUi.calm(): return
	if mode == "active":
		var pulse := dot.create_tween().set_loops()
		pulse.tween_property(dot, "scale", Vector2.ONE * 1.14, 0.6).set_trans(Tween.TRANS_SINE)
		pulse.tween_property(dot, "scale", Vector2.ONE, 0.6).set_trans(Tween.TRANS_SINE)
		step.pulse = pulse
	elif mode == "done" and before == "active":
		# A step finishing pops its tick.
		dot.scale = Vector2.ONE * 1.3
		dot.create_tween().tween_property(dot, "scale", Vector2.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)

## Gold on the dark drawer, a deeper amber on the paper card.
func _accent() -> Color:
	return RpgUi.GOLD if dark else Color("8a5a1c")

func _show_quote(value: Dictionary) -> void:
	var quote: Dictionary = value.get("provenance", {})
	var concept: Dictionary = value.get("concept", {})
	var design: Dictionary = value.get("design", {})
	var look := _entry("styles", str(quote.get("style", "")))
	if not look.is_empty():
		var chosen := _entry("sizes", str(quote.get("size", "auto")))
		_label(status, tr("스타일 %s · 크기 %s") % [_name(look), _size_text(chosen) if not chosen.is_empty() else tr("자동")], 13, true)
	if not concept.is_empty():
		_label(status, tr("AI가 그린 그림이에요. 이 그림으로 3D를 만들까요?"), 15)
		var picture := TextureRect.new()
		picture.custom_minimum_size = Vector2(0, 260)
		picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		status.add_child(picture)
		_load_picture(picture, str(concept.get("url", "")))
	if not design.get("parts", []).is_empty():
		_label(status, tr("AI가 이렇게 정리했어요 (Tripo에 보내는 문장)"), 13, false, RpgUi.GOLD if dark else Color("8a5a1c"))
		for part in design.parts:
			_label(status, "• %s: %s" % [part.id, part.prompt], 13, true)
	var rate: float = float(quote.get("stars_per_credit", 1.0))
	var reserved := int(value.get("cost", 20))
	var row := _row(status)
	if concept.is_empty():
		_label(status, tr("확정하면 바로 만들기 시작해요. 제작비 별씨 %d") % int(quote.get("quoted_game_cost", reserved)), 15)
		_button(row, tr("제작 확정"), func() -> void: confirm(true), "gold")
	else:
		var with_picture := maxi(reserved, ceili(_number(concept.get("estimate_with_concept")) * rate))
		var with_text := maxi(reserved, ceili(_number(concept.get("estimate_text_only")) * rate))
		_button(row, tr("이 그림으로 만들기 · 별씨 %d") % with_picture, func() -> void: confirm(true), "gold")
		var redraw := _button(row, tr("다시 그리기 (+5크레딧)"), redraw_concept)
		var draws := int(concept.get("draws", 1))
		var next_total := int(_number(concept.get("estimate_with_concept"))) + CONCEPT_CREDITS
		redraw.disabled = draws >= int(concept.get("max_draws", 4)) or (cap > 0 and next_total > cap)
		if redraw.disabled: redraw.tooltip_text = tr("그림은 최대 %d장까지, 1회 한도 안에서 그릴 수 있어요.") % int(concept.get("max_draws", 4))
		var text_row := _row(status)
		_button(text_row, tr("그림 없이 글로 만들기 · 별씨 %d") % with_text, func() -> void: confirm(false))
		row = text_row
	if preview_action.is_valid(): _button(row, tr("모습 미리보기"), func() -> void: preview_action.call(job_id))
	_button(row, tr("취소하고 별씨 돌려받기"), cancel)

func _load_picture(target: TextureRect, url: String) -> void:
	if url.is_empty(): return
	if textures.has(url):
		target.texture = textures[url]
		return
	var reply: Dictionary = await api.request(url.split("?")[0], {}, HTTPClient.METHOD_GET, true)
	if not reply.ok or not is_instance_valid(target): return
	var image := Image.new()
	var bytes: PackedByteArray = reply.bytes
	var error := image.load_jpg_from_buffer(bytes)
	if error != OK: error = image.load_png_from_buffer(bytes)
	if error != OK: return
	textures[url] = ImageTexture.create_from_image(image)
	target.texture = textures[url]

func confirm(use_picture: bool) -> void:
	if busy or job_id.is_empty(): return
	busy = true
	var reply: Dictionary = await api.post("/v1/studio/jobs/" + job_id + "/confirm", api.mutation({"use_concept": use_picture}))
	busy = false
	if not reply.ok:
		_say(_explain(reply.error))
		return
	RpgUi.sfx("click")
	_say(tr("확인한 설계로 3D 메시를 만들고 있어요"))
	follow()

func redraw_concept() -> void:
	if busy or job_id.is_empty(): return
	busy = true
	var reply: Dictionary = await api.post("/v1/studio/jobs/" + job_id + "/redraw", api.mutation())
	busy = false
	if not reply.ok:
		_say(_explain(reply.error))
		return
	follow()

func cancel() -> void:
	if busy or job_id.is_empty(): return
	busy = true
	var reply: Dictionary = await api.post("/v1/studio/jobs/" + job_id + "/cancel", api.mutation())
	busy = false
	if not reply.ok:
		_say(_explain(reply.error))
		return
	var cancelled := {"id": job_id, "state": "cancelled"}
	job_id = ""
	job_finished.emit(cancelled)
	_show_form()

# ------------------------------------------------------------------ styles and sizes

## Builds the style and size buttons from the server's lists (once; they rarely change).
func _fill_styles() -> void:
	var styles: Array = info.get("styles", [])
	var sizes: Array = info.get("sizes", [])
	if styles.is_empty() or not style_buttons.is_empty(): return
	if _entry("styles", style_id).is_empty(): style_id = str(info.get("default_style", styles[0].get("id", "rpg")))
	var group := ButtonGroup.new()
	for entry in styles:
		var id := str(entry.get("id", ""))
		var b := _choice(style_grid, _name(entry), group, func() -> void: _pick_style(id))
		b.tooltip_text = str(entry.get("hints", {}).get(I18n.language(), entry.get("hints", {}).get("ko", "")))
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.clip_text = true
		style_buttons[id] = b
	if _entry("sizes", size_id).is_empty(): size_id = "auto"
	var sizes_group := ButtonGroup.new()
	for entry in sizes:
		var id := str(entry.get("id", ""))
		var b := _choice(size_row, _size_text(entry), sizes_group, func() -> void: _pick_size(id))
		if float(entry.get("meters", 0)) <= 0.0: b.tooltip_text = tr("AI가 물건에 맞는 실제 크기로 정해요")
		size_buttons[id] = b
	for control in [style_title, style_grid]: control.visible = true
	for control in [size_title, size_row]: control.visible = not sizes.is_empty()
	_show_choice(style_buttons, style_id)
	_show_choice(size_buttons, size_id)

func _choice(parent: Node, value: String, group: ButtonGroup, callback: Callable) -> Button:
	var b := Button.new()
	b.text = value
	b.toggle_mode = true
	b.button_group = group
	b.custom_minimum_size.y = 38
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(func() -> void: callback.call())
	parent.add_child(b)
	return b

func _pick_style(id: String) -> void:
	style_id = id
	_show_choice(style_buttons, id)
	_save_choice()

func _pick_size(id: String) -> void:
	size_id = id
	_show_choice(size_buttons, id)
	_save_choice()

## The chosen button stays pressed and turns gold.
func _show_choice(buttons: Dictionary, id: String) -> void:
	for key in buttons:
		var b: Button = buttons[key]
		b.set_pressed_no_signal(key == id)
		b.theme_type_variation = "GoldButton" if key == id else ""

func _save_choice() -> void:
	RpgUi.sfx("click")
	var config := ConfigFile.new()
	config.load(I18n.settings_path())
	config.set_value(SETTINGS_SECTION, "style", style_id)
	config.set_value(SETTINGS_SECTION, "size", size_id)
	config.save(I18n.settings_path())

func _entry(list: String, id: String) -> Dictionary:
	for entry in info.get(list, []):
		if str(entry.get("id", "")) == id: return entry
	return {}

func _name(entry: Dictionary) -> String:
	var names: Dictionary = entry.get("names", {})
	return str(names.get(I18n.language(), names.get("ko", entry.get("id", ""))))

func _size_text(entry: Dictionary) -> String:
	var meters := float(entry.get("meters", 0))
	return _name(entry) + (tr(" · 약 %sm") % String.num(meters, 1) if meters > 0.0 else "")

# ------------------------------------------------------------------ helpers

## Sample-shape crafts have no Tripo estimate (null).
func _number(value) -> float:
	return float(value) if value is int or value is float else 0.0

func _say(value: String) -> void:
	if say.is_valid(): say.call(value)

func _explain(code: String) -> String:
	# Bad input in the craft window is about the description, never the login form's name and password.
	if code in ["invalid_craft_request", "invalid_request"]: return tr("만들 물건을 2~1500자로 적어 주세요.")
	# Some refusals arrive already worded (the per-account limit).
	if code.contains(" ") or not explain.is_valid(): return code
	return str(explain.call(code))

func _label(parent: Node, value: String, size := 15, muted := false, color := Color(0, 0, 0, 0)) -> Label:
	var l := Label.new()
	l.text = value
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	l.add_theme_font_size_override("font_size", size)
	if size >= 20: l.add_theme_font_override("font", RpgUi.FONT_DISPLAY)
	var tone: Color = color if color.a > 0.0 else ((RpgUi.INK if not muted else Color(RpgUi.INK, .72)) if dark else (RpgUi.PAPER_INK if not muted else RpgUi.PAPER_MUTED))
	l.add_theme_color_override("font_color", tone)
	parent.add_child(l)
	return l

## Button rows wrap, so the same window fits the village card and a room's narrow drawer.
func _row(parent: Node) -> HFlowContainer:
	var r := HFlowContainer.new()
	r.add_theme_constant_override("h_separation", 8)
	r.add_theme_constant_override("v_separation", 8)
	parent.add_child(r)
	return r

func _button(parent: Node, value: String, callback: Callable, variant := "") -> Button:
	var b := Button.new()
	b.text = value
	b.custom_minimum_size.y = 42
	b.focus_mode = Control.FOCUS_NONE
	if variant == "gold": b.theme_type_variation = "GoldButton"
	RpgUi.hover_motion(b, 1.03)
	b.pressed.connect(func() -> void: callback.call())
	parent.add_child(b)
	return b

func _option(parent: Node, items: Array) -> OptionButton:
	var o := OptionButton.new()
	o.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	o.fit_to_longest_item = false
	o.clip_text = true
	for value in items: o.add_item(str(value))
	parent.add_child(o)
	return o
