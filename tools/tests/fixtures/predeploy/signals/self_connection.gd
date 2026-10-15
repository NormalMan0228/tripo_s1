extends Node
signal done

func duplicate_self_connection() -> void:
	self.connect("done", handler)
	done.connect(handler)

func handler() -> void:
	pass
