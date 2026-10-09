extends Node3D
## A fixed pose parent plus a motion pivot per part, with bbox-normalized GLB.
const VM=preload("res://scripts/asset_vm.gd")
const Loader=preload("res://scripts/model_loader.gd")
var manifest: Dictionary={}
var pivots: Dictionary={}
var surfaces: Dictionary={}
var vm=VM.new()
var elapsed := 0.0
var nearby := false
var healthy := true
var runtime_version := 1
var colors: Dictionary={}
var pose_nodes: Dictionary={}
var normalizers: Dictionary={}
var mesh_bounds: Dictionary={}

static func fetch(api: Node, object_id: String, prefix: String="/v1/objects/") -> Node3D:
	var reply: Dictionary=await api.request(prefix+object_id+"/assembly")
	if not reply.ok: return null
	var value: Dictionary=reply.data
	var blobs := {}
	var total_bytes := 0
	for p in value.plan.parts:
		var response: Dictionary=await api.request(prefix+object_id+"/parts/"+p.id,{},HTTPClient.METHOD_GET,true)
		if not response.ok: return null
		total_bytes+=response.bytes.size()
		if total_bytes>48*1024*1024:return null
		var hashing := HashingContext.new()
		hashing.start(HashingContext.HASH_SHA256); hashing.update(response.bytes)
		if hashing.finish().hex_encode()!=p.sha256: return null
		blobs[p.id]=response.bytes
	var root=load("res://scripts/asset_assembly.gd").new()
	if not root.build(value,blobs): root.free(); return null
	return root

func build(value: Dictionary, blobs: Dictionary) -> bool:
	manifest=value.duplicate(true)
	if value.get("schema")!=1 or not value.get("plan",{}).get("parts") is Array: return false
	var parts: Array=value.plan.parts
	if parts.is_empty() or parts.size()>8: return false
	var holders := {}
	for p in parts:
		if not blobs.has(p.id) or pivots.has(p.id): return false
		var doc := GLTFDocument.new()
		var data := GLTFState.new()
		if doc.append_from_buffer(blobs[p.id],"",data)!=OK: return false
		var meshroot := doc.generate_scene(data) as Node3D
		if meshroot==null: return false
		# Tripo's default export is X-forward; this assembly contract is +Z-forward.
		if value.get("provenance",{}).get("geometry")=="tripo":
			meshroot.transform=Transform3D(Basis(Vector3.UP,-PI*.5),Vector3.ZERO)*meshroot.transform
		var meshes: Array[MeshInstance3D]=[]
		Loader._collect_meshes(meshroot,meshes)
		if meshes.is_empty(): meshroot.free(); return false
		Loader.shrink_textures(meshroot)
		var bounds := AABB()
		var first := true
		for m in meshes:
			var b: AABB=Loader._local_transform(m,meshroot)*m.get_aabb()
			bounds=b if first else bounds.merge(b); first=false
		if minf(bounds.size.x,minf(bounds.size.y,bounds.size.z))<0.0001: meshroot.free(); return false
		# Generated thin parts may arrive facing a different axis despite the prompt.
		# Align their short axis before fitting; otherwise a rotor is flattened edge-on.
		var desired_size := vector(p.size)
		var source_axis := bounds.size.min_axis_index()
		var desired_axis := desired_size.min_axis_index()
		if source_axis!=desired_axis and desired_size[desired_axis]<desired_size[desired_size.max_axis_index()]*.3 and bounds.size[source_axis]<bounds.size[bounds.size.max_axis_index()]*.6:
			var from := Vector3.ZERO;from[source_axis]=1
			var to := Vector3.ZERO;to[desired_axis]=1
			var correction := Basis(from.cross(to).normalized(),PI*.5)
			meshroot.transform=Transform3D(correction,Vector3.ZERO)*meshroot.transform
			first=true
			for m in meshes:
				var b: AABB=Loader._local_transform(m,meshroot)*m.get_aabb()
				bounds=b if first else bounds.merge(b);first=false
		var holder := Node3D.new()
		holder.name=p.id+"_pose"
		holder.position=vector(p.position); holder.rotation_degrees=vector(p.rotation)
		var pivot := Node3D.new()
		holder.add_child(pivot)
		var normalization := Node3D.new()
		pivot.add_child(normalization); normalization.add_child(meshroot)
		var size := vector(p.size)
		normalization.scale=fit_scale(size,bounds)
		normalization.position=-bounds.get_center()*normalization.scale-vector(p.pivot)*size
		pivots[p.id]=pivot; surfaces[p.id]=meshes; holders[p.id]=holder
		pose_nodes[p.id]=holder;normalizers[p.id]=normalization;mesh_bounds[p.id]=bounds
		for m in meshes:
			var original_colors: Array[Color]=[]
			for i in m.mesh.get_surface_count():
				var source=m.get_active_material(i)
				var mat: StandardMaterial3D=source.duplicate() if source is StandardMaterial3D else StandardMaterial3D.new()
				if mat.albedo_texture==null:mat.albedo_color=Color(p.color)
				original_colors.append(mat.albedo_color);mat.roughness=0.85
				m.set_surface_override_material(i,mat)
			m.set_meta("original_colors",original_colors)
	# Attach only after every id exists; server has already checked cycles.
	for p in parts:
		if p.parent=="": add_child(holders[p.id])
		elif pivots.has(p.parent): pivots[p.parent].add_child(holders[p.id])
		else: return false
	# Ground and size every assembly to a consistent furniture parcel, including
	# models whose designer puts the object origin at its center rather than feet.
	var all_meshes: Array[MeshInstance3D]=[]
	Loader._collect_meshes(self,all_meshes)
	var total := AABB()
	var initial_bounds := true
	for mesh in all_meshes:
		var b: AABB=Loader._local_transform(mesh,self)*mesh.get_aabb()
		total=b if initial_bounds else total.merge(b);initial_bounds=false
	# The player's chosen size sets the longest side (provenance.size_m); otherwise the designer's own
	# size, at most 1.8 m.
	var longest := maxf(total.size.x,maxf(total.size.y,total.size.z))
	var chosen := float(value.get("provenance",{}).get("size_m",0))
	var factor := clampf(chosen,0.2,3.0)/longest if chosen>0.0 else minf(1.0,1.8/longest)
	var content := Node3D.new()
	var roots := get_children()
	add_child(content)
	for node in roots:remove_child(node);content.add_child(node)
	content.scale=Vector3.ONE*factor
	content.position=-Vector3(total.get_center().x,total.position.y,total.get_center().z)*factor
	var runtime: Dictionary=value.get("runtime",{})
	runtime_version=int(runtime.get("version",1)); colors=runtime.get("colors",{})
	vm.setup(value.program,pivots.keys())
	paint(colors)
	apply_commands(vm.run("spawn").commands)
	for key in runtime.get("state",{}):
		if vm.state.has(key):vm.state[key]=runtime.state[key]
	apply_commands(vm.run("tick",{"dt":0,"time":0}).commands)
	set_meta("size",total.size*factor)
	set_meta("studio",true)
	return true

