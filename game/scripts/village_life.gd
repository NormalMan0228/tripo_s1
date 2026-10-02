extends Node
const Town=preload("res://scripts/town.gd")
const Map=preload("res://scripts/town_map.gd")
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
var fishing_bar: ProgressBar
var reel_button: Button
var cast_button: Button
var info: Label
var map_view: Control
var goal: Dictionary={}
var marker: Node3D
var bite_announced := false
var errors := {"life_missing_items":"재료가 부족해요. 창고와 씨앗 가게를 확인하세요.",
	"stale_life_version":"다른 요청으로 바뀐 상태를 새로 읽었어요. 다시 선택하세요.",
	"life_plot_occupied":"이미 심어 둔 작물이 있어요.","life_not_ready":"물을 준 뒤 작물이 자랄 때까지 기다려 주세요.",
	"life_already_watered":"이미 물을 주었어요.","life_empty_plot":"먼저 씨앗을 심어 주세요.",
	"life_already_fishing":"이미 던진 찌가 있어요.","life_not_fishing":"먼저 미끼를 달고 찌를 던져 주세요.",
	"life_regrowing":"다시 자라는 중이에요. 잠시 뒤에 찾아오세요.","life_not_enough_coins":"잎전이 부족해요. 수확물이나 물고기를 팔아 보세요.",
	"life_order_completed":"오늘의 배달을 이미 마쳤어요."}

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
	if reading or app.api.token.is_empty(): return
	reading=true
	var epoch: int=app.world_epoch
	var response: Dictionary=await app.api.request("/v1/homestead")
	reading=false
	if epoch!=app.world_epoch: return
	if response.ok: accept(response.data)
	elif app.screen=="village": app.message("마을 생활 정보를 읽지 못했어요. 다시 접속해 주세요.")
func action(kind: String, extra: Dictionary={}) -> bool:
	if pending or state.is_empty() or app.screen!="village": return false
	pending=true
	var epoch: int=app.world_epoch
	var response: Dictionary=await app.api.post("/v1/homestead",app.api.mutation(extra.merged({"action":kind,"version":state.version})))
	pending=false
	if epoch!=app.world_epoch: return false
	if not response.ok:
		app.message(errors.get(response.error,app.error_message(response.error)))
		await refresh()
		return false
	accept(response.data)
	app.message(response.data.message)
	app.sound.effect("reward" if kind in ["harvest","sell","order","reel"] else "gather")
	if kind in ["plant","water","harvest","gather"]: app.player.react("gather")
	return true
func closest() -> Dictionary:
	if app.screen!="village": return {}
	var p := Vector2(app.player.position.x,app.player.position.z)
	for i in Town.PLOTS.size():
		if p.distance_to(Town.PLOTS[i])<1.65: return {"id":"plot","title":"%d번 텃밭"%(i+1),"kind":"plot","index":i}
	for place in Town.PLACES:
		if place.kind=="farm": continue
		if p.distance_to(place.at)<2.3: return place
	return {}
func interact() -> void:
	var place := closest()
	if place.is_empty(): return
	match place.kind:
		"home","workshop":app.open_studio(place.kind)
		"plot": open_plot(place.index)
		"shop": open_shop()
		"fish": open_fishing(place.id)
		"gather":
			await action("gather",{"item":place.id})
		"bell":
			app.sound.effect("reward")
			app.floating_feedback("종소리가 마을에 퍼집니다",app.player.position,Color("f4d58e"))
			app.message("별바람 언덕에서 잠시 쉬어 가세요. Tab으로 다음 목적지를 고를 수 있어요.")
		"view":
			var v: VBoxContainer=app.modal_card("소나무 전망대")
			mode="view"
			app.camera.size=25
			app.text(v,"강 건너 텃밭과 남쪽 바다가 한눈에 보여요.\nEsc를 누르면 산책으로 돌아갑니다.",16)

