extends SceneTree
var failures := 0
func _initialize() -> void:
	var cases=JSON.parse_string(FileAccess.get_file_as_string("res://../artifacts/vm-parity.json"))
	for test in cases:
		var vm=load("res://scripts/asset_vm.gd").new();vm.setup(test.program,test.targets)
		for frame in test.trace:
			var result: Dictionary=vm.run(frame.event,frame.inputs)
			if not result.ok or result.commands.size()!=frame.commands.size():failures+=1;break
			for i in result.commands.size():
				var a: Dictionary=result.commands[i];var b: Dictionary=frame.commands[i]
				if a.op!=b.op or a.target!=b.target or absf(a.value-b.value)>0.00001:failures+=1;break
			for key in frame.state:
				if absf(vm.state[key]-frame.state[key])>0.00001:failures+=1;break
	print("VM_PARITY programs=",cases.size()," failures=",failures)
	quit(0 if failures==0 else 1)
