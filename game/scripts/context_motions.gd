extends RefCounted
## Shared policy for imported clips. Position, combat results and seat contacts
## remain owned by the movement/interaction systems.
const LOOPS := ["idle","walk","run","work","relax","look_around","fold_arms","wait","swagger","warm_up","dig"]
const PLAYER_IDLE := {"m1":"relax","m2":"fold_arms","m3":"look_around","m4":"fold_arms",
	"f1":"relax","f2":"wait","f3":"look_around","f4":"wait"}
const RESIDENT_IDLE := {"naru":"look_around","sora":"relax","moru":"fold_arms","haeru":"wait",
	"boni":"fold_arms","sol":"look_around"}
const WORK := {"guide":"look_around","camp":"fold_arms","farm":"dig","garden":"dig","tend":"dig",
	"craft":"work","sweep":"work","tailor":"idle","fish":"idle","play":"warm_up",
	"scout":"look_around","write":"idle","stargaze":"look_around"}

static func configure(player: AnimationPlayer) -> void:
	for clip in player.get_animation_list():
		player.get_animation(clip).loop_mode=Animation.LOOP_LINEAR if clip in LOOPS or str(clip).begins_with("Idle_") else Animation.LOOP_NONE

static func fallback(player: AnimationPlayer, desired: String) -> String:
	if player.has_animation(desired): return desired
	if player.has_animation("idle"): return "idle"
	for clip in player.get_animation_list():
		if str(clip).begins_with("Idle_"): return clip
	return ""

static func idle(player: AnimationPlayer, id: String) -> String:
	return fallback(player,str(PLAYER_IDLE.get(id,"idle")))

static func resident(player: AnimationPlayer, id: String, activity: String) -> String:
	var desired: String=WORK.get(activity,RESIDENT_IDLE.get(id,"idle"))
	return fallback(player,desired)

static func action(kind: String, tool: String) -> Dictionary:
	match kind:
		"attack":
			if tool=="spear": return {} # A forward thrust is the additive weapon pose.
			return {"clip":"slash","from":1.1,"span":2.2,"seconds":.7} if tool=="axe" else {"clip":"punch","from":.15,"span":.9,"seconds":.42}
		"gather":
			if tool=="axe": return {"clip":"chop","from":1.1,"span":2.2,"seconds":.62}
		"hurt": return {"clip":"hurt","from":0.0,"span":1.3,"seconds":.45}
		"greet": return {"clip":"greet","from":0.0,"span":3.53,"seconds":2.0}
		"cheer": return {"clip":"cheer","from":2.0,"span":4.0,"seconds":2.5}
		"clap": return {"clip":"clap","from":2.0,"span":3.0,"seconds":2.0}
		"bow": return {"clip":"bow","from":0.0,"span":6.03,"seconds":2.5}
	return {}
