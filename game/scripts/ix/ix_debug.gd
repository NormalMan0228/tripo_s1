extends Node3D
## ISS-1 socket gizmo (development only; off by default, nothing exists while it is off). Draws the
## sockets of the things near the walker: a cross at the contact point, its +Z (where the user's
## chest faces) and sideways axis, the approach feet points with arrows to the seat, an id/type/
## height label, and the driver's state above the walker with its contact error.
## Colours: sit gold, lie blue, use green, grip orange, look white, approach cyan, claimed grey,
## invalid red, bounding-box fallback amber.
const IxSources = preload("res://scripts/ix/ix_sources.gd")
const IxRig = preload("res://scripts/ix/ix_rig.gd")
const Driver = preload("res://scripts/ix/ix_driver.gd")

const COLORS := {"sit": Color("f2c14e"), "perch": Color("e8a33c"), "sit_ground": Color("d9b45a"), "lie": Color("5aa0f2"),
	"stand_use": Color("63c46b"), "reach": Color("63c46b"), "grip": Color("f28c3a"), "look_at": Color("ffffff"), "passage": Color("b48cf2"),
	"place": Color("63c46b"), "talk": Color("ffffff")}
const APPROACH := Color("3fd6e0")
const CLAIMED := Color("8a8a8a")
const INVALID := Color("e2483d")
const BBOX := Color("ffb000")
const REFRESH := 0.2
const REACH := 9.0

## Objects whose sockets are drawn: a Callable returning nodes (crafted pieces, props) and one
## returning room records; the walker (its driver is labelled).
var nodes := Callable()
var records := Callable()
var player: Node3D
var _wait := 0.0
var _im: ImmediateMesh
var _labels: Array[Label3D] = []
var _used := 0

func _ready() -> void:
	name = "IxDebug"
	_im = ImmediateMesh.new()
	var mesh := MeshInstance3D.new()
	mesh.mesh = _im
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.vertex_color_use_as_albedo = true
	material.no_depth_test = true
	material.render_priority = 10
	mesh.material_override = material
	add_child(mesh)

func _process(delta: float) -> void:
	_wait -= delta
	if _wait > 0.0: return
	_wait = REFRESH
	rebuild()

func rebuild() -> void:
	_im.clear_surfaces()
	_used = 0
	var here: Vector3 = player.global_position if is_instance_valid(player) else Vector3.ZERO
	var entries: Array = []
	if nodes.is_valid():
		for n in nodes.call():
			if is_instance_valid(n) and (n as Node3D).global_position.distance_to(here) < REACH:
				for e in IxSources.for_node(n, str(n.get("rest")) if "rest" in n else ""): entries.append(e)
	if records.is_valid():
		for r in records.call():
			if is_instance_valid(r.get("node")) and (r.node as Node3D).global_position.distance_to(here) < REACH:
				entries.append_array(IxSources.for_room(r))
	_im.surface_begin(Mesh.PRIMITIVE_LINES)
	var drew := false
	for e in entries:
		var s := IxSources.resolve(e)
		if not s.has("origin"): continue
		drew = true
		var color: Color = COLORS.get(str(s.type), Color.WHITE)
		if str(s.source) == "bbox": color = BBOX
		if Driver.claims.has(Driver.key_of(e.node, s)): color = CLAIMED
		if not bool(s.valid): color = INVALID
		var o: Vector3 = s.origin
		var b: Basis = s.basis
		_cross(o, 0.06, color)
		_line(o, o + b.z * 0.35, color)
		_line(o + b.z * 0.35, o + b.z * 0.28 + b.x * 0.05, color)
		_line(o + b.z * 0.35, o + b.z * 0.28 - b.x * 0.05, color)
		_line(o, o + b.x * 0.15, color.darkened(0.4))
		_line(o, o + Vector3.UP * 0.12, color.darkened(0.2))
		for a in s.get("approach", []):
			var p: Vector3 = a.pos + Vector3(0, 0.03, 0)
			_cross(p, 0.08, APPROACH)
			_line(p, Vector3(o.x, p.y, o.z), APPROACH.darkened(0.3))
			var f := Vector3(sin(float(a.yaw)), 0, cos(float(a.yaw)))
			_line(p, p + f * 0.22, APPROACH)
		var text := "%s %s %dcm" % [s.id, s.type, int(round(float(s.height) * 100.0))]
		if not bool(s.valid): text += " (%s)" % s.why
		elif str(s.source) != "authored": text += " · " + str(s.source)
		_label(o + Vector3(0, 0.22, 0), text, color)
	if is_instance_valid(player) and "ix" in player and is_instance_valid(player.ix):
		var d: Node = player.ix
		var info := "ix %s" % d.state_name()
		if d.busy():
			info += " %.2fs" % float(d.phase_t)
			if d.seated() and not d.entry.is_empty() and "hand_skeleton" in player and is_instance_valid(player.hand_skeleton):
				var point := IxSources.point_now(d.entry)
				if d.kind == "lie": point += Vector3(0, IxRig.LIE_LIFT, 0)
				var contact: Vector3 = d.measured_contact()
				info += " · 접점 %.1fcm" % (contact.distance_to(point) * 100.0)
				_line(contact, point, INVALID)
				drew = true
		_label(player.global_position + Vector3(0, 2.25, 0), info, Color("e8f3ff"))
	if not drew:
		# An empty surface is not allowed: one invisible point keeps the mesh valid.
		_im.surface_set_color(Color(0, 0, 0, 0))
		_im.surface_add_vertex(here)
		_im.surface_add_vertex(here)
	_im.surface_end()
	for i in range(_used, _labels.size()): _labels[i].visible = false

func _line(a: Vector3, b: Vector3, color: Color) -> void:
	_im.surface_set_color(color)
	_im.surface_add_vertex(a)
	_im.surface_set_color(color)
	_im.surface_add_vertex(b)

func _cross(at: Vector3, size: float, color: Color) -> void:
	_line(at - Vector3(size, 0, 0), at + Vector3(size, 0, 0), color)
	_line(at - Vector3(0, 0, size), at + Vector3(0, 0, size), color)

func _label(at: Vector3, text: String, color: Color) -> void:
	if _used >= 40: return
	if _used >= _labels.size():
		var l := Label3D.new()
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		l.fixed_size = true
		l.pixel_size = 0.0011
		l.font_size = 22
		l.outline_size = 6
		l.render_priority = 11
		add_child(l)
		_labels.append(l)
	var label := _labels[_used]
	_used += 1
	label.visible = true
	label.text = text
	label.modulate = color
	label.global_position = at
