extends RefCounted
## Export features decide which tools a packaged client exposes. The server
## remains authoritative for credit, ownership and generation permissions.

## Set at login from the server's account role; operator accounts get the
## developer tools in any build. The server still checks every admin request.
static var admin := false

static func developer() -> bool:
	return admin or OS.has_feature("tripothon_dev") or (not OS.has_feature("tripothon_player") and OS.get_cmdline_user_args().has("--developer"))
