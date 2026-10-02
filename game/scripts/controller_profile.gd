extends RefCounted
## Shared world scale and presentation tuning. Survival speed remains server-owned.
const CHARACTER_SCALE := 1.7
const BODY_RADIUS := .32
const BODY_HEIGHT := 1.5
const VILLAGE_WALK := 2.8
const VILLAGE_RUN := 4.5
const ROOM_WALK := 2.8
const TURN_RESPONSE := 14.0
const CAMERA_RESPONSE := 6.0
const CAMERA_OFFSET := Vector3(0,8.8,16.5)
const CAMERA_FOCUS_OFFSET := Vector3(0,1.0,-.55)
const CAMERA_DEFAULT := 14.5
const CAMERA_MIN := 12.0
const CAMERA_MAX := 26.0

static func damping(response: float,delta: float) -> float:
	return 1.0-exp(-response*maxf(delta,0.0))

static func ensure_input() -> void:
	for action in {"move_left":KEY_A,"move_right":KEY_D,"move_forward":KEY_W,"move_back":KEY_S}:
		if InputMap.has_action(action):continue
		InputMap.add_action(action)
		var event := InputEventKey.new()
		event.physical_keycode={"move_left":KEY_A,"move_right":KEY_D,"move_forward":KEY_W,"move_back":KEY_S}[action]
		InputMap.action_add_event(action,event)
