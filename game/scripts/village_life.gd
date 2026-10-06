extends Node
## Village life loop: farming (till, plant, water, harvest), shore fishing and
## foraging. The server (homestead.py) owns bag, plots, catches and respawns; this
## node stages each action in the world (farm.gd, fishing.gd, forage.gd) and keeps
## the old entry points main.gd uses: closest(), interact(), reel(), mode, goal_text().
const Town=preload("res://scripts/town.gd")
const Map=preload("res://scripts/town_map.gd")
const Art=preload("res://scripts/life_art.gd")
const Icon=preload("res://scripts/life_icon.gd")
const Farm=preload("res://scripts/farm.gd")
const Forage=preload("res://scripts/forage.gd")
const Fishing=preload("res://scripts/fishing.gd")
const RpgUi=preload("res://scripts/rpg_ui.gd")
const CROP_ORDER := ["turnip","carrot","pumpkin","strawberry","sunflower"]
var app: Node3D
var state: Dictionary={}
var synced_at := 0.0
var pending := false
var reading := false
var poll := 0.0
var mode := ""
var current_plot := 0
var current_spot := "pond"
var status_label: Label
var map_view: Control
var goal: Dictionary={}
var marker: Node3D
var farm: Node3D
var forage: Node3D
var fishing: Node
var sfx: Node
var last_reward: Dictionary={}
var focus: Dictionary={}
var focus_key := ""
var shore: Dictionary={}
var shore_from := Vector3.INF
var seed_plot := -1
var seed_choices: Array=[]
var errors := {"life_missing_items":tr("재료가 부족해요. 창고와 씨앗 가게를 확인하세요."),
	"stale_life_version":tr("그새 상황이 바뀌었어요. 다시 골라 주세요."),
	"life_plot_occupied":tr("이미 심어 둔 작물이 있어요."),"life_not_ready":tr("물을 준 뒤 작물이 자랄 때까지 기다려 주세요."),
	"life_already_watered":tr("이미 물을 주었어요."),"life_empty_plot":tr("먼저 씨앗을 심어 주세요."),
	"life_already_fishing":tr("이미 던진 찌가 있어요."),"life_not_fishing":tr("먼저 미끼를 달고 찌를 던져 주세요."),
	"life_regrowing":tr("다시 자라는 중이에요. 잠시 뒤에 찾아오세요."),"life_not_enough_coins":tr("잎전이 부족해요. 수확물이나 물고기를 팔아 보세요."),
	"life_order_completed":tr("오늘의 배달을 이미 마쳤어요."),"life_plot_limit":tr("밭은 최대 %d칸까지 일굴 수 있어요.") % 18,
	"life_not_farmland":tr("여기는 밭을 일굴 수 없는 땅이에요. 풍차 들판에서 일궈 보세요."),"life_plot_overlap":tr("다른 밭과 너무 가까워요."),
	"life_too_fast":tr("숨을 고르고 천천히 모아 보세요."),"life_reel_too_fast":tr("줄이 팽팽해요. 조금 더 감아 주세요."),
	"life_no_plot":tr("그 밭은 이제 없어요."),"life_starter_plot":tr("처음 받은 여섯 칸은 그대로 둘게요."),
	"life_nothing_here":tr("이미 주웠거나 사라졌어요.")}

func _ready() -> void:
	sfx=preload("res://scripts/life_sfx.gd").new()
	add_child(sfx)
	fishing=Fishing.new()
	fishing.life=self
	fishing.app=app
	add_child(fishing)

func now() -> float: return float(state.get("server_time",0))+(Time.get_ticks_msec()*0.001-synced_at)
func accept(data: Dictionary) -> void:
	if not state.is_empty() and data.version<state.version: return
	state=data
	synced_at=Time.get_ticks_msec()*0.001
func enter() -> void:
	state={}
	mode=""
	goal={}
	await refresh()
func refresh() -> void:
	if app.social.visiting():
		app.social.accept_crops()
		return
	if reading or app.api.token.is_empty(): return
	reading=true
	var epoch: int=app.world_epoch
	var response: Dictionary=await app.api.request("/v1/homestead")
	reading=false
	if epoch!=app.world_epoch: return
	if response.ok: accept(response.data)
	elif app.screen=="village": app.message(tr("마을 생활 정보를 읽지 못했어요. 다시 접속해 주세요."))

