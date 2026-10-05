extends Node
## Local onboarding, scoped to server + account. Currency and objects stay server-owned.
const I18n=preload("res://scripts/i18n.gd")
const Town=preload("res://scripts/town.gd")
const FILE="user://tutorial.cfg"
const LAST=6
const HEADINGS=["이곳은 나의 집이에요","사과를 모아 보세요","사과를 팔아 잎전을 얻어요","두 가지 재화를 알아봐요","원하는 물건을 의뢰해요","물건을 놓고 자유롭게 즐겨요"]
const BODIES=[
	"WASD로 움직여 금빛 표식을 따라 내 집 문 앞에 가 보세요. 집과 공방 문 앞에서는 E로 들어갈 수 있어요.",
	"사과 과수원으로 가서 E를 눌러 사과를 모으세요. 직접 얻은 물건은 B 생활 창고에서 확인할 수 있어요.",
	"씨앗 가게 앞에서 E를 누르고 사과를 한 개 팔아 보세요. 판매가 실제로 끝나면 다음 안내로 이어집니다.",
	"방금 판매한 사과로 잎전을 얻었어요. 잎전은 씨앗·미끼에, 별씨는 물건 제작에 써요. 별씨는 탐험에서 일곱 밤을 완주해 얻습니다.",
	"C 제작에서 원하는 물건을 문장으로 적어 보세요. 의뢰 후 견적을 확인하고, 제작 확정을 눌러야 만들기 시작해요. 완성까지 다른 활동을 즐겨도 괜찮아요.",
	"I 가방에서 보관 중인 물건을 골라 배치하세요. 바닥 클릭으로 놓기, R 회전, Esc 취소. 완성한 제작물도 가방에서 받을 수 있고 C로 진행을 확인해요."
]
var app: Node3D
var account := ""
var step := 0
var skipped := false
var completed := false
var reviewing := false
var craft_seen := false
var craft_requested := false
var quote_seen := false
var sale_coins := 0
var sale_apples := 0
var sale_version := 0
var panel: Control
var help_button: Button
var help_overlay: Control
var title: Label
var body: Label
var policy: Label
var action_button: Button
var signature := ""
var elapsed := 0.0

func active() -> bool:
	return (not completed or reviewing) and not skipped and step<LAST

func key() -> String:
	return "player_"+(str(app.api.base_url).trim_suffix("/")+"\n"+str(app.me.get("username","")).to_lower()).sha256_text()

func load_progress() -> void:
	var config := ConfigFile.new();config.load(FILE)
	step=clampi(int(config.get_value(account,"step",0)),0,LAST)
	skipped=bool(config.get_value(account,"skipped",false))
	completed=step==LAST
	craft_seen=bool(config.get_value(account,"craft_seen",false))
	craft_requested=bool(config.get_value(account,"craft_requested",false))
	quote_seen=bool(config.get_value(account,"quote_seen",false))
	sale_coins=int(config.get_value(account,"sale_coins",0))
	sale_apples=int(config.get_value(account,"sale_apples",0))
	sale_version=int(config.get_value(account,"sale_version",0))

func save() -> void:
	if reviewing or account.is_empty(): return
	var config := ConfigFile.new()
	var error := config.load(FILE)
	if error==OK or error==ERR_FILE_NOT_FOUND:
		for field in ["step","skipped","craft_seen","craft_requested","quote_seen","sale_coins","sale_apples","sale_version"]:
			config.set_value(account,field,get(field))
		error=config.save(FILE)
	if error!=OK: app.message(tr("처음 안내 진행을 저장하지 못했어요. 다음 접속에서 안내가 다시 나올 수 있어요."))

