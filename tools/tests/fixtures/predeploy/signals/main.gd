extends Node
signal done
signal other

func duplicate() -> void:
	done.connect(handler)
	done.connect(handler)

func guarded() -> void:
	if not done.is_connected(handler):
		done.connect(handler)
	if not done.is_connected(handler):
		done.connect(handler)

func different_callables() -> void:
	done.connect(handler)
	done.connect(other_handler)
	other.connect(handler)

func separate_function() -> void:
	done.connect(handler)

func unrelated_guard() -> void:
	if not other.is_connected(handler):
		other.connect(handler)
	done.connect(handler)
	done.connect(handler)

func handler() -> void:
	pass

func other_handler() -> void:
	pass
