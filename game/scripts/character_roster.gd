extends RefCounted
## The playable roster. Old save ids are migration aliases, never drawable models.
const IDS := ["m1","m2","m3","m4","f1","f2","f3","f4"]
const LEGACY := {"explorer_b":"f1","explorer":"m1","ranger":"f1","tinker":"m1","haeru":"m3"}
const DEFAULT := "f1"
const CARDS := [["m1","m1_adventurer","m","모험가"],["m2","m2_artisan","m","장인"],["m3","m3_fisher","m","낚시꾼"],["m4","m4_smith","m","대장장이"],
    ["f1","f1_adventurer","f","모험가"],["f2","f2_herbalist","f","약초사"],["f3","f3_inventor","f","발명가"],["f4","f4_sailor","f","선원"]]
const PRESETS := {"m1":{"hair":"#67321b","skin":"#ca9582","coat":"#c05426","pants":"#21243a","boots":"#9a4b22","accent":"#516b3c"},
	"m2":{"hair":"#171518","skin":"#cb9383","coat":"#865a27","pants":"#623e29","boots":"#341d16","accent":"#858484"},
	"m3":{"hair":"#181717","skin":"#975a38","coat":"#5787b8","pants":"#cabaa6","boots":"#8a5b3c","accent":"#cfc2ad"},
	"m4":{"hair":"#b84208","skin":"#d39081","coat":"#62664d","pants":"#2b394e","boots":"#20201d","accent":"#808074"},
	"f1":{"hair":"#d36629","skin":"#d09b87","coat":"#d8ad2b","pants":"#347272","boots":"#ece9e5","accent":"#844330"},
	"f2":{"hair":"#1c1b20","skin":"#d09988","coat":"#9f7fb8","pants":"#1e1f42","boots":"#603222","accent":"#6f4146"},
	"f3":{"hair":"#7bbfa7","skin":"#d7a288","coat":"#883b21","pants":"#676460","boots":"#252420","accent":"#726761"},
	"f4":{"hair":"#5f3927","skin":"#9f5e3f","coat":"#5b5978","pants":"#961f24","boots":"#d8d5cf","accent":"#90687d"}}

static func canonical(id: String) -> String:
    var migrated: String=LEGACY.get(id,id)
    return migrated if migrated in IDS else DEFAULT

static func model_path(id: String) -> String:
    return "res://assets/%s.glb"%canonical(id)

static func portrait_path(id: String) -> String:
    return "res://assets/ui/portrait_%s.png"%canonical(id)
