extends Control
const Api=preload("res://scripts/api.gd")
const Assembly=preload("res://scripts/asset_assembly.gd")
const Loader=preload("res://scripts/model_loader.gd")
const PaintApply=preload("res://scripts/painter/paint_apply.gd")
const ObjectTransform=preload("res://scripts/object_transform.gd")
const ShapePanel=preload("res://scripts/shape_panel.gd")
const InteractionPanel=preload("res://scripts/interaction_panel.gd")
const Art=preload("res://scripts/art.gd")
const BuildMode=preload("res://scripts/build_mode.gd")
const ControllerProfile=preload("res://scripts/controller_profile.gd")
const Transition=preload("res://scripts/transition.gd")
const LoadPace=preload("res://scripts/load_pace.gd")
const I18n=preload("res://scripts/i18n.gd")
const Interiors=preload("res://scripts/interiors.gd")
const Daylight=preload("res://scripts/daylight.gd")
const RpgUi=preload("res://scripts/rpg_ui.gd")
const Residents=preload("res://scripts/residents.gd")
const DayFolk=preload("res://scripts/day_folk.gd")
const GameSettings=preload("res://scripts/game_settings.gd")
const PauseMenu=preload("res://scripts/pause_menu.gd")
const CraftPanel=preload("res://scripts/craft_panel.gd")
const CraftWindow=preload("res://scripts/craft_window.gd")
const CraftTracker=preload("res://scripts/craft_tracker.gd")
const CraftWords=preload("res://scripts/craft_words.gd")
const Fx=preload("res://scripts/fx.gd")
## Residents' babble, greetings and emote barks (voice_babble.gd).
const VoiceBabble=preload("res://scripts/voice_babble.gd")
## Room tone, the room's bed, floor footsteps (world_audio.gd) and the room music (sound.gd).
const WorldAudio=preload("res://scripts/world_audio.gd")
const Sound=preload("res://scripts/sound.gd")
## The room music swells in over this many seconds (the village track was just cut by the scene
## change), and on the way out it fades over MUSIC_HANDOFF s across the change to the village.
const MUSIC_IN := 3.0
const MUSIC_HANDOFF := 1.6
## Visitors' and residents' footsteps sit this far under the walker's own (dB).
const PEER_STEP_DB := -8.0
const RESIDENT_STEP_DB := -11.0
## Room beds sit this low (WorldAudio.ambience_db; the village uses -10): a hearth's crackle or a
## clock stays under the music and the furniture sounds.
const ROOM_AMBIENCE_DB := -13.0
## A resident's activity cue (♪ at the piano, ✦ at the telescope) barks again only after this long.
const CUE_BARK_GAP := 15.0
const NpcGifts=preload("res://scripts/npc_gifts.gd")
const ShopSell=preload("res://scripts/shop_sell.gd")
const AvatarLook=preload("res://scripts/avatar_look.gd")
## Visitors' and the host's walk in the home, drawn smoothly from the presence replies.
const RemoteMotion=preload("res://scripts/remote_motion.gd")
const SocialHud=preload("res://scripts/social_hud.gd")
## The home shares spots four times a second; other rooms (the workshop, a public building) still
## say every few seconds that this player is here, so a host crafting in the workshop keeps the
## guests in the village (server/multiplayer.py HOST_GONE_SECONDS).
const ROOM_PRESENCE := 0.25
const ROOM_HEARTBEAT := 3.0
const RestSeat=preload("res://scripts/rest_seat.gd")
## The opening story chapter at home: the welcome letter on the desk (story_home.gd).
const StoryHome=preload("res://scripts/story_home.gd")
## A new session opens in the attic bed: the eyes open, the walker gets up (bed_wake.gd).
const BedWake=preload("res://scripts/bed_wake.gd")
## The front door swings for whoever walks through it (room_door.gd).
const RoomDoor=preload("res://scripts/room_door.gd")
var front_door: Node
var wake_up := false
var bed_wake: Node
## Game version and server notices (update window, new-version banner, maintenance countdown/screen).
const VersionGate=preload("res://scripts/version_gate.gd")
## Build mode: the placed-object menu, 물건 통과 and the loading ring (scripts/build/).
const RoomBuild=preload("res://scripts/build/room_build.gd")
const LoadRing=preload("res://scripts/build/load_ring.gd")
## On ladder rungs the walker climbs with this clip (the explorer's crouched step) instead of the
## walk clip, which would march in place: the rise is straight up, nothing moves across.
const LADDER_CLIP := "Legs_Crouch_Step"
var api: Node
var gate: CanvasLayer
var viewport: SubViewport
## The painting workspace (scripts/painter/painter.gd) while open, and the 보관함 entry to it.
var painter: Control
## The interaction editor (scripts/interaction_panel.gd) while open.
var interaction_panel: Control
var paint_button: Button
var paint_rows: Array=[]
var view_container: SubViewportContainer
var stage: Node3D
var furniture: Node3D
var room_root: Node3D
var camera: Camera3D
var hero: Node3D
var inventory: ItemList
var title_label: Label
var status_label: Label
var wallet: Label
var detail: Label
var room_capacity: Label
## The one craft window (craft_window.gd), the same the village opens with C, while it is open here.
var craft_window: Control
## Its form and craft view (null while the window is closed).
var craft: CraftPanel:
	get: return craft_window.panel if is_instance_valid(craft_window) else null
## The craft window's controls under their old names for tests and tools (they open the window).
var prompt: TextEdit:
	get: return craft_panel().prompt
var surface_mode: OptionButton:
	get: return craft_panel().surface
var motion: OptionButton:
	get: return craft_panel().motion
var designer: OptionButton:
	get: return craft_panel().designer
var geometry: OptionButton:
	get: return craft_panel().geometry
var models: OptionButton:
	get: return craft_panel().models
var efforts: OptionButton:
	get: return craft_panel().efforts
var mesh_models: OptionButton:
	get: return craft_panel().mesh_model
var part_choice: OptionButton
var code_view: CodeEdit
var data: Dictionary={}
var selected: Dictionary={}
var placed: Dictionary={}
var inspected: Node3D
var ghost: Node3D
var room := "workshop"
## Home visits: a friend's home opens read-only; everyone inside the same home
## shares presence so visitors and the host see each other.
var visit_host := ""
var visit_name := ""
## The look the village (or the sign-in) handed over, so the walker wears it before /v1/studio
## answers, and its profile version (avatar_look.gd).
var session_avatar: Dictionary={}
var session_version := -1
var dock_panel: Control
var room_buttons: Array[Button] = []
var peers: Dictionary = {}
## Visitors' join/leave sounds (peer_sounds): the first presence answer has been taken stock of, and
## the last one played (ms).
var peer_baseline := false
var peer_sound_ms := -100000
var presence_time := 0.0
var presence_pending := false
var shared_presence := false
## Signed in to a world with multiplayer (the village's session).
var social_session := false
## Velocity and clock in the spot (an older server refuses them with 422: then the 0.11.4 fields).
var rich_presence := true
var placement_mode := false
var placement_rotation := 0
## The placing tools' angle readout (between the ↶ ↷ arrows).
var turn_readout: Label
## The 보관함's 모양 바꾸기 window (shape_panel.gd) while it is open.
var shape_panel: Control
var place_at := Vector3.ZERO
var pending := false
var epoch := 0
var selection_epoch := 0
var placement_epoch := 0
## The session's craft under way (craft_tracker.gd follows it here, in other rooms and outside).
var job_id: String:
	get:
		var tracker := craft_tracker()
		return tracker.job_id if tracker else ""
var refreshing := false
var auth_time := 0.0
var orbit := 0.0
var proximity_time := 0.0
var proximity_pending := false
var placement_marker: MeshInstance3D
var preview_stage: Node3D
var preview_camera: Camera3D
var generated_functions: OptionButton
var function_args: LineEdit
var function_fields: Array[SpinBox]=[]
var function_fields_box: VBoxContainer
var function_fields_scroll: ScrollContainer
var function_signature: Label
var raw_args_toggle: CheckButton
var function_result: Label
var binding_part: OptionButton
var binding_fields: Dictionary={}
var binding_hint: Label
var binding_dirty := false
var history_list: ItemList
var history_detail: Label
var history_selected := ""
var placement_tools: PanelContainer
var placement_title: Label
var placement_feedback: Label
var place_button: Button
var floor_grid: MeshInstance3D
var grid_toggle: CheckButton
## Interior rooms: "home" and "workshop" can be decorated; a building id such as
## "01_cafe" opens that building's read-only public interior (scripts/interiors.gd).
var room_spec: Dictionary={}
## The room's WorldAudio: room tone, the room's bed (hearth, clock, mill, cafe, the sea through the
## walls) and the floor's footsteps (planks, tile, stone, rug, stairs).
var world_audio: Node
## The room's music (sound.gd).
var room_music: Node
## Last play (ms) of the UI ticks that can come many times a second (soft_tick).
var tick_times: Dictionary={}
## Residents walking right now (walk_to), whose steps room_steps plays.
var stepping: Array=[]
var decor: Array=[]
var public_room := false
var subtitle_label: Label
var controls_label: Label
var environment: Environment
var sun: DirectionalLight3D
var cam_focus := Vector3.ZERO
var interact_count := 0
var bubble: PanelContainer
var bubble_label: Label
var bubble_anchor := Vector3.ZERO
var bubble_tween: Tween
var hint_label: Label
var hint_anchor := Vector3.ZERO
var hint_time := 0.0
var tone_player: AudioStreamPlayer
var leaving := false
## Floors: the building spec, one root per floor (only the current one is shown)
## and each floor's furniture/window records. room_spec is the current floor.
var building_spec: Dictionary={}
var floor_index := 0
var floor_roots: Array=[]
var decor_by_floor: Array=[]
var travelling := false
## Tests drive the walker directly and switch this off to keep it on one floor.
var travel_enabled := true
var sfx_player: AudioStreamPlayer
## Server per-craft Tripo credit cap (0 = none), from /v1/studio.
var craft_cap := 0
var place_label: Label
var current_room := -1
var cam_distance := 9.0
## Real-time outside light (Daylight); a test can pin the hour.
var hour_override := -1.0
var daylight_time := 0.0
var daylight_sample: Dictionary={}
## Sitting or lying on furniture (rest_seat.gd, shared with the village): "", "sit" or "lie".
var seat: Node
var resting: String:
	get: return seat.mode if is_instance_valid(seat) else ""
var walk_out := Vector3.ZERO
## RPG-style HUD over the full-screen room view.
var name_panel: PanelContainer
var name_tween: Tween
## The location card's picture and its flavour line (shown on arrival, then rolled up).
var place_icon: TextureRect
var place_flavour: VBoxContainer
var toast_lane: VBoxContainer
## The one prompt chip (RpgUi.prompt): what the interact key does right here.
var hint_chip: Label
## The HUD root (design canvas), the character frame (RpgUi.player_frame) and its portrait drawing.
var hud: Control
var frame: Dictionary={}
var portrait_view: Node
## The name and leaf coins the village handed over (-1: not known here).
var session_name := ""
var session_coins := -1
## The 가방 drawer (RpgUi.drawer, kept), its scrolling pages and tabs, and the furniture preview.
var bag: Dictionary={}
var bag_scroll: ScrollContainer
var bag_strip: HBoxContainer
var bag_pages: Dictionary={}
var preview_view: SubViewportContainer
## The hotbar slots, as in the village: 가방 (I) opens the dock, 제작 (C) the craft window.
var dock_toggle: Button
var craft_slot: Button
var leave_button: Button
## The last piece of furniture used (tests read it).
var last_used: Dictionary={}
## Residents inside public buildings (scripts/residents.gd decides who is where).
var npcs: Dictionary={}
var residents_time := 0.0
var cue_time := 0.0
var talk_box: Control
var talk_body: Label
var talk_footer: HBoxContainer
## The RpgUi.dialogue window parts while a resident is talking.
var talk_window: Dictionary = {}
var talk_lines: Array=[]
var talk_choices: Array=[]
var talk_page := 0
var talk_id := ""
var pick_cycle := 0
var pick_spot := Vector3(INF,0,INF)
var pick_time := -100.0
## Gifts the residents of this house put up (npc_gifts.gd, server/npc_homes.py): the building id
## when this is a gift home, the layout version shown, and {object id: {item, node, record}}.
var gift_home := ""
var gift_version := -1
var gift_nodes: Dictionary = {}
var gift_time := 0.0
var gift_pending := false
var gift_epoch := 0
## Visiting a friend's village (gifts go to your own village's residents only).
var visiting := false
## The story chapter in the owner's home (the letter on the desk), or null.
var story_home: Node

func _ready() -> void:
	I18n.setup()
	Art.watch_labels(get_tree())
	Loader.warm_up_compression()
	var veil := Transition.of(get_tree())
	veil.cover()
	# The room is built under the card, paced over frames (load_pace.gd); the room's own per-frame
	# work and keys wait for it, and the card fades once it stands.
	set_process(false);set_process_unhandled_key_input(false)
	api=Api.new();add_child(api)
	gate=VersionGate.new();add_child(gate);gate.watch(api)
	# Maintenance over: the room shows the server's state again (nothing was lost).
	gate.resumed.connect(func():
		if public_room:
			if not api.token.is_empty(): load_avatar()
		else: refresh())
	gate.logout_required.connect(logged_out)
	if Engine.has_meta("studio_session"):
		var session: Dictionary=Engine.get_meta("studio_session")
		api.token=session.token;api.base_url=session.url
		room=str(session.get("room","workshop"))
		visit_host=str(session.get("visit_host",""))
		visit_name=str(session.get("visit_name",""))
		visiting=bool(session.get("visiting",false)) or not visit_host.is_empty()
		session_name=str(session.get("username",""))
		session_coins=int(session.get("coins",-1))
		if session.get("avatar") is Dictionary: session_avatar=session.avatar
		if session.get("profile") is Dictionary and session.profile.get("avatar") is Dictionary:
			session_avatar=session.profile.avatar
			session_version=int(session.profile.get("version",-1))
		social_session=bool(session.get("multiplayer",false))
		shared_presence=social_session and room=="home"
		wake_up=bool(session.get("wake",false)) and room=="home" and visit_host.is_empty()
		Engine.remove_meta("studio_session")
	if not Interiors.has_interior(room): room="workshop"
	public_room=Interiors.is_public(room)
	tone_player=AudioStreamPlayer.new();tone_player.volume_db=-5;tone_player.bus=GameSettings.BUS_SFX;add_child(tone_player)
	sfx_player=AudioStreamPlayer.new();sfx_player.volume_db=-8;sfx_player.bus=GameSettings.BUS_SFX;add_child(sfx_player)
	# Indoor music (집 BGM) for the home and the other rooms: it swells in softly under the card.
	room_music=Sound.new();add_child(room_music);room_music.play_music("home")
	ease_in_music()
	# Room tone, the room's own bed (hearth, clock, mill, cafe), the sea through the walls; floor footsteps.
	# The building's bed starts under the card; each floor and room refines it (update_room_audio).
	world_audio=WorldAudio.new();world_audio.name="WorldAudio";add_child(world_audio);world_audio.setup()
	world_audio.ambience_db=ROOM_AMBIENCE_DB
	update_room_audio()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--hour="): hour_override=clampf(float(arg.trim_prefix("--hour=")),0.0,23.99)
	if Engine.has_meta("interior_hour"): hour_override=float(Engine.get_meta("interior_hour"))
	# The scene switch and the session took this frame; the room's HUD comes in the next ones.
	await LoadPace.step("room ui")
	await build_ui()
	LoadPace.done(0.3)
	await LoadPace.step("room stage")
	await build_stage()
	set_dock_open(room=="workshop")
	set_process(true);set_process_unhandled_key_input(true)
	LoadPace.done(1.0)
	veil.fade_in()
	if is_instance_valid(bed_wake) and not bed_wake.is_queued_for_deletion(): bed_wake.open_eyes()
	# In through the front door as the card lifts; it shuts behind (no door for the wake-up in bed).
	elif is_instance_valid(front_door) and is_instance_valid(front_door.hinge) and is_instance_valid(hero): front_door.walk_in(hero)
	else: veil.play_door("close",room)
	# The session's craft is told here now (any room: the home, the workshop, a friend's, a building).
	if not api.token.is_empty(): craft_tracker()
	show_story()
	if public_room:
		# Village buildings are only for looking around: no bag or editing (the craft window still opens;
		# the finished object waits in the bag). The location card tells the building's flavour.
		set_dock_open(false);update_room_slots()
		if not api.token.is_empty():
			load_avatar()
			refresh_gifts()
		return
	if not visit_host.is_empty():
		# Visitors only look around: no bag, room switching or editing (crafting goes on as anywhere).
		set_dock_open(false);update_room_slots()
		message(tr("%s님의 집에 놀러 왔어요. 가구는 구경만 할 수 있어요.") % visit_name)
	# The owner's front door (lock, guests inside) in their own home while friends can visit.
	preload("res://scripts/home_door_panel.gd").attach(self)
	if api.token.is_empty():
		message(tr("마을에서 로그인한 뒤 공방으로 들어오세요."))
	else: await refresh()

## Public rooms need no studio data; the walker still wears the player's look.
func load_avatar() -> void:
	var response: Dictionary=await api.request("/v1/studio")
	if response.ok and is_instance_valid(hero) and response.data is Dictionary:
		wear_profile(response.data.get("profile",{}))
		show_stars(int(response.data.get("shards",0)))

## The saved look on the room's walker (a no-op when its version is the one already worn).
func wear_profile(profile: Dictionary, animate := false) -> void:
	if not is_instance_valid(hero) or not profile.get("avatar") is Dictionary: return
	AvatarLook.wear(hero,profile.avatar,int(profile.get("version",-1)),animate)
	show_portrait(profile.avatar,int(profile.get("version",-1)))

## The 가방 drawer (I): built once and kept, opened and closed in place (RpgUi.show_drawer), so the
## picked piece, its preview and the developer tabs stay as they were. On the window stack while
## open: I and Esc close it like any window. The location card steps aside while it is open.
## Its slide sound is the drawer's own (RpgUi.show_drawer, only on a real change once the room
## stands: animate is is_processing(), so the arrival's first state stays silent).
func set_dock_open(open: bool) -> void:
	if not is_instance_valid(dock_panel): return
	var shown: bool=open and visit_host.is_empty() and not public_room
	RpgUi.show_drawer(bag,shown,is_processing())
	if shown: fit_bag()
	if is_instance_valid(name_panel): name_panel.visible=not shown and not is_instance_valid(talk_box)
	if is_instance_valid(dock_toggle): dock_toggle.modulate=RpgUi.WARM.lerp(Color.WHITE,0.55) if shown else Color.WHITE

## The location card (top right) unrolls its flavour line on arrival and on every room or floor
## change, then rolls it up again to the place's name.
func show_place_panel() -> void:
	if not is_instance_valid(name_panel) or not is_instance_valid(place_flavour): return
	if name_tween and name_tween.is_valid(): name_tween.kill()
	place_flavour.visible=true
	place_flavour.modulate.a=1.0
	name_tween=create_tween()
	name_tween.tween_interval(6.0)
	name_tween.tween_property(place_flavour,"modulate:a",0.0,0.6)
	name_tween.tween_callback(func():
		if is_instance_valid(place_flavour): place_flavour.visible=false
		if is_instance_valid(name_panel): RpgUi._snug(name_panel))

func row(parent: Node) -> HBoxContainer:
	var r := HBoxContainer.new();r.add_theme_constant_override("separation",8);parent.add_child(r);return r

## Body text on the bag's parchment (wrapping, full width).
func paper_text(parent: Node, value: String, size_px := 13, color := RpgUi.PAPER_INK) -> Label:
	var l := RpgUi.caption(parent,value,size_px,color)
	l.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	return l

## A drop-down on the bag's parchment.
func paper_choice(parent: Node, items: Array) -> OptionButton:
	var o := OptionButton.new();o.size_flags_horizontal=Control.SIZE_EXPAND_FILL;o.focus_mode=Control.FOCUS_NONE
	for value in items: o.add_item(value)
	parent.add_child(o);return o

func build_ui() -> void:
	# Night glass for what floats over the room (the placing tools, the talk and chest cards); the
	# bag drawer and the windows bring the parchment theme with them (RpgUi.drawer, RpgUi.window).
	theme=RpgUi.night_theme()
	# The room fills the whole screen; the HUD floats over it like the village's.
	view_container=SubViewportContainer.new();view_container.stretch=true;view_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(view_container)
	viewport=SubViewport.new();viewport.size=Vector2i(1280,800);viewport.own_world_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.msaa_3d=Viewport.MSAA_4X;view_container.add_child(viewport)
	GameSettings.track_viewport(viewport,view_container)
	view_container.gui_input.connect(view_input)
	# The HUD on the village's 1280x800 design canvas (RpgUi.pin keeps each piece on its edge).
	hud=Control.new();hud.name="Hud";hud.mouse_filter=Control.MOUSE_FILTER_IGNORE
	hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);hud.theme=RpgUi.theme();add_child(hud)
	# Top left: the character frame (portrait, name, the two currencies), the village's own.
	var look := AvatarLook.normalize(session_avatar)
	var portrait := "res://assets/ui/portrait_%s.png" % str(look.get("character","explorer"))
	frame=RpgUi.player_frame(hud,portrait if ResourceLoader.exists(portrait) else "res://assets/ui/portrait_explorer.png","profile")
	frame.panel.name="PlayerFrame"
	frame.name.text=session_name
	frame.name.visible=not session_name.is_empty()
	show_coins(session_coins)
	show_portrait(session_avatar,session_version)
	# Top right, in the village minimap's spot: where you are (building, floor, room).
	build_location_card()
	# Top centre: what just happened (server replies, furniture lines), on the shared toast lane;
	# status_label keeps the last line.
	toast_lane=RpgUi.toast_lane(self,94)
	status_label=Label.new();status_label.name="StatusText";status_label.visible=false;status_label.text=tr("서버에 연결하고 있어요");add_child(status_label)
	# Above the hotbar: the one prompt chip of every place (what the interact key does right here).
	hint_chip=RpgUi.prompt(hud,560);hint_chip.name="HintChip"
	controls_label=hint_chip
	await LoadPace.step("room hud")
	# Bottom centre: the village's hotbar slots for what rooms have (same icons, keys and tooltips)
	# and the ways out, so the bottom left stays the chat's.
	# One sound for the bag slot's press: the drawer's own slide (set_dock_open, RpgUi.show_drawer),
	# not the slot's click a moment before it ("press" "").
	var bar := RpgUi.hotbar(hud,[{"icon":"res://assets/ui/bag.svg","action":"inventory","label":tr("가방"),"press":"","call":func(): set_dock_open(not dock_panel.visible)},
		{"icon":"res://assets/ui/craft.svg","action":"craft","label":tr("제작"),"call":func(): open_craft()},
		{"icon":"res://assets/ui/icons/leave.png","action":"","label":tr("마을로"),"call":func(): leave()},
		{"icon":"res://assets/ui/icons/home.png","action":"","label":tr("내 집"),"call":func(): await change_room("home")},
		{"icon":"res://assets/ui/icons/starseed.png","action":"","label":tr("공방"),"call":func(): await change_room("workshop")}],700,"hotbar")
	bar.name="RoomNav"
	dock_toggle=bar.get_child(0);dock_toggle.name="DockToggle"
	craft_slot=bar.get_child(1);craft_slot.name="CraftSlot"
	leave_button=bar.get_child(2);leave_button.name="LeaveSlot"
	room_buttons=[bar.get_child(3),bar.get_child(4)]
	room_buttons[0].name="HomeSlot";room_buttons[1].name="WorkshopSlot"
	# In-world dressing tools remain visible next to the furniture, not in dev tabs.
	placement_tools=PanelContainer.new();placement_tools.name="PlacementTools"
	placement_tools.position=Vector2(18,128);placement_tools.custom_minimum_size.x=345
	placement_tools.add_theme_stylebox_override("panel",RpgUi.panel_style("night"))
	add_child(placement_tools);placement_tools.visible=false
	var tools := VBoxContainer.new();tools.add_theme_constant_override("separation",8);placement_tools.add_child(tools)
	placement_title=RpgUi.label(tools,tr("가구 놓기"),18,RpgUi.GOLD)
	placement_title.max_lines_visible=1;placement_title.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	placement_feedback=RpgUi.label(tools,tr("빈자리를 골라 주세요"),13,RpgUi.INK,false)
	placement_feedback.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	var rotate_row := row(tools)
	# Any angle: the arrows turn 15°, R 15° (Shift back, Alt/Ctrl 1°) and the wheel 5°.
	turn_readout=ObjectTransform.turn_bar(rotate_row,rotate_placement)
	grid_toggle=CheckButton.new();grid_toggle.text=tr("격자");grid_toggle.button_pressed=true;grid_toggle.focus_mode=Control.FOCUS_NONE;rotate_row.add_child(grid_toggle)
	var confirm_row := row(tools)
	place_button=RpgUi.button(confirm_row,tr("여기에 놓기"),commit_place,"primary");place_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	# One sound for the press: the button's own press kind is the cancel (not a click and a cancel);
	# button_down only carries hover_motion's press sound.
	var cancel_button := RpgUi.button(confirm_row,tr("취소"),cancel_placement)
	for link in cancel_button.button_down.get_connections(): cancel_button.button_down.disconnect(link.callable)
	cancel_button.button_down.connect(func(): RpgUi.sfx("cancel",-8.0))
	await LoadPace.step("room drawer")
	build_bag()

