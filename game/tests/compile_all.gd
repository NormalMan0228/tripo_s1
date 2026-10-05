extends SceneTree
## Loads every client script so parse errors surface in one headless run.
func _initialize() -> void:
	var failed := 0
	for name in DirAccess.get_files_at("res://scripts"):
		if not name.ends_with(".gd"): continue
		var script: GDScript = load("res://scripts/"+name)
		if script == null or not script.can_instantiate():
			failed += 1
			print("COMPILE_FAIL ", name)
	print("COMPILE_DONE failed=", failed)
	quit(1 if failed else 0)
