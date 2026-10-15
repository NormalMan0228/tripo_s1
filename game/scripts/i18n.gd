extends RefCounted
## Korean is the source language. res://i18n/strings.json maps each Korean UI or
## server string to English and Chinese; templates cover server messages that
## embed names or counts. Code wraps user-facing literals in tr() or I18n.t().
const CATALOG := "res://i18n/strings.json"
const TEMPLATES := "res://i18n/templates.json"
const SETTINGS := "user://settings.cfg"
## Test runs (tools/test.ps1 passes --qa) keep their own settings, so switching
## languages or logging in during QA never changes the player's language, world or name.
## A run of tools/test.ps1 keeps them in its own throwaway data folder (TRIPOTHON_DATA_DIR, an
## absolute path made for that run): it starts from defaults, goes away with the folder, and runs
## from other worktrees at the same time (the same user:// folder) never read or delete its world,
## language or keys.
const QA_SETTINGS := "user://settings_qa.cfg"
static func settings_path() -> String:
	if not "--qa" in OS.get_cmdline_user_args(): return SETTINGS
	var run := OS.get_environment("TRIPOTHON_DATA_DIR")
	if run.is_absolute_path() and DirAccess.dir_exists_absolute(run): return run.path_join("settings_qa.cfg")
	return QA_SETTINGS
const LANGUAGES := [["ko","한국어"],["en","English"],["zh","中文"]]
static var installed := false
static var templates: Array = []

static func setup() -> void:
	if installed: return
	installed = true
	var data = JSON.parse_string(FileAccess.get_file_as_string(CATALOG)) if FileAccess.file_exists(CATALOG) else null
	if data is Dictionary:
		for code in ["en","zh"]:
			var translation := Translation.new()
			translation.locale = code
			for source in data.get("strings",{}):
				var entry: Dictionary = data.strings[source]
				if entry.has(code) and not String(entry[code]).is_empty(): translation.add_message(source, entry[code])
			TranslationServer.add_translation(translation)
	var patterns = JSON.parse_string(FileAccess.get_file_as_string(TEMPLATES)) if FileAccess.file_exists(TEMPLATES) else null
	if patterns is Array:
		for entry in patterns:
			var pattern := RegEx.new()
			if pattern.compile(entry.pattern) == OK: templates.append({"regex":pattern,"text":entry})
	TranslationServer.set_locale(language())

static func language() -> String:
	var config := ConfigFile.new()
	config.load(settings_path())
	var code := String(config.get_value("game","language",""))
	if code.is_empty():
		var system := OS.get_locale_language()
		code = system if system in ["ko","en","zh"] else "ko"
	return code

static func set_language(code: String) -> void:
	var config := ConfigFile.new()
	config.load(settings_path())
	config.set_value("game","language",code)
	config.save(settings_path())
	TranslationServer.set_locale(code)

static func setting(key: String, fallback = "") -> Variant:
	var config := ConfigFile.new()
	config.load(settings_path())
	return config.get_value("game",key,fallback)

static func remember(key: String, value) -> void:
	var config := ConfigFile.new()
	config.load(settings_path())
	config.set_value("game",key,value)
	config.save(settings_path())

static func t(source: String) -> String:
	return TranslationServer.translate(source)

## Server text: an exact catalog entry, else a template such as "{0} {1}개를 수확했어요!".
## "Talk to <name>" with the Korean particle that fits the name: 와 after a vowel, 과 after a
## final consonant ("가람 · 시인과 대화"). Other languages use their own translation as is.
static func talk_to(name: String) -> String:
	var text := TranslationServer.translate("%s와 대화") % name
	if language() == "ko" and has_final_consonant(name): text = text.replace(name + "와", name + "과")
	return text

## Whether a word ends in a Hangul syllable with a final consonant (받침).
static func has_final_consonant(word: String) -> bool:
	if word.is_empty(): return false
	var code := word.unicode_at(word.length() - 1)
	return code >= 0xAC00 and code <= 0xD7A3 and (code - 0xAC00) % 28 != 0

static func server(source: String) -> String:
	var direct := TranslationServer.translate(source)
	if direct != source or TranslationServer.get_locale().begins_with("ko"): return direct
	for entry in templates:
		var found: RegExMatch = entry.regex.search(source)
		if found == null: continue
		var text: String = entry.text.get(TranslationServer.get_locale().substr(0,2), "")
		if text.is_empty(): return source
		for i in range(1, found.get_group_count()+1):
			text = text.replace("{%d}" % (i-1), TranslationServer.translate(found.get_string(i)))
		return text
	return source