func open_plot(index: int) -> void:
	if state.is_empty(): return
	current_plot=index
	var v: VBoxContainer=app.modal_card("햇살 텃밭 · %d번 밭"%(index+1))
	mode="plot"
	var plot: Dictionary=state.plots[index]
	app.text(v,"씨앗 심기 → 한 번 물주기 → 성장 → 수확\n마을을 떠나거나 게임을 꺼도 작물은 계속 자라요.",15)
	status_label=app.text(v,"",20)
	var row := HBoxContainer.new()
	v.add_child(row)
	if plot.is_empty():
		for crop in ["turnip","pumpkin"]:
			var data: Dictionary=state.catalog.crops[crop]
			var b: Button=app.button(row,"%s 심기 · 씨앗 %d개\n성장 %d초 / 수확 2개"%[data.name,state.bag.get(crop+"_seed",0),data.seconds],func():
				await action("plant",{"plot":index,"item":crop})
				if mode=="plot" and is_instance_valid(app.village_modal): open_plot(index))
			b.custom_minimum_size=Vector2(320,80)
			b.disabled=state.bag.get(crop+"_seed",0)<1
	elif not plot.watered:
		app.button(row,"물뿌리개로 물주기",func():
			app.player.equip("watering_can")
			await action("water",{"plot":index})
			if mode=="plot" and is_instance_valid(app.village_modal): open_plot(index))
	else:
		reel_button=app.button(row,"다 자란 작물 수확하기",func():
			await action("harvest",{"plot":index})
			if mode=="plot" and is_instance_valid(app.village_modal): open_plot(index))
	app.text(v,"씨앗 가게에서 씨앗을 사고 수확물을 잎전으로 바꿀 수 있어요.",14)

func open_storage() -> void:
	if state.is_empty(): return
	var v: VBoxContainer=app.modal_card("마을 생활 창고")
	mode="storage"
	app.text(v,"잎전 %d  ·  수확 %d개  ·  낚은 물고기 %d마리"%[state.coins,state.harvested,state.caught],20)
	app.text(v,"잎전은 씨앗과 미끼를 사는 마을 전용 돈이에요. 별씨와는 별개입니다.",14)
	var grid := GridContainer.new()
	grid.columns=3
	v.add_child(grid)
	for item in state.catalog.names:
		var card := PanelContainer.new()
		var paper := StyleBoxFlat.new()
		paper.bg_color=Color("f2e6cf")
		paper.set_corner_radius_all(9)
		paper.set_content_margin_all(10)
		card.add_theme_stylebox_override("panel",paper)
		card.custom_minimum_size=Vector2(220,64)
		grid.add_child(card)
		var row := HBoxContainer.new();row.add_theme_constant_override("separation",10);card.add_child(row)
		var icon := TextureRect.new();icon.texture=load("res://assets/items/"+life_icon(item)+".svg")
		icon.custom_minimum_size=Vector2(38,38);icon.expand_mode=TextureRect.EXPAND_IGNORE_SIZE;icon.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		row.add_child(icon)
		app.text(row,"%s  × %d"%[state.catalog.names[item],state.bag.get(item,0)],16)
	app.text(v,"낚시 도감: 강농어 %d마리 / 은빛 도미 %d마리\n호수에는 강농어, 바다에는 은빛 도미가 더 자주 찾아와요."%[state.collection.get("perch",0),state.collection.get("silverfish",0)],15)
	app.button(v,"지도에서 텃밭과 낚시터 찾기",open_map)

func life_icon(item: String) -> String:
	if item in ["perch","silverfish"]:return "fish"
	if item.ends_with("_seed") or item=="bait":return "seed"
	if item=="herb":return "fiber"
	if item in ["turnip","pumpkin"]:return "harvest"
	return "berry"

