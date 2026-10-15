extends Node3D

const Art = preload("res://scripts/art.gd")
const Loader = preload("res://scripts/model_loader.gd")
const PaintApply = preload("res://scripts/painter/paint_apply.gd")
const ObjectTransform = preload("res://scripts/object_transform.gd")
const ShapePanel = preload("res://scripts/shape_panel.gd")
const InteractionPanel = preload("res://scripts/interaction_panel.gd")
const Player = preload("res://scripts/player.gd")
const AvatarLook = preload("res://scripts/avatar_look.gd")
const ControllerProfile=preload("res://scripts/controller_profile.gd")
const Api = preload("res://scripts/api.gd")
const Sound = preload("res://scripts/sound.gd")
const Landscape = preload("res://scripts/world_detail.gd")
const TownLayout = preload("res://scripts/town.gd")
const I18n = preload("res://scripts/i18n.gd")
const RpgUi = preload("res://scripts/rpg_ui.gd")
const CraftPanel = preload("res://scripts/craft_panel.gd")
const CraftWindow = preload("res://scripts/craft_window.gd")
const CraftTracker = preload("res://scripts/craft_tracker.gd")
const CraftWords = preload("res://scripts/craft_words.gd")
const Fx = preload("res://scripts/fx.gd")
const Transition = preload("res://scripts/transition.gd")
const LoadPace = preload("res://scripts/load_pace.gd")
const Minimap = preload("res://scripts/minimap.gd")
const NpcBody = preload("res://scripts/npc.gd")
const WorldAudio = preload("res://scripts/world_audio.gd")
const Roads = preload("res://scripts/roads.gd")
const Daylight = preload("res://scripts/daylight.gd")
const CombatAudio = preload("res://scripts/combat_audio.gd")
const HeroVoice = preload("res://scripts/hero_voice.gd")
const SfxBank = preload("res://scripts/sfx_bank.gd")
const VoiceBabble = preload("res://scripts/voice_babble.gd")
const GameSettings = preload("res://scripts/game_settings.gd")
const SettingsMenu = preload("res://scripts/settings_menu.gd")
const PauseMenu = preload("res://scripts/pause_menu.gd")
## Game version and server notices (update window, new-version banner, maintenance countdown/screen).
const VersionGate = preload("res://scripts/version_gate.gd")
## Loaded first of all as an autoload (project.godot): this is that same, cached copy.
const PatchBoot = preload("res://scripts/patch_boot.gd")
const NpcGifts = preload("res://scripts/npc_gifts.gd")
const Brand = preload("res://scripts/brand.gd")
const SocialHud = preload("res://scripts/social_hud.gd")
## The building doors swing and the walker walks through them (entering and leaving rooms).
const VillageDoors = preload("res://scripts/village_doors.gd")
## Login presets. The PC server is the one with Tripo enabled; the online server
## is the hosted demo.
const SERVERS := [["local","http://127.0.0.1:8765","이 PC 월드"],["online","https://34-28-65-113.sslip.io","온라인 월드"]]
## School builds (export feature "villagen_school") play on the school server (Seoul VM) instead of
## the judging server. Empty until that server has an address; tools/package_release.py --school checks.
const SCHOOL_SERVER := "https://54-117-10-64.sslip.io"

## A world.cfg beside Villagen.exe replaces the online world, so another group can ship the
## same ZIP for its own server without rebuilding (docs/SHARE_GUIDE_KO.md):
##   [world]
##   name="우리 학과 월드"
##   url="https://1-2-3-4.sslip.io"
static func custom_world() -> Array:
	var config := ConfigFile.new()
	if OS.has_feature("editor") or config.load(OS.get_executable_path().get_base_dir().path_join("world.cfg"))!=OK: return []
	var url := str(config.get_value("world","url","")).strip_edges().trim_suffix("/")
	if not (url.begins_with("https://") or url.begins_with("http://")): return []
	return ["online",url,str(config.get_value("world","name","온라인 월드"))]

static func worlds() -> Array:
	var own := custom_world()
	if not own.is_empty(): return [SERVERS[0],own]
	if OS.has_feature("villagen_school") and not SCHOOL_SERVER.is_empty():
		return [SERVERS[0],["online",SCHOOL_SERVER,"학교 월드"]]
	return SERVERS
# Trading is deferred while the village / survival / generation loop is developed.
const TRADING_UI_ENABLED := false
const ITEM_NAMES := {"wood":"목재","stone":"돌","berry":"열매","fiber":"섬유","axe":"도끼","spear":"창","soup":"수프","bandage":"붕대"}
const COLORS := RpgUi.PALETTE
const RECIPES := {"axe":{"wood":3,"stone":2},"spear":{"wood":4,"stone":2},"soup":{"berry":3,"wood":1},"bandage":{"fiber":3}}
## Seconds the morning motif waits for the dawn sting (2.2 s takes) to ring out, and the window the
## win fanfare starts in once the hero's level-up chime (1.7-2.0 s takes) has rung.
const DAWN_RING := 2.4
const WIN_AFTER_MIN := 1.6
const WIN_AFTER_MAX := 2.0
## Sprint-start whoosh: a run-key press counts while moving; at most one every SPRINT_CUE_GAP s.
const SPRINT_CUE_GAP := 1.5
## Warded cue (monsters pushed back at the warm campfire): beasts within this many m of the camp, at
## most one cue every WARD_CUE_GAP s.
const WARD_REACH := 12.0
const WARD_CUE_GAP := 6.0
## Using a crafted object: one soft cue per click, at most one every USE_CUE_GAP_MS per object.
const USE_CUE_GAP_MS := 250
var api: Node
var gate: CanvasLayer
var social: Node
var coop_run := false
var furniture_proximity_time := 0.0
var furniture_event_pending := false
var sound: Node
var world: Node3D
var player: CharacterBody3D
## Sitting and lying on crafted seats and beds, as in rooms (rest_seat.gd; village_seat()).
var seat: Node
var camera: Camera3D
var environment: Environment
var sun: DirectionalLight3D
var ui: Control
var left: VBoxContainer
var right: VBoxContainer
var notice: Label
var wallet: Label
var metrics: Label
var pack: Label
var objects_list: ItemList
var object_info: Label
var prompt: LineEdit
var price: SpinBox
var screen := "login"
var me: Dictionary = {}
## The HUD medallion's live face (avatar_portrait.gd), made the first time the village HUD needs it.
var portrait_view: SubViewport
var selected: Dictionary = {}
var run: Dictionary = {}
var run_id := ""
var job_id := ""
var loaded: Dictionary = {}
var nodes: Dictionary = {}
var enemy_nodes: Dictionary = {}
var object_root: Node3D
var preview: Node3D
var preview_rotation := 0
## Placing: the turn bar (↶ angle ↷), the placed object being moved or turned (its old
## copy hides meanwhile) and whether the ghost follows the pointer yet.
var turn_hud: Control
var turn_readout: Label
var preview_moving := ""
var preview_follow := true
var preview_mouse := Vector2.ZERO
## The bag's 모양 바꾸기 window (shape_panel.gd) while it is open.
var shape_panel: Control
var shape_button: Button
var flame: Node3D
var busy := false
var ticking := false
## Client-side prediction of the expedition walker (see predict_walker).
var predicted := Vector2.INF
var predict_fix := Vector2.ZERO
var predict_log: Array = []
var tick_elapsed := 0.0
var poll_elapsed := 0.0
var entitlement_elapsed := 0.0
var polling_entitlements := false
var refreshing := false
var polling_job := false
var reward_button: Button
var hint: Label
var hp_bar: ProgressBar
var hunger_bar: ProgressBar
var hp_readout: Label
var hunger_readout: Label
var pending_action := ""
var pending_target := ""
var network_failures := 0
var world_epoch := 0
var craft_buttons: Dictionary = {}
var harvest_marker: MeshInstance3D
var objective: Label
## The card around `objective` (village tracker or the field's goal card).
var objective_card: Control
var minimap: Control
var frame: Dictionary = {}
var world_audio: Node
var daylight: Node
var step_distance := 0.0
var last_step_at := Vector3.ZERO
var ambience_elapsed := 10.0
## Landing and wading sounds (update_world_audio): airborne last frame, fastest fall since, in the
## shallows last frame, and when the last shallows splash played (msec).
var was_airborne := false
var fall_speed := 0.0
var was_wading := false
var wade_splash_at := 0
## Throttles (msec) for the frequent placement ticks (the prompt chip keeps its own: RpgUi.prompt).
var snap_tick_at := 0
var flip_tick_at := 0
var survival_deny_at := 0
## When the last sprint-start whoosh and warded cue played (s, Time ticks).
var sprint_cue_at := -10.0
var ward_cue_at := -100.0
var day_track: Label
## The boss night's health bar under the stage tracker (stage runs, run.boss), and the last hp seen.
var boss_panel: Control
var boss_meter: Dictionary = {}
var boss_last_hp := -1.0
var toast_lane: VBoxContainer
var last_notice := ""
var ambience: CPUParticles3D
var sun_defaults: Dictionary
var results_shown := false
var prior_day := 1
var prior_night := false
## The expedition guidance line last shown: it is said once per change, not on every state update.
var last_run_line := ""
var inspect_panel: PanelContainer
var inspect_view: SubViewport
var inspect_stage: Node3D
var inspect_model: Node3D
var inspect_request := 0
var stamina_bar: ProgressBar
var stamina_readout: Label
var supplies: Label
var camp_status: Label
var field_map: Control
## The field's map card (top right, where the village's minimap sits) and its icon hotbar
## (가방, 먹기, 모닥불, 붕대, 귀환: RpgUi.hotbar, fold id "toolbar").
var field_panel: Control
var toolbar_bar: HBoxContainer
var warmth_ring: MeshInstance3D
var strike_markers: Dictionary = {}
var repeat_action := 0.0
## The survival "end the expedition?" window (its RpgUi.window root) while it is open.
var return_dialog: Control
var last_camp_warning := -100.0
var canopy_elapsed := 0.0
var paused := false
var pause_shade: Control
var inventory_slots: Dictionary = {}
var quick_counts: Dictionary = {}
var expedition_button: Button
var village_modal: Control
## The painting workspace (scripts/painter/painter.gd) while it is open, and the bag's way in.
var painter: Control
## The interaction editor (scripts/interaction_panel.gd) while it is open.
var interaction_panel: Control
var paint_palette: HBoxContainer
var paint_button: Button
var paint_hint: Label
var npcs: Array[Node3D]=[]
## Village add-ons plug in here without touching this file. Each script is a Node
## (usually Node3D) added under the village world, with optional methods:
##   setup(app)                          once the walker and the NPCs exist
##   closest(at: Vector3) -> Dictionary   {"prompt":String,"distance":float,...} or {}
##   interact(entry: Dictionary)         E pressed on what closest() returned
##   leave()                             the village is about to be torn down
## Missing scripts are skipped, so each add-on can land on its own.
## story.gd (the opening chapter) comes before shadow_folk.gd: it holds 모카's plan before her walker is placed.
const VILLAGE_MODULES := ["res://scripts/building_dressing.gd","res://scripts/village_doors.gd","res://scripts/field_objects.gd","res://scripts/story.gd","res://scripts/shadow_folk.gd","res://scripts/occluder_fade.gd","res://scripts/guide.gd","res://scripts/treasure.gd"]
var modules: Array[Node]=[]
var prompt_wait := 0.0
var chosen_map := "forest"
var chosen_difficulty := "standard"
var town: Node3D
var life: Node
var camera_focus := Vector3.ZERO
var camera_focus_ready := false
var camera_zoom_target := ControllerProfile.CAMERA_DEFAULT
var camera_zoom_active := false
var developer_label: Label
var developer_panel: Control
## The title's page ("checking" while the launch version check runs).
var title_page := ""

func _ready() -> void:
	I18n.setup()
	# Window, renderer, buses, key bindings, UI scale (game_settings.gd).
	GameSettings.apply_all(get_tree())
	var veil := Transition.of(get_tree())
	# The first load shows the island cover art; a walk out of a room keeps its card. At the game's
	# start boot.gd (main.tscn's first node) has drawn it already: it stays as it is (same tip).
	if not Engine.has_meta("studio_session") and not (veil.card.visible and veil.style == "start"): veil.loading("", "start")
	veil.cover()
	# The ambience is synthesized on a worker thread meanwhile (world_audio.setup() below waits for it).
	WorldAudio.prepare()
	api = Api.new()
	add_child(api)
	gate = VersionGate.new()
	add_child(gate)
	gate.watch(api)
	gate.resumed.connect(gate_resumed)
	gate.logout_required.connect(force_logout)
	social = preload("res://scripts/social.gd").new()
	social.app = self
	add_child(social)
	sound = Sound.new()
	add_child(sound)
	world_audio = WorldAudio.new()
	add_child(world_audio)
	# The first start sets it up once the village is built (by then its thread is done).
	if Engine.has_meta("studio_session"): world_audio.setup()
	life=preload("res://scripts/village_life.gd").new()
	life.app=self
	add_child(life)
	ControllerProfile.ensure_input()
	Loader.warm_up_compression()
	var e := WorldEnvironment.new()
	environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("b7ccd1")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.WHITE
	environment.ambient_light_energy = 0.35
	environment.tonemap_mode=Environment.TONE_MAPPER_LINEAR
	e.environment = environment
	add_child(e)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48,-32,0)
	sun.light_color=Color("fff5e9")
	sun.light_energy = 0.25
	sun.shadow_enabled = true
	add_child(sun)
	daylight = Daylight.new()
	daylight.name = "Daylight"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--hour="): daylight.override_hour = clampf(float(arg.trim_prefix("--hour=")),0.0,23.99)
	add_child(daylight)
	sun_defaults={"rotation":sun.rotation_degrees,"bias":sun.shadow_bias,"normal_bias":sun.shadow_normal_bias,"distance":sun.directional_shadow_max_distance}
	apply_graphics()
	# A method, not a lambda: the static listener list holding a lambda crashed the game on exit.
	GameSettings.listen(settings_changed)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = ControllerProfile.CAMERA_DEFAULT
	camera.current = true
	add_child(camera)
	var layer := CanvasLayer.new()
	add_child(layer)
	ui = Control.new()
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.theme = make_theme()
	layer.add_child(ui)
	if not Engine.has_meta("studio_session") and DisplayServer.get_name()!="headless":
		# Let the loading card reach the screen before the village is built.
		for i in 2: await get_tree().process_frame
	# Back from a room, enter_village() below builds the village (once, after the server answers).
	if not Engine.has_meta("studio_session"):
		# What the village needs loads on worker threads while the build goes on under the card.
		# (The village modules' scripts too: compiled on the main thread at the first build they held
		# frames of 30-140 ms.)
		LoadPace.want(TownLayout.resource_paths()+NpcBody.resource_paths(CAST.map(func(entry): return entry.cast))+AvatarLook.resource_paths()+VILLAGE_MODULES)
		await build_world(false)
		world_audio.setup()
		# The home is the first room after signing in: its scene reads in the background meanwhile.
		LoadPace.want([STUDIO_SCENE])
	if Engine.has_meta("studio_session"):
		# Back from a room: the village modules' scripts read on a worker thread while the server answers.
		LoadPace.want(VILLAGE_MODULES)
		var session: Dictionary=Engine.get_meta("studio_session")
		Engine.remove_meta("studio_session")
		api.token=session.token;api.base_url=session.url
		# The room hands over the look it showed, so the village walker wears it from the first frame.
		if session.get("profile") is Dictionary: me={"profile":session.profile}
		# No village yet while the server answers: nothing of main's own runs until enter_village() built it.
		hold(true)
		var server_status: Dictionary = await api.request("/health")
		hold(false)
		# Maintenance began during the walk out of the room: the gate already sent the player to the title.
		if api.token.is_empty(): return
		social.enabled = social.feature_enabled() and server_status.ok and int(server_status.data.get("multiplayer_protocol", 0)) == 1
		await enter_village()
		# The walker steps out of the open door and it shuts behind (village_doors.gd); no door there: the doorstep.
		if not VillageDoors.walk_out(self,str(session.get("room","workshop")),veil):
			player.position=TownLayout.door_return(str(session.get("room","workshop")))
			follow_camera(1)
			veil.play_door("close",str(session.get("room","workshop")))
			veil.fade_in()
	else:
		# The game opens on its title, which first asks the remembered world whether this version may
		# play: an update (patch or installer) or the maintenance screen comes before the menu.
		login_ui("checking")
		veil.fade_in()
		await gate.check(default_world())
		if screen=="login" and title_page=="checking": login_ui("menu")
		# This version reached its title: a downloaded patch works (patch_boot.gd stops counting).
		PatchBoot.confirm()
		# --log-load: when the title came (an exported game cannot run the test scripts that time it).
		if LoadPace.log_slow: print("LOAD_TITLE %d ms after the engine started" % Time.get_ticks_msec())
		print("[Villagen] v%s at the title (installed v%s%s)" % [Api.client_version(), PatchBoot.base_version, ", patched" if not PatchBoot.patch.is_empty() else ""])

## The shared cozy theme (fonts, parchment/night frames, buttons, fields, lists,
## sliders, tooltips). Built once in RpgUi so the studio and menus match.
func make_theme() -> Theme:
	return RpgUi.theme()

func clear_ui() -> void:
	# The chat and the 함께하기 drawer step back until the next HUD binds them (social.install_hud).
	SocialHud.release_place(self)
	craft_buttons.clear()
	inventory_slots.clear()
	quick_counts.clear()
	paused=false
	if is_instance_valid(return_dialog): return_dialog.queue_free()
	inspect_request+=1
	for child in ui.get_children():
		ui.remove_child(child)
		child.queue_free()

## A framed card. "default"/"hero" are parchment cards with dark ink; "night" and
## "objective" are HUD glass with cream text.
func panel(at: Vector2, width: float, variant := "default") -> VBoxContainer:
	var p := PanelContainer.new()
	p.position = at
	p.custom_minimum_size.x = width
	var night: bool = variant in ["night","objective"]
	var style := RpgUi.panel_style("night" if night else ("paper" if variant=="hero" else "paper_plain"))
	p.add_theme_stylebox_override("panel",style)
	if night: p.theme=night_theme()
	ui.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation",8)
	p.add_child(v)
	return v

## Overrides for controls on night glass (kept for callers; the theme lives in RpgUi).
static func night_theme() -> Theme:
	return RpgUi.night_theme()

func text(parent: Node, value: String, size := 15) -> Label:
	var l := Label.new()
	l.text = value
	l.add_theme_font_size_override("font_size",size)
	if size>=20: l.add_theme_font_override("font",RpgUi.FONT_DISPLAY)
	parent.add_child(l)
	return l

func rule(parent: Node) -> void:
	RpgUi.divider(parent)

## Buttons: "default" parchment key, "primary" leaf green, "gold" call to action,
## "slot" plain key in the current panel's look, "choice" a toggle that turns gold.
func button(parent: Node, value: String, callback: Callable, variant := "default") -> Button:
	var b := Button.new()
	b.text = value
	b.custom_minimum_size.y = 44 if variant in ["primary","slot","gold"] else 40
	b.focus_mode = Control.FOCUS_NONE
	match variant:
		"primary": b.theme_type_variation="PrimaryButton"
		"gold": b.theme_type_variation="GoldButton"
		"choice": b.theme_type_variation="ChoiceButton"
	RpgUi.hover_motion(b,1.03)
	b.pressed.connect(func(): callback.call())
	parent.add_child(b)
	return b

## kind: RpgUi.toast's kind ("info", "success", "warn", "error", "social"), which picks the pill's
## look and its chime (toast_success, toast_social ...).
func message(value: String, kind := "info") -> void:
	# Maintenance or a too-old game: the gate's one screen speaks instead of scattered errors.
	if VersionGate.is_blocked(): return
	# Server messages arrive in Korean; already translated client text passes through.
	value = I18n.server(value)
	if is_instance_valid(notice): notice.text = value
	# The shared toast lane (RpgUi.toast): a line still on screen refreshes, a new one stacks (max 3).
	if is_instance_valid(toast_lane) and not value.is_empty() and (value!=last_notice or RpgUi.find_toast(toast_lane,value)):
		last_notice=value
		RpgUi.toast(toast_lane,value,kind,{"sound":screen!="survival"})

## The HUD's toast lane at design y (520 px pills) and a hidden copy of the last line (notice).
func lay_toasts(y: float) -> void:
	toast_lane = RpgUi.toast_lane(ui,y,520)
	notice = Label.new()
	notice.name = "NoticeText"
	notice.visible = false
	ui.add_child(notice)
	last_notice = ""

func error_message(code: String) -> String:
	# Craft refusals read the same in the village and in rooms (craft_words.gd).
	var craft := CraftWords.refusal(code)
	if not craft.is_empty(): return craft
	var messages := {
		"server_update_required":tr("월드가 새 단장을 하고 있어요. 잠시 뒤 다시 들어와 주세요."),
		"invalid_credentials":tr("아이디 또는 비밀번호를 확인하세요."),"username_unavailable":tr("이미 사용 중인 이름입니다."),
		"invalid_request":tr("입력 형식을 확인하세요. 이름 3~24자, 비밀번호 10자 이상입니다."),
		"placement_overlap":tr("다른 물건과 겹칩니다."),
		"room_render_budget_exceeded":tr("꾸미기 용량이 꽉 찼습니다. 가구 일부를 회수한 뒤 배치해 주세요."),
		"login_locked":tr("비밀번호를 여러 번 틀려 잠시 잠겼어요. 15분 뒤에 다시 시도해 주세요."),
		"username_reserved":tr("이 이름은 쓸 수 없어요. 다른 모험가 이름을 골라 주세요."),
		"admin_grant_limit":tr("오늘 지급할 수 있는 양을 모두 썼어요."),
		"message_empty":tr("보낼 말을 적어 주세요."),
		"weak_password":tr("비밀번호에는 대문자와 특수문자가 하나 이상 들어가야 해요. (10자 이상)"),
		"invalid_invitation":tr("이 월드는 지금 새 모험가를 받지 않아요. 잠시 뒤 다시 시도하거나 '이 PC 월드'를 골라 주세요."),
		"spawn_area_reserved":tr("중앙 광장에는 놓을 수 없습니다."),"workshop_area_reserved":tr("공방 입구 앞은 비워 주세요."),"reserved_area":tr("길과 입구 앞은 비워 주세요."),
		"gate_area_reserved":tr("숲 입구에는 놓을 수 없습니다."),
		"session_expired":tr("오래 쉬어서 다시 들어와야 해요."),"session_reset":tr("다시 로그인해 주세요."),"object_not_found":tr("내 물건이 아니에요."),
		"stale_object_version":tr("물건이 그새 바뀌었어요. 가방을 다시 열어 주세요."),"object_is_listed":tr("판매 중인 물건입니다. 판매를 취소하세요."),
		"too_many_registrations":tr("이 곳에서는 오늘 계정을 더 만들 수 없어요. 만든 계정으로 로그인해 주세요."),
		"registration_closed_today":tr("오늘은 새 모험가를 더 받을 수 없어요. 내일 다시 찾아와 주세요."),
		"client_update_required":tr("새 버전을 받아야 계속할 수 있어요."),
		"server_maintenance":tr("서버 점검 중이에요. 잠시 뒤 다시 들어와 주세요.")}
	if not preload("res://scripts/build_mode.gd").developer():
		messages.server_update_required=tr("마을을 업데이트하고 있어요. 잠시 뒤 다시 접속해 주세요.")
	return str(messages.get(code,tr("요청을 완료하지 못했습니다: ")+code if preload("res://scripts/build_mode.gd").developer() else tr("지금은 완료하지 못했어요. 잠시 뒤 다시 시도해 주세요.")))

func check(result: Dictionary) -> bool:
	if not result.ok:
		refuse(error_message(result.error))
		return false
	return true

## A refusal or a failed request: message() with the soft deny in place of the toast's success
## chime (a kind played right before message() stamps RpgUi's toast dedupe, so that chime stays
## quiet). Only when message() raises a new toast: a line still on screen just refreshes, and the
## field's toasts are silent, so a repeated error never stacks denies.
func refuse(value: String) -> void:
	var line := I18n.server(value)
	if screen!="survival" and not line.is_empty() and not VersionGate.is_blocked() and is_instance_valid(toast_lane) and line!=last_notice and not RpgUi.find_toast(toast_lane,line):
		RpgUi.sfx("deny",-6.0)
	message(value)

## sound.effect(kind) a moment later (after a sting or a chime it would stack on), unless the
## screen has changed meanwhile.
func effect_later(kind: String, seconds: float) -> void:
	var on := screen
	get_tree().create_timer(seconds).timeout.connect(func():
		if is_instance_valid(sound) and screen==on: sound.effect(kind))

## HeroVoice.play(event) a moment later (forced: chance and gap skipped), the same way.
func voice_later(event: String, seconds: float, db := 0.0) -> void:
	var on := screen
	get_tree().create_timer(seconds).timeout.connect(func():
		if screen==on: HeroVoice.play(self,event,db,true))

## core/newday after the dawn sting, unless the run has ended (or another began) meanwhile.
func newday_later(seconds: float) -> void:
	var on := screen
	var id := run_id
	get_tree().create_timer(seconds).timeout.connect(func():
		if is_instance_valid(sound) and screen==on and run_id==id and run.get("status","")=="active": sound.effect("newday"))

## How long a take rings (its length less a short fade tail), kept within lo..hi s; hi when unknown.
func chime_length(path: String, lo: float, hi: float) -> float:
	var take: AudioStream = SfxBank.stream(path) if not path.is_empty() else null
	return clampf(take.get_length()-0.15 if take else hi, lo, hi)

## The world the login card opens on: the one remembered, or the build's default (player builds
## start online). A school build first opens on the school world even if an older build saved the
## judging one.
func default_world() -> String:
	var list := worlds()
	var saved := str(I18n.setting("server",list[1][1] if OS.has_feature("tripothon_player") else list[0][1]))
	if OS.has_feature("villagen_school") and saved==SERVERS[1][1]: saved=list[1][1]
	return saved

## Maintenance is over (or the minimum version was lowered): show the server's state again.
## Everything lives on the server, so the village or the expedition just reloads.
func gate_resumed() -> void:
	match screen:
		"village": await refresh_inventory()
		"survival":
			if run_id.is_empty(): return
			var epoch := world_epoch
			var snapshot: Dictionary = await api.request(run_route())
			if epoch==world_epoch and snapshot.ok:
				run=snapshot.data
				network_failures=0
				update_run()

## The key art for the hour the game opens at (the player's own clock): morning to afternoon, golden hour
## around sunset, and the lantern-lit village at night.
static func title_art_for(hour: float) -> String:
	if hour >= Daylight.SUNSET - 2.5 and hour < Daylight.SUNSET + 0.75: return "res://assets/title_golden.jpg"
	if hour >= Daylight.SUNSET + 0.75 or hour < Daylight.SUNRISE - 0.5: return "res://assets/title_evening.jpg"
	return "res://assets/title_morning.jpg"