## Top right, in the village minimap's spot: the building's name over a gold rule, the floor and
## room under it, on the objective tracker's night glass. Its flavour line shows for a moment on
## each arrival (show_place_panel).
func build_location_card() -> void:
	name_panel=PanelContainer.new();name_panel.name="PlacePanel";name_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
	var plate := RpgUi.panel_style("night")
	plate.content_margin_top=14;plate.content_margin_bottom=16
	name_panel.add_theme_stylebox_override("panel",plate)
	name_panel.position=Vector2(994,10);name_panel.custom_minimum_size.x=272
	hud.add_child(name_panel)
	var column := VBoxContainer.new();column.add_theme_constant_override("separation",4);column.mouse_filter=Control.MOUSE_FILTER_IGNORE;name_panel.add_child(column)
	var head := HBoxContainer.new();head.add_theme_constant_override("separation",8);head.mouse_filter=Control.MOUSE_FILTER_IGNORE;column.add_child(head)
	place_icon=RpgUi.icon("res://assets/ui/icons/map.png",26);place_icon.size_flags_vertical=Control.SIZE_SHRINK_CENTER;head.add_child(place_icon)
	title_label=RpgUi.label(head,tr("물결빛 공방"),17,RpgUi.GOLD)
	title_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	title_label.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	title_label.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	RpgUi.divider(column,Color(RpgUi.GOLD,.55))
	place_label=RpgUi.label(column,"",14,RpgUi.INK,false)
	place_flavour=VBoxContainer.new();place_flavour.add_theme_constant_override("separation",2);place_flavour.mouse_filter=Control.MOUSE_FILTER_IGNORE;column.add_child(place_flavour)
	subtitle_label=RpgUi.label(place_flavour,tr("상상한 가구를 만들고, 색칠하고, 내 공간에 놓아요"),13,RpgUi.SOFT,false)
	subtitle_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;subtitle_label.custom_minimum_size.x=236
	if BuildMode.developer(): RpgUi.label(place_flavour,tr("개발 화면 · 생성 방식과 모델, 코드, 기록을 검증할 수 있습니다"),11,RpgUi.WARM,false).autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	RpgUi.pin(name_panel,1.0,0.0)

## The location card's picture: the home, the workshop, or a village building.
func location_icon() -> String:
	if public_room: return "res://assets/ui/icons/map.png"
	return "res://assets/ui/icons/home.png" if room=="home" else "res://assets/ui/icons/starseed.png"

## The ways out on the hotbar: 마을로 always; the owner's other room (내 집 / 공방) in their own
## rooms only (a visit or a village building has no room switching).
func update_room_slots() -> void:
	if room_buttons.size()<2: return
	var own: bool=visit_host.is_empty() and not public_room
	RpgUi.show_slot(room_buttons[0],own and room!="home")
	RpgUi.show_slot(room_buttons[1],own and room!="workshop")
	RpgUi.show_slot(dock_toggle,own)

## The frame's leaf coins (잎전) when the village told them (the session); hidden otherwise.
func show_coins(coins: int) -> void:
	if not frame.has("leaves") or not is_instance_valid(frame.leaves): return
	var known := coins>=0
	var coins_row: Node=frame.leaves.get_parent()
	var at: int=frame.leaves.get_index()
	for index in [at-1,at]:
		var part := coins_row.get_child(index) as Control
		if part: part.visible=known
	# The gap before the leaf goes with it.
	var gap := coins_row.get_child(at-2) as Control
	if gap and not gap is Label: gap.visible=known
	if known: RpgUi.count_to(frame.leaves,coins)

## The star-seed balance from a presence reply (social_hud.gd ingest).
func live_shards(shards: int) -> void:
	if is_instance_valid(wallet): wallet.text=tr("별씨 %d") % shards
	show_stars(shards)

## The frame's star-seeds (별씨) after /v1/studio or a resident's reward.
func show_stars(shards: int) -> void:
	if frame.has("stars") and is_instance_valid(frame.stars): RpgUi.count_to(frame.stars,shards)

## The medallion shows the player's own character as dressed (avatar_portrait.gd, as in the
## village); the authored picture of the same character stands in until that drawing is ready.
func show_portrait(avatar: Dictionary, version := -1) -> void:
	if not frame.has("portrait") or not is_instance_valid(frame.portrait): return
	var look := AvatarLook.normalize(avatar)
	if not is_instance_valid(portrait_view):
		portrait_view=preload("res://scripts/avatar_portrait.gd").new()
		add_child(portrait_view)
		portrait_view.rendered.connect(func():
			if frame.has("portrait") and is_instance_valid(frame.portrait): frame.portrait.texture=portrait_view.get_texture())
	if not portrait_view.drawn_key.is_empty(): frame.portrait.texture=portrait_view.get_texture()
	portrait_view.show_look(look,version)

## The bag drawer: the village's parchment drawer (RpgUi.drawer, I), with the furniture list, its
## preview, placing, painting (the village palette) and the craft entry; developer builds add the
## code, part-fitting and craft-history tabs (RpgUi.tab_strip).
func build_bag() -> void:
	bag=RpgUi.drawer(self,tr("가방"),{"action":"inventory","width":RpgUi.DRAWER_W,"icon":"res://assets/ui/bag.svg","id":"room_bag","hidden":true,
		"on_close":func(): set_dock_open(false)})
	dock_panel=bag.root;dock_panel.name="Dock"
	var column: VBoxContainer=bag.body
	# Developer builds: the server's generation mode (the frame shows the star-seeds).
	wallet=paper_text(column,"",12,RpgUi.PAPER_MUTED)
	wallet.visible=BuildMode.developer()
	var entries := [{"id":"own","label":tr("보관함")}]
	if BuildMode.developer(): entries.append_array([{"id":"source","label":tr("동작 코드")},{"id":"fit","label":tr("부품 맞춤")},{"id":"history","label":tr("제작 기록")}])
	bag_strip=RpgUi.tab_strip(column,entries,show_bag_page)
	bag_strip.visible=entries.size()>1
	bag_scroll=ScrollContainer.new();bag_scroll.name="Scroll";bag_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(bag_scroll)
	var pages := VBoxContainer.new();pages.name="Pages";pages.size_flags_horizontal=Control.SIZE_EXPAND_FILL;bag_scroll.add_child(pages)
	pages.minimum_size_changed.connect(fit_bag)
	get_viewport().size_changed.connect(fit_bag)
	# 보관함: the furniture, its preview and what can be done with it.
	var own := VBoxContainer.new();own.name="Own";own.add_theme_constant_override("separation",8);pages.add_child(own)
	bag_pages["own"]=own
	room_capacity=paper_text(own,tr("배치한 가구를 확인하고 있어요"),12,RpgUi.PAPER_MUTED)
	inventory=ItemList.new();inventory.custom_minimum_size.y=150;inventory.fixed_icon_size=Vector2i(26,26);own.add_child(inventory);inventory.item_selected.connect(select_item)
	# A soft tick when the player picks a piece in the bag (selecting from code is silent).
	inventory.item_selected.connect(func(_index: int): RpgUi.sfx("select",-10.0))
	preview_view=SubViewportContainer.new();preview_view.custom_minimum_size.y=150;preview_view.stretch=true;own.add_child(preview_view)
	RpgUi.name_tip(preview_view,tr("미리보기 · 드래그 회전 / 휠 확대"))
	var preview_port := SubViewport.new();preview_port.size=Vector2i(258,150);preview_port.own_world_3d=true;preview_port.render_target_update_mode=SubViewport.UPDATE_ALWAYS;preview_port.msaa_3d=Viewport.MSAA_4X;preview_view.add_child(preview_port)
	preview_stage=Node3D.new();preview_port.add_child(preview_stage)
	var preview_env := WorldEnvironment.new();preview_env.environment=Environment.new();preview_env.environment.background_mode=Environment.BG_COLOR;preview_env.environment.background_color=Color("b5c1ad");preview_env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;preview_env.environment.ambient_light_color=Color.WHITE;preview_env.environment.ambient_light_energy=.12;preview_stage.add_child(preview_env)
	var preview_sun := DirectionalLight3D.new();preview_sun.rotation_degrees=Vector3(-40,-30,0);preview_sun.light_energy=.45;preview_stage.add_child(preview_sun)
	preview_camera=Camera3D.new();preview_camera.projection=Camera3D.PROJECTION_ORTHOGONAL;preview_camera.size=2.9;preview_camera.position=Vector3(2.7,2.2,4);preview_stage.add_child(preview_camera);preview_camera.look_at(Vector3(0,.65,0));preview_camera.current=true
	Art.box(preview_stage,Vector3(0,-.04,0),Vector3(8,.06,8),Color("a9b7a0"))
	preview_view.gui_input.connect(preview_input)
	detail=paper_text(own,tr("가구를 고르면 모습을 살펴볼 수 있어요"),13)
	var actions := row(own)
	for spec in [[tr("놓기"),begin_place,tr("바닥에 배치")],[tr("회수"),retrieve,tr("가방으로 회수")],[tr("사용"),interact_selected,tr("열기·켜기 같은 동작")]]:
		var key := RpgUi.button(actions,spec[0],spec[1],"normal","sm")
		key.size_flags_horizontal=Control.SIZE_EXPAND_FILL
		RpgUi.name_tip(key,spec[2])
	# Furniture with UVs is painted in the painting workspace; the colour rows below stay
	# for furniture made without UVs (whole colour per part).
	paint_button=RpgUi.button(own,tr("색칠하기"),open_painter,"primary")
	paint_button.tooltip_text=tr("붓·채우기·그라데이션으로 표면을 직접 칠해요")
	var tools := row(own)
	var interact_key := RpgUi.button(tools,tr("상호작용"),open_interactions,"normal","sm")
	interact_key.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	RpgUi.name_tip(interact_key,tr("누르거나 다가가면 움직이고 빛나게"))
	var shape_key := RpgUi.button(tools,tr("모양 바꾸기"),open_shape_panel,"normal","sm")
	shape_key.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	shape_key.tooltip_text=tr("가로 · 깊이 · 높이 · 크기 · 좌우 반전")
	part_choice=paper_choice(own,[tr("전체 색칠")])
	var palette := row(own)
	palette.alignment=BoxContainer.ALIGNMENT_CENTER
	for color in RpgUi.PALETTE:
		var hex: String=color
		RpgUi.swatch(palette,hex,false,func(): await paint(hex))
	# A colour of one's own: the picker waits under a ghost key, with the way back to the original.
	var custom_box := VBoxContainer.new();custom_box.add_theme_constant_override("separation",6);own.add_child(custom_box)
	var custom_row := row(custom_box)
	var custom_color := ColorPickerButton.new();custom_color.text=tr("직접 색 고르기");custom_color.edit_alpha=false;custom_color.color=Color("dfa958");custom_color.size_flags_horizontal=Control.SIZE_EXPAND_FILL;custom_color.focus_mode=Control.FOCUS_NONE;custom_row.add_child(custom_color)
	custom_color.popup_closed.connect(func():await paint("#"+custom_color.color.to_html(false)))
	RpgUi.button(custom_row,tr("원래 색 복원"),func():await paint("#ffffff",true),"normal","sm")
	custom_row.visible=false
	var reveal := RpgUi.button(custom_box,tr("직접 고르기"),func(): custom_row.visible=not custom_row.visible,"ghost","sm")
	custom_box.move_child(reveal,0)
	paint_rows=[part_choice,palette,custom_box]
	# The same call to craft as the village bag's; its key cap follows the bindings.
	var craft_entry := RpgUi.button(own,tr("새 물건 제작 의뢰"),func(): open_craft(),"gold")
	RpgUi.name_tip(craft_entry,tr("새 물건 제작 의뢰"),RpgUi.key_text("craft"))
	RpgUi.keycap(craft_entry,"craft",11).position=Vector2(10,9)
	RpgUi.button(own,tr("새로고침"),refresh,"ghost","sm")
	# Built for everyone (the code and history fields are filled on every pick and refresh); only
	# developer builds get the tabs that show them.
	build_dev_pages(pages)
	select_bag_page("own")

## The developer tabs: the generated control code, part fitting and the craft history.
func build_dev_pages(pages: VBoxContainer) -> void:
	var source := VBoxContainer.new();source.name="Source";source.add_theme_constant_override("separation",8);pages.add_child(source)
	bag_pages["source"]=source
	RpgUi.label(source,tr("생성된 조작 함수와 이벤트"),17,RpgUi.PAPER_INK,false)
	paper_text(source,tr("서버가 검사한 숫자 연산·부품 제어 코드입니다. 파일이나 재화에 접근할 수 없습니다."),12,RpgUi.PAPER_MUTED)
	generated_functions=paper_choice(source,[])
	generated_functions.item_selected.connect(load_function_fields)
	function_signature=paper_text(source,"",12)
	function_fields_scroll=ScrollContainer.new();function_fields_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;source.add_child(function_fields_scroll)
	function_fields_box=VBoxContainer.new();function_fields_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;function_fields_scroll.add_child(function_fields_box)
	raw_args_toggle=CheckButton.new();raw_args_toggle.text=tr("개발자용 JSON 입력");source.add_child(raw_args_toggle)
	function_args=LineEdit.new();function_args.text="[]";function_args.placeholder_text=tr("숫자 인수 예: [0.5]");source.add_child(function_args);function_args.visible=false
	raw_args_toggle.toggled.connect(func(enabled):function_args.visible=enabled;function_fields_scroll.visible=not enabled)
	RpgUi.button(source,tr("선택한 생성 함수 호출"),invoke_generated,"normal","sm")
	function_result=paper_text(source,tr("가구를 선택하면 생성된 함수를 검사할 수 있어요."),12)
	code_view=CodeEdit.new();code_view.editable=false;code_view.custom_minimum_size.y=220;source.add_child(code_view)
	var fit := VBoxContainer.new();fit.name="Fit";fit.add_theme_constant_override("separation",8);pages.add_child(fit)
	bag_pages["fit"]=fit
	RpgUi.label(fit,tr("움직이는 부품 맞추기"),17,RpgUi.PAPER_INK,false)
	paper_text(fit,tr("뚜껑·바늘의 위치와 회전축을 조정합니다. 저장하면 내 가구에만 적용되며 원래 설계로 되돌릴 수 있어요."),12,RpgUi.PAPER_MUTED)
	binding_part=paper_choice(fit,[]);binding_part.item_selected.connect(load_binding_fields)
	for spec in [["position",tr("위치 · m"),-3.0,3.0,.01],["rotation",tr("방향 · 도"),-360.0,360.0,1.0],["pivot",tr("회전축 · 중심 기준"),-.5,.5,.01],["size",tr("크기 · m"),.02,3.0,.01]]:
		paper_text(fit,spec[1],13)
		var axes := row(fit);var fields: Array[SpinBox]=[]
		for axis in ["X","Y","Z"]:
			var field := SpinBox.new();field.prefix=axis;field.min_value=spec[2];field.max_value=spec[3];field.step=spec[4];field.size_flags_horizontal=Control.SIZE_EXPAND_FILL;axes.add_child(field);fields.append(field)
			field.value_changed.connect(func(_value):preview_binding_fields())
		binding_fields[spec[0]]=fields
	var fitting_actions := row(fit)
	RpgUi.button(fitting_actions,tr("맞춤 저장"),func():await save_binding(false),"normal","sm")
	RpgUi.button(fitting_actions,tr("원래 설계로"),func():await save_binding(true),"normal","sm")
	RpgUi.button(fit,tr("열기·닫기 등 동작 시험"),interact_selected,"normal","sm")
	binding_hint=paper_text(fit,tr("가구를 고르면 부품 목록이 표시됩니다. 전체 크기는 배치 구역에 맞게 자동 조절됩니다."),12)
	var history := VBoxContainer.new();history.name="History";history.add_theme_constant_override("separation",8);pages.add_child(history)
	bag_pages["history"]=history
	RpgUi.label(history,tr("최근 제작 30건 · 시간 UTC"),17,RpgUi.PAPER_INK,false)
	history_list=ItemList.new();history_list.custom_minimum_size.y=180;history_list.item_selected.connect(select_history);history.add_child(history_list)
	history_detail=paper_text(history,tr("기록을 선택하면 예약·확정 별씨와 확인된 Tripo 비용을 볼 수 있어요."),13)
	RpgUi.button(history,tr("이 설계의 도형 미리보기"),func():await show_design(history_selected),"normal","sm")
	RpgUi.button(history,tr("기록 새로고침"),refresh,"ghost","sm")

## Picks a bag tab (its strip key too).
func select_bag_page(id: String) -> void:
	if is_instance_valid(bag_strip) and bag_strip.visible: RpgUi.select_tab(bag_strip,id)
	show_bag_page(id)

## Shows one bag page; the furniture preview moves along to the pages that use it.
func show_bag_page(id: String) -> void:
	for key in bag_pages: (bag_pages[key] as Control).visible=key==id
	if id!="history" and bag_pages.has(id) and is_instance_valid(preview_view):
		var target: Control=bag_pages[id]
		preview_view.reparent(target)
		target.move_child(preview_view,2)
	fit_bag()

## The bag scrolls once its page would pass the screen's foot (at any UI scale).
func fit_bag() -> void:
	if not is_instance_valid(bag_scroll) or not bag_scroll.is_inside_tree(): return
	var pages: Control=bag_scroll.get_child(0)
	var room := maxf(200.0,get_viewport_rect().size.y-150.0)
	bag_scroll.custom_minimum_size.y=minf(pages.get_combined_minimum_size().y,room)

## A line in the status bar and the room's toast lane. kind is the toast's (RpgUi.toast: info,
## success, warn, error, social), which picks its icon and chime.
func message(value: String, toast := true, kind := "info") -> void:
	# Maintenance or a too-old game: the gate's one screen speaks instead of scattered errors.
	if VersionGate.is_blocked(): return
	value=message_text(value)
	status_label.text=value
	if is_instance_valid(toast_lane) and is_inside_tree():
		if not toast or value.is_empty(): RpgUi.clear_toasts(toast_lane)
		else: RpgUi.toast(toast_lane,value,kind)

## A refusal or a failed request: message() with the soft deny in place of the toast's chime (a kind
## played right before message() stamps RpgUi's toast dedupe, so that chime stays quiet), as the
## village's main.refuse(). Only when message() raises a new toast: a line still on screen just
## refreshes, so a repeated error never stacks denies.
func refuse(value: String) -> void:
	var line := message_text(value)
	if not line.is_empty() and not VersionGate.is_blocked() and is_instance_valid(toast_lane) and is_inside_tree() and not RpgUi.find_toast(toast_lane,line):
		RpgUi.sfx("deny",-6.0)
	message(value)

## The words message() shows: server codes in plain words (player builds), the rest as it is.
func message_text(value: String) -> String:
	value=value.replace("room_render_budget_exceeded",tr("꾸미기 용량이 꽉 찼어요. 가구 일부를 회수하거나 다른 방에 놓아 주세요."))
	if not BuildMode.developer():
		var words := {"insufficient_shards":tr("별씨가 부족해요. 탐험 보상을 모아 보세요."),"stale_version":tr("가구가 바뀌었어요. 다시 골라 주세요."),"stale_runtime_version":tr("가구가 바뀌었어요. 다시 골라 주세요."),"not_found":tr("물건을 찾을 수 없어요. 보관함을 새로고침해 주세요."),"unauthorized":tr("다시 로그인해 주세요."),"geometry_disabled":tr("지금은 새 가구 제작을 준비하고 있어요."),"placement_overlap":tr("다른 가구와 겹쳐요."),"placement_out_of_bounds":tr("벽과 출입문에서 떨어진 곳에 놓아 주세요."),"model_download_failed":tr("가구를 읽지 못했어요. 잠시 뒤 다시 골라 주세요.")}
		words.merge(RoomBuild.BuildRules.server_words())
		var pattern := RegEx.new();pattern.compile("[a-z][a-z0-9]*_[a-z0-9_]+")
		# Only known codes, or a reply that is nothing but a code, are rewritten;
		# player names such as host_841 stay as they are.
		if pattern.search(value) and pattern.search(value).get_string()==value.strip_edges() and not words.has(value.strip_edges()):
			value=tr("지금은 완료하지 못했어요. 잠시 뒤 다시 시도해 주세요.")
		for match_value in pattern.search_all(value):
			var code: String=match_value.get_string()
			if words.has(code): value=value.replace(code,words[code])
	return value

func build_stage() -> void:
	stage=Node3D.new();viewport.add_child(stage)
	var env := WorldEnvironment.new();environment=Environment.new()
	environment.background_mode=Environment.BG_COLOR;environment.background_color=Color("2a2420")
	environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;environment.ambient_light_color=Color("f2e4cb");environment.ambient_light_energy=0.42
	env.environment=environment;stage.add_child(env)
	sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-56,18,0);sun.light_color=Color("fff1dc");sun.light_energy=0.55;sun.shadow_enabled=true
	sun.directional_shadow_max_distance=28;stage.add_child(sun)
	GameSettings.track_light(sun)
	# Animal Crossing style: a perspective camera in front of the open front edge,
	# above the door, looking down toward the back wall and following the walker.
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_PERSPECTIVE;camera.fov=40;camera.near=0.2;camera.far=80
	stage.add_child(camera);camera.current=true
	furniture=Node3D.new();stage.add_child(furniture)
	room_root=Node3D.new();stage.add_child(room_root)
	placement_marker=Art.box(stage,Vector3(0,0.065,0),Vector3(1.95,0.015,1.95),Color("8ccbb1"))
	placement_marker.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	placement_marker.material_override.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	placement_marker.visible=false
	floor_grid=MeshInstance3D.new();floor_grid.name="DecoratingGrid"
	var lines := ImmediateMesh.new();lines.surface_begin(Mesh.PRIMITIVE_LINES)
	for cell in 21:
		var at := -5.0+cell*.5
		lines.surface_add_vertex(Vector3(at,.056,-5));lines.surface_add_vertex(Vector3(at,.056,5))
		lines.surface_add_vertex(Vector3(-5,.056,at));lines.surface_add_vertex(Vector3(5,.056,at))
	lines.surface_end();floor_grid.mesh=lines
	var grid_material := Art.material(Color("f4ead0",.32));grid_material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	grid_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;floor_grid.material_override=grid_material
	floor_grid.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	stage.add_child(floor_grid);floor_grid.visible=false
	build_overlays()
	var span := LoadPace.narrow(0.3, 0.85)
	await build_room()
	LoadPace.span = span
	await LoadPace.step("room walker")
	# Authored character is separate from all player-created furniture.
	if ResourceLoader.exists("res://assets/explorer_b_reference.glb"):
		hero=AvatarLook.walker(session_avatar,session_version);hero.controls_enabled=false;hero.visual_only=true
		stage.add_child(hero)
		if not is_instance_valid(seat):
			seat=RestSeat.new();add_child(seat)
			# The walk up to a seat uses the room's own walking (no doors or stairs on the way).
			seat.mover=func(direction: Vector3, step: float): move_hero(direction,step,false)
			seat.free_check=func(point: Vector3) -> bool: return can_stand(point)
			seat.walk_off=walk_allowed
		seat.hero=hero
		place_hero_at_door()
		if wake_up:
			bed_wake=BedWake.new();add_child(bed_wake)
			if not await bed_wake.lie_down(self): bed_wake.queue_free()

