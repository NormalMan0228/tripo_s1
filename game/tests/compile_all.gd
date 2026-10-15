extends SceneTree
## Loads every client script so parse errors surface in one headless run.
func _initialize() -> void:
	var failed := 0
	# The interaction socket scripts (ISS-1) live in scripts/ix.
	for folder in ["res://scripts", "res://scripts/ix"]:
		for name in DirAccess.get_files_at(folder):
			if not name.ends_with(".gd"): continue
			var script: GDScript = load(folder+"/"+name)
			if script == null or not script.can_instantiate():
				failed += 1
				print("COMPILE_FAIL ", folder, "/", name)
	print("COMPILE_DONE failed=", failed)
	quit(1 if failed else 0)
