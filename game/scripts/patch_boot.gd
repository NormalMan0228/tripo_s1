extends Node
## Loads the downloaded game patch before anything else of the game is loaded (exported games only).
##
## This is the FIRST autoload (project.godot). Godot loads and creates the autoloads one at a time, in
## order, and this script's _static_init runs as soon as it is loaded: no other game script, scene or
## asset is cached yet. Loading the patch pack here (replace_files) makes every later autoload, the
## main scene and everything they load come from the patch; the engine also refreshes its class and
## UID lists for the new pack.
##
## Keep it tiny and without preloads: this file itself always runs from the installed Villagen.pck,
## so a release that changes it must be installed in full (tools/publish_school_build.py marks such a
## release requires_reinstall). The download, checks and screens live in patcher.gd and
## version_gate.gd, which a patch can change.
##
## user://patches/state.json (written by patcher.gd once a download is verified):
##   {"base": "0.11.4", "version": "0.11.6", "file": "0.11.4_to_0.11.6.pck", "size": N, "sha256": "...",
##    "boots": 0}
## A patch for another installed version (the player reinstalled) is removed. A patch that does not
## reach the title three launches in a row is set aside (boots counts launches; the title resets it),
## so a broken patch can never lock the game: it then starts as installed and asks for the installer.

const DIR := "user://patches"
const STATE := "state.json"
const MAX_BOOTS := 3

## The installed game's version (Villagen.pck), before any patch.
static var base_version := ""
## The version that runs now: the patch's, or base_version.
static var version := ""
## The loaded patch's state ({} when none), and the folder it came from.
static var patch := {}
static var patch_dir := ""
## Why no patch was loaded ("" = none was waiting, or it loaded): other_base, missing, size,
## unreadable, crashed.
static var problem := ""

static func _static_init() -> void:
	base_version = str(ProjectSettings.get_setting("application/config/version", "0"))
	version = base_version
	if enabled(): boot(DIR)

## Exported games only: source runs never load downloaded packs (tests call boot() themselves).
## "--no-patch" on the command line starts the game as installed.
static func enabled() -> bool:
	return OS.has_feature("template") and not ("--no-patch" in OS.get_cmdline_args() or "--no-patch" in OS.get_cmdline_user_args())

static func read_state(dir: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(dir.path_join(STATE))
	if text.is_empty(): return {}
	var data = JSON.parse_string(text)
	return data if data is Dictionary else {}

static func write_state(dir: String, state: Dictionary) -> void:
	var file := FileAccess.open(dir.path_join(STATE + ".tmp"), FileAccess.WRITE)
	if file == null: return
	file.store_string(JSON.stringify(state))
	file.close()
	DirAccess.rename_absolute(dir.path_join(STATE + ".tmp"), dir.path_join(STATE))

## Loads the patch the state names; true when it runs now.
static func boot(dir: String) -> bool:
	var state := read_state(dir)
	if state.is_empty(): return false
	var file := dir.path_join(str(state.get("file", "")).get_file())
	if str(state.get("base", "")) != base_version:
		# The game was installed again (another version): its patches belong to the old one.
		problem = "other_base"
		forget(dir, state)
		return false
	if bool(state.get("disabled", false)):
		problem = "crashed"
		return false
	var opened := FileAccess.open(file, FileAccess.READ)
	if opened == null:
		problem = "missing"
		forget(dir, state)
		return false
	var length := opened.get_length()
	opened.close()
	if length != int(state.get("size", -1)):
		problem = "size"
		forget(dir, state)
		return false
	var boots := int(state.get("boots", 0)) + 1
	state.boots = boots
	if boots > MAX_BOOTS:
		# Three launches never reached the title: start as installed, the gate offers the installer.
		problem = "crashed"
		state.disabled = true
		write_state(dir, state)
		return false
	write_state(dir, state)
	if not ProjectSettings.load_resource_pack(file, true):
		problem = "unreadable"
		forget(dir, state)
		return false
	patch = state
	patch_dir = dir
	problem = ""
	# Project settings were read from the installed pack: the patch's own version comes from its
	# project.binary (the patcher's record when it has none, as in source-run tests).
	version = pack_version()
	if version.is_empty(): version = str(state.get("version", base_version))
	ProjectSettings.set_setting("application/config/version", version)
	return true

## The title (or a login) was reached: this patch works, launches stop counting.
static func confirm() -> void:
	if patch.is_empty() or int(patch.get("boots", 0)) == 0: return
	patch.boots = 0
	var state := read_state(patch_dir)
	if str(state.get("file", "")) == str(patch.get("file", "")):
		state.boots = 0
		write_state(patch_dir, state)

static func forget(dir: String, state: Dictionary) -> void:
	var name := str(state.get("file", "")).get_file()
	if not name.is_empty(): DirAccess.remove_absolute(dir.path_join(name))
	DirAccess.remove_absolute(dir.path_join(STATE))

## application/config/version from res://project.binary (the patch's when it carries one).
## Format (ProjectSettings::_save_settings_binary): "ECFG", u32 count, then per setting a u32-length
## UTF-8 name and a u32-length encoded Variant.
static func pack_version() -> String:
	var bytes := FileAccess.get_file_as_bytes("res://project.binary")
	if bytes.size() < 8 or bytes.slice(0, 4).get_string_from_ascii() != "ECFG": return ""
	var count := bytes.decode_u32(4)
	var at := 8
	for i in count:
		if at + 4 > bytes.size(): return ""
		var name_length := bytes.decode_u32(at)
		at += 4
		if at + name_length + 4 > bytes.size(): return ""
		var key := bytes.slice(at, at + name_length).get_string_from_utf8()
		at += name_length
		var value_length := bytes.decode_u32(at)
		at += 4
		if at + value_length > bytes.size(): return ""
		if key == "application/config/version":
			var value = bytes_to_var(bytes.slice(at, at + value_length))
			return str(value) if value is String else ""
		at += value_length
	return ""
