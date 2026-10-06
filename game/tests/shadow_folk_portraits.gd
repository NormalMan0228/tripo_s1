extends SceneTree
## Renders each shadow folk figure head-and-shoulders on a transparent background
## to artifacts/shadow-folk-portraits/<id>.png (2x size). tools step: the Python
## composer adds the soft card and writes game/assets/ui/shadow_<id>.png.
## Needs a window (not --headless):
##   Godot --path game --script res://tests/shadow_folk_portraits.gd -- [--ids=miller,shopkeeper]
const Folk = preload("res://scripts/shadow_folk.gd")
const Figure = preload("res://scripts/shadow_figure.gd")
const SMILING := ["kid", "postman", "poet", "regular", "stroller", "shopkeeper"]

class Holder extends Node:
	var walkers: Array = []
	var villager_points: Array[Vector2] = []
	func player_xz() -> Vector2: return Vector2(1e6, 1e6)
	func footstep(_w: Node, _s: float) -> void: pass

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var out := ProjectSettings.globalize_path("res://../artifacts/shadow-folk-portraits/")
	DirAccess.make_dir_recursive_absolute(out)
	var only: Array = []
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--ids="): only = Array(arg.trim_prefix("--ids=").split(","))
	for entry in Folk.FOLK:
		if not only.is_empty() and not entry.id in only: continue
		var view := SubViewport.new()
		view.size = Vector2i(960, 1200)
		view.transparent_bg = true
		view.own_world_3d = true
		view.msaa_3d = Viewport.MSAA_4X
		view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(view)
		var walker: CharacterBody3D = Figure.new()
		walker.configure(entry, null, null)
		view.add_child(walker)
		walker.dress()
		walker.set_physics_process(false)
		walker.nameplate.visible = false
		walker.visual.rotation.y = 0.22
		if entry.id in SMILING: walker.smile(100.0)
		var night := 1.0 if entry.get("hours", "") == "night" else 0.0
		walker.set_night(night*0.35)
		for glint in walker.glints: glint.visible = false
		if is_instance_valid(walker.lantern):
			walker.lantern_glow.visible = night > 0.0
			walker.lantern_pool.visible = false
		if is_instance_valid(walker.animator):
			walker.animator.speed_scale = 1.0
			walker.animator.advance(0.35)
		var h: float = walker.height_scale
		var camera := Camera3D.new()
		var tall: bool = "umbrella" in entry.get("gear", [])
		camera.fov = 30.0 if tall else 23.0
		view.add_child(camera)
		var centre := Vector3(0, 1.47*h+(0.22 if tall else 0.06), 0)
		camera.position = centre+Vector3(0, 0.05, 3.1)
		camera.look_at(centre)
		camera.current = true
		for i in 6: await process_frame
		await RenderingServer.frame_post_draw
		var image := view.get_texture().get_image()
		var path: String = out+str(entry.id)+".png"
		print("PORTRAIT ", entry.id, " ", image.save_png(path), " ", path)
		view.queue_free()
		await process_frame
	quit()
