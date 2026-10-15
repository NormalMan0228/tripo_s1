extends Node
const ChildScript = preload("res://child.gd")
const PathChildScript = preload("res://path_child.gd")

func valid_calls() -> void:
	FixtureChild.own_method()
	FixtureChild.inherited_method()
	FixturePathChild.inherited_method()
	ChildScript.own_method()
	ChildScript.inherited_method()
	PathChildScript.inherited_method()
	ChildScript.new()
	FileAccess.file_exists("res://parent.gd")

func invalid_calls() -> void:
	FixtureChild.absent_method()
	ChildScript.another_absent_method()

func quoted_call_is_not_code() -> void:
	var example = "FixtureChild.not_a_real_call(); ChildScript.not_a_real_call()"
	print(example)
