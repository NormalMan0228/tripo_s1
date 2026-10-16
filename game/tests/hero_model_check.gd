extends SceneTree
## Loads the new player models (assets/<id>.glb) and checks what player.gd needs from them:
## the bones it attaches to (R_Hand, Head, Spine02, R_Upperarm, R_Forearm), the clips it plays
## (idle, walk, run, slash) and the recolourable materials (<part>__<hex>).
func _init() -> void:
	var failures: Array[String] = []
	for id in ["m1", "f1", "m2", "f2", "m3", "f3", "m4", "f4"]:
		var path := "res://assets/%s.glb" % id
		if not ResourceLoader.exists(path): continue
		var scene := (load(path) as PackedScene).instantiate()
		var skels := scene.find_children("*", "Skeleton3D", true, false)
		var players := scene.find_children("*", "AnimationPlayer", true, false)
		var meshes := scene.find_children("*", "MeshInstance3D", true, false)
		if skels.is_empty(): failures.append(id + ": no skeleton"); continue
		var sk: Skeleton3D = skels[0]
		for b in ["R_Hand", "Head", "Spine02", "R_Upperarm", "R_Forearm"]:
			if sk.find_bone(b) < 0: failures.append(id + ": no bone " + b)
		var anims: PackedStringArray = players[0].get_animation_list() if not players.is_empty() else PackedStringArray()
		for c in ["idle", "walk", "run", "slash"]:
			if not anims.has(c): failures.append(id + ": no clip " + c)
		var parts := []
		for m in meshes:
			for s in m.mesh.get_surface_count():
				parts.append(str(m.mesh.surface_get_material(s).resource_name))
		print("HERO ", id, " bones=", sk.get_bone_count(), " clips=", anims, " materials=", parts)
		scene.free()
	print("HERO_RESULT ", JSON.stringify({"failures": failures}))
	quit(1 if failures.size() > 0 else 0)
