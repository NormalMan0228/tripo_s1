extends SceneTree
class DelayedStudio:
	extends "res://scripts/studio.gd"
	var calls := 0
	func _ready() -> void:pass
	func _process(_delta: float) -> void:pass
	func load_item(_obj: Dictionary) -> Node3D:
		calls+=1;var serial := calls
		await get_tree().create_timer(.12 if serial%2 else .035).timeout
		var value := Node3D.new();value.set_meta("serial",serial);return value
var failures: Array[String]=[]
func check(value: bool,label: String) -> void:
	if not value:failures.append(label)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	var app := DelayedStudio.new();root.add_child(app)
	app.stage=Node3D.new();app.add_child(app.stage)
	app.status_label=Label.new();app.add_child(app.status_label)
	app.selected={"id":"first","rotation":0};app.begin_place()
	await create_timer(.01).timeout;app.clear_selection()
	await create_timer(.16).timeout
	check(not is_instance_valid(app.ghost) and app.stage.get_child_count()==0,"cancel rejects delayed placement")
	app.selected={"id":"second","rotation":0};app.begin_place();app.begin_place()
	await create_timer(.16).timeout
	check(app.stage.get_child_count()==1 and app.ghost.get_meta("serial")==3,"latest duplicate placement wins once")
	app.clear_selection();await process_frame
	app.data={"objects":[{"id":"same","rotation":0}]};app.select_item(0)
	await create_timer(.01).timeout;app.clear_selection()
	# Selecting the same id again must not revive the discarded preview.
	app.selected={"id":"same","rotation":0}
	await create_timer(.16).timeout
	check(not is_instance_valid(app.inspected),"selection generation rejects a stale same-id response")
	print("STUDIO_RACES ",JSON.stringify({"ok":failures.is_empty(),"failures":failures}))
	app.queue_free();await process_frame;quit(0 if failures.is_empty() else 1)
