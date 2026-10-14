extends RefCounted
## What the craft feature says to the player, one source for every place the craft window opens
## (the village and every room): refusals of a craft, the toasts when the craft needs the player or
## is done, and the window's own labels. main.gd's error_message takes the craft codes from here too.
const BuildMode = preload("res://scripts/build_mode.gd")

## The window's title and the finished craft's button (it places the object where the player is).
const TITLE := "공방 제작 의뢰"
const PLACE := "여기에 놓기"

static func _t(source: String) -> String:
	return TranslationServer.translate(source)

## A craft refusal in words, or "" for a code crafting does not know. `cap` is the server's
## per-craft Tripo credit cap (0 = none): a combination over it is worded as the cap, not the trial.
static func refusal(code: String, cap := 0) -> String:
	var developer := BuildMode.developer()
	match code:
		"invalid_craft_request": return _t("만들 물건을 2~1500자로 적어 주세요.")
		"craft_over_trial_limit":
			if cap >= 20: return _t("이 조합은 1회 제작 한도(%d크레딧)를 넘어요. 옵션을 줄이거나 운영자에게 한도를 물어보세요.") % cap
			return _t("체험판에서는 가장 간단한 제작(직접 색칠 · 정적인 가구 · H3)만 할 수 있어요.")
		"tripo_budget_exhausted": return _t("이번 학기 제작 예산을 모두 썼어요. 운영자에게 문의해 주세요.")
		"user_total_generation_limit": return _t("이 계정의 제작 의뢰 횟수를 모두 썼어요. 만든 물건으로 마을을 꾸며 보세요!")
		"user_daily_generation_limit": return _t("오늘 맡길 수 있는 제작을 모두 썼어요. 내일 다시 찾아와 주세요.")
		"daily_generation_limit": return _t("오늘 생성 한도에 도달했습니다.")
		"provider_busy": return _t("공방 장인이 다른 의뢰를 만들고 있어요. 조금 뒤에 다시 맡겨 주세요.")
		"generation_pending": return _t("진행 중인 생성이 있습니다.")
		"insufficient_shards": return _t("별씨가 부족합니다. 생존 도전을 완료해 보세요.")
		"live_generation_disabled":
			return _t("공방 장인이 아직 자리를 비웠어요.") if developer else _t("새 가구 제작을 준비하고 있어요. 지금은 보관함의 물건으로 꾸며 보세요.")
		"insufficient_provider_credit":
			return _t("공방 재료가 떨어졌어요. 맡긴 별씨는 돌려드려요.") if developer else _t("지금은 제작을 완료할 수 없어요. 맡긴 별씨는 돌려드렸어요.")
		"connection_failed": return _t("마을과의 연결이 끊어졌어요. 잠시 뒤 다시 들어와 주세요.")
	return ""

## Any reply to a craft call in words. Bad input is about the description (never the login form's
## name and password); some refusals arrive already worded (the per-account limit).
static func error(code: String, cap := 0) -> String:
	if code.contains(" "): return code
	var words := refusal("invalid_craft_request" if code == "invalid_request" else code, cap)
	if not words.is_empty(): return words
	return _t("요청을 완료하지 못했습니다: ") + code if BuildMode.developer() else _t("지금은 완료하지 못했어요. 잠시 뒤 다시 시도해 주세요.")

## The toast when the craft needs the player; `away` (the window is closed) adds how to open it.
static func ready_words(value: Dictionary, away := false) -> String:
	var picture: bool = not value.get("concept", {}).is_empty()
	if away: return _t("AI가 그림을 그렸어요! C를 눌러 확인해 주세요." if picture else "설계와 견적이 나왔어요! C를 눌러 확인해 주세요.")
	return _t("AI가 그림을 그렸어요! 마음에 드는지 확인해 주세요." if picture else "설계와 견적이 나왔어요! 확인하고 제작을 맡겨 주세요.")

## The toast when a craft ends; "" when the open window shows it already (the finished view).
static func ended_words(value: Dictionary, away := false) -> String:
	match str(value.get("state", "")):
		"ready": return _t("새 물건이 완성됐어요! C를 눌러 확인해 보세요.") if away else ""
		"unknown": return _t("제작 요청을 확인하고 있어요. 운영자가 확인하면 맡긴 별씨가 돌아와요.")
		"failed":
			if str(value.get("error", "")) == "generation_timeout": return _t("공방이 너무 오래 걸려 이번 제작을 멈췄어요. 맡긴 별씨는 돌려드렸어요.")
			return _t("제작을 마치지 못했어요. 맡긴 별씨는 돌려드렸어요.")
	return ""

## Why the finished object cannot be put down where the player is ("" = it can).
static func place_block(where: String) -> String:
	match where:
		"visit": return _t("친구의 마을과 집에는 놓을 수 없어요. 가방에 보관돼요.")
		"public": return _t("이 건물은 꾸밀 수 없어요. 가방에 보관돼요.")
	return ""
