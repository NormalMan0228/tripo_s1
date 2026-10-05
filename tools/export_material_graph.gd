extends SceneTree
## Compatibility runner using Material Maker's shipped graph/export API.
## Run with the installed MM Godot executable's standard --script option.
func _initialize() -> void:
	call_deferred("export_graph")

func export_graph() -> void:
	await process_frame
	var loader=root.get_node_or_null("mm_loader")
	if loader==null:
		print("MM_EXPORT_NO_LOADER");quit(1);return
	var source="C:/lsm26/triphthonS1/art/source/village_materials/village_timber.ptex"
	var graph=await loader.load_gen(source)
	if graph==null:
		print("MM_EXPORT_NO_GRAPH");quit(1);return
	root.add_child(graph)
	for node in graph.get_children():
		if node.has_method("export_material"):
			print("MM_EXPORT_NODE ",node.name)
			await node.export_material("C:/lsm26/triphthonS1/artifacts/detail-map-20261003/materials/village_timber","Godot/Godot 4 Standard",512)
	await process_frame
	quit()
