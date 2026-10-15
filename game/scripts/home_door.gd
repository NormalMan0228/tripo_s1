## A friend's home opens only while its owner is inside (server/home_access.py,
## docs/contracts/SERVER_CONTRACTS_KO.md): the line shown when the door stays shut.
extends RefCounted

const SHUT := {"owner_away": "아무도 없는 것 같아요. 문이 잠겨 있어요.", "locked": "문이 잠겨 있어요.",
	"ejected": "지금은 이 집에 들어갈 수 없어요."}

## The translated line for a presence reply's home block that is not open; "" while it is open or missing.
static func refusal(door) -> String:
	if not door is Dictionary or bool(door.get("open", true)): return ""
	return TranslationServer.translate(SHUT.get(str(door.get("reason", "")), SHUT.ejected))
