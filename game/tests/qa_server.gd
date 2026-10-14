## The QA server a test talks to: --server=URL when given (tools/test.ps1 always passes the one it
## started, on TRIPOTHON_QA_PORT), else the runner's default port.
static func url() -> String:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): return arg.trim_prefix("--server=").trim_suffix("/")
	return preload("res://tests/qa_server.gd").url()
