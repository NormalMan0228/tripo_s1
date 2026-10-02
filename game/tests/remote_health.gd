extends SceneTree

const Api = preload("res://scripts/api.gd")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var base_url := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--base-url="):
			base_url = argument.trim_prefix("--base-url=").trim_suffix("/")
	if not base_url.begins_with("https://"):
		push_error("Pass an HTTPS server with --base-url=https://host")
		quit(1)
		return
	var api := Api.new()
	root.add_child(api)
	api.base_url = base_url
	var result: Dictionary = await api.request("/health")
	var status: Dictionary = result.get("data", {})
	var valid: bool = bool(result.get("ok", false)) and bool(status.get("ok", false)) and status.get("mode") == "live" and int(status.get("protocol", 0)) == 6
	if valid:
		print("PASS: Godot HTTP client reached live HTTPS server (protocol 6)")
	else:
		push_error("Godot live HTTPS connection or protocol check failed: " + str(result.get("error", "unexpected_health_response")))
	quit(0 if valid else 1)