## A furniture's words and the interact key's cap drawn over the room view, pinned to 3D points:
## the night pill of the toasts and prompt, and the key cap of the hotbar (key from the bindings).
func build_overlays() -> void:
	bubble=PanelContainer.new();bubble.name="InteractionBubble";bubble.mouse_filter=Control.MOUSE_FILTER_IGNORE;bubble.visible=false
	var bubble_style := RpgUi.panel_style("pill")
	bubble_style.content_margin_left=18;bubble_style.content_margin_right=18;bubble_style.content_margin_top=9;bubble_style.content_margin_bottom=11
	bubble.add_theme_stylebox_override("panel",bubble_style)
	bubble_label=RpgUi.label(bubble,"",17,RpgUi.INK)
	bubble_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	add_child(bubble)
	hint_label=RpgUi.keycap(self,RpgUi.key_text("interact"),15)
	hint_label.name="InteractHint";hint_label.visible=false

## Keeps an overlay control centred just above a 3D point of the room view.
func pin_overlay(control: Control, anchor: Vector3, lift := 10.0) -> void:
	if not control.visible or not is_instance_valid(camera): return
	if camera.is_position_behind(anchor):
		control.modulate.a=0.0;return
	var at := view_container.global_position+camera.unproject_position(anchor)
	control.reset_size()
	var left := clampf(at.x-control.size.x*0.5,view_container.global_position.x+6,view_container.global_position.x+view_container.size.x-control.size.x-6)
	control.global_position=Vector2(left,maxf(at.y-control.size.y-lift,view_container.global_position.y+6))
	var tail := control.get_node_or_null("Tail") as Polygon2D
	if tail: tail.position=Vector2(clampf(at.x-left,18,control.size.x-18),control.size.y-1)

func place_hero_at_door() -> void:
	if not is_instance_valid(hero): return
	stand_up(false)
	set_floor(0)
	hero.position=Interiors.spawn_point(room_spec)
	# Turned toward the camera, as if just stepping in through the door.
	hero.facing=Vector3.BACK
	update_camera(0.0,true)

## Rebuilds every floor of the current building; the ground floor is shown.
func build_room() -> void:
	for child in room_root.get_children():child.queue_free()
	npcs.clear()
	close_talk(false)
	building_spec=Interiors.spec(room)
	public_room=bool(building_spec.public)
	# Floors are rebuilt: the residents' gifts load again on top.
	gift_nodes.clear();gift_version=-1;gift_epoch+=1
	gift_home=str(building_spec.building) if public_room and NpcGifts.is_gift_home(str(building_spec.building)) else ""
	floor_roots.clear();decor_by_floor.clear()
	for index in building_spec.floors.size():
		LoadPace.done(float(index)/building_spec.floors.size())
		await LoadPace.step("room floor")
		var level := Node3D.new();level.name="Floor_%d" % index;room_root.add_child(level)
		floor_roots.append(level)
		decor_by_floor.append(await Interiors.build(level,building_spec.floors[index]))
	floor_index=-1
	set_floor(0)
	title_label.text=tr("나의 작은 집") if room=="home" else tr("물결빛 공방")
	subtitle_label.text=tr("상상한 가구를 만들고, 색칠하고, 내 공간에 놓아요")
	if not visit_host.is_empty():
		title_label.text=tr("%s님의 집") % visit_name
		subtitle_label.text=tr("놀러 온 집 · 가구는 구경만 할 수 있어요")
	if public_room:
		title_label.text=tr(str(building_spec.name))
		subtitle_label.text=tr(str(building_spec.kind))+"  ·  "+tr(str(building_spec.flavour))
	if is_instance_valid(place_icon): place_icon.texture=load(location_icon())
	update_room_slots()
	set_chip("","")
	show_place_panel()
	apply_daylight(true)
	await LoadPace.step("room residents")
	refresh_residents(true)
	apply_daylight(true)
	if is_instance_valid(bubble): bubble.visible=false
	if is_instance_valid(hint_label): hint_label.visible=false
	front_door=RoomDoor.bind(self,front_door,floor_roots[0] if not floor_roots.is_empty() else null,room)
	update_camera(0.0,true)

## Shows one floor; player-made furniture and visitors live on the ground floor.
func set_floor(index: int) -> void:
	if building_spec.is_empty(): return
	index=clampi(index,0,building_spec.floors.size()-1)
	floor_index=index
	room_spec=building_spec.floors[index]
	decor=decor_by_floor[index]
	for i in floor_roots.size(): floor_roots[i].visible=i==index
	if is_instance_valid(furniture): furniture.visible=index==0
	if is_instance_valid(floor_grid): floor_grid.visible=false
	for entry in peers.values():
		if is_instance_valid(entry.node): entry.node.visible=int(entry.get("floor",0))==index
	current_room=-1
	update_place_label()
	show_place_panel()

func update_place_label() -> void:
	if not is_instance_valid(place_label) or room_spec.is_empty(): return
	var x: float=hero.position.x if is_instance_valid(hero) else 0.0
	var index := Interiors.room_at(room_spec,x)
	if index==current_room: return
	current_room=index
	update_room_audio()
	var parts: PackedStringArray=[]
	if int(room_spec.floors)>1 and not str(room_spec.label).is_empty(): parts.append(tr(str(room_spec.label)))
	var room_name := tr(str(room_spec.rooms[index].name))
	if parts.is_empty() or parts[0]!=room_name: parts.append(room_name)
	place_label.text="  ·  ".join(parts)
	# A new room on the same floor brightens its name in place; a new floor unrolls the card.
	if not RpgUi.calm() and place_label.is_inside_tree():
		place_label.modulate.a=0.25
		place_label.create_tween().tween_property(place_label,"modulate:a",1.0,0.35)

## Stairs, ladders and hatches: a short fade with footsteps, then the other floor.
func travel(record: Dictionary, instant := false) -> void:
	if travelling or not record.has("link") or leaving: return
	travelling=true
	stand_up(false)
	var link: Dictionary=record.link
	var from_floor := floor_index
	if is_instance_valid(bubble): bubble.visible=false
	if not instant and is_instance_valid(hero):
		# Walk onto the stair and up (or down into the hatch); the floors swap
		# under a short fade near the end of the visible part of the climb.
		# Stairs and hatches step on "stairs" through the room's footsteps (_process); a ladder's rungs
		# (no walking) and a room without WorldAudio keep the climbing thuds.
		if not is_instance_valid(world_audio) or record.kind=="ladder": Interiors.play(self,"steps")
		var veil := Transition.of(get_tree())
		var path: Array[Vector3]=Interiors.climb_path(record,hero.position)
		await follow_path(path,1.15,0.62,veil,record.kind=="ladder",record)
		if veil.veil.modulate.a<0.99: await veil.fade_out(0.12)
	set_floor(int(link.to))
	var counterpart := {}
	for other in decor:
		if other.has("link") and int(other.link.to)==from_floor: counterpart=other;break
	if is_instance_valid(hero):
		hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
		hero.position=link.arrive
		hero.facing=Vector3.BACK
	apply_daylight(true)
	if not instant and is_instance_valid(hero) and not counterpart.is_empty():
		# Step off the stair on the new floor instead of appearing on the spot.
		var off: Array[Vector3]=Interiors.arrival_path(counterpart,link.arrive)
		hero.position=off[0]
		update_camera(0.0,true)
		Transition.of(get_tree()).fade_in()
		await follow_path(off,1.15,-1.0,null,counterpart.kind=="ladder",counterpart)
	else:
		update_camera(0.0,true)
		if not instant: await Transition.of(get_tree()).fade_in()
	if is_instance_valid(hero):
		hero.position=link.arrive
		hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
	travelling=false

## Moves the walker along points (with height) at walking pace: the walk clip
## runs from the real displacement, so steps never slide. On a ladder the
## walker faces the rungs and rises with a little bob instead.
func follow_path(points: Array[Vector3], speed: float, fade_at: float, veil: CanvasLayer, ladder := false, record := {}) -> void:
	if points.size()<2 or not is_instance_valid(hero): return
	var lengths: Array[float]=[]
	var total := 0.0
	for i in points.size()-1:
		var length: float=points[i].distance_to(points[i+1])
		lengths.append(length)
		total+=length
	if total<0.001: return
	var face_ladder := Vector3.ZERO
	if ladder and not record.is_empty(): face_ladder=Vector3(0,0,-1).rotated(Vector3.UP,float(record.yaw))
	var travelled := 0.0
	var faded := false
	while travelled<total:
		var delta := get_process_delta_time()
		if delta<=0.0: delta=1.0/60.0
		# One distance along the whole path, so steps keep an even pace across corners.
		var segment := 0
		var along := travelled
		while segment<lengths.size()-1 and along>lengths[segment]:
			along-=lengths[segment];segment+=1
		var a: Vector3=points[segment]
		var b: Vector3=points[segment+1]
		var flat := Vector3(b.x-a.x,0,b.z-a.z)
		var climbing_rungs: bool=ladder and flat.length()<0.05
		travelled=minf(total,travelled+speed*delta*(0.6 if climbing_rungs else 1.0))
		along=travelled
		segment=0
		while segment<lengths.size()-1 and along>lengths[segment]:
			along-=lengths[segment];segment+=1
		var before: Vector3=hero.position
		hero.position=points[segment].lerp(points[segment+1],clampf(along/maxf(lengths[segment],0.0001),0.0,1.0))
		var step := Vector2(hero.position.x-before.x,hero.position.z-before.z)
		if "clip_override" in hero: hero.clip_override=LADDER_CLIP if climbing_rungs else ""
		if climbing_rungs:
			# Hand over hand up the rungs, facing the ladder: the crouched stepping clip, not the
			# walk clip marching in place (no walking pace is reported while nothing moves across).
			hero.facing=face_ladder
			hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
		elif step.length()<0.0005:
			hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
		else:
			hero.facing=Vector3(step.x,0,step.y).normalized()
			# Steps are steep: the stepping clip keeps at least a gentle walking pace.
			hero.external_velocity=step.normalized()*maxf(step.length()/delta,0.9)
			hero.external_motion=step.normalized()
		if fade_at>=0.0 and not faded and veil and travelled/total>=fade_at:
			faded=true
			veil.fade_out()
		await get_tree().process_frame
		if not is_instance_valid(hero): return
	hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
	if "clip_override" in hero: hero.clip_override=""

## Real-time light: windows, sunbeams, ambient, sun and room lamps follow the clock.
func apply_daylight(force := false) -> void:
	if building_spec.is_empty() or not is_instance_valid(environment): return
	var hour := hour_override if hour_override>=0.0 else Daylight.clock_hour()
	daylight_sample=Daylight.sample(hour)
	# Birds and crickets through the walls follow the clock.
	update_room_audio()
	var day: float=daylight_sample.daylight
	var night: float=daylight_sample.night
	var sun_color: Color=daylight_sample.sun_color
	var tint := Color.WHITE.lerp(sun_color,0.55)*lerpf(0.82,1.08,day)
	tint.a=1.0
	for view in get_tree().get_nodes_in_group("window_view"):
		if not room_root.is_ancestor_of(view): continue
		var material: ShaderMaterial=view.material_override
		material.set_shader_parameter("night",clampf(night*1.15,0.0,1.0))
		material.set_shader_parameter("tint",tint)
	for index in floor_roots.size():
		if force or index==floor_index: Interiors.sunbeams(floor_roots[index],building_spec.floors[index],daylight_sample)
	var colors: Dictionary=room_spec.colors
	var theme_ambient := Color(str(colors.ambient))
	environment.ambient_light_color=theme_ambient.lerp(daylight_sample.ambient_color,0.25+0.35*night)
	environment.ambient_light_energy=lerpf(0.31,0.42,day)*(0.86 if room_spec.theme=="observatory" else 1.0)
	environment.background_color=Color("2a2420").lerp(Color("0f1430"),night)
	sun.light_color=sun_color if day>0.05 else Color("a3bcff")
	sun.light_energy=lerpf(0.1,0.55,day)*(0.6 if room_spec.theme=="observatory" else 1.0)
	var awake_rooms := {}
	var sleeping_rooms := {}
	for entry in npcs.values():
		var where := "%d/%d" % [int(entry.floor),Interiors.room_at(building_spec.floors[entry.floor],float(entry.holder.position.x))]
		if entry.state.get("asleep",false): sleeping_rooms[where]=true
		else: awake_rooms[where]=true
	for index in floor_roots.size():
		for lamp in floor_roots[index].find_children("*","OmniLight3D",true,false):
			if not lamp.is_in_group("room_lamp"): continue
			var where := "%d/%d" % [index,int(lamp.get_meta("room",0))]
			var dim := 0.3 if sleeping_rooms.has(where) and not awake_rooms.has(where) else 1.0
			lamp.light_energy=float(lamp.get_meta("base_energy",0.5))*lerpf(0.8,1.45,night)*dim
	var clock := resident_clock()
	for entry in npcs.values():
		if entry.body.has_method("set_night"): entry.body.set_night(clampf(night,0.0,0.6))
		# Shadow folk are villagers by day; a room in view dissolves them at dusk and dawn.
		if entry.body.has_method("set_day"): entry.body.set_day(DayFolk.is_day(str(entry.id),float(clock.hour)),force)
		# Rooms keep their own lamps only: a carried lantern stays unlit indoors.
		var lantern = entry.body.get("lantern_light")
		if lantern is OmniLight3D: lantern.visible=false

func refresh() -> void:
	if public_room or VersionGate.is_blocked(): return
	if not visit_host.is_empty():
		await share_presence()
		return
	if refreshing:return
	refreshing=true
	var response: Dictionary=await api.request("/v1/studio")
	refreshing=false
	if not response.ok:
		refuse(tr("서버 연결을 확인해 주세요 · ")+response.error)
		clear_owned()
		return
	data=response.data
	wallet.text=tr("별씨 %d")%data.shards
	show_stars(int(data.shards))
	if BuildMode.developer(): wallet.text+="  ·  "+(tr("Tripo 실제 생성 가능") if data.geometry_enabled else (tr("개발 공방") if data.llm!="openai" else tr("온라인 공방")))
	# The craft window opens on this at once (its options follow the server's per-craft cap and
	# setup), and a craft still under way is followed again.
	craft_cap=int(data.get("max_tripo_credits",0))
	var tracker := craft_tracker()
	if tracker: tracker.adopt(data)
	wear_profile(data.get("profile",{}))
	update_capacity()
	history_list.clear()
	for entry in data.jobs:history_list.add_item(job_status(entry.state)+tr(" · %d 별씨 · %s")%[entry.cost,Time.get_datetime_string_from_unix_time(int(entry.created)).replace("T"," ")])
	inventory.clear()
	for obj in data.objects:
		var kind := "furniture"
		var title: String=str(obj.name).to_lower()
		if "상자" in title or "chest" in title or "box" in title:kind="chest"
		elif "시계" in title or "clock" in title:kind="clock"
		elif "조명" in title or "lamp" in title:kind="lamp"
		var elsewhere := "" if obj.state!="placed" or obj.room==room else "  · "+tr({"village":"마을","home":"나의 집","workshop":"별씨 공방"}.get(obj.room,str(obj.room)))
		inventory.add_item(("● " if obj.state=="placed" else "○ ")+obj.name+elsewhere,load("res://assets/items/"+kind+".svg"))
	if not selected.is_empty():
		var exists := false
		for obj in data.objects:
			if obj.id==selected.id:selected=obj;exists=true
		if not exists: clear_selection()
	await reload_placed()
	if not selected.is_empty() and is_instance_valid(inspected) and inspected.get_meta("studio",false) and not pending and not placement_mode:
		if selected.get("runtime_version",inspected.runtime_version)!=inspected.runtime_version:
			var selected_id: String=selected.id;var refresh_selection := selection_epoch
			var latest: Dictionary=await api.request("/v1/objects/"+selected_id+"/assembly")
			if refresh_selection!=selection_epoch:return
			if not latest.ok:clear_selection();refuse(tr("선택한 가구를 다시 불러올 수 없어요."));return
			if latest.data.plan!=inspected.manifest.plan:
				if binding_dirty:
					message(tr("다른 곳에서 부품 맞춤이 바뀌었어요. 편집값은 보존했습니다. 가구를 다시 선택하면 최신 설계를 불러옵니다."));return
				for index in data.objects.size():
					if data.objects[index].id==selected_id:await select_item(index);break
			else:
				if not sync_interaction(inspected,latest.data):inspected.accept_event({"state":latest.data.runtime.state,"commands":[],"version":latest.data.runtime.version})
				inspected.paint(latest.data.runtime.colors)

func clear_selection() -> void:
	cancel_placement()
	if is_instance_valid(shape_panel): shape_panel.close()
	selection_epoch+=1;placement_epoch+=1
	binding_dirty=false
	selected={};placement_mode=false
	if is_instance_valid(inspected):inspected.queue_free()
	if is_instance_valid(ghost):ghost.queue_free()
	ghost=null
	if is_instance_valid(code_view):code_view.text=""
	if is_instance_valid(generated_functions):generated_functions.clear()
	if is_instance_valid(function_fields_box):load_function_fields(-1)
	if is_instance_valid(binding_part):binding_part.clear()
	if is_instance_valid(detail):detail.text=tr("가구를 고르면 모습을 살펴볼 수 있어요")

func clear_owned() -> void:
	epoch+=1
	clear_selection()
	for n in furniture.get_children():n.queue_free()
	placed.clear()

func load_item(obj: Dictionary, route := "") -> Node3D:
	# A visitor reads the host's furniture through the read-only guest routes (so do residents' gifts).
	var prefix := route if not route.is_empty() else ("/v1/objects/" if visit_host.is_empty() else "/v1/social/village/objects/")
	var value: Node3D=await Assembly.fetch(api,obj.id,prefix)
	if not value:
		if obj.get("studio",false):return null
		var response: Dictionary=await api.request(prefix+obj.id+"/model",{},HTTPClient.METHOD_GET,true)
		if not response.ok:return null
		value=Loader.load_bytes(response.bytes)
		if value:Loader.paint(value,Color(obj.color))
	# The painted surface (painter/paint_apply.gd), cached by object and paint version.
	if value:await PaintApply.attach(api,value,obj,prefix)
	# The owner's shape edit (object_transform.gd); the size meta and footprint follow it.
	if value:ObjectTransform.apply(value,obj.get("shape"))
	return value

func reload_placed() -> void:
	epoch+=1;var current := epoch
	var desired := {}
	for obj in data.objects:
		if obj.state=="placed" and obj.room==room:desired[obj.id]=obj
	for id in placed.keys():
		if not desired.has(id):placed[id].queue_free();placed.erase(id)
	for obj in data.objects:
		if obj.state!="placed" or obj.room!=room:continue
		if placed.has(obj.id):
			var existing: Node3D=placed[obj.id]
			existing.position=Vector3(obj.x,0.07,obj.z);existing.rotation_degrees.y=obj.rotation
			if existing.get_meta("studio",false) and obj.get("runtime_version")!=null and existing.runtime_version!=obj.runtime_version:
				# A visitor reads the host's state through the guest route (the owner route refused it, so
				# every change of the host's furniture state freed and reloaded the model).
				var fresh: Dictionary=await api.request(("/v1/objects/" if visit_host.is_empty() else "/v1/social/village/objects/")+obj.id+"/assembly")
				if current!=epoch:return
				if fresh.ok and is_instance_valid(existing):
					if fresh.data.plan!=existing.manifest.plan:
						var replacement := await load_item(obj)
						if current!=epoch:
							if replacement:replacement.queue_free()
							return
						if replacement:
							furniture.add_child(replacement);replacement.position=existing.position;replacement.rotation=existing.rotation;placed[obj.id]=replacement
						existing.queue_free()
						if not replacement:placed.erase(obj.id)
						continue
					if not sync_interaction(existing,fresh.data):existing.accept_event({"state":fresh.data.runtime.state,"commands":[],"version":fresh.data.runtime.version})
					existing.paint(fresh.data.runtime.colors)
				elif is_instance_valid(existing):existing.queue_free();placed.erase(obj.id)
			elif not existing.get_meta("studio",false) and existing.get_meta("paint",Color.WHITE)!=Color(obj.color):Loader.paint(existing,Color(obj.color))
			# A shape saved elsewhere (another device, the host while visiting); an open shape window
			# keeps its live draft on screen.
			if is_instance_valid(existing) and not ObjectTransform.same(existing.get_meta("shape",{}),obj.get("shape")) and not (is_instance_valid(shape_panel) and str(shape_panel.object.get("id",""))==str(obj.id)):
				ObjectTransform.apply(existing,obj.get("shape"))
			if is_instance_valid(existing) and str(existing.get_meta("paint_key",""))!=PaintApply.key_for(obj):
				await PaintApply.attach(api,existing,obj,"/v1/objects/" if visit_host.is_empty() else "/v1/social/village/objects/")
				if current!=epoch:return
			continue
		var item := await load_item(obj)
		if current!=epoch:
			if item:item.queue_free()
			return
		if item:
			furniture.add_child(item);item.position=Vector3(obj.x,0.07,obj.z);item.rotation_degrees.y=obj.rotation;placed[obj.id]=item

func select_item(index: int) -> void:
	if pending or index>=data.objects.size():return
	clear_selection();selected=data.objects[index];var id: String=selected.id;var selection_request := selection_epoch
	var item := await load_item(selected)
	if selected.get("id")!=id or selection_request!=selection_epoch:
		if item:item.queue_free()
		return
	if not item:refuse(tr("에셋을 읽을 수 없습니다"));return
	inspected=item;preview_stage.add_child(item);item.position=Vector3.ZERO
	var preview_size: Vector3=item.get_meta("size",Vector3.ONE)
	# The whole object in view, however wide or tall (preview_frame.gd); a lid swings open above it.
	preload("res://scripts/preview_frame.gd").fit(preview_camera,preview_size)
	if item.get_meta("studio",false) and item.pivots.has("lid"):preview_camera.size=maxf(1.9,preview_camera.size)
	detail.text=selected.name+"\n"+(tr("배치됨 · ")+{"home":tr("내 집"),"workshop":tr("공방"),"village":tr("마을")}.get(selected.room,tr("다른 공간")) if selected.state=="placed" else tr("보관 중"))
	part_choice.clear();part_choice.add_item(tr("전체 색칠"))
	if item.get_meta("studio",false):
		generated_functions.clear()
		binding_part.clear()
		for fn in item.manifest.program.functions:generated_functions.add_item(fn)
		load_function_fields(0)
		for p in item.manifest.plan.parts:
			var friendly: String={"body":tr("본체"),"lid":tr("뚜껑"),"base":tr("받침"),"stem":tr("줄기"),"hour_hand":tr("시침"),"minute_hand":tr("분침"),"second_hand":tr("초침"),"face":tr("앞면"),"bulb":tr("전구")}.get(p.id,tr("부분 %d")%part_choice.item_count)
			if str(p.id).begins_with("petal_"):friendly=tr("꽃잎 ")+str(p.id).trim_prefix("petal_")
			part_choice.add_item(str(p.id) if BuildMode.developer() else friendly)
			part_choice.set_item_metadata(part_choice.item_count-1,p.id)
			binding_part.add_item(p.id)
		load_binding_fields(0)
		code_view.text=JSON.stringify(item.manifest.program,"  ")
		if BuildMode.developer():
			detail.text+=tr("\n설계: ")+str(item.manifest.provenance.provider)+tr("\n메시: ")+str(item.manifest.provenance.geometry)
			if item.manifest.provenance.geometry=="tripo":detail.text+=tr("\nTripo 실측: %s 크레딧")%str(item.manifest.provenance.get("tripo_credits_consumed",tr("미기록")))
	else:code_view.text=tr("개발자가 제작한 일반 에셋");generated_functions.clear();load_function_fields(-1)
	update_paint_entry(item)
	message(tr("선택한 가구의 최신 상태를 불러왔어요."))

