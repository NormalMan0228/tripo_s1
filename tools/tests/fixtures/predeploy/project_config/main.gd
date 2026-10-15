extends Node

func inspect_actions() -> void:
	Input.is_action_pressed("jump")
	Input.is_action_just_pressed("jump")
	InputMap.has_action("jump")
	Input.is_action_pressed("missing_pressed")
	Input.is_action_just_pressed("missing_just_pressed")
	Input.is_action_just_released("missing_released")
	InputMap.action_get_events("missing_map")
	InputMap.has_action("missing_has")
	Input.is_action_pressed(&"missing_string_name")
	Input.is_action_pressed(&"jump")