## Title screen: the village art under a vignette with floating
## light motes, the game's wordmark and a keyboard-navigable menu (start, settings,
## quit). Starting opens the server login card; every session plays on a server account.
func login_ui(page := "menu") -> void:
	screen = "login"
	title_page = page
	clear_ui()
	# The world this game would log in to: is this game still allowed there, is a newer one out?
	# (At launch, _ready asks and waits before the menu appears.)
	if page not in ["settings","checking"]: gate.check(default_world())
	if is_instance_valid(player): player.controls_enabled = false
	var art := TextureRect.new()
	var hour: float = daylight.current_hour() if is_instance_valid(daylight) else Daylight.clock_hour()
	art.texture = load(title_art_for(hour))
	# 2560 px art shown smaller: mipmaps keep it smooth at any window size.
	art.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(art)
	# The art stays still: a slow zoom resampled the picture every frame and it shimmered.
	# The light motes keep the title alive.
	for spec in [[Vector2(0,0),Vector2(0,1),Color("bfe6ee"),0.0,0.30],[Vector2(0,0),Vector2(1,0),Color(0.03,0.05,0.06,.82),0.0,0.58],[Vector2(0,1),Vector2(0,0),Color(0.03,0.05,0.06,.55),0.0,0.32]]:
		var gradient := Gradient.new()
		gradient.colors = PackedColorArray([spec[2],Color(spec[2],0)])
		gradient.offsets = PackedFloat32Array([spec[3],spec[4]])
		var fill := GradientTexture2D.new()
		fill.gradient = gradient;fill.fill_from = spec[0];fill.fill_to = spec[1]
		var veil := TextureRect.new()
		veil.texture = fill
		veil.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		veil.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ui.add_child(veil)
	var vignette := TextureRect.new()
	var ring := GradientTexture2D.new()
	ring.fill = GradientTexture2D.FILL_RADIAL
	ring.fill_from = Vector2(0.5,0.5);ring.fill_to = Vector2(1.08,1.08)
	ring.gradient = Gradient.new()
	ring.gradient.colors = PackedColorArray([Color(0,0,0,0),Color(0.02,0.03,0.04,.55)])
	ring.gradient.offsets = PackedFloat32Array([0.55,1.0])
	vignette.texture = ring
	vignette.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	vignette.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(vignette)
	ui.add_child(title_motes())
	var heading := VBoxContainer.new()
	heading.position = Vector2(56,34)
	heading.add_theme_constant_override("separation",0)
	ui.add_child(heading)
	# Villagen = village + generate: the painted logo (a sprout and the star seed on the name),
	# no tagline under it (the user found extra lines cheap).
	heading.add_child(Brand.logo(420))
	var body := VBoxContainer.new()
	body.position = Vector2(92,300 if page=="menu" else 250)
	body.add_theme_constant_override("separation",12)
	ui.add_child(body)
	match page:
		"checking":
			# The version check at launch (a few seconds at most; offline goes on to the menu).
			var row := HBoxContainer.new()
			row.add_theme_constant_override("separation",12)
			body.add_child(row)
			var seed_spin := RpgUi.icon("res://assets/starseed.svg",30)
			seed_spin.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			row.add_child(seed_spin)
			if not RpgUi.calm():
				seed_spin.pivot_offset = Vector2(15,15)
				seed_spin.create_tween().set_loops().tween_property(seed_spin,"rotation",TAU,2.4).from(0.0)
			RpgUi.label(row,tr("최신 버전인지 확인하고 있어요…"),19,Color("f1e8d2")).size_flags_vertical = Control.SIZE_SHRINK_CENTER
		"menu":
			# The UI kit 2 menu plates: gold for the way in, night glass for the others.
			var entries := [RpgUi.menu_button(body,tr("게임 시작"),func(): login_ui("login"),300.0,"MenuGoldButton"),
				RpgUi.menu_button(body,tr("설정"),func(): login_ui("settings"),300.0,"MenuNightButton"),
				RpgUi.menu_button(body,tr("게임 종료"),func(): preload("res://scripts/clean_exit.gd").request_quit(get_tree()),300.0,"MenuNightButton")]
			# Arrow keys / pad move between the entries; Enter starts.
			for entry in entries:
				entry.focus_mode = Control.FOCUS_ALL
				entry.focus_entered.connect(func(): RpgUi.sfx("hover"))
				if entry.theme_type_variation=="MenuNightButton": entry.add_theme_color_override("font_focus_color",RpgUi.HOVER)
			entries[0].grab_focus.call_deferred()
		"settings":
			# Tabbed settings (scripts/settings_menu.gd) over the title art.
			SettingsMenu.open(ui,func(): login_ui("menu"))
		"login":
			var card := PanelContainer.new()
			card.add_theme_stylebox_override("panel",RpgUi.panel_style("night"))
			card.theme = night_theme()
			body.add_child(card)
			var column := VBoxContainer.new()
			column.add_theme_constant_override("separation",7)
			card.add_child(column)
			RpgUi.label(column,tr("모험가 로그인"),24,RpgUi.GOLD)
			RpgUi.divider(column,Color(RpgUi.GOLD,.8))
			var username := RpgUi.field(column,tr("아이디 · 영문·숫자·밑줄 3~24자"),false,func(): message(tr("한/영 키가 한글이었어요 · 누른 자판대로 영문으로 넣었어요.")),true)
			username.text = str(I18n.setting("username",""))
			var password := RpgUi.field(column,tr("비밀번호 · 10자 이상, 대문자와 특수문자 포함"),true,func(): message(tr("비밀번호는 영문으로 입력해요 · 한/영 키로 바꿔 주세요.")))
			RpgUi.label(column,tr("월드"),14,RpgUi.GOLD)
			var servers := OptionButton.new()
			servers.custom_minimum_size = Vector2(340,42)
			servers.focus_mode = Control.FOCUS_NONE
			servers.theme_type_variation = "NightButton"
			servers.add_theme_icon_override("arrow",RpgUi.half("arrow_down_light"))
			servers.alignment = HORIZONTAL_ALIGNMENT_LEFT
			column.add_child(servers)
			var custom := RpgUi.field(column,tr("월드 주소 · 예: http://100.101.1.2:8765"),false,Callable(),true)
			# Player builds (the judging ZIP) start on the online world; source runs on this PC.
			var list := worlds()
			var saved := default_world()
			var chosen := list.size()
			for i in list.size():
				servers.add_item(tr(list[i][2])+"  ·  "+list[i][1].trim_prefix("https://").trim_prefix("http://"))
				if list[i][1]==saved: chosen=i
			servers.add_item(tr("직접 입력"))
			if chosen==list.size(): custom.text=saved
			servers.select(chosen)
			custom.visible = chosen==list.size()
			var host := func() -> String: return custom.text if servers.selected==list.size() else list[servers.selected][1]
			servers.item_selected.connect(func(index):
				custom.visible = index==list.size()
				if index<list.size(): gate.check(host.call()))
			var actions := HBoxContainer.new()
			actions.add_theme_constant_override("separation",8)
			column.add_child(actions)
			var enter := RpgUi.menu_button(actions,tr("로그인"),func(): authenticate(false,host.call(),username.text,password.text,""),166)
			enter.theme_type_variation = "GoldButton"
			enter.add_theme_color_override("font_hover_color",RpgUi.PAPER_INK)
			RpgUi.menu_button(actions,tr("계정 만들기"),func(): authenticate(true,host.call(),username.text,password.text,""),166)
			notice = RpgUi.label(column,"",14,Color("ffd9a0"))
			notice.custom_minimum_size.x = 320
			notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			password.text_submitted.connect(func(_value): authenticate(false,host.call(),username.text,password.text,""))
			RpgUi.menu_button(body,tr("뒤로"),func(): login_ui("menu"))
			if username.text.is_empty(): username.grab_focus.call_deferred()
			else: password.grab_focus.call_deferred()
	var footer := RpgUi.label(ui,"v"+str(ProjectSettings.get_setting("application/config/version","0.9")),13,Color(1,1,1,.7))
	footer.position = Vector2(1060,762)
	footer.size = Vector2(196,20)
	footer.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	RpgUi.slide_in(body,Vector2(-18,0),0.32)

## Warm light motes drifting up over the title art.
func title_motes() -> CPUParticles2D:
	var motes := CPUParticles2D.new()
	var dot := GradientTexture2D.new()
	dot.width = 32;dot.height = 32
	dot.fill = GradientTexture2D.FILL_RADIAL
	dot.fill_from = Vector2(0.5,0.5);dot.fill_to = Vector2(1.0,0.5)
	dot.gradient = Gradient.new()
	dot.gradient.colors = PackedColorArray([Color(1,0.94,0.75,0.9),Color(1,0.85,0.5,0)])
	motes.texture = dot
	motes.amount = 38
	motes.lifetime = 9.0
	motes.preprocess = 9.0
	motes.position = Vector2(640,830)
	motes.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	motes.emission_rect_extents = Vector2(700,40)
	motes.direction = Vector2(0.15,-1)
	motes.spread = 18
	motes.gravity = Vector2.ZERO
	motes.initial_velocity_min = 22
	motes.initial_velocity_max = 48
	motes.scale_amount_min = 0.18
	motes.scale_amount_max = 0.55
	var fade := Gradient.new()
	fade.colors = PackedColorArray([Color(1,1,1,0),Color(1,1,1,.85),Color(1,1,1,0)])
	fade.offsets = PackedFloat32Array([0,0.3,1])
	motes.color_ramp = fade
	return motes

func authenticate(register: bool, host: String, username: String, password: String, invitation: String) -> void:
	if busy: return
	host = host.strip_edges().trim_suffix("/")
	var local_pattern := RegEx.new()
	# Plain HTTP only for this PC, a home network or a Tailscale network (100.64/10,
	# *.ts.net; Tailscale encrypts the link). Anything else on the internet needs HTTPS.
	local_pattern.compile("^http://(127\\.0\\.0\\.1|localhost|10(\\.[0-9]{1,3}){3}|192\\.168(\\.[0-9]{1,3}){2}|172\\.(1[6-9]|2[0-9]|3[01])(\\.[0-9]{1,3}){2}|100\\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])(\\.[0-9]{1,3}){2}|[a-z0-9-]+(\\.[a-z0-9-]+)*\\.ts\\.net):[0-9]{1,5}$")
	if not (host.begins_with("https://") or local_pattern.search(host)!=null):
		refuse(tr("멀리 있는 월드는 https:// 주소로 들어가요."))
		return
	if username.strip_edges().is_empty() or password.is_empty():
		refuse(tr("아이디와 비밀번호를 입력하세요."))
		return
	busy = true
	# Signing in again (another account or world) ends the earlier session's craft follower.
	CraftTracker.end(api)
	api.base_url = host
	api.token = ""
	message(tr("마을로 가는 중…"))
	var health: Dictionary=await api.request("/health")
	if not check(health):
		busy=false
		return
	# Too old for this world, or the world is under maintenance: the gate's window explains.
	gate.adopt(host)
	if health.data.get("service","")=="tripothon" and not gate.apply(health.data).is_empty():
		busy=false
		if is_instance_valid(notice): notice.text = ""
		return
	if health.data.get("service","")!="tripothon" or int(health.data.get("protocol",0))!=6:
		busy=false
		refuse(error_message("server_update_required"))
		return
	var result: Dictionary = await api.post("/v1/auth/"+("register" if register else "login"),{"username":username,"password":password,"invitation":invitation})
	busy = false
	if not check(result): return
	social.reset_session()
	social.enabled = social.feature_enabled() and int(health.data.get("multiplayer_protocol", 0)) == 1
	api.token = result.data.token
	api.mode = result.data.mode
	# The sign-in answer carries the look: the first walker (home or village) already wears it, and
	# the previous account's look never shows.
	me = {"profile":result.data.get("profile",{})}
	# Settings follow the account: read them now (a fresh install picks up the player's own).
	var cloud := get_node_or_null("/root/CloudPrefs")
	if cloud: cloud.start(api.base_url, api.token)
	preload("res://scripts/build_mode.gd").admin = str(result.data.get("role","player"))=="admin"
	# Only the real game remembers the login; test harnesses add Main to the root directly.
	if get_tree().current_scene==self:
		I18n.remember("server",host)
		I18n.remember("username",username.strip_edges())
	var veil := Transition.of(get_tree())
	# Where the session picks up (server/last_spot.py): a first sign-in, a long time away or a game
	# ended at home wakes up in the attic bed; otherwise back on the spot in the own village.
	var resume = result.data.get("resume")
	var wake: bool = not resume is Dictionary or bool(resume.get("wake",false))
	var spot = resume.get("spot") if resume is Dictionary and not wake else null
	var in_village: bool = spot is Dictionary and str(spot.get("scene",""))=="village"
	var at_home: bool = get_tree().current_scene==self and not in_village
	veil.loading(TownLayout.room_title("home") if at_home else tr("다섯 섬 마을"),"","room" if at_home else "village")
	await veil.fade_out()
	if at_home:
		# A new session starts at home; walking out of the front door opens the village.
		# Waking: the walker gets up from the attic bed (studio.gd, bed_wake.gd); else in at the door.
		Engine.set_meta("studio_session",{"token":api.token,"url":api.base_url,"room":"home","multiplayer":social.enabled,"profile":me.profile,
			"username":username.strip_edges().to_lower(),"wake":wake})
		# The title's village map waits outside the tree for the walk out of the home (as open_studio).
		leave_modules()
		if is_instance_valid(town): town.release_map()
		get_tree().change_scene_to_packed(studio_scene())
		return
	await enter_village()
	if in_village: preload("res://scripts/bed_wake.gd").resume_spot(self,spot)
	veil.fade_in()

## Under the loading card (LoadPace.covered) the build is paced over frames so the card keeps
## turning: await it. Uncovered it runs in one go as before. False when a newer build (a logout
## during the load) replaced this one before it finished.
func build_world(survival: bool) -> bool:
	var paced := LoadPace.covered
	if paced: hold(true)
	social.reset_world()
	world_epoch += 1
	var epoch := world_epoch
	camera_focus_ready=false
	camera_zoom_active=false
	paused=false
	results_shown=false
	prior_day=1
	prior_night=false
	last_run_line=""
	sound.play_music(region_track() if survival else village_track())
	leave_modules()
	if is_instance_valid(town): town.release_map()
	# The village seat (and its interaction driver) belongs to the walker that goes with this world:
	# let go of it first, and the next village_seat() makes a fresh one for the new walker.
	if is_instance_valid(seat):
		seat.reset()
		seat.queue_free()
	seat=null
	if is_instance_valid(world):
		remove_child(world)
		world.queue_free()
	# The old walker goes with its world; nothing should reach it while a paced build runs.
	player = null
	preview = null
	loaded.clear()
	nodes.clear()
	enemy_nodes.clear()
	strike_markers.clear()
	pending_action=""
	pending_target=""
	tick_elapsed=0
	predicted=Vector2.INF
	predict_log.clear()
	last_camp_warning=-100
	world = Node3D.new()
	add_child(world)
	npcs.clear()
	close_village_modal()
	town=null
	var span := LoadPace.narrow(0.0, 0.85)
	if survival: await preload("res://scripts/biomes.gd").build(world,run)
	else:
		town=preload("res://scripts/town.gd").new()
		town.camera=camera
		for chapter in me.get("campaign",[]):
			if chapter.completed:town.story_progress+=1
		world.add_child(town)
		if not town.finished: await town.built
	LoadPace.span = span
	if epoch!=world_epoch: return false
	object_root = Node3D.new()
	world.add_child(object_root)
	# Built in the saved look from the first frame (applying it after _ready showed the default
	# explorer first and loaded the character twice).
	var profile: Dictionary = me.get("profile",{})
	for path in AvatarLook.resource_paths(): if LoadPace.pending(path): await LoadPace.fetch(path)
	await LoadPace.step("walker")
	player = AvatarLook.walker(profile.get("avatar",{}),int(profile.get("version",-1)))
	player.visual_only=survival
	world.add_child(player)
	LoadPace.done(0.88)
	if not survival: await spawn_villagers()
	if epoch!=world_epoch: return false
	if not survival: await spawn_modules()
	if epoch!=world_epoch: return false
	player.position = TownLayout.point(TownLayout.SPAWN,.3) if not survival else Vector3(run.get("x",0),0.1,run.get("z",1.4))
	player.min_ground_y = TownLayout.SHORE_MIN_Y if not survival else -INF
	flame = Node3D.new()
	world.add_child(flame)
	for index in 3:
		var tongue := MeshInstance3D.new();var quad := QuadMesh.new();quad.size=Vector2(.72,.72)
		tongue.mesh=quad;tongue.position.y=.47;tongue.rotation.y=index*PI/3
		tongue.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var fire_material := ShaderMaterial.new();fire_material.shader=preload("res://shaders/camp_flame.gdshader")
		fire_material.set_shader_parameter("phase",float(index)*1.8);tongue.material_override=fire_material;flame.add_child(tongue)
	flame.visible = false
	harvest_marker = MeshInstance3D.new()
	var ring := TorusMesh.new()
	ring.inner_radius=0.7
	ring.outer_radius=0.77
	ring.rings=24
	ring.ring_segments=8
	harvest_marker.mesh=ring
	var marker_material := Art.material(Color("f2d38c"))
	marker_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	harvest_marker.material_override=marker_material
	harvest_marker.visible=false
	world.add_child(harvest_marker)
	warmth_ring=MeshInstance3D.new()
	var warm_mesh := TorusMesh.new()
	warm_mesh.inner_radius=3.94
	warm_mesh.outer_radius=4.0
	warm_mesh.rings=64
	warm_mesh.ring_segments=6
	warmth_ring.mesh=warm_mesh
	warmth_ring.position.y=0.035
	var warm_mat := Art.material(Color(0.92,0.73,0.38,0.4))
	warm_mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	warm_mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	warmth_ring.material_override=warm_mat
	warmth_ring.visible=false
	world.add_child(warmth_ring)
	var light := OmniLight3D.new()
	light.position.y = 1
	light.light_color = Color("ffb16b")
	light.light_energy = 1.5
	light.omni_range = 7
	flame.add_child(light)
	var sparks := CPUParticles3D.new()
	sparks.amount=22
	sparks.lifetime=1.1
	sparks.position.y=0.3
	sparks.direction=Vector3.UP
	sparks.spread=25
	sparks.initial_velocity_min=0.6
	sparks.initial_velocity_max=1.3
	sparks.gravity=Vector3(0,0.35,0)
	sparks.scale_amount_min=0.035
	sparks.scale_amount_max=0.075
	var spark_mesh := SphereMesh.new()
	spark_mesh.radius=0.5
	spark_mesh.height=1
	sparks.mesh=spark_mesh
	var spark_mat := Art.material(Color("ffd68c"))
	spark_mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	sparks.material_override=spark_mat
	flame.add_child(sparks)
	ambience=CPUParticles3D.new()
	ambience.amount=45
	ambience.lifetime=8
	ambience.emission_shape=CPUParticles3D.EMISSION_SHAPE_BOX
	ambience.emission_box_extents=Vector3(12,1.7,12)
	ambience.position.y=1.6
	ambience.direction=Vector3(1,0.2,0.3)
	ambience.initial_velocity_min=0.12
	ambience.initial_velocity_max=0.3
	ambience.gravity=Vector3.ZERO
	ambience.scale_amount_min=0.018
	ambience.scale_amount_max=0.035
	ambience.mesh=spark_mesh
	ambience.material_override=spark_mat
	world.add_child(ambience)
	environment.ambient_light_energy = 0.35
	environment.ambient_light_color=Color.WHITE
	environment.background_color = Color("88bcb9")
	sun.light_energy = 0.25
	sun.light_color=Color("fff5e9")
	environment.tonemap_mode=Environment.TONE_MAPPER_LINEAR
	environment.tonemap_exposure=1.0
	environment.fog_enabled=false
	sun.rotation_degrees=sun_defaults.rotation
	sun.shadow_bias=sun_defaults.bias
	sun.shadow_normal_bias=sun_defaults.normal_bias
	sun.directional_shadow_max_distance=sun_defaults.distance
	camera.size = ControllerProfile.CAMERA_DEFAULT
	if not survival:
		TownLayout.Archipelago.apply_lighting(environment,sun)
		daylight.attach(environment,sun,town.map if is_instance_valid(town) else null)
		camera.size = ControllerProfile.VILLAGE_CAMERA_DEFAULT
	else:
		daylight.detach()
	fit_shadow_to_camera()
	camera_zoom_active=false
	follow_camera(1)
	LoadPace.done(1.0)
	LoadPace.release()
	hold(false)
	return true

## While a paced build runs, main's own per-frame work and input wait (the walker, the camera and
## the HUD are being replaced); its children (network, sound) go on.
func hold(on: bool) -> void:
	set_process(not on)
	set_process_unhandled_input(not on)

## Shadow splits keep their old distances from the walker after the camera moved
## back (CAMERA_PULLBACK), so shadows stay as sharp as before.
var shadow_fitted := false
func fit_shadow_to_camera() -> void:
	shadow_fitted=true
	var back := ControllerProfile.CAMERA_OFFSET.length()*(ControllerProfile.CAMERA_PULLBACK-1.0)
	var base := sun.directional_shadow_max_distance
	sun.directional_shadow_max_distance=base+back
	sun.directional_shadow_split_1=(back+base*0.1)/(base+back)
	sun.directional_shadow_split_2=(back+base*0.2)/(base+back)
	sun.directional_shadow_split_3=(back+base*0.5)/(base+back)
	if GameSettings.shadow_quality()!="high":
		# Two splits: the near one stops just short of what the camera frames.
		sun.directional_shadow_mode=DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
		sun.directional_shadow_split_1=(back+base*0.25)/(base+back)
	else:
		sun.directional_shadow_mode=DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.shadow_enabled=GameSettings.shadow_quality()!="off"

## MSAA, 3D scale, LOD, frame cap and window mode are GameSettings' job; the
## village sun is fitted here because its splits follow the camera pull-back.
func apply_graphics() -> void:
	if is_instance_valid(sun) and shadow_fitted:
		# Undo the camera pull-back added last time, then fit again for the new setting.
		sun.directional_shadow_max_distance-=ControllerProfile.CAMERA_OFFSET.length()*(ControllerProfile.CAMERA_PULLBACK-1.0)
		fit_shadow_to_camera()

func enter_village() -> void:
	coop_run = false
	screen = "loading"
	if not await build_world(false): return
	clear_ui()
	frame = RpgUi.player_frame(ui,"res://assets/ui/portrait_explorer.png","profile")
	left = frame.column
	wallet = frame.status
	reward_button=button(left,tr("받지 않은 생존 보상 받기"),claim_pending_reward,"primary")
	reward_button.visible=false
	right = panel(Vector2(948,20),308,"hero")
	RpgUi.pin(right.get_parent(),1.0,0.0)
	var drawer_title := HBoxContainer.new()
	right.add_child(drawer_title)
	drawer_title.add_child(RpgUi.icon("res://assets/ui/bag.svg",30))
	text(drawer_title,tr("가방"),24).size_flags_horizontal=Control.SIZE_EXPAND_FILL
	close_button(drawer_title,toggle_drawer,"I")
	rule(right)
	objects_list = ItemList.new()
	objects_list.custom_minimum_size = Vector2(252,150)
	objects_list.item_selected.connect(select_object)
	objects_list.item_selected.connect(func(_index: int): RpgUi.sfx("select",-9.0))
	right.add_child(objects_list)
	object_info = text(right,tr("물건을 선택하세요."),13)
	object_info.custom_minimum_size.x = 250
	object_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var palette := HBoxContainer.new()
	palette.add_theme_constant_override("separation",8)
	palette.alignment = BoxContainer.ALIGNMENT_CENTER
	right.add_child(palette)
	for color in COLORS: RpgUi.name_tip(swatch(palette,Color(color),func(): paint_object(color)),RpgUi.color_name(color))
	paint_palette = palette
	# Objects with UVs are painted in the workspace; the swatches stay for the others.
	paint_button = button(right,tr("색칠하기"),open_painter,"primary")
	paint_button.tooltip_text = tr("붓·채우기·그라데이션으로 표면을 직접 칠해요")
	paint_hint = text(right,"",12)
	paint_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	paint_hint.custom_minimum_size.x = 250
	paint_hint.visible = false
	shape_button = button(right,tr("모양 바꾸기"),open_shape_panel)
	shape_button.tooltip_text = tr("가로 · 깊이 · 높이 · 크기 · 좌우 반전")
	button(right,tr("선택한 물건 놓기"),begin_place)
	button(right,tr("선택한 물건 회수"),retrieve_object)
	button(right,tr("선택한 가구 사용"),func():await village_furniture_event(selected.get("id",""),"click"))
	RpgUi.name_tip(button(right,tr("상호작용"),open_interactions),tr("누르거나 다가가면 움직이고 빛나게"))
	if TRADING_UI_ENABLED:
		var sell_row := HBoxContainer.new()
		right.add_child(sell_row)
		price = SpinBox.new()
		price.min_value = 1
		price.max_value = 10000
		price.value = 25
		price.custom_minimum_size.x = 115
		sell_row.add_child(price)
		button(sell_row,tr("별씨로 판매"),sell_object)
	RpgUi.name_tip(button(right,tr("새 물건 제작 의뢰"),open_craft,"gold"),tr("새 물건 제작 의뢰"),RpgUi.key_text("craft"))
	prompt = LineEdit.new()
	prompt.max_length = 500
	right.add_child(prompt)
	prompt.visible=false # Retained for legacy integration/recovery, outside the player flow.
	var utilities := HBoxContainer.new()
	right.add_child(utilities)
	button(utilities,tr("가방 정리"),refresh_inventory)
	button(utilities,tr("로그아웃"),logout)
	right.get_parent().visible=false
	await LoadPace.step("village hud")
	build_play_hud(false)
	await LoadPace.step("inspector")
	build_inspector()
	await refresh_inventory()
	screen = "village"
	if social.visiting(): social.accept_crops()
	else: await life.enter()
	player.controls_enabled = true
	hint=RpgUi.prompt(ui,560)
	# While the opening story chapter runs, its next step is the first word (story.gd).
	var story := chapter()
	var hello: String = story.welcome() if story else ""
	message(hello if not hello.is_empty() else tr("물결빛 마을에 오신 것을 환영해요! 다리를 건너 다섯 섬을 둘러보세요."))
	await warm_up_shaders()

## The first time the village opens in a session, draw the whole archipelago once
## from far above while the screen is still dark. Materials compile now instead of
## hitching the first time each one walks into view.
static var shaders_warm := false
var warming := false
func warm_up_shaders() -> void:
	if shaders_warm or not is_instance_valid(town) or not is_instance_valid(town.map): return
	# Nothing is drawn without a window (headless tests), so there is nothing to warm.
	if DisplayServer.get_name()=="headless": return
	shaders_warm=true
	warming=true
	var keep_size := camera.size
	var keep_far := camera.far
	camera.size=200.0
	camera.far=2000.0
	var centre := Vector3(2.5,0,10)
	camera.global_position=centre+ControllerProfile.CAMERA_OFFSET.normalized()*400.0
	camera.look_at(centre)
	# Each idle frame ends in a draw, so three frames have drawn the wide view.
	for i in 3: await get_tree().process_frame
	camera.size=keep_size
	camera.far=keep_far
	warming=false
	follow_camera(1)