## Furniture with UVs opens the painting workspace; furniture without keeps the per-part
## colour rows (the workspace would only offer the whole colour with a reason).
func update_paint_entry(item: Node3D) -> void:
	if not is_instance_valid(paint_button):return
	var paintable := PaintApply.has_uvs(item)
	for node in paint_rows:node.visible=not paintable
	paint_button.text=tr("색칠하기") if paintable else tr("전체 색 고르기")
	paint_button.tooltip_text=tr("붓·채우기·그라데이션으로 표면을 직접 칠해요") if paintable else tr("이 물건은 표면 좌표(UV) 없이 만들어져 전체 색만 바꿀 수 있어요.")

func open_painter() -> void:
	if pending or selected.is_empty() or is_instance_valid(painter) or not visit_host.is_empty():return
	if not is_instance_valid(inspected):refuse(tr("가구를 고르면 모습을 살펴볼 수 있어요"));return
	if is_instance_valid(shape_panel):shape_panel.close()
	var parts: Array=[]
	for i in range(1,part_choice.item_count):parts.append([str(part_choice.get_item_metadata(i)),part_choice.get_item_text(i)])
	var id: String=selected.id
	painter=load("res://scripts/painter/painter.gd").new()
	painter.setup(api,selected.duplicate(),inspected,{"views":[viewport],"parts":parts,
		"saved":func(image,version):painter_saved(id,image,version),
		"flat":func(hex: String,part: String,reset: bool):painter_flat(id,hex,part,reset)})
	add_child(painter)

## The painter saved (image) or cleared (null) a piece's paint: the preview and the placed copy show it.
func painter_saved(id: String, image, version) -> void:
	for obj in data.get("objects",[]):
		if obj.id==id:obj.paint_version=version
	if selected.get("id","")==id:selected.paint_version=version
	var key := "" if version==null else id+":"+str(int(version))
	for item in [inspected if selected.get("id","")==id else null,placed.get(id)]:
		if not is_instance_valid(item):continue
		if image==null:PaintApply.clear(item)
		else:PaintApply.apply(item,image,key)
	message(tr("칠한 모습을 저장했어요.") if image!=null else tr("처음 모습으로 되돌렸어요."))

## The interaction editor (interaction_panel.gd) for the selected piece; it borrows the preview copy.
func open_interactions() -> void:
	if pending or selected.is_empty() or is_instance_valid(interaction_panel) or is_instance_valid(painter) or not visit_host.is_empty():return
	if not is_instance_valid(inspected) or not inspected.get_meta("studio",false) or not inspected.has_method("use_interaction"):
		refuse(tr("직접 만든 물건만 상호작용을 넣을 수 있어요."));return
	if selected.get("state","")=="listed":refuse(tr("장터에 올린 물건은 바꿀 수 없어요."));return
	var id: String=selected.id
	interaction_panel=InteractionPanel.new()
	interaction_panel.setup(api,selected.duplicate(),inspected,{"saved":func(reply: Dictionary):interactions_saved(id,reply)})
	add_child(interaction_panel)

## A saved interaction: the placed copy runs it now and the list knows the new runtime version.
func interactions_saved(id: String, reply: Dictionary) -> void:
	for obj in data.get("objects",[]):
		if obj.id==id:obj.runtime_version=reply.runtime.version
	if selected.get("id","")==id:selected.runtime_version=reply.runtime.version
	var value = reply.get("interaction")
	var item: Node3D=placed.get(id)
	if is_instance_valid(item) and item.has_method("use_interaction"):item.use_interaction(value if value is Dictionary else {},reply.program,reply.runtime)

## A copy whose interaction changed elsewhere (another device, a host) runs the new one; true when it did.
func sync_interaction(item: Node3D, fresh: Dictionary) -> bool:
	return item.has_method("sync_interaction") and item.sync_interaction(fresh)

## Whole colour from the painter's fallback panel (furniture without UVs).
func painter_flat(id: String, hex: String, part: String, reset: bool) -> void:
	if selected.get("id","")!=id:return
	part_choice.select(0)
	for i in part_choice.item_count:
		if str(part_choice.get_item_metadata(i))==part:part_choice.select(i)
	await paint(hex,reset)

## 모양 바꾸기: sliders for the selected piece, previewed on the 보관함 view and the placed copy.
func open_shape_panel() -> void:
	if pending or selected.is_empty() or is_instance_valid(painter) or not visit_host.is_empty() or public_room:return
	if is_instance_valid(shape_panel):shape_panel.close();return
	if selected.get("state")=="listed":refuse(tr("장터에 올린 물건은 모양을 바꿀 수 없어요."));return
	if not is_instance_valid(inspected):refuse(tr("가구를 고르면 모습을 살펴볼 수 있어요"));return
	cancel_placement()
	var id: String=selected.id
	shape_panel=ShapePanel.new()
	# On the left, under the room's frame: the bag's preview on the right stays in view.
	shape_panel.setup(api,selected,func(): return [inspected if selected.get("id","")==id else null,placed.get(id)],func(text: String): message(text),{"side":"left","top":128.0})
	shape_panel.saved.connect(func(shape: Dictionary): shape_saved(id,shape))
	add_child(shape_panel)

## A saved shape: the room's list matches the server again.
func shape_saved(id: String, shape: Dictionary) -> void:
	for obj in data.get("objects",[]):
		if obj.id==id:obj.shape=shape
	if selected.get("id","")==id:selected.shape=shape
	message(tr("모양을 바꿨어요.") if not ObjectTransform.is_default(shape) else tr("처음 모양으로 돌아왔어요."))

func load_function_fields(index: int) -> void:
	function_fields.clear()
	function_fields_scroll.custom_minimum_size.y=0
	for child in function_fields_box.get_children():function_fields_box.remove_child(child);child.queue_free()
	function_args.text="[]";function_signature.text=tr("이 물건에는 생성된 조작 함수가 없어요.")
	if not is_instance_valid(inspected) or not inspected.get_meta("studio",false) or index<0 or index>=generated_functions.item_count:return
	var function_name := generated_functions.get_item_text(index)
	var definition: Dictionary=inspected.manifest.program.functions[function_name]
	function_fields_scroll.custom_minimum_size.y=min(3,definition.params.size())*40
	var names: PackedStringArray=[]
	for parameter in definition.params:
		names.append(str(parameter))
		var line := row(function_fields_box)
		paper_text(line,str(parameter),12)
		var field := SpinBox.new();field.min_value=-1000000;field.max_value=1000000;field.step=.01;field.custom_minimum_size.x=150
		line.add_child(field);function_fields.append(field)
		field.value_changed.connect(func(_v):sync_function_args())
	function_signature.text=function_name+"("+", ".join(names)+")"+(tr(" · 입력값 없이 실행") if names.is_empty() else tr(" · 숫자를 입력하고 실행하세요"))
	sync_function_args()

func sync_function_args() -> void:
	var values: Array=[]
	for field in function_fields:values.append(field.value)
	function_args.text=JSON.stringify(values)

func load_binding_fields(index: int) -> void:
	if not is_instance_valid(inspected) or not inspected.get_meta("studio",false) or index<0 or index>=binding_part.item_count:return
	var id := binding_part.get_item_text(index)
	binding_dirty=false
	for p in inspected.manifest.plan.parts:
		inspected.preview_binding(p.id,p)
		if p.id!=id:continue
		for key in binding_fields:
			for axis in 3:binding_fields[key][axis].set_value_no_signal(p[key][axis])
		binding_hint.text=tr("%s · X 좌우 / Y 높이 / Z 앞뒤\n회전축 -0.5는 부품의 뒤·아래·왼쪽 끝, 0.5는 반대쪽 끝입니다.")%id

func preview_binding_fields() -> void:
	if binding_part.item_count==0 or not is_instance_valid(inspected):return
	var edits := {}
	for key in binding_fields:
		edits[key]=[]
		for field in binding_fields[key]:edits[key].append(field.value)
	if edits.size()!=4:return
	inspected.preview_binding(binding_part.get_item_text(binding_part.selected),edits)
	binding_dirty=true
	binding_hint.text=tr("미리보기만 변경됨 · ‘맞춤 저장’을 누르면 서버에 저장합니다.")

func save_binding(reset: bool) -> void:
	if pending or selected.is_empty() or binding_part.item_count==0 or not is_instance_valid(inspected):return
	var id: String=selected.id
	var chosen := binding_part.get_item_text(binding_part.selected)
	var body := {"version":inspected.runtime_version,"part":chosen,"reset":reset}
	if not reset:
		for key in binding_fields:
			body[key]=[]
			for field in binding_fields[key]:body[key].append(field.value)
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+id+"/bindings",api.mutation(body))
	pending=false
	if not reply.ok:refuse(tr("맞춤을 저장하지 못했어요 · ")+reply.error);return
	binding_dirty=false
	if placed.has(id):placed[id].queue_free();placed.erase(id)
	await refresh()
	for i in data.objects.size():
		if data.objects[i].id==id:await select_item(i);break
	for i in binding_part.item_count:
		if binding_part.get_item_text(i)==chosen:binding_part.select(i);load_binding_fields(i);break
	message(tr("원래 부품 설계로 돌아왔어요") if reset else tr("부품 맞춤을 저장했어요"))

func invoke_generated() -> void:
	if pending or selected.is_empty() or generated_functions.item_count==0 or not is_instance_valid(inspected):return
	var args=JSON.parse_string(function_args.text)
	if not args is Array:function_result.text=tr("숫자 배열로 입력해 주세요. 예: [0.5]");return
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/invoke",api.mutation({"version":inspected.runtime_version,"function":generated_functions.get_item_text(generated_functions.selected),"args":args}))
	pending=false
	if reply.ok:
		inspected.accept_event(reply.data)
		if placed.has(selected.id):placed[selected.id].accept_event(reply.data)
		function_result.text=tr("반환값: ")+str(reply.data.result)+tr(" · 명령 %d개")%reply.data.commands.size()
	else:function_result.text=reply.error

# ------------------------------------------------------------------ crafting (craft_window.gd)

## The session's craft follower, with this room as the place that speaks (null before signing in).
func craft_tracker() -> Node:
	var tracker := CraftTracker.of(api)
	if tracker and not is_queued_for_deletion() and tracker.host!=self: tracker.attach(self)
	return tracker

## C or the 제작 slot: the same craft window as the village's, in every room.
func open_craft() -> void:
	if api.token.is_empty() or leaving or VersionGate.is_blocked() or is_instance_valid(craft_window): return
	if placement_mode: cancel_placement()
	if is_instance_valid(talk_box): close_talk(false)
	if is_instance_valid(shape_panel): shape_panel.close()
	craft_window=CraftWindow.new()
	craft_window.setup(self,api)
	add_child(craft_window)
	await craft_window.open()

## The open craft window's form; opens the window first when it is closed (tests and tools).
func craft_panel() -> CraftPanel:
	if not is_instance_valid(craft_window): open_craft()
	return craft

func close_craft() -> void:
	if not is_instance_valid(craft_window): return
	RpgUi.sfx("close",-10.0)
	remove_child(craft_window)
	craft_window.queue_free()
	craft_window=null

## The craft window's line as a toast here; kind as message()'s (optional, info by default).
func craft_say(words: String, kind := "info") -> void:
	message(words,true,kind)

func craft_bag_changed() -> void:
	refresh()

## Finished crafts go down in the player's own home and workshop.
func craft_place_block() -> String:
	if public_room: return CraftWords.place_block("public")
	if not visit_host.is_empty(): return CraftWords.place_block("visit")
	return ""

func craft_place(object_id: String) -> void:
	await place_crafted(object_id)

func generate() -> void:
	await craft_panel().request()

func poll_job() -> void:
	var tracker := craft_tracker()
	if tracker: await tracker.follow()

func confirm_job() -> void:
	await craft_panel().confirm(true)

func cancel_job() -> void:
	await craft_panel().cancel()

## "여기에 놓기" in a room: pick the new object and start placing it here.
func place_crafted(object_id: String) -> void:
	var tracker := craft_tracker()
	if tracker: tracker.clear_done()
	close_craft()
	for attempt in 2:
		for i in data.get("objects",[]).size():
			if data.objects[i].id==object_id:
				inventory.select(i)
				await select_item(i)
				await begin_place()
				return
		await refresh()

func begin_place() -> void:
	if selected.is_empty() or pending:return
	if floor_index!=0:
		# Decorating happens on the ground floor, where the server keeps the furniture.
		stand_up(false);set_floor(0);place_hero_at_door()
	if is_instance_valid(shape_panel):shape_panel.close()
	placement_epoch+=1;var placement_request := placement_epoch;var object_id: String=selected.id
	placement_mode=true;placement_rotation=ObjectTransform.wrap_degrees(float(selected.get("rotation",0)))
	ObjectTransform.show_angle(turn_readout,placement_rotation)
	if is_instance_valid(ghost):ghost.queue_free()
	ghost=null
	var ring := LoadRing.start(self)
	var loaded := await load_item(selected.duplicate(true))
	LoadRing.finish(ring)
	if placement_request!=placement_epoch or not placement_mode or selected.get("id")!=object_id:
		if loaded:loaded.queue_free()
		return
	ghost=loaded
	if ghost:
		stage.add_child(ghost);ghost.position=Vector3(0,0.08,0);ghost.rotation_degrees.y=placement_rotation
		# When moving furniture, hide its old instance until confirmation or cancel.
		if placed.has(object_id):placed[object_id].visible=false
		for mesh in ghost.find_children("*","MeshInstance3D",true,false):
			# Its own materials come back when the ghost becomes the placed piece (adopt_ghost).
			var own: Array=[]
			for index in mesh.mesh.get_surface_count():own.append(mesh.get_surface_override_material(index))
			mesh.set_meta("placing_materials",own)
			for index in mesh.mesh.get_surface_count():
				var source: Material=mesh.get_active_material(index)
				if source is StandardMaterial3D:
					var translucent: StandardMaterial3D=source.duplicate()
					translucent.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
					translucent.albedo_color.a=.62
					mesh.set_surface_override_material(index,translucent)
		place_at=ghost.position
	else:
		placement_mode=false;refuse(tr("가구를 불러오지 못했어요. 다시 선택해 주세요."));return
	# The ghost is up: a lift, and the green/red flip (_process) only sounds on a real change.
	if is_instance_valid(placement_feedback): placement_feedback.set_meta("free",placement_problem(place_at).is_empty())
	RpgUi.sfx("lift",-6.0)
	message(tr("빈 바닥을 가리켜 보세요 · 클릭해서 놓기 · R·휠 돌리기"))

## Turns the ghost by any whole number of degrees; it eases there (_process).
func rotate_placement(degrees: int) -> void:
	if not placement_mode or pending:return
	placement_rotation=ObjectTransform.wrap_degrees(placement_rotation+degrees)
	soft_tick("rotate",-8.0)
	ObjectTransform.show_angle(turn_readout,placement_rotation)

## A UI tick that can come many times a second (grid snap, turning, the green/red flip): at most
## one per `gap` s for each kind, so sweeping the mouse or spinning the wheel stays a soft ratchet.
func soft_tick(kind: String, db: float, gap := 0.08) -> void:
	var now := Time.get_ticks_msec()
	if now-int(tick_times.get(kind,-100000))<int(gap*1000.0): return
	tick_times[kind]=now
	RpgUi.sfx(kind,db)

func cancel_placement() -> void:
	placement_mode=false;placement_epoch+=1
	if is_instance_valid(ghost):ghost.queue_free()
	ghost=null
	if placed.has(selected.get("id")) and is_instance_valid(placed[selected.id]):placed[selected.id].visible=true

func view_input(event: InputEvent) -> void:
	if placement_mode and event is InputEventMouseMotion:
		var origin := camera.project_ray_origin(event.position)
		var direction := camera.project_ray_normal(event.position)
		if absf(direction.y)>0.001:
			var point := origin+direction*(-origin.y/direction.y)
			# A soft tick when the ghost lands on a new 0.5 m cell.
			if not Vector3(roundf(point.x*2)/2,0.08,roundf(point.z*2)/2).is_equal_approx(place_at): soft_tick("snap",-14.0,0.09)
			place_at=Vector3(roundf(point.x*2)/2,0.08,roundf(point.z*2)/2)
			if is_instance_valid(ghost):ghost.position=place_at
	if placement_mode and event is InputEventMouseButton and event.pressed and ObjectTransform.wheel_turn(event)!=0:
		rotate_placement(ObjectTransform.wheel_turn(event));view_container.accept_event();return
	if not placement_mode and event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_RIGHT:RoomBuild.right_click(self,event.position)
	if placement_mode and event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT:await commit_place()
	# A click on a player-made piece within reach uses it, like E.
	elif not placement_mode and event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT and resting.is_empty() and not pending:
		var crafted := nearest_crafted()
		if crafted.is_empty() or not is_instance_valid(camera):return
		var item: Node3D=crafted.item
		var tall: Vector3=item.get_meta("size",Vector3.ONE)
		# Viewport pixels to this container's pixels (the 3D view may render scaled).
		var ratio: Vector2=Vector2(viewport.size)/view_container.size.max(Vector2.ONE)
		var spot: Vector2=camera.unproject_position(item.global_position+Vector3(0,tall.y*0.5,0))/ratio
		if spot.distance_to(event.position)<maxf(70.0,tall.y*60.0):await use_crafted(crafted.id)

func job_status(state: String) -> String:
	if not BuildMode.developer():
		return {"queued":tr("만들기를 기다리고 있어요"),"planning":tr("상상을 설계하고 있어요"),"awaiting_confirmation":tr("완성할 준비가 됐어요"),"building":tr("가구를 만들고 있어요"),"submitting":tr("가구를 만들고 있어요"),"unknown":tr("제작 결과를 확인하고 있어요"),"ready":tr("가구 완성!"),"failed":tr("제작을 완료하지 못했어요 · 맡긴 별씨를 돌려드렸어요"),"cancelled":tr("제작을 취소했어요")}.get(state,tr("제작 상황을 확인하고 있어요"))
	return {"queued":tr("작업 대기"),"planning":tr("설계와 동작 코드 생성"),"awaiting_confirmation":tr("견적 확인 대기"),"building":tr("메시 생성 · 검증 · 조립"),"submitting":tr("Tripo 요청 전송"),"unknown":tr("요청 결과 확인 필요 · 중복 과금 방지를 위해 정지"),"ready":tr("완성"),"failed":tr("제작 실패 · 별씨 환불"),"cancelled":tr("제작 취소")}.get(state,state)

func select_history(index: int) -> void:
	if index<0 or index>=data.jobs.size():return
	var id: String=data.jobs[index].id;history_selected=id
	var response: Dictionary=await api.request("/v1/studio/jobs/"+id)
	if history_selected!=id:return
	if not response.ok:history_detail.text=response.error;return
	var job: Dictionary=response.data;var proof: Dictionary=job.provenance
	history_detail.text=job_status(job.state)+tr("\n별씨 예약/확정: %d\n")%job.cost
	if proof.has("quoted_game_cost"):history_detail.text+=tr("설계 후 최종 견적: %d 별씨\n")%int(proof.quoted_game_cost)
	if proof.get("geometry")=="tripo":
		history_detail.text+=tr("Tripo 예상: %s 크레딧\n확인된 사용: %s 크레딧\n")%[str(proof.get("estimated_tripo_credits",tr("미기록"))),str(proof.get("known_tripo_credits",0))]
		if not proof.get("billing_complete",false):history_detail.text+=tr("일부 작업 비용은 아직 미확인입니다. 0원 확정이 아닙니다.\n")
	else:history_detail.text+=tr("도형 메시 · Tripo 호출 없음\n")
	if job.state=="failed":history_detail.text+=tr("게임 별씨는 환불했지만 이미 실행된 제공사 비용은 남을 수 있습니다.\n")
	if job.get("error"):history_detail.text+=tr("상태 코드: ")+str(job.error)

func preview_design() -> void:
	await show_design(job_id)

## The design as moving shapes (the history tab; the craft window has the same button).
func show_design(id: String) -> void:
	await CraftPanel.preview_design(api,id,self,message)

func preview_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and event.button_mask&MOUSE_BUTTON_MASK_LEFT and is_instance_valid(inspected):
		inspected.rotation.y+=event.relative.x*.012
	if event is InputEventMouseButton and event.pressed:
		if event.button_index==MOUSE_BUTTON_WHEEL_UP:preview_camera.size=maxf(0.6,preview_camera.size-.2)
		if event.button_index==MOUSE_BUTTON_WHEEL_DOWN:preview_camera.size=minf(8.0,preview_camera.size+.2)

func commit_place() -> void:
	if pending or selected.is_empty():return
	var blocked := placement_problem(place_at)
	if not blocked.is_empty():RpgUi.sfx("deny",-6.0);message(blocked);return
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/placement",api.mutation({"version":selected.version,"room":room,"x":place_at.x,"z":place_at.z,"rotation":placement_rotation}))
	pending=false
	if not reply.ok:RpgUi.sfx("deny",-6.0);message(tr("여기에는 놓을 수 없어요 · ")+reply.error);await refresh();return
	adopt_ghost()
	# Set down: a soft thunk under the arrival's own pop and twinkle (Fx.arrive).
	RpgUi.sfx("place",-8.0)
	cancel_placement()
	await refresh()
	message(tr("좋아요! 가구를 놓았어요."))

## The ghost the player put down becomes the placed piece with its own materials, so the refresh
## finds it already there: no second download and no frame without it. It arrives with a pop, or a
## puff of dust when it only moved (fx.gd arrive).
func adopt_ghost() -> void:
	if not is_instance_valid(ghost) or selected.is_empty():return
	var id: String=selected.id;var item: Node3D=ghost
	ghost=null
	var moved: bool=placed.has(id) and is_instance_valid(placed[id])
	if moved:placed[id].queue_free()
	for mesh in item.find_children("*","MeshInstance3D",true,false):
		# get_meta with a null default still reports a missing key: ask first.
		var own=mesh.get_meta("placing_materials") if mesh.has_meta("placing_materials") else null
		if own is Array:
			for index in own.size():mesh.set_surface_override_material(index,own[index])
			mesh.remove_meta("placing_materials")
	item.reparent(furniture)
	item.position=Vector3(place_at.x,0.07,place_at.z);item.rotation_degrees.y=placement_rotation
	placed[id]=item
	Fx.arrive(furniture,item,null,not moved)

func retrieve() -> void:
	if pending or selected.is_empty():return
	pending=true
	var reply: Dictionary=await api.post("/v1/objects/"+selected.id+"/placement",api.mutation({"version":selected.version,"action":"retrieve","room":room}))
	pending=false
	if not reply.ok:refuse(reply.error)
	else:RpgUi.sfx("lift",-6.0);message(tr("보관함으로 옮겼어요."))
	await refresh()

func interact_selected() -> void:
	if pending or selected.is_empty() or not is_instance_valid(inspected) or not inspected.get_meta("studio",false):return
	pending=true
	var response: Dictionary=await api.post("/v1/objects/"+selected.id+"/event",api.mutation({"version":inspected.runtime_version,"event":"click"}))
	pending=false
	if response.ok:
		inspected.accept_event(response.data)
		if placed.has(selected.id):placed[selected.id].accept_event(response.data)
	else:refuse(response.error)

