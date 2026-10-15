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
	# An inappropriate request is refused with its reason, never softened (server/craft_moderation.py).
	if code.begins_with("refused_"): return refused(code.trim_prefix("refused_"))
	match code:
		"image_too_large", "body_too_large": return _t("그림이 너무 커요. 20MB 이하의 그림을 골라 주세요.")
		"image_too_small": return _t("그림이 너무 작아요. 더 큰 그림을 골라 주세요.")
		"image_unreadable", "invalid_image": return _t("그림을 읽지 못했어요. PNG나 JPG 그림을 골라 주세요.")
		"invalid_craft_request": return _t("만들 물건을 2~1500자로 적어 주세요.")
		"craft_over_trial_limit":
			if cap >= 20: return _t("이 조합은 1회 제작 한도(%d크레딧)를 넘어요. 옵션을 줄이거나 운영자에게 한도를 물어보세요.") % cap
			return _t("체험판에서는 가장 간단한 제작(직접 색칠 · 정적인 가구 · H3)만 할 수 있어요.")
		"tripo_budget_exhausted": return _t("이번 학기 제작 예산을 모두 썼어요. 운영자에게 문의해 주세요.")
		"tester_credit_budget_exhausted": return _t("이 계정의 제작 예산을 모두 썼어요. 운영자에게 문의해 주세요.")
		"craft_star_limit_exceeded": return _t("이 제작은 별씨 한도를 넘어요. 옵션을 줄여 다시 맡겨 주세요.")
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

## Why a request cannot be made, by refusal category (sexual, violence, hate, drugs, person, words, other).
static func refused(category: String) -> String:
	match category:
		"sexual": return _t("성적인 내용은 만들 수 없어요.")
		"violence": return _t("잔인하거나 끔찍한 내용은 만들 수 없어요.")
		"hate": return _t("혐오를 담은 상징은 만들 수 없어요.")
		"drugs": return _t("마약과 관련된 물건은 만들 수 없어요.")
		"person": return _t("실제 사람의 얼굴이나 모습은 만들 수 없어요.")
		"words": return _t("욕설이 들어간 의뢰는 받을 수 없어요.")
	return _t("모두가 함께하는 마을에 어울리지 않아 만들 수 없어요.")

## A failed craft: a short title and why, from the server's reason (older servers: the error code).
## {"title": ..., "why": ..., "refused": bool}
static func failure(value: Dictionary) -> Dictionary:
	var code := str(value.get("error", ""))
	var reason := str(value.get("reason", ""))
	if reason.is_empty():
		reason = "refused" if code.begins_with("refused_") else ("timeout" if code == "generation_timeout" else "other")
	var back := _t("맡긴 별씨는 돌려드렸어요.")
	if reason == "refused":
		var category := str(value.get("refusal", code.trim_prefix("refused_")))
		return {"title": _t("만들 수 없는 의뢰예요"), "why": refused(category) + " " + back, "refused": true}
	var why := ""
	match reason:
		"timeout": why = _t("공방이 너무 오래 걸려 이번 제작을 멈췄어요.")
		"design": why = _t("AI가 설계도를 완성하지 못했어요. 조금 더 구체적으로 적어 다시 맡겨 보세요.")
		"busy": why = _t("AI 공방이 지금 붐벼요. 잠시 뒤 다시 맡겨 주세요.")
		"mesh": why = _t("3D 모양을 빚다가 실패했어요. 표현을 바꿔 다시 맡겨 보세요.")
		"heavy": why = _t("만든 모델이 너무 복잡해 마을에 놓을 수 없었어요. 더 단순한 물건으로 해 보세요.")
		"photo": why = _t("참고 그림을 처리하지 못했어요. 다른 그림으로 해 보세요.")
		"restart": why = _t("공방 서버가 다시 시작되어 제작이 멈췄어요. 다시 맡겨 주세요.")
		"setup": why = _t("공방 설정 문제로 만들지 못했어요. 운영자에게 알려 주세요.")
		"credit": why = _t("공방 재료가 떨어졌어요. 운영자에게 알려 주세요.")
		"limit": why = _t("제작 한도를 넘어 멈췄어요.")
		_: why = _t("제작을 마치지 못했어요.")
	return {"title": _t("제작에 실패했어요"), "why": why + " " + back, "refused": false}

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
		"failed": return str(failure(value).why)
	return ""

## Why the finished object cannot be put down where the player is ("" = it can).
static func place_block(where: String) -> String:
	match where:
		"visit": return _t("친구의 마을과 집에는 놓을 수 없어요. 가방에 보관돼요.")
		"public": return _t("이 건물은 꾸밀 수 없어요. 가방에 보관돼요.")
	return ""
