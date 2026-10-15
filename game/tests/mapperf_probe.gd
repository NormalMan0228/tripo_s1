extends SceneTree
## Map-side render cost (window, logged-in village like terrain_probe; --server=URL, --hour=H):
## at fixed views (spot x zoom) the frame time, draw calls and primitives (visible and shadow passes),
## and what the props (map/Environment) and the buildings (map/Buildings) add, plus video memory.
## Prints MAPPERF_VIEW lines and MAPPERF {...}.
##   --buildings-2048 (also --shots=<dir>): the building colour maps capped at 2048 px at run time
##   (a preview of an import change, nothing is saved): captures of three buildings at zoom 6.5 and 10
##   before and after, and the texture memory both ways. Prints MAPPERF_BUILDINGS {...}.
const Town = preload("res://scripts/town.gd")
const Profile = preload("res://scripts/controller_profile.gd")
const VIEWS := [["square", Vector2(-33,37), 6.5], ["square", Vector2(-33,37), 10.0], ["town hall", Vector2(-33,30), 10.0],
	["camp", Vector2(52,36), 10.0], ["meadow", Vector2(-18,-31), 10.0], ["lighthouse", Vector2(5,74), 10.0], ["square wide", Vector2(-33,37), 22.0]]
## Three buildings for the texture sheet: where the walker stands (in front, camera side) and the id.
const SHOT_BUILDINGS := [["09_town_hall", Vector2(-33,30.5), Vector2(-33,33.5)], ["01_cafe", Vector2(-62,-31), Vector2(-62,-28)], ["16_blue_cottage", Vector2(70,58.5), Vector2(70,61.5)]]
var app: Node

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	if not await enter_village():
		quit(1)
		return
	# The game applies its own frame cap and vsync from settings on the way in: off again (real frame times).
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var report := {"vram": vram(), "meshes": app.find_children("*", "MeshInstance3D", true, false).size()}
	var map: Node3D = app.town.map
	var env: Node3D = map.get_node_or_null("Environment")
	var buildings: Node3D = map.get_node_or_null("Buildings")
	report["props"] = env.get("prop_nodes").size() if env and env.get("prop_nodes") != null else 0
	report["lod_entries"] = env.get("lod_entries").size() if env and env.get("lod_entries") != null else 0
	if "--buildings-2048" in OS.get_cmdline_user_args():
		report["buildings"] = await building_sheet(buildings)
		print("MAPPERF_BUILDINGS ", JSON.stringify(report.buildings))
		quit(0)
		return
	var views := []
	for view in VIEWS:
		place(view[1], view[2])
		var all := await info()
		var timing := await sample(1.5)
		env.visible = false
		var no_env := await info()
		env.visible = true
		buildings.visible = false
		var no_buildings := await info()
		buildings.visible = true
		var row := {"view": "%s z%.1f" % [view[0], view[2]], "ms": timing.ms, "process_ms": timing.process, "draws": all.draws, "prims": all.prims, "objects": all.objects,
			"shadow_draws": all.shadow_draws, "shadow_prims": all.shadow_prims,
			"props_draws": all.draws-no_env.draws, "props_shadow_draws": all.shadow_draws-no_env.shadow_draws, "props_prims": all.prims-no_env.prims,
			"buildings_draws": all.draws-no_buildings.draws, "buildings_prims": all.prims-no_buildings.prims}
		views.append(row)
		print("MAPPERF_VIEW ", JSON.stringify(row))
	report["views"] = views
	# What each of the map's parts and the village modules add at the square (zoom 10), shadow pass apart.
	place(Vector2(-33,37), 10.0)
	var base := await info()
	var parts := {}
	var groups: Array = []
	for child in map.get_children():
		if child is Node3D and child.visible: groups.append(["map/"+String(child.name), child])
	for m in app.modules:
		if is_instance_valid(m) and m is Node3D and m.visible: groups.append(["module/"+str(m.get_script().resource_path).get_file().get_basename(), m])
	for g in groups:
		g[1].visible = false
		var without := await info()
		g[1].visible = true
		var d := {"draws": base.draws-without.draws, "shadow_draws": base.shadow_draws-without.shadow_draws, "prims": base.prims-without.prims, "shadow_prims": base.shadow_prims-without.shadow_prims}
		if d.draws != 0 or d.shadow_draws != 0:
			parts[g[0]] = d
			print("MAPPERF_PART %-34s %s" % [g[0], JSON.stringify(d)])
	report["parts_square_z10"] = {"base": base, "parts": parts}
	report["vram_end"] = vram()
	print("MAPPERF ", JSON.stringify(report))
	quit(0)

## Logs a fresh QA account in and waits for the village (terrain_probe.gd).
func enter_village() -> bool:
	var api = load("res://scripts/api.gd").new()
	root.add_child(api)
	api.base_url = preload("res://tests/qa_server.gd").url()
	var login: Dictionary = await api.post("/v1/auth/register", {"username":"mapperf_"+str(Time.get_ticks_usec()), "password":"Mapperf-probe-password-1"})
	if not login.ok:
		print("LOGIN_FAILED")
		return false
	Engine.set_meta("studio_session", {"token":login.data.token, "url":api.base_url, "room":"home"})
	change_scene_to_file("res://scenes/main.tscn")
	var deadline := Time.get_ticks_msec()+90000
	while Time.get_ticks_msec() < deadline and not (is_instance_valid(current_scene) and current_scene.get("screen") == "village" and is_instance_valid(current_scene.get("player"))):
		await process_frame
	app = current_scene
	if not is_instance_valid(app) or app.get("screen") != "village":
		print("VILLAGE_NOT_READY")
		return false
	await create_timer(5.0).timeout
	return true

