extends Node3D
## Stand-in for main.gd in the shadow folk tests: the members and calls the
## village module contract uses (player, camera, town, npcs, daylight, life,
## sound, world_audio, open_dialogue, message, floating_feedback), recorded so a
## test can read what the module showed.
const Town = preload("res://scripts/town.gd")
const Daylight = preload("res://scripts/daylight.gd")

class StubPlayer extends CharacterBody3D:
	var faced := Vector3.ZERO
	func _ready() -> void:
		collision_layer = 4
		collision_mask = 1|2|8
		var shape := CollisionShape3D.new()
		var capsule := CapsuleShape3D.new()
		capsule.radius = 0.32
		capsule.height = 1.5
		shape.shape = capsule
		shape.position.y = 0.75
		add_child(shape)
	func face_point(point: Vector3) -> void: faced = point
	func react(_kind: String) -> void: pass

class StubSound extends Node:
	var played: Array[String] = []
	func effect(kind: String) -> void: played.append(kind)

class StubAudio extends Node:
	var steps := 0
	func footstep(_surface: String, _speed: float) -> void: steps += 1

class StubLife extends Node:
	var state: Dictionary = {"bag":{}}

var player: CharacterBody3D
var camera: Camera3D
var town: Node3D
var npcs: Array[Node3D] = []
var daylight: Node
var life: Node
var sound: Node
var world_audio: Node
var village_modal: Control
var world: Node3D
var dialogues: Array = []
var messages: Array[String] = []
var floating: Array[String] = []

## Builds the real village layout (map, roads, places) under this node.
func build(view: Camera3D) -> void:
	world = self
	camera = view
	town = Town.new()
	town.camera = camera
	add_child(town)
	daylight = Daylight.new()
	daylight.override_hour = 12.0
	add_child(daylight)
	life = StubLife.new()
	add_child(life)
	sound = StubSound.new()
	add_child(sound)
	world_audio = StubAudio.new()
	add_child(world_audio)
	player = StubPlayer.new()
	add_child(player)
	player.position = Vector3(0, 30, -120)

## The four named villagers as markers with the same metas main.gd sets.
func spawn_villagers() -> void:
	var cast := {"map":["naru","나루 · 길잡이"],"wardrobe":["sora","소라 · 재단사"],"guide":["moru","모루 · 야영 전문가"],"angler":["haeru","해루 · 낚시꾼"]}
	for role in Town.VILLAGERS:
		var npc := Node3D.new()
		add_child(npc)
		npc.position = Town.point(Town.VILLAGERS[role], 0.02)
		npc.set_meta("title", cast[role][1])
		npc.set_meta("cast", cast[role][0])
		npc.set_meta("role", role)
		npcs.append(npc)

func open_dialogue(speaker: String, cast: String, lines: Array, choices: Array) -> void:
	dialogues.append({"speaker":speaker, "cast":cast, "lines":lines, "choices":choices})

func message(text: String) -> void:
	messages.append(text)

func floating_feedback(text: String, _at: Vector3, _color: Color) -> void:
	floating.append(text)
