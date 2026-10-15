extends SceneTree
## Farm growth stages, watering and the added crops on the client (farm.gd, life_art.gd,
## life_icon.gd), without a server. Plots are shaped like the server's (docs/design/FARM_API.md:
## stage, stage_index, progress, watered, watered_at, growth_rate, ready). Checks the stage and
## thirst reading, wet soil, the stage-up pop and its signal, the watering splash, a model per
## crop and stage, and that the seed list matches server/homestead.py. With --capture (windowed)
## it lays every crop out by stage (seed, sprout, leafy, budding, ripe; with thirsty, just
## watered and just ripened beds) under the item icons: artifacts/farm_stages.png.
const Farm := preload("res://scripts/farm.gd")
const Art := preload("res://scripts/life_art.gd")
const Icon := preload("res://scripts/life_icon.gd")
const Fx := preload("res://scripts/fx.gd")
const Life := preload("res://scripts/village_life.gd")
const RpgUi := preload("res://scripts/rpg_ui.gd")
## The server catalog's crop rules (homestead.py CROPS: seconds and stage_seconds seed/sprout/growing).
const CROPS := {
	"turnip":[90,20,30,40],"carrot":[120,25,40,55],"pumpkin":[150,30,50,70],"strawberry":[200,40,60,100],
	"sunflower":[260,50,90,120],"radish":[100,20,35,45],"potato":[140,30,45,65],"tomato":[180,35,65,80],"corn":[240,50,80,110],
}
const NAMES := {"turnip":"순무","carrot":"당근","pumpkin":"호박","strawberry":"딸기","sunflower":"해바라기",
	"radish":"무","potato":"감자","tomato":"토마토","corn":"옥수수"}
const GROUND_Y := 2.24

var failures: Array[String] = []
var world: Node3D
var farm: Node3D

func _initialize() -> void: call_deferred("run_test")