func open_shop() -> void:
	if state.is_empty(): return
	var v: VBoxContainer=app.modal_card("씨앗 가게 · 잎전 %d"%state.coins)
	mode="shop"
	app.text(v,"잎전으로 씨앗과 미끼를 사고, 직접 얻은 수확물을 팔아요.",14)
	var row := HBoxContainer.new()
	v.add_child(row)
	for item in ["turnip_seed","pumpkin_seed","bait"]:
		var cost: int={"turnip_seed":2,"pumpkin_seed":4,"bait":1}[item]
		var b: Button=app.button(row,"%s +1 · %d잎전"%[state.catalog.names[item],cost],func():
			await action("buy",{"item":item})
			if mode=="shop" and is_instance_valid(app.village_modal): open_shop())
		b.disabled=state.coins<cost
	app.text(v,"수확물 판매 · 한 개씩",18)
	var grid := GridContainer.new()
	grid.columns=3
	v.add_child(grid)
	for item in state.catalog.prices:
		var b: Button=app.button(grid,"%s %d개 · +%d잎전"%[state.catalog.names[item],state.bag.get(item,0),state.catalog.prices[item]],func():
			await action("sell",{"item":item})
			if mode=="shop" and is_instance_valid(app.village_modal): open_shop())
		b.disabled=state.bag.get(item,0)<1
	app.text(v,"오늘의 마을 식탁: 순무 2개 + 강농어 1마리 → 20잎전\n매일 오전 9시(한국 시간)에 새 배달이 열려요.",15)
	var order: Button=app.button(v,"식탁에 배달하기" if state.order_available else "오늘 배달 완료",func():
		await action("order")
		if mode=="shop" and is_instance_valid(app.village_modal): open_shop())
	order.disabled=not state.order_available or state.bag.get("turnip",0)<2 or state.bag.get("perch",0)<1

func open_fishing(spot: String) -> void:
	if state.is_empty(): return
	current_spot=spot
	var v: VBoxContainer=app.modal_card("바람 호수 낚시" if spot=="pond" else "조개빛 해변 낚시")
	mode="fish"
	var panel: Control=v.get_parent()
	panel.position=Vector2(24,205)
	panel.custom_minimum_size.x=420
	panel.size.x=420
	for child in v.get_child(0).get_children():
		if child is Label: child.add_theme_font_size_override("font_size",20)
	for child in app.village_modal.get_children():
		if child is ColorRect: child.color.a=0.08
	app.player.face_point(app.player.position+Vector3(0,0,3))
	app.player.equip("rod")
	app.text(v,"금빛 입질 신호에 E로 챔질하세요.\n사용 가능한 미끼 %d개"%state.bag.get("bait",0),14)
	status_label=app.text(v,"",19)
	fishing_bar=ProgressBar.new()
	fishing_bar.custom_minimum_size=Vector2(380,18)
	fishing_bar.show_percentage=false
	v.add_child(fishing_bar)
	var row := HBoxContainer.new()
	v.add_child(row)
	var cast: Button=app.button(row,"찌 던지기 · 미끼 1",func():
		bite_announced=false
		await action("cast",{"spot":spot})
		if mode=="fish" and is_instance_valid(app.village_modal): open_fishing(spot))
	cast.disabled=state.bag.get("bait",0)<1 or (state.fishing is Dictionary and now()<=state.fishing.ends_at)
	cast_button=cast
	reel_button=app.button(row,"E · 챔질",reel)
	app.button(row,"거두기",func():
		await action("cancel_fishing")
		if mode=="fish" and is_instance_valid(app.village_modal): open_fishing(spot))

func reel() -> void:
	if mode!="fish" or pending: return
	app.player.react("gather")
	await action("reel")
	if mode=="fish" and is_instance_valid(app.village_modal): open_fishing(current_spot)