func paint(color: String, reset := false) -> void:
	if pending or selected.is_empty() or not is_instance_valid(inspected):return
	if reset and not inspected.get_meta("studio",false):refuse(tr("기본 가구는 팔레트에서 색을 골라 주세요"));return
	pending=true
	if inspected.get_meta("studio",false):
		var target := "all" if part_choice.selected==0 else str(part_choice.get_item_metadata(part_choice.selected))
		var response: Dictionary=await api.post("/v1/objects/"+selected.id+"/colors",api.mutation({"version":inspected.runtime_version,"part":target,"color":color,"reset":reset}))
		if response.ok:
			inspected.runtime_version=response.data.version;inspected.paint(response.data.colors)
			RpgUi.sfx("paint",-6.0)
			if placed.has(selected.id):placed[selected.id].runtime_version=response.data.version;placed[selected.id].paint(response.data.colors)
		else:refuse(response.error)
	else:
		var response: Dictionary=await api.post("/v1/objects/"+selected.id,api.mutation({"version":selected.version,"action":"paint","color":color}))
		if response.ok:selected.version=response.data.version;Loader.paint(inspected,Color(color));RpgUi.sfx("paint",-6.0)
		else:refuse(response.error)
	pending=false

func change_room(value: String) -> void:
	clear_selection();room=value;await build_room()
	update_capacity()
	place_hero_at_door()
	# The presence follows the room (as _ready sets it): the home shares the walk, the other rooms keep
	# the player present as away. Sent at once, so a friend at the door hears the owner is in
	# (server/home_access.py) and nobody walks into an empty home.
	shared_presence=social_session and room=="home"
	presence_time=ROOM_HEARTBEAT
	show_story()
	await reload_placed()

## The story chapter's letter and goal card in the owner's own home (story_home.gd).
func show_story() -> void:
	if is_instance_valid(story_home): story_home.queue_free()
	story_home=null
	# A resident's request to come to this room (quests.gd: 하늘's observatory at night).
	preload("res://scripts/quests.gd").entered_room(self,room)
	# The treasure chest in the owner's own home (treasure.gd).
	preload("res://scripts/treasure.gd").enter_room(self)
	if room!="home" or public_room or not visit_host.is_empty() or visiting or api.token.is_empty(): return
	story_home=StoryHome.new()
	add_child(story_home)
	story_home.setup(self)

func update_capacity() -> void:
	var capacity: Dictionary=data.get("room_usage",{}).get(room,{})
	room_capacity.text=tr("배치 %d / 30 · 꾸미기 용량 %.0f%%")%[capacity.get("count",0),capacity.get("percent",0)]
	room_capacity.tooltip_text=tr("가구의 복잡도와 이미지 크기에 따라 용량이 달라져요. 꽉 차면 일부 가구를 회수하거나 다른 방으로 옮겨 주세요.")

func _exit_tree() -> void:
	SocialHud.release_place(self)
	if not Engine.has_meta("studio_session"): preload("res://scripts/town.gd").discard_kept()

## This session's social layer (chat, the 함께하기 drawer), bound to this room; null without multiplayer.
func social_hub() -> Node:
	if not social_session or api.token.is_empty(): return null
	var hub := SocialHud.of(api)
	if hub and hub.place != self and is_inside_tree(): hub.bind(self,"room",toast_lane if is_instance_valid(toast_lane) else null)
	return hub

## Where this walker is, for the lists (social_hud.presence_extra).
func social_place() -> String:
	if room=="home": return "home"
	return "workshop" if room=="workshop" else "room"

## A chat line said by someone in this room: a bubble over their head.
func chat_bubble(user_id: String, username: String, text: String) -> void:
	var actor: Node3D=null
	if peers.has(user_id) and is_instance_valid(peers[user_id].node): actor=peers[user_id].node
	elif is_instance_valid(hero) and not user_id.is_empty() and user_id==str(SocialHud.of(api).overview.get("self_id","")): actor=hero
	if actor and actor.visible: SocialHud.bubble(actor,text)

## Shares this walker's spot inside the home and, for visitors, loads the host's
## furniture. Everyone in the same home sees the others (server: mp_presence).
## The floor travels in y (3 m a floor) so walkers only meet on the same floor.
func share_presence() -> void:
	if presence_pending or not is_instance_valid(hero) or api.token.is_empty() or VersionGate.is_blocked(): return
	presence_pending=true
	var heading: float=hero.visual.rotation.y if is_instance_valid(hero.visual) else 0.0
	# The room walker moves by position and reports its pace in external_velocity (report_motion).
	var moving: Vector2=hero.external_velocity
	# The walker's velocity and this game's clock, so the others draw the walk at its true pace
	# (remote_motion.gd); kept-alive like the village's polls.
	var spot := {"scene":"home","x":hero.position.x,"z":hero.position.z,"y":floor_index*3.0,"yaw":wrapf(heading,-PI,PI)}
	if rich_presence: spot.merge({"vx":clampf(moving.x,-30,30),"vz":clampf(moving.y,-30,30),"t":RemoteMotion.now()})
	var hub := social_hub()
	if hub: spot.merge(hub.presence_extra(social_place(),floor_index))
	var response: Dictionary=await api.post_kept("/v1/social/presence",spot,4.0)
	presence_pending=false
	if not response.ok and int(response.get("status",0))==422 and not (hub and hub.presence_refused(response)): rich_presence=false
	if not response.ok or not is_inside_tree(): return
	# The room's chat arrives with the walk (social_hud.gd).
	if hub and is_instance_valid(hub): hub.ingest(response.data)
	preload("res://scripts/home_door_panel.gd").feed(self,response.data)
	# The host walked out, locked us out or sent us out: back to the host's village (home_access).
	var shut: String=preload("res://scripts/home_door.gd").refusal(response.data.get("home")) if not visit_host.is_empty() else ""
	if not shut.is_empty():
		preload("res://scripts/home_door_panel.gd").show_refusal(self,response.data.get("home"),visit_name)
		return
	var space = response.data.get("space")
	if not space is Dictionary: return
	if not visit_host.is_empty():
		if str(space.host_id)!=visit_host:
			# The host left (logged out, quit, lost the connection) or ended the visit: back out to
			# this player's own village, which says why (social.gd announce_visit_end).
			var ended = response.data.get("visit_ended")
			var host_name: String=str(ended.get("host_name",visit_name)) if ended is Dictionary else visit_name
			message(tr("%s님의 마을 방문이 끝나서 내 마을로 돌아가요.")%host_name if not host_name.is_empty() else tr("방문이 끝나 마을로 돌아갑니다."))
			visit_host=""
			leave()
			return
		var objects: Array=space.objects
		for obj in objects: obj.room="home"
		var signature := JSON.stringify(objects)
		if signature!=str(data.get("signature","")):
			data={"objects":objects,"signature":signature}
			await reload_placed()
	var self_id := str(response.data.get("self_id",""))
	var present := {}
	var arrival := RemoteMotion.now()
	var before: Array=peers.keys()
	for record in space.players:
		var version := int(record.get("avatar_version",-1))
		if str(record.id)==self_id:
			# A look saved elsewhere meanwhile reaches the room's walker as well.
			if record.has("avatar_version"): wear_profile({"avatar":record.get("avatar"),"version":version},true)
			continue
		present[record.id]=true
		var level := int(roundf(float(record.get("y",0.0))/3.0))
		if not peers.has(record.id):
			# Built in the visitor's look from the first frame; later changes follow its version.
			var body: Node3D=AvatarLook.walker(record.get("avatar",{}),version)
			body.controls_enabled=false;body.visual_only=true
			body.position=Vector3(record.x,0,record.z)
			stage.add_child(body)
			var plate := Art.label3d(body,str(record.username),Vector3(0,2.05,0),Color("f0dfba"))
			Art.style_nameplate(plate)
			peers[record.id]={"node":body,"motion":RemoteMotion.new()}
			# Someone who just came in walks in through the front door (not those already here).
			if peer_baseline and level==0 and is_instance_valid(front_door): front_door.arrive(peers[record.id])
		AvatarLook.wear(peers[record.id].node,record.get("avatar",{}),version,true)
		SocialHud.host_crown(peers[record.id].node,str(record.id)==str(space.get("host_id","")))
		if int(peers[record.id].get("floor",-1))!=level:
			# Changing floors is a jump, not a glide across the room.
			peers[record.id].motion.reset()
		peers[record.id].motion.push_record(record,Vector3(record.x,0,record.z),arrival)
		peers[record.id]["goal"]=Vector3(record.x,0,record.z)
		peers[record.id]["floor"]=level
		peers[record.id].node.visible=level==floor_index
	for id in peers.keys():
		if not present.has(id):
			# Gone from the home: seen on this floor, they walk out through the door.
			var out: bool=int(peers[id].get("floor",0))==0 and floor_index==0 and is_instance_valid(front_door) and front_door.depart(peers[id])
			if is_instance_valid(peers[id].node) and not out: peers[id].node.queue_free()
			peers.erase(id)
	peer_sounds(before)

## A visitor coming into the home or leaving it: the soft join or leave, as in the village
## (social.gd peer_sounds). The first answer after arriving only takes stock (whoever is already
## here is no news), then one sound per answer at most and at most one every 2 s. A floor change
## keeps the visitor in `peers`, so it is no arrival.
func peer_sounds(before: Array) -> void:
	var settled := peer_baseline
	peer_baseline=true
	if not settled or leaving or Time.get_ticks_msec()-peer_sound_ms<2000: return
	var kind := ""
	if peers.keys().any(func(id): return not before.has(id)): kind="join"
	elif before.any(func(id): return not peers.has(id)): kind="leave"
	if kind.is_empty(): return
	peer_sound_ms=Time.get_ticks_msec()
	RpgUi.sfx(kind,-6.0)

func update_peers(delta: float) -> void:
	for entry in peers.values():
		if not is_instance_valid(entry.node): continue
		entry.motion.update(delta)
		if not (is_instance_valid(front_door) and front_door.walk_peer_in(entry,delta)): entry.motion.apply_to(entry.node)
		# Visitors on this floor walk audibly: quieter, their own voices, falling off with distance.
		if is_instance_valid(world_audio) and entry.node.visible and entry.node.is_inside_tree():
			world_audio.stride("peer%d" % entry.node.get_instance_id(),entry.node.global_position,delta,floor_surface(entry.node.global_position),false,PEER_STEP_DB)

## Outside the home: only "still here" for friends (the answer is not used).
func keep_present() -> void:
	if presence_pending or api.token.is_empty() or VersionGate.is_blocked(): return
	presence_pending=true
	var hub := social_hub()
	var body := {"scene":"away"}
	if hub: body.merge(hub.presence_extra(social_place(),floor_index))
	var response: Dictionary=await api.post_kept("/v1/social/presence",body,4.0)
	presence_pending=false
	if not is_inside_tree() or not hub or not is_instance_valid(hub): return
	# The workshop and the residents' rooms get the chat on the heartbeat's answer.
	if response.ok: hub.ingest(response.data)
	else: hub.presence_refused(response)

## Closing the game in a room: friends see this player leave at once (social.gd does the same in
## the village; server/multiplayer.py leave).
func _notification(what: int) -> void:
	if what==NOTIFICATION_WM_CLOSE_REQUEST and social_session and is_instance_valid(api) and not api.token.is_empty():
		api.farewell("/v1/social/offline")

## Maintenance began or the server ended the session (version_gate.gd): to the title, no session.
func logged_out(_reason: String) -> void:
	if api.token.is_empty(): return
	CraftTracker.end(api)
	SocialHud.end(api)
	api.token=""
	leaving=true
	var cloud := get_node_or_null("/root/CloudPrefs")
	if cloud: cloud.stop()
	Engine.remove_meta("studio_session")
	var veil := Transition.of(get_tree())
	veil.loading("", "start")
	await veil.fade_out()
	get_tree().change_scene_to_file("res://scenes/main.tscn")

func leave() -> void:
	var veil := Transition.of(get_tree())
	if veil.veil.modulate.a > 0.5 or leaving: return
	# The welcome letter first (story_home.gd): the door stays shut until it is read.
	if visit_host.is_empty() and is_instance_valid(story_home) and story_home.keeps_door_shut():
		story_home.hold_at_door()
		return
	leaving=true
	stand_up(false)
	# The walker keeps walking out through the doorway while the veil falls.
	if floor_index==0 and is_instance_valid(hero):
		walk_out=Vector3(float(room_spec.get("door_x",0.0)),0,float(room_spec.size.y)*0.5+1.6)
	if floor_index==0 and is_instance_valid(front_door) and is_instance_valid(front_door.hinge): front_door.hold("walker",5.0)
	else: veil.play_door("open",room)
	veil.loading(tr("%s님의 마을") % visit_name if not visit_host.is_empty() else tr("다섯 섬 마을"),"","village")
	# The room's sound goes with the light: the beds fade with the veil, the music fades across the
	# scene change while the village's own track comes in (no hard cut).
	fade_room_audio(Transition.OUT)
	hand_off_music()
	await veil.fade_out()
	if is_instance_valid(hero):
		hero.external_velocity=Vector2.ZERO;hero.external_motion=Vector2.ZERO
	var session := {"token":api.token,"url":api.base_url,"room":room}
	# The village walker wears the look this room showed from its first frame.
	if is_instance_valid(hero): session.profile={"avatar":hero.avatar.duplicate(true),"version":int(hero.look_version)}
	Engine.set_meta("studio_session",session)
	get_tree().change_scene_to_file("res://scenes/main.tscn")

func _unhandled_key_input(event: InputEvent) -> void:
	if is_instance_valid(painter) or is_instance_valid(interaction_panel):return
	# Placing: R turns 15° (Shift back, Alt/Ctrl a single degree); a held key keeps turning.
	if placement_mode and event is InputEventKey and event.is_pressed() and GameSettings.canonical_key(event)==KEY_R and not is_instance_valid(talk_box):
		rotate_placement(ObjectTransform.key_turn(event));get_viewport().set_input_as_handled();return
	if not event.is_pressed() or event.is_echo():return
	# Rebinding-aware: a key bound to Interact reports KEY_E (game_settings.gd).
	var key := GameSettings.canonical_key(event)
	if is_instance_valid(talk_box):
		match key:
			KEY_E,KEY_SPACE,KEY_ENTER: advance_talk()
			KEY_ESCAPE: close_talk()
			KEY_1,KEY_2,KEY_3,KEY_4,KEY_5,KEY_6,KEY_7,KEY_8,KEY_9:
				var index: int=event.physical_keycode-KEY_1
				if talk_page>=talk_lines.size()-1 and index<talk_choices.size(): pick_talk(talk_choices[index])
		get_viewport().set_input_as_handled()
		return
	var focus := get_viewport().gui_get_focus_owner()
	var typing: bool = focus is LineEdit or focus is TextEdit
	# The craft window (on the window stack, as in the village) takes the keys while open; Esc closes
	# it (also while typing), and so does its own key C when no field is being typed in.
	if is_instance_valid(craft_window):
		if event.physical_keycode==KEY_ESCAPE or (not typing and RpgUi.closes_window(craft_window.window,key)):
			close_craft()
			get_viewport().set_input_as_handled()
		return
	# Any other shared window over the room: Esc or its own opening key closes it.
	var top := RpgUi.top_window()
	if not top.is_empty() and str(top.get("kind",""))!="dialogue":
		if event.physical_keycode==KEY_ESCAPE or (not typing and RpgUi.closes_window(top,key)):
			if RpgUi.close_top(top):
				get_viewport().set_input_as_handled()
				return
		if bool(top.get("modal",false)): return
	if typing:return
	if event.physical_keycode==KEY_ESCAPE:
		if placement_mode:
			RpgUi.sfx("cancel",-8.0)
			cancel_placement()
		elif not resting.is_empty(): stand_up()
		elif is_instance_valid(dock_panel) and dock_panel.visible: set_dock_open(false)
		else: PauseMenu.open(self)
	# HUD key (U): fold every HUD panel at once (or open them all again), as in the village.
	if key==KEY_U:
		RpgUi.toggle_all_folds()
		return
	if key==KEY_V:
		RoomBuild.toggle_pass(self)
		return
	# The village's keys: C the craft window, I the bag (here the drawer with the bag).
	if key==KEY_C:
		open_craft()
		return
	if key==KEY_I and is_instance_valid(dock_toggle) and dock_toggle.visible:
		set_dock_open(not dock_panel.visible)
	if key==KEY_E:
		if not resting.is_empty():stand_up()
		elif is_instance_valid(hero) and floor_index==0 and Interiors.near_door(room_spec,hero.position):leave()
		else:interact_nearest()

func interact_nearest() -> void:
	if not is_instance_valid(hero) or pending or travelling:return
	var list := decor_candidates()
	var pick := next_pick(list.size())
	var fixed: Dictionary=list[pick] if not list.is_empty() else {}
	var crafted := nearest_crafted()
	var nearest: String=crafted.get("id","");var distance: float=crafted.get("distance",2.3)
	# Player-made furniture keeps its server interaction; room furniture talks locally.
	if not fixed.is_empty() and (nearest.is_empty() or float(fixed.distance)+1.0<distance):
		pick_cycle=pick;pick_spot=hero.position;pick_time=Time.get_ticks_msec()*0.001
		use_decor(fixed.record)
		return
	if nearest.is_empty():return
	await use_crafted(nearest)

## The player-made piece within reach on this floor (the host's, on a visit): {id, item, distance}.
func nearest_crafted() -> Dictionary:
	var best := {};var distance := 2.3
	if not is_instance_valid(hero) or public_room or floor_index!=0:return best
	for id in placed:
		var item: Node3D=placed[id]
		if not is_instance_valid(item):continue
		var d: float=hero.position.distance_to(item.position)
		if d<distance:distance=d;best={"id":id,"item":item,"distance":d}
	return best

## E on a player-made piece: a seat or a bed (상호작용 · 쉬기) takes the walker, and its click
## behaviour runs - on the server for the owner, on this screen only for a visitor.
func use_crafted(id: String) -> void:
	var item: Node3D=placed.get(id)
	if not is_instance_valid(item):return
	var kind: String=str(item.get("rest")) if item.has_method("use_interaction") else ""
	if kind=="sit" or kind=="lie":rest_on_crafted(item,kind)
	if not visit_host.is_empty():
		if item.has_method("local_event"):item.local_event("click")
		return
	if selected.get("id","")==id and is_instance_valid(inspected):
		await interact_selected();return
	for i in data.get("objects",[]).size():
		if data.objects[i].id==id:await select_item(i);await interact_selected();return

## Sits on or lies down on a crafted piece the owner marked as a seat or a bed.
func rest_on_crafted(item: Node3D, kind: String) -> void:
	if not is_instance_valid(seat) or not resting.is_empty(): return
	hook_seat_sounds()
	seat.crafted(item,kind)
	if not resting.is_empty(): seat_sound("cushion")

## The room seat driver's own sounds (IxDriver.sound, as the village's main.seat_sound): a soft deny
## when the walk up gives up (the way blocked, out of reach, too long) and a rocking or swinging
## piece's creak where its sway turns. The weight landing and getting up stay with seat_sound
## (on_settled / on_done), the feet with room_steps.
func hook_seat_sounds() -> void:
	if not is_instance_valid(seat): return
	var driver: Node=seat.ensure_driver()
	if is_instance_valid(driver) and "sound" in driver: driver.sound=seat_event_sound

func seat_event_sound(event: String, info: Dictionary) -> void:
	if leaving or not is_inside_tree(): return
	match event:
		"refused": RpgUi.sfx("deny",-10.0)
		"rock":
			# The driver spaces the creaks 0.8-1.3 s apart; a wider sway is a little louder, and the
			# pitch drifts so no two sound alike. Rope (a hammock, a swing) sighs instead of creaking.
			if DisplayServer.get_name()=="headless": return
			var amount := clampf(float(info.get("amount",1.0)),0.0,1.0)
			var at: Vector3=info.get("at",Vector3.INF)
			Fx.sound(self,"field/hammock" if str(info.get("material",""))=="rope" else "field/wood_creak",at,randf_range(0.95,1.05),-12.0+4.0*amount)

## The seat's sound for sitting or lying down: played when the walker settles on the seat (the seat
## driver's on_settled, ix/ix_driver.gd), and a softer one when it gets up again (on_done after a
## settle). Without the driver (rest_seat.gd's fallback settles at once) it plays now, and only when
## a seat took the walker: nothing sounds on the E press of a seat that could not be reached.
func seat_sound(sound: String) -> void:
	var driver: Node=seat.driver if is_instance_valid(seat) else null
	if not is_instance_valid(driver) or not driver.busy() or driver.seated():
		if not resting.is_empty(): Interiors.play(self,sound)
		return
	var target: Node=driver.target
	var state := {"settled":false,"up":false}
	driver.on_settled=func():
		if state.settled or not is_instance_valid(driver) or driver.target!=target: return
		state.settled=true
		Interiors.play(self,sound)
	driver.on_done=func():
		if not state.settled or state.up: return
		state.up=true
		Interiors.play(self,sound,-15.0)

## Everything within reach, best first: the piece the walker faces and is closest
## to leads; pieces hanging above others (a clock over a wardrobe, a window over
## the sink) follow, and pressing E again on the same spot moves on to them.
func decor_candidates() -> Array:
	var found: Array=[]
	if not is_instance_valid(hero): return found
	var facing: Vector3=hero.facing
	facing.y=0
	for record in decor:
		if not record.interactive or not is_instance_valid(record.node): continue
		var local: Vector3=(hero.position-record.center).rotated(Vector3.UP,-float(record.yaw))
		var half: Vector2=record.half
		var gap := Vector2(maxf(0.0,absf(local.x)-half.x),maxf(0.0,absf(local.z)-half.y)).length()
		var reach := 1.35 if record.mounted else 0.85
		if gap>=reach: continue
		var toward: Vector3=record.center-hero.position
		toward.y=0
		var score := gap-0.45*(facing.normalized().dot(toward.normalized()) if toward.length()>0.01 and facing.length()>0.01 else 0.0)
		found.append({"record":record,"distance":gap,"score":score})
	found.sort_custom(func(a,b): return a.score<b.score)
	return found

## Which candidate the next E press uses (cycling while the walker stays put).
func next_pick(count: int) -> int:
	if count<=0 or not is_instance_valid(hero): return 0
	if hero.position.distance_to(pick_spot)<0.25 and Time.get_ticks_msec()*0.001-pick_time<8.0: return (pick_cycle+1)%count
	return 0

## The piece of room furniture the next E press would use, as {record, distance}.
func nearest_decor() -> Dictionary:
	var list := decor_candidates()
	if list.is_empty(): return {}
	return list[next_pick(list.size())]

func use_decor(record: Dictionary) -> void:
	last_used=record
	if is_instance_valid(story_home) and story_home.use(record): return
	if preload("res://scripts/treasure.gd").use_home(self,record): return
	if record.kind=="gift":
		use_gift(record)
		return
	if record.get("storage",false) and not gift_home.is_empty() and not api.token.is_empty():
		open_storage(record)
		return
	var who := str(record.get("id","")) if record.kind=="resident" else str(record.get("occupant",""))
	if not who.is_empty() and npcs.has(who):
		talk_to(who,record)
		return
	interact_count+=1
	var hour: float=daylight_sample.get("hour",12.0)
	var result: Dictionary=Interiors.interact(record,interact_count,hour,str(building_spec.get("outlook","meadow")))
	if result.is_empty(): return
	var action: String=result.get("action","look")
	if action=="travel" and travel_enabled:
		travel(record)
		return
	if is_instance_valid(hero) and action!="sit" and action!="lie": hero.face_point(record.center)
	if result.has("chip"): say(str(result.chip),record)
	elif not result.get("quiet",false): say(str(result.text),record)
	var sound: String=result.get("sound","pop")
	var seated := action=="sit" or action=="lie"
	if sound=="piano":
		tone_player.stream=Interiors.piano_stream(interact_count)
		tone_player.play()
	elif not seated:
		Interiors.play(self,sound)
	play_effect(action,record)
	# Sitting and lying: the cushion sounds when the walker settles on it, not on the E press.
	if seated and sound!="piano": seat_sound(sound)

