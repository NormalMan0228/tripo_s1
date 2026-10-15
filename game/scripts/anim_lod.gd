extends RefCounted
## Animation level of detail for characters (residents, villagers, room figures): how many frames
## pass between two rig updates. The follow camera is orthographic and sits ~47 m back, so camera
## distance said nothing about what is on screen: residents in plain view stepped at 3-8 frames.
## Now anything on screen (or within MARGIN of its edge) animates every frame; off screen it is
## judged by its ground distance from the focus (the walker).
const MARGIN := 3.0

## The camera's frustum planes, once per frame for a loop over many characters.
static func planes(camera: Camera3D) -> Array:
	if camera == null or not is_instance_valid(camera) or not camera.is_inside_tree(): return []
	return camera.get_frustum()

static func inside(frustum: Array, point: Vector3, margin := MARGIN) -> bool:
	for plane in frustum:
		if (plane as Plane).distance_to(point) > margin: return false
	return true

## 1 on screen; off screen 3 near the focus, 8 far away. No camera: every frame.
static func stride(frustum: Array, at: Vector3, focus: Vector3) -> int:
	if frustum.is_empty(): return 1
	if inside(frustum, at+Vector3(0, 1.0, 0)): return 1
	return 3 if Vector2(at.x-focus.x, at.z-focus.z).length() < 40.0 else 8