func toggle_drawer() -> void:
	if screen == "village" and social.visiting():
		refuse(tr("방문 중에는 함께하기 메뉴에서 대화하거나 내 마을로 돌아갈 수 있습니다."))
		return
	if not is_instance_valid(right): return
	var opening: bool=not right.get_parent().visible
	if not opening and is_instance_valid(shape_panel): shape_panel.close()
	right.get_parent().visible=opening
	# The side drawer's own slide (as RpgUi.drawer), not the centred windows' open / close.
	if opening:
		RpgUi.slide_in(right.get_parent(),Vector2(28,0),0.26)
		RpgUi.sfx("drawer_open",-10.0)
	else: RpgUi.sfx("drawer_close",-10.0)
	if screen=="village":player.controls_enabled=world_movement_allowed()
	if is_instance_valid(objective_card): objective_card.visible=not opening
	if is_instance_valid(minimap): minimap.visible=not opening
	if is_instance_valid(field_panel): field_panel.visible=not opening
	if is_instance_valid(inspect_panel): inspect_panel.visible=opening
	if is_instance_valid(inspect_view): inspect_view.render_target_update_mode=SubViewport.UPDATE_ALWAYS if opening else SubViewport.UPDATE_DISABLED

func build_inspector() -> void:
	var card := panel(Vector2(20,206),254)
	inspect_panel=card.get_parent()
	inspect_panel.visible=false
	text(card,tr("물건 미리 보기"),20)
	rule(card)
	inspect_view=SubViewport.new()
	inspect_view.size=Vector2i(320,280)
	inspect_view.transparent_bg=true
	inspect_view.own_world_3d=true
	inspect_view.render_target_update_mode=SubViewport.UPDATE_DISABLED
	inspect_panel.add_child(inspect_view)
	inspect_stage=Node3D.new()
	inspect_view.add_child(inspect_stage)
	var preview_camera := Camera3D.new()
	preview_camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	preview_camera.size=2.7
	inspect_stage.add_child(preview_camera)
	preview_camera.position=Vector3(2,1.75,3)
	preview_camera.look_at(Vector3(0,0.65,0))
	var preview_light := DirectionalLight3D.new()
	preview_light.rotation_degrees=Vector3(-45,-30,0)
	preview_light.light_energy=0.4
	inspect_stage.add_child(preview_light)
	var env := WorldEnvironment.new()
	env.environment=Environment.new()
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color=Color.WHITE
	env.environment.ambient_light_energy=0.5
	inspect_stage.add_child(env)
	var view := TextureRect.new()
	view.texture=inspect_view.get_texture()
	view.custom_minimum_size=Vector2(210,185)
	view.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
	view.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	view.mouse_filter=Control.MOUSE_FILTER_IGNORE
	card.add_child(view)
	RpgUi.caption(card,tr("팔레트로 전체 색을 바꿔 보세요.\nR · 휠 · 놓을 방향 돌리기"),12)

func inspect_object(obj: Dictionary) -> void:
	if not is_instance_valid(inspect_stage): return
	inspect_request+=1
	var request := inspect_request
	# The same object, unchanged: keep the model already in the preview.
	if is_instance_valid(inspect_model) and str(inspect_model.get_meta("inspect_id",""))==str(obj.id) and str(inspect_model.get_meta("object_key",""))==object_key(obj):
		sync_shape(inspect_model,obj)
		if await sync_runtime(inspect_model,obj) or request!=inspect_request: return
	if is_instance_valid(inspect_model):
		inspect_model.queue_free()
		inspect_model=null
	var model := await load_object(obj)
	if request!=inspect_request or not is_instance_valid(inspect_stage) or selected.get("id","")!=obj.id:
		if model: model.queue_free()
		return
	if model:
		inspect_model=model
		model.set_meta("inspect_id",obj.id)
		model.set_meta("object_key",object_key(obj))
		if not model.get_meta("studio",false):Loader.paint(model,Color(selected.color))
		inspect_stage.add_child(model)
		# The whole object in view, however wide or tall (preview_frame.gd).
		preload("res://scripts/preview_frame.gd").fit(preload("res://scripts/preview_frame.gd").camera_in(inspect_stage),model.get_meta("size",Vector3.ZERO))
		update_paint_entry(model)
		# A reload while the shape window is open keeps showing its unsaved draft.
		if is_instance_valid(shape_panel): shape_panel.refresh()

## Village HUD: character frame (enter_village), round minimap, objective tracker,
## slot hotbar and a top toast. The survival HUD keeps its own layout below.
func build_village_hud() -> void:
	minimap = Minimap.new()
	minimap.position = Vector2(1060,10)
	ui.add_child(minimap)
	var tracker := PanelContainer.new()
	tracker.position = Vector2(994,246)
	tracker.custom_minimum_size.x = 272
	var plate := RpgUi.panel_style("night")
	plate.content_margin_top = 14
	plate.content_margin_bottom = 16
	tracker.add_theme_stylebox_override("panel",plate)
	tracker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(tracker)
	RpgUi.pin(tracker,1.0,0.0)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation",4)
	tracker.add_child(column)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation",6)
	column.add_child(head)
	head.add_child(RpgUi.name_tip(RpgUi.icon("res://assets/ui/book.svg",22),tr("목표")))
	RpgUi.label(head,tr("목표"),15,RpgUi.GOLD)
	# Folding rolls the divider and the goals up into the header row.
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation",4)
	column.add_child(body)
	RpgUi.divider(body,Color(RpgUi.GOLD,.55))
	objective = RpgUi.label(body,"",14,RpgUi.INK,false)
	objective.add_theme_constant_override("line_spacing",4)
	objective.custom_minimum_size.x = 240
	objective.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	objective_card = tracker
	RpgUi.fold_card(tracker,head,body,"objective")
	# A folded minimap is just its chip: the tracker rises to sit under it.
	RpgUi.fold_shift(tracker,"minimap",Vector2(0,-Minimap.FOLD_LIFT),"move")
	var slots := []
	# Action ids: the key caps and "name  ·  key" tooltips follow rebinding (RpgUi.key_text).
	for spec in [["bag.svg","inventory",tr("가방"),toggle_drawer],["craft.svg","craft",tr("제작"),open_craft],["map.svg","map",tr("지도"),life.open_map],
			["chest.svg","storage",tr("창고"),life.open_storage],["wardrobe.svg","wardrobe",tr("옷장"),open_wardrobe],["expedition.svg","",tr("탐험"),open_expedition]]+(
			[["admin.svg","F9",tr("관리"),open_admin]] if preload("res://scripts/build_mode.gd").admin else []):
		var action: Callable = spec[3]
		# The bag slot's press is heard as the drawer's own slide (toggle_drawer), as in rooms.
		slots.append({"icon":"res://assets/ui/"+spec[0],"action":spec[1],"label":tr(spec[2]),"primary":spec[0]=="expedition.svg",
			"press":"" if spec[1]=="inventory" else "click","call":func(): action.call()})
	var bar := RpgUi.hotbar(ui,slots,700,"hotbar")
	expedition_button = bar.get_child(5)
	lay_toasts(94)
	if preload("res://scripts/build_mode.gd").developer():
		var debug_box := panel(Vector2(20,520),252,"night")
		developer_panel=debug_box.get_parent()
		developer_panel.visible=false
		developer_label=text(debug_box,"F3",12)
		developer_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
		# ISS-1 socket gizmo (ix/ix_debug.gd): off by default, nothing exists while it is off.
		var sockets := CheckBox.new()
		sockets.text=tr("소켓 보기 (ISS-1)")
		sockets.focus_mode=Control.FOCUS_NONE
		sockets.add_theme_font_size_override("font_size",12)
		sockets.toggled.connect(func(on: bool): show_ix_debug(on))
		debug_box.add_child(sockets)
	if "--ix-debug" in OS.get_cmdline_user_args(): show_ix_debug(true)

## The socket gizmo over the village (crafted pieces and map props near the walker).
func show_ix_debug(on: bool) -> void:
	var current: Node = world.get_node_or_null("IxDebug") if is_instance_valid(world) else null
	if not on:
		if is_instance_valid(current): current.queue_free()
		return
	if is_instance_valid(current) or not is_instance_valid(world): return
	var gizmo: Node3D = preload("res://scripts/ix/ix_debug.gd").new()
	gizmo.player=player
	gizmo.nodes=func() -> Array:
		var out: Array=loaded.values()
		if is_instance_valid(town):
			for entry in town.props: out.append(entry.node)
		return out
	world.add_child(gizmo)

func build_play_hud(survival: bool) -> void:
	social.install_hud(survival)
	if not survival:
		build_village_hud()
		return
	# Right column, as in the village: the map card on top (field_panel), the goal card under it.
	var task_top: float=20.0+(field_panel.get_combined_minimum_size().y+8.0 if is_instance_valid(field_panel) else 0.0)
	var task_card := panel(Vector2(1000,task_top),256,"objective")
	RpgUi.pin(task_card.get_parent(),1.0,0.0)
	var task_head := HBoxContainer.new()
	task_head.add_theme_constant_override("separation",6)
	task_card.add_child(task_head)
	task_head.add_child(RpgUi.name_tip(RpgUi.icon("res://assets/ui/book.svg",22),tr("목표")))
	RpgUi.label(task_head,tr("목표"),15,RpgUi.GOLD)
	var task_body := VBoxContainer.new()
	task_body.add_theme_constant_override("separation",8)
	task_card.add_child(task_body)
	RpgUi.divider(task_body,Color(RpgUi.GOLD,.55))
	objective=text(task_body,"",14)
	objective.custom_minimum_size.x=212
	objective.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	objective_card=task_card.get_parent()
	RpgUi.fold_card(objective_card,task_head,task_body,"survival_objective")
	# The goal card stays just under the map card when that grows (the ground's line on ice or embers).
	if is_instance_valid(field_panel): field_panel.resized.connect(follow_field_panel)
	# Bottom centre: the field's icon hotbar, keys and "name · key" tooltips from the bindings.
	var slots := []
	for spec in [["bag","inventory",tr("가방"),toggle_drawer],["hunger","eat",tr("먹기"),func(): intent("eat")],
			["fire","campfire",tr("모닥불"),func(): intent("fire")],["heart","heal",tr("붕대"),func(): intent("heal")],
			["home","",tr("귀환"),confirm_return]]:
		var action: Callable=spec[3]
		# A press picks: a soft select for eat, fire and bandage (their outcome sounds when the field
		# acts); the bag's drawer slide and the return question's window are the bag and home slots' sound.
		var press: String="" if spec[0] in ["bag","home"] else "select"
		slots.append({"icon":"res://assets/ui/icons/%s.png" % spec[0],"action":spec[1],"label":spec[2],"press":press,"press_db":-8.0,
			"call":func(): action.call()})
	# Folds to a handle tab like the village hotbar (fold id "toolbar"); the keys keep working.
	toolbar_bar=RpgUi.hotbar(ui,slots,700,"toolbar")
	toolbar_bar.name="FieldHotbar"
	lay_toasts(94)
	var tracker := PanelContainer.new()
	tracker.add_theme_stylebox_override("panel",RpgUi.panel_style("pill"))
	tracker.position=Vector2(470,16)
	tracker.custom_minimum_size=Vector2(340,0)
	tracker.mouse_filter=Control.MOUSE_FILTER_IGNORE
	ui.add_child(tracker)
	tracker.size=Vector2(340,48)
	RpgUi.pin(tracker,0.5,0.0)
	day_track=RpgUi.numbers(RpgUi.label(tracker,"",18,RpgUi.INK),18)
	day_track.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	RpgUi.name_tip(day_track,tr("탐험 진행"))
	if preload("res://scripts/build_mode.gd").developer():
		var debug_box := panel(Vector2(20,520),252,"night")
		developer_panel=debug_box.get_parent()
		developer_panel.visible=false
		developer_label=text(debug_box,tr("F3 · 개발 정보"),12)
		developer_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART

## The field's goal card sits 8 px under the map card (both pinned to the top right).
func follow_field_panel() -> void:
	if not is_instance_valid(objective_card) or not is_instance_valid(field_panel): return
	var drop: float=field_panel.position.y+field_panel.size.y+8.0-objective_card.offset_top
	objective_card.offset_top+=drop
	objective_card.offset_bottom+=drop

## Shrinks the prompt chip to its key cap and text after the text changes (RpgUi.fit_prompt).
func fit_chip(chip: Label) -> void:
	RpgUi.fit_prompt(chip)

