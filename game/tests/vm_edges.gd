extends SceneTree
func _initialize() -> void:
	var rows: Array=JSON.parse_string(FileAccess.get_file_as_string("res://../artifacts/vm-edges.json"));var failures: Array=[]
	for row in rows:
		var vm=load("res://scripts/asset_vm.gd").new();vm.setup(row.program,[])
		var result: Dictionary=vm.run(row.event,row.inputs)
		var same: bool=result.ok==row.ok and result.commands==row.commands
		for key in row.state:
			var expected: float=row.state[key]
			if absf(float(vm.state[key])-expected)>maxf(1e-12,absf(expected)*1e-12):same=false
		if not same:failures.append({"label":row.label,"expected_ok":row.ok,"actual_ok":result.ok,"expected":row.state,"actual":vm.state})
	var report := {"cases":rows.size(),"failures":failures}
	var file := FileAccess.open("res://../artifacts/vm-edges-results.json",FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "));file.close()
	print("VM_EDGES ",JSON.stringify({"cases":rows.size(),"failures":failures.size()}));quit(0 if failures.is_empty() else 1)
