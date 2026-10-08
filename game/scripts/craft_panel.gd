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

signal job_started(job_id: String)
signal job_finished(job: Dictionary)
## Hosts that watch the craft themselves (the village keeps polling after its window closes) set
## "self_poll": false and get this instead of the panel polling.
signal follow_requested
## The player cleared a finished craft ("새로 만들기").
signal new_craft

const CONCEPT_CREDITS := 5
const TERMINAL := ["ready", "failed", "cancelled"]

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
	_update_options()

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
	var photo := _row(form)
	photo_buttons.append(_button(photo, tr("사진·그림 추가"), func() -> void: _file_dialog().popup_centered_ratio(0.7)))
	photo_buttons.append(_button(photo, tr("제거"), func() -> void:
		image_data = ""
		image_label.text = tr("참고 이미지 없음")
		_update_options()))
	image_label = _label(form, tr("참고 그림을 추가할 수 있어요"), 13, true)
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
	motion.set_item_disabled(1, not _fits(20) or simple)
	if (not _fits(20) or simple) and motion.selected == 1: motion.select(0)
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
	var least := unit * (2 if moving else 1)
	var concept := not photo and not moving
	var with_concept := (unit + 10 + CONCEPT_CREDITS) if mesh_model.selected == 0 else unit + CONCEPT_CREDITS
	var stars := (40 if textured else 20) + (10 if moving else 0)
	var over := tripo and cap > 0 and least > cap
	price_label.text = tr("별씨 %d · Tripo 약 %d크레딧") % [stars, with_concept if concept and _fits(with_concept) else least] if tripo else tr("별씨 %d") % stars
	if over: price_label.text += tr(" · 한도 %d 크레딧을 넘어요") % cap
	concept_note.visible = concept
	if concept:
		concept_note.text = tr("사진이 없으면 AI가 먼저 그림을 그려 보여 드려요. 마음에 들면 그 그림으로 3D를 만들어요. (그림 1장 5크레딧)") if not tripo or _fits(with_concept) else tr("이번에는 그림 단계 없이 글로 만들어요. (1회 한도)")
	# Live servers build only with Tripo; a local world makes free sample shapes.
	var ready_to_build := tripo or not _live()
	ask.disabled = busy or over or not ready_to_build
	if not ready_to_build: price_label.text = tr("공방 장인이 자리를 비워 지금은 제작할 수 없어요.")

func _body() -> Dictionary:
	var tripo := _tripo()
	return {"prompt": prompt.text.strip_edges(), "material": "textured" if surface.selected == 0 else "mesh",
		"motion": "dynamic" if motion.selected == 1 else "static", "designer": _design(), "geometry": "tripo" if tripo else "proxy",
		"mesh_model": "v3.1-20260211" if mesh_model.selected == 0 else "P2-20260801",
		"model": models.get_item_text(models.selected), "effort": efforts.get_item_text(efforts.selected),
		"image": image_data, "image_mode": "refine" if tripo and not image_data.is_empty() and refine.button_pressed else "original",
		"concept": image_data.is_empty() and motion.selected == 0}

func request() -> void:
	if busy or not job_id.is_empty(): return
	if prompt.text.strip_edges().length() < 2:
		_say(tr("만들 물건을 두 글자 이상 적어 주세요."))
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
	while not job_id.is_empty() and is_inside_tree():
		var reply: Dictionary = await api.request("/v1/studio/jobs/" + job_id)
		if not is_inside_tree(): break
		if not reply.ok: break
		show_job(reply.data)
		var state := str(reply.data.state)
		if state == "awaiting_confirmation": break
		if state in TERMINAL:
			job_id = ""
			job_finished.emit(reply.data)
			if state == "ready": RpgUi.sfx("click")
			break
		await get_tree().create_timer(2.0).timeout
	polling = false

func show_job(value: Dictionary) -> void:
	job = value
	var state := str(value.get("state", ""))
	for child in status.get_children(): child.queue_free()
	if state.is_empty() or state in ["failed", "cancelled"]:
		_show_form()
		if state == "failed": _label(status, tr("제작에 실패했어요. 맡긴 별씨는 돌려드렸어요."), 15, false, RpgUi.ACCENT)
		return
	form.visible = false
	var titles := {"queued": tr("주문을 접수했어요"), "planning": tr("장인이 설계도를 그리고 있어요…"), "awaiting_confirmation": tr("설계가 끝났어요!"),
		"building": tr("공방에서 만들고 있어요…"), "submitting": tr("공방에서 만들고 있어요…"), "unknown": tr("제작 결과를 확인하고 있어요…"), "ready": tr("완성했어요!")}
	_label(status, str(titles.get(state, tr("제작 중이에요…"))), 20)
	if state == "awaiting_confirmation": _show_quote(value)
	elif state == "ready":
		_label(status, tr("가방에 들어왔어요. 마을이든 집이든 비어 있는 곳에 놓을 수 있어요."), 15)
		var object_id := str(value.get("object_id", ""))
		var row := _row(status)
		if place_action.is_valid(): _button(row, place_label, func() -> void: place_action.call(object_id), "gold")
		_button(row, tr("새로 만들기"), func() -> void:
			job = {}
			new_craft.emit()
			_show_form())
	else:
		var bar := ProgressBar.new()
		bar.indeterminate = true
		bar.custom_minimum_size = Vector2(0, 14)
		status.add_child(bar)
		var parts: Dictionary = value.get("parts", {})
		if state == "building" and parts.size() > 1:
			var done := parts.values().filter(func(s) -> bool: return s == "ready").size()
			_label(status, tr(" · %d / %d부품 완료") % [done, parts.size()], 13, true)
		_label(status, tr("창을 닫아도 계속 만들어져요. 완성되면 알려 드릴게요."), 14, true)

func _show_form() -> void:
	form.visible = true
	for child in status.get_children(): child.queue_free()
	_update_options()

func _show_quote(value: Dictionary) -> void:
	var quote: Dictionary = value.get("provenance", {})
	var concept: Dictionary = value.get("concept", {})
	var design: Dictionary = value.get("design", {})
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

# ------------------------------------------------------------------ helpers

## Sample-shape crafts have no Tripo estimate (null).
func _number(value) -> float:
	return float(value) if value is int or value is float else 0.0

func _say(value: String) -> void:
	if say.is_valid(): say.call(value)

func _explain(code: String) -> String:
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