func meter(parent: Node, color: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.custom_minimum_size.y=12
	bar.show_percentage=false
	bar.add_theme_stylebox_override("background",RpgUi.frame("bar_bg"))
	bar.add_theme_stylebox_override("fill",RpgUi.frame("bar_fill",color))
	parent.add_child(bar)
	return bar

func status_meter(parent: Node, title: String, color: Color, icon_name := "") -> Dictionary:
	return RpgUi.meter(parent,title,color,icon_name)

func refresh_inventory() -> void:
	# The village is where the craft's news is told now (also while visiting a friend).
	craft_tracker()
	if social.visiting():
		if is_instance_valid(wallet):
			wallet.visible = true
			wallet.text = tr("%s님의 마을 방문 중") % str(social.data.get("host_name", tr("친구")))
		if is_instance_valid(reward_button): reward_button.visible = false
		await social.refresh_guest_objects()
		return
	var requested_epoch := world_epoch
	while refreshing:
		await get_tree().process_frame
		if requested_epoch!=world_epoch: return
	refreshing=true
	var epoch := world_epoch
	var old_selection: String = selected.get("id","")
	var result: Dictionary = await api.request("/v1/me")
	if epoch!=world_epoch or not check(result):
		refreshing=false
		return
	var newer: Dictionary = me.get("profile",{})
	me = result.data
	NpcGifts.set_versions(me.get("npc_homes"),me.get("npc_homes_host",""))
	# The opening story chapter (story.gd) follows the server's progress.
	var story := chapter()
	if story: story.adopt(me.get("story"))
	if story: story.adopt_quests(me.get("quests"))
	# A newer look adopted while this answer was on its way stays.
	if int(newer.get("version",-1))>int(me.get("profile",{}).get("version",-1)): me.profile=newer
	# Also while the village is still loading (screen "loading"): the walker built before /v1/me
	# answered wears the saved look now.
	wear_profile()
	reward_button.visible=me.get("pending_reward")!=null
	if is_instance_valid(expedition_button):
		var saved = me.get("active_run_summary")
		expedition_button.tooltip_text=(tr("탐험 이어하기 · %d일") % saved.day) if saved is Dictionary else tr("탐험")
	if me.get("pending_job")!=null and job_id.is_empty(): job_id=me.pending_job
	# The craft under way, also after a relaunch: the village follows it again without opening C.
	var crafting = me.get("pending_craft")
	var tracker := craft_tracker()
	if crafting is Dictionary and tracker and tracker.job_id.is_empty(): tracker.follow(str(crafting.get("id","")))
	if frame.has("name") and is_instance_valid(frame.name):
		frame.name.text = me.username
		show_portrait()
		RpgUi.count_to(frame.stars,int(me.shards))
		wallet.visible = false
	else: wallet.text = "%s  ·  %s %d" % [me.username,tr("별씨"),me.shards]
	objects_list.clear()
	selected = {}
	for obj in me.objects:
		var state_name: String = {"inventory":tr("보관"),"placed":tr("배치"),"listed":tr("판매")}[obj.state]
		objects_list.add_item("[%s] %s" % [state_name,obj.name])
	await sync_placed(me.objects.filter(func(obj): return obj.state=="placed" and obj.get("room","village")=="village"))
	if epoch!=world_epoch:
		refreshing=false
		return
	if objects_list.item_count>0:
		var index := 0
		for i in me.objects.size():
			if me.objects[i].id==old_selection: index=i
		objects_list.select(index)
		# A placement the player started while this refresh was on its way stays: selecting again
		# would cancel its ghost (select_object -> cancel_preview). Its piece stays the selection,
		# fresh from /v1/me: a craft ending meanwhile (craft_tracker -> craft_bag_changed) refreshed
		# the bag mid-placement and left nothing selected, so the ghost could not be put down.
		if not is_instance_valid(preview): select_object(index)
		elif str(me.objects[index].id)==old_selection: selected = me.objects[index]
	if is_instance_valid(shape_panel): shape_panel.refresh()
	refreshing=false

## What a loaded model depends on: a change here reloads it; anything else updates in place.
func object_key(obj: Dictionary) -> String:
	return JSON.stringify([obj.get("color",""),obj.get("paint_version"),obj.get("studio",false)])

## Brings the village's placed models in line with `objects` (the player's own, or the host's
## during a visit, read through `prefix`). Only a new, removed or repainted object loads or frees a
## model: rebuilding every placed model (Tripo textures included) on each change froze the village
## whenever starseeds or a runtime version changed, and kept a visitor's village reloading. The rest
## move, turn, reshape and take their new interaction state in place. False when a model could not
## be loaded or the world changed meanwhile (the caller checks world_epoch).
func sync_placed(objects: Array, prefix: String="/v1/objects/") -> bool:
	var epoch := world_epoch
	var wanted := {}
	for obj in objects: wanted[obj.id]=obj
	for id in loaded.keys():
		var node = loaded[id]
		if not wanted.has(id) or not is_instance_valid(node) or str(node.get_meta("object_key",""))!=object_key(wanted[id]): drop_loaded(id)
	var complete := true
	for obj in objects:
		var existing = loaded.get(obj.id)
		if is_instance_valid(existing):
			existing.position = TownLayout.furniture_point(obj.x,obj.z)
			existing.rotation_degrees.y = obj.rotation
			sync_shape(existing,obj)
			var kept: bool=await sync_runtime(existing,obj,prefix)
			if epoch!=world_epoch: return false
			if kept: continue
		drop_loaded(obj.id)
		var asset = await load_object(obj,prefix)
		if epoch!=world_epoch:
			if is_instance_valid(asset): asset.queue_free()
			return false
		if not asset:
			complete=false
			continue
		asset.set_meta("object_key",object_key(obj))
		object_root.add_child(asset)
		asset.position = TownLayout.furniture_point(obj.x,obj.z)
		asset.rotation_degrees.y = obj.rotation
		Loader.add_collision(asset)
		loaded[obj.id] = asset
	return complete

func drop_loaded(id: String) -> void:
	var node = loaded.get(id)
	if is_instance_valid(node):
		if node.get_parent(): node.get_parent().remove_child(node)
		node.queue_free()
	loaded.erase(id)

## A crafted object whose state moved on elsewhere (a room, another PC, the host while a friend
## visits) takes the server's state without reloading its model. False when its parts changed (a
## new binding): the caller loads the model again.
func sync_runtime(item: Node3D, obj: Dictionary, prefix: String="/v1/objects/") -> bool:
	if not item.get_meta("studio",false) or obj.get("runtime_version")==null: return true
	if int(item.runtime_version)==int(obj.runtime_version): return true
	var fresh: Dictionary=await api.request(prefix+str(obj.id)+"/assembly")
	if not fresh.ok or not is_instance_valid(item): return true
	if fresh.data.get("plan")!=item.manifest.get("plan"): return false
	# A changed interaction (상호작용 saved on another device) runs its new program; otherwise only the state moves.
	if not (item.has_method("sync_interaction") and item.sync_interaction(fresh.data)):
		item.accept_event({"state":fresh.data.runtime.state,"commands":[],"version":fresh.data.runtime.version})
	item.paint(fresh.data.runtime.colors)
	return true

## A shape saved elsewhere (another PC) reshapes a kept model in place; the object the shape
## window is editing keeps showing its unsaved draft.
func sync_shape(item: Node3D, obj: Dictionary) -> void:
	if ObjectTransform.same(item.get_meta("shape",{}),obj.get("shape")): return
	if is_instance_valid(shape_panel) and str(shape_panel.object.get("id",""))==str(obj.id): return
	ObjectTransform.apply(item,obj.get("shape"))

## /v1/me without the runtime versions near/leave/click events keep raising.
static func objects_signature(objects: Array) -> String:
	var copies := []
	for obj in objects:
		var copy: Dictionary=obj.duplicate()
		copy.erase("runtime_version")
		copies.append(copy)
	return JSON.stringify(copies)

func claim_pending_reward() -> void:
	if busy or me.get("pending_reward")==null: return
	busy=true
	var result: Dictionary = await api.post("/v1/runs/"+me.pending_reward.id+"/claim",api.mutation())
	busy=false
	if check(result):
		await refresh_inventory()
		message(tr("생존 보상 %d 별씨를 받았습니다.") % result.data.reward,"success")
		# The hero's soft reward sparkle follows the success chime instead of landing on it.
		voice_later("reward",0.5,-4.0)

func poll_entitlements() -> void:
	if social.visiting(): return
	if polling_entitlements or busy or refreshing or VersionGate.is_blocked(): return
	polling_entitlements=true
	var epoch := world_epoch
	var result: Dictionary = await api.request("/v1/me")
	polling_entitlements=false
	if epoch!=world_epoch: return
	# Maintenance or a too-old game is not a lost session: the gate's screen waits it out.
	if not result.ok and result.error in Api.GATE_CODES: return
	if not result.ok:
		# Fail closed on auth loss or disconnection; don't retain protected models.
		cancel_preview()
		CraftTracker.end(api)
		SocialHud.end(api)
		api.token=""
		build_world(false)
		login_ui()
		refuse(error_message(result.error))
		return
	# Residents' home versions: a house cached at this version opens without asking again.
	NpcGifts.set_versions(result.data.get("npc_homes"),result.data.get("npc_homes_host",""))
	var story := chapter()
	if story: story.adopt(result.data.get("story"))
	if story: story.adopt_quests(result.data.get("quests"))
	if objects_signature(result.data.objects)!=objects_signature(me.objects) or result.data.shards!=me.shards:
		cancel_preview()
		await refresh_inventory()

func select_object(index: int) -> void:
	if is_instance_valid(preview): cancel_preview()
	if is_instance_valid(shape_panel) and str(shape_panel.object.get("id",""))!=str(me.objects[index].id): shape_panel.close()
	selected = me.objects[index]
	var state_name: String={"inventory":tr("보관 중"),"placed":tr("배치됨 · ")+{"home":tr("내 집"),"workshop":tr("공방"),"village":tr("마을")}.get(selected.get("room","village"),tr("다른 공간")),"listed":tr("장터에서 판매 중")}[selected.state]
	object_info.text = "%s\n%s" % [selected.name,state_name]
	inspect_object(selected.duplicate())

func load_object(obj: Dictionary, prefix: String="/v1/objects/") -> Node3D:
	var assembly: Node3D=await preload("res://scripts/asset_assembly.gd").fetch(api,obj.id,prefix)
	if assembly:
		await PaintApply.attach(api,assembly,obj,prefix)
		# The owner's shape edit (width, depth, height, size, mirror) shows wherever it stands.
		ObjectTransform.apply(assembly,obj.get("shape"))
		return assembly
	if obj.get("studio",false):refuse(tr("가구의 모든 부품을 불러오지 못했습니다."));return null
	var response: Dictionary = await api.request(prefix+obj.id+"/model",{},HTTPClient.METHOD_GET,true)
	if not check(response): return null
	var model := Loader.load_bytes(response.bytes)
	if model:
		Loader.paint(model,Color(obj.color))
		# The painted surface (painter/paint_apply.gd), cached by object and paint version.
		await PaintApply.attach(api,model,obj,prefix)
		ObjectTransform.apply(model,obj.get("shape"))
	else: refuse(tr("물건을 꺼내지 못했어요."))
	return model

## The bag's paint entry follows the selected object: objects with UVs open the painting
## workspace; others keep the colour swatches (whole-object colour) with a short reason.
func update_paint_entry(model: Node3D) -> void:
	if not is_instance_valid(paint_button): return
	var paintable := PaintApply.has_uvs(model)
	paint_palette.visible = not paintable
	paint_button.visible = true
	paint_button.text = tr("색칠하기") if paintable else tr("전체 색 고르기")
	paint_hint.visible = not paintable
	paint_hint.text = tr("이 물건은 표면 좌표(UV) 없이 만들어져 전체 색만 바꿀 수 있어요.")

func open_painter() -> void:
	if selected.is_empty() or busy or is_instance_valid(painter): return
	if selected.state=="listed":
		refuse(tr("장터에 올린 물건은 칠할 수 없어요."))
		return
	if not is_instance_valid(inspect_model):
		message(tr("물건을 불러오는 중이에요. 잠시 뒤에 다시 눌러 주세요."))
		return
	if is_instance_valid(shape_panel): shape_panel.close()
	var parts: Array=[]
	if inspect_model.get_meta("studio",false):
		for p in inspect_model.manifest.plan.parts: parts.append([str(p.id),str(p.id)])
	var id: String=selected.id
	painter=load("res://scripts/painter/painter.gd").new()
	painter.setup(api,selected.duplicate(),inspect_model,{"views":[get_viewport()],"parts":parts,
		"saved":func(image,version): painter_saved(id,image,version),
		"flat":func(hex: String,part: String,reset: bool): painter_flat(id,hex,part,reset)})
	ui.add_child(painter)
	player.controls_enabled=false

## The interaction editor (scripts/interaction_panel.gd) for the selected crafted object. The bag's
## preview model is borrowed while it is open.
func open_interactions() -> void:
	if selected.is_empty() or busy or is_instance_valid(interaction_panel) or is_instance_valid(painter) or social.visiting(): return
	if not selected.get("studio",false) or not is_instance_valid(inspect_model) or not inspect_model.has_method("use_interaction"):
		refuse(tr("직접 만든 물건만 상호작용을 넣을 수 있어요."))
		return
	if selected.state=="listed":
		refuse(tr("장터에 올린 물건은 바꿀 수 없어요."))
		return
	var id: String=selected.id
	interaction_panel=InteractionPanel.new()
	interaction_panel.setup(api,selected.duplicate(),inspect_model,{"saved":func(reply: Dictionary): interactions_saved(id,reply)})
	ui.add_child(interaction_panel)
	player.controls_enabled=false

## A saved interaction: the placed copy runs it now, and the bag knows the new runtime version
## (so the next poll does not reload every object).
func interactions_saved(id: String, reply: Dictionary) -> void:
	for obj in me.objects:
		if obj.id==id: obj.runtime_version=reply.runtime.version
	if selected.get("id","")==id: selected.runtime_version=reply.runtime.version
	var value = reply.get("interaction")
	var item: Node3D=loaded.get(id)
	if is_instance_valid(item) and item.has_method("use_interaction"):
		item.use_interaction(value if value is Dictionary else {},reply.program,reply.runtime)

## The painter saved (image) or cleared (null) an object's paint: every copy shows it now.
func painter_saved(id: String, image, version) -> void:
	for i in me.objects.size():
		if me.objects[i].id==id: me.objects[i].paint_version=version
	if selected.get("id","")==id: selected.paint_version=version
	var key := "" if version==null else id+":"+str(int(version))
	for item in [inspect_model,loaded.get(id),preview]:
		if not is_instance_valid(item): continue
		if image==null: PaintApply.clear(item)
		elif item!=preview or selected.get("id","")==id: PaintApply.apply(item,image,key)
	message(tr("칠한 모습을 저장했어요.") if image!=null else tr("처음 모습으로 되돌렸어요."))

## 모양 바꾸기: sliders for the selected object, previewed on the bag's view and the placed copy.
func open_shape_panel() -> void:
	if selected.is_empty() or busy or is_instance_valid(painter): return
	if is_instance_valid(shape_panel):
		shape_panel.close()
		return
	if selected.state=="listed":
		refuse(tr("장터에 올린 물건은 모양을 바꿀 수 없어요."))
		return
	if not is_instance_valid(inspect_model):
		message(tr("물건을 불러오는 중이에요. 잠시 뒤에 다시 눌러 주세요."))
		return
	cancel_preview()
	var id: String=selected.id
	shape_panel=ShapePanel.new()
	shape_panel.setup(api,selected,func(): return [inspect_model if selected.get("id","")==id else null,loaded.get(id)],message)
	shape_panel.saved.connect(func(shape: Dictionary): shape_saved(id,shape))
	ui.add_child(shape_panel)

## A saved shape: the lists match the server again, so the next poll reloads nothing.
func shape_saved(id: String, shape: Dictionary) -> void:
	for obj in me.get("objects",[]):
		if obj.id==id: obj.shape=shape
	if selected.get("id","")==id: selected.shape=shape
	message(tr("모양을 바꿨어요.") if not ObjectTransform.is_default(shape) else tr("처음 모양으로 돌아왔어요."))

## Whole-object colour from the painter's fallback panel (objects without UVs).
func painter_flat(id: String, hex: String, part: String, reset: bool) -> void:
	if selected.get("id","")!=id: return
	if not selected.get("studio",false):
		await paint_object("#f6eee0" if reset else hex)
		return
	if busy or not is_instance_valid(inspect_model): return
	busy=true
	var reply: Dictionary=await api.post("/v1/objects/"+id+"/colors",api.mutation({"version":inspect_model.runtime_version,"part":part,"color":hex,"reset":reset}))
	busy=false
	if not check(reply): return
	for item in [inspect_model,loaded.get(id),preview]:
		if is_instance_valid(item) and item.get_meta("studio",false): item.paint(reply.data.colors);item.runtime_version=reply.data.version
	for obj in me.objects:
		if obj.id==id: obj.runtime_version=reply.data.version
	message(tr("가구 색을 바꿨어요."))

func edit_object(extra: Dictionary) -> bool:
	if selected.is_empty() or busy: return false
	busy = true
	var id: String = selected.id
	var response: Dictionary = await api.post("/v1/objects/"+id,api.mutation(extra.merged({"version":selected.version})))
	busy = false
	if not check(response): return false
	selected = response.data
	return true

func paint_object(color: String) -> void:
	if selected.get("studio",false):
		if busy or not is_instance_valid(inspect_model):return
		busy=true
		var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/colors",api.mutation({"version":inspect_model.runtime_version,"part":"all","color":color}))
		busy=false
		if not check(reply):return
		for item in [inspect_model,loaded.get(selected.id),preview]:
			if is_instance_valid(item) and item.get_meta("studio",false):item.paint(reply.data.colors);item.runtime_version=reply.data.version
		for obj in me.objects:
			if obj.id==selected.id:obj.runtime_version=reply.data.version
		RpgUi.sfx("paint",-6.0)
		message(tr("가구의 모든 부품 색상을 저장했어요."))
		return
	if await edit_object({"action":"paint","color":color}):
		RpgUi.sfx("paint",-6.0)
		message(tr("새 색으로 칠했어요."))
		if is_instance_valid(preview): Loader.paint(preview,Color(color))
		if loaded.has(selected.id): Loader.paint(loaded[selected.id],Color(color))
		if is_instance_valid(inspect_model): Loader.paint(inspect_model,Color(color))
		for i in me.objects.size():
			if me.objects[i].id==selected.id:
				me.objects[i]=selected

func retrieve_object() -> void:
	cancel_preview()
	if await edit_object({"action":"retrieve"}):
		await refresh_inventory()
		RpgUi.sfx("lift",-6.0)
		message(tr("보관함으로 회수했습니다."))

func begin_place() -> void:
	if selected.is_empty() or busy or refreshing: return
	# Something standing in the village can be picked up again: moved or turned in one step.
	var moving: bool=selected.state=="placed" and selected.get("room","village")=="village" and loaded.has(selected.id)
	if selected.state!="inventory" and not moving:
		refuse(tr("보관 중인 물건을 선택하세요."))
		return
	cancel_preview()
	if is_instance_valid(shape_panel): shape_panel.close()
	busy = true
	preview = await load_object(selected)
	busy = false
	if preview:
		world.add_child(preview)
		preview_rotation=ObjectTransform.wrap_degrees(float(selected.get("rotation",0))) if moving else 0
		preview_moving=str(selected.id) if moving else ""
		preview_follow=not moving
		preview_mouse=get_viewport().get_mouse_position()
		if moving:
			preview.position=TownLayout.furniture_point(selected.x,selected.z)
			if is_instance_valid(loaded.get(preview_moving)): loaded[preview_moving].visible=false
		preview.rotation_degrees.y=preview_rotation
		# A ground disc shows whether the spot is free: green to place, red when blocked.
		var disc := MeshInstance3D.new()
		var plate := CylinderMesh.new()
		var span: Vector3=preview.get_meta("size",Vector3.ONE)
		# Wide enough for the footprint at any turn.
		plate.top_radius=Vector2(span.x,span.z).length()*.5+.04;plate.bottom_radius=plate.top_radius;plate.height=.04
		disc.mesh=plate;disc.position.y=.03;disc.name="PlacementDisc"
		var tint := StandardMaterial3D.new();tint.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		tint.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;tint.albedo_color=Color(.4,.9,.5,.45)
		disc.material_override=tint;disc.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		preview.add_child(disc)
		# The spot's state from the start, so the first frame plays no valid/invalid flip. A picked-up
		# piece already stands on its spot; a new one has none until the pointer first places it
		# (_process: that first spot sets the colour and plays no snap tick).
		disc.set_meta("free",placement_problem().is_empty())
		if moving: preview.set_meta("ghost_spot",true)
		player.controls_enabled=false
		if right.get_parent().visible: toggle_drawer()
		show_turn_hud(true)
		RpgUi.sfx("lift",-6.0)
		message(tr("바닥을 클릭해 놓기 · R·휠 돌리기 · Esc 취소"))

func cancel_preview() -> void:
	if is_instance_valid(preview): preview.queue_free()
	preview=null
	if not preview_moving.is_empty():
		if is_instance_valid(loaded.get(preview_moving)): loaded[preview_moving].visible=true
		preview_moving=""
	show_turn_hud(false)
	if is_instance_valid(player): player.controls_enabled=screen=="village"

## Turns the placement ghost (R, the wheel or the turn bar's arrows).
func turn_preview(degrees: int) -> void:
	if not is_instance_valid(preview): return
	preview_rotation=ObjectTransform.wrap_degrees(preview_rotation+degrees)
	RpgUi.sfx("rotate",-9.0)
	ObjectTransform.show_angle(turn_readout,preview_rotation)

## ↶ angle ↷ above the prompt chip while placing.
func show_turn_hud(on: bool) -> void:
	if not on:
		if is_instance_valid(turn_hud): turn_hud.queue_free()
		turn_hud=null
		return
	if not is_instance_valid(turn_hud):
		var pill := PanelContainer.new()
		pill.name="TurnHud"
		pill.theme=night_theme()
		var chip := RpgUi.panel_style("pill")
		chip.content_margin_left=14;chip.content_margin_right=22
		pill.add_theme_stylebox_override("panel",chip)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation",12)
		pill.add_child(row)
		turn_readout=ObjectTransform.turn_bar(row,turn_preview)
		RpgUi.label(row,tr("%s · 휠") % RpgUi.key_text("rotate"),13,RpgUi.SOFT,false).size_flags_vertical=Control.SIZE_SHRINK_CENTER
		ui.add_child(pill)
		var size := pill.get_combined_minimum_size()
		pill.position=Vector2(640-size.x*.5,496)
		RpgUi.pin(pill,0.5,1.0)
		RpgUi.pop_in(pill)
		turn_hud=pill
	ObjectTransform.show_angle(turn_readout,preview_rotation)

## Why the preview spot cannot take the furniture, or "" when it is free.
## Mirrors homestead.village_inside/village_reserved and adds the map's own geometry.
func placement_problem() -> String:
	var p := TownLayout.furniture_local(preview.position)
	if p.x< -60 or p.x>130 or p.y< -115 or p.y>60: return tr("섬 안쪽에 놓아 주세요.")
	if preview.position.y<TownLayout.SHORE_MIN_Y+.5: return tr("물 위에는 놓을 수 없어요.")
	if absf(p.x)<2 and absf(p.y)<2: return tr("광장 한가운데는 비워 주세요.")
	if absf(p.x)<3.5 and p.y> -12 and p.y< -6: return tr("공방 입구 앞은 비워 주세요.")
	if Vector2(player.position.x-preview.position.x,player.position.z-preview.position.z).length()<1.3:
		return tr("캐릭터와 겹치지 않는 곳에 놓으세요.")
	var span: Vector3=preview.get_meta("size",Vector3.ONE)
	var box := BoxShape3D.new();box.size=Vector3(maxf(span.x,.4),maxf(span.y-.1,.2),maxf(span.z,.4))
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape=box;query.collision_mask=2|8|16
	# The box turns with the ghost, so any angle checks its real footprint.
	query.transform=Transform3D(Basis(Vector3.UP,deg_to_rad(preview_rotation)),preview.position+Vector3(0,box.size.y*.5+.08,0))
	# The object being moved does not block its own new spot.
	if is_instance_valid(loaded.get(preview_moving)):
		var own: Array[RID]=[]
		for body in loaded[preview_moving].get_children():
			if body is CollisionObject3D: own.append(body.get_rid())
		query.exclude=own
	if not get_world_3d().direct_space_state.intersect_shape(query,1).is_empty(): return tr("건물이나 다른 물건과 겹쳐요.")
	return ""

func place_preview() -> void:
	if not is_instance_valid(preview): return
	var p := TownLayout.furniture_local(preview.position)
	var problem := placement_problem()
	if not problem.is_empty():
		refuse(problem)
		return
	if not preview_moving.is_empty():
		if await move_object(p):
			# The standing copy takes the new spot and turn at once; the refresh confirms it.
			var standing: Node3D=loaded.get(preview_moving)
			if is_instance_valid(standing) and is_instance_valid(preview):
				standing.position=TownLayout.furniture_point(p.x,p.y);standing.rotation_degrees.y=preview_rotation
				standing.visible=true
				Fx.arrive(object_root,standing,self,false)
			cancel_preview()
			await refresh_inventory()
			RpgUi.sfx("place",-8.0)
			message(tr("자리와 방향을 바꿨어요."))
		return
	if selected.is_empty():
		cancel_preview()
		return
	var placing_id := str(selected.id)
	var placing_key := object_key(selected)
	if await edit_object({"action":"place","x":p.x,"z":p.y,"rotation":preview_rotation}):
		adopt_preview(placing_id,placing_key,TownLayout.furniture_point(p.x,p.y))
		cancel_preview()
		await refresh_inventory()
		RpgUi.sfx("place",-4.0)
		message(tr("마을에 놓았습니다. 다시 접속해도 유지됩니다."))

## The ghost the player put down stays as the placed object, so the refresh finds it already loaded:
## no second download and no frame without it. It arrives with a pop (fx.gd arrive).
func adopt_preview(id: String, key: String, at: Vector3) -> void:
	if not is_instance_valid(preview) or not is_instance_valid(object_root): return
	var item := preview
	preview = null
	var disc := item.get_node_or_null("PlacementDisc")
	if disc: disc.free()
	if is_instance_valid(loaded.get(id)): loaded[id].queue_free()
	item.reparent(object_root)
	item.position = at
	item.rotation_degrees.y = preview_rotation
	item.set_meta("object_key",key)
	Loader.add_collision(item)
	loaded[id] = item
	Fx.arrive(object_root,item,self)

## Moves or turns an object already standing in the village (one server step, no retrieve).
func move_object(at: Vector2) -> bool:
	if selected.is_empty() or busy: return false
	busy=true
	var response: Dictionary=await api.post("/v1/objects/"+selected.id+"/placement",api.mutation({"version":selected.version,"room":"village","x":at.x,"z":at.y,"rotation":preview_rotation}))
	busy=false
	return check(response)

func generate() -> void:
	if busy or not job_id.is_empty(): return
	if prompt.text.strip_edges().length()<3:
		refuse(tr("만들고 싶은 물건을 세 글자 이상 적어 주세요."))
		return
	busy=true
	var result: Dictionary = await api.post("/v1/generations",api.mutation({"prompt":prompt.text}))
	busy=false
	if not check(result): return
	job_id=result.data.id
	message(tr("공방에서 만들고 있습니다…"))
	await refresh_inventory()

func poll_job() -> void:
	if polling_job or job_id.is_empty(): return
	polling_job=true
	var epoch := world_epoch
	var result: Dictionary = await api.request("/v1/generations/"+job_id)
	if epoch!=world_epoch:
		polling_job=false
		return
	if not check(result):
		polling_job=false
		return
	if result.data.state=="ready":
		await refresh_inventory()
		job_id=""
		RpgUi.sfx("craft_done",-6.0)
		message(tr("새 물건이 보관함에 도착했습니다!"))
	elif result.data.state in ["failed","unknown"]:
		job_id=""
		RpgUi.sfx("craft_fail",-6.0)
		message(tr("생성 상태: ")+result.data.state+" · "+error_message(str(result.data.error_code)))
	else: message(tr("공방에서 물건을 만들고 있습니다…"))
	polling_job=false

func sell_object() -> void:
	if not TRADING_UI_ENABLED or selected.is_empty() or busy: return
	busy=true
	var result: Dictionary = await api.post("/v1/market",api.mutation({"object_id":selected.id,"version":selected.version,"price":int(price.value)}))
	busy=false
	if check(result):
		await refresh_inventory()
		message(tr("장터에 등록했습니다. 판매 중에는 배치와 색칠이 잠깁니다."))

func show_market() -> void:
	if not TRADING_UI_ENABLED: return
	cancel_preview()
	var result: Dictionary = await api.request("/v1/market")
	if not check(result): return
	var popup := Window.new()
	popup.title=tr("별씨 장터")
	popup.size=Vector2i(650,470)
	popup.theme=ui.theme
	popup.close_requested.connect(popup.queue_free)
	add_child(popup)
	var scroll := ScrollContainer.new()
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	popup.add_child(scroll)
	var rows := VBoxContainer.new()
	rows.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	scroll.add_child(rows)
	text(rows,tr("물건과 별씨는 서버에서 동시에 이전됩니다."),17)
	if result.data.listings.is_empty(): text(rows,tr("아직 등록된 물건이 없습니다."))
	for listing in result.data.listings:
		var line := HBoxContainer.new()
		rows.add_child(line)
		text(line,tr("%s · %d 별씨 · %s") % [listing.name,listing.price,listing.seller]).size_flags_horizontal=Control.SIZE_EXPAND_FILL
		button(line,tr("판매 취소") if listing.mine else tr("구매"),func():
			var response: Dictionary = await api.post("/v1/market/"+listing.id+("/cancel" if listing.mine else "/buy"),api.mutation())
			if check(response):
				popup.queue_free()
				await refresh_inventory()
				message(tr("장터 거래가 완료됐습니다.")))
	popup.popup_centered()

func start_run(map_id := "forest", difficulty := "standard", chapter_id := "", party_run_id := "") -> void:
	if busy: return
	if screen == "survival" and coop_run and party_run_id == run_id:
		close_village_modal()
		return
	close_village_modal()
	cancel_preview()
	# The first expedition is the tutorial until it is cleared once (/v1/me tutorial_done; a run under
	# way resumes as it is, a party goes where its leader chose).
	if party_run_id.is_empty() and not bool(me.get("tutorial_done",true)):
		map_id="tutorial"
		chapter_id=""
	busy=true
	# The expedition's props read on a worker thread while the server answers and the card comes up,
	# for the map the run is on: a run under way (resumed) stays on the map it began on. A co-op run's
	# map is known once its snapshot is in (prefetch_run_map below).
	var prefetched := ""
	if party_run_id.is_empty():
		var active = me.get("active_run_summary")
		prefetched = str(active.get("map_id",map_id)) if active is Dictionary else map_id
		LoadPace.want(preload("res://maps/survival/survival_map.gd").resource_paths(prefetched))
	coop_run = not party_run_id.is_empty()
	var result: Dictionary = {"ok":true,"data":{"id":party_run_id}} if coop_run else await api.post("/v1/runs",api.mutation({"map_id":map_id,"difficulty":difficulty,"chapter_id":chapter_id}))
	if not check(result):
		busy=false
		return
	run_id=result.data.id
	sound.stinger("res://assets/sfx/world/portal.wav")
	var snapshot: Dictionary = await api.request(run_route())
	if not check(snapshot):
		busy=false
		return
	run=snapshot.data
	prefetch_run_map(str(run.get("map_id",map_id)),prefetched)
	# Into the expedition under the same loading card as every other change of place.
	var veil := Transition.of(get_tree())
	veil.loading(region_name(str(run.get("map_id",map_id))),"run",str(run.get("map_id",map_id)))
	await veil.fade_out()
	# The village's own per-frame work stops while the expedition is built under the card.
	screen="loading"
	if not await build_world(true):
		busy=false
		return
	# The HUD over the next frames under the card, a piece where a frame has room (LoadPace.step),
	# main's own per-frame work and input still held as in the build: built in the build's last frame
	# with the run's first nodes, the village HUD's teardown and their layout and first draws, it held
	# that one frame 55-80 ms (tests/expedition_baseline.gd).
	var paced := LoadPace.covered
	if paced: hold(true)
	await LoadPace.step("expedition hud")
	clear_ui()
	screen="survival"
	player.controls_enabled=false
	left=panel(Vector2(20,20),256,"night")
	var region_head := HBoxContainer.new()
	region_head.add_theme_constant_override("separation",8)
	left.add_child(region_head)
	region_head.add_child(RpgUi.icon("res://assets/ui/expedition.svg",34))
	var region_titles := VBoxContainer.new()
	region_titles.add_theme_constant_override("separation",-2)
	region_head.add_child(region_titles)
	RpgUi.label(region_titles,region_name(run.get("map_id","forest")),23,RpgUi.INK)
	# The run's terms: its stages (and the boss of the last night), the tutorial; seven nights before stages.
	var terms := [difficulty_name(run.get("difficulty","standard"))]
	if bool(run.get("tutorial",false)): terms.append(tr("튜토리얼"))
	elif run.has("stage_count"):
		terms.append(tr("스테이지 %d") % int(run.stage_count))
		if bool(run.get("has_boss",false)): terms.append(tr("우두머리"))
	else: terms.append(tr("일곱 밤 생존"))
	RpgUi.label(region_titles," · ".join(terms),12,RpgUi.GOLD)
	RpgUi.divider(left,Color(RpgUi.GOLD,.55))
	metrics=text(left,"",13)
	metrics.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	metrics.custom_minimum_size.x=214
	var hp_meter := status_meter(left,tr("♥  체력").trim_prefix("♥  "),Color("e2735f"),"heart")
	hp_bar=hp_meter.bar;hp_readout=hp_meter.readout
	var hunger_meter := status_meter(left,tr("◆  포만감").trim_prefix("◆  "),RpgUi.AMBER,"hunger")
	hunger_bar=hunger_meter.bar;hunger_readout=hunger_meter.readout
	var stamina_meter := status_meter(left,tr("✧  기력").trim_prefix("✧  "),Color("6fd0b6"),"stamina")
	stamina_bar=stamina_meter.bar;stamina_readout=stamina_meter.readout
	hp_bar.tooltip_text=tr("체력");hunger_bar.tooltip_text=tr("포만감");stamina_bar.tooltip_text=tr("기력")
	# The four gathered resources at a glance (pictures and numbers; the bag has the rest).
	RpgUi.divider(left,Color(RpgUi.GOLD,.55))
	var quick_row := HBoxContainer.new()
	quick_row.name="QuickCounts"
	quick_row.add_theme_constant_override("separation",4)
	left.add_child(quick_row)
	for item in ["wood","stone","berry","fiber"]:
		var chip := HBoxContainer.new()
		chip.add_theme_constant_override("separation",3)
		chip.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		chip.alignment=BoxContainer.ALIGNMENT_CENTER
		quick_row.add_child(chip)
		RpgUi.name_tip(chip,tr(ITEM_NAMES[item]))
		chip.add_child(RpgUi.name_tip(RpgUi.icon("res://assets/items/"+item+".svg",24),tr(ITEM_NAMES[item])))
		quick_counts[item]=RpgUi.numbers(RpgUi.label(chip,"0",16),16)
	await LoadPace.step("expedition field map")
	# Top right, where the village's minimap sits: the field map and the way back to camp.
	var navigation := panel(Vector2(1000,20),256,"night")
	field_panel=navigation.get_parent()
	field_panel.name="FieldMap"
	RpgUi.pin(field_panel,1.0,0.0)
	field_map=preload("res://scripts/field_map.gd").new()
	navigation.add_child(field_map)
	RpgUi.name_tip(field_map,tr("주변 지도"))
	camp_status=text(navigation,"",12)
	camp_status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	camp_status.custom_minimum_size=Vector2(210,0)
	# Two lines (distance and fire, warmth); the ground's line on ice or embers makes a third.
	camp_status.max_lines_visible=3
	camp_status.custom_minimum_size.y=camp_status.get_line_height()*2+camp_status.get_theme_constant("line_spacing")
	await LoadPace.step("expedition bag")
	right=panel(Vector2(948,20),308,"hero")
	RpgUi.pin(right.get_parent(),1.0,0.0)
	var drawer_title := HBoxContainer.new()
	right.add_child(drawer_title)
	drawer_title.add_child(RpgUi.icon("res://assets/ui/bag.svg",30))
	text(drawer_title,tr("탐험 가방"),24).size_flags_horizontal=Control.SIZE_EXPAND_FILL
	close_button(drawer_title,toggle_drawer,"I")
	pack=RpgUi.caption(right,"",13)
	var inventory_grid := GridContainer.new()
	inventory_grid.columns=4
	inventory_grid.add_theme_constant_override("h_separation",5)
	inventory_grid.add_theme_constant_override("v_separation",5)
	right.add_child(inventory_grid)
	for item in ITEM_NAMES:
		var slot := Button.new()
		slot.custom_minimum_size=Vector2(61,70)
		slot.focus_mode=Control.FOCUS_NONE
		slot.theme_type_variation="SlotButton"
		RpgUi.hover_motion(slot,1.06)
		RpgUi.name_tip(slot,tr(ITEM_NAMES[item])+(tr(" · 클릭해서 먹기") if item in ["berry","soup"] else tr(" · 클릭해서 치료") if item=="bandage" else ""))
		slot.pressed.connect(func():
			if item in ["berry","soup"]: intent("eat",item)
			elif item=="bandage": intent("heal"))
		inventory_grid.add_child(slot)
		var icon := TextureRect.new()
		icon.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
		icon.texture=load("res://assets/items/"+item+".svg")
		icon.position=Vector2(10,4)
		icon.size=Vector2(40,40)
		icon.mouse_filter=Control.MOUSE_FILTER_IGNORE
		slot.add_child(icon)
		var count := Label.new()
		count.position=Vector2(0,44)
		count.size=Vector2(61,20)
		count.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
		count.mouse_filter=Control.MOUSE_FILTER_IGNORE
		RpgUi.numbers(count,14)
		slot.add_child(count)
		inventory_slots[item]={"count":count,"icon":icon,"button":slot}
	await LoadPace.step("expedition crafts")
	rule(right)
	text(right,tr("제작대"),21)
	craft_buttons.axe=button(right,tr("돌도끼 · 목재 3 + 돌 2"),func(): intent("craft","axe"))
	craft_buttons.spear=button(right,tr("창 · 목재 4 + 돌 2"),func(): intent("craft","spear"))
	craft_buttons.soup=button(right,tr("수프 · 열매 3 + 목재 1"),func(): intent("craft","soup"))
	craft_buttons.bandage=button(right,tr("붕대 · 섬유 3"),func(): intent("craft","bandage"))
	craft_buttons.axe.tooltip_text=tr("나무에서 목재를 한 번에 2개 채집합니다. 밤의 모닥불용 목재 2개를 남겨 두세요.")
	craft_buttons.spear.tooltip_text=tr("공격 피해 10 → 25. 적의 준비 동작을 공격으로 끊을 수 있습니다.")
	craft_buttons.soup.tooltip_text=tr("열매보다 많은 포만감과 체력을 회복합니다. Q를 누르면 수프를 먼저 먹습니다.")
	craft_buttons.bandage.tooltip_text=tr("H로 사용하면 체력 30을 회복합니다. 체력이 가득 차면 소모하지 않습니다.")
	RpgUi.caption(right,tr("제작 전에 밤에 쓸 목재 2개를 남겨 두세요."),12,RpgUi.ACCENT)
	RpgUi.caption(right,tr("붉은 공격 예고는 Shift로 피하세요.\n목재 두 개는 모닥불을 위해 남겨 두세요."),12)
	right.get_parent().visible=false
	await LoadPace.step("expedition hotbar")
	build_play_hud(true)
	# The one prompt chip, as in the village and rooms: what the interact key gathers right here.
	hint=RpgUi.prompt(ui,560)
	await LoadPace.step("expedition nodes")
	if paced: hold(false)
	update_run()
	busy=false
	veil.fade_in()

## The run is on `actual`; start_run read `prefetched` ahead ("" for none, a co-op run). Another map's
## reads still queued are dropped and this map's are queued, so its baked ground, props and resource
## models come from the worker threads instead of loading on the main thread under the card (a read
## already on a worker finishes and is let go at LoadPace.release()).
func prefetch_run_map(actual: String, prefetched: String) -> void:
	if actual == prefetched: return
	var survival_map := preload("res://maps/survival/survival_map.gd")
	var needed: Array = survival_map.resource_paths(actual)
	if not prefetched.is_empty():
		for path in survival_map.resource_paths(prefetched):
			if not path in needed: LoadPace.queue.erase(path)
	LoadPace.want(needed)

func intent(action: String, target := "") -> void:
	if screen!="survival" or paused or run.get("status","")!="active": return
	# Eating, healing, crafting and fueling take precedence over a held gather/attack key.
	if not pending_action.is_empty() and (action in ["harvest","attack"] or pending_action not in ["harvest","attack"]): return
	if action=="harvest" and target.is_empty():
		var nearest := 2.4
		for node in run.nodes:
			var dist := Vector2(run.x-node.x,run.z-node.z).length()
			if node.quantity>0 and dist<nearest:
				nearest=dist
				target=node.id
		if target.is_empty():
			# Nothing in reach: the press gets the soft deny the field uses (its toasts are silent),
			# on the shared 800 ms throttle; a held E repeating the gather stays quiet.
			if Input.is_action_just_pressed("interact") and Time.get_ticks_msec()-survival_deny_at>800:
				survival_deny_at=Time.get_ticks_msec()
				RpgUi.sfx("deny",-9.0)
			message(tr("채집할 나무·바위·풀·열매 가까이 가세요."))
			return
	pending_action=action
	pending_target=target

func run_route() -> String:
	return ("/v1/coop/runs/" if coop_run else "/v1/runs/")+run_id

func tick_run() -> void:
	if ticking or busy or (paused and not coop_run) or run.get("status","")!="active" or VersionGate.is_blocked(): return
	ticking=true
	var movement := movement_input()
	var ready: bool=run.get("action_cooldown",0)<=0.01 and (pending_action!="attack" or run.get("attack_cooldown",0)<=0.01)
	var payload := {"sequence":int(run.sequence)+1,"dx":movement.x,"dz":movement.y,"sprint":world_movement_allowed() and GameSettings.running(),"action":pending_action if ready else "","target":pending_target if ready else ""}
	if ready:
		pending_action=""
		pending_target=""
	var epoch := world_epoch
	var sent_at := Time.get_ticks_msec()
	var result: Dictionary = await api.post_kept(run_route()+"/input",payload)
	if epoch!=world_epoch:
		ticking=false
		return
	if not result.ok:
		network_failures+=1
		message(tr("숲과의 연결을 다시 잇는 중이에요…"))
		# An uncertain response may have committed. Resync sequence before sending again.
		var snapshot: Dictionary = await api.request(run_route())
		if epoch!=world_epoch:
			ticking=false
			return
		if snapshot.ok:
			run=snapshot.data
			update_run()
		ticking=false
		return
	ticking=false
	network_failures=0
	if result.data.hp<run.get("hp",100)-1:
		CombatAudio.play(self,"player_hit")
		HeroVoice.play(self,"hurt")
		player.react("hurt")
		floating_feedback("−%d" % int(ceil(run.hp-result.data.hp)),player.position,Color("ef9983"))
	else:
		# A telegraphed strike ended (windup -> recover) without hurting the hero or being interrupted: it missed.
		for after in result.data.get("enemies",[]):
			if str(after.get("phase",""))!="recover": continue
			for before in run.get("enemies",[]):
				if before.id==after.id and str(before.get("phase",""))=="windup" and float(after.hp)>=float(before.hp):
					CombatAudio.play(self,"whiff",Vector3(float(after.get("target_x",after.x)),0,float(after.get("target_z",after.z))))
	# A won run is voiced once by the hero's level-up chime in update_run (no reward jingle on top).
	if not str(payload.action).is_empty():
		var feedback: String=result.data.message
		if feedback.contains("+"):
			for n in run.nodes:
				if n.id==payload.target:
					player.equip("axe" if n.kind=="tree" and run.inventory.axe>0 else "")
					player.face_point(Vector3(n.x,0,n.z))
					resource_response(n)
					CombatAudio.harvest(self,n.kind,Vector3(n.x,0,n.z),"axe" if run.inventory.axe>0 else "")
			player.react("gather")
			if not HeroVoice.play(self,"harvest"): HeroVoice.play(self,"pickup")
			floating_feedback(feedback,player.position,Color("ece1b4"))
		elif feedback.contains("제작 완료"):
			if not CombatAudio.craft(self,str(payload.target)): sound.effect("craft")
			HeroVoice.play(self,"pickup",0.0,true)
			player.react("craft")
			floating_feedback(feedback,player.position,Color("b8dfb1"))
		elif feedback.contains("회복했습니다"):
			# Cloth rip, wrap and pat (combat/bandage, else core/bandage; berries and soup keep core/eat).
			if not CombatAudio.play(self,"bandage"): sound.effect("bandage")
			player.react("eat")
		elif feedback.contains("먹었습니다"):
			sound.effect("eat_soup" if feedback.contains("수프") else "eat")
			player.react("eat")
			HeroVoice.play(self,"eat")
		elif feedback.contains("피웠습니다"): CombatAudio.play(self,"fuel",Vector3.ZERO)
		elif feedback.contains("공격!") or feedback=="가까운 적이 없습니다.":
			var weapon: String="spear" if run.inventory.spear>0 else "axe" if run.inventory.axe>0 else ""
			var struck_enemy := {}
			var hp_left := 0.0
			for enemy in run.enemies:
				var hp_after := 0.0
				for after in result.data.enemies:
					if after.id==enemy.id: hp_after=after.hp
				if hp_after<enemy.hp:
					struck_enemy=enemy
					hp_left=hp_after
					break
			var kill: bool=not struck_enemy.is_empty() and hp_left<=0
			CombatAudio.swing(self,weapon,kill)
			HeroVoice.play(self,"attack_heavy" if kill or CombatAudio.combo%3==0 else "attack")
			player.equip(weapon)
			if not struck_enemy.is_empty():
				var at := Vector3(struck_enemy.x,0,struck_enemy.z)
				CombatAudio.impact(self,str(struck_enemy.get("kind","wolf")),at,kill)
				# The blow cut a telegraphed strike short: the clash of a parry.
				if str(struck_enemy.get("phase",""))=="windup" and not kill: CombatAudio.play(self,"block",at)
				player.face_point(at)
				floating_feedback(str(int(struck_enemy.hp-hp_left)),at,Color("f3c980"))
			player.react("attack")
			attack_sweep()
		elif str(payload.action) in ["eat","heal","craft","fire"] and Time.get_ticks_msec()-survival_deny_at>800:
			# A refused key press (nothing to eat, missing materials, away from the camp...): a soft
			# deny, as the field's toasts are silent. Held gather and attack keys stay quiet.
			survival_deny_at=Time.get_ticks_msec()
			RpgUi.sfx("deny",-9.0)
	run=result.data
	reconcile_walker(sent_at)
	update_run()

## Expedition movement is decided by the server, but waiting a round trip for every step feels
## like lag on an online world. The walker moves at once by the server's own rules (speed,
## sprint, ice, the same blockers and bounds), and each server answer folds back in however far
## the two drifted apart, measured against where the walker was predicted to be at that time.
func predict_walker(delta: float) -> Vector3:
	var server := Vector2(float(run.get("x",0.0)),float(run.get("z",0.0)))
	if predicted==Vector2.INF or run.get("status","")!="active" or paused or results_shown or network_failures>0:
		predicted=server
		predict_fix=Vector2.ZERO
		predict_log.clear()
		return Vector3(predicted.x,0.03,predicted.y)
	var input := movement_input()
	if input.length()>0.01:
		var on_ice := false
		for h in run.get("hazards",[]):
			if str(h.get("kind",""))=="ice" and predicted.distance_to(Vector2(float(h.x),float(h.z)))<float(h.radius): on_ice=true
		var sprint: bool=world_movement_allowed() and GameSettings.running() and (run.get("sprinting",false) or float(run.get("stamina",100.0))>20.0)
		var step: Vector2=input/maxf(1.0,input.length())*(6.75 if sprint else 4.5)*(0.65 if on_ice else 1.0)*delta
		var limit := walker_bounds()
		var parts := maxi(1,ceili(maxf(absf(step.x),absf(step.y))/0.25))
		for i in parts:
			var nx := clampf(predicted.x+step.x/parts,-limit,limit)
			if walker_clear(nx,predicted.y): predicted.x=nx
			var nz := clampf(predicted.y+step.y/parts,-limit,limit)
			if walker_clear(predicted.x,nz): predicted.y=nz
	var fold := predict_fix*minf(1.0,delta*8.0)
	predicted+=fold
	predict_fix-=fold
	var now := Time.get_ticks_msec()
	predict_log.append([now,predicted+predict_fix])
	while not predict_log.is_empty() and now-int(predict_log[0][0])>2000: predict_log.pop_front()
	return Vector3(predicted.x,0.03,predicted.y)

func reconcile_walker(sent_at: int) -> void:
	if predicted==Vector2.INF or predict_log.is_empty(): return
	var server := Vector2(float(run.get("x",0.0)),float(run.get("z",0.0)))
	# The server moved the walker up to about halfway through the round trip.
	var mid := (sent_at+Time.get_ticks_msec())/2
	var then: Vector2=predict_log[0][1]
	for entry in predict_log:
		if int(entry[0])>mid: break
		then=entry[1]
	var error: Vector2=server-then
	if error.length()>4.0:
		predicted=server
		predict_fix=Vector2.ZERO
		predict_log.clear()
		return
	predict_fix+=error
	for entry in predict_log: entry[1]+=error

func walker_bounds() -> float:
	var map: Node=world.get_node_or_null("SurvivalMap") if is_instance_valid(world) else null
	return float(map.bounds) if map else 18.0

## The server's clear_position: outside the fire pit, clear of obstacles and of standing trees and stones.
func walker_clear(x: float, z: float) -> bool:
	if Vector2(x,z).length()<1.05: return false
	for o in run.get("obstacles",[]):
		if Vector2(x-float(o.x),z-float(o.z)).length()<float(o.radius)+0.25: return false
	for n in run.get("nodes",[]):
		if str(n.get("kind","")) in ["tree","stone"] and float(n.get("quantity",0))>0 and Vector2(x-float(n.x),z-float(n.z)).length()<0.85: return false
	return true

func update_run() -> void:
	if coop_run:
		social.sync_peers(run.get("players", []))
		social.update_status()
	var remaining := int(ceil(run.get("phase_remaining",0)))
	# A night that holds (the boss night, the tutorial's last night) has no clock: phase_remaining
	# stays 0 until the boss falls or the goals are met.
	if bool(run.get("boss_night",false)): metrics.text=tr("우두머리의 밤")
	elif run.has("stage") and int(run.get("stage_remaining",0))<0: metrics.text=tr("달이 뜬 밤")
	else: metrics.text=tr("%s   ·   %s %d초") % [tr("달이 뜬 밤") if run.night else tr("탐험하기 좋은 낮"),tr("아침까지") if run.night else tr("밤까지"),remaining]
	if is_instance_valid(day_track):
		day_track.text=stage_text()
		# The boss night glows red; the clock reads ∞ until the boss falls.
		day_track.add_theme_color_override("font_color",RpgUi.ACCENT.lightened(0.35) if bool(run.get("boss_night",false)) else RpgUi.INK)
	update_boss_bar()
	hp_bar.value=run.hp
	CombatAudio.heartbeat(self,run.hp if run.status=="active" else 0.0)
	if run.status=="active" and float(run.get("stamina",100.0))<5.0: HeroVoice.play(self,"tired")
	hunger_bar.value=run.hunger
	stamina_bar.value=run.get("stamina",100)
	hp_readout.text="%d / 100" % int(run.hp)
	hunger_readout.text="%d / 100" % int(run.hunger)
	stamina_readout.text="%d / 100" % int(run.get("stamina",100))
	for item in quick_counts: quick_counts[item].text=str(int(run.inventory[item]))
	var camp_distance := Vector2(run.x,run.z).length()
	camp_status.text=tr("야영지 %.0fm · 불 %d초\n%s") % [camp_distance,run.fire_remaining,tr("불빛 안 · 밤의 위협을 막아 줍니다") if run.get("warm",false) else tr("지도 중앙의 ▲로 돌아오세요")]
	if run.get("terrain_effect","")=="ice": camp_status.text+=tr("\n얼음 위 · 이동 둔화 / 허기 증가")
	elif run.get("terrain_effect","")=="ember": camp_status.text+=tr("\n뜨거운 균열! 빨리 벗어나세요")
	field_map.update_state(run,Vector2(player.facing.x,player.facing.z))
	var total := 0
	for item in ITEM_NAMES:
		var amount := int(run.inventory[item])
		total+=amount
		inventory_slots[item].count.text=str(amount)
		inventory_slots[item].icon.modulate=Color.WHITE if amount>0 else Color(0.45,0.5,0.47)
		inventory_slots[item].button.disabled=amount<=0
	pack.text=tr("탐험 소지품  %d / 80") % total
	if is_instance_valid(objective):
		if run.status=="won": objective.text=tr("탐험 성공!\n귀환하여 %d 별씨를 받으세요.") % run.reward
		elif run.status!="active": objective.text=tr("이번 탐험은 여기까지예요.\n귀환 후 다시 도전할 수 있어요.")
		elif run.hunger<35: objective.text=tr("먼저 배를 채우세요\nQ로 열매나 수프를 먹으세요.")
		elif run.night: objective.text=tr("불빛 안에서 밤을 버티세요\nF · 목재 2개로 불 30초 연장\n\n붉은 원 = 적의 공격 예고\nShift로 피하거나 Space로 공격")
		elif run.inventory.wood<4: objective.text=tr("첫 준비 · 목재 모으기\n나무 옆에서 E로 채집하세요.\n밤에 쓸 목재를 남겨 두세요.")
		elif run.inventory.axe==0: objective.text=tr("도끼를 만들면 채집이 빨라져요\n목재 3 + 돌 2를 모으세요.\nI · 가방에서 도구 만들기")
		else: objective.text=tr("다음 밤을 준비하세요\n열매와 목재를 비축하고,\n창으로 그림자 짐승에 맞서세요.")
		if run.get("story") is Dictionary and run.status=="active":
			objective.text=run.story.title+"\n"
			for goal in run.story.goals:objective.text+="%s  %d / %d\n"%[goal.label,goal.current,goal.target]
			objective.text+="\n"+(tr("%s · 먼저 음식을 드세요") % RpgUi.key_text("eat") if run.hunger<35 else tr("%s 제작 · %s 모닥불 · %s 식사") % [RpgUi.key_text("inventory"),RpgUi.key_text("campfire"),RpgUi.key_text("eat")])
	for recipe in craft_buttons:
		var can_make: bool=run.status=="active"
		for item in RECIPES[recipe]:
			if run.inventory.get(item,0)<RECIPES[recipe][item]: can_make=false
		if recipe in ["axe","spear"] and run.inventory.get(recipe,0)>0: can_make=false
		craft_buttons[recipe].disabled=not can_make
	if Time.get_ticks_msec()*0.001>=player.action_until and (not is_instance_valid(player.action_pose) or player.action_pose.elapsed>=player.action_pose.duration):
		player.equip("spear" if run.inventory.spear>0 else "axe" if run.inventory.axe>0 else "")
	# The run's guidance line comes with every state update: say it when it changes, not on every
	# update (the shared toast lane would keep refreshing it, so it never left the screen).
	var run_line := str(run.message)
	if run.status=="won": run_line = tr("생존 성공! 마을로 돌아가 %d 별씨를 받으세요.") % run.reward
	if run_line!=last_run_line:
		last_run_line=run_line
		message(run_line)
	var dawn_now: bool=bool(run.night)!=prior_night and not bool(run.night)
	# A run that ends in this update is heard alone (below): no morning motif or night/dawn sting under it.
	var going_on: bool=run.status=="active"
	if int(run.day)!=prior_day:
		prior_day=int(run.day)
		message(tr("%d일째 아침이에요. 숲을 둘러보고 다음 밤을 준비하세요.") % run.day)
		# A morning motif (core/newday). The day turns at dawn, so it waits until the dawn sting
		# (2.2 s) has rung out instead of overlapping it; skipped if the run is over by then.
		if going_on and dawn_now: newday_later(DAWN_RING)
		elif going_on: sound.effect("newday")
	if bool(run.night)!=prior_night:
		prior_night=bool(run.night)
		if going_on: CombatAudio.play(self,"night" if run.night else "dawn")
		if run.night: message(tr("해가 졌어요. 야영지로 돌아가 불을 지키세요."))
	if run.status!="active" and not results_shown:
		results_shown=true
		var won: bool=run.status=="won"
		# The run's own ending, one phrase each: the hero's level-up chime, then the horn fanfare
		# (core/win) once that chime has rung; or the faint over a soft falling phrase (core/lose).
		# The results card adds nothing on top (show_results).
		var voiced: bool=HeroVoice.play(self,"levelup" if won else "faint",0.0,true)
		if won: effect_later("win",chime_length(str(HeroVoice.last_take.get("levelup","")),WIN_AFTER_MIN,WIN_AFTER_MAX) if voiced else 0.3)
		elif run.status=="lost": sound.effect("lose")
		if is_instance_valid(return_dialog): return_dialog.queue_free()
		show_results()
	flame.visible=run.fire_remaining>0
	warmth_ring.visible=flame.visible
	survival_audio(remaining)
	if run.status=="active" and run.elapsed-last_camp_warning>12:
		if run.night and run.fire_remaining>0 and run.fire_remaining<7:
			message(tr("모닥불이 곧 꺼져요. 야영지에서 F로 목재를 보태세요."))
			last_camp_warning=run.elapsed
		elif not run.night and remaining<=10:
			message(tr("밤까지 %d초! 야영지로 돌아갈 준비를 하세요.") % remaining)
			last_camp_warning=run.elapsed
	for n in run.nodes:
		if not nodes.has(n.id):
			var root := Node3D.new()
			world.add_child(root)
			root.position=Vector3(n.x,0,n.z)
			nodes[n.id]=root
			nodes[n.id].set_meta("kind",n.kind)
			# The survival map supplies Tripo trees, stone piles, berry bushes and grass
			# (plus a stump for felled trees) per map, with the old shapes as fallback.
			preload("res://scripts/biomes.gd").dress_resource(world,root,n.kind)
		# A node that was full and is now used up: its last piece breaks off (not on first sight).
		var spent: bool=n.quantity<=0
		if spent and nodes[n.id].has_meta("full") and nodes[n.id].get_meta("full"): CombatAudio.depleted(self,str(n.kind),Vector3(n.x,0,n.z))
		nodes[n.id].set_meta("full",not spent)
		if n.kind=="tree":
			for child in nodes[n.id].get_children(): child.visible=(n.quantity<=0) if child.name=="Stump" else (n.quantity>0)
		else: nodes[n.id].visible=n.quantity>0
	var alive := []
	for enemy in run.enemies:
		alive.append(enemy.id)
		if not enemy_nodes.has(enemy.id):
			var root := preload("res://scripts/shadow_beast.gd").new()
			root.kind=enemy.get("kind","wolf")
			root.variant=enemy.get("variant","")
			root.from_enemy(enemy)
			world.add_child(root)
			root.position=Vector3(enemy.x,0,enemy.z)
			enemy_nodes[enemy.id]=root
			CombatAudio.play(self,"spawn",root.position)
			var marker := MeshInstance3D.new()
			var disk := CylinderMesh.new()
			disk.top_radius=enemy.get("impact",1.35)
			disk.bottom_radius=enemy.get("impact",1.35)
			disk.height=0.018
			disk.radial_segments=32
			marker.mesh=disk
			var danger := Art.material(Color(0.95,0.25,0.18,0.4))
			danger.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
			danger.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
			marker.material_override=danger
			world.add_child(marker)
			strike_markers[enemy.id]=marker
		var node: Node3D=enemy_nodes[enemy.id]
		node.update_snapshot(enemy,Vector3(run.x,0,run.z))
		var strike: MeshInstance3D=strike_markers[enemy.id]
		strike.visible=enemy.get("phase","")=="windup"
		strike.position=Vector3(enemy.get("target_x",enemy.x),0.04,enemy.get("target_z",enemy.z))
	for id in enemy_nodes.keys():
		if id not in alive:
			# Killed at night: the monster plays its death and frees itself. At dawn the
			# server clears the rest without a fight, so they just dissolve.
			if run.night and enemy_nodes[id].has_method("die"): enemy_nodes[id].die()
			else:
				# Not under a run's ending (the dawn of the seventh day): that is heard alone.
				if run.get("status","")=="active": CombatAudio.play(self,"dissolve",enemy_nodes[id].position)
				enemy_nodes[id].queue_free()
			enemy_nodes.erase(id)
			strike_markers[id].queue_free()
			strike_markers.erase(id)

## The sprint-start whoosh and the hero's quick exhale, on a real run-key press (_process) while the
## walker moves and has the stamina to start a sprint. Not on the server's sprinting flag: with the
## run key latched (run_mode "toggle") that turns on at every start of movement. At most one every
## SPRINT_CUE_GAP s.
func sprint_cue() -> void:
	if run.get("status","")!="active" or not world_movement_allowed() or not GameSettings.running(): return
	if movement_input().length()<0.2: return
	if not bool(run.get("sprinting",false)) and float(run.get("stamina",100.0))<=20.0: return
	var now := Time.get_ticks_msec()*0.001
	if now-sprint_cue_at<SPRINT_CUE_GAP: return
	sprint_cue_at=now
	CombatAudio.play(self,"dodge")
	HeroVoice.play(self,"dodge")

## Survival sounds that follow the run state on every update: warded beasts, hunger / cold /
## ember-ground cues, the ten-second night warning, the campfire loop and a newly crafted weapon.
func survival_audio(remaining: int) -> void:
	var active: bool=run.get("status","")=="active"
	# (The sprint-start whoosh follows the run key itself: sprint_cue().)
	# Warded: the warm campfire pushes the night's beasts back (the server's "warded" phase). One soft,
	# low shimmer at the fire for the whole group when that starts, never one per beast, and at most
	# one every WARD_CUE_GAP s (stepping in and out at the ring's edge).
	var warded := false
	if active and bool(run.get("warm",false)):
		for enemy in run.get("enemies",[]):
			if str(enemy.get("phase",""))=="warded" and Vector2(float(enemy.get("x",0.0)),float(enemy.get("z",0.0))).length()<WARD_REACH:
				warded=true
				break
	if CombatAudio.edge("warded",warded) and Time.get_ticks_msec()*0.001-ward_cue_at>=WARD_CUE_GAP:
		ward_cue_at=Time.get_ticks_msec()*0.001
		Fx.sound(self,"twinkle",Vector3.ZERO,0.8,-6.0)
	var hunger := float(run.get("hunger",100.0))
	CombatAudio.cue(self,"hunger",active and hunger<30.0,10.0 if hunger<=0.0 else 26.0)
	# Not on top of the night sting: the cold cue waits until it has rung out.
	var settling: bool=Time.get_ticks_msec()*0.001-float(CombatAudio.last_time.get("night",-10.0))<3.0
	CombatAudio.cue(self,"cold",active and bool(run.night) and not bool(run.get("warm",false)) and not settling,14.0)
	CombatAudio.cue(self,"ember",active and str(run.get("terrain_effect",""))=="ember",2.5)
	if CombatAudio.edge("night_warn",active and not bool(run.night) and remaining<=10 and remaining>0): CombatAudio.play(self,"night_warn")
	CombatAudio.campfire(self,float(run.get("fire_remaining",0.0)) if active else 0.0,Vector3.ZERO,bool(run.night))
	var weapon: String="spear" if int(run.inventory.get("spear",0))>0 else "axe" if int(run.inventory.get("axe",0))>0 else ""
	# After the crafting sound: the new weapon settles into the hero's hand.
	if CombatAudio.changed("weapon/"+run_id,weapon) and not weapon.is_empty(): CombatAudio.later(self,"equip",0.6)

func resource_response(resource: Dictionary) -> void:
	if not nodes.has(resource.id): return
	var root: Node3D=nodes[resource.id]
	var tween := root.create_tween()
	tween.tween_property(root,"rotation:z",0.045,0.07)
	tween.tween_property(root,"rotation:z",-0.025,0.06)
	tween.tween_property(root,"rotation:z",0.0,0.12)
	for i in 5:
		var chip := Art.box(world,Vector3(resource.x,0.75,resource.z),Vector3.ONE*0.08,Color("c4a26d") if resource.kind=="tree" else Color("aabc8a"))
		var scatter := chip.create_tween().set_parallel(true)
		scatter.tween_property(chip,"position",chip.position+Vector3(sin(i*2.4)*0.8,-0.65,cos(i*2.4)*0.8),0.4)
		scatter.tween_property(chip,"scale",Vector3.ZERO,0.3).set_delay(0.1)
		scatter.chain().tween_callback(chip.queue_free)

func confirm_return() -> void:
	if run.get("status","")!="active":
		leave_run()
		return
	if is_instance_valid(return_dialog): return
	# A night window like the pause menu's questions: over the pause menu (its layer and shade) when
	# asked from there, otherwise on a layer of its own over the HUD, toasts and chat (the pause
	# menu's layer), which goes with it. Esc or 계속 생존하기 keeps going.
	var host: Control
	var own_layer: CanvasLayer
	if PauseMenu.is_open() and is_instance_valid(PauseMenu.current.root): host=PauseMenu.current.root
	else:
		own_layer=CanvasLayer.new()
		own_layer.name="ReturnQuestion"
		own_layer.layer=50
		add_child(own_layer)
		host=Control.new()
		host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		host.mouse_filter=Control.MOUSE_FILTER_IGNORE
		host.theme=ui.theme
		own_layer.add_child(host)
	var w := RpgUi.window(host,tr("탐험을 마칠까요?"),{"kind":"night","width":440,"place":"centre","scroll":false,"id":"return_confirm"})
	return_dialog=w.root
	if own_layer: return_dialog.tree_exited.connect(func(): if is_instance_valid(own_layer) and not own_layer.is_queued_for_deletion(): own_layer.queue_free())
	var words := RpgUi.label(w.body,tr("지금 돌아가면 이번 도전이 끝나고 완주 보상을 받을 수 없습니다.\n")+(tr("동료의 탐험은 계속되며, 나의 완주 보상은 포기합니다.") if coop_run else (tr("현재 탐험은 일시 정지되어 있습니다.") if paused else tr("이 창을 보는 동안에도 생존 시간은 흐릅니다."))),16)
	words.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	words.custom_minimum_size.x=380
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation",RpgUi.GAP)
	w.body.add_child(row)
	var leave := RpgUi.button(row,tr("탐험을 마치고 귀환"),func():
		RpgUi.close_window(w,false)
		leave_run(),"primary","lg",true)
	var stay := RpgUi.button(row,tr("계속 생존하기"),func(): RpgUi.close_window(w),"night","lg",true)
	for b in [leave,stay]: b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	stay.grab_focus.call_deferred()

## Esc in survival: the pause menu (scripts/pause_menu.gd). Opening it sets paused
## and clears the pending action exactly as before, so tick_run sends nothing.
func toggle_pause() -> void:
	if PauseMenu.is_open():
		PauseMenu.close()
		return
	if screen!="survival" or run.get("status","")!="active": return
	PauseMenu.open(self)

func retry_run() -> void:
	var region: String=run.get("map_id","forest")
	var difficulty: String=run.get("difficulty","standard")
	# One fade for the whole retry: the village is rebuilt under the card, not shown.
	var veil := Transition.of(get_tree())
	veil.loading(region_name(region),"run",region)
	await veil.fade_out()
	await leave_run(false)
	if screen=="village": await start_run(region,difficulty)
	if veil.veil.modulate.a>0.5: veil.fade_in()

func suspend_run() -> void:
	if coop_run: return
	if busy or screen!="survival" or run.get("status","")!="active": return
	busy=true
	paused=true
	pending_action=""
	while ticking: await get_tree().process_frame
	# Each accepted input is already persisted by the server. Preserve this active run.
	run_id=""
	busy=false
	await back_to_village()
	message(tr("탐험을 저장했습니다. 하단의 이어하기로 같은 날부터 돌아갈 수 있어요."),"success")

func floating_feedback(value: String, at: Vector3, color: Color) -> void:
	var label := Label3D.new()
	label.text=I18n.server(value)
	label.font=RpgUi.FONT_BOLD
	label.font_size=34
	label.pixel_size=0.007
	label.position=at+Vector3(0,2.1,0)
	label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate=color
	label.outline_size=12
	label.outline_modulate=Color(0.12,0.08,0.04,0.9)
	label.no_depth_test=true
	world.add_child(label)
	var tween := label.create_tween().set_parallel(true)
	tween.tween_property(label,"position:y",label.position.y+0.85,1)
	tween.tween_property(label,"modulate:a",0.0,0.5).set_delay(0.5)
	tween.chain().tween_callback(label.queue_free)

func attack_sweep() -> void:
	var mesh := ImmediateMesh.new()
	mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP)
	for i in 13:
		var angle := -0.85+i*1.7/12
		for radius in [1.3,1.47]: mesh.surface_add_vertex(Vector3(sin(angle)*radius,0,-cos(angle)*radius))
	mesh.surface_end()
	var arc := MeshInstance3D.new()
	arc.mesh=mesh
	arc.position=player.position+Vector3(0,0.8,0)
	arc.rotation.y=atan2(-player.facing.x,-player.facing.z)
	var mat := Art.material(Color("efe4b4"))
	mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.cull_mode=BaseMaterial3D.CULL_DISABLED
	mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	arc.material_override=mat
	world.add_child(arc)
	var tween := arc.create_tween()
	tween.tween_property(mat,"albedo_color:a",0,0.23)
	tween.tween_callback(arc.queue_free)