## One server action; returns the new state (with "reward") or {} after an error.
func request(kind: String, extra: Dictionary={}) -> Dictionary:
	if app.social.visiting():
		app.message(tr("방문한 마을의 텃밭과 물건은 주인만 수정할 수 있습니다."))
		return {}
	if pending or state.is_empty() or app.screen!="village": return {}
	pending=true
	var epoch: int=app.world_epoch
	var response: Dictionary=await app.api.post("/v1/homestead",app.api.mutation(extra.merged({"action":kind,"version":state.version})))
	pending=false
	if epoch!=app.world_epoch: return {}
	if not response.ok:
		app.message(errors.get(response.error,app.error_message(response.error)))
		sfx.play("escape",1.3,-4)
		await refresh()
		return {}
	accept(response.data)
	last_reward=response.data.get("reward",{})
	return response.data

## Older call sites (shop, tree shaking, tests): message, sound and item feedback.
func action(kind: String, extra: Dictionary={}) -> bool:
	var data: Dictionary=await request(kind,extra)
	if data.is_empty(): return false
	app.message(data.message)
	app.sound.effect("reward" if kind in ["harvest","sell","order","reel"] else "gather")
	if kind in ["plant","water","harvest","gather"]: app.player.react("gather")
	if kind=="gather" and data.get("reward",{}).has("items"): fly_items(data.reward.items,app.player.position+Vector3(0,1.2,0))
	return true

# ------------------------------------------------------------------ world

## Farm beds and gather spots live under the village town node.
func attach_world() -> void:
	if is_instance_valid(farm) and farm.get_parent()==app.town: return
	farm=Farm.new()
	farm.name="LifeFarm"
	app.town.add_child(farm)
	forage=Forage.new()
	forage.name="LifeForage"
	app.town.add_child(forage)
	forage.build()
	# town.gd's fixed plots sat on the path; the beds now come from the server.
	for old in app.town.get("plots"):
		if is_instance_valid(old): old.visible=false
	for child in app.town.get_children():
		if child is Label3D and child.text==tr("햇살 텃밭 · 씨앗을 심고 물을 주세요"):
			child.position=Town.point(Vector2(-19.3,-37.2),2.6)
			child.text=tr("햇살 텃밭 · E로 땅을 일구고 씨앗을 심어요")

func plot_entry(index: int) -> Dictionary:
	var plot: Dictionary=state.plots[index]
	var stage := Farm.stage(plot,now())
	var crop_name: String=tr(state.get("catalog",{}).get("crops",{}).get(str(plot.get("crop","")),{}).get("name",""))
	var prompt := ""
	match stage:
		0: prompt=tr("씨앗 심기")
		1: prompt=tr("%s에 물 주기") % crop_name
		5: prompt=tr("%s 수확하기") % crop_name
		_:
			var left := int(ceil(maxf(0,float(plot.ready_at)-now())))
			prompt=tr("%s 자라는 중 · %d:%02d") % [crop_name,left/60,left%60]
	return {"id":"plot","kind":"plot","index":index,"stage":stage,"title":prompt,"prompt":prompt}

func closest() -> Dictionary:
	if app.screen!="village" or not is_instance_valid(app.player): return {}
	var key := "%d/%s/%s" % [Engine.get_process_frames(),app.player.position.snapped(Vector3.ONE*0.05),app.player.facing.snapped(Vector3.ONE*0.1)]
	if key==focus_key: return focus
	focus_key=key
	focus=find_focus()
	return focus