func bind() -> void:
	account=key();reviewing=false;load_progress()
	if is_instance_valid(panel): panel.queue_free()
	if is_instance_valid(help_button): help_button.queue_free()
	help_button=app.button(app.ui,tr("F1 · 처음 안내"),show_help)
	help_button.position=Vector2(24,207);help_button.custom_minimum_size.x=318
	var box: VBoxContainer=app.panel(Vector2(24,254),318,"hero")
	panel=box.get_parent()
	title=app.text(box,"",19)
	var scroll := ScrollContainer.new();scroll.custom_minimum_size=Vector2(280,240);scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;box.add_child(scroll)
	var content := VBoxContainer.new();content.size_flags_horizontal=Control.SIZE_EXPAND_FILL;content.add_theme_constant_override("separation",10);scroll.add_child(content)
	policy=app.text(content,"",13);policy.custom_minimum_size.x=260;policy.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;policy.modulate=Color("75562d")
	body=app.text(content,"",14);body.custom_minimum_size.x=260;body.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	action_button=app.button(box,"",perform,"primary")
	app.button(box,tr("안내 건너뛰기"),skip)
	signature="";route();update()

func clear_route() -> void:
	if not app.life.goal.get("tutorial",false): return
	app.life.goal={}
	if is_instance_valid(app.life.marker): app.life.marker.queue_free()

func route() -> void:
	if not active(): clear_route();return
	var target: String={0:"home",1:"apple",2:"shop"}.get(step,"")
	if target.is_empty(): clear_route();return
	for place in Town.PLACES:
		if place.id==target:
			app.life.goal=place.duplicate();app.life.goal.tutorial=true;return

func advance() -> void:
	step+=1
	if step==2:
		sale_coins=int(app.life.state.get("coins",0));sale_apples=int(app.life.state.get("bag",{}).get("apple",0));sale_version=int(app.life.state.get("version",0))
	if step==LAST:
		if reviewing: reviewing=false;load_progress()
		else: completed=true;save()
		app.message(tr("처음 안내를 마쳤어요! 자유롭게 즐기고, F1로 안내를 다시 볼 수 있어요."))
	else: save()
	route();signature="";update()

func skip() -> void:
	if reviewing: reviewing=false;load_progress()
	else: skipped=true;save()
	clear_route();signature="";update()
	app.message(tr("안내를 건너뛰었어요. 마을에서 F1을 누르면 이어서 볼 수 있어요."))

func can_craft() -> bool:
	return app.me.get("studio_tripo_enabled",false) and int(app.me.get("shards",0))>=20

func opened_craft() -> void:
	if not active() or step!=4: return
	craft_seen=true;save();signature=""

func accepted_craft(job: Dictionary) -> void:
	if not active() or step!=4 or not job.has("id"): return
	craft_requested=true
	if job.get("state","") in ["awaiting_confirmation","ready"]: quote_seen=true
	save();signature=""

func perform() -> void:
	if not active(): return
	if step<3: route();app.message(tr("금빛 표식을 따라가세요. 가까이에서 E로 상호작용할 수 있어요."))
	elif step==3: advance() # Knowledge page only; never grants currency.
	elif step==4:
		if craft_seen and (not can_craft() or craft_requested): advance()
		else: await app.open_craft()
	elif step==5:
		if is_instance_valid(app.preview): return
		if not app.right.get_parent().visible: app.toggle_drawer()

func update() -> void:
	if not is_instance_valid(panel) or not is_instance_valid(help_button): return
	var visible_now: bool=app.screen=="village" and not app.social.visiting() and not is_instance_valid(app.village_modal) and not blocks_input() and not app.right.get_parent().visible
	help_button.visible=visible_now
	panel.visible=visible_now and active() and not is_instance_valid(app.preview)
	if not active(): return
	var next_signature := "%s/%s/%s/%s/%s/%s/%s"%[step,TranslationServer.get_locale(),can_craft(),craft_seen,craft_requested,quote_seen,app.me.get("shards",0)]
	if next_signature==signature: return
	signature=next_signature
	title.text=tr("처음 안내 · %d/%d")%[step+1,LAST]+"\n"+tr(HEADINGS[step])
	body.text=tr(BODIES[step])
	policy.text=""
	if not app.me.get("studio_tripo_enabled",false): policy.text=tr("이 서버는 새 제작이 꺼져 있어요. 가입 때 받은 기존 물건으로 배치를 연습해요. 실시간 생성 체험이 아닙니다.")
	elif not craft_requested and int(app.me.get("shards",0))<20: policy.text=tr("지금은 제작할 별씨가 부족해요. 기존 물건으로 배치를 연습하고, 탐험 보상으로 제작비를 모으세요.")
	if step==4 and craft_requested:
		body.text+=tr("\n맡긴 의뢰는 C에서 견적과 진행을 확인하세요. 완성을 기다리지 않고 기존 물건으로 먼저 연습할 수 있어요.")
	action_button.text=tr("길잡이 표시") if step<3 else tr("이해했어요") if step==3 else (tr("기존 물건으로 배치 연습") if craft_seen and (not can_craft() or craft_requested) else tr("제작 의뢰 열기")) if step==4 else tr("가방 열기")