func open_map() -> void:
	var v: VBoxContainer=app.modal_card("물결빛 마을 산책 지도")
	mode="map"
	app.text(v,"목적지를 고르면 길잡이 표식이 생겨요. 강은 두 다리로 건너세요.",14)
	var row := HBoxContainer.new()
	v.add_child(row)
	map_view=Map.new()
	row.add_child(map_view)
	var list := VBoxContainer.new()
	row.add_child(list)
	for i in Town.PLACES.size():
		var place: Dictionary=Town.PLACES[i]
		var b: Button=app.button(list,"%d  %s"%[i+1,place.title],func():
			goal=place
			app.close_village_modal()
			app.message(place.title+"에 길잡이를 표시했어요."))
		b.custom_minimum_size.x=315
	app.button(v,"B · 생활 창고 열기",open_storage)

func closed() -> void:
	if mode=="view" and is_instance_valid(app.camera): app.camera.size=16
	mode=""
	if is_instance_valid(app.player) and app.screen!="survival" and app.player.equipped in ["rod","watering_can"]: app.player.equip("")

func _process(delta: float) -> void:
	if not is_instance_valid(app) or app.screen!="village" or not is_instance_valid(app.town): return
	if not is_instance_valid(app.village_modal) and not mode.is_empty(): closed()
	poll+=delta
	if poll>2 and not pending:
		poll=0
		refresh()
	if state.is_empty(): return
	app.town.update_plots(state,now())
	if mode=="plot" and is_instance_valid(status_label):
		var plot: Dictionary=state.plots[current_plot]
		if plot.is_empty(): status_label.text="빈 밭이에요. 어떤 작물을 심을까요?"
		elif not plot.watered: status_label.text="흙이 말라 있어요. 물을 주세요."
		else:
			var remaining := maxf(0,float(plot.ready_at)-now())
			status_label.text="수확할 준비가 되었어요!" if remaining<=0 else "자라는 중 · %d초 남음"%int(ceil(remaining))
			if is_instance_valid(reel_button): reel_button.disabled=remaining>0 or pending
	var fish=state.get("fishing")
	var active: bool=mode=="fish" and fish is Dictionary and now()<=fish.ends_at
	var bite: bool=active and now()>=fish.bite_at
	if mode=="fish" and is_instance_valid(status_label):
		status_label.text="찌를 던져 보세요." if fish==null else ("입질! 지금 챔질하세요!" if bite else ("조용히 입질을 기다려요…" if active else "물고기가 달아났어요. 다시 던져 보세요."))
		status_label.modulate=Color("ffdf7d") if bite else Color.WHITE
		fishing_bar.value=clampf((float(fish.ends_at)-now())/3.5*100,0,100) if bite else 0
		reel_button.disabled=fish==null or pending
		if is_instance_valid(cast_button): cast_button.disabled=pending or state.bag.get("bait",0)<1 or active
		if bite and not bite_announced:
			bite_announced=true
			app.sound.effect("click")
	var cast_at := Vector3(-7,-0.4,18.3) if current_spot=="pond" else Vector3(26,-1.7,36)
	var hand: Vector3=app.player.position+Vector3(0.35,2.2,0.7)
	if is_instance_valid(app.player.tool_node): hand=app.player.tool_node.to_global(app.player.tool_node.get_meta("line_tip",Vector3(0,2.3,0)))
	app.town.update_fishing(active,cast_at,bite,hand)
	if mode=="map" and is_instance_valid(map_view):
		map_view.player_at=Vector2(app.player.position.x,app.player.position.z)
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
		if goal.id=="pond": marker.position.y=0
		if Vector2(app.player.position.x,app.player.position.z).distance_to(goal.at)<2:
			goal={}
			marker.queue_free()

func goal_text() -> String:
	if goal.is_empty():
		var note := "Tab · 마을 지도  /  B · 생활 창고\n서쪽 텃밭에서 첫 씨앗을 심어 보세요."
		if not state.is_empty(): note+="\n\n잎전 %d  ·  미끼 %d개"%[state.coins,state.bag.get("bait",0)]
		return note
	var distance := Vector2(app.player.position.x,app.player.position.z).distance_to(goal.at)
	return "%s · %.0fm\n금빛 표식을 따라 산책하세요.\nTab · 다른 목적지 고르기"%[goal.title,distance]
