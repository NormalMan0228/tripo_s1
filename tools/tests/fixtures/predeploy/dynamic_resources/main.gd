extends Node
const DIR = "res://models/"

func build_path(name: String) -> void:
	var by_constant = DIR + name + ".glb"
	var by_literal = "res://models/" + name + ".glb"
	var by_format = "res://models/%s.glb" % name
	var unresolved = "res://absent/" + name + ".glb"
	var missing_format = "res://absent/%s.glb" % name
	print(by_constant, by_literal, by_format, unresolved, missing_format)