## A short speech bubble above the furniture, mirrored in the status bar.
func say(text: String, record: Dictionary) -> void:
	message(text,false)
	if not is_instance_valid(bubble): return
	var size: Vector3=record.get("size",Vector3.ONE)
	var top: float=record.node.global_position.y+(size.y*0.5 if record.mounted else size.y)
	var long_line := text.length()>28
	bubble_label.text=text
	bubble_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART if long_line else TextServer.AUTOWRAP_OFF
	bubble_label.custom_minimum_size.x=340 if long_line else 0
	bubble_anchor=Vector3(record.center.x,minf(top+0.25,float(room_spec.height)),record.center.z)
	bubble.modulate.a=1.0;bubble.visible=true
	hint_label.visible=false
	pin_overlay(bubble,bubble_anchor,14)
	if bubble_tween and bubble_tween.is_valid(): bubble_tween.kill()
	bubble_tween=create_tween()
	bubble_tween.tween_interval(3.4)
	bubble_tween.tween_property(bubble,"modulate:a",0.0,0.45)
	bubble_tween.tween_callback(func(): bubble.visible=false)

## Shows the interact key's cap over whatever the walker can use (furniture or the door) and
## the matching prompt chip above the hotbar; with nothing in reach the chip steps back.
func update_hint() -> void:
	var key := RpgUi.key_text("interact")
	if not is_instance_valid(hint_label) or not is_instance_valid(hero) or placement_mode or travelling:
		if is_instance_valid(hint_label): hint_label.visible=false
		set_chip("","")
		return
	if not resting.is_empty():
		hint_label.visible=false
		set_chip("interact",tr("일어나기"))
		return
	if floor_index==0 and Interiors.near_door(room_spec,hero.position):
		hint_label.text=key
		hint_anchor=Vector3(float(room_spec.get("door_x",0.0)),1.45,float(room_spec.size.y)*0.5+0.3)
		hint_label.visible=true
		set_chip("interact",tr("마을로 나가기"))
		return
	var fixed := nearest_decor()
	if fixed.is_empty():
		# A player-made piece that does something (or seats/beds) shows its key too.
		var crafted := nearest_crafted()
		var piece: Node3D=crafted.get("item")
		if is_instance_valid(piece) and piece.has_method("use_interaction") and (not piece.vm.program.get("events",{}).is_empty() or str(piece.rest)!=""):
			var tall: Vector3=piece.get_meta("size",Vector3.ONE)
			hint_label.text=key
			hint_anchor=Vector3(piece.position.x,minf(piece.position.y+tall.y+0.15,float(room_spec.height)),piece.position.z)
			hint_label.visible=not bubble.visible
			set_chip("interact",{"sit":tr("앉기"),"lie":tr("눕기")}.get(str(piece.rest),tr("사용")))
			return
		hint_label.visible=false
		set_chip("","")
		return
	var record: Dictionary=fixed.record
	var size: Vector3=record.get("size",Vector3.ONE)
	var top: float=record.node.global_position.y+(size.y*0.5 if record.mounted else size.y)
	var up: bool=record.has("link") and int(record.link.to)>floor_index
	hint_label.text=key+("  ▲" if up else ("  ▼" if record.has("link") else ""))
	hint_anchor=Vector3(record.center.x,minf(top+0.15,float(room_spec.height)),record.center.z)
	hint_label.visible=not bubble.visible
	var who := str(record.get("id","")) if record.kind=="resident" else str(record.get("occupant",""))
	if not who.is_empty() and npcs.has(who):
		set_chip("interact",tr("쉿, 자고 있어요") if npcs[who].state.get("asleep",false) else tr("말 걸기"))
	elif record.has("link"): set_chip("interact",(tr("▲ 계단 오르기") if up else tr("▼ 계단 내려가기")))
	elif is_instance_valid(story_home) and not story_home.chip(record).is_empty(): set_chip("interact",story_home.chip(record))
	elif not preload("res://scripts/treasure.gd").home_chip(self,record).is_empty(): set_chip("interact",preload("res://scripts/treasure.gd").home_chip(self,record))
	else: set_chip("interact",tr(str(Interiors.ACTION_HINTS.get(str(Interiors.ACTIONS.get(str(record.kind),"look")),"살펴보기"))))

## The prompt chip (RpgUi.prompt, y 560 like every place): the action's key as a cap (from the
## bindings, so a rebind shows at once) and what it does; hidden with nothing to do, during a talk
## and when interaction prompts are switched off.
func set_chip(action: String, text: String) -> void:
	if not is_instance_valid(hint_chip): return
	var value := "" if action.is_empty() or text.is_empty() else RpgUi.key_text(action)+"  "+text
	if is_instance_valid(hint_label): hint_label.modulate.a=1.0 if GameSettings.show_prompts() else 0.0
	if str(hint_chip.get_meta("prompt",""))!=value:
		RpgUi.set_prompt(hint_chip,value)
	hint_chip.visible=not value.is_empty() and GameSettings.show_prompts() and not is_instance_valid(talk_box)

## Camera framing: in front of the open front edge, above the door side, framing
## the room the walker is in (closer than outside); distance follows that room.
func camera_rig() -> Dictionary:
	var size: Vector2=room_spec.get("size",Vector2(10,10))
	var rooms: Array=room_spec.get("rooms",[{"x0":-size.x*0.5,"x1":size.x*0.5}])
	var index := Interiors.room_at(room_spec,hero.position.x) if is_instance_valid(hero) and not room_spec.is_empty() else 0
	var x0: float=rooms[index].x0
	var x1: float=rooms[index].x1
	var aspect := 1.5
	if is_instance_valid(viewport) and viewport.size.y>0: aspect=float(viewport.size.x)/float(viewport.size.y)
	var pitch := deg_to_rad(30.0)
	var width := x1-x0
	# The view is full screen (1280x800): a little further back than the old
	# letterboxed view so a whole room still fits around the walker.
	var distance := clampf((4.4+maxf(size.y,width*0.85)*0.6)*1.2,9.0,13.4)
	var half_width := distance*tan(deg_to_rad(camera.fov*0.5))*aspect
	var limit := maxf(width*0.5+0.4-half_width*0.92,minf(0.9,width*0.09))
	return {"offset":Vector3(0,sin(pitch),cos(pitch)),"distance":distance,"centre":(x0+x1)*0.5,"x_limit":limit}

func update_camera(delta: float, snap := false) -> void:
	if not is_instance_valid(camera) or room_spec.is_empty(): return
	var size: Vector2=room_spec.size
	var rig := camera_rig()
	var at: Vector3=hero.position if is_instance_valid(hero) else Interiors.spawn_point(room_spec)
	var limit: float=rig.x_limit
	var centre: float=rig.centre
	var target := Vector3(centre+clampf((at.x-centre)*0.65,-limit,limit),0.85+maxf(at.y,0.0)*0.6,clampf(lerpf(-size.y*0.12,at.z,0.55),-size.y*0.5+1.8,size.y*0.5-1.4))
	var weight := ControllerProfile.damping(3.2,delta)
	cam_focus=target if snap else cam_focus.lerp(target,weight)
	cam_distance=float(rig.distance) if snap else lerpf(cam_distance,float(rig.distance),weight)
	camera.position=cam_focus+(rig.offset as Vector3)*cam_distance
	camera.look_at(cam_focus)
	# With the drawer open the room slides left so it stays framed beside it.
	var aspect := float(viewport.size.x)/maxf(1.0,float(viewport.size.y))
	var shift := 0.16*2.0*cam_distance*tan(deg_to_rad(camera.fov*0.5))*aspect if is_instance_valid(dock_panel) and dock_panel.visible else 0.0
	camera.h_offset=shift if snap else lerpf(camera.h_offset,shift,weight)

func proximity() -> void:
	if proximity_pending or pending or not is_instance_valid(hero):return
	# Visitors play the host's interactions on this screen only.
	if not visit_host.is_empty():
		for id in placed:
			var guest_item: Node3D=placed[id]
			if not is_instance_valid(guest_item) or not guest_item.get_meta("studio",false) or not guest_item.has_method("local_event"):continue
			var near_guest: bool=hero.position.distance_to(guest_item.position)<(2.5 if guest_item.nearby else 1.8)
			if near_guest!=guest_item.nearby:guest_item.local_event("near" if near_guest else "leave")
		return
	proximity_pending=true
	var snapshot := placed.keys()
	for id in snapshot:
		if not placed.has(id):continue
		var item: Node3D=placed[id]
		if not is_instance_valid(item) or not item.get_meta("studio",false):continue
		var distance: float=hero.position.distance_to(item.position)
		var near_now: bool=distance<(2.5 if item.nearby else 1.8)
		if near_now==item.nearby:continue
		var response: Dictionary=await api.post("/v1/objects/"+id+"/event",api.mutation({"version":item.runtime_version,"event":"near" if near_now else "leave"}))
		if not is_instance_valid(item):continue
		if response.ok:
			item.nearby=near_now;item.accept_event(response.data)
			if selected.get("id")==id and is_instance_valid(inspected) and inspected.manifest.plan==item.manifest.plan:
				inspected.nearby=near_now;inspected.accept_event(response.data)
			if selected.get("id")==id and is_instance_valid(inspected):inspected.accept_event(response.data)
		elif response.get("status")==409:
			var fresh: Dictionary=await api.request("/v1/objects/"+id+"/assembly")
			if fresh.ok and is_instance_valid(item):item.runtime_version=fresh.data.runtime.version
		else:
			item.queue_free();placed.erase(id)
	proximity_pending=false

func _process(delta: float) -> void:
	if is_instance_valid(placement_tools):
		placement_tools.visible=placement_mode
		if placement_mode:
			var problem := placement_problem(place_at)
			# The spot turning free or blocked: a soft tick, only on a flip (and not in a flurry).
			if bool(placement_feedback.get_meta("free",true))!=problem.is_empty():
				placement_feedback.set_meta("free",problem.is_empty())
				soft_tick("valid" if problem.is_empty() else "invalid",-10.0,0.15)
			placement_title.text=tr("놓을 자리 고르기 · ")+str(selected.get("name",tr("가구")))
			placement_feedback.text=tr("이곳에 놓을 수 있어요 · %d°")%placement_rotation if problem.is_empty() else problem
			placement_feedback.modulate=RpgUi.LEAF_LIGHT if problem.is_empty() else RpgUi.ACCENT.lightened(0.45)
			place_button.disabled=pending or not problem.is_empty() or not is_instance_valid(ghost)
			if is_instance_valid(ghost):ghost.rotation.y=ObjectTransform.ease_yaw(ghost.rotation.y,placement_rotation,delta)
	if is_instance_valid(floor_grid):floor_grid.visible=placement_mode and grid_toggle.button_pressed
	if is_instance_valid(placement_marker):
		placement_marker.visible=placement_mode
		placement_marker.position=Vector3(place_at.x,0.065,place_at.z)
		placement_marker.material_override.albedo_color=Color("87c7a7",.32) if placement_problem(place_at).is_empty() else Color("d27566",.32)
	auth_time+=delta
	if visit_host.is_empty() and not public_room and not api.token.is_empty():
		if auth_time>20:auth_time=0;refresh()
	presence_time+=delta
	if shared_presence or not visit_host.is_empty():
		# On schedule, or as soon as a slow answer is in (not skipped while one is under way).
		if presence_time>=ROOM_PRESENCE and not presence_pending:
			presence_time=0
			share_presence()
	elif social_session and presence_time>=ROOM_HEARTBEAT and not presence_pending:
		presence_time=0
		keep_present()
	update_peers(delta)
	proximity_time+=delta
	if proximity_time>0.35:proximity_time=0;proximity();gift_proximity()
	gift_time+=delta
	if gift_time>3.0:gift_time=0;refresh_gifts()
	if not is_instance_valid(hero):return
	# A stair climb (follow_path) sets the walker's motion just before this runs each
	# frame; clearing it here left the idle pose gliding up the steps.
	if not travelling:
		hero.external_motion=Vector2.ZERO
		hero.external_velocity=Vector2.ZERO
	hint_time+=delta
	if hint_time>0.15:hint_time=0;update_hint();update_place_label();update_name_plates()
	daylight_time+=delta
	if daylight_time>20.0:daylight_time=0;apply_daylight()
	residents_time+=delta
	if residents_time>25.0:residents_time=0;refresh_residents(false);apply_daylight()
	cue_time+=delta
	if cue_time>3.5:cue_time=0;resident_cues()
	if leaving:
		walk_out_step(delta)
	elif is_instance_valid(front_door) and front_door.guiding(delta): pass
	elif not placement_mode and not travelling and not is_instance_valid(talk_box) and not is_instance_valid(craft_window) and not PauseMenu.is_open() and not VersionGate.is_blocked():
		var focus := get_viewport().gui_get_focus_owner()
		if not (focus is TextEdit or focus is LineEdit) and not is_instance_valid(painter) and not is_instance_valid(interaction_panel):walk(delta)
	update_camera(delta)
	room_steps(delta)
	if is_instance_valid(bubble) and bubble.visible: pin_overlay(bubble,bubble_anchor,14)
	if is_instance_valid(hint_label) and hint_label.visible: pin_overlay(hint_label,hint_anchor,6)

## Out through the doorway while the screen fades, at walking pace.
func walk_out_step(delta: float) -> void:
	if not is_instance_valid(hero) or walk_out==Vector3.ZERO: return
	var before: Vector3=hero.position
	hero.position=hero.position.move_toward(walk_out,ControllerProfile.ROOM_WALK*delta)
	report_motion(before,delta)

# ---------------------------------------------------------------- room sound

## Footsteps on the floor the walker is on (WorldAudio.stride turns movement into steps, so walk,
## move_hero, the seat walk-up, stairs and the walk out all step): planks, tile, flagstone or a rug,
## "stairs" while climbing; residents walking in, out or to a new spot step more quietly.
func room_steps(delta: float) -> void:
	if not is_instance_valid(world_audio) or not is_instance_valid(hero): return
	world_audio.stride("hero",hero.position,delta,"stairs" if travelling else floor_surface(hero.position),true)
	for i in range(stepping.size()-1,-1,-1):
		var entry: Dictionary=stepping[i]
		if not entry.get("walking",false) or not is_instance_valid(entry.holder):
			stepping.remove_at(i)
			continue
		if int(entry.floor)!=floor_index: continue
		world_audio.stride("resident:"+str(entry.id),entry.holder.position,delta,floor_surface(entry.holder.position),false,RESIDENT_STEP_DB)

## Footstep surface at a spot of the current floor: the floor of the room it is in (interiors.gd
## THEMES "floor": planks, tile, flagstone), a rug when standing on one.
func floor_surface(at: Vector3) -> String:
	if room_spec.is_empty(): return "planks"
	var floor_kind := str(room_spec.get("colors",{}).get("floor","planks"))
	var rooms: Array=room_spec.get("rooms",[])
	if rooms.size()>1:
		var index := Interiors.room_at(room_spec,at.x)
		if index>=0 and index<rooms.size(): floor_kind=str(rooms[index].get("colors",{}).get("floor",floor_kind))
	return WorldAudio.room_surface(floor_kind,decor,at)

## The room's bed for where the walker is: the hearth, a clock, the mill, the cafe's murmur, the
## sea through the lighthouse walls, over the room tone (WorldAudio.room_ambience). Crossfades
## (WorldAudio fade) as the walker crosses into another room or floor; day follows the clock.
func update_room_audio() -> void:
	if not is_instance_valid(world_audio) or leaving: return
	var theme := str(Interiors.ROOMS.get(Interiors.building_for(room),{}).get("theme",room))
	if not room_spec.is_empty():
		theme=str(room_spec.get("theme",theme))
		var rooms: Array=room_spec.get("rooms",[])
		if current_room>=0 and current_room<rooms.size(): theme=str(rooms[current_room].get("theme",theme))
	var day := float(daylight_sample.get("daylight",1.0))
	var next := WorldAudio.room_ambience(theme,day)
	next["hour"]=float(daylight_sample.get("hour",-1.0))
	world_audio.set_ambience(next)

## Into the room softly: the home track rises from faint over MUSIC_IN s (instead of the 1.2 s
## mode crossfade), while the card is up and the room bed fades in under it.
func ease_in_music() -> void:
	if not is_instance_valid(room_music) or room_music.music.is_empty(): return
	var player: AudioStreamPlayer=room_music.music[room_music.music_index]
	if not player.playing: return
	if room_music.fade and room_music.fade.is_valid(): room_music.fade.kill()
	for other in room_music.music:
		if other!=player: other.stop()
	player.volume_db=-40.0
	room_music.fade=room_music.create_tween()
	room_music.fade.tween_property(player,"volume_db",Sound.MUSIC_DB,MUSIC_IN)

## The room's beds fade out over `seconds` (leaving: they go with the light, no cut at the change).
func fade_room_audio(seconds: float) -> void:
	if not is_instance_valid(world_audio): return
	world_audio.set_process(false)
	var sounding: Array=[]
	for key in world_audio.beds:
		if world_audio.beds[key].playing: sounding.append(world_audio.beds[key])
	if sounding.is_empty(): return
	var fade := world_audio.create_tween().set_parallel(true)
	for player in sounding: fade.tween_property(player,"volume_db",-60.0,maxf(seconds,0.05))

## Leaving: the room's music moves to a short-lived player under the veil (transition.gd, which
## outlives the scene) at the same spot and level, then fades over MUSIC_HANDOFF s, so it crosses
## the scene change into the village's own fade-in instead of stopping dead. Skipped headless
## (the dummy driver never ends a playback).
func hand_off_music() -> void:
	if DisplayServer.get_name()=="headless" or not is_instance_valid(room_music): return
	var playing: AudioStreamPlayer=null
	for player in room_music.music:
		if player.playing and player.stream!=null and (playing==null or player.volume_db>playing.volume_db): playing=player
	if playing==null or playing.volume_db<=Sound.SILENT_DB+1.0: return
	var keeper := Transition.of(get_tree())
	if not is_instance_valid(keeper) or not keeper.is_inside_tree(): return
	if room_music.fade and room_music.fade.is_valid(): room_music.fade.kill()
	var tail := AudioStreamPlayer.new()
	tail.name="RoomMusicTail"
	tail.bus=playing.bus
	tail.stream=playing.stream
	tail.volume_db=playing.volume_db
	keeper.add_child(tail)
	tail.play(playing.get_playback_position())
	for player in room_music.music: player.stop()
	# Let go of the stream however the tail ends (faded, or the game closing mid-fade).
	tail.tree_exiting.connect(func():
		tail.stop()
		tail.stream=null)
	var fade := tail.create_tween()
	fade.tween_property(tail,"volume_db",Sound.SILENT_DB,MUSIC_HANDOFF)
	fade.tween_callback(tail.queue_free)

## Whether the walker's own movement keys count now (the room's walking gate; the seat driver asks too).
func walk_allowed() -> bool:
	if placement_mode or travelling or leaving or is_instance_valid(talk_box) or is_instance_valid(craft_window) or PauseMenu.is_open() or VersionGate.is_blocked(): return false
	var focus := get_viewport().gui_get_focus_owner()
	return not (focus is TextEdit or focus is LineEdit) and not is_instance_valid(painter) and not is_instance_valid(interaction_panel)

## WASD walking inside the room.
func walk(delta: float) -> void:
	var input_direction := Input.get_vector("move_left","move_right","move_forward","move_back")
	var direction := Vector3(input_direction.x,0,input_direction.y)
	if direction.length()<=0:return
	if not resting.is_empty():
		stand_up()
		return
	move_hero(direction,delta)

## One step of walking: stays on the floor, slides along furniture, eases into
## doorways, climbs stairs it walks into and leaves through the front door.
## side_effects false (walking up to a seat): no doorway easing, stairs or leaving, and the
## direction's length is the pace (the walk slows into the seat).
func move_hero(direction: Vector3, delta: float, side_effects := true) -> void:
	if not is_instance_valid(hero) or direction.length()<=0.0: return
	var before: Vector3=hero.position
	var step := (direction.normalized() if side_effects else direction.limit_length(1.0))*delta*ControllerProfile.ROOM_WALK
	var limits := Interiors.walk_limits(room_spec)
	var door_x: float=limits.door_x
	# Heading for the front door from a little to the side: ease into the doorway.
	if side_effects and room_spec.get("has_door",false) and step.z>0 and hero.position.z>float(limits.front)-0.25 and absf(hero.position.x-door_x)<Interiors.DOOR_HALF+0.4:
		var eased := Vector3(move_toward(hero.position.x,door_x,delta*1.6),0,hero.position.z)
		if can_stand(eased): hero.position=eased
	# ...and the same for doorways between rooms.
	for door in room_spec.get("doorways",[]) if side_effects else []:
		var middle: float=(float(door.z0)+float(door.z1))*0.5
		if absf(step.x)>0.001 and absf(hero.position.x-float(door.x))<0.9 and absf(hero.position.z-middle)<Interiors.DOORWAY*0.5+0.45:
			var eased := Vector3(hero.position.x,0,move_toward(hero.position.z,middle,delta*1.6))
			if can_stand(eased): hero.position=eased
	var stuck := movement_blocked(hero.position)
	var candidate: Vector3=hero.position+Vector3(step.x,0,0)
	if can_stand(candidate,stuck):hero.position=candidate
	elif side_effects: try_stairs(candidate,direction)
	candidate=hero.position+Vector3(0,0,step.z)
	if can_stand(candidate,stuck):hero.position=candidate
	elif side_effects: try_stairs(candidate,direction)
	report_motion(before,delta)
	if side_effects and room_spec.get("has_door",false) and step.z>0 and direction.normalized().z>0.5 and Interiors.at_door(room_spec,hero.position+Vector3(0,0,step.z)):leave()

## The walk clip and contact IK follow where the walker really went: a blocked or
## clamped step reads as standing still instead of marching in place.
func report_motion(before: Vector3, delta: float) -> void:
	var moved := Vector2(hero.position.x-before.x,hero.position.z-before.z)/maxf(delta,.001)
	if moved.length()<0.25: moved=Vector2.ZERO
	hero.external_velocity=moved
	hero.external_motion=moved.normalized()

## Walking into a staircase, ladder or hatch takes it.
func try_stairs(at: Vector3, direction: Vector3) -> void:
	if not travel_enabled or travelling: return
	var record := blocking_record(at)
	if record.is_empty() or not record.has("link"): return
	var toward: Vector3=record.center-hero.position
	toward.y=0
	if toward.length()<0.01 or direction.normalized().dot(toward.normalized())>0.35: travel(record)

func can_stand(at: Vector3, stuck := false) -> bool:
	if not Interiors.walkable(room_spec,at):return false
	return stuck or not movement_blocked(at)

func movement_blocked(at: Vector3) -> bool:
	if not blocking_record(at).is_empty(): return true
	if floor_index!=0: return false
	# 물건 통과 (V): the walker passes through placed pieces.
	RoomBuild.PassThrough.load_pref()
	if RoomBuild.PassThrough.on: return false
	for id in placed:
		var item: Node3D=placed[id]
		var size: Vector3=item.get_meta("size",Vector3(1.6,1.6,1.6))
		var local := (at-item.position).rotated(Vector3.UP,-item.rotation.y)
		if absf(local.x)<size.x*0.5+ControllerProfile.BODY_RADIUS and absf(local.z)<size.z*0.5+ControllerProfile.BODY_RADIUS:return true
	return false

## The room furniture whose footprint the walker would stand in at this spot.
func blocking_record(at: Vector3) -> Dictionary:
	for record in decor:
		if not record.solid:continue
		var local: Vector3=(at-record.center).rotated(Vector3.UP,-float(record.yaw))
		var half: Vector2=record.half
		if absf(local.x)<half.x+ControllerProfile.BODY_RADIUS*0.8 and absf(local.z)<half.y+ControllerProfile.BODY_RADIUS*0.8:return record
	return {}

