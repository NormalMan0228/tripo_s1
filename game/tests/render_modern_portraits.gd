extends SceneTree
const Portrait=preload("res://scripts/avatar_portrait.gd")
const Roster=preload("res://scripts/character_roster.gd")
func _initialize() -> void:call_deferred("run")
func run() -> void:
	for id in Roster.IDS:
		var portrait := Portrait.new();root.add_child(portrait)
		var look: Dictionary=Roster.PRESETS[id].duplicate(true)
		look.character=id;look.backpack=false
		portrait.show_look(look)
		await portrait.rendered
		var path := ProjectSettings.globalize_path(Roster.portrait_path(id))
		if portrait.get_texture().get_image().save_png(path)!=OK:quit(1);return
		print("PORTRAIT ",id)
		portrait.queue_free();await process_frame;await process_frame
	print("MODERN_PORTRAITS_DONE");quit()