## The village camera over the walker at a spot and zoom (terrain_probe.gd place()).
func place(at: Vector2, zoom: float) -> void:
	app.player.position = Town.point(at, 0.1)
	var focus: Vector3 = Town.point(at, 0.1)+Profile.CAMERA_FOCUS_OFFSET
	app.camera_focus = focus
	app.camera_focus_ready = true
	app.camera_zoom_active = false
	app.camera.size = zoom
	app.camera.position = focus+Profile.CAMERA_OFFSET*Profile.CAMERA_PULLBACK
	app.camera.look_at(focus)

func info() -> Dictionary:
	for i in 6: await process_frame
	var vp := root.get_viewport_rid()
	var r := RenderingServer
	return {"prims": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, r.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME),
		"draws": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, r.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME),
		"objects": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, r.VIEWPORT_RENDER_INFO_OBJECTS_IN_FRAME),
		"shadow_prims": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_SHADOW, r.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME),
		"shadow_draws": r.viewport_get_render_info(vp, r.VIEWPORT_RENDER_INFO_TYPE_SHADOW, r.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)}

## Mean frame time and _process time over `seconds` (vsync off).
func sample(seconds: float) -> Dictionary:
	for i in 10: await process_frame
	var frames := 0
	var process := 0.0
	var started := Time.get_ticks_usec()
	while Time.get_ticks_usec()-started < seconds*1000000.0:
		await process_frame
		frames += 1
		process += Performance.get_monitor(Performance.TIME_PROCESS)*1000.0
	return {"ms": snappedf((Time.get_ticks_usec()-started)/1000.0/frames, 0.01), "process": snappedf(process/frames, 0.01)}

func vram() -> Dictionary:
	var r := RenderingServer
	return {"total": snappedf(r.get_rendering_info(r.RENDERING_INFO_VIDEO_MEM_USED)/1048576.0, 0.1),
		"buffers": snappedf(r.get_rendering_info(r.RENDERING_INFO_BUFFER_MEM_USED)/1048576.0, 0.1),
		"textures": snappedf(r.get_rendering_info(r.RENDERING_INFO_TEXTURE_MEM_USED)/1048576.0, 0.1)}

func shots_dir() -> String:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--shots="): return argument.trim_prefix("--shots=")
	return ProjectSettings.globalize_path("res://../artifacts/mapperf")

func capture(tag: String) -> void:
	for spot in SHOT_BUILDINGS:
		for zoom in [6.5, 10.0]:
			place(spot[1] if zoom < 8.0 else spot[2], zoom)
			for i in 12: await process_frame
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(shots_dir().path_join("bld_%s_z%s_%s.png" % [spot[0], str(zoom).replace(".", "_"), tag]))

## Every texture a building material uses (standard and shader materials), by object.
func building_materials(buildings: Node3D) -> Array:
	var out := []
	for node in buildings.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		if mesh.mesh == null: continue
		if mesh.material_override: out.append(mesh.material_override)
		for s in mesh.mesh.get_surface_count():
			for m in [mesh.mesh.surface_get_material(s), mesh.get_surface_override_material(s)]:
				if m: out.append(m)
	return out

func building_sheet(buildings: Node3D) -> Dictionary:
	Engine.time_scale = 0.0001
	# Only the world in the pictures: no HUD, chat, door hints or name tags.
	for layer in root.find_children("*", "CanvasLayer", true, false): layer.visible = false
	for label in root.find_children("*", "Label3D", true, false): label.visible = false
	if app.get("hint") is CanvasItem: app.hint.visible = false
	var result := {"vram_before": vram()}
	await capture("4096")
	# Colour maps above 2048 px, each replaced (everywhere it is used) by a 2048 px copy, block-compressed
	# as the importer would (BPTC where the GPU has it, else S3TC).
	var materials := building_materials(buildings)
	var replaced := {}
	var sizes := []
	for m in materials:
		for entry in texture_slots(m):
			var texture: Texture2D = entry.texture
			if texture == null or texture.get_width() <= 2048: continue
			if not replaced.has(texture):
				var image := texture.get_image()
				if image.is_compressed(): image.decompress()
				image.clear_mipmaps()
				image.resize(2048, 2048, Image.INTERPOLATE_LANCZOS)
				image.generate_mipmaps()
				image.compress(Image.COMPRESS_BPTC if RenderingServer.has_os_feature("bptc") else Image.COMPRESS_S3TC, Image.COMPRESS_SOURCE_SRGB)
				replaced[texture] = ImageTexture.create_from_image(image)
				sizes.append([texture.get_width(), texture.get_height()])
			set_slot(m, entry, replaced[texture])
	result["capped_textures"] = replaced.size()
	result["sizes"] = sizes
	for i in 30: await process_frame
	result["vram_after"] = vram()
	await capture("2048")
	return result

func texture_slots(m: Material) -> Array:
	var out := []
	if m is BaseMaterial3D:
		for p in BaseMaterial3D.TEXTURE_MAX:
			out.append({"param": p, "texture": (m as BaseMaterial3D).get_texture(p)})
	elif m is ShaderMaterial and (m as ShaderMaterial).shader:
		for u in (m as ShaderMaterial).shader.get_shader_uniform_list():
			var v = (m as ShaderMaterial).get_shader_parameter(u.name)
			if v is Texture2D: out.append({"uniform": u.name, "texture": v})
	return out

func set_slot(m: Material, entry: Dictionary, texture: Texture2D) -> void:
	if entry.has("param"): (m as BaseMaterial3D).set_texture(entry.param, texture)
	else: (m as ShaderMaterial).set_shader_parameter(entry.uniform, texture)