## Client-side check before asking the server; the server accepts x,z in [-4,4]
## with the door strip (|x|<1.5, z>2.5) kept clear, for home and workshop only.
func placement_problem(at: Vector3) -> String:
	if public_room:return tr("이곳에는 가구를 놓을 수 없어요.")
	if floor_index!=0:return tr("가구는 1층에만 놓을 수 있어요.")
	if absf(at.x)>4 or absf(at.z)>4:return tr("벽에서 한 칸 안쪽에 놓아 주세요.")
	if absf(at.x)<1.5 and at.z>2.5:return tr("출입문 앞은 비워 주세요.")
	if room=="workshop" and at.x < -1.8 and at.z < -1.5:return tr("고정 작업대와 겹쳐요.")
	for record in decor:
		if not record.solid:continue
		var half: Vector2=record.world_half
		if absf(record.center.x-at.x)<half.x+0.75 and absf(record.center.z-at.z)<half.y+0.75:return tr("방에 원래 있던 가구와 겹쳐요.")
	if is_instance_valid(hero) and absf(hero.position.x-at.x)<1.15 and absf(hero.position.z-at.z)<1.15:return tr("캐릭터가 서 있는 곳은 비워 주세요.")
	# The ghost's real footprint at its angle and shape: inside the walls, clear of the furniture.
	if placement_mode and is_instance_valid(ghost):
		var size: Vector3=ghost.get_meta("size",Vector3.ONE)
		var half := ObjectTransform.footprint_half(size,placement_rotation)
		var walls: Vector2=Vector2(room_spec.get("size",Vector2(10,10)))*0.5
		if absf(at.x)+half.x>walls.x+0.05 or absf(at.z)+half.y>walls.y+0.05:return tr("벽에 닿아요. 조금 안쪽으로 옮기거나 돌려 보세요.")
		for id in placed:
			var item: Node3D=placed[id]
			if id==selected.get("id") or not is_instance_valid(item):continue
			if ObjectTransform.footprints_overlap(Vector2(at.x,at.z),Vector2(size.x,size.z),placement_rotation,Vector2(item.position.x,item.position.z),Vector2(item.get_meta("size",Vector3.ONE).x,item.get_meta("size",Vector3.ONE).z),item.rotation_degrees.y):
				return tr("다른 가구와 겹쳐요.")
	return ""

# ---------------------------------------------------------------- furniture feedback

## What using furniture looks like: small, cheap effects instead of sentences.
func play_effect(action: String, record: Dictionary) -> void:
	var node: Node3D=record.node
	var size: Vector3=record.get("size",Vector3.ONE)
	var base_y: float=node.global_position.y
	var top: Vector3=Vector3(record.center.x,base_y+(size.y*0.5 if record.mounted else size.y),record.center.z)
	var front: Vector3=Vector3(0,0,1).rotated(Vector3.UP,float(record.yaw))
	match action:
		"sit": sit_on(record)
		"lie": lie_on(record);sparkle(top+Vector3(0,0.2,0),Color("cfd8ff"),3)
		"open":
			if record.has("lid"):
				var lid: Node3D=record.lid
				var tween := lid.create_tween()
				tween.tween_property(lid,"rotation:x",-1.1,0.35).set_trans(Tween.TRANS_BACK)
				tween.tween_interval(1.4)
				tween.tween_property(lid,"rotation:x",0.0,0.3)
			else: wobble(node,Vector3(1.03,0.97,1.03))
			sparkle(top+front*0.2,Color("ffe39a"),5)
		"cook":
			puff(top+Vector3(0,0.1,0),Color("f4f4f2",0.8),9,1.3,0.3,0.26)
			puff(top+Vector3(0,0.05,0),Color("ffb347",0.9),5,0.35,0.2,0.04)
		"wash":
			bubbles(top+front*0.1+Vector3(0,0.05,0),9)
			puff(top+Vector3(0,0.4,0),Color("7fc4ec",0.9),6,-0.5,0.2,0.05)
		"water":
			puff(top+Vector3(0,0.45,0),Color("7fc4ec",0.9),9,-0.55,0.3,0.06)
			sparkle(top+Vector3(0,0.15,0),Color("c8f0b0"),3)
			wobble(node,Vector3(1.02,1.05,1.02))
		"warm": puff(Vector3(record.center.x,0.6,record.center.z)+front*(size.z*0.5),Color("ffb347",0.95),12,1.3,0.35,0.06)
		"shine":
			sparkle(top+Vector3(0,-size.y*0.35,0),Color("fff2b0"),8)
			ring(top+Vector3(0,-size.y*0.4,0),Color("ffe39a",0.8),1.6)
			for light in node.find_children("*","OmniLight3D",true,false):
				var glow := light.create_tween()
				glow.tween_property(light,"light_energy",light.light_energy*3.0,0.25)
				glow.tween_property(light,"light_energy",light.light_energy,0.8)
		"play":
			for i in 4: note_pop(top+Vector3(randf_range(-0.4,0.4),0.1,0),"♪" if i%2==0 else "♫",i*0.18)
		"read": pages(top+front*0.25,5)
		"wind":
			ring(top,Color(RpgUi.GOLD,0.9),0.9)
			spin_hands(node)
		"ring":
			ring(top+Vector3(0,0.1,0),Color("ffe39a",0.9),1.2)
			note_pop(top+Vector3(0,0.2,0),"♪",0.0)
		"sip":
			puff(top+Vector3(0,0.05,0),Color("f4f4f2",0.6),4,0.6,0.12,0.08)
			note_pop(top+Vector3(0,0.25,0),"♥",0.15)
		"hammer":
			burst(top+Vector3(0,0.05,0),Color("ffd36a"),8)
			wobble(node,Vector3(1.03,0.96,1.03))
		"pat","grind","pull":
			puff(top,Color("f3ead6",0.8),9,0.6,0.35,0.12)
			wobble(node,Vector3(1.03,0.96,1.03))
			if record.has("bob"):
				var sack: Node3D=record.bob
				var lift := sack.create_tween()
				lift.tween_property(sack,"position:y",sack.position.y+0.8,0.5).set_trans(Tween.TRANS_SINE)
				lift.tween_property(sack,"position:y",sack.position.y,0.6).set_trans(Tween.TRANS_BOUNCE)
		"knock":
			puff(top,Color("c9b9a0",0.6),6,0.4,0.3,0.1)
			wobble(node,Vector3(1.04,0.96,1.04))
		"turn":
			wobble(node,Vector3(1.03,0.97,1.03));turn_once(node,action)
			sparkle(top,Color("fff2b0"),4)
		"switch": ring(top,Color("ffcf86",0.7),0.6)
		"look_out": sparkle(top,Color("fff2b0"),3)
		_:
			wobble(node,Vector3(1.02,1.02,1.02))
			sparkle(top,Color("fff2b0"),3)
	if is_instance_valid(hero) and action in ["read","wash","cook","warm","water","ring","hammer","wind","sip"]: hero.react("craft")

## Shared little meshes and materials so effects never allocate much.
var fx_meshes: Dictionary={}
func fx_mesh(kind: String) -> Mesh:
	if fx_meshes.has(kind): return fx_meshes[kind]
	var mesh: Mesh
	match kind:
		"page":
			var quad := QuadMesh.new();quad.size=Vector2(0.14,0.1);mesh=quad
		"ring":
			var torus := TorusMesh.new();torus.inner_radius=0.42;torus.outer_radius=0.5;torus.rings=24;torus.ring_segments=4;mesh=torus
		_:
			var ball := SphereMesh.new();ball.radius=0.5;ball.height=1.0;ball.radial_segments=8;ball.rings=4;mesh=ball
	fx_meshes[kind]=mesh
	return mesh

func fx_node(kind: String, color: Color, at: Vector3, scale_value: float) -> MeshInstance3D:
	var bit := MeshInstance3D.new()
	bit.mesh=fx_mesh(kind)
	var material := StandardMaterial3D.new()
	material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	material.cull_mode=BaseMaterial3D.CULL_DISABLED
	material.albedo_color=color
	bit.material_override=material
	bit.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	stage.add_child(bit)
	bit.global_position=at
	bit.scale=Vector3.ONE*scale_value
	return bit

## Little four-point stars that pop and fade.
func sparkle(at: Vector3, color: Color, count: int) -> void:
	for i in count:
		var star := Art.label3d(stage,"✦",at+Vector3(randf_range(-0.35,0.35),randf_range(-0.1,0.3),randf_range(-0.2,0.2)),color)
		star.font_size=58;star.outline_size=8;star.outline_modulate=Color(0.45,0.3,0.08,0.7);star.no_depth_test=true
		star.scale=Vector3.ONE*0.2
		var tween := star.create_tween()
		tween.tween_interval(i*0.08)
		tween.tween_property(star,"scale",Vector3.ONE,0.18).set_trans(Tween.TRANS_BACK)
		tween.parallel().tween_property(star,"position:y",star.position.y+0.25,0.7)
		tween.tween_property(star,"modulate:a",0.0,0.35)
		tween.tween_callback(star.queue_free)

func note_pop(at: Vector3, text: String, delay: float) -> void:
	var note := Art.label3d(stage,text,at,Color("fff2c8"))
	note.font_size=62;note.outline_size=8;note.outline_modulate=Color(0.25,0.18,0.3,0.8);note.no_depth_test=true;note.modulate.a=0.0
	var tween := note.create_tween()
	tween.tween_interval(delay)
	tween.tween_property(note,"modulate:a",1.0,0.1)
	tween.parallel().tween_property(note,"position",at+Vector3(randf_range(-0.3,0.3),0.7,0),1.1).set_trans(Tween.TRANS_SINE)
	tween.tween_property(note,"modulate:a",0.0,0.3)
	tween.tween_callback(note.queue_free)

## A soft ring that widens and fades (bells, clocks, lamps, the lens).
func ring(at: Vector3, color: Color, width: float) -> void:
	var halo := fx_node("ring",color,at,0.2)
	var tween := halo.create_tween()
	tween.set_parallel(true)
	tween.tween_property(halo,"scale",Vector3(width,0.3,width),0.6).set_trans(Tween.TRANS_SINE)
	tween.tween_property(halo.material_override,"albedo_color:a",0.0,0.6)
	tween.set_parallel(false)
	tween.tween_callback(halo.queue_free)

## Soap bubbles that wobble upward.
func bubbles(at: Vector3, count: int) -> void:
	for i in count:
		var bubble_bit := fx_node("ball",Color("dff4ff",0.6),at+Vector3(randf_range(-0.3,0.3),0,randf_range(-0.15,0.15)),randf_range(0.09,0.17))
		var tween := bubble_bit.create_tween()
		tween.tween_interval(i*0.07)
		tween.tween_property(bubble_bit,"global_position",bubble_bit.global_position+Vector3(randf_range(-0.2,0.2),randf_range(0.5,0.9),0),1.0).set_trans(Tween.TRANS_SINE)
		tween.tween_callback(bubble_bit.queue_free)

## Pages that flutter up out of a book.
func pages(at: Vector3, count: int) -> void:
	for i in count:
		var page := fx_node("page",Color("fbf6e6",0.95),at+Vector3(randf_range(-0.2,0.2),0,0),1.8)
		var tween := page.create_tween()
		tween.tween_interval(i*0.09)
		tween.set_parallel(true)
		tween.tween_property(page,"global_position",page.global_position+Vector3(randf_range(-0.4,0.4),randf_range(0.5,0.9),randf_range(0.0,0.3)),0.9)
		tween.tween_property(page,"rotation",Vector3(randf_range(-2,2),randf_range(-3,3),randf_range(-2,2)),0.9)
		tween.tween_property(page.material_override,"albedo_color:a",0.0,0.9).set_delay(0.4)
		tween.set_parallel(false)
		tween.tween_callback(page.queue_free)

## Sparks that jump out and fall (a hammer on the workbench).
func burst(at: Vector3, color: Color, count: int) -> void:
	for i in count:
		var spark := fx_node("ball",color,at,0.05)
		var out := Vector3(randf_range(-0.5,0.5),0,randf_range(-0.5,0.5))
		var tween := spark.create_tween()
		tween.tween_property(spark,"global_position",at+out*0.6+Vector3(0,0.35,0),0.18)
		tween.tween_property(spark,"global_position",at+out+Vector3(0,-0.2,0),0.3).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		tween.tween_callback(spark.queue_free)

## Clock hands whirl round once (built clocks); a generated clock just rings.
func spin_hands(node: Node3D) -> void:
	for hand in node.find_children("*","Node3D",true,false):
		if hand.get_child_count()==1 and hand.get_child(0) is MeshInstance3D and absf(hand.position.z)>0.04 and absf(hand.position.z)<0.07:
			var tween := hand.create_tween()
			tween.tween_property(hand,"rotation:z",hand.rotation.z-TAU,0.8).set_trans(Tween.TRANS_CUBIC)