func show_results() -> void:
	paused=false
	if is_instance_valid(pause_shade): pause_shade.queue_free()
	var shade := ColorRect.new()
	shade.color=Color(0.03,0.06,0.07,0.68)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.add_child(shade)
	var won: bool=run.status=="won"
	var card := panel(Vector2(400,150),480,"hero")
	RpgUi.pin(card.get_parent(),0.5,0.0)
	RpgUi.pop_in(card.get_parent(),0.32,0.9)
	# The run's ending is already heard (update_run: the level-up chime and then core/win, or the faint
	# with core/lose), so the card pops in silently; only without those takes does it chime itself.
	if not SfxBank.has("core/win" if won else "core/lose"): RpgUi.sfx("confirm" if won else "close",-6.0)
	var band := RpgUi.ribbon(card,tr("탐험 성공") if won else tr("다시 피울 작은 불씨"),not won,24)
	band.size_flags_horizontal=Control.SIZE_SHRINK_CENTER
	var destination := "%s · %s" % [region_name(run.get("map_id","forest")),difficulty_name(run.get("difficulty","standard"))]
	if preload("res://scripts/build_mode.gd").developer(): destination += tr(" · 보상 ×%.3f") % run.get("reward_multiplier",1.0)
	var where := RpgUi.caption(card,destination,14)
	where.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	RpgUi.divider(card)
	var stats := text(card,tr("생존  %d일     채집  %d회     처치  %d") % [run.day,run.get("harvested",0),run.get("kills",0)],17)
	stats.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	RpgUi.numbers(stats,17)
	if won:
		var prize := HBoxContainer.new()
		prize.alignment=BoxContainer.ALIGNMENT_CENTER
		prize.add_theme_constant_override("separation",10)
		card.add_child(prize)
		prize.add_child(RpgUi.icon("res://assets/starseed.svg",40))
		var reward_text := RpgUi.heading(prize,tr("보상  %d 별씨") % run.get("reward",0),28,Color("8a5a1c"))
		reward_text.size_flags_vertical=Control.SIZE_SHRINK_CENTER
	else:
		var later := RpgUi.caption(card,tr("완주 보상은 7일 생존 후 받을 수 있어요."),14)
		later.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	if run.get("story") is Dictionary:
		var story_text := tr("목표가 남아 있어 이야기는 다음 도전에서 이어집니다.")
		if run.story.objectives_met:story_text=run.story.ending+tr("\n첫 완료 보너스 %d 별씨")%int(run.get("story_bonus",0))
		var story_note := text(card,story_text,14);story_note.custom_minimum_size.x=420;story_note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	if not won:
		var lesson := tr("밤에는 목재 2개를 남기고 야영지의 불을 지키세요.")
		if run.get("hunger",100)<1: lesson=tr("열매와 수프를 비축하고, 포만감이 떨어지면 Q로 먹으세요.")
		elif run.get("fire_remaining",0)>0: lesson=tr("모닥불의 금색 원 안으로 돌아오거나, 붉은 공격 예고를 피하세요.")
		var advice := RpgUi.caption(card,lesson,13,RpgUi.ACCENT)
		advice.custom_minimum_size.x=420
		advice.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	RpgUi.divider(card)
	button(card,tr("보상 받고 마을로") if won else tr("마을로 돌아가기"),leave_run,"gold" if won else "primary")
	if not won and not coop_run: button(card,tr("새 탐험으로 다시 도전"),retry_run)

