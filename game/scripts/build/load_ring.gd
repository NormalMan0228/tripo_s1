extends Control
## A small spinning ring by the pointer while a piece's model downloads for placing (item 66).
## It only appears after a short wait, so a model already in the cache never flashes it, and it
## fades out when the ghost is up (or the load failed).
const RpgUi = preload("res://scripts/rpg_ui.gd")
const DELAY := 0.18
const RADIUS := 11.0

var age := 0.0
var spin := 0.0
var done := false
var word: Label

static func start(host: Control) -> Control:
	var ring: Control=load("res://scripts/build/load_ring.gd").new()
	ring.name="LoadRing"
	host.add_child(ring)
	return ring

## Ends the ring (safe on a freed or null ring).
static func finish(ring) -> void:
	if ring is Control and is_instance_valid(ring): ring.stop()

func _ready() -> void:
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	top_level=true
	z_index=50
	modulate.a=0.0
	size=Vector2(150,28)
	word=RpgUi.label(self,tr("불러오는 중"),12,RpgUi.INK)
	word.position=Vector2(RADIUS*2+8,3)
	word.mouse_filter=Control.MOUSE_FILTER_IGNORE

func stop() -> void:
	if done: return
	done=true
	var t := create_tween()
	t.tween_property(self,"modulate:a",0.0,0.12)
	t.tween_callback(queue_free)

func _process(delta: float) -> void:
	age+=delta
	spin+=delta*7.0
	if not done and age>=DELAY: modulate.a=minf(1.0,modulate.a+delta*6.0)
	global_position=get_global_mouse_position()+Vector2(16,12)
	queue_redraw()

func _draw() -> void:
	var centre := Vector2(RADIUS+2,RADIUS+3)
	draw_circle(centre,RADIUS+3,Color(0.07,0.09,0.1,0.75))
	draw_arc(centre,RADIUS-1,0.0,TAU,32,Color(1,1,1,0.15),3.0,true)
	draw_arc(centre,RADIUS-1,spin,spin+TAU*0.32,16,RpgUi.GOLD,3.0,true)