func find_focus() -> Dictionary:
	var p := Vector2(app.player.position.x,app.player.position.z)
	var facing := Vector2(app.player.facing.x,app.player.facing.z)
	facing=facing.normalized() if facing.length()>0.1 else Vector2(0,1)
	var ahead := p+facing*0.9
	for place in Town.PLACES:
		if place.kind in ["farm","fish"]: continue
		if p.distance_to(place.at)<2.3: return place
	for door in Town.DOORS:
		if p.distance_to(door.at)<1.9:
			# Dark windows mean everyone inside is asleep or out: the door stays shut
			# (residents.gd). The player's own rooms are always open.
			var door_state: Dictionary=preload("res://scripts/residents.gd").building_state(door.room,app.daylight.current_hour() if is_instance_valid(app.daylight) else -1.0,int(preload("res://scripts/residents.gd").clock().day))
			if not door_state.enterable:
				var why: String={"asleep":"🔒 %s · 불이 꺼져 있어요","closed":"🔒 %s · 문을 닫았어요","away":"🔒 %s · 아무도 없어요"}.get(str(door_state.reason),"🔒 %s · 불이 꺼져 있어요")
				return {"id":door.id,"title":door.title,"kind":"door","room":door.room,"at":door.at,"locked":true,"message":door_state.message,"prompt":tr(why) % tr(door.title)}
			return {"id":door.id,"title":door.title,"kind":"door","room":door.room,"at":door.at,"prompt":tr("%s 들어가기") % tr(door.title)}
	if app.social.visiting() or state.is_empty() or not is_instance_valid(farm): return {}
	var index: int=farm.index_at(ahead)
	if index<0: index=farm.index_at(p)
	if index>=0 and index<state.plots.size(): return plot_entry(index)
	var spot: Dictionary=forage.nearest(ahead)
	if spot.is_empty(): spot=forage.nearest(p)
	if not spot.is_empty(): return {"id":spot.id,"kind":"forage","spot":spot,"title":forage.prompt(spot),"prompt":forage.prompt(spot)}
	if farm.in_zone(p) or farm.in_zone(ahead):
		var cell: Vector2=Farm.snap(p+facing*1.9)
		if farm.till_problem(cell,state.plots,int(state.get("catalog",{}).get("max_plots",18))).is_empty():
			var count: int=state.plots.size()
			return {"id":"till","kind":"till","cell":cell,"title":tr("괭이로 땅 일구기"),"prompt":tr("괭이로 땅 일구기 · 밭 %d/%d") % [count,int(state.catalog.get("max_plots",18))]}
	for place in Town.PLACES:
		if place.kind=="fish" and p.distance_to(place.at)<2.3:
			var at: Vector3=Town.CAST_POINTS.get(place.id,Town.CAST_POINTS.pond)
			var target: Dictionary=fishing.find_cast(app.player.position,at-app.player.position)
			if target.is_empty(): target={"at":Vector3(at.x,Fishing.water_level(Vector2(at.x,at.z)),at.z),"spot":"pond" if place.id=="pond" else "sea"}
			return place.merged({"target":target,"prompt":tr("낚시하기 · %s") % tr(place.title)})
	if app.player.position.distance_to(shore_from)>0.25:
		shore_from=app.player.position
		shore=fishing.find_cast(app.player.position,Vector3(facing.x,0,facing.y))
	if not shore.is_empty():
		var where: String=tr(Fishing.SPOT_NAMES.get(shore.spot,"바다"))
		return {"id":shore.spot,"kind":"fish","title":tr("낚시하기"),"prompt":tr("낚시하기 · %s") % where,"target":shore}
	return {}

func interact() -> void:
	var place := closest()
	if app.social.visiting():
		# Visitors may enter the host's home and the public buildings, never the workshop.
		if place.get("id","")=="home": app.open_studio("home")
		elif place.get("kind","")=="door" and place.get("locked",false): knock(place)
		elif place.get("kind","")=="door" and place.room!="workshop": app.open_studio(place.room)
		else: app.social.open_menu()
		return
	if place.is_empty() or pending: return
	match place.kind:
		"door":
			if place.get("locked",false): knock(place)
			else: app.open_studio(place.room)
		"home","workshop":app.open_studio(place.kind)
		"plot": use_plot(place.index)
		"till": till(place.cell)
		"forage": gather_spot(place.spot)
		"shop": open_shop()
		"fish": open_fishing(place.get("target",place.id))
		"gather":
			await action("gather",{"item":place.id})
		"bell":
			app.sound.effect("reward")
			app.floating_feedback(tr("종소리가 마을에 퍼집니다"),app.player.position,Color("f4d58e"))
			app.message(tr("등대 종소리를 들으며 잠시 쉬어 가세요. Tab으로 다음 목적지를 고를 수 있어요."))
		"view":
			var v: VBoxContainer=app.modal_card(tr("별빛 천문대 전망"))
			mode="view"
			app.camera.size=34
			app.text(v,tr("다섯 섬과 다리가 한눈에 보여요.\nEsc를 누르면 산책으로 돌아갑니다."),16)

## A locked door: two soft knocks and the reason as a toast instead of entering.
func knock(place: Dictionary) -> void:
	sfx.play("rock",0.55,-3)
	get_tree().create_timer(0.17).timeout.connect(func(): if is_instance_valid(sfx): sfx.play("rock",0.6,-5))
	app.message(str(place.get("message","")) if not str(place.get("message","")).is_empty() else tr("불이 꺼져 있어요. 다들 곤히 자고 있나 봐요."))

# ------------------------------------------------------------------ farming

func bed_point(index: int) -> Vector3:
	var plot: Dictionary=state.plots[index]
	return Town.point(Vector2(float(plot.x),float(plot.z)),0.2)

func use_plot(index: int) -> void:
	match Farm.stage(state.plots[index],now()):
		0: open_plot(index)
		1: water(index)
		5: harvest(index)
		_:
			sfx.play("rustle",1.2,-6)
			app.message(tr("무럭무럭 자라고 있어요. 마을을 떠나도 계속 자랍니다."))