func check(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ")+what)
	if not ok: failures.append(what)

func catalog() -> Dictionary:
	var out := {}
	for crop in CROPS:
		var r: Array = CROPS[crop]
		out[crop] = {"name":NAMES[crop], "seconds":r[0], "stage_seconds":{"seed":r[1], "sprout":r[2], "growing":r[3]}}
	return out

## A planted plot as the server sends it, `look` 1..5 (seed, sprout, leafy, budding, ripe).
func plot(crop: String, look: int, watered: bool, now: float, x := 0.0, z := 0.0, watered_ago := 300.0) -> Dictionary:
	var r: Array = CROPS[crop]
	var total := float(r[0])
	var growth: float = [0.0, r[1]*0.5, r[1]+r[2]*0.5, r[1]+r[2]+r[3]*0.2, r[1]+r[2]+r[3]*0.8, total][look]
	var index: int = [0, 0, 1, 2, 2, 3][look]
	var p := {"x":x, "z":z, "crop":crop, "planted_at":now-600, "stage":["seed","sprout","growing","ripe"][index], "stage_index":index,
		"progress":growth/total, "growth_seconds":growth, "watered":watered, "growth_rate":1.0 if watered else 0.5,
		"ready":look == 5, "remaining":0.0 if look == 5 else (total-growth)/(1.0 if watered else 0.5)}
	p["ready_at"] = now+float(p.remaining)
	p["watered_until"] = null
	if watered: p["watered_until"] = now+3600
	if watered: p["watered_at"] = now-watered_ago
	return p

func run_test() -> void:
	var capture := "--capture" in OS.get_cmdline_user_args()
	world = Node3D.new()
	world.name = "World"
	root.add_child(world)
	Farm.crops = catalog()
	var now := 1_800_000_000.0
	# --- stage and thirst come from the server's fields
	check(Farm.stage({"x":0, "z":0}) == 0, "an empty bed shows nothing")
	var looks: Array = []
	for look in range(1, 6): looks.append(Farm.stage(plot("carrot", look, true, now)))
	check(looks == [1, 2, 3, 4, 5], "seed, sprout, growing (two halves) and ripe map to looks 1-5 (%s)" % [looks])
	check(Farm.thirsty(plot("tomato", 3, false, now)) and not Farm.thirsty(plot("tomato", 3, true, now)) and not Farm.thirsty(plot("tomato", 5, false, now)),
		"thirsty = planted, not ripe, not watered (half-speed growth)")
	check(is_equal_approx(Farm.wetness(plot("corn", 2, true, now, 0, 0, 0.0), now), 1.0) and is_equal_approx(Farm.wetness(plot("corn", 2, true, now), now), Farm.WET_FLOOR)
		and Farm.wetness(plot("corn", 2, false, now), now) == 0.0, "soil is soaked right after watering, damp while watered, dry without water")
	# --- the seed list and the art cover every server crop
	var server := FileAccess.get_file_as_string(ProjectSettings.globalize_path("res://../server/homestead.py"))
	var ids: Array = []
	var re := RegEx.new()
	re.compile("'(\\w+)': \\{'name':'[^']+','seconds'")
	for m in re.search_all(server): ids.append(m.get_string(1))
	check(not ids.is_empty() and Life.CROP_ORDER == ids, "seed picker order matches homestead.CROPS (%s)" % [ids])
	for crop in CROPS:
		var counts: Array = []
		for look in range(1, 6):
			var model: Node3D = Art.crop(crop, look, 7)
			var n := model.find_children("*", "MeshInstance3D", true, false).size()
			counts.append(n)
			model.free()
		check(counts[2] != counts[3] or counts[3] != counts[4], "%s: %s meshes per stage" % [crop, counts])
	# --- village_life's bed prompt and action follow the same reading
	var life: Node = Life.new()
	life.state = {"server_time":now-Time.get_ticks_msec()*0.001, "catalog":{"crops":catalog()},
		"plots":[{"x":0, "z":0}, plot("corn", 3, false, now), plot("corn", 3, true, now), plot("corn", 5, false, now)]}
	var prompts: Array = []
	for i in 4: prompts.append([int(life.plot_entry(i).stage), str(life.plot_entry(i).prompt)])
	check(prompts[0][0] == 0 and prompts[1][1].contains("물 주기") and prompts[2][1].contains("자라는 중") and prompts[3][0] == 5 and prompts[3][1].contains("수확"),
		"bed prompts: plant, water when dry (any stage), growing timer, harvest (%s)" % [prompts])
	life.free()
	# --- the farm node: wet soil, stage-up pop with its signal, watering splash
	farm = Farm.new()
	world.add_child(farm)
	farm.viewer = Vector3.ZERO
	var grown: Array = []
	farm.grew.connect(func(i, s): grown.append([i, s]))
	farm.sync([plot("potato", 4, true, now)], now)
	await process_frame
	var before := Fx.played
	farm.sync([plot("potato", 5, true, now)], now)
	check(grown == [[0, 5]] and Fx.played > before, "a crop turning ripe near the walker pops and signals (%s)" % [grown])
	check(farm.beds[0].root.get_node_or_null("Halo") != null and farm.beds[0].root.get_node_or_null("Sparkle") != null, "a ripe crop glows and twinkles")
	before = Fx.played
	farm.watered(0)
	check(Fx.played > before, "watering splashes")
	farm.sync([plot("potato", 2, false, now)], now)
	farm.beds[0].thirst = 0.0
	before = Fx.played
	for f in 3: await process_frame
	check(Fx.played > before, "a thirsty bed asks for water with a drop bubble")
	farm.sync([plot("potato", 2, true, now, 0, 0, 0.0)], now)
	await create_timer(0.9).timeout
	var soil_mat: StandardMaterial3D = farm.beds[0].soil.get_meta("wet_mats")[1]
	check(soil_mat.albedo_color.v < Art.SOIL_DRY.v-0.1, "freshly watered soil darkens (%.2f vs %.2f)" % [soil_mat.albedo_color.v, Art.SOIL_DRY.v])
	farm.free()
	if capture: await shoot(now)
	print("FARM_STAGES_CHECK %s failures=%d" % ["PASS" if failures.is_empty() else "FAIL", failures.size()])
	quit(0 if failures.is_empty() else 1)

# ------------------------------------------------------------------ capture
func label(text: String, at: Vector3, size := 34) -> void:
	var l := Label3D.new()
	l.text = text
	l.font = RpgUi.FONT_BOLD
	l.font_size = size
	l.pixel_size = 0.0075
	l.outline_size = 10
	l.modulate = Color("fff3c4")
	l.outline_modulate = Color(0.15, 0.1, 0.05)
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.position = at
	world.add_child(l)

func stage_scene() -> Camera3D:
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = 0.95
	sun.shadow_enabled = true
	world.add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color("9cc3d8")
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color = Color("d6e2c8")
	env.environment.ambient_light_energy = 0.5
	world.add_child(env)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(40, 30)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color("5f8a45")
	gm.roughness = 1.0
	gm.metallic_specular = 0.0
	ground.material_override = gm
	ground.position = Vector3(0, GROUND_Y-0.02, -2)
	world.add_child(ground)
	var cam := Camera3D.new()
	cam.fov = 18
	world.add_child(cam)
	cam.look_at_from_position(Vector3(0, GROUND_Y+26.0, 27.0), Vector3(0, GROUND_Y+0.2, -3.2))
	cam.current = true
	return cam

func shoot(now: float) -> void:
	for f in 30: await process_frame
	stage_scene()
	farm = Farm.new()
	world.add_child(farm)
	farm.viewer = Vector3(0, GROUND_Y, -3.6)
	var crops: Array = Life.CROP_ORDER
	var looks := 5
	var gap := 1.8
	var plots: Array = []
	var where: Array = []
	# Columns are crops; rows run from seeds (front) to ripe (back). Row states: seeds thirsty,
	# sprouts just watered (soaked), leafy watered, budding thirsty (droop + bubble), ripe.
	for look in range(1, looks+1):
		for c in crops.size():
			var x := (c-(crops.size()-1)*0.5)*gap
			var z := -(look-1)*gap
			var wet: bool = look in [2, 3, 5]
			plots.append(plot(crops[c], 4 if look == 5 else look, wet, now, x, z, 0.0 if look == 2 else 300.0))
			where.append(Vector3(x, GROUND_Y, z))
	farm.sync(plots, now)
	for i in farm.beds.size(): farm.beds[i].root.position = where[i]
	for c in crops.size(): label(NAMES[crops[c]], Vector3((c-(crops.size()-1)*0.5)*gap, GROUND_Y+0.1, 1.35), 30)
	var rows := ["씨앗", "새싹", "성장", "개화", "수확"]
	for r in rows.size(): label(rows[r], Vector3(-(crops.size()*0.5)*gap-0.6, GROUND_Y+0.3, -r*gap), 28)
	# Item and seed icons across the top, as the seed picker and storage show them.
	var layer := CanvasLayer.new()
	root.add_child(layer)
	var strip := HBoxContainer.new()
	strip.position = Vector2(24, 14)
	strip.add_theme_constant_override("separation", 6)
	layer.add_child(strip)
	for crop in crops:
		var card := PanelContainer.new()
		card.add_theme_stylebox_override("panel", RpgUi.frame("slot_paper"))
		strip.add_child(card)
		var pair := HBoxContainer.new()
		pair.add_theme_constant_override("separation", 0)
		card.add_child(pair)
		pair.add_child(Icon.make(crop, 56))
		pair.add_child(Icon.make(crop+"_seed", 56))
	for f in 150: await process_frame
	# Ripe row turns ripe now (the pop), the sprout row gets its water (the splash), thirsty beds ask.
	var ripe_plots: Array = plots.duplicate(true)
	for i in ripe_plots.size():
		if i >= crops.size()*(looks-1): ripe_plots[i] = plot(crops[i%crops.size()], 5, true, now, where[i].x, where[i].z)
	farm.sync(ripe_plots, now)
	for i in crops.size(): farm.watered(crops.size()+i)
	for i in farm.beds.size():
		if farm.beds[i].get("thirsty", false): farm.beds[i].thirst = 0.05+0.01*(i%crops.size())
	await create_timer(0.4).timeout
	await RenderingServer.frame_post_draw
	var shot := root.get_texture().get_image()
	var path := ProjectSettings.globalize_path("res://../artifacts/farm_stages.png")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	print("SHEET ", shot.save_png(path), " ", path)
