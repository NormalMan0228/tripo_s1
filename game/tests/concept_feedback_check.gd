extends SceneTree
const CraftPanel=preload("res://scripts/craft_panel.gd")
class FakeApi extends Node:
	var sent := {}
	func mutation(value := {}) -> Dictionary: return value
	func post(path: String, value: Dictionary) -> Dictionary:
		sent={"path":path,"body":value}
		return {"ok":true,"data":{"state":"queued"}}
class FakeTracker extends Node:
	var api := FakeApi.new()
	var followed := ""
	func follow(value: String) -> void: followed=value
var failures := 0
func check(value: bool, words: String) -> void:
	print(("PASS " if value else "FAIL ")+words)
	if not value: failures+=1
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var panel=CraftPanel.new();root.add_child(panel)
	panel.form=VBoxContainer.new();panel.add_child(panel.form)
	panel.status=VBoxContainer.new();panel.add_child(panel.status)
	panel.kinds_row=preload("res://scripts/craft_kinds_row.gd").new();panel.add_child(panel.kinds_row)
	var tracker=FakeTracker.new();root.add_child(tracker);tracker.add_child(tracker.api)
	panel.tracker=tracker;panel.job_id="feedback-test";panel.cap=200
	var value={"id":panel.job_id,"state":"awaiting_confirmation","cost":20,"concept":{"draws":1,"max_draws":4,"estimate_with_concept":35,"estimate_text_only":25},"provenance":{}}
	panel.show_job(value)
	check(is_instance_valid(panel.concept_feedback) and panel.concept_feedback.editable,"feedback entry is visible and editable")
	check(panel.concept_feedback.max_length==500,"feedback length matches server")
	panel.concept_feedback.text="지붕은 파랗게";panel.concept_feedback.text_changed.emit(panel.concept_feedback.text)
	await panel.redraw_concept()
	check(tracker.api.sent.body.get("feedback")=="지붕은 파랗게" and tracker.api.sent.path.ends_with("/redraw"),"feedback is sent with redraw")
	check(tracker.followed==panel.job_id,"tracker follows edited picture")
	panel.show_job(value)
	check(panel.concept_feedback.text=="지붕은 파랗게","same picture preserves draft after a failed redraw")
	value.concept.draws=2;value.concept.feedback="지붕은 파랗게"
	panel.show_job(value)
	check(panel.concept_feedback.text.is_empty(),"successful new picture starts a fresh feedback draft")
	value.concept.draws=4;panel.show_job(value)
	check(not panel.concept_feedback.editable,"redraw limit disables feedback editing")
	panel.free();tracker.free()
	print("CONCEPT_FEEDBACK_DONE checks=7 failures=",failures)
	quit(1 if failures else 0)
