extends SceneTree
const BuildMode=preload("res://scripts/build_mode.gd")

func _initialize() -> void: call_deferred("run_review")

func run_review() -> void:
	var scene: PackedScene=load("res://scenes/studio.tscn")
	var room := scene.instantiate()
	root.add_child(room)
	await create_timer(1.2).timeout
	var mode := "developer" if BuildMode.developer() else "player"
	var tabs: TabContainer=room.find_children("*","TabContainer",true,false)[0]
	print("STUDIO_MODE ",mode," visible_tabs=",tabs.get_tab_count()-int(tabs.is_tab_hidden(2))-int(tabs.is_tab_hidden(3))-int(tabs.is_tab_hidden(4)))
	await RenderingServer.frame_post_draw
	var folder := ProjectSettings.globalize_path("res://../artifacts")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--artifacts="): folder=argument.trim_prefix("--artifacts=")
	DirAccess.make_dir_recursive_absolute(folder)
	root.get_texture().get_image().save_png(folder.path_join("studio-"+mode+"-review.png"))
	room.queue_free()
	await process_frame
	quit()