## Seed picker for an empty bed (kept under the old name for tests and main.gd).
func open_plot(index: int) -> void:
	if state.is_empty() or index>=state.plots.size(): return
	if state.plots[index].get("crop"):
		use_plot(index)
		return
	app.close_village_modal()
	seed_plot=index
	seed_choices=[]
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter=Control.MOUSE_FILTER_IGNORE
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel",RpgUi.panel_style("night"))
	panel.position=Vector2(250,500)
	panel.custom_minimum_size=Vector2(780,0)
	RpgUi.slide_in(panel,Vector2(0,24))
	RpgUi.sfx("open",-10.0)
	root.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation",8)
	panel.add_child(v)
	RpgUi.label(v,tr("어떤 씨앗을 심을까요?"),22,RpgUi.GOLD)
	RpgUi.divider(v,Color(RpgUi.GOLD,.55))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation",8)
	v.add_child(row)
	var crops: Dictionary=state.get("catalog",{}).get("crops",{})
	for crop in CROP_ORDER:
		if not crops.has(crop): continue
		var count := int(state.bag.get(crop+"_seed",0))
		var data: Dictionary=crops[crop]
		var b := Button.new()
		b.custom_minimum_size=Vector2(146,112)
		b.focus_mode=Control.FOCUS_NONE
		b.disabled=count<1
		b.name="Seed_"+crop
		RpgUi.name_tip(b,"%s ×%d" % [tr(str(state.get("catalog",{}).get("names",{}).get(crop+"_seed",data.name))),count],str(seed_choices.size()+1))
		for look in ["normal","hover","pressed","disabled"]:
			b.add_theme_stylebox_override(look,RpgUi.frame({"normal":"slot_paper","hover":"slot_paper_hover","pressed":"slot_paper_hover","disabled":"slot_paper_empty"}[look]))
		var stack := VBoxContainer.new()
		stack.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		stack.mouse_filter=Control.MOUSE_FILTER_IGNORE
		stack.alignment=BoxContainer.ALIGNMENT_CENTER
		stack.add_theme_constant_override("separation",0)
		b.add_child(stack)
		var icon := Icon.make(crop,46)
		icon.size_flags_horizontal=Control.SIZE_SHRINK_CENTER
		stack.add_child(icon)
		for text in ["%d  %s ×%d" % [seed_choices.size()+1,tr(data.name),count],tr("%d초 · 수확 %d") % [int(data.seconds),int(data.get("yield",1))]]:
			var l := RpgUi.label(stack,text,13 if text.begins_with(str(seed_choices.size()+1)) else 11,Color("2f2a1f"),false)
			l.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
		var chosen: String=crop
		b.pressed.connect(func():
			app.sound.effect("click")
			plant(index,chosen))
		row.add_child(b)
		seed_choices.append(crop)
	var foot := HBoxContainer.new()
	v.add_child(foot)
	RpgUi.label(foot,tr("1~5 또는 클릭으로 고르기 · 씨앗은 씨앗 노점에서 살 수 있어요 · Esc 닫기"),12,RpgUi.GOLD,false).size_flags_horizontal=Control.SIZE_EXPAND_FILL
	if index>=int(state.get("catalog",{}).get("starter_plots",6)):
		app.button(foot,tr("풀밭으로 되돌리기"),func():
			app.close_village_modal()
			Art.burst(app.world,bed_point(index),"leaf",14)
			sfx.play("rustle")
			await request("untill",{"plot":index}))
	claim_hud(root)
	mode="seeds"

func plant(index: int, crop: String) -> void:
	app.close_village_modal()
	app.player.face_point(bed_point(index))
	app.player.react("craft")
	sfx.play("seed")
	Art.burst(app.world,bed_point(index),"seed",12)
	var data := await request("plant",{"plot":index,"item":crop})
	if data.is_empty(): return
	preload("res://scripts/fx.gd").burst(app.world,bed_point(index)+Vector3(0,0.15,0),"seed",10)

func water(index: int) -> void:
	var at := bed_point(index)
	app.player.face_point(at)
	app.player.equip("watering_can")
	app.player.react("craft")
	sfx.play("water")
	for i in 3:
		get_tree().create_timer(i*0.18).timeout.connect(func(): if is_instance_valid(app.world): Art.burst(app.world,at+Vector3(0,0.9,0),"drop",14))
	var data := await request("water",{"plot":index})
	get_tree().create_timer(0.9).timeout.connect(func(): if is_instance_valid(app.player) and app.player.equipped=="watering_can" and mode!="fish": app.player.equip(""))
	if data.is_empty(): return
	preload("res://scripts/fx.gd").burst(app.world,at+Vector3(0,0.3,0),"drop",14)