func wobble(node: Node3D, peak: Vector3) -> void:
	if not is_instance_valid(node) or node.has_meta("wobbling"): return
	node.set_meta("wobbling",true)
	var tween := node.create_tween()
	tween.tween_property(node,"scale",peak,0.08)
	tween.tween_property(node,"scale",Vector3.ONE,0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tween.tween_callback(func(): node.remove_meta("wobbling"))

func turn_once(node: Node3D, action: String) -> void:
	if action!="turn": return
	var model := node.get_node_or_null("Model") as Node3D
	var target: Node3D=model if model else node
	var tween := target.create_tween()
	tween.tween_property(target,"rotation:y",target.rotation.y+0.5,0.5).set_trans(Tween.TRANS_SINE)
	tween.tween_property(target,"rotation:y",target.rotation.y,0.7).set_trans(Tween.TRANS_SINE)

## A few soft particles (steam, water drops, embers, flour) that drift and fade.
func puff(at: Vector3, color: Color, count: int, rise: float, spread: float, radius: float) -> void:
	var material := StandardMaterial3D.new()
	material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color=color
	for i in count:
		var bit := MeshInstance3D.new()
		var ball := SphereMesh.new();ball.radius=radius;ball.height=radius*2;ball.radial_segments=8;ball.rings=4
		bit.mesh=ball;bit.material_override=material.duplicate()
		bit.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		stage.add_child(bit)
		bit.global_position=at+Vector3(randf_range(-spread,spread),randf_range(0,0.15),randf_range(-spread,spread))
		var tween := bit.create_tween()
		tween.tween_interval(i*0.06)
		tween.set_parallel(true)
		tween.tween_property(bit,"global_position",bit.global_position+Vector3(randf_range(-0.15,0.15),rise,randf_range(-0.15,0.15)),0.9)
		tween.tween_property(bit,"scale",Vector3.ONE*(1.8 if rise>0 else 0.6),0.9)
		tween.tween_property(bit.material_override,"albedo_color:a",0.0,0.9)
		tween.set_parallel(false)
		tween.tween_callback(bit.queue_free)

## Sits on a chair, sofa or bench: hips and knees bend and the walker settles on
## the seat facing out. Any movement key or E gets up again.
func sit_on(record: Dictionary) -> void:
	if is_instance_valid(seat): hook_seat_sounds();seat.sit(record)

## Lies down on a bed, head on the pillow.
func lie_on(record: Dictionary) -> void:
	if is_instance_valid(seat): hook_seat_sounds();seat.lie(record)

func stand_up(face_away := true) -> void:
	if is_instance_valid(seat): seat.stand(face_away)

# ---------------------------------------------------------------- residents

func resident_clock() -> Dictionary:
	var day: int=int(Engine.get_meta("interior_day")) if Engine.has_meta("interior_day") else int(Residents.clock().day)
	return {"hour":float(daylight_sample.get("hour",Daylight.clock_hour())),"day":day}

## Brings the room in line with the schedule: leavers walk out, newcomers walk
## in through the door, people whose activity changed move to their new spot.
func refresh_residents(instant := false) -> void:
	if not public_room or building_spec.is_empty(): return
	var c := resident_clock()
	var now: Array=Residents.occupants(str(building_spec.building),c.hour,c.day)
	var wanted := {}
	for occupant in now: wanted[str(occupant.id)]=occupant
	var taken := {}
	for id in npcs.keys():
		var entry: Dictionary=npcs[id]
		var next: Dictionary=wanted.get(id,{})
		if next.is_empty(): remove_resident(id,not instant)
		elif next.activity!=entry.state.activity or next.spot!=entry.state.spot or next.asleep!=entry.state.asleep:
			var from: Vector3=entry.holder.position
			var same_floor: bool=int(entry.floor)==floor_index
			remove_resident(id,false)
			place_resident(next,taken,from if same_floor and not instant else Vector3.INF)
		else:
			entry.state=next
			if not entry.record.is_empty(): taken[entry.record.node.get_instance_id()]=true
	for occupant in now:
		var id := str(occupant.id)
		if npcs.has(id): continue
		var door := Vector3(float(building_spec.floors[0].get("door_x",0.0)),0,float(building_spec.floors[0].size.y)*0.5-0.45)
		place_resident(occupant,taken,door if not instant and floor_index==0 else Vector3.INF)

func place_resident(occupant: Dictionary, taken: Dictionary, walk_from := Vector3.INF) -> void:
	var id := str(occupant.id)
	var pick: Dictionary=Interiors.choose_spot(occupant,decor_by_floor,taken)
	var level := int(pick.get("floor",0))
	var record: Dictionary=pick.get("record",{})
	if not record.is_empty(): taken[record.node.get_instance_id()]=true
	var holder := Node3D.new();holder.name="Resident_"+id
	floor_roots[level].add_child(holder)
	var body := make_body(id,holder)
	var entry := {"id":id,"holder":holder,"body":body,"state":occupant,"floor":level,"record":record,"pose":"stand","talk":{},"zzz":null}
	npcs[id]=entry
	pose_resident(entry)
	if walk_from!=Vector3.INF and level==floor_index and entry.pose=="stand":
		var target: Vector3=holder.position
		holder.position=walk_from
		walk_to(entry,target,func(): pass)

## A still figure for a resident: shadow folk from shadow_figure.gd, the cast from npc.gd.
func make_body(id: String, holder: Node3D) -> Node3D:
	var info: Dictionary=Residents.resident(id)
	if str(info.get("kind",""))=="cast":
		var npc_script := load("res://scripts/npc.gd") as GDScript
		if npc_script and npc_script.call("available",id):
			var npc: Node3D=npc_script.new()
			holder.add_child(npc)
			npc.call("setup",id,0.0)
			name_plate(holder,id)
			return npc
	else:
		var shadow_script := load("res://scripts/shadow_figure.gd") as GDScript
		if shadow_script and shadow_script.can_instantiate():
			var figure = shadow_script.call("create_still",id)
			if figure is Node3D:
				holder.add_child(figure)
				figure.set_day(DayFolk.is_day(id,float(resident_clock().hour)),true)
				# The figure's tag keeps one size on screen, made for the far village camera; the room's
				# close camera blew it up over the whole café. Sized in the room like the other residents'.
				var own = figure.get("nameplate")
				if own is Label3D:
					own.fixed_size=false;own.pixel_size=0.006;own.font_size=28;own.outline_size=4
				return figure
	var stand_in := Interiors.stand_in_figure(id)
	holder.add_child(stand_in)
	name_plate(holder,id)
	return stand_in

func name_plate(holder: Node3D, id: String) -> void:
	var plate := Art.label3d(holder,tr(Interiors.resident_title(id)),Vector3(0,2.1,0),Color("d4cdf2"))
	plate.font_size=28;plate.outline_size=4;plate.name="NamePlate"

## Puts a resident on their spot: lying in their bed, sitting on a seat, or
## standing in front of the piece they use, facing it.
func pose_resident(entry: Dictionary) -> void:
	var record: Dictionary=entry.record
	var occupant: Dictionary=entry.state
	var holder: Node3D=entry.holder
	var body: Node3D=entry.body
	var level := int(entry.floor)
	var f: Dictionary=building_spec.floors[level]
	var still := body.has_method("set_pose")
	holder.basis=Basis()
	var kind := str(record.get("kind",""))
	if occupant.get("asleep",false) and kind=="bed":
		entry.pose="lie"
		var size: Vector3=record.size
		var head := Vector3(0,0,-1).rotated(Vector3.UP,float(record.yaw))
		var top := minf(size.y*0.5,0.62)+0.02
		if still:
			holder.position=record.center+Vector3(0,top,0)
			body.face(atan2(head.x,head.z))
			body.set_pose("lie")
		else:
			holder.position=record.center-head*(size.z*0.5-0.2)+Vector3(0,top+0.12,0)
			holder.basis=Basis(head.cross(Vector3.UP),head,Vector3.UP)
		record["occupant"]=entry.id
		var zzz := Label3D.new();zzz.text="Z z z";zzz.font_size=34;zzz.pixel_size=0.005;zzz.outline_size=6
		zzz.billboard=BaseMaterial3D.BILLBOARD_ENABLED;zzz.modulate=Color("cfd8ff")
		holder.get_parent().add_child(zzz)
		zzz.position=record.center-head*(size.z*0.5-0.45)+Vector3(0,top+0.75,0)
		var bob := zzz.create_tween().set_loops()
		bob.tween_property(zzz,"position:y",zzz.position.y+0.18,1.2).set_trans(Tween.TRANS_SINE)
		bob.tween_property(zzz,"position:y",zzz.position.y,1.2).set_trans(Tween.TRANS_SINE)
		entry.zzz=zzz
		hide_plate(holder,body,true)
		return
	if kind in Interiors.SEATS and still:
		entry.pose="sit"
		var size: Vector3=record.size
		var height: float=size.y*0.5 if kind!="bench" else 0.47
		holder.position=record.center+Vector3(0,0,0.04).rotated(Vector3.UP,float(record.yaw))+Vector3(0,height+0.02,0)
		body.face(float(record.yaw))
		body.set_pose("sit")
		record["occupant"]=entry.id
		return
	entry.pose="stand"
	var others: Array=[]
	for other in npcs.values():
		if other!=entry and int(other.floor)==level and other.pose=="stand": others.append(other.holder.position)
	var at: Vector3=Interiors.stand_spot(record,f,decor_by_floor[level],others,floor_entries(level)) if not record.is_empty() else Interiors.spawn_point(f)+Vector3(0.9,0,-0.6)
	holder.position=at
	var look: Vector3=(record.center if not record.is_empty() else at+Vector3(0,0,1))-at
	face_body(entry,atan2(look.x,look.z) if Vector2(look.x,look.z).length()>0.05 else 0.0)
	if still: body.set_pose("stand")
	var talk := {"kind":"resident","id":entry.id,"node":holder,"center":at,"yaw":0.0,"mounted":false,"solid":true,"interactive":true,"glb":false,
		"size":Vector3(0.6,1.75,0.6),"half":Vector2(0.28,0.28),"world_half":Vector2(0.28,0.28),"top":1.75,"floor":level,"room":Interiors.room_at(f,at.x)}
	decor_by_floor[level].append(talk)
	entry.talk=talk

## Where the walker comes onto a floor: the front door's spot on the ground floor, every
## stair's arrival on the others (a standing resident keeps these and the way from them open).
func floor_entries(level: int) -> Array:
	var points: Array=[]
	if level==0: points.append(Interiors.spawn_point(building_spec.floors[0]))
	for f in building_spec.floors:
		for item in f.get("furniture",[]):
			if item.has("link") and int(item.link.to)==level: points.append(item.link.arrive)
	return points

func face_body(entry: Dictionary, yaw: float) -> void:
	var body: Node3D=entry.body
	if body.has_method("face"): body.face(yaw)
	elif body.get("turn_target")!=null:
		body.set("turn_target",yaw);body.rotation.y=yaw
	else: body.rotation.y=yaw

func hide_plate(holder: Node3D, body: Node3D, hidden: bool) -> void:
	var plate := holder.get_node_or_null("NamePlate") as Label3D
	if plate: plate.visible=not hidden
	var own = body.get("nameplate")
	if own is Label3D: own.visible=not hidden

func remove_resident(id: String, walk_out_door: bool) -> void:
	var entry: Dictionary=npcs.get(id,{})
	if entry.is_empty(): return
	npcs.erase(id)
	if talk_id==id: close_talk()
	var record: Dictionary=entry.record
	if str(record.get("occupant",""))==id: record.erase("occupant")
	if not entry.talk.is_empty(): decor_by_floor[int(entry.floor)].erase(entry.talk)
	if is_instance_valid(entry.zzz): entry.zzz.queue_free()
	var holder: Node3D=entry.holder
	if walk_out_door and int(entry.floor)==floor_index and entry.pose=="stand" and is_instance_valid(holder):
		var f: Dictionary=building_spec.floors[int(entry.floor)]
		var exit: Vector3
		if int(entry.floor)==0: exit=Vector3(float(f.get("door_x",0.0)),0,float(f.size.y)*0.5+0.3)
		else:
			exit=holder.position
			for other in decor_by_floor[int(entry.floor)]:
				if other.has("link") and int(other.link.to)<int(entry.floor): exit=other.center
		walk_to(entry,exit,func():
			var fade := holder.create_tween()
			fade.tween_property(holder,"scale",Vector3(0.9,0.05,0.9),0.35)
			fade.tween_callback(holder.queue_free))
	elif is_instance_valid(holder): holder.queue_free()

## Walks a standing resident in place along a straight line (they are props: no collision).
func walk_to(entry: Dictionary, target: Vector3, done: Callable) -> void:
	var holder: Node3D=entry.holder
	var body: Node3D=entry.body
	var from: Vector3=holder.position
	var offset := target-from
	offset.y=0
	if offset.length()<0.05:
		done.call();return
	face_body(entry,atan2(offset.x,offset.z))
	if body.has_method("play_clip"): body.play_clip("walk")
	# Heard on the floor while it walks (room_steps), walking out of the room too.
	entry["walking"]=true
	if not entry in stepping: stepping.append(entry)
	var tween := holder.create_tween()
	tween.tween_property(holder,"position",target,offset.length()/1.1)
	tween.tween_callback(func():
		entry["walking"]=false
		if body.has_method("play_clip"): body.play_clip("idle")
		if not entry.record.is_empty() and npcs.has(str(entry.id)):
			var look: Vector3=entry.record.center-holder.position
			face_body(entry,atan2(look.x,look.z))
		done.call())

## Small signs of life on the floor the walker is on: steam, notes, flour, stars.
func resident_cues() -> void:
	for entry in npcs.values():
		if int(entry.floor)!=floor_index or entry.state.get("asleep",false) or entry.record.is_empty(): continue
		var record: Dictionary=entry.record
		var size: Vector3=record.get("size",Vector3.ONE)
		var top := Vector3(record.center.x,record.node.global_position.y+size.y,record.center.z)
		match str(entry.state.activity):
			"cook": puff(top+Vector3(0,0.1,0),Color("f4f4f2",0.7),5,1.0,0.2,0.18)
			"barista": if randf()<0.5: puff(top+Vector3(0,0.1,0),Color("f4f4f2",0.6),4,0.8,0.2,0.14)
			"mill": puff(top,Color("f3ead6",0.7),5,0.5,0.4,0.12)
			"tend": puff(top+Vector3(0,0.3,0),Color("7fc4ec",0.85),6,-0.45,0.25,0.06)
			"piano": pop_over(entry,"♪")
			"stargaze": pop_over(entry,"✦")
			"read","tidy": if randf()<0.3: pop_over(entry,"…")

func pop_over(entry: Dictionary, text: String) -> void:
	var body: Node3D=entry.body
	if body.has_method("pop"):
		body.pop(text,1.6);return
	# Bodies without pop() (the cast): the cue's bark in the resident's register. An activity cue
	# repeats every few seconds, so the same bubble barks again only after CUE_BARK_GAP s.
	var now := Time.get_ticks_msec()*0.001
	if text!=str(entry.get("bark_text","")) or now-float(entry.get("bark_time",-100.0))>=CUE_BARK_GAP:
		if VoiceBabble.emote(self,str(entry.get("id","")),text,entry.holder.global_position):
			entry["bark_text"]=text;entry["bark_time"]=now
	var label := Art.label3d(entry.holder,text,Vector3(0,2.0,0),Color("fff2c8"))
	label.font_size=40
	var tween := label.create_tween()
	tween.set_parallel(true)
	tween.tween_property(label,"position:y",2.5,1.4)
	tween.tween_property(label,"modulate:a",0.0,1.4)
	tween.set_parallel(false)
	tween.tween_callback(label.queue_free)

## E on a resident: sleepers only murmur; everyone else talks.
func talk_to(id: String, record: Dictionary) -> void:
	var entry: Dictionary=npcs[id]
	if is_instance_valid(hero): hero.face_point(entry.holder.global_position)
	if entry.state.get("asleep",false):
		VoiceBabble.emote(self,id,"zz")
		say(tr("쿨쿨… 깊이 잠들었어요."),record)
		return
	open_talk(id)

## The village's RPG dialogue box: portrait, name plate, typed lines, choices.
## lines/choices replace the resident's own talk (the gift conversation); such choices are
## [label, Callable] instead of [label, action word].
func open_talk(id: String, lines: Array = [], choices: Array = []) -> void:
	# A talk replaced by the next one (the gift conversation, a request) goes quietly.
	close_talk(false)
	if not npcs.has(id): return
	var entry: Dictionary=npcs[id]
	var c := resident_clock()
	var talk: Dictionary=Interiors.resident_talk(id,entry.state,building_spec,c.hour) if lines.is_empty() else {"lines":lines,"choices":choices if not choices.is_empty() else [[tr("알겠어요"),Callable()]]}
	# Residents of a house take gifts from their own village's player.
	if lines.is_empty() and NpcGifts.can_receive(id) and not visiting and not api.token.is_empty():
		talk.choices.insert(maxi(0,talk.choices.size()-1),["선물하기","gift"])
	# 단비 at the counter buys the bag's finds: leaf coins and a daily starseed allowance (shop_sell.gd).
	if lines.is_empty() and id=="shopkeeper" and str(entry.state.get("activity",""))=="shopkeep" and not visiting and not api.token.is_empty():
		talk.choices.insert(0,["물건 팔기","sell"])
	# The resident's request (quests.gd) comes first, as in the village.
	if lines.is_empty() and not visiting:
		var request: Array=preload("res://scripts/quests.gd").room_choice(self,id)
		# Marked "request". Keys pick it only once the choices are up (RpgUi.dialogue_ready), and
		# taking a request still asks first, with '다음에요' leading.
		if not request.is_empty(): talk.choices.insert(0,request+["request"])
	talk_id=id;talk_lines=talk.lines;talk_choices=talk.choices;talk_page=0
	if entry.pose=="stand" and is_instance_valid(hero):
		var look: Vector3=hero.global_position-entry.holder.global_position
		face_body(entry,atan2(look.x,look.z))
	if entry.body.has_method("smile"): entry.body.smile(3.0)
	# The dialogue box opens with its own sound (RpgUi.dialogue) and the resident greets (VoiceBabble):
	# no extra pop on top, as in the village.
	talk_box=Control.new();talk_box.name="TalkBox";talk_box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	talk_box.mouse_filter=Control.MOUSE_FILTER_IGNORE
	add_child(talk_box)
	# The same illustrated card + night box as the village (RpgUi.dialogue).
	var hour: float=float(resident_clock().hour)
	talk_window=RpgUi.dialogue(talk_box,tr(Interiors.resident_title(id,hour)),Interiors.portrait(id,hour))
	talk_window.shade.gui_input.connect(func(event):
		if event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT: advance_talk())
	talk_body=talk_window.body
	# Kept for older callers; choices now live in talk_window.choices.
	talk_footer=HBoxContainer.new();talk_footer.visible=false;talk_box.add_child(talk_footer)
	show_hud(false)
	show_talk_page()

func show_talk_page() -> void:
	if not is_instance_valid(talk_box): return
	talk_body.text=str(talk_lines[talk_page])
	RpgUi.dialogue_line(talk_window,talk_body.text)
	RpgUi.dialogue_type(talk_window,GameSettings.typing_seconds(talk_body.text.length()))
	# The resident babbles in their own voice along the typing (a new talk greets first); a skip shows
	# the line whole, and closing the talk frees the label, which ends it.
	VoiceBabble.speak(self,talk_id,talk_body.text,0.0,talk_body)
	if talk_page<talk_lines.size()-1:
		RpgUi.dialogue_more(talk_window,true)
	else:
		RpgUi.dialogue_more(talk_window,false)
		var entries := []
		for choice in talk_choices:
			var picked: Array=choice
			entries.append([tr(str(choice[0])),func(): pick_talk(picked)])
		RpgUi.dialogue_choices(talk_window,entries)

## A dialogue choice: an action word (run_choice) or, in the gift conversation, a Callable.
func pick_talk(choice: Array) -> void:
	if choice[1] is Callable:
		var action: Callable=choice[1]
		# A plain 알겠어요 closes with the close sound; a choice that goes on is heard in what follows.
		close_talk(not action.is_valid())
		if action.is_valid(): action.call()
	else: run_choice(str(choice[1]))

func advance_talk() -> void:
	if not is_instance_valid(talk_box): return
	# The storage chest's list has no pages: E closes it.
	if talk_window.is_empty():
		close_talk()
		return
	if RpgUi.dialogue_typing(talk_window):
		RpgUi.dialogue_skip(talk_window)
	elif talk_page<talk_lines.size()-1:
		talk_page+=1
		# The village dialogue's page turn (main.gd open_dialogue).
		RpgUi.sfx("page",-8.0)
		show_talk_page()
	elif not talk_choices.is_empty():
		# The highlighted choice, as in the village (RpgUi.dialogue_pick; W/S or the arrows move it).
		RpgUi.dialogue_pick(talk_window)

## Closes the talk (or the storage chest's window), with the close sound only when a box was open.
## sound false: a talk replaced by the next one, or a choice whose outcome has its own sound.
func close_talk(sound := true) -> void:
	# A shared window (the storage chest) leaves the window stack with its own close sound and fade.
	if is_instance_valid(talk_box) and talk_box.has_meta("rpg_window"): RpgUi.close_window(talk_box.get_meta("rpg_window"))
	elif is_instance_valid(talk_box):
		talk_box.queue_free()
		if sound and not leaving: RpgUi.sfx("close",-10.0)
	talk_box=null
	talk_window={}
	talk_id=""
	show_hud(true)

## A conversation (or the chest's list) takes the screen: the HUD steps back, as in the village;
## the prompt chip and the key cap over the furniture come back with the next update_hint.
func show_hud(shown: bool) -> void:
	if is_instance_valid(hud): hud.visible=shown
	if not shown:
		for item in [hint_label,bubble]:
			if is_instance_valid(item): item.visible=false

## What a dialogue choice does: small gifts and tips, or the telescope at night.
func run_choice(action: String) -> void:
	var id := talk_id
	# A choice with an outcome is heard in it (its own sound or its toast's chime), not a close as
	# well; 또 봐요 (bye) just closes.
	const OUTCOMES := ["gift","sell","coffee","seed_tip","shop_tip","flour","flower","fish_tip","telescope"]
	close_talk(not (action in OUTCOMES))
	var head: Vector3=hero.global_position+Vector3(0,1.6,0) if is_instance_valid(hero) else Vector3.ZERO
	match action:
		"gift":
			open_gift(id)
			return
		"sell":
			open_sell(id)
			return
		"coffee":
			# The outcome's own sound stands in for the toast's chime (hush_toast), never both.
			Interiors.play(self,"clink");RpgUi.hush_toast()
			message(tr("따뜻한 코코아를 받았어요. 달콤해요!"),true,"success")
			puff(head,Color("f4f4f2",0.7),5,0.8,0.15,0.12)
		"seed_tip":
			Interiors.play(self,"ding");RpgUi.hush_toast()
			message(tr("추천: 별사탕 씨앗은 햇살 좋은 밭에서 잘 자라요."))
		"shop_tip":
			Interiors.play(self,"ding");RpgUi.hush_toast()
			message(tr("오늘의 추천은 반짝이는 낚싯바늘이에요."))
		"flour":
			message(tr("밀가루 한 줌을 받았어요. 고소한 냄새가 나요."),true,"success")
			puff(head-Vector3(0,0.6,0),Color("f3ead6",0.8),8,0.5,0.3,0.12)
		"flower":
			Interiors.play(self,"chime");RpgUi.hush_toast()
			message(tr("들꽃 한 송이를 받았어요. 향기가 좋아요."),true,"success")
		"fish_tip":
			message(tr("물때가 바뀔 때 찌를 던져 보세요. 꼭 낚일 거예요!"))
		"telescope":
			for record in decor:
				if record.kind=="telescope" and not record.has("occupant"):
					use_decor(record);return
			message(tr("별자리가 보여요. 오늘은 고래자리가 또렷해요!"))
	if npcs.has(id) and npcs[id].body.has_method("smile"): npcs[id].body.smile(2.0)

# ---------------------------------------------------------------- residents' gifts

## "선물하기" inside a house: the same conversation as in the village (npc_gifts.gd), in this
## room's dialogue box, with hearts over the resident.
func open_gift(id: String) -> void:
	var say := func(lines: Array, choices: Array) -> void:
		if is_inside_tree() and npcs.has(id): open_talk(id,lines,choices)
	var done := func(reply: Dictionary) -> void:
		if not npcs.has(id): return
		var entry: Dictionary=npcs[id]
		NpcGifts.thanks_effect(stage,entry.holder.global_position)
		pop_over(entry,"♥")
		if entry.body.has_method("smile"): entry.body.smile(3.0)
		# thanks_effect's twinkle and the toast's chime are the sound, as in the village (no third chime).
		message(NpcGifts.thanks_text(Interiors.short_name(id,float(resident_clock().hour)),reply))
		var note := NpcGifts.letters_note(reply)
		if not note.is_empty(): create_tween().tween_callback(func(): message(note)).set_delay(2.6)
		gift_time=2.0
	NpcGifts.start(api,id,say,done)

## The residents' gifts in this house: a layout the village poll still reports current shows at
## once from the cache; then the guest route (owner and visitors alike) answers "unchanged" until
## the server moves something, every few seconds while the player is inside.
func refresh_gifts() -> void:
	if gift_home.is_empty() or gift_pending or api.token.is_empty() or VersionGate.is_blocked() or not is_inside_tree(): return
	gift_pending=true
	var home := gift_home
	var epoch_now := gift_epoch
	if gift_version<0:
		var cached := NpcGifts.cached(home)
		if not cached.is_empty(): await apply_gifts(cached,false)
	var reply: Dictionary=await api.request("/v1/social/npc-homes/%s?version=%d" % [home,gift_version])
	gift_pending=false
	if epoch_now!=gift_epoch or home!=gift_home or not reply.ok or reply.data.get("unchanged",false): return
	NpcGifts.remember(home,reply.data)
	await apply_gifts(reply.data,gift_version>=0)

func apply_gifts(data: Dictionary, fresh: bool) -> void:
	gift_version=int(data.get("version",0))
	var epoch_now := gift_epoch
	var wanted := {}
	for item in data.get("items",[]): wanted[str(item.id)]=item
	for id in gift_nodes.keys():
		var shown: Dictionary=gift_nodes[id].item
		if not wanted.has(id) or str(wanted[id].slot)!=str(shown.slot) or int(wanted[id].rotation)!=int(shown.rotation): drop_gift(id)
	for id in wanted:
		if gift_nodes.has(id): continue
		var item: Dictionary=wanted[id]
		var node := await load_item(item,"/v1/social/village/objects/")
		if epoch_now!=gift_epoch or gift_nodes.has(id):
			if node: node.queue_free()
			if epoch_now!=gift_epoch: return
			continue
		if node: add_gift(item,node,fresh)

## Sets a piece at its slot: on the floor, against the wall, or on the real table's top.
func add_gift(item: Dictionary, node: Node3D, fresh: bool) -> void:
	var level := clampi(int(item.get("floor",0)),0,floor_roots.size()-1)
	floor_roots[level].add_child(node)
	var at := Vector3(float(item.x),float(item.y),float(item.z))
	if str(item.kind)=="table": at.y=table_top(level,at,at.y)
	node.position=at+Vector3(0,0.02 if str(item.kind)=="floor" else 0.0,0)
	node.rotation_degrees.y=float(item.rotation)
	var raw: Array=item.get("size",[1,1,1])
	var wanted := Vector3(float(raw[0]),float(raw[1]),float(raw[2]))
	# An older one-mesh model loads 1.6 m long; indoors the server sized it smaller.
	if not item.get("studio",true) and node.has_meta("size") and Vector3(node.get_meta("size")).length()>0.001:
		node.scale*=wanted.length()/Vector3(node.get_meta("size")).length()
		node.set_meta("size",wanted)
	Loader.add_collision(node)
	var size: Vector3=node.get_meta("size",wanted)
	var turn := node.rotation.y
	var record := {"kind":"gift","id":str(item.id),"npc":str(item.get("npc","")),"name":str(item.get("name","")),"node":node,
		"center":Vector3(at.x,0,at.z),"yaw":turn,"mounted":str(item.kind)=="wall","solid":str(item.kind)=="floor","interactive":true,"glb":true,
		"size":size,"half":Vector2(size.x*0.5,size.z*0.5),
		"world_half":Vector2(absf(cos(turn))*size.x*0.5+absf(sin(turn))*size.z*0.5,absf(sin(turn))*size.x*0.5+absf(cos(turn))*size.z*0.5),
		"top":at.y+size.y,"floor":level,"room":Interiors.room_at(building_spec.floors[level],at.x)}
	decor_by_floor[level].append(record)
	gift_nodes[str(item.id)]={"item":item,"node":node,"record":record}
	# Put up while the player is inside: a little sparkle where it appears.
	if fresh and level==floor_index: Fx.arrive(floor_roots[level],node,null,true)

func drop_gift(id: String) -> void:
	var entry: Dictionary=gift_nodes.get(id,{})
	gift_nodes.erase(id)
	if entry.is_empty(): return
	var level := int(entry.record.floor)
	if level<decor_by_floor.size(): decor_by_floor[level].erase(entry.record)
	if last_used==entry.record: last_used={}
	if is_instance_valid(entry.node): entry.node.queue_free()

## The top of the room's own table (or chest, desk...) under a table-top slot.
func table_top(level: int, at: Vector3, fallback: float) -> float:
	var best := fallback;var distance := 0.8
	for record in decor_by_floor[level]:
		if record.kind=="gift" or record.mounted or not record.has("top"): continue
		if not record.kind in ["dining_table","round_cafe_table","desk","map_table","chest","side_table"]: continue
		var d: float=Vector2(record.center.x-at.x,record.center.z-at.z).length()
		if d<distance: distance=d;best=float(record.top)
	return best

## E on a gift: its own interaction plays on this screen (the piece is the resident's now), a seat
## or bed takes the walker, and a word says whose it is.
func use_gift(record: Dictionary) -> void:
	var node: Node3D=record.node
	if not is_instance_valid(node): return
	var kind: String=str(node.get("rest")) if node.has_method("use_interaction") else ""
	if kind=="sit" or kind=="lie": rest_on_crafted(node,kind)
	if node.has_method("local_event"): node.local_event("click")
	var owner_name := Interiors.short_name(str(record.npc),float(resident_clock().hour)) if not str(record.npc).is_empty() else ""
	say(tr("%s의 소중한 선물 · %s") % [owner_name,str(record.name)],record)
	Interiors.play(self,"pop")

## 단비's selling window at the counter (shop_sell.gd). E or Esc closes it, like the storage list.
func open_sell(id: String) -> void:
	# The talk it replaces goes quietly; the card opens with a window's open sound (ShopSell.window
	# has none of its own), and E or Esc closes it with close_talk's.
	close_talk(false)
	RpgUi.sfx("open",-8.0)
	talk_box=ShopSell.window(self,api,func(reply: Dictionary): sold(id,reply))
	talk_window={};talk_lines=[];talk_choices=[]
	for item in [name_panel,hint_chip,hint_label,bubble]:
		if is_instance_valid(item): item.visible=false

## A sale at the counter: sparkles over 단비, starseeds into the wallet line (the coins' jingle is
## ShopSell's).
func sold(id: String, reply: Dictionary) -> void:
	var stars := int(reply.get("stars",0))
	if npcs.has(id):
		var resident: Dictionary=npcs[id]
		pop_over(resident,"✦" if stars>0 else "♪")
		if stars>0:
			var at: Vector3=resident.holder.global_position
			Fx.burst(stage,at+Vector3(0,1.5,0),"sparkle",18,Color(0,0,0,0),0.5)
			Fx.glow(stage,at+Vector3(0,1.3,0),Color("ffd27a"),1.6,1.0)
	if stars>0 and is_instance_valid(wallet):
		wallet.text=tr("별씨 %d") % int(reply.get("shards",0))
		wallet.pivot_offset=wallet.size*0.5
		var bump := wallet.create_tween()
		bump.tween_property(wallet,"scale",Vector2.ONE*1.2,0.08)
		bump.tween_property(wallet,"scale",Vector2.ONE,0.14)
	# ShopSell's coin_gain is the sale's sound and stands in for the toast's chime (hush_toast, never
	# both); starseeds add a star over 단비's sparkles.
	if stars>0: RpgUi.sfx("star",-9.0)
	RpgUi.hush_toast()
	message(str(reply.get("message","")))

## E on the house's storage chest: what the residents keep in storage (names and pictures only),
## for the owner and visitors alike. E or Esc closes it.
func open_storage(record: Dictionary) -> void:
	if gift_home.is_empty(): return
	var reply: Dictionary=await api.request("/v1/social/npc-homes/%s" % gift_home)
	if not reply.ok or not is_inside_tree(): return
	close_talk(false)
	Interiors.play(self,"creak")
	if is_instance_valid(record.get("node")): Fx.wobble(record.node,0.05)
	# The shared window (RpgUi.window): a small parchment card in the middle with the close key (Esc);
	# E closes it too (advance_talk), shown as a key hint. The chest's creak is its opening sound
	# (no window open over it); closing it is the window's close.
	var w := RpgUi.window(self,tr("보관 상자"),{"width":RpgUi.WINDOW_W.small,"place":"centre","scroll":false,"on_close":close_talk,"id":"storage_chest","sound":false})
	talk_box=w.root
	talk_window={};talk_lines=[];talk_choices=[]
	w.shade.gui_input.connect(func(event): if event is InputEventMouseButton and event.pressed: close_talk())
	var column: VBoxContainer=w.body
	var stored: Array=reply.data.get("stored",[])
	var hour: float=float(resident_clock().hour)
	RpgUi.caption(column,tr("곧 꺼내 놓을지도 몰라요.") if not stored.is_empty() else tr("지금은 상자가 비어 있어요. 선물은 모두 집 안에 나와 있어요."),14)
	for item in stored.slice(0,8):
		var row := HBoxContainer.new();row.add_theme_constant_override("separation",12);column.add_child(row)
		row.add_child(RpgUi.icon(NpcGifts.icon_for(item.get("tags",[])),40))
		var words := VBoxContainer.new();row.add_child(words)
		RpgUi.label(words,str(item.get("name","")),16,RpgUi.PAPER_INK,false).add_theme_font_override("font",RpgUi.FONT_STRONG)
		RpgUi.caption(words,tr("%s의 선물") % Interiors.short_name(str(item.get("npc","")),hour),12)
	if stored.size()>8: RpgUi.caption(column,tr("…그리고 %d개 더") % (stored.size()-8),13)
	RpgUi.divider(column)
	RpgUi.key_hint(column,"interact",tr("닫기"),"paper").size_flags_horizontal=Control.SIZE_SHRINK_END
	show_hud(false)

## Gifts react to the walker coming near and leaving, on this screen only.
func gift_proximity() -> void:
	if gift_nodes.is_empty() or not is_instance_valid(hero): return
	for id in gift_nodes:
		var entry: Dictionary=gift_nodes[id]
		var node: Node3D=entry.node
		if not is_instance_valid(node) or not node.get_meta("studio",false) or not node.has_method("local_event"): continue
		var near: bool=int(entry.record.floor)==floor_index and hero.position.distance_to(node.position)<(2.5 if node.nearby else 1.8)
		if near!=node.nearby: node.local_event("near" if near else "leave")

## Name plates show only for residents close to the walker, like in the village.
func update_name_plates() -> void:
	if npcs.is_empty() or not is_instance_valid(hero): return
	for entry in npcs.values():
		if int(entry.floor)!=floor_index: continue
		var near: bool=entry.holder.global_position.distance_to(hero.global_position)<3.2 and entry.pose!="lie"
		hide_plate(entry.holder,entry.body,not near)