## Back from an expedition: the village is rebuilt under the loading card.
func back_to_village(fade := true) -> void:
	var veil := Transition.of(get_tree())
	if fade:
		veil.loading(tr("다섯 섬 마을"),"","village")
		await veil.fade_out()
	await enter_village()
	if fade: veil.fade_in()

func leave_run(fade := true) -> void:
	if busy: return
	CombatAudio.heartbeat(self,0.0)
	VoiceBabble.stop()
	busy=true
	while ticking: await get_tree().process_frame
	if run.status=="won" and not run.claimed:
		var result: Dictionary = await api.post(run_route()+"/claim",api.mutation())
		if not result.ok and coop_run:
			var current: Dictionary = await api.request(run_route())
			if current.ok and current.data.get("claimed", false): result = {"ok":true}
		if not check(result):
			busy=false
			return
	elif run.status=="active":
		var result: Dictionary = await api.post(run_route()+"/abandon",api.mutation())
		if not check(result):
			busy=false
			return
	busy=false
	run_id=""
	await back_to_village(fade)

func logout() -> void:
	if busy: return
	preload("res://scripts/build_mode.gd").admin = false
	busy=true
	screen="logging_out"
	world_epoch+=1
	var veil := Transition.of(get_tree())
	veil.loading("", "start")
	await veil.fade_out()
	await api.post("/v1/auth/logout",{})
	CraftTracker.end(api)
	SocialHud.end(api)
	api.token=""
	social.reset_session()
	job_id=""
	await build_world(false)
	login_ui()
	busy=false
	veil.fade_in()

## Maintenance began or the server ended this session (version_gate.gd): back to the title at once.
## No logout call (the server is closed or forgot the session); progress is already on the server,
## and an active expedition waits under "이어하기" after the next sign-in.
func force_logout(reason: String) -> void:
	if api.token.is_empty() or screen=="logging_out": return
	CraftTracker.end(api)
	SocialHud.end(api)
	api.token=""
	screen="logging_out"
	world_epoch+=1
	busy=true
	paused=true
	pending_action=""
	run_id=""
	coop_run=false
	job_id=""
	preload("res://scripts/build_mode.gd").admin = false
	PauseMenu.close()
	CombatAudio.heartbeat(self,0.0)
	VoiceBabble.stop()
	var cloud := get_node_or_null("/root/CloudPrefs")
	if cloud: cloud.stop()
	social.reset_session()
	print("[Villagen] logged out: ", reason)
	var veil := Transition.of(get_tree())
	veil.loading("", "start")
	await veil.fade_out()
	await build_world(false)
	busy=false
	login_ui()
	veil.fade_in()

func _exit_tree() -> void:
	SocialHud.release_place(self)
	GameSettings.unlisten(settings_changed)
	# A pending studio session means the map is only travelling to a room and back.
	if not Engine.has_meta("studio_session"): TownLayout.discard_kept()

func settings_changed(keys: Array) -> void:
	if "shadows" in keys or "preset" in keys: apply_graphics()

## Footsteps follow the ground under the walker (bridges and floors are wood,
## paths gravel, beaches sand, the water's edge shallow) and its pace; the
## ambience beds follow time of day, the sea, the waterfall and the screen.
func update_world_audio(delta: float) -> void:
	if not is_instance_valid(world_audio) or not is_instance_valid(player): return
	ambience_elapsed+=delta
	if ambience_elapsed>0.5:
		ambience_elapsed=0.0
		var day := 1.0
		if is_instance_valid(daylight) and daylight.has_method("current_hour"):
			day=float(Daylight.sample(daylight.current_hour()).get("daylight",1.0))
		# set_ambience keeps any key it is not given: every screen sets zone, room and ember.
		if screen=="village":
			sound.play_music(village_track())
			var waterfall := clampf(1.0-Vector2(player.position.x-1.0,player.position.z+7.9).length()/24.0,0.0,1.0)
			# The hour lets the rooster crow only at dawn; the windmill (town.gd 04_windmill) creaks from where it stands.
			var hour: float=float(daylight.current_hour()) if is_instance_valid(daylight) and daylight.has_method("current_hour") else -1.0
			world_audio.set_ambience({"day":day,"coast":clampf((2.6-player.position.y)/1.7,0.15,1.0),"wind":0.2+0.25*(1.0-day),"waterfall":waterfall,"indoor":false,
				"zone":"","room":"","ember":0.0,"hour":hour,"windmill_at":Vector3(-18.0,0.0,-44.0)})
		elif screen=="survival":
			# Each region its own bed (forest canopy, frost wind and ice, quarry dry wind and pebbles);
			# the ember roar fades in while the walker stands on the hot cracks.
			world_audio.set_ambience({"day":0.0 if run.get("night",false) else 1.0,"coast":0.0,"wind":0.3,"waterfall":0.0,"indoor":false,
				"room":"","hour":-1.0,"zone":str(run.get("map_id","forest")),"ember":1.0 if run.get("terrain_effect","")=="ember" else 0.0})
		else:
			world_audio.set_ambience({"day":day,"coast":0.45,"wind":0.15,"waterfall":0.0,"indoor":false,"zone":"","room":"","ember":0.0})
	if screen not in ["village","survival"]:
		last_step_at=player.position
		was_airborne=false
		fall_speed=0.0
		was_wading=false
		return
	var moved := Vector2(player.position.x-last_step_at.x,player.position.z-last_step_at.z).length()
	# Put back on the shore after going under in the sea (player.gd min_ground_y reset): a splash.
	# Falling in, or walked down to the reset line (a warp while wading higher up is no splash).
	if screen=="village" and moved>1.5:
		var sea_floor_value = player.get("min_ground_y")
		var sea_floor: float=float(sea_floor_value) if sea_floor_value!=null else -INF
		if last_step_at.y<sea_floor+(0.6 if was_airborne else 0.2): world_audio.splash(1.0)
	last_step_at=player.position
	if moved>1.5 or delta<=0.0:
		# A teleport or a warp is no fall.
		was_airborne=false
		fall_speed=0.0
		return
	if screen=="village":
		# A landing after a drop (a ledge, a bridge's edge): a thud scaled by the fall. Seated or
		# carried (visual_only) the body is not falling.
		var airborne: bool=not player.is_on_floor() and not bool(player.get("visual_only"))
		if airborne: fall_speed=maxf(fall_speed,-player.velocity.y)
		elif was_airborne and fall_speed>4.0: world_audio.land(fall_speed,ground_surface())
		if not airborne: fall_speed=0.0
		was_airborne=airborne
		# Stepping into the shallows: a splash (a little hysteresis and a gap, so walking along the
		# waterline does not splash on every step).
		var wading: bool=not airborne and player.position.y<(0.85 if was_wading else 0.75)
		if wading and not was_wading and Time.get_ticks_msec()-wade_splash_at>1500:
			wade_splash_at=Time.get_ticks_msec()
			world_audio.splash(0.5)
		was_wading=wading
	var speed := moved/delta
	if speed<0.4 or (screen=="village" and not player.is_on_floor()):
		step_distance=0.0
		return
	step_distance+=moved
	if step_distance>=(0.98 if speed>3.6 else 0.74):
		step_distance=0.0
		world_audio.footstep(ground_surface() if screen=="village" else survival_surface(),speed)

## Village music follows the hour: the night track once the light is mostly gone, the day
## track again after dawn (the gap between the two thresholds stops it flipping at dusk).
func village_track() -> String:
	var day := 1.0
	if is_instance_valid(daylight) and daylight.has_method("current_hour"):
		day=float(Daylight.sample(daylight.current_hour()).get("daylight",1.0))
	if sound.music_mode=="village_night" and day<0.5: return "village_night"
	return "village_night" if day<0.3 else "village_day"

## Each expedition region has its own track; 노을 채석장 borrows the forest's for now.
func region_track() -> String:
	var region: String=run.get("map_id","forest")
	return region if region in ["forest","frost"] else "forest"

## Survival ground by region and by the hazard underfoot: snow (ice on the frozen patches) in the
## frost basin, gravel (ash on the hot cracks) in the quarry, leaf litter in the forest.
func survival_surface() -> String:
	var effect := str(run.get("terrain_effect",""))
	if effect=="ice": return "ice"
	if effect=="ember": return "ash"
	return region_surface()

## The region's own ground, without the hazards (other players' steps on an expedition).
func region_surface() -> String:
	return str({"frost":"snow","quarry":"gravel"}.get(str(run.get("map_id","forest")),"leaves"))

func ground_surface() -> String:
	var from := player.global_position+Vector3(0,0.6,0)
	var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(from,from+Vector3(0,-1.6,0),1|2))
	if not hit.is_empty() and hit.collider is CollisionObject3D:
		if hit.collider.collision_layer&2: return "wood"
		var owner_name := str(hit.collider.get_parent().name) if hit.collider.get_parent() else ""
		if "rock" in owner_name.to_lower(): return "rock"
	# Tilled farm plots are soft soil.
	var farm = life.get("farm") if is_instance_valid(life) else null
	if is_instance_valid(farm) and farm.has_method("index_at") and farm.index_at(Vector2(player.position.x,player.position.z),0.95)>=0: return "dirt"
	if Roads.on_road(Vector2(player.position.x,player.position.z)): return "stone"
	if player.position.y<0.8: return "shallow"
	if player.position.y<1.55: return "sand"
	return "grass"

## The HUD medallion shows the player's own character as it is dressed: the same walker drawn
## from the head (avatar_portrait.gd). Until that first drawing is ready, the authored picture of
## the same character stands in.
func show_portrait() -> void:
	if not frame.has("portrait") or not is_instance_valid(frame.portrait): return
	var profile: Dictionary = me.get("profile",{})
	var look := AvatarLook.normalize(profile.get("avatar",{}))
	if not is_instance_valid(portrait_view):
		portrait_view = preload("res://scripts/avatar_portrait.gd").new()
		add_child(portrait_view)
		portrait_view.rendered.connect(func():
			if frame.has("portrait") and is_instance_valid(frame.portrait): frame.portrait.texture=portrait_view.get_texture())
	# A face already drawn stays up while a new look is drawn over it (no flash of another picture).
	if not portrait_view.drawn_key.is_empty():
		frame.portrait.texture=portrait_view.get_texture()
	else:
		var path := "res://assets/ui/portrait_%s.png" % str(look.character)
		if ResourceLoader.exists(path): frame.portrait.texture=load(path)
	portrait_view.show_look(look,int(profile.get("version",-1)))

## Puts the saved look (me.profile) on the walker and the HUD medallion.
func wear_profile(animate := false) -> void:
	var profile: Dictionary = me.get("profile",{})
	if is_instance_valid(player): AvatarLook.wear(player,profile.get("avatar",{}),int(profile.get("version",-1)),animate)
	show_portrait()

## A newer saved look from elsewhere (the wardrobe, this account's own presence record): every
## place this client draws the player follows it.
func adopt_profile(profile: Dictionary, animate := false) -> void:
	if not profile.get("avatar") is Dictionary: return
	if int(profile.get("version",-1))<=int(me.get("profile",{}).get("version",-1)): return
	me.profile={"avatar":profile.avatar.duplicate(true),"version":int(profile.get("version",0))}
	wear_profile(animate)

## Village distance on the ground plane; island terrain heights vary by metres.
func near(at: Vector2, radius: float) -> bool:
	return is_instance_valid(player) and Vector2(player.position.x,player.position.z).distance_to(at)<radius

func follow_camera(delta: float) -> void:
	if not is_instance_valid(player) or warming: return
	if is_instance_valid(ambience) and screen=="village": ambience.position=player.position+Vector3(0,1.6,0)
	# The walker's drawn position, between physics ticks, so the view glides with it.
	var target: Vector3=(player.render_position() if player.has_method("render_position") else player.position)+ControllerProfile.CAMERA_FOCUS_OFFSET
	if not camera_focus_ready or delta>=1.0:
		camera_focus=target;camera_focus_ready=true
	else: camera_focus=camera_focus.lerp(target,ControllerProfile.damping(ControllerProfile.CAMERA_RESPONSE,delta))
	# One smoothed focus and a fixed offset keep pitch constant during movement.
	# Independently smoothing position made the view nod on starts and stops.
	camera.position=camera_focus+ControllerProfile.CAMERA_OFFSET*ControllerProfile.CAMERA_PULLBACK
	camera.look_at(camera_focus)
	if camera_zoom_active:
		camera.size=lerpf(camera.size,camera_zoom_target,ControllerProfile.damping(10.0,delta))
		if absf(camera.size-camera_zoom_target)<.005:
			camera.size=camera_zoom_target;camera_zoom_active=false

func text_input_active() -> bool:
	var focus := get_viewport().gui_get_focus_owner()
	return focus is LineEdit or focus is TextEdit

func world_movement_allowed() -> bool:
	if PauseMenu.is_open() or VersionGate.is_blocked(): return false
	if is_instance_valid(painter) or is_instance_valid(interaction_panel): return false
	if busy or text_input_active() or is_instance_valid(village_modal) or is_instance_valid(preview) or is_instance_valid(return_dialog):return false
	if is_instance_valid(right) and right.get_parent().visible:return false
	if screen=="village":return true
	return screen=="survival" and not paused and not results_shown and network_failures==0 and run.get("status","")=="active" and run.get("hp", 0)>0

func movement_input() -> Vector2:
	return Input.get_vector("move_left","move_right","move_forward","move_back") if world_movement_allowed() else Vector2.ZERO

func _process(delta: float) -> void:
	follow_camera(delta)
	update_world_audio(delta)
	if is_instance_valid(developer_label) and is_instance_valid(developer_panel) and developer_panel.visible:
		developer_label.text=tr("개발 화면 · F3 닫기\nFPS %d  |  %s\n위치 %.1f, %.1f\n서버 %s\nTripo %s") % [Engine.get_frames_per_second(),screen,player.position.x,player.position.z,api.base_url,tr("사용 가능") if me.get("studio_tripo_enabled",false) else tr("비활성")]
		developer_label.text+=tr("\n이동 %.2f m/s · 시야 %.1f\n입력 %s") % [player.locomotion_velocity.length(),camera.size,tr("허용") if world_movement_allowed() else tr("잠금")]
		if is_instance_valid(player.locomotion_pose):developer_label.text+=tr("\n보행 주기 %.2f초 · 접지 오차 %.1fcm") % [player.locomotion_pose.cycle_seconds,player.locomotion_pose.contact_error*100.0]
	canopy_elapsed+=delta
	if canopy_elapsed>0.08:
		canopy_elapsed=0
		update_canopy_visibility()
	if is_instance_valid(inspect_model) and is_instance_valid(inspect_panel) and inspect_panel.visible:
		inspect_model.rotation.y+=delta*0.35
	if is_instance_valid(flame) and flame.visible:
		flame.scale=Vector3(1.0+sin(Time.get_ticks_msec()*0.011)*0.07,1.0+sin(Time.get_ticks_msec()*0.015)*0.12,1.0)
	if screen=="survival":
		player.sprinting=run.get("sprinting",false)
		if Input.is_action_just_pressed("run"): sprint_cue()
		repeat_action+=delta
		if repeat_action>=0.43 and world_movement_allowed():
			repeat_action=0
			if Input.is_action_pressed("attack"): intent("attack")
			elif Input.is_action_pressed("interact"): intent("harvest")
		var previous_position: Vector3=player.position
		player.position=predict_walker(delta)
		# The walker faces where the player steers; a server correction folding in only slides it.
		var steer := movement_input()
		var moved := Vector2(player.position.x-previous_position.x,player.position.z-previous_position.z)/maxf(delta,.001)
		player.external_velocity=moved if steer.length()>0.1 else Vector2.ZERO
		player.external_motion=steer.normalized() if steer.length()>0.1 else Vector2.ZERO
		if paused or results_shown or network_failures>0:player.external_velocity=Vector2.ZERO
		tick_elapsed+=delta
		if tick_elapsed>=(0.2 if coop_run else 0.1):
			tick_elapsed=0
			tick_run()
		var night: bool=run.get("night",false)
		# The rebuilt survival maps grade their own day and night (maps/survival/survival_map.gd).
		if not world.has_node("SurvivalMap"):
			environment.ambient_light_energy=lerpf(environment.ambient_light_energy,0.25 if night else 0.35,delta*1.2)
			environment.ambient_light_color=environment.ambient_light_color.lerp(Color("788fab") if night else Color.WHITE,delta)
			sun.light_energy=lerpf(sun.light_energy,0.22 if night else 0.25,delta*1.2)
			sun.light_color=sun.light_color.lerp(Color("7fa9cf") if night else Color("fff5e9"),delta)
			environment.background_color=environment.background_color.lerp(Color("233b50") if night else Color("88bcb9"),delta)
		update_harvest_hint()
	elif screen=="village":
		player.sprinting=world_movement_allowed() and GameSettings.running()
		if is_instance_valid(objective):
			var placed := 0
			for obj in me.get("objects",[]):
				if obj.state=="placed": placed+=1
			if is_instance_valid(preview): objective.text=tr("나만의 자리 찾기\n바닥을 클릭하면 배치돼요.\nR · 회전    Esc · 취소")
			elif me.get("active_run_summary") is Dictionary: objective.text=tr("돌아갈 탐험이 있어요\n%d일째 · 체력 %d\n하단의 이어하기 또는 돌문 앞 E\n\n마을에서는 생존 시간이 멈춥니다.") % [me.active_run_summary.day,me.active_run_summary.hp]
			elif placed==0: objective.text=tr("첫 번째 마을 꾸미기\nI로 보관함을 열어 색을 고르고,\n환영의 의자를 놓아 보세요.")
			else: objective.text=tr("나의 마을 · 물건 %d개 배치\n숲에서 7일을 살아남으면\n새 물건을 만들 별씨를 받아요.\n\n돌문 앞에서 E · 탐험 시작") % placed
			if not is_instance_valid(preview) and (not life.goal.is_empty() or not me.get("active_run_summary") is Dictionary): objective.text=life.goal_text()
			# The opening story chapter's lines come first while it runs (story.gd).
			var story := chapter()
			if story and not is_instance_valid(preview): objective.text=story.objective(objective.text)
		if not is_instance_valid(preview):
			player.controls_enabled=world_movement_allowed()
			# The E prompt scans doors, villagers, add-ons and ~600 props; ten times a
			# second is plenty and keeps the frame free.
			prompt_wait-=delta
			if is_instance_valid(hint) and prompt_wait<=0.0:
				prompt_wait=0.1
				var npc := nearest_npc()
				var activity: Dictionary=life.closest()
				var module_entry := module_closest()
				var prop: Dictionary=town.nearest_prop(Vector2(player.position.x,player.position.z))
				var prompt_text := ""
				# The interact key as bound (E, or G after a rebind) leads the chip as a key cap.
				var key := RpgUi.key_text("interact")+"  "
				if not activity.is_empty() and social.visiting() and activity.get("id","")=="home": prompt_text=key+tr("%s님의 집 들어가기") % str(social.data.get("host_name",tr("친구")))
				elif not activity.is_empty() and activity.has("prompt"): prompt_text=key+activity.prompt
				elif not activity.is_empty(): prompt_text=key+tr(activity.title)
				elif npc: prompt_text=key+I18n.talk_to(tr(npc.get_meta("title")))
				elif not module_entry.is_empty(): prompt_text=key+str(module_entry.get("prompt",""))
				elif not prop.is_empty(): prompt_text=key+town.prop_prompt(prop)
				elif near(TownLayout.GATE,3): prompt_text=key+tr("탐험 떠나기")
				elif near(TownLayout.HOME_DOOR,2): prompt_text=key+tr("나의 집 들어가기")
				elif near(TownLayout.WORKSHOP_DOOR,2.5): prompt_text=key+tr("별씨 공방 들어가기")
				elif not nearest_furniture().is_empty(): prompt_text=key+{"sit":tr("앉기"),"lie":tr("눕기")}.get(str(loaded[nearest_furniture()].get("rest")),tr("가구 사용하기"))
				if is_instance_valid(seat) and seat.resting(): prompt_text=key+tr("일어나기")
				if is_instance_valid(village_modal): prompt_text=""
				if str(hint.get_meta("prompt",""))!=prompt_text:
					# The chip ticks very softly as it appears (RpgUi.prompt, every place alike).
					RpgUi.set_prompt(hint,prompt_text)
					fit_chip(hint)
				hint.visible=not prompt_text.is_empty() and GameSettings.show_prompts()
			if is_instance_valid(minimap): minimap.follow(Vector2(player.position.x,player.position.z),-player.visual.rotation.y)
			if frame.has("leaves") and is_instance_valid(frame.leaves) and life.state.has("coins"): RpgUi.count_to(frame.leaves,int(life.state.coins))
		entitlement_elapsed+=delta
		furniture_proximity_time+=delta
		if furniture_proximity_time>.5:furniture_proximity_time=0;village_furniture_proximity()
		if entitlement_elapsed>3:
			entitlement_elapsed=0
			poll_entitlements()
		if not job_id.is_empty():
			poll_elapsed+=delta
			if poll_elapsed>2:
				poll_elapsed=0
				poll_job()
		if is_instance_valid(preview):
			var mouse := get_viewport().get_mouse_position()
			# A picked-up object stays put (to turn it in place) until the pointer moves.
			if not preview_follow and mouse.distance_to(preview_mouse)>8: preview_follow=true
			var origin := camera.project_ray_origin(mouse)
			var hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(origin,origin+camera.project_ray_normal(mouse)*400,1|2|8)) if preview_follow else {}
			# A new piece's ghost has no spot of its own until the pointer first puts it on the ground:
			# that frame (and the ones before it) stay silent, it only takes its colour.
			var first_spot := not preview.has_meta("ghost_spot")
			# Only open ground takes furniture; buildings, bridges and props keep the last spot.
			if not hit.is_empty() and hit.collider is CollisionObject3D and hit.collider.collision_layer&1:
				var local := TownLayout.furniture_local(hit.position).snapped(Vector2(0.5,0.5))
				var cell := TownLayout.furniture_point(local.x,local.y)
				# A faint tick when the ghost lands on a new 0.5 m cell (at most ~11 a second).
				if not first_spot and not preview.position.is_equal_approx(cell) and Time.get_ticks_msec()-snap_tick_at>90:
					snap_tick_at=Time.get_ticks_msec()
					RpgUi.sfx("snap",-15.0)
				preview.position=cell
				preview.set_meta("ghost_spot",true)
			preview.rotation.y=ObjectTransform.ease_yaw(preview.rotation.y,preview_rotation,delta)
			var disc := preview.get_node_or_null("PlacementDisc") as MeshInstance3D
			if disc:
				var free := placement_problem().is_empty()
				# Heard only when the spot flips between free (green) and blocked (red).
				if bool(disc.get_meta("free",free))!=free and not first_spot and Time.get_ticks_msec()-flip_tick_at>150:
					flip_tick_at=Time.get_ticks_msec()
					RpgUi.sfx("valid" if free else "invalid",-11.0)
				disc.set_meta("free",free)
				disc.material_override.albedo_color=Color(.4,.9,.5,.45) if free else Color(.95,.35,.3,.5)

func update_canopy_visibility() -> void:
	if not is_instance_valid(player): return
	for group in ["npc_nameplates","place_nameplates"]:
		for label in get_tree().get_nodes_in_group(group):
			if world.is_ancestor_of(label):label.visible=player.position.distance_to(label.global_position)<(6.0 if group=="npc_nameplates" else 9.0)
	var hero_screen := camera.unproject_position(player.position+Vector3(0,1,0))
	var radius := 720.0/camera.size
	for canopy in get_tree().get_nodes_in_group("canopy"):
		if not world.is_ancestor_of(canopy): continue
		var point: Vector3=canopy.global_transform*canopy.get_aabb().get_center()
		canopy.rotation.x=sin(Time.get_ticks_msec()*0.0012+point.x)*0.008
		canopy.rotation.z=sin(Time.get_ticks_msec()*0.0009+point.z)*0.008
		var obscures: bool=point.z>player.position.z-0.7 and point.z<player.position.z+5 and camera.unproject_position(point).distance_to(hero_screen)<radius*1.65
		var mat: StandardMaterial3D=canopy.material_override
		var color := mat.albedo_color
		color.a=lerpf(color.a,0.2 if obscures else 1.0,0.45)
		mat.albedo_color=color
		mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS if color.a<0.99 else BaseMaterial3D.TRANSPARENCY_DISABLED