func harvest(index: int) -> void:
	var at := bed_point(index)
	app.player.face_point(at)
	app.player.react("gather")
	var data := await request("harvest",{"plot":index})
	if data.is_empty(): return
	farm.harvest_pop(index,app.player.position)
	sfx.play("pop")
	get_tree().create_timer(0.35).timeout.connect(func(): sfx.play("collect"))
	var items: Dictionary=data.get("reward",{}).get("items",{})
	fly_items(items,at+Vector3(0,0.6,0),0.45)
	var delay := 0.0
	for item in items:
		preload("res://scripts/fx.gd").item_pop(app,at+Vector3(0,0.5,0),item,int(items[item]),delay)
		delay += 0.12

func till(cell: Vector2) -> void:
	var at := Town.point(cell,0.05)
	app.player.face_point(at)
	app.player.equip("hoe")
	dress_hoe()
	app.player.react("attack")
	await get_tree().create_timer(0.16).timeout
	sfx.play("hoe")
	Art.burst(app.world,at,"dirt",16)
	Art.burst(app.world,at,"dust",8)
	var data := await request("till",{"x":cell.x,"z":cell.y})
	get_tree().create_timer(0.5).timeout.connect(func(): if is_instance_valid(app.player) and app.player.equipped=="hoe": app.player.equip(""))
	if data.is_empty(): return
	app.floating_feedback(tr("새 밭 · %d/%d") % [state.plots.size(),int(state.catalog.get("max_plots",18))],at,Color("e8d0a0"))

## The generic tool is a hammer shape; give it a hoe's flat blade.
func dress_hoe() -> void:
	var tool: Node3D=app.player.tool_node
	if not is_instance_valid(tool) or tool.has_meta("hoe"): return
	tool.set_meta("hoe",true)
	for child in tool.get_children(): child.queue_free()
	Art.part(tool,"rod",Vector3(0,0.2,0),Vector3(0.05,1.25,0.05),Color("9a744c"))
	Art.part(tool,"box",Vector3(0,0.82,0.11),Vector3(0.24,0.05,0.24),Color("b9c3c4"),Vector3(0.25,0,0),0.4)
	Art.part(tool,"box",Vector3(0,0.82,0.0),Vector3(0.07,0.08,0.07),Color("6b6f70"))

# ------------------------------------------------------------------ foraging

func gather_spot(spot: Dictionary) -> void:
	var at: Vector3=spot.root.global_position
	app.player.face_point(at)
	app.player.react("gather")
	forage.anticipate(spot)
	sfx.play(Forage.SOUNDS[spot.kind],randf_range(0.95,1.08))
	var data := await request("gather",{"node":spot.id})
	forage.finish(spot,not data.is_empty())
	if data.is_empty(): return
	var items: Dictionary=data.get("reward",{}).get("items",{})
	fly_items(items,at+Vector3(0,0.4,0),0.15)
	get_tree().create_timer(0.2).timeout.connect(func(): sfx.play("collect",1.1,-3))
	# Icons instead of words; rare finds get a sparkle on top.
	var delay := 0.0
	for item in items:
		preload("res://scripts/fx.gd").item_pop(app,at+Vector3(0,0.4,0),item,int(items[item]),delay)
		delay += 0.12
	if items.has("pearl") or items.has("gold_mushroom") or items.has("copper_ore"):
		preload("res://scripts/fx.gd").burst(app.world,at+Vector3(0,0.3,0),"sparkle",16)

