extends RefCounted
## Survival world entry point (main.gd build_world(true)). The three expedition maps are built by
## maps/survival/survival_map.gd from the server's authored layout (server/survival_maps.py, exported to
## maps/survival/layouts.json) and the run state's obstacles, hazards and resources.
const SurvivalMap = preload("res://maps/survival/survival_map.gd")

static func build(parent: Node3D, state: Dictionary) -> Node3D:
	var map := SurvivalMap.new()
	parent.add_child(map)
	map.build(state)
	return map

## Optional direct hook for main.gd's resource rendering: dress a resource root with the map's Tripo
## model (trees get a hidden "Stump" child). Without the hook the map adopts the roots by their "kind" meta.
static func dress_resource(world: Node, root: Node3D, kind: String) -> void:
	var map := world.get_node_or_null("SurvivalMap")
	if map: map.dress_resource(root, kind)
