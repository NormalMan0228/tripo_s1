extends RefCounted
## Korean is the source language. res://i18n/strings.json maps each Korean UI or
## server string to English and Chinese; templates cover server messages that
## embed names or counts. Code wraps user-facing literals in tr() or I18n.t().
const CATALOG := "res://i18n/strings.json"
const TEMPLATES := "res://i18n/templates.json"
const SETTINGS := "user://settings.cfg"
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
	config.load(SETTINGS)
	var code := String(config.get_value("game","language",""))
	if code.is_empty():
		var system := OS.get_locale_language()
		code = system if system in ["ko","en","zh"] else "ko"
	return code

static func set_language(code: String) -> void:
	var config := ConfigFile.new()
	config.load(SETTINGS)
	config.set_value("game","language",code)
	config.save(SETTINGS)
	TranslationServer.set_locale(code)

static func setting(key: String, fallback = "") -> Variant:
	var config := ConfigFile.new()
	config.load(SETTINGS)
	return config.get_value("game",key,fallback)

static func remember(key: String, value) -> void:
	var config := ConfigFile.new()
	config.load(SETTINGS)
	config.set_value("game",key,value)
	config.save(SETTINGS)

static func t(source: String) -> String:
	return TranslationServer.translate(source)

## Server text: an exact catalog entry, else a template such as "{0} {1}개를 수확했어요!".
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