## Item icons pop out of the world and fly into the storage slot on the hotbar.
func fly_items(items: Dictionary, from: Vector3, delay := 0.0) -> void:
	if not is_instance_valid(app.camera) or not is_instance_valid(app.ui): return
	var start: Vector2=app.camera.unproject_position(from)
	var goal_at := Vector2(640,760)
	var slot: Control=null
	if is_instance_valid(app.get("expedition_button")) and app.expedition_button.get_parent().get_child_count()>3:
		slot=app.expedition_button.get_parent().get_child(3)
		goal_at=slot.get_global_rect().get_center()
	var k := 0
	for item in items:
		for n in mini(int(items[item]),3):
			var icon := Icon.make(item,44)
			icon.position=start-Vector2(22,22)
			icon.pivot_offset=Vector2(22,22)
			icon.scale=Vector2.ZERO
			app.ui.add_child(icon)
			var rise := start-Vector2(22,22)+Vector2(randf_range(-40,40),-70-randf_range(0,30))
			var t := icon.create_tween()
			t.tween_interval(delay+k*0.08)
			t.tween_property(icon,"scale",Vector2.ONE*1.25,0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			t.parallel().tween_property(icon,"position",rise,0.28).set_ease(Tween.EASE_OUT)
			t.tween_property(icon,"position",goal_at-Vector2(22,22),0.5).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
			t.parallel().tween_property(icon,"scale",Vector2.ONE*0.55,0.5)
			t.tween_callback(func():
				icon.queue_free()
				if is_instance_valid(slot):
					slot.pivot_offset=slot.size*0.5
					var bump := slot.create_tween()
					bump.tween_property(slot,"scale",Vector2.ONE*1.12,0.07)
					bump.tween_property(slot,"scale",Vector2.ONE,0.12))
			k+=1

# ------------------------------------------------------------------ fishing

## Puts a HUD control in the game's modal slot so E reaches reel() and Esc closes.
func claim_hud(node: Control) -> void:
	app.village_modal=node
	app.ui.add_child(node)
	app.player.controls_enabled=false

## target: a {"at":Vector3,"spot":String} cast or a legacy spot id ("pond"/"sea").
func open_fishing(target) -> void:
	if state.is_empty(): return
	if target is String:
		var at: Vector3=Town.CAST_POINTS.get(target,Town.CAST_POINTS.pond)
		target={"at":Vector3(at.x,Fishing.water_level(Vector2(at.x,at.z)),at.z),"spot":target}
	app.close_village_modal()
	current_spot=target.spot
	mode="fish"
	fishing.begin(target)

func reel() -> void:
	if mode!="fish": return
	fishing.press()

# ------------------------------------------------------------------ menus

func open_storage() -> void:
	if state.is_empty(): return
	var v: VBoxContainer=app.modal_card(tr("마을 생활 창고"))
	mode="storage"
	app.text(v,tr("잎전 %d  ·  수확 %d개  ·  낚은 물고기 %d마리  ·  채집 %d번")%[state.coins,state.harvested,state.caught,int(state.get("gathered",0))],18)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size=Vector2(700,330)
	scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	var grid := GridContainer.new()
	grid.columns=4
	grid.add_theme_constant_override("h_separation",8)
	grid.add_theme_constant_override("v_separation",8)
	scroll.add_child(grid)
	for item in state.catalog.names:
		if int(state.bag.get(item,0))<1: continue
		grid.add_child(item_card(item,"× %d" % int(state.bag.get(item,0))))
	if grid.get_child_count()==0: app.text(v,tr("아직 모은 물건이 없어요. 밭과 바닷가, 숲 그늘을 둘러보세요."),15)
	app.text(v,tr("잎전은 씨앗과 미끼를 사는 마을 전용 돈이에요. 별씨와는 별개입니다."),13)
	var row := HBoxContainer.new()
	v.add_child(row)
	app.button(row,tr("낚시 도감 %d/%d") % [state.collection.size(),state.catalog.get("fish",{}).size()],open_log)
	app.button(row,tr("지도에서 텃밭과 낚시터 찾기"),open_map)

func item_card(item: String, detail: String) -> PanelContainer:
	var card := PanelContainer.new()
	var paper := RpgUi.frame("slot_paper")
	paper.set_content_margin_all(9)
	card.add_theme_stylebox_override("panel",paper)
	card.custom_minimum_size=Vector2(166,58)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation",8)
	card.add_child(row)
	row.add_child(Icon.make(item,42))
	var text := VBoxContainer.new()
	text.add_theme_constant_override("separation",0)
	row.add_child(text)
	app.text(text,tr(state.catalog.names.get(item,item)),14).add_theme_color_override("font_color",Color("3b2a1c"))
	app.text(text,detail,13).add_theme_color_override("font_color",Color("7a5a2c"))
	return card

## Fish log: every species with its water, time of day, count and best size.
func open_log() -> void:
	if state.is_empty(): return
	var fish: Dictionary=state.catalog.get("fish",{})
	var v: VBoxContainer=app.modal_card(tr("낚시 도감 · %d/%d종") % [state.collection.size(),fish.size()])
	mode="log"
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size=Vector2(700,400)
	scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	var grid := GridContainer.new()
	grid.columns=4
	grid.add_theme_constant_override("h_separation",8)
	grid.add_theme_constant_override("v_separation",8)
	scroll.add_child(grid)
	var times := {"any":"언제나","day":"낮","night":"밤"}
	for kind in fish:
		var data: Dictionary=fish[kind]
		var caught: int=int(state.collection.get(kind,0))
		var card := PanelContainer.new()
		var paper := RpgUi.frame("slot_paper" if caught else "slot_paper_empty")
		paper.set_content_margin_all(9)
		card.add_theme_stylebox_override("panel",paper)
		card.custom_minimum_size=Vector2(166,150)
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation",0)
		card.add_child(col)
		var art := Icon.make(kind,84,caught==0)
		art.custom_minimum_size=Vector2(150,76)
		col.add_child(art)
		var title: Label=app.text(col,tr(data.name) if caught else "???",15)
		title.add_theme_color_override("font_color",Color("3b2a1c"))
		var stars: String="★".repeat(int(data.rarity))
		var waters := PackedStringArray()
		for w in data.spots: waters.append(tr(Fishing.SPOT_NAMES.get(w,w)))
		var info: Label=app.text(col,"%s  %s · %s" % [stars,"/".join(waters),tr(times.get(data.time,""))],12)
		info.add_theme_color_override("font_color",Color("7a5a2c"))
		var best: float=float(state.get("records",{}).get(kind,0))
		var record: Label=app.text(col,tr("%d마리 · 최고 %.1fcm") % [caught,best] if caught else tr("아직 못 만났어요"),12)
		record.add_theme_color_override("font_color",Color("5d4a35"))
		grid.add_child(card)
	app.text(v,tr("지금은 %s이에요. 밤에만 나오는 물고기도 있어요.") % (tr("밤") if state.get("night",false) else tr("낮")),13)

func open_shop() -> void:
	if state.is_empty(): return
	var v: VBoxContainer=app.modal_card(tr("씨앗 가게 · 잎전 %d")%state.coins)
	mode="shop"
	app.text(v,tr("잎전으로 씨앗과 미끼를 사고, 직접 얻은 수확물을 팔아요."),14)
	var row := HBoxContainer.new()
	v.add_child(row)
	var shop: Dictionary=state.catalog.get("shop",{"turnip_seed":2,"pumpkin_seed":4,"bait":1})
	for item in shop:
		var cost: int=int(shop[item])
		var b: Button=app.button(row,tr("%s\n+1 · %d잎전")%[tr(state.catalog.names[item]),cost],func():
			await action("buy",{"item":item})
			if mode=="shop" and is_instance_valid(app.village_modal): open_shop())
		b.disabled=state.coins<cost
		b.custom_minimum_size.x=112
	app.text(v,tr("가진 물건 팔기 · 누르면 최대 20개씩"),16)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size=Vector2(700,220)
	scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	var grid := GridContainer.new()
	grid.columns=3
	scroll.add_child(grid)
	for item in state.catalog.prices:
		var count := int(state.bag.get(item,0))
		if count<1: continue
		var amount := mini(count,20)
		var b: Button=app.button(grid,tr("%s %d개 → +%d잎전")%[tr(state.catalog.names[item]),amount,int(state.catalog.prices[item])*amount],func():
			await action("sell",{"item":item,"quantity":amount})
			if mode=="shop" and is_instance_valid(app.village_modal): open_shop())
		b.custom_minimum_size.x=228
	if grid.get_child_count()==0: app.text(grid,tr("팔 물건이 없어요."),14)
	app.text(v,tr("오늘의 마을 식탁: 순무 2개 + 강농어 1마리 → 20잎전\n매일 오전 9시(한국 시간)에 새 배달이 열려요."),14)
	var order: Button=app.button(v,tr("식탁에 배달하기") if state.order_available else tr("오늘 배달 완료"),func():
		await action("order")
		if mode=="shop" and is_instance_valid(app.village_modal): open_shop())
	order.disabled=not state.order_available or state.bag.get("turnip",0)<2 or state.bag.get("perch",0)<1

func open_map() -> void:
	# Tab again folds the map away.
	if mode=="map" and is_instance_valid(app.village_modal):
		app.close_village_modal()
		return
	# The route guide (guide.gd) takes the picks: pins, glowing roads, the window stays.
	var guide: Node=preload("res://scripts/guide.gd").current
	var v: VBoxContainer=app.modal_card(tr("물결빛 마을 산책 지도"))
	mode="map"
	app.text(v,tr("장소나 지도 위를 누르면 빛나는 길이 이어져요.") if guide else tr("목적지를 고르면 길잡이 표식이 생겨요. 섬과 섬은 다리로 이어져 있어요."),14)
	var row := HBoxContainer.new()
	v.add_child(row)
	map_view=Map.new()
	row.add_child(map_view)
	var list := VBoxContainer.new()
	row.add_child(list)
	for i in Town.PLACES.size():
		var place: Dictionary=Town.PLACES[i]
		var b: Button=app.button(list,"%d  %s"%[i+1,tr(place.title)],func():
			if is_instance_valid(guide):
				guide.pick_place(place.id)
				return
			goal=place
			app.close_village_modal()
			app.message(tr(place.title)+tr("에 길잡이를 표시했어요.")))
		b.custom_minimum_size.x=315
	if is_instance_valid(guide): guide.attach_map(map_view,list)
	app.button(v,tr("B · 생활 창고 열기"),open_storage)

func closed() -> void:
	if mode=="view" and is_instance_valid(app.camera): app.camera.size=preload("res://scripts/controller_profile.gd").VILLAGE_CAMERA_DEFAULT
	if mode=="fish":
		# Leaving mid-cast frees the line on the server so the next cast is not refused.
		if fishing.phase in ["flying","waiting","fight"] and state.get("fishing") is Dictionary: request("cancel_fishing")
		fishing.end()
	mode=""
	if is_instance_valid(app.player) and app.screen!="survival" and app.player.equipped in ["rod","watering_can","hoe"]: app.player.equip("")

func _unhandled_input(event: InputEvent) -> void:
	if mode!="seeds" or not event is InputEventKey or not event.pressed or event.echo: return
	var n: int=event.physical_keycode-KEY_1
	if n>=0 and n<seed_choices.size() and int(state.bag.get(seed_choices[n]+"_seed",0))>0:
		get_viewport().set_input_as_handled()
		plant(seed_plot,seed_choices[n])

func _process(delta: float) -> void:
	if not is_instance_valid(app) or app.screen!="village" or not is_instance_valid(app.town): return
	attach_world()
	if not is_instance_valid(app.village_modal) and not mode.is_empty(): closed()
	poll+=delta
	if poll>2 and not pending:
		poll=0
		refresh()
	if state.is_empty(): return
	farm.sync(state.get("plots",[]),now())
	forage.sync(state,now())
	fishing.update(delta)
	var f: Dictionary=closest() if not is_instance_valid(app.village_modal) else {}
	if f.get("kind","")=="till": farm.show_ghost(f.cell,true)
	else: farm.hide_ghost()
	forage.highlight(f.get("id","") if f.get("kind","")=="forage" else "")
	if mode=="map" and is_instance_valid(map_view):
		map_view.player_at=Vector2(app.player.position.x,app.player.position.z)
		var guide: Node=preload("res://scripts/guide.gd").current
		if is_instance_valid(guide) and guide.active():
			map_view.has_destination=true
			map_view.destination=guide.target.at
		else:
			map_view.has_destination=not goal.is_empty()
			if not goal.is_empty(): map_view.destination=goal.at
		map_view.queue_redraw()
	if not goal.is_empty():
		if not is_instance_valid(marker):
			marker=Node3D.new()
			app.world.add_child(marker)
			var arrow=preload("res://scripts/art.gd").cone(marker,Vector3(0,3.8,0),0.32,0.65,Color("f6d17d"))
			arrow.rotation.z=PI
		marker.position=Town.point(goal.at)
		if Vector2(app.player.position.x,app.player.position.z).distance_to(goal.at)<2:
			goal={}
			marker.queue_free()

func goal_text() -> String:
	if app.social.visiting(): return tr("%s님의 마을 방문 중") % str(app.social.data.get("host_name", tr("친구")))
	if goal.is_empty():
		var lines := PackedStringArray()
		var plots: Array=state.get("plots",[])
		var ripe := plots.filter(func(plot): return Farm.stage(plot,now())==5).size()
		var dry := plots.filter(func(plot): return Farm.stage(plot,now())==1).size()
		if ripe>0: lines.append("▸ "+tr("다 자란 작물 %d칸 수확하기") % ripe)
		elif dry>0: lines.append("▸ "+tr("마른 밭 %d칸에 물 주기") % dry)
		elif not plots.any(func(plot): return plot.get("crop")): lines.append("▸ "+tr("풍차 들판 텃밭에 씨앗 심기"))
		else: lines.append("▸ "+tr("텃밭 작물 돌보기"))
		lines.append("▸ "+tr("물가를 바라보고 E로 낚시하기"))
		lines.append("▸ "+tr("바닷가 조개·숲 그늘 버섯 모으기"))
		if not state.is_empty() and int(state.get("bag",{}).get("bait",0))>0: lines.append("\n"+tr("미끼 %d개") % state.bag.get("bait",0))
		return "\n".join(lines)
	var distance := Vector2(app.player.position.x,app.player.position.z).distance_to(goal.at)
	return "▸ %s\n%s" % [tr(goal.title),tr("금빛 표식까지 %.0fm") % distance]
