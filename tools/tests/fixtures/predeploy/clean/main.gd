extends Node
const FakeCode = "func fake(): var duplicate = 1; MissingClass.bad(); done.connect(handler)"
const Explanation = "# this hash remains within a string"
# func fake():
# Input.is_action_pressed("not_defined_in_a_comment")
# done.connect(handler)
const ExistingResource = "res://present.txt"

func first() -> void:
	var local = 1
	Input.is_action_pressed("jump")
	print(local)

func second() -> void:
	var local = 2
	InputMap.has_action("jump")
	print(local)

class Inner:
	var item = 1
	func first() -> void:
		pass

var item = 2

func strings_are_not_code() -> void:
	var text = "done.connect(handler); done.connect(handler); Input.is_action_pressed('not_an_action')"
	print(text)
