extends Node3D
## A stand-in village for build_mode_check.gd: a world to put effects in and a walker.
var world: Node3D
var player: Node3D

func _init() -> void:
	world=Node3D.new();add_child(world)
	player=Node3D.new();world.add_child(player)