func update_harvest_hint() -> void:
	if not is_instance_valid(hint): return
	var closest := 2.3
	var selected_node: Dictionary={}
	for n in run.get("nodes",[]):
		var distance := Vector2(run.x-n.x,run.z-n.z).length()
		if n.quantity>0 and distance<closest:
			closest=distance
			selected_node=n
	harvest_marker.visible=not selected_node.is_empty() and run.status=="active"
	# The prompt chip names only what the interact key does here (its key from the bindings);
	# away from anything to gather it steps back, as in the village.
	var value := ""
	if harvest_marker.visible:
		harvest_marker.position=Vector3(selected_node.x,0.1,selected_node.z)
		var names := {"tree":tr("나무"),"stone":tr("돌"),"berry":tr("열매"),"fiber":tr("풀")}
		value=RpgUi.key_text("interact")+"  "+tr("%s 채집 (남은 자원 %d)") % [names[selected_node.kind],selected_node.quantity]
	if str(hint.get_meta("prompt",""))!=value:
		RpgUi.set_prompt(hint,value)
		fit_chip(hint)
	hint.visible=not value.is_empty() and GameSettings.show_prompts()

func _unhandled_input(event: InputEvent) -> void:
	# Rebinding-aware: a key bound to an action reports that action's default key
	# (Interact moved to G -> KEY_E); Esc, Enter, F-keys and digits report themselves.
	var key := GameSettings.canonical_key(event)
	var press: bool = event is InputEventKey and event.pressed and not event.echo
	# The return question over survival: Esc keeps surviving; nothing behind it reacts meanwhile.
	if is_instance_valid(return_dialog):
		if press and key==KEY_ESCAPE: RpgUi.close_top(return_dialog.get_meta("rpg_window",{}))
		if event is InputEventKey or event is InputEventMouseButton: get_viewport().set_input_as_handled()
		return
	if is_instance_valid(village_modal):
		if press and key==KEY_E and life.mode=="fish":
			life.reel()
			return
		# A conversation: E, Space and Enter show the rest of the line, then the next page.
		if press and village_modal.has_meta("advance") and key in [KEY_E,KEY_SPACE,KEY_ENTER,KEY_KP_ENTER]:
			village_modal.get_meta("advance").call()
			get_viewport().set_input_as_handled()
			return
		if event is InputEventKey and event.pressed and key==KEY_ESCAPE:
			close_village_modal()
			return
		# The key that opened a window closes it (C craft, Tab map, B storage, O wardrobe).
		if press and not text_input_active() and RpgUi.closes_window(modal_window(village_modal),key):
			close_village_modal()
			get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo and key in [KEY_ESCAPE,KEY_E] and screen=="village" and is_instance_valid(seat) and seat.resting():
		# The fallback stands up at once (the driver voices its own getting up).
		if not str(seat.legacy_mode).is_empty(): seat_sound("rise",{"at":player.global_position,"material":"wood"})
		seat.stand()
		return
	if event is InputEventKey and event.pressed and not event.echo and key==KEY_ESCAPE and screen in ["village","survival"]:
		# Esc backs out of placement, then a side drawer on the window stack, then the bag, then
		# opens the pause menu.
		var top := RpgUi.top_window()
		if screen=="village" and is_instance_valid(preview):
			RpgUi.sfx("cancel",-8.0)
			cancel_preview()
		elif not top.is_empty() and not bool(top.get("modal",false)) and RpgUi.close_top(top): pass
		elif is_instance_valid(right) and right.get_parent().visible: toggle_drawer()
		elif screen=="survival": toggle_pause()
		else: PauseMenu.open(self)
		return
	if paused: return
	if text_input_active():return
	# Placing: R turns 15° (Shift back, Alt/Ctrl a single degree; held keys repeat), the wheel 5°.
	if screen=="village" and is_instance_valid(preview):
		if event is InputEventKey and event.pressed and key==KEY_R:
			turn_preview(ObjectTransform.key_turn(event))
			get_viewport().set_input_as_handled()
			return
		if event is InputEventMouseButton and event.pressed and ObjectTransform.wheel_turn(event)!=0:
			turn_preview(ObjectTransform.wheel_turn(event))
			get_viewport().set_input_as_handled()
			return
	if screen in ["village","survival"] and event is InputEventMouseButton and event.pressed:
		if event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
			if not camera_zoom_active:camera_zoom_target=camera.size
			var village := screen=="village"
			camera_zoom_target=clampf(camera_zoom_target+GameSettings.zoom_step(event.button_index),ControllerProfile.VILLAGE_CAMERA_MIN if village else ControllerProfile.CAMERA_MIN,ControllerProfile.VILLAGE_CAMERA_MAX if village else ControllerProfile.CAMERA_MAX)
			camera_zoom_active=true
	if event is InputEventKey and event.pressed and not event.echo:
		if key==KEY_F3 and is_instance_valid(developer_panel):
			developer_panel.visible=not developer_panel.visible
			return
		if key==KEY_M:
			sound.toggle()
			message(tr("소리를 껐습니다. M으로 다시 켤 수 있습니다.") if sound.muted else tr("소리를 켰습니다."))
		# HUD key (U): fold every HUD panel at once, or open them all again.
		if screen in ["village","survival"] and key==KEY_U:
			RpgUi.toggle_all_folds()
			return
		if screen in ["village","survival"] and key==KEY_I:
			toggle_drawer()
			return
		# C opens the craft window over the bag too (as in rooms, where the bag is a drawer as well).
		if screen=="village" and key==KEY_C and not is_instance_valid(village_modal):
			open_craft()
			return
		if is_instance_valid(right) and right.get_parent().visible:return
		if screen=="survival":
			match key:
				KEY_E: intent("harvest")
				KEY_Q: intent("eat")
				KEY_F: intent("fire")
				KEY_H: intent("heal")
				KEY_SPACE: intent("attack")
		elif screen=="village":
			if key==KEY_TAB: life.open_map()
			if key==KEY_B: life.open_storage()
			if key==KEY_F9 and preload("res://scripts/build_mode.gd").admin: open_admin()
			if key==KEY_O and not is_instance_valid(village_modal): open_wardrobe()
			if key==KEY_E and not life.closest().is_empty(): life.interact()
			elif key==KEY_E and nearest_npc(): talk_after_turn(nearest_npc())
			elif key==KEY_E and not module_closest().is_empty(): use_module(module_closest())
			elif key==KEY_E and is_instance_valid(town) and not town.nearest_prop(Vector2(player.position.x,player.position.z)).is_empty(): town.use_prop(self,town.nearest_prop(Vector2(player.position.x,player.position.z)))
			elif key==KEY_E and near(TownLayout.GATE,3): open_expedition()
			elif key==KEY_E and near(TownLayout.HOME_DOOR,2): open_studio("home")
			elif key==KEY_E and near(TownLayout.WORKSHOP_DOOR,2.5): open_studio()
			elif key==KEY_E: village_furniture_event(nearest_furniture(),"click")
	if screen=="village" and event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT:
		if is_instance_valid(preview): place_preview()
		else: click_furniture(event.position)

func region_name(id: String) -> String:
	var known: Dictionary={"forest":tr("솔바람 숲"),"quarry":tr("노을 채석장"),"frost":tr("서리빛 분지")}
	# A map the catalog names (the tutorial, a renamed region) goes by that name.
	for region in me.get("catalog",{}).get("maps",[]):
		if region is Dictionary and str(region.get("id",""))==id and not str(region.get("name","")).is_empty(): return str(region.name)
	return known.get(id,id)

## The expedition's progress line: "스테이지 2/5  1:30" on staged maps (∞ on the boss night),
## the seven-day dots on a server without stages.
func stage_text() -> String:
	if run.has("stage"):
		var left := int(run.get("stage_remaining",-1))
		var clock := "∞" if left<0 or bool(run.get("boss_night",false)) else "%d:%02d" % [left/60,left%60]
		return tr("스테이지 %d/%d") % [int(run.stage),int(run.get("stage_count",1))]+"   "+clock
	var days := ""
	for i in 7: days+=("● " if i<int(run.get("day",1)) else "○ ")
	return "DAY %02d   %s" % [int(run.get("day",1)),days.strip_edges()]

## The boss's health under the stage tracker while run.boss is set: it shakes and flashes when hit,
## and the toast lane steps down under it.
func update_boss_bar() -> void:
	var boss = run.get("boss")
	if not boss is Dictionary or screen!="survival":
		if is_instance_valid(boss_panel):
			boss_panel.queue_free()
			if is_instance_valid(toast_lane): toast_lane.position.y-=48
		boss_panel=null
		boss_last_hp=-1.0
		return
	var hp := float(boss.get("hp",0.0))
	var top := maxf(1.0,float(boss.get("max_hp",1.0)))
	if not is_instance_valid(boss_panel):
		var plate := PanelContainer.new()
		plate.name="BossBar"
		plate.add_theme_stylebox_override("panel",RpgUi.panel_style("pill"))
		plate.mouse_filter=Control.MOUSE_FILTER_IGNORE
		plate.position=Vector2(400,66+(28 if is_instance_valid(ui.get_node_or_null("CoopLine")) else 0))
		plate.custom_minimum_size=Vector2(480,0)
		ui.add_child(plate)
		boss_meter=RpgUi.meter(plate,str(boss.get("name",tr("우두머리"))),RpgUi.ACCENT,"crown")
		(boss_meter.bar as ProgressBar).custom_minimum_size.y=16
		(boss_meter.name as Label).add_theme_color_override("font_color",RpgUi.GOLD)
		(boss_meter.name as Label).add_theme_font_size_override("font_size",15)
		plate.size=Vector2(480,plate.get_combined_minimum_size().y)
		RpgUi.pin(plate,0.5,0.0)
		boss_panel=plate
		if is_instance_valid(toast_lane): toast_lane.position.y+=48
		RpgUi.pop_in(plate)
	(boss_meter.bar as ProgressBar).max_value=top
	(boss_meter.bar as ProgressBar).value=hp
	(boss_meter.readout as Label).text="%d / %d" % [int(ceil(hp)),int(top)]
	if boss_last_hp>=0.0 and hp<boss_last_hp and not RpgUi.calm():
		# A hit: a short shake and a white flash on the bar.
		var shake := boss_panel.create_tween()
		var x := boss_panel.position.x
		for step in [6.0,-5.0,3.0,0.0]: shake.tween_property(boss_panel,"position:x",x+step,0.04)
		var flash := (boss_meter.bar as ProgressBar).create_tween()
		(boss_meter.bar as ProgressBar).modulate=Color(1.8,1.8,1.8)
		flash.tween_property(boss_meter.bar,"modulate",Color.WHITE,0.25)
	boss_last_hp=hp

func difficulty_name(id: String) -> String:
	return {"relaxed":tr("산책"),"standard":tr("탐험"),"veteran":tr("개척")}.get(id,id)

## sound false: closed for the next window (its open is the one sound) or by an outcome with its own
## sound (a seed planted).
func close_village_modal(sound := true) -> void:
	if is_instance_valid(life): life.closed()
	restore_hud()
	if is_instance_valid(village_modal):
		# A shared window (modal_card) leaves the window stack; dialogues and the craft window (its
		# window lives under its holder) are freed whole.
		if village_modal.has_meta("rpg_window"): RpgUi.close_window(village_modal.get_meta("rpg_window"),false,sound)
		else:
			if sound: RpgUi.sfx("close",-10.0)
			village_modal.get_parent().remove_child(village_modal)
			village_modal.queue_free()
	village_modal=null
	if is_instance_valid(player) and screen=="village":player.controls_enabled=world_movement_allowed()

## A centred parchment window over the shared shade (RpgUi.window): display-font title, the close
## key, an ornamented rule, then the caller's content. `action` is the GameSettings action that
## opens it (its key names the close key; "" names Esc). Opens with a fade + pop.
## The opening key closes the window too (main._unhandled_input); Esc always does.
## A window already open is swapped out without its close sound (the new one's open is heard);
## quiet: the same window rebuilt in place (the stall after a trade), no sound at all.
func modal_card(title: String, action := "", quiet := false) -> VBoxContainer:
	close_village_modal(false)
	cancel_preview()
	player.controls_enabled=false
	var w := RpgUi.window(ui,title,{"action":action,"scroll":false,"on_close":close_village_modal,"id":"village_modal","sound":not quiet})
	village_modal=w.root
	player.controls_enabled=false
	return w.body

## The social layer's hooks (social_hud.gd): an invitation or knock answered from a notice, a
## visit that started from the friends list, a chat line said by someone here.
func answer_social_invite(invitation: Dictionary, decision: String) -> void:
	await social.answer(invitation, decision)

func follow_visit() -> void:
	social.poll()

func chat_bubble(user_id: String, username: String, text: String) -> void:
	if screen=="village": social.bubble(user_id, username, text)

## The window-stack description of a village modal (the craft window holds its window one level
## down, under the notes' lane), so its opening key can close it.
func modal_window(modal: Control) -> Dictionary:
	if not is_instance_valid(modal): return {}
	if modal==craft_window: return craft_window.window
	return modal.get_meta("rpg_window",{})

## The round close key for drawers and side panels (RpgUi.close_key), named "닫기" with the panel's key.
func close_button(parent: Node, callback: Callable, key := "") -> Button:
	return RpgUi.close_key(parent,callback,key)

## A round paint swatch that lifts on hover.
func swatch(parent: Node, color: Color, callback: Callable) -> Button:
	var b := Button.new()
	b.custom_minimum_size=Vector2(34,34)
	b.focus_mode=Control.FOCUS_NONE
	for state in ["normal","hover","pressed"]:
		var dot := StyleBoxFlat.new()
		dot.bg_color=color
		dot.set_corner_radius_all(17)
		dot.corner_detail=12
		dot.set_border_width_all(3 if state!="normal" else 2)
		dot.border_color=Color("ffe08a") if state!="normal" else Color("6e4b2c")
		dot.shadow_color=Color(0,0,0,.25)
		dot.shadow_size=3
		dot.shadow_offset=Vector2(0,2)
		b.add_theme_stylebox_override(state,dot)
	RpgUi.hover_motion(b,1.15)
	b.pressed.connect(func(): callback.call())
	parent.add_child(b)
	return b

func open_expedition() -> void:
	if screen!="village" or busy: return
	if me.get("active_run_summary") is Dictionary:
		await start_run()
		return
	var v := modal_card(tr("어디로 떠날까요?"))
	button(v,tr("이야기 수첩 · 섬의 세 가지 기록"),open_story)
	text(v,tr("지역과 난이도는 탐험을 시작하면 고정됩니다."),13)
	var region_row := HBoxContainer.new()
	v.add_child(region_row)
	region_row.add_theme_constant_override("separation",10)
	var details := text(v,"",14)
	details.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	details.custom_minimum_size=Vector2(700,68)
	var diff_row := HBoxContainer.new()
	v.add_child(diff_row)
	diff_row.add_theme_constant_override("separation",10)
	var estimate := text(v,"",15)
	estimate.custom_minimum_size.y=60
	var maps: Array=me.get("catalog",{}).get("maps",[]).duplicate()
	# Left to right as the catalog orders them (the tutorial first), else as listed.
	maps.sort_custom(func(a,b): return int(a.get("order",0))<int(b.get("order",0)))
	var difficulties: Array=me.get("catalog",{}).get("difficulties",[])
	var refresh := func():
		var multiplier := 1.0
		for region in maps:
			if region.id==chosen_map:
				details.text=region.name+"\n"+region.description
				multiplier*=float(region.reward_multiplier)
		for difficulty in difficulties:
			if difficulty.id==chosen_difficulty:
				multiplier*=float(difficulty.reward_multiplier)
				estimate.text=difficulty.description+tr("\n완주하면 성과에 따라 별씨 %d–%d개를 받을 수 있어요.") % [int(floor(35*multiplier+0.000001)),int(floor(100*multiplier+0.000001))]
				if preload("res://scripts/build_mode.gd").developer():estimate.text+=tr("  ·  보상 계수 ×%.3f")%multiplier
		for b in region_row.get_children(): b.button_pressed=b.get_meta("id")==chosen_map
		for b in diff_row.get_children(): b.button_pressed=b.get_meta("id")==chosen_difficulty
	for region in maps:
		map_card(region_row,region,func(): chosen_map=region.id; refresh.call())
	for difficulty in difficulties:
		var b := button(diff_row,difficulty.name,func(): chosen_difficulty=difficulty.id; refresh.call(),"choice")
		b.set_meta("id",difficulty.id)
		b.toggle_mode=true
		b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	button(v,tr("준비 완료 · 출발하기"),func(): start_run(chosen_map,chosen_difficulty),"gold")
	if not maps.is_empty() and not maps.any(func(m): return m.id==chosen_map): chosen_map=str(maps[0].id)
	refresh.call()

## The painted loading backdrop of a map (transition.gd BACKDROPS), for its card.
const MAP_ART := {"tutorial":"res://assets/ui/loading/camp.jpg","forest":"res://assets/ui/loading/forest.jpg",
	"quarry":"res://assets/ui/loading/quarry.jpg","frost":"res://assets/ui/loading/frost.jpg"}

## One map as a picture card: its painting, its name, how many stages and whether a boss waits;
## the tutorial wears a 처음 ribbon. A toggle in the row (meta "id").
func map_card(row: Container, region: Dictionary, pick: Callable) -> Button:
	var card := Button.new()
	card.name="Map_"+str(region.id)
	card.set_meta("id",region.id)
	card.toggle_mode=true
	card.focus_mode=Control.FOCUS_NONE
	card.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	card.custom_minimum_size=Vector2(170,178)
	card.add_theme_stylebox_override("normal",RpgUi.frame("card_frame"))
	card.add_theme_stylebox_override("hover",RpgUi.frame("card_frame",Color(1.08,1.06,1.0)))
	card.add_theme_stylebox_override("pressed",RpgUi.frame("card_frame",Color(1.25,1.12,0.78)))
	card.add_theme_stylebox_override("hover_pressed",RpgUi.frame("card_frame",Color(1.25,1.12,0.78)))
	card.add_theme_stylebox_override("focus",StyleBoxEmpty.new())
	card.pressed.connect(func(): pick.call())
	RpgUi.hover_motion(card,1.03)
	row.add_child(card)
	var column := VBoxContainer.new()
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	column.offset_left=10;column.offset_top=10;column.offset_right=-10;column.offset_bottom=-8
	column.add_theme_constant_override("separation",4)
	column.mouse_filter=Control.MOUSE_FILTER_IGNORE
	card.add_child(column)
	var frame_box := Control.new()
	frame_box.custom_minimum_size=Vector2(0,92)
	frame_box.clip_contents=true
	frame_box.mouse_filter=Control.MOUSE_FILTER_IGNORE
	column.add_child(frame_box)
	var art := TextureRect.new()
	var path: String=MAP_ART.get(str(region.id),"res://assets/ui/loading/village.jpg")
	art.texture=load(path) if ResourceLoader.exists(path) else null
	art.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	art.expand_mode=TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.texture_filter=CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	art.mouse_filter=Control.MOUSE_FILTER_IGNORE
	frame_box.add_child(art)
	if bool(region.get("tutorial",false)):
		var ribbon := RpgUi.label(frame_box,tr("처음"),13,RpgUi.INK)
		ribbon.add_theme_stylebox_override("normal",RpgUi.panel_style("pill",4))
		ribbon.position=Vector2(6,6)
	var title := RpgUi.label(column,str(region.get("name",region.id)),16,RpgUi.PAPER_INK,false)
	title.add_theme_font_override("font",RpgUi.FONT_STRONG)
	title.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	if region.has("stages"):
		var facts := HBoxContainer.new()
		facts.alignment=BoxContainer.ALIGNMENT_CENTER
		facts.add_theme_constant_override("separation",6)
		facts.mouse_filter=Control.MOUSE_FILTER_IGNORE
		column.add_child(facts)
		RpgUi.label(facts,tr("스테이지 %d") % int(region.stages),13,RpgUi.PAPER_MUTED,false)
		if bool(region.get("has_boss",false)):
			var crown := RpgUi.icon("crown",18)
			RpgUi.name_tip(crown,tr("마지막 밤에 우두머리"))
			crown.mouse_filter=Control.MOUSE_FILTER_PASS
			facts.add_child(crown)
	return card

func open_story() -> void:
	if screen!="village" or busy:return
	var v := modal_card(tr("이야기 수첩 · 돌아오는 빛"))
	text(v,tr("첫 완료 시 별씨와 집 앞 기념등이 추가됩니다. 자유 탐험은 지역 제한 없이 계속할 수 있어요."),13)
	var choice := HBoxContainer.new();choice.add_theme_constant_override("separation",10);v.add_child(choice)
	var description := text(v,"",16);description.custom_minimum_size=Vector2(700,140);description.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var goals := text(v,"",15);goals.custom_minimum_size.y=100
	var difficulty := OptionButton.new();difficulty.add_item(tr("산책 · 천천히 이야기 즐기기"));difficulty.add_item(tr("탐험 · 기본 생존"));difficulty.add_item(tr("개척 · 더 강한 적"));difficulty.select(1);v.add_child(difficulty)
	var start := button(v,tr("이야기 시작"),func():pass,"gold")
	var selected_story := {"id":""}
	var select_chapter := func(chapter):
		selected_story.id=chapter.id
		description.text=chapter.speaker+tr("의 부탁\n\n")+chapter.intro
		goals.text=tr("이번 탐험의 목표\n")+" · ".join(chapter.objectives)+"\n\n"+(tr("첫 완료 보상 수령 완료 · 다시 도전할 수 있어요") if chapter.completed else tr("첫 완료 보상 +%d 별씨 · %s")%[chapter.bonus,tr("도전 가능") if chapter.unlocked else tr("이전 장을 먼저 완료하세요")])
		start.disabled=not chapter.unlocked
		for child in choice.get_children():child.button_pressed=child.get_meta("id")==chapter.id
	start.pressed.connect(func():
		for chapter in me.get("campaign",[]):
			if chapter.id==selected_story.id:start_run(chapter.map_id,["relaxed","standard","veteran"][difficulty.selected],chapter.id))
	for chapter in me.get("campaign",[]):
		var b := button(choice,chapter.title+(" ✓" if chapter.completed else ""),func():select_chapter.call(chapter),"choice");b.toggle_mode=true;b.set_meta("id",chapter.id);b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var chapters: Array=me.get("campaign",[])
	if chapters.is_empty():description.text=tr("월드가 새 단장을 마치면 다시 열려요");start.disabled=true
	else:
		var current: Dictionary=chapters[0]
		for chapter in chapters:
			if chapter.unlocked and not chapter.completed:current=chapter;break
		select_chapter.call(current)

## The four authored NPCs: Naru (expedition guide), Sora (tailor), Moru (camp
## expert) and Haeru (angler). Without the local cast files a stand-in walker is used.
const CAST := [
	{"cast":"naru","title":"나루 · 길잡이","role":"map","coat":"#70afa3"},
	{"cast":"sora","title":"소라 · 재단사","role":"wardrobe","coat":"#ab789f"},
	{"cast":"moru","title":"모루 · 야영 전문가","role":"guide","coat":"#6889a1"},
	{"cast":"haeru","title":"해루 · 낚시꾼","role":"angler","coat":"#ad803b"}]

func spawn_modules() -> void:
	modules.clear()
	for path in VILLAGE_MODULES:
		await LoadPace.step("module "+path.get_file())
		if not ResourceLoader.exists(path): continue
		# Still being read on the worker thread (LoadPace.want): it goes next and the card turns meanwhile.
		var script: Script=(await LoadPace.fetch(path)) if LoadPace.pending(path) else load(path)
		if script==null or not script.can_instantiate(): continue
		var module: Node=script.new()
		world.add_child(module)
		modules.append(module)
		if module.has_method("setup"): await module.setup(self)

## The opening story chapter's module (story.gd), or null.
func chapter() -> Node:
	for module in modules:
		if is_instance_valid(module) and module.has_method("story_goal"): return module
	return null

func leave_modules() -> void:
	for module in modules:
		if is_instance_valid(module) and module.has_method("leave"): module.leave()
	modules.clear()

func module_closest() -> Dictionary:
	var best := {}
	if not is_instance_valid(player): return best
	for module in modules:
		if not is_instance_valid(module) or not module.has_method("closest"): continue
		var entry: Dictionary=module.closest(player.position)
		if entry.is_empty(): continue
		if best.is_empty() or float(entry.get("distance",99.0))<float(best.get("distance",99.0)):
			best=entry.duplicate()
			best["module"]=module
	return best

func use_module(entry: Dictionary) -> void:
	var module: Node=entry.get("module")
	if is_instance_valid(module) and module.has_method("interact"): module.interact(entry)

func spawn_villagers() -> void:
	for entry in CAST:
		await LoadPace.step("villager")
		# The model may still be arriving from a worker thread (LoadPace.want at the start).
		var model_path: String = NpcBody.resource_paths([entry.cast])[0]
		if LoadPace.pending(model_path): await LoadPace.fetch(model_path)
		var npc: Node3D
		if NpcBody.available(entry.cast):
			npc=NpcBody.new()
			world.add_child(npc)
			npc.setup(entry.cast,0.0)
			npc.player=player
		else:
			var walker := Player.new()
			walker.controls_enabled=false
			walker.avatar={"character":"explorer_b","coat":entry.coat,"pants":"#51574b","boots":"#826345","backpack":entry.role=="map","headwear":"none"}
			world.add_child(walker)
			walker.facing=Vector3(0,0,1)
			npc=walker
		npc.position=TownLayout.point(TownLayout.VILLAGERS[entry.role],.02)
		npc.set_meta("title",tr(entry.title))
		npc.set_meta("role",entry.role)
		npc.set_meta("cast",entry.cast)
		var nameplate := Art.label3d(npc,entry.title,Vector3(0,2.05,0),Color("f0dfba"))
		Art.style_nameplate(nameplate);nameplate.no_depth_test=false
		nameplate.add_to_group("npc_nameplates")
		npcs.append(npc)
		# Out at their spot only while residents.gd says so (npc.gd).
		if npc.has_method("follow_schedule"): npc.follow_schedule(self,entry.cast)

func nearest_npc() -> Node3D:
	var found: Node3D
	var distance := 2.1
	for npc in npcs:
		if not is_instance_valid(npc) or not npc.visible: continue
		var d := player.position.distance_to(npc.position)
		if d<distance:
			distance=d
			found=npc
	return found