func preview_binding(id: String, edit: Dictionary) -> void:
	# Inspection-only pose edit. Server validation is required before persistence.
	if not pose_nodes.has(id):return
	var bounds: AABB=mesh_bounds[id]
	var size := vector(edit.size)
	pose_nodes[id].position=vector(edit.position)
	pose_nodes[id].rotation_degrees=vector(edit.rotation)
	normalizers[id].scale=fit_scale(size,bounds)
	normalizers[id].position=-bounds.get_center()*normalizers[id].scale-vector(edit.pivot)*size

## A part's scale into its design box. A one-piece craft keeps the generated model's proportions
## (stretching it into its design box made tall or long objects chunky); designed multi-part boxes
## still fit each part exactly. The studio's binding preview uses this too, so selecting a piece
## there no longer stretches it (and its painter no longer saw another shape than the world).
func fit_scale(size: Vector3, bounds: AABB) -> Vector3:
	if manifest.get("plan",{}).get("parts",[]).size()==1:
		return Vector3.ONE*(size[size.max_axis_index()]/bounds.size[bounds.size.max_axis_index()])
	return size/bounds.size

static func vector(a: Array) -> Vector3:
	return Vector3(a[0],a[1],a[2])

func _process(delta: float) -> void:
	if not healthy: return
	elapsed=fposmod(elapsed+delta,100000)
	var result: Dictionary=vm.run("tick",{"dt":delta,"time":elapsed,"near":int(nearby)})
	healthy=result.ok
	if healthy: apply_commands(result.commands)

func apply_commands(commands: Array) -> void:
	for c in commands:
		if not pivots.has(c.target): continue
		var pivot: Node3D=pivots[c.target]
		match c.op:
			"rotate_x": pivot.rotation_degrees.x=c.value
			"rotate_y": pivot.rotation_degrees.y=c.value
			"rotate_z": pivot.rotation_degrees.z=c.value
			"offset_y": pivot.position.y=c.value
			"emission","hue":
				for mesh in surfaces[c.target]:
					for i in mesh.mesh.get_surface_count():
						var mat: StandardMaterial3D=mesh.get_surface_override_material(i)
						if c.op=="hue": mat.albedo_color=Color.from_hsv(c.value,0.45,0.9)
						else:
							mat.emission_enabled=true; mat.emission=mat.albedo_color; mat.emission_energy_multiplier=c.value

func paint(values: Dictionary) -> void:
	colors=values.duplicate(true)
	for part in manifest.plan.parts:
		var id: String=part.id
		if not surfaces.has(id): continue
		for mesh in surfaces[id]:
			# A painted surface (painter/paint_apply.gd) shows its texture untinted.
			var painted: Array=mesh.get_meta("paint_textures",[])
			var base: Array=mesh.get_meta("paint_base",[])
			for i in mesh.mesh.get_surface_count():
				var mat: StandardMaterial3D=mesh.get_surface_override_material(i)
				if i<painted.size() and painted[i]!=null:
					mat.albedo_texture=painted[i];mat.albedo_color=Color.WHITE;continue
				if i<base.size():mat.albedo_texture=base[i]
				mat.albedo_color=Color(values[id]) if values.has(id) else mesh.get_meta("original_colors")[i]

func accept_event(data: Dictionary) -> void:
	for key in data.get("patch",data.state):
		if vm.state.has(key): vm.state[key]=data.get("patch",data.state)[key]
	runtime_version=data.version
	apply_commands(data.commands)