func _process(delta: float) -> void:
	if account.is_empty() or app.screen!="village": return
	elapsed+=delta
	if elapsed<.15: return
	elapsed=0
	if active() and not app.social.visiting():
		var state: Dictionary=app.life.state
		if step==0 and Vector2(app.player.position.x,app.player.position.z).distance_to(Town.HOME_DOOR)<2.7: advance()
		elif step==1 and int(state.get("bag",{}).get("apple",0))>0: advance()
		elif step==2 and int(state.get("version",0))>sale_version and int(state.get("coins",0))>sale_coins and int(state.get("bag",{}).get("apple",0))<sale_apples: advance()
		elif step==5 and app.me.get("objects",[]).any(func(obj): return obj.state=="placed"): advance()
	update()

func blocks_input() -> bool:
	return is_instance_valid(help_overlay)

func close_help() -> void:
	if is_instance_valid(help_overlay): help_overlay.get_parent().remove_child(help_overlay);help_overlay.queue_free()
	help_overlay=null
	app.player.controls_enabled=app.world_movement_allowed();update()

func resume() -> void:
	if completed: reviewing=true;step=0;skipped=false;craft_seen=false;craft_requested=false;quote_seen=false
	else: skipped=false;save()
	close_help();route();signature="";update()

func show_help() -> void:
	if blocks_input(): close_help();return
	help_overlay=Control.new();help_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);app.ui.add_child(help_overlay)
	var shade := ColorRect.new();shade.color=Color(0.025,0.05,0.06,.76);shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);help_overlay.add_child(shade)
	var box: VBoxContainer=app.panel(Vector2(265,110),750,"hero")
	var card: Node=box.get_parent();app.ui.remove_child(card);help_overlay.add_child(card)
	var header := HBoxContainer.new();box.add_child(header)
	app.text(header,tr("처음 안내와 조작"),25).size_flags_horizontal=Control.SIZE_EXPAND_FILL
	app.button(header,tr("닫기 · Esc"),close_help)
	var text: Label=app.text(box,tr("WASD 이동 · E 상호작용 · I 가방 · C 제작 · Tab 지도\nR 배치 회전 · Esc 취소/닫기 · M 소리\n\n1. 내 집 문 앞까지 금빛 표식을 따라가요.\n2. 사과 과수원에서 E로 사과를 모아요.\n3. 씨앗 가게에서 사과를 팔아 잎전을 얻어요.\n4. 잎전은 씨앗·미끼, 별씨는 제작에 써요. 별씨는 일곱 밤 탐험의 완주 보상이에요.\n5. C에서 자연어 의뢰와 견적·진행을 확인해요. 확정 전 비용을 확인하고, 완성될 때까지 다른 활동을 즐겨요.\n6. I에서 물건을 골라 놓고 공간을 꾸며요. 제작 제한·재화 부족이면 기존 물건으로 연습해요."),15)
	text.custom_minimum_size.x=700;text.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	app.button(box,tr("처음부터 다시 따라하기") if completed else tr("안내 이어보기"),resume,"primary")
	app.player.controls_enabled=false;update()
