extends RefCounted
## Export features decide which tools a packaged client exposes. The server
## remains authoritative for credit, ownership and generation permissions.

static func developer() -> bool:
	return OS.has_feature("tripothon_dev") or (not OS.has_feature("tripothon_player") and OS.get_cmdline_user_args().has("--developer"))
