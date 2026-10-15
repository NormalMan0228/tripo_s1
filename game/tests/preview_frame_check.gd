extends SceneTree
## Preview cameras (village inspector, room bag) frame the whole object: every corner of a wide, a tall
## and a small box lands inside the view, and the object fills a fair part of it (task 73).
const PreviewFrame = preload("res://scripts/preview_frame.gd")
var failed := false

func expect(value: bool, description: String) -> void:
	print(("PASS " if value else "FAIL ") + description)
	if not value: failed = true

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var view := SubViewport.new()
	view.size = Vector2i(320, 260)
	root.add_child(view)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 2.7
	view.add_child(camera)
	camera.position = Vector3(2, 1.75, 3)
	for size in [Vector3(2.4, 0.8, 1.2), Vector3(0.6, 2.4, 0.6), Vector3(0.3, 0.2, 0.3), Vector3(3.0, 3.0, 3.0)]:
		PreviewFrame.fit(camera, size)
		await process_frame
		var inside := true
		var reach := 0.0
		for i in 8:
			var corner: Vector3 = Vector3(float(i & 1) - 0.5, float((i >> 1) & 1), float((i >> 2) & 1) - 0.5) * size
			var at: Vector2 = camera.unproject_position(corner)
			inside = inside and at.x >= 0.0 and at.y >= 0.0 and at.x <= view.size.x and at.y <= view.size.y
			reach = maxf(reach, maxf(absf(at.x - view.size.x * 0.5) / view.size.x, absf(at.y - view.size.y * 0.5) / view.size.y))
		expect(inside and reach > 0.25, "a %s box shows whole and fills the view (%.2f)" % [size, reach])
	expect(camera.position.y > 0.0 and camera.position.z > 0.0, "the camera keeps its viewing side")
	print("PREVIEW_FRAME " + ("FAILED" if failed else "OK"))
	quit(1 if failed else 0)
