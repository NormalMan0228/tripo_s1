extends SceneTree
## The IME helper moves a syllable that was still being composed when focus changed back to the field
## it was typed in: into another text field (it arrives there and is moved back) or onto a button.
## The open composition is simulated by setting the helper's state, as no IME can run in a test.
var failed := false

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ")+description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var helper: Node = root.get_node("ImeCaret")
	var box := VBoxContainer.new(); root.add_child(box)
	var a := LineEdit.new(); var b := LineEdit.new(); var c := TextEdit.new(); var button := Button.new()
	for n in [a, b, c, button]: box.add_child(n)
	await process_frame
	a.grab_focus(); a.text = "한"; a.caret_column = 1
	helper.composing_field = a; helper.composing_text = "글"
	b.grab_focus()
	b.insert_text_at_caret("글")  # what Windows does: commit into the newly focused field
	for i in 3: await process_frame
	expect(a.text == "한글" and b.text == "", "syllable moved back from the next LineEdit (a='%s' b='%s')" % [a.text, b.text])
	c.grab_focus(); c.text = "입"; c.set_caret_column(1)
	helper.composing_field = c; helper.composing_text = "력"
	button.grab_focus()
	await process_frame
	expect(c.text == "입력", "syllable committed to its TextEdit when focus went to a button (c='%s')" % c.text)
	b.grab_focus(); b.text = ""
	helper.composing_field = b; helper.composing_text = "ㅌ"
	a.grab_focus()
	for i in 20: await process_frame
	expect(b.text == "ㅌ" and a.text == "한글", "nothing arrived: committed to its own field after a few frames (b='%s' a='%s')" % [b.text, a.text])
	quit(1 if failed else 0)
