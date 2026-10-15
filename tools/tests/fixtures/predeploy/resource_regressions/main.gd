extends Node
const TEMPLATE = "res://models/%s.glb"

func paths(name: String) -> void:
	var formatted = TEMPLATE % name
	var nested = choose("res://missing_nested_a.txt", "res://missing_nested_b.txt") + name
	var case_mismatch = "res://case.txt"
	print(formatted, nested, case_mismatch)

func choose(first: String, second: String) -> String:
	return first + second

func nested_dynamic_resource() -> void:
	var path = "res://models/" + choose("res://absent-nested.txt", "")
	print(path)