## What each NPC says (one line per page) and what the player can do next. The
## first line fits the hour and what the villager is doing now (residents.gd).
func npc_script(role: String) -> Dictionary:
	var cast := ""
	for entry in CAST: if entry.role==role: cast=entry.cast
	var Residents := preload("res://scripts/residents.gd")
	var hour: float=daylight.current_hour() if is_instance_valid(daylight) else 12.0
	var doing: String=str(Residents.now(cast,hour,int(Residents.clock().day)).get("activity",""))
	var band := "night" if hour<5.0 or hour>=21.0 else ("morning" if hour<11.0 else ("afternoon" if hour<17.0 else "evening"))
	if doing=="stroll": band="rest"
	var openers: Dictionary={
		"map":{"morning":["좋은 아침! 돌문 앞은 아침 공기가 제일 맑아.","일찍 나왔네! 오늘 길은 내가 먼저 살펴 뒀어."],
			"afternoon":["오후엔 탐험 떠나는 사람이 제일 많아.","햇살 좋다! 숲에 가기 딱 좋은 날이야."],
			"evening":["곧 해가 져. 숲은 밤이 길다는 거 잊지 마.","저녁이네. 오늘 탐험은 어땠어?"],
			"night":["이렇게 늦게까지? 나도 이제 들어가 쉬려고.","밤엔 돌문도 조용해. 별이 잘 보이지?"],
			"rest":["잠깐 쉬는 중이야. 길잡이도 산책은 해야지!","여기 바람이 좋아서 자주 와."]},
		"wardrobe":{"morning":["아침부터 손님이네요! 바늘에 실 꿰던 참이에요.","좋은 아침이에요. 오늘은 어떤 색이 끌려요?"],
			"afternoon":["오후 햇살엔 밝은 색 옷이 잘 어울려요.","점심 먹고 나니 손이 더 잘 움직여요."],
			"evening":["저녁엔 차분한 색이 예쁘죠. 하나 골라 볼까요?","노을빛 옷감이 오늘 막 들어왔어요."],
			"night":["늦었네요. 그래도 옷 고르는 건 언제든 환영이에요.","밤엔 실 색이 잘 안 보여서… 조심조심 골라요."],
			"rest":["일 쉬는 중이에요. 바람 쐬면 새 무늬가 떠오르거든요.","잠깐 산책 나왔어요. 저 꽃 색, 옷감으로 쓰면 예쁘겠죠?"]},
		"guide":{"morning":["좋은 아침. 모닥불 재부터 정리하던 참이야.","아침이슬이 마르면 텐트를 걷어야지."],
			"afternoon":["낮이라고 방심하면 안 돼. 숲은 금방 어두워져.","오후엔 장작 패기 좋은 시간이야."],
			"evening":["해 질 녘이야. 숲이라면 지금쯤 모닥불을 지펴야 해.","저녁엔 캠프 냄새가 제일 좋아."],
			"night":["밤엔 모닥불 곁이 최고지. 너도 쉬어.","이 시간엔 숲 쪽을 보지 마. 눈이 마주칠지도."],
			"rest":["잠깐 쉬는 중. 캠프 밖 공기도 나쁘지 않네.","가끔은 텐트 말고 하늘 아래서 쉬어야 해."]},
		"angler":{"morning":["새벽 물때가 제일 좋아요. 벌써 몇 마리 놓쳤지만요.","아침 바다는 거울 같아요. 찌가 또렷하게 보여요."],
			"afternoon":["오후엔 입질이 뜸해요. 그래도 기다리는 게 낚시죠.","해가 높을 땐 물고기도 낮잠을 자나 봐요."],
			"evening":["저녁 물때예요. 노을 지는 바다에 찌가 반짝여요.","해 질 녘엔 은빛 도미가 올라와요."],
			"night":["밤바다는 찌가 안 보여서 오늘은 여기까지예요.","별빛 아래 파도 소리, 좋죠?"],
			"rest":["오늘은 낚싯대 내려놓고 쉬는 중이에요.","바다만 보다가 가끔은 마을도 걸어요."]}}
	var pool: Array=openers.get(role,{}).get(band,[])
	var opener: String=tr(pool[randi()%pool.size()]) if not pool.is_empty() else ""
	var plan: Dictionary={"lines":[tr("좋은 하루예요!")],"choices":[[tr("안녕"),Callable()]]}
	match role:
		"map": plan={"lines":[tr("어서 와! 나는 길잡이 나루야."),tr("캠프 초원의 돌문을 지나면 일곱 밤의 숲이 시작돼."),tr("처음이라면 '산책'으로 길을 익혀 봐. 어려운 길일수록 별씨를 많이 받아.")],
			"choices":[[tr("탐험 지도 펼치기"),open_expedition],[tr("길 안내 받기"),life.open_map],[tr("다음에 올게"),Callable()]]}
		"wardrobe": plan={"lines":[tr("어머, 반가워! 재단사 소라예요."),tr("오늘은 어떤 차림으로 섬을 걸어 볼까요?"),tr("옷 색과 모자, 배낭까지 마음대로 골라 보세요.")],
			"choices":[[tr("옷장 열기"),open_wardrobe],[tr("지금은 괜찮아"),Callable()]]}
		"guide": plan={"lines":[tr("모루라고 해. 숲에서 밤을 버티는 법이라면 맡겨 줘."),tr("첫날엔 목재와 돌을 모아 도끼부터 만들어."),tr("밤엔 모닥불 곁을 지키고, 붉은 원이 보이면 바로 피해!")],
			"choices":[[tr("준비하러 갈게"),Callable()]]}
		"angler": plan={"lines":[tr("오늘 물때가 좋아요."),tr("미끼를 달고 찌를 던진 뒤, 금빛 입질이 오면 바로 당기면 돼요."),tr("바다 쪽엔 은빛 도미가 더 많답니다.")],
			"choices":[[tr("낚시 도감 보기"),life.open_storage],[tr("고마워요"),Callable()]]}
	if not opener.is_empty(): plan.lines.insert(0,opener)
	return plan

## E on a villager (ISS-1 talk): both turn toward each other first; the dialogue opens once the
## villager faces the walker within 20 degrees, or after 0.4 s at most. talk_to() itself stays
## immediate for scripted calls.
var talk_turning := false
func talk_after_turn(npc: Node3D) -> void:
	if talk_turning or not is_instance_valid(npc): return
	talk_turning=true
	npc.face_point(player.position)
	player.face_point(npc.position)
	if "talk_rate" in npc: npc.talk_rate=9.0
	var waited := 0.0
	while waited<0.4 and is_instance_valid(npc) and is_instance_valid(player):
		var to: Vector3=player.global_position-npc.global_position
		if absf(angle_difference(npc.rotation.y,atan2(to.x,to.z)))<deg_to_rad(20.0): break
		await get_tree().process_frame
		waited+=get_process_delta_time()
	talk_turning=false
	if not is_instance_valid(npc): return
	if "talk_rate" in npc: npc.talk_rate=5.0
	if screen=="village" and not is_instance_valid(village_modal): talk_to(npc)

func talk_to(npc: Node3D) -> void:
	npc.face_point(player.position)
	player.face_point(npc.position)
	var plan := npc_script(npc.get_meta("role"))
	var cast := str(npc.get_meta("cast",""))
	# Residents of a house take gifts from their own village's player (npc_gifts.gd).
	if NpcGifts.can_receive(cast) and can_gift():
		plan.choices.insert(maxi(0,plan.choices.size()-1),[tr("선물하기"),func(): open_gift(cast,str(npc.get_meta("title")),cast,npc)])
	# The resident's request (quests.gd) comes first.
	var request: Array=preload("res://scripts/quests.gd").choice(self,cast,str(npc.get_meta("title")),cast,npc)
	if not request.is_empty(): plan.choices.insert(0,request)
	open_dialogue(str(npc.get_meta("title")),cast,plan.lines,plan.choices)

## Gifts go to the residents of your own village only.
func can_gift() -> bool:
	return not api.token.is_empty() and not social.visiting()

## "선물하기" from any village conversation (the cast here, the walkers in shadow_folk.gd):
## the bag's crafted pieces as choices, the resident's reaction and a thank-you effect.
func open_gift(npc_id: String, speaker: String, portrait: String, anchor: Node3D) -> void:
	var say := func(lines: Array, choices: Array) -> void:
		open_dialogue(speaker,portrait,lines,choices if not choices.is_empty() else [[tr("알겠어요"),Callable()]])
	var done := func(reply: Dictionary) -> void:
		if is_instance_valid(anchor):
			NpcGifts.thanks_effect(world,anchor.global_position,self)
			if anchor.has_method("pop"): anchor.pop("♥",1.6)
			if anchor.has_method("smile"): anchor.smile(3.0)
		message(NpcGifts.thanks_text(speaker.split(" · ")[0],reply),"social")
		# A new heart brings a letter (and at the fourth a present in the bag): say so after the thanks.
		var note := NpcGifts.letters_note(reply)
		if not note.is_empty(): create_tween().tween_callback(func(): message(note)).set_delay(2.6)
		await refresh_inventory()
	NpcGifts.start(api,npc_id,say,done)

## RPG dialogue: an illustration on the left, a name plate and a box that types
## each line out. E, Space or a click advances; choices appear on the last line.
func open_dialogue(speaker: String, cast: String, lines: Array, choices: Array) -> void:
	close_village_modal()
	cancel_preview()
	village_modal=Control.new()
	village_modal.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.add_child(village_modal)
	hide_hud()
	player.controls_enabled=false
	var portrait_path := cast if cast.begins_with("res://") else "res://assets/portraits/%s.png" % cast
	var window: Dictionary = RpgUi.dialogue(village_modal,speaker,portrait_path if not cast.is_empty() else "")
	var body: Label = window.body
	var page := [0]
	var show_page := func(index: int) -> void:
		body.text=lines[index]
		RpgUi.dialogue_line(window,lines[index])
		RpgUi.dialogue_type(window,GameSettings.typing_seconds(lines[index].length()))
		VoiceBabble.speak(self,cast,lines[index],0.0,body)
		if index<lines.size()-1:
			RpgUi.dialogue_more(window,true)
		else:
			RpgUi.dialogue_more(window,false)
			var entries := []
			for choice in choices:
				var action: Callable=choice[1]
				entries.append([choice[0],func():
					close_village_modal()
					if action.is_valid(): action.call()])
			RpgUi.dialogue_choices(window,entries)
	var advance := func() -> void:
		if RpgUi.dialogue_typing(window):
			RpgUi.dialogue_skip(window)
		elif page[0]<lines.size()-1:
			page[0]+=1
			RpgUi.sfx("page",-8.0)
			show_page.call(page[0])
		else:
			# The last page: the highlighted choice (E, Space or Enter when no choice holds the focus).
			RpgUi.dialogue_pick(window)
	village_modal.set_meta("advance",advance)
	window.shade.gui_input.connect(func(event):
		if event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT: advance.call())
	show_page.call(0)

## Conversations hide the HUD, the way story scenes do in console RPGs; closing the
## window brings back exactly the panels that were showing.
var hidden_hud: Array[CanvasItem] = []
func hide_hud() -> void:
	for child in ui.get_children():
		if child!=village_modal and child is CanvasItem and (child as CanvasItem).visible:
			(child as CanvasItem).visible=false
			hidden_hud.append(child)

func restore_hud() -> void:
	for item in hidden_hud:
		if is_instance_valid(item): item.visible=true
	hidden_hud.clear()

func open_wardrobe() -> void:
	if screen!="village": return
	var v := modal_card(tr("나의 여행자"),"wardrobe")
	var editor := preload("res://scripts/wardrobe.gd").new()
	editor.avatar=me.get("profile",{}).get("avatar",{}).duplicate(true)
	v.add_child(editor)
	var status := RpgUi.caption(v,tr("외형은 모든 지역에서 같게 유지됩니다. 능력치는 바뀌지 않습니다."),12)
	var save := button(v,tr("이 모습으로 저장"),func():
		var result: Dictionary=await api.post("/v1/profile",api.mutation({"version":me.get("profile",{}).get("version",0),"avatar":editor.avatar}))
		if not is_instance_valid(editor): return
		if result.ok:
			adopt_profile(result.data,true)
			close_village_modal()
			RpgUi.sfx("save",-6.0)
			message(tr("새로운 여행자 모습이 저장되었습니다."))
		else:
			RpgUi.sfx("deny",-6.0)
			status.text=tr("옷을 갈아입지 못했어요. 옷장을 다시 열어 주세요.")
	)
	save.custom_minimum_size.y=44
	save.theme_type_variation="GoldButton"


func open_studio(destination: String="workshop") -> void:
	var session := {"token":api.token,"url":api.base_url,"room":destination,"multiplayer":social.enabled,
		"profile":me.get("profile",{}).duplicate(true),"username":str(me.get("username",""))}
	# The room's character frame shows the same two currencies as the village's.
	if is_instance_valid(life) and life.state.has("coins"): session.coins=int(life.state.coins)
	session.visiting=social.visiting()
	if social.visiting():
		# Friends may step into the host's home and public buildings; the workshop stays private.
		if destination=="workshop":
			refuse(tr("친구의 공방은 들어갈 수 없어요. 친구 집에는 놀러 갈 수 있어요."))
			return
		if destination=="home":
			# The host's home opens only while the host is inside (server/home_access.py).
			var shut: String=preload("res://scripts/home_door.gd").refusal(social.data.get("home"))
			if not shut.is_empty():
				preload("res://scripts/home_door.gd").refuse_at_door(self,social.data)
				return
			session.visit_host=str(social.data.get("host_id",""))
			session.visit_name=str(social.data.get("host_name",tr("친구")))
	if busy or api.token.is_empty() or VillageDoors.walking(self): return
	Engine.set_meta("studio_session",session)
	var veil := Transition.of(get_tree())
	player.controls_enabled=false
	veil.loading(tr("%s님의 집") % str(session.visit_name) if session.has("visit_name") else TownLayout.room_title(destination),"","room")
	# Near the door the walker turns to it, the door swings open and it walks in under the fade (village_doors.gd).
	if not await VillageDoors.walk_in(self,destination,veil):
		veil.play_door("open",destination)
		await veil.fade_out()
	leave_modules()
	if is_instance_valid(town): town.release_map()
	get_tree().change_scene_to_packed(studio_scene())

## The room scene, read on a worker thread while the title shows (LoadPace.want in _ready) and kept:
## reading it at the door held the card for about 0.4 s.
const STUDIO_SCENE := "res://scenes/studio.tscn"
static var studio_packed: PackedScene
static func studio_scene() -> PackedScene:
	if studio_packed == null: studio_packed = LoadPace.take(STUDIO_SCENE)
	return studio_packed

## Crafting is one feature wherever the player is: C (or the 제작 slot) opens the same craft window
## (craft_window.gd) here and in every room, and the session's CraftTracker follows the craft, so it
## goes on after the window closes and while the player walks into the home and back. The village
## is one of the window's places: it implements craft_say, craft_place, craft_place_block,
## craft_bag_changed and close_craft.
## Crafting works while visiting a friend too (the craft is the player's own and lands in their bag);
## only putting it down waits for the player's own village or rooms.
var craft_window: Control
## The open window's form and craft view (tests and tools).
var craft_box: CraftPanel:
	get: return craft_window.panel if is_instance_valid(craft_window) else null
## The session's craft under way, the finished one and the picture already announced.
var craft_job: String:
	get:
		var tracker := craft_tracker()
		return tracker.job_id if tracker else ""
var craft_done: Dictionary:
	get:
		var tracker := craft_tracker()
		return tracker.done if tracker else {}
var craft_announced: String:
	get:
		var tracker := craft_tracker()
		return tracker.announced if tracker else ""

## The session's craft follower, with this village as the place that speaks (null before signing in).
func craft_tracker() -> Node:
	var tracker := CraftTracker.of(api)
	if tracker and not is_queued_for_deletion() and tracker.host!=self: tracker.attach(self)
	return tracker

func open_craft() -> void:
	if screen!="village" or api.token.is_empty(): return
	close_village_modal()
	cancel_preview()
	craft_window = CraftWindow.new()
	craft_window.setup(self,api)
	village_modal = craft_window
	ui.add_child(craft_window)
	player.controls_enabled=false
	await craft_window.open()

func close_craft() -> void:
	if is_instance_valid(craft_window) and village_modal==craft_window: close_village_modal()
	elif is_instance_valid(craft_window): craft_window.queue_free()

func craft_say(words: String) -> void:
	message(words)

func craft_bag_changed() -> void:
	refresh_inventory()

## Finished crafts go down in the player's own village only.
func craft_place_block() -> String:
	return CraftWords.place_block("visit") if social.visiting() else ""

func craft_place(object_id: String) -> void:
	await place_crafted(object_id)

func render_craft(job: Dictionary) -> void:
	if is_instance_valid(craft_box): craft_box.show_job(job)

## Writes the idea into the open craft window and asks for it (tests and tools).
func request_craft(idea: String) -> void:
	if not is_instance_valid(craft_box): return
	craft_box.prompt.text = idea
	await craft_box.request()

func confirm_craft() -> void:
	if is_instance_valid(craft_box): await craft_box.confirm(true)

func cancel_craft() -> void:
	if is_instance_valid(craft_box): await craft_box.cancel()

## Follows the craft under way (the session's one loop; see craft_tracker.gd).
func follow_craft() -> void:
	var tracker := craft_tracker()
	if tracker: await tracker.follow()

## "여기에 놓기" in the village: the new object follows the cursor to a free spot.
func place_crafted(object_id: String) -> void:
	var tracker := craft_tracker()
	if tracker: tracker.clear_done()
	close_village_modal()
	# The bag may not have heard of it yet: asked again once.
	for attempt in 2:
		for i in me.objects.size():
			if me.objects[i].id==object_id:
				select_object(i)
				await begin_place()
				return
		if attempt==0: await refresh_inventory()

## Operator tools (F9, admin accounts only): top up currencies through the
## server's ledgered admin route and jump to any village site.
func open_admin() -> void:
	if screen!="village": return
	var v := modal_card(tr("관리자 도구"))
	RpgUi.caption(v,tr("관리자 계정 전용입니다. 지급 내역은 서버 원장에 남아요."),14)
	var grants := HBoxContainer.new()
	grants.add_theme_constant_override("separation",8)
	v.add_child(grants)
	for spec in [[tr("별씨 +1000"),{"shards":1000}],[tr("별씨 +10000"),{"shards":10000}],[tr("잎전 +500"),{"coins":500}]]:
		var amount: Dictionary = spec[1]
		button(grants,spec[0],func():
			var reply: Dictionary = await api.post("/v1/admin/grant",api.mutation(amount))
			if check(reply):
				message(tr("지급했어요 · 별씨 %d · 잎전 %d") % [int(reply.data.shards),int(reply.data.coins)],"success")
				await refresh_inventory()
				await life.refresh())
	text(v,tr("순간 이동"),20)
	var places := GridContainer.new()
	places.columns = 3
	v.add_child(places)
	var sites := [[tr("물결빛 광장"),TownLayout.SPAWN],[tr("탐험 출발지"),TownLayout.GATE]]
	for place in TownLayout.PLACES: sites.append([tr(place.title),place.at])
	for site in sites:
		var at: Vector2 = site[1]
		button(places,site[0],func():
			close_village_modal()
			player.position = TownLayout.point(at+Vector2(0,1.2),.3)
			camera_focus_ready = false)
	var dev := HBoxContainer.new()
	v.add_child(dev)
	button(dev,tr("F3 개발 정보 켜기/끄기"),func():
		if is_instance_valid(developer_panel): developer_panel.visible = not developer_panel.visible)

func nearest_furniture() -> String:
	var result := "";var distance := 2.3
	for id in loaded:
		if not is_instance_valid(loaded[id]): continue
		var item: Node3D=loaded[id]
		if not is_instance_valid(item) or not item.get_meta("studio",false):continue
		var d: float=player.position.distance_to(item.position)
		if d<distance:distance=d;result=id
	return result

func village_furniture_event(id: String,event: String) -> void:
	var item: Node3D=loaded.get(id)
	# A seat or a bed takes the walker, as in rooms; its click behaviour runs too.
	if event=="click" and is_instance_valid(item) and str(item.get("rest")) in ["sit","lie"]:
		var rest := village_seat()
		var was_resting: bool=rest.resting()
		rest.crafted(item,str(item.rest),item.global_position.y)
		# The fallback (no driver, no socket) seats the walker at once: the contact is now. The driver
		# voices its own contact when the walker gets there (seat_sound).
		if not was_resting and not str(rest.legacy_mode).is_empty():
			seat_sound("settle",{"at":item.global_position,"material":"soft" if str(item.rest)=="lie" else "wood","kind":str(item.rest)})
	# A visitor plays the host's interactions on this screen only; the host's object is not changed.
	if social.visiting():
		if not id.is_empty() and is_instance_valid(item) and item.has_method("local_event"):
			item.local_event(event)
			# The program's own commands for this click (its VM keeps the last run's).
			var vm = item.get("vm")
			if event=="click" and vm!=null and vm.get("commands") is Array: use_cue(item,vm.commands)
		return
	if id.is_empty() or busy or refreshing:return
	# Near/leave run every half second and can skip a beat, but a click (E) is the player's own
	# action: it waits for an event still on its way (sitting down moves the walker, which sends
	# one) instead of being dropped.
	if furniture_event_pending:
		if event!="click":return
		var waited := 0.0
		while furniture_event_pending and waited<3.0:
			await get_tree().process_frame
			waited+=get_process_delta_time()
		if furniture_event_pending:return
	if not is_instance_valid(item) and selected.get("id")==id:item=inspect_model
	if not is_instance_valid(item) or not item.get_meta("studio",false):return
	furniture_event_pending=true
	var epoch := world_epoch
	var reply: Dictionary=await api.post("/v1/objects/"+id+"/event",api.mutation({"version":item.runtime_version,"event":event}))
	furniture_event_pending=false
	if epoch!=world_epoch:return
	if not reply.ok:
		if reply.get("status")==409:await refresh_inventory()
		else:refuse(error_message(reply.error))
		return
	if is_instance_valid(item):
		item.accept_event(reply.data)
		if event in ["near","leave"]:item.nearby=event=="near"
		if event=="click" and reply.data.get("commands") is Array: use_cue(item,reply.data.commands)
	if selected.get("id")==id and is_instance_valid(inspect_model) and inspect_model!=item:inspect_model.accept_event(reply.data)
	for obj in me.objects:
		if obj.id==id:obj.runtime_version=reply.data.version

## Using a crafted object (the player's click or E running its program): one soft cue at the piece by
## what the click did. A light turned on twinkles (a lower twinkle when it goes off), a colour change
## plucks, a turn or a slide pops. Nothing when the click changed nothing, on seats and beds (sitting
## down has its own contact) and more than once per USE_CUE_GAP_MS per piece. Clicks only: tick
## programs run every frame (asset_assembly.gd) and stay silent.
func use_cue(item: Node3D, commands: Array) -> void:
	if not is_instance_valid(item) or commands.is_empty() or str(item.get("rest")) in ["sit","lie"]: return
	var now := Time.get_ticks_msec()
	if now-int(item.get_meta("use_cue_at",-100000))<USE_CUE_GAP_MS: return
	var light := -1.0
	var tint := false
	var move := false
	for c in commands:
		if not c is Dictionary: continue
		var op := str(c.get("op",""))
		if op=="emission": light=maxf(light,float(c.get("value",0.0)))
		elif op=="hue": tint=true
		elif op.begins_with("rotate_") or op.begins_with("offset_"): move=true
	if light<0.0 and not tint and not move: return
	item.set_meta("use_cue_at",now)
	# The bag's inspect copy lives in its own viewport: heard as is, without distance.
	var at := Vector3.INF
	if is_instance_valid(world) and world.is_ancestor_of(item):
		var size: Vector3=item.get_meta("size",Vector3.ONE)
		at=item.global_position+Vector3(0,size.y*0.5,0)
	if light>=0.0: Fx.sound(self,"twinkle",at,1.1 if light>0.05 else 0.85,-9.0)
	elif tint: Fx.sound(self,"pluck",at,1.15,-10.0)
	else: Fx.sound(self,"pop",at,0.9,-10.0)

## The village's rest_seat.gd, following the walker of the current world.
func village_seat() -> Node:
	if not is_instance_valid(seat):
		seat=preload("res://scripts/rest_seat.gd").new()
		seat.keep_height=true
		seat.walk_off=world_movement_allowed
		add_child(seat)
	seat.hero=player
	# Its driver (ix/ix_driver.gd, made here for the first seat) voices the contact, lying back,
	# getting up, the feet down and a rocking piece's creaks through seat_sound().
	var driver: Node=seat.ensure_driver()
	if is_instance_valid(driver) and "sound" in driver: driver.sound=seat_sound
	return seat

## The village seats' sounds (IxDriver.sound): by the seat's material, a wood creak or a cushion as
## the weight lands, a cushion sink lying back, the seat letting go when getting up, one soft step
## when the feet are down, a rocking piece's creak at the end of a sway, and a soft deny when the
## walk up to the seat gives up. All soft; the rock is throttled by the driver.
func seat_sound(event: String, info: Dictionary) -> void:
	if screen!="village": return
	var at: Vector3=info.get("at",Vector3.INF)
	var material := str(info.get("material","wood"))
	match event:
		"settle":
			match material:
				"soft": Fx.sound(self,"cushion",at,1.0,-6.0)
				"ground": Fx.sound(self,"cushion",at,1.1,-11.0)
				"rope": Fx.sound(self,"field/settle",at,1.0,-3.0)
				_: Fx.sound(self,"seat",at,1.0,-8.0)
		"lie": Fx.sound(self,"cushion",at,0.88,-9.0)
		"rise":
			if material!="ground": Fx.sound(self,"field/stand",at,1.0,-3.0)
		"feet":
			if is_instance_valid(world_audio) and is_instance_valid(player): world_audio.footstep(ground_surface(),1.4)
		"rock":
			var amount := clampf(float(info.get("amount",1.0)),0.0,1.0)
			Fx.sound(self,"field/hammock" if material=="rope" else "field/wood_creak",at,randf_range(0.95,1.05),-10.0+4.0*amount)
		"refused": RpgUi.sfx("deny",-10.0)

## A click on crafted furniture within reach uses it, like E.
func click_furniture(at: Vector2) -> void:
	var id := nearest_furniture()
	if id.is_empty() or not is_instance_valid(camera) or not world_movement_allowed(): return
	var item: Node3D=loaded.get(id)
	if not is_instance_valid(item): return
	var tall: Vector3=item.get_meta("size",Vector3.ONE)
	var spot: Vector2=camera.unproject_position(item.global_position+Vector3(0,tall.y*0.5,0))
	if spot.distance_to(at)<maxf(70.0,tall.y*60.0): await village_furniture_event(id,"click")

func village_furniture_proximity() -> void:
	if furniture_event_pending or busy or refreshing or not is_instance_valid(player):return
	if social.visiting():
		for id in loaded.keys():
			var guest_item = loaded.get(id)
			if not is_instance_valid(guest_item) or not guest_item.get_meta("studio",false) or not guest_item.has_method("local_event"):continue
			var near_guest: bool=player.position.distance_to(guest_item.position)<(2.5 if guest_item.nearby else 1.8)
			if near_guest!=guest_item.nearby: guest_item.local_event("near" if near_guest else "leave")
		return
	for id in loaded.keys():
		if not loaded.has(id) or not is_instance_valid(loaded[id]):continue
		var item: Node3D=loaded[id]
		if not is_instance_valid(item) or not item.get_meta("studio",false):continue
		var near_now: bool=player.position.distance_to(item.position)<(2.5 if item.nearby else 1.8)
		if near_now!=item.nearby:await village_furniture_event(id,"near" if near_now else "leave")
