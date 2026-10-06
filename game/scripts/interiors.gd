extends RefCounted
## Interiors for every enterable village building. The floor size follows the
## building footprint (res://maps/archipelago/building_placements.json), each
## theme has its own shell (floor, walls, windows, front door) and a furnished
## default layout. Furniture uses the generated GLBs listed in
## res://assets/interior/manifest.json once they are imported, then village
## props, and otherwise a primitive stand-in, so a room always looks furnished.
##
## Coordinates: the room is centred on the origin, the open front edge (door,
## camera side) is +z, the back wall is -z. Furniture faces +z before its yaw.
const Art = preload("res://scripts/art.gd")
const Detail = preload("res://scripts/world_detail.gd")
const Loader = preload("res://scripts/model_loader.gd")
const Daylight = preload("res://scripts/daylight.gd")
const Residents = preload("res://scripts/residents.gd")
const BUILDINGS := "res://maps/archipelago/building_placements.json"
const MANIFEST := "res://assets/interior/manifest.json"
const INTERIOR_DIR := "res://assets/interior/"
const ENVIRONMENT_DIR := "res://maps/archipelago/assets/environment/"
## The player's rooms keep their old names; the village opens the others by building id.
const PRIVATE := {"home":"10_red_house","workshop":"09_town_hall"}
const OPEN_STRUCTURES := ["08_gazebo","14_stage","15_picnic_shelter"]
const WALL := 0.22
const KNEE := 0.5
const DOOR_HALF := 0.85
const PART := 0.16
const DOORWAY := 1.3
## Floors of side-by-side rooms: [name, width share, theme?]. Total width and depth
## follow the building's footprint (about 80-95% of it, ground floor; lofts and
## upper floors are smaller). Home and workshop keep their 10x10+ ground floor so
## the server's [-4,4] furniture square stays inside.
const PLANS := {
	"10_red_house":[{"rooms":[["거실",1.0]],"w":10.0,"d":10.0,"h":3.4,"label":"1층"},{"rooms":[["다락 침실",1.0]],"w":8.0,"d":6.5,"h":2.9,"theme":"attic","label":"다락"}],
	"09_town_hall":[{"rooms":[["공방",1.0]],"w":10.5,"d":10.5,"h":4.2,"label":"1층"},{"rooms":[["자료실",0.58,"archive"],["사무실",0.42]],"w":10.0,"d":7.5,"h":3.4,"theme":"office","label":"2층"}],
	"01_cafe":[{"rooms":[["홀",0.62],["주방",0.38,"cafe_kitchen"]],"w":10.0,"d":8.5,"h":3.4,"door_z":-1.0,"label":"1층"},{"rooms":[["주인 방",1.0]],"w":7.0,"d":5.5,"h":2.9,"theme":"owner_room","label":"2층"}],
	"02_timber_house":[{"rooms":[["거실",1.0]],"w":9.5,"d":9.5,"h":3.4,"label":"1층"},{"rooms":[["다락 침실",1.0]],"w":7.5,"d":6.5,"h":2.9,"theme":"loft","label":"다락"}],
	"03_teal_cottage":[{"rooms":[["가게",0.6],["창고",0.4,"storeroom"]],"w":7.5,"d":6.0,"h":2.9,"door_z":0.3,"label":"1층"},{"rooms":[["농부의 방",1.0]],"w":6.5,"d":5.0,"h":2.8,"theme":"owner_room","label":"다락"}],
	"04_windmill":[{"rooms":[["맷돌방",1.0]],"w":8.0,"d":6.0,"h":4.0,"label":"1층"},{"rooms":[["톱니바퀴 다락",0.6],["방앗간지기 방",0.4,"owner_room"]],"w":8.0,"d":5.5,"h":3.2,"theme":"gear_loft","label":"2층","door_z":0.6}],
	"05_observatory":[{"rooms":[["서재",0.65],["별지기 방",0.35,"owner_room"]],"w":8.5,"d":7.5,"h":3.4,"theme":"study","label":"1층","door_z":0.6},{"rooms":[["관측 돔",1.0]],"w":8.0,"d":8.0,"h":4.4,"shape":"round","label":"돔"}],
	"06_orange_cottage":[{"rooms":[["부엌",0.58],["작은 침실",0.42,"cottage_bedroom"]],"w":8.0,"d":6.5,"h":2.9,"door_z":0.2}],
	"07_greenhouse":[{"rooms":[["온실",0.7],["정원사 방",0.3,"potting"]],"w":9.0,"d":8.5,"h":3.8,"door_z":0.8}],
	"11_purple_house":[{"rooms":[["응접실",0.58],["서재",0.42,"purple_study"]],"w":9.0,"d":8.0,"h":3.4,"door_z":0.3,"label":"1층"},{"rooms":[["침실",0.55],["소라의 방",0.45,"purple_study"]],"w":8.8,"d":6.5,"h":2.9,"label":"2층","door_z":0.6}],
	"12_blue_house":[{"rooms":[["침실",0.56],["욕실",0.44,"bath"]],"w":8.0,"d":7.0,"h":2.9,"door_z":0.4}],
	"13_shop":[{"rooms":[["매장",0.6],["창고",0.4,"storeroom"]],"w":7.0,"d":6.0,"h":2.9,"door_z":0.2,"label":"1층"},{"rooms":[["주인 방",1.0]],"w":6.0,"d":5.0,"h":2.8,"theme":"owner_room","label":"다락"}],
	"16_blue_cottage":[{"rooms":[["거실",0.58],["침실",0.42,"bedroom"]],"w":8.5,"d":7.5,"h":2.9,"door_z":0.3}],
	"17_lighthouse":[{"rooms":[["창고",1.0]],"w":7.0,"d":6.0,"h":3.8,"shape":"round","label":"1층"},{"rooms":[["등대지기 방",1.0]],"w":7.0,"d":6.0,"h":3.4,"shape":"round","theme":"keeper","label":"2층"},{"rooms":[["등실",1.0]],"w":6.5,"d":6.0,"h":3.4,"shape":"round","theme":"lantern","label":"등실","balcony":true}],
}
## What each building's windows look out on (its island's surroundings).
const OUTLOOK := {"01_cafe":"meadow","02_timber_house":"meadow","03_teal_cottage":"meadow","04_windmill":"meadow","05_observatory":"garden","06_orange_cottage":"garden","07_greenhouse":"garden","09_town_hall":"town","10_red_house":"town","11_purple_house":"town","12_blue_house":"town","13_shop":"town","16_blue_cottage":"camp","17_lighthouse":"sea"}
const WINDOW_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;
uniform sampler2D day_tex : source_color, filter_linear_mipmap;
uniform sampler2D night_tex : source_color, filter_linear_mipmap;
uniform float night = 0.0;
uniform vec4 tint : source_color = vec4(1.0);
uniform float lift = 0.0;
uniform float round_mask = 0.0;
void fragment() {
	if (round_mask > 0.5 && length(UV - vec2(0.5)) > 0.5) discard;
	vec2 uv = vec2(UV.x, clamp(UV.y * (1.0 - lift) + lift * 0.55, 0.0, 1.0));
	vec3 day = texture(day_tex, uv).rgb * tint.rgb;
	vec3 moon = texture(night_tex, uv).rgb;
	ALBEDO = mix(day, moon, night);
}
"""
static var window_shader: Shader

## Korean source strings are translated where they are displayed.
const ROOMS := {
	"10_red_house":{"theme":"home","name":"빨간 지붕 붉은 벽돌 주택","kind":"나의 작은 집","flavour":"","dims":[10.05,8.0,9.76]},
	"09_town_hall":{"theme":"workshop","name":"시계탑이 있는 마을 회관","kind":"물결빛 공방","flavour":"","dims":[12.44,10.0,12.27],"height":4.2,"fill":0.85},
	"01_cafe":{"theme":"cafe","name":"빨간 곡면 지붕 카페","kind":"마을 카페","flavour":"갓 내린 커피 향과 피아노 소리가 반겨 주는 카페예요.","dims":[10.06,8.0,10.83]},
	"02_timber_house":{"theme":"lodge","name":"청색 지붕 목조 주택","kind":"통나무 거실","flavour":"벽난로가 타닥타닥, 나무 향이 가득한 집이에요.","dims":[12.13,8.0,11.79]},
	"03_teal_cottage":{"theme":"seed_shop","name":"청록 지붕 크림색 주택","kind":"씨앗 가게","flavour":"계절 씨앗과 새싹 화분을 파는 작은 가게예요.","dims":[7.65,6.2,7.75]},
	"04_windmill":{"theme":"windmill","name":"풍차","kind":"맷돌 방앗간","flavour":"커다란 맷돌이 천천히 돌며 밀가루를 빻고 있어요.","dims":[10.19,12.0,6.73],"height":4.0},
	"05_observatory":{"theme":"observatory","name":"망원경과 청색 돔 천문대","kind":"별빛 천문대","flavour":"밤하늘을 닮은 방에 커다란 망원경이 놓여 있어요.","dims":[10.16,11.0,11.3],"height":4.4},
	"06_orange_cottage":{"theme":"kitchen","name":"주황 지붕 청록색 주택","kind":"빵 굽는 부엌","flavour":"오븐에서 갓 구운 빵 냄새가 솔솔 나요.","dims":[8.51,6.2,8.21]},
	"07_greenhouse":{"theme":"greenhouse","name":"유리 온실","kind":"햇살 온실","flavour":"햇살이 가득한 유리벽 안에서 새싹이 자라요.","dims":[11.17,6.5,10.47],"height":3.8},
	"11_purple_house":{"theme":"parlour","name":"보라색 지붕 주택","kind":"음악 응접실","flavour":"피아노와 책이 가득한 조용한 응접실이에요.","dims":[9.82,8.0,9.82]},
	"12_blue_house":{"theme":"bedroom","name":"노란 지붕 파란 주택","kind":"아늑한 침실","flavour":"포근한 이불과 작은 창이 있는 침실이에요.","dims":[8.75,6.8,8.8]},
	"13_shop":{"theme":"shop","name":"녹백색 줄무늬 차양 상점","kind":"마을 잡화점","flavour":"없는 게 없는 마을 잡화점이에요. 구경은 언제나 무료!","dims":[6.74,5.5,6.21]},
	"16_blue_cottage":{"theme":"reading","name":"청색 지붕 크림색 주택","kind":"벽난로 오두막","flavour":"벽난로 옆 안락의자에서 책 읽기 좋은 오두막이에요.","dims":[9.11,6.8,9.1]},
	"17_lighthouse":{"theme":"lighthouse","name":"빨간 등실 등대","kind":"바다를 지키는 등대","flavour":"둥근 벽을 따라 등실로 오르는 나선 계단이 있어요.","dims":[4.57,9.0,5.06],"height":3.8,"shape":"round"},
}

## floor: texture style; wall_tex: wall style; colours are hex strings.
const THEMES := {
	"home":{"floor":"planks","floor_a":"cda97a","floor_b":"b88f62","wall":"f0e3c7","wall_tex":"plaster","wainscot":"93b09c","trim":"7a5a40","accent":"d9826b","cut":"4b3a2d","view":"day","curtain":"eab7a1","ambient":"f2e4cb","light":"ffd9a3"},
	"workshop":{"floor":"wide_planks","floor_a":"ae845a","floor_b":"98714a","wall":"e4d7ba","wall_tex":"plaster","wainscot":"7d634a","trim":"5f4632","accent":"5e8c7d","cut":"3d3026","beams":true,"view":"day","curtain":"","ambient":"efe2c8","light":"ffd7a0"},
	"cafe":{"floor":"checker","floor_a":"f2e7d0","floor_b":"c9735b","wall":"f5e9d3","wall_tex":"plaster","wainscot":"6f906b","trim":"5a4232","accent":"c44f43","cut":"3f3027","view":"day","curtain":"f3d9a0","ambient":"f6e6cc","light":"ffd39a"},
	"lodge":{"floor":"planks","floor_a":"ab7f54","floor_b":"966b44","wall":"c49567","wall_tex":"logs","wainscot":"","trim":"5b3f2a","accent":"3f6f8f","cut":"3a2a1e","view":"day","curtain":"c7d9e6","ambient":"f1e0c8","light":"ffcf91"},
	"seed_shop":{"floor":"planks","floor_a":"cbb089","floor_b":"b79d75","wall":"e6f1e6","wall_tex":"stripes","stripe":"d3e7df","wainscot":"5c9b92","trim":"5b4a39","accent":"e0a24c","cut":"3b3a30","view":"day","curtain":"f5e2a0","ambient":"eef0dc","light":"ffe0aa"},
	"windmill":{"floor":"flags","floor_a":"c2b9a6","floor_b":"a89f8c","wall":"ebe0cb","wall_tex":"plaster","wainscot":"","trim":"6b4e36","accent":"d9b45a","cut":"3d3128","beams":true,"view":"day","curtain":"","ambient":"efe3cc","light":"ffd8a0"},
	"observatory":{"floor":"tiles","floor_a":"4a5781","floor_b":"3d486e","wall":"2a3762","wall_tex":"stars","wainscot":"1f2a4c","trim":"c9a45c","accent":"e8c66a","cut":"151b33","view":"night","curtain":"","ambient":"b8c2e6","light":"ffd28f"},
	"kitchen":{"floor":"tiles","floor_a":"f1e9d8","floor_b":"dccbb0","wall":"f7e4c9","wall_tex":"plaster","wainscot":"e2905a","trim":"6b4a33","accent":"4fa39a","cut":"3f2f24","view":"day","curtain":"bfe3dc","ambient":"f6e5ca","light":"ffd8a2"},
	"greenhouse":{"floor":"terracotta","floor_a":"cc9069","floor_b":"b97d59","wall":"e2f1e8","wall_tex":"glass","wainscot":"9c8c79","trim":"f6f4ec","accent":"6fae6a","cut":"5f6e64","view":"garden","curtain":"","ambient":"eef4e2","light":"fff0c8"},
	"parlour":{"floor":"planks","floor_a":"a17856","floor_b":"8d6847","wall":"eee2f1","wall_tex":"stripes","stripe":"e3d3eb","wainscot":"82629c","trim":"4f3a5c","accent":"b58ad1","cut":"35283f","view":"day","curtain":"c9a3d9","ambient":"f1e4ea","light":"ffd6a6"},
	"bedroom":{"floor":"planks","floor_a":"d2b186","floor_b":"c19d70","wall":"dde9f4","wall_tex":"plaster","wainscot":"e3c45c","trim":"5d6f86","accent":"5d86b8","cut":"2f3a48","view":"day","curtain":"f4e7b3","ambient":"eceae0","light":"ffdcae"},
	"shop":{"floor":"planks","floor_a":"d9c39c","floor_b":"c6af88","wall":"f2f5eb","wall_tex":"stripes","stripe":"d2e9d6","wainscot":"4f8a6a","trim":"3f5a48","accent":"e9b949","cut":"2e3b33","view":"day","curtain":"","ambient":"f0f0e0","light":"ffe2b0"},
	"reading":{"floor":"planks","floor_a":"bb9266","floor_b":"a88157","wall":"f3ead8","wall_tex":"plaster","wainscot":"5d82aa","trim":"4d3a2a","accent":"c8553d","cut":"33291f","view":"day","curtain":"b9cde4","ambient":"f2e3cc","light":"ffd093"},
	"lighthouse":{"floor":"flags","floor_a":"c6bfb2","floor_b":"b0a89a","wall":"f5f2ea","wall_tex":"plaster","wainscot":"c4483e","trim":"3f5c75","accent":"2f6c9b","cut":"2e3540","view":"sea","curtain":"","ambient":"eef0ec","light":"ffe4b0"},
	"attic":{"floor":"wide_planks","floor_a":"c39a6c","floor_b":"ad845a","wall":"efe0c4","wall_tex":"plaster","wainscot":"b98d62","trim":"6e4e36","accent":"6f9fc4","cut":"43342a","beams":true,"curtain":"e7d3a8","ambient":"f2e2c8","light":"ffd39a"},
	"office":{"floor":"planks","floor_a":"b48a5e","floor_b":"a07a50","wall":"e8dcc2","wall_tex":"stripes","stripe":"dfd2b4","wainscot":"6d5a46","trim":"54402f","accent":"3f6f8f","cut":"3a2e25","curtain":"c8b48a","ambient":"efe2c8","light":"ffd7a0"},
	"archive":{"floor":"wide_planks","floor_a":"9e7a55","floor_b":"8a6a48","wall":"e2d6bb","wall_tex":"plaster","wainscot":"5c4a3a","trim":"4b3a2c","accent":"8a5a3c","cut":"352a22","curtain":"","ambient":"eadcc2","light":"ffd093"},
	"cafe_kitchen":{"floor":"tiles","floor_a":"eef0ea","floor_b":"c9d6d0","wall":"f4efe4","wall_tex":"tiles","stripe":"e2ebe6","wainscot":"6f906b","trim":"5a4232","accent":"c44f43","cut":"3f3027","curtain":"f3d9a0","ambient":"f6eedc","light":"ffe2b0"},
	"loft":{"floor":"planks","floor_a":"b98c5e","floor_b":"a37a50","wall":"c99d70","wall_tex":"logs","wainscot":"","trim":"5b3f2a","accent":"5f8f6a","cut":"3a2a1e","curtain":"e0d2b0","ambient":"f1e0c8","light":"ffcf91"},
	"storeroom":{"floor":"wide_planks","floor_a":"b0956e","floor_b":"9c8360","wall":"e6dcc6","wall_tex":"plaster","wainscot":"8b7458","trim":"5b4a39","accent":"c8913f","cut":"3b3a30","curtain":"","ambient":"ece0c8","light":"ffd9a0"},
	"gear_loft":{"floor":"wide_planks","floor_a":"a8875e","floor_b":"937451","wall":"e8dcc4","wall_tex":"plaster","wainscot":"","trim":"6b4e36","accent":"d9b45a","cut":"3d3128","beams":true,"curtain":"","ambient":"efe3cc","light":"ffd8a0"},
	"study":{"floor":"planks","floor_a":"9a7350","floor_b":"86613f","wall":"dfe6dc","wall_tex":"stripes","stripe":"d3dccf","wainscot":"3f6a5c","trim":"4b3a2a","accent":"3c6a5a","cut":"2a3029","curtain":"c9a45c","ambient":"ece6d4","light":"ffd28f"},
	"cottage_bedroom":{"floor":"planks","floor_a":"d2b186","floor_b":"c19d70","wall":"f6ead6","wall_tex":"stripes","stripe":"f0dcc4","wainscot":"4fa39a","trim":"6b4a33","accent":"e08a5a","cut":"3f2f24","curtain":"f4e7b3","ambient":"f6e5ca","light":"ffd8a2"},
	"purple_study":{"floor":"planks","floor_a":"9c7452","floor_b":"886445","wall":"e6dcef","wall_tex":"plaster","wainscot":"5c4a78","trim":"4f3a5c","accent":"8a6ab0","cut":"35283f","curtain":"c9a3d9","ambient":"efe4ea","light":"ffd6a6"},
	"bath":{"floor":"checker","floor_a":"f4f7f8","floor_b":"9cc4dc","wall":"eef5f8","wall_tex":"tiles","stripe":"dceaf1","wainscot":"7fb0d0","trim":"5d6f86","accent":"5d9cc8","cut":"2f3a48","curtain":"f4e7b3","ambient":"eef2f2","light":"fff0d0"},
	"keeper":{"floor":"planks","floor_a":"c4a27a","floor_b":"b08e66","wall":"f5f2ea","wall_tex":"plaster","wainscot":"3f5c75","trim":"2f4a60","accent":"c4483e","cut":"2e3540","curtain":"c9dbe8","ambient":"eef0ec","light":"ffe0a8"},
	"owner_room":{"floor":"planks","floor_a":"c9a274","floor_b":"b48c60","wall":"f3e6cf","wall_tex":"stripes","stripe":"ead9bd","wainscot":"8a6a4c","trim":"5e4430","accent":"d98a5a","cut":"3e2f24","curtain":"e9c9a0","ambient":"f3e3c8","light":"ffd39a"},
	"potting":{"floor":"wide_planks","floor_a":"b39370","floor_b":"9f8160","wall":"e6e0cc","wall_tex":"plaster","wainscot":"6f9a6a","trim":"5b4a39","accent":"6fae6a","cut":"3b3a30","curtain":"d9e8c8","ambient":"eef0dc","light":"ffe0aa"},
	"lantern":{"floor":"flags","floor_a":"9ea6ad","floor_b":"8a9299","wall":"eef2f4","wall_tex":"plaster","wainscot":"c4483e","trim":"2f3540","accent":"c4483e","cut":"2e3540","curtain":"","ambient":"eef0f2","light":"fff0c0"},
}

## Default footprint [w, h, d] in metres; generated GLBs are fitted into it.
const CATALOG := {
	"bed":[1.4,1.0,2.1],"wardrobe_closet":[1.2,2.0,0.6],"bookshelf":[1.4,1.9,0.45],"dining_table":[1.5,0.78,0.95],
	"wooden_chair":[0.5,0.95,0.5],"sofa":[1.9,0.9,0.85],"armchair":[0.95,0.9,0.85],"kitchen_counter":[1.8,0.95,0.65],
	"cooking_stove":[0.9,1.0,0.7],"potted_plant":[0.6,1.25,0.6],"floor_lamp":[0.45,1.7,0.45],"shop_counter":[2.0,1.0,0.75],
	"display_shelf":[1.4,1.7,0.5],"crate_stack":[1.0,1.1,0.9],"barrel":[0.7,0.95,0.7],"workbench":[1.8,0.95,1.0],
	"telescope":[1.2,2.0,1.2],"seedling_bench":[1.8,0.85,0.7],"cafe_counter":[2.6,1.05,0.8],"round_cafe_table":[0.85,0.76,0.85],
	"piano":[1.5,1.3,1.0],"fireplace":[1.6,1.4,0.6],"lighthouse_lens":[1.4,1.9,1.4],"rug":[3.0,0.02,2.0],"wall_clock":[0.6,0.6,0.1],
	"side_table":[0.5,0.55,0.45],"globe":[0.6,1.1,0.6],"star_chart":[1.8,1.2,0.06],"menu_board":[1.6,1.0,0.08],
	"notice_board":[1.5,1.0,0.08],"picture_frame":[0.9,0.7,0.06],"wall_shelf":[1.3,0.5,0.3],"banner":[0.8,1.6,0.06],
	"tool_rack":[1.6,1.0,0.1],"shop_sign":[1.6,0.45,0.08],"ship_wheel":[0.9,0.9,0.12],"millstone":[2.2,1.25,2.2],
	"flour_sacks":[1.2,0.8,0.8],"spiral_stair":[2.1,3.8,2.1],"map_table":[1.2,0.85,0.8],"soil_bed":[2.4,0.5,1.3],
	"ladder":[0.6,2.6,0.3],"staircase":[1.4,3.4,2.7],"stair_hatch":[1.5,0.95,1.8],"chest":[0.9,0.6,0.5],"washstand":[0.7,1.9,0.5],"bathtub":[1.6,0.65,0.8],"coat_rack":[0.5,1.8,0.5],"basket":[0.55,0.45,0.45],"gear_wheel":[2.4,2.7,0.7],"hoist":[0.9,3.0,0.9],"bench":[1.6,0.95,0.6],"planter":[0.7,0.75,0.7],"signboard":[0.7,1.05,0.6],"desk":[1.3,0.8,0.65],
}
## Mounted on a wall: no collision, still something to look at.
const MOUNTED := ["wall_clock","star_chart","menu_board","notice_board","picture_frame","wall_shelf","banner","tool_rack","shop_sign","ship_wheel"]
const FLAT := ["rug"]
## Kinds that can use an existing village prop when no generated GLB exists yet.
const PROP_FALLBACK := {"round_cafe_table":"cafe_table","bench":"bench","planter":"planter"}
## Turn (degrees) that makes a GLB face +z, keyed by file name. Most generated
## interior models (and the village bench) were authored facing +x.
const YAW_FIX := {"bed":-90,"wardrobe_closet":-90,"bookshelf":-90,"dining_table":-90,"wooden_chair":-90,"sofa":-90,
	"kitchen_counter":-90,"cooking_stove":-90,"display_shelf":-90,"crate_stack":-90,"workbench":-90,"telescope":-90,
	"seedling_bench":-90,"piano":-90,"fireplace":-90,"wall_clock":-90,"bench":-90}
## Kinds always built from primitives (tailored sizes or room-specific details).
const PRIMITIVE_ONLY := ["rug","spiral_stair","millstone","soil_bed","signboard","staircase","stair_hatch","chest","washstand","bathtub","coat_rack","basket","gear_wheel","hoist","ladder"]

## What a kind says when the player presses E next to it.
const LINES := {
	"bed":["포근한 침대예요. 잠깐 쉬어 갈까요?","이불에서 햇볕 냄새가 나요."],
	"wardrobe_closet":["옷장 안에 계절 옷이 가지런해요.","옷장 문을 살짝 열어 봤어요. 나프탈렌 향이 나요."],
	"dining_table":["따뜻한 차 한 잔이 놓여 있어요.","식탁에 둘러앉으면 이야기꽃이 피어요."],
	"wooden_chair":["삐걱, 정겨운 소리가 나는 나무 의자예요."],
	"sofa":["푹신한 소파예요. 잠깐 앉아 볼까요?"],
	"armchair":["안락의자에 앉으니 스르르 졸음이 와요."],
	"kitchen_counter":["갓 구운 빵 냄새가 나요.","도마 위에 잘 익은 토마토가 있어요."],
	"cooking_stove":["보글보글 수프가 끓고 있어요.","화덕이 따끈따끈해요."],
	"potted_plant":["잎이 반짝반짝 윤이 나요.","화분에 물을 살짝 줬어요."],
	"shop_counter":["어서 오세요! 오늘의 추천은 별사탕 씨앗이에요.","계산대 위 작은 종이 딸랑 울려요."],
	"display_shelf":["알록달록한 물건이 가지런히 진열돼 있어요."],
	"crate_stack":["상자마다 섬 이름이 적혀 있어요."],
	"barrel":["통 안에서 사과 향이 나요."],
	"workbench":["망치와 대패가 가지런히 놓여 있어요."],
	"desk":["책상 위에 별 관측 일지가 펼쳐져 있어요."],
	"telescope":["별자리가 보여요. 오늘은 고래자리가 또렷해요!","렌즈 너머로 반짝이는 별똥별이 지나갔어요."],
	"seedling_bench":["새싹이 쏙쏙 올라오고 있어요.","새싹에 '곧 꽃 핌'이라는 이름표가 붙어 있어요."],
	"cafe_counter":["따끈한 코코아를 주문했어요. 달콤해요!","오늘의 케이크는 딸기 생크림이에요."],
	"round_cafe_table":["창가 자리에 햇살이 비쳐요."],
	"fireplace":["불가에 서니 몸이 사르르 따뜻해져요.","장작이 타닥타닥 타고 있어요."],
	"lighthouse_lens":["커다란 렌즈가 바다 쪽으로 빛을 모으고 있어요."],
	"side_table":["작은 탁자 위에 읽다 만 편지가 있어요."],
	"globe":["지구본을 빙글 돌려 봤어요."],
	"star_chart":["별자리 지도에 반짝이는 점이 가득해요."],
	"menu_board":["오늘의 메뉴: 별빛 라테, 구름 케이크, 햇살 레모네이드"],
	"notice_board":["게시판에 '이번 주말 바닷가 소풍' 공지가 붙어 있어요."],
	"picture_frame":["바닷가 마을을 그린 그림이에요."],
	"wall_shelf":["선반 위 찻잔들이 반짝여요."],
	"banner":["마을 깃발에 별씨 문장이 수놓여 있어요."],
	"tool_rack":["연장이 크기순으로 걸려 있어요."],
	"shop_sign":["간판 글씨가 정성스럽게 칠해져 있어요."],
	"ship_wheel":["오래된 배의 키예요. 바다 냄새가 나요."],
	"millstone":["맷돌이 천천히 돌며 밀을 빻고 있어요."],
	"flour_sacks":["밀가루 포대가 묵직해요."],
	"spiral_stair":["꼭대기 등실로 이어지는 나선 계단이에요."],
	"map_table":["바다 지도 위에 항로가 그려져 있어요."],
	"soil_bed":["꽃이 활짝 피었어요. 벌이 놀러 올 것 같아요."],
	"ladder":["다락으로 오르는 사다리예요."],
	"bench":["벤치에 앉아 새싹을 바라봐요."],
	"planter":["화분 속 꽃이 방긋 웃는 것 같아요."],
	"signboard":["입간판에 '어서 오세요' 라고 적혀 있어요."],
	"chest":["상자 뚜껑을 열어 보니 오래된 사진이 들어 있어요.","상자 안에 털실 뭉치가 가득해요."],
	"washstand":["찰방찰방, 손을 깨끗이 씻었어요.","거울 속 내 얼굴이 웃고 있어요."],
	"bathtub":["따뜻한 물에 거품이 몽글몽글해요."],
	"coat_rack":["외투에서 바닷바람 냄새가 나요."],
	"basket":["바구니에 잘 익은 과일이 담겨 있어요."],
	"gear_wheel":["커다란 톱니바퀴가 덜컹덜컹 돌아가요."],
	"hoist":["도르래를 당기니 밀가루 포대가 스르르 올라가요."],
	"staircase":["계단을 올라가요."],
	"stair_hatch":["계단을 내려가요."],
}
## What pressing E does with each kind (the studio plays the matching effect).
const ACTIONS := {"bed":"lie","wooden_chair":"sit","sofa":"sit","armchair":"sit","bench":"sit","wardrobe_closet":"open","side_table":"open","chest":"open",
	"kitchen_counter":"wash","washstand":"wash","bathtub":"wash","cooking_stove":"cook","fireplace":"warm","potted_plant":"water","planter":"water",
	"seedling_bench":"water","soil_bed":"water","bookshelf":"read","desk":"read","map_table":"read","notice_board":"read","star_chart":"read",
	"menu_board":"read","dining_table":"read","wall_clock":"wind","shop_counter":"ring","cafe_counter":"ring","piano":"play","telescope":"turn",
	"ship_wheel":"turn","globe":"turn","gear_wheel":"turn","floor_lamp":"switch","crate_stack":"knock","barrel":"knock","flour_sacks":"pat",
	"window":"look_out","millstone":"grind","lighthouse_lens":"shine","round_cafe_table":"sip","workbench":"hammer","hoist":"pull"}
## The key chip text for each action ("E 살펴보기" by default).
const ACTION_HINTS := {"lie":"눕기","sit":"앉기","open":"열어 보기","wash":"씻기","cook":"요리하기","warm":"불 쬐기","water":"물 주기","read":"읽기",
	"wind":"태엽 감기","ring":"종 울리기","turn":"돌려 보기","switch":"불 켜고 끄기","knock":"두드려 보기","pat":"툭툭 치기","look_out":"창밖 보기",
	"grind":"맷돌 보기","shine":"렌즈 닦기","sip":"차 마시기","hammer":"망치질","pull":"도르래 당기기","play":"연주하기","look":"살펴보기"}
const SOUNDS := {"lie":"cushion","sit":"cushion","open":"creak","wash":"splash","cook":"sizzle","warm":"crackle","water":"splash","read":"page",
	"wind":"tick","ring":"ding","turn":"creak","switch":"click","knock":"knock","pat":"cushion","look_out":"whoosh","grind":"rumble",
	"shine":"chime","sip":"clink","hammer":"knock","pull":"creak","travel":"steps","look":"pop"}
const BOOKS := ["『등대지기의 여름 일기』","『별씨를 심는 법』","『바다를 건너는 고래』","『일곱 밤의 숲 이야기』","『빵 굽는 곰의 레시피』","『작은 섬의 큰 모험』"]
const PIANO_TUNES := [[523.25,659.25,783.99,1046.5],[659.25,587.33,523.25,587.33,659.25,659.25,659.25],[392.0,523.25,659.25,783.99,659.25,523.25]]

static var manifest_cache: Dictionary = {}
static var manifest_loaded := false
static var dims_cache: Dictionary = {}
static var texture_cache: Dictionary = {}
static var sound_cache: Dictionary = {}

static func building_for(room: String) -> String:
	return str(PRIVATE.get(room,room))

static func is_private(room: String) -> bool:
	return PRIVATE.has(room)

## True when the village can open this building id (or home/workshop) as a room.
static func has_interior(room: String) -> bool:
	return ROOMS.has(building_for(room))

static func is_public(room: String) -> bool:
	return has_interior(room) and not is_private(room)

static func building_dims(id: String) -> Vector3:
	if dims_cache.is_empty() and FileAccess.file_exists(BUILDINGS):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(BUILDINGS))
		if parsed is Dictionary:
			for entry in parsed.get("buildings",[]):
				var size: Array = entry.get("dimensions_m",[])
				if size.size()==3: dims_cache[str(entry.id)]={"dims":Vector3(size[0],size[1],size[2]),"name":str(entry.get("name",""))}
	if dims_cache.has(id): return dims_cache[id].dims
	var fallback: Array = ROOMS.get(id,{}).get("dims",[10,8,10])
	return Vector3(fallback[0],fallback[1],fallback[2])

static func size_of(kind: String) -> Vector3:
	var s: Array = CATALOG.get(kind,[1,1,1])
	return Vector3(s[0],s[1],s[2])

## Everything the studio needs for one building: building-level text plus a list
## of floors. Each floor is a self-contained dictionary (the studio walks one floor
## at a time): size, height, side-by-side rooms, doorways, windows, furniture and
## the stairs that link it to other floors.
static func spec(room: String) -> Dictionary:
	var id := building_for(room)
	if not ROOMS.has(id): id="10_red_house"
	var base: Dictionary = ROOMS[id]
	var plan: Array = PLANS[id]
	var building := {"room":room,"building":id,"theme":base.theme,"name":base.name,"kind":base.kind,"flavour":base.flavour,
		"public":not is_private(room),"outlook":OUTLOOK.get(id,"meadow"),"floors":[]}
	for index in plan.size():
		var p: Dictionary = plan[index]
		var w: float = p.w
		var d: float = p.d
		var h: float = p.h
		var theme_key: String = p.get("theme",base.theme)
		var rooms: Array = []
		var share_total := 0.0
		for r in p.rooms: share_total+=float(r[1])
		var x := -w*0.5
		for r in p.rooms:
			var width := w*float(r[1])/share_total
			var room_theme: String = r[2] if r.size()>2 else theme_key
			rooms.append({"name":r[0],"x0":x,"x1":x+width,"colors":THEMES[room_theme],"theme":room_theme})
			x+=width
		var doorways: Array = []
		for i in rooms.size()-1:
			var dz: float = p.get("door_z",d*0.08)
			doorways.append({"x":rooms[i].x1,"z0":dz-DOORWAY*0.5,"z1":dz+DOORWAY*0.5})
		var entry_room: int = p.get("entry",0)
		var floor_spec := {"room":room,"building":id,"theme":theme_key,"name":base.name,"kind":base.kind,"flavour":base.flavour,
			"public":building.public,"outlook":building.outlook,"floor":index,"floors":plan.size(),"label":p.get("label",""),
			"size":Vector2(w,d),"height":h,"shape":p.get("shape","rect"),"colors":THEMES[theme_key],"rooms":rooms,"doorways":doorways,
			"has_door":index==0,"door_x":(rooms[entry_room].x0+rooms[entry_room].x1)*0.5 if index==0 else 0.0,"balcony":p.get("balcony",false)}
		floor_spec["windows"]=windows(id,index,floor_spec)
		floor_spec["furniture"]=layout(id,index,floor_spec)
		building.floors.append(floor_spec)
	assign_beds(building)
	pair_stairs(building)
	return building

## Each stair arrives just off its counterpart on the other floor (the hatch's
## open side, a staircase's or spiral's foot, the front of a ladder).
static func pair_stairs(building: Dictionary) -> void:
	for index in building.floors.size():
		for entry in building.floors[index].furniture:
			if not entry.has("link"): continue
			var to := int(entry.link.to)
			for other in building.floors[to].furniture:
				if other.has("link") and int(other.link.to)==index:
					entry.link["arrive"]=stair_end(other,0.65)
					entry.link["counterpart"]=other.kind
					break

## A point on the floor just off a stair's walking end.
static func stair_end(entry: Dictionary, beyond: float) -> Vector3:
	var size: Vector3 = entry.get("size",size_of(str(entry.kind)))
	var front := Vector3(0,0,1).rotated(Vector3.UP,deg_to_rad(float(entry.get("yaw",0.0))))
	var at: Vector3 = entry.at
	var reach := size.z*0.5 if entry.kind!="ladder" else 0.15
	var point := at+front*(reach+beyond)
	point.y=0
	return point

## The visible part of a climb (or descent) from where the walker stands:
## onto the first step and up (or down into the hatch), as world points with
## height. The floor swap happens under a short fade near the end.
static func climb_path(record: Dictionary, from: Vector3) -> Array[Vector3]:
	var size: Vector3 = record.size
	var basis := Basis(Vector3.UP,float(record.yaw))
	var c: Vector3 = record.center
	var points: Array[Vector3] = [Vector3(from.x,0,from.z)]
	match str(record.kind):
		"staircase":
			var steps := maxi(8,int(size.y/0.24))
			var rise := size.y/steps
			var run := size.z/steps
			points.append(c+basis*Vector3(0,0,size.z*0.5+0.35))
			for i in int(steps*0.7):
				points.append(c+basis*Vector3(0,(i+1)*rise,size.z*0.5-(i+0.5)*run))
		"spiral_stair":
			var steps := 13
			var radius := size.x*0.3
			points.append(c+basis*Vector3(0,0,size.x*0.5+0.35))
			for i in int(steps*0.6):
				var a := PI*0.5+i*TAU*0.92/steps
				points.append(c+basis*Vector3(cos(a)*radius,0.2+i*(size.y-0.25)/steps+0.04,sin(a)*radius))
		"ladder":
			var foot := c+basis*Vector3(0,0,0.5)
			points.append(foot)
			for i in 5: points.append(foot+basis*Vector3(0,0.32*(i+1),-0.08))
		_:
			# Down through a hatch: to the open side, then step down into the hole.
			points.append(c+basis*Vector3(0,0,size.z*0.5+0.3))
			for i in 6: points.append(c+basis*Vector3(0,-0.24*(i+1),size.z*0.5-0.22*(i+1)))
	return points

## Stepping off a stair onto the arrival floor: from the stair's end to the arrival point.
static func arrival_path(counterpart: Dictionary, arrive: Vector3) -> Array[Vector3]:
	var size: Vector3 = counterpart.size
	var basis := Basis(Vector3.UP,float(counterpart.yaw))
	var c: Vector3 = counterpart.center
	var points: Array[Vector3] = []
	match str(counterpart.kind):
		"staircase":
			var steps := maxi(8,int(size.y/0.24))
			var rise := size.y/steps
			var run := size.z/steps
			for i in [3,2,1,0]: points.append(c+basis*Vector3(0,(i+1)*rise,size.z*0.5-(i+0.5)*run))
		"spiral_stair":
			var radius := size.x*0.3
			for i in [3,2,1,0]:
				var a: float = PI*0.5+i*TAU*0.92/13
				points.append(c+basis*Vector3(cos(a)*radius,0.2+i*(size.y-0.25)/13+0.04,sin(a)*radius))
		"ladder":
			var foot := c+basis*Vector3(0,0,0.5)
			for i in [3,2,1]: points.append(foot+basis*Vector3(0,0.32*i,-0.08))
			points.append(foot)
		_:
			for i in [3,2,1]: points.append(c+basis*Vector3(0,-0.24*i,size.z*0.5-0.22*i))
			points.append(c+basis*Vector3(0,0,size.z*0.5+0.1))
	points.append(arrive)
	return points

## Every resident sleeps in their own bed in their home building (read from
## Residents at runtime): a bed marked for someone goes to them, the rest in order.
static func assign_beds(building: Dictionary) -> void:
	if not building.public: return
	var owners: Array = Array(Residents.residents_of(str(building.building)))
	var beds: Array = []
	for f in building.floors:
		for entry in f.furniture:
			if entry.kind=="bed": beds.append(entry)
	for entry in beds:
		var hint := str(entry.get("owner_hint",""))
		if not hint.is_empty() and owners.has(hint):
			entry["owner"]=hint
			owners.erase(hint)
	for entry in beds:
		if entry.has("owner") or owners.is_empty(): continue
		entry["owner"]=owners.pop_front()
	building["unbedded"]=owners

## Index of the room (on this floor) that contains x.
static func room_at(f: Dictionary, x: float) -> int:
	var rooms: Array = f.rooms
	for i in rooms.size():
		if x<float(rooms[i].x1) or i==rooms.size()-1: return i
	return 0

## Walkable floor for the hero (the knee wall leaves only the doorway open at the front).
static func walk_limits(s: Dictionary) -> Dictionary:
	var size: Vector2 = s.size
	return {"x":size.x*0.5-0.42,"back":-size.y*0.5+0.42,"front":size.y*0.5-0.62,"door_front":size.y*0.5-0.12,"door_half":DOOR_HALF-0.25,"door_x":float(s.get("door_x",0.0))}

static func walkable(s: Dictionary, at: Vector3) -> bool:
	var limits := walk_limits(s)
	if absf(at.x)>limits.x or at.z<limits.back: return false
	var at_doorway: bool = s.get("has_door",true) and absf(at.x-float(limits.door_x))<limits.door_half
	var front: float = limits.door_front if at_doorway else limits.front
	if at.z>front: return false
	for door in s.get("doorways",[]):
		if absf(at.x-float(door.x))<PART*0.5+0.3 and (at.z<float(door.z0)+0.3 or at.z>float(door.z1)-0.3): return false
	if s.shape=="round":
		var radius: float = s.size.x*0.5
		var centre: float = -s.size.y*0.5+radius
		if at.z<centre and Vector2(at.x,at.z-centre).length()>radius-0.45: return false
	return true

static func spawn_point(s: Dictionary) -> Vector3:
	return Vector3(float(s.get("door_x",0.0)),0,s.size.y*0.5-1.05)

static func at_door(s: Dictionary, at: Vector3) -> bool:
	if not s.get("has_door",true): return false
	var limits := walk_limits(s)
	return absf(at.x-float(limits.door_x))<limits.door_half and at.z>=limits.door_front-0.03

static func near_door(s: Dictionary, at: Vector3) -> bool:
	if not s.get("has_door",true): return false
	return absf(at.x-float(s.get("door_x",0.0)))<DOOR_HALF+0.6 and at.z>s.size.y*0.5-0.95

# ---------------------------------------------------------------- layouts

static func it(kind: String, x: float, z: float, yaw := 0.0, extra := {}) -> Dictionary:
	var entry := {"kind":kind,"at":Vector3(x,0,z),"yaw":yaw}
	entry.merge(extra,true)
	return entry

## Against the back wall; mounted pieces hang at height y.
static func back(kind: String, x: float, f: Dictionary, y := 0.0, extra := {}) -> Dictionary:
	var entry := it(kind,x,-f.size.y*0.5+size_of(kind).z*0.5+(0.01 if kind in MOUNTED else 0.07),0.0,extra)
	entry.at.y=y
	entry["anchor"]="back"
	return entry

## Against the left (side -1) or right (side 1) wall of room i: an outer wall or a
## partition. The piece turns to face into the room.
static func wall(kind: String, f: Dictionary, i: int, side: int, z: float, y := 0.0, extra := {}) -> Dictionary:
	var rooms: Array = f.rooms
	var face: float
	if side<0: face=float(rooms[i].x0)+(PART*0.5 if i>0 else 0.0)
	else: face=float(rooms[i].x1)-(PART*0.5 if i<rooms.size()-1 else 0.0)
	var gap := 0.01 if kind in MOUNTED else 0.07
	var entry := it(kind,face-side*(size_of(kind).z*0.5+gap),z,-90.0*side,extra)
	entry.at.y=y
	entry["anchor"]="wall"
	entry["wall_x"]=face
	entry["wall_side"]=side
	return entry

## Stairs up (staircase, ladder, spiral) or the hatch down, linked to another floor.
static func link(entry: Dictionary, to: int, arrive: Vector2) -> Dictionary:
	entry["link"]={"to":to,"arrive":Vector3(arrive.x,0,arrive.y)}
	return entry

## A shop or workplace owner's own room upstairs: bed, wardrobe, desk and a few
## comforts, with the hatch back down beside the stairs.
static func owner_room(l: Array, f: Dictionary, arrive_below: Vector2, hatch_depth := 1.8, hatch_width := 1.0) -> void:
	var hw: float = f.size.x*0.5
	var hd: float = f.size.y*0.5
	l.append(link(it("stair_hatch",hw-0.35-hatch_width*0.5,-hd+0.15+hatch_depth*0.5,0.0,{"size":Vector3(hatch_width,0.95,hatch_depth)}),0,arrive_below))
	l.append(back("bed",-hw+0.85,f))
	l.append(back("side_table",-hw+2.05,f))
	l.append(back("wardrobe_closet",0.45,f))
	l.append(wall("desk",f,0,-1,hd-1.2))
	l.append(it("wooden_chair",-hw+1.25,hd-1.2,-90.0))
	l.append(it("armchair",0.5,hd-1.3,90.0))
	l.append(it("floor_lamp",hw-0.45,hd-1.75))
	l.append(it("potted_plant",hw-0.45,hd-0.55))
	l.append(back("picture_frame",-hw+2.05,f,1.85))
	l.append(it("rug",0.3,hd-1.4,0.0,{"size":Vector3(2.0,0.02,1.3)}))

static func layout(id: String, floor_index: int, f: Dictionary) -> Array:
	var w: float = f.size.x
	var d: float = f.size.y
	var h: float = f.height
	var hw := w*0.5
	var hd := d*0.5
	var r: Array[Vector2] = []
	for room in f.rooms: r.append(Vector2(room.x0,room.x1))
	var l: Array = []
	match "%s/%d" % [id,floor_index]:
		"10_red_house/0":
			# Fixed pieces hug the walls so the central [-4,4] square stays free to decorate.
			l.append(back("kitchen_counter",-3.55,f))
			l.append(back("cooking_stove",-2.2,f))
			l.append(wall("picture_frame",f,0,1,-0.7,1.95))
			l.append(back("wall_shelf",-3.55,f,1.85))
			l.append(back("wardrobe_closet",2.3,f))
			l.append(back("wall_clock",2.3,f,2.62))
			l.append(link(it("staircase",hw-0.78,-hd+1.4,0.0,{"size":Vector3(1.4,h,2.7),"variant":"left"}),1,Vector2.ZERO))
			l.append(it("floor_lamp",3.12,-hd+0.42))
			l.append(wall("bookshelf",f,0,1,0.9))
			l.append(wall("sofa",f,0,-1,0.5))
			l.append(wall("picture_frame",f,0,-1,2.6,1.95))
			l.append(it("coat_rack",-hw+0.4,hd-0.75))
			l.append(it("potted_plant",hw-0.42,hd-0.95))
			l.append(it("potted_plant",-hw+0.42,-1.2))
			l.append(it("rug",0,0.3,0.0,{"size":Vector3(3.6,0.02,2.6)}))
		"10_red_house/1":
			l.append(link(it("stair_hatch",hw-1.05,-hd+1.05,0.0,{"size":Vector3(1.5,0.95,1.8)}),0,Vector2.ZERO))
			l.append(back("bed",-2.55,f))
			l.append(back("side_table",-1.25,f))
			l.append(it("chest",-2.55,-0.8))
			l.append(back("bookshelf",0.75,f))
			l.append(back("wall_clock",0.75,f,2.2))
			l.append(wall("desk",f,0,-1,1.7))
			l.append(it("wooden_chair",-hw+1.25,1.7,-90.0))
			l.append(it("floor_lamp",hw-0.45,0.9))
			l.append(it("potted_plant",-hw+0.45,hd-0.62))
			l.append(it("rug",0.2,0.7,0.0,{"size":Vector3(2.6,0.02,1.8)}))
		"09_town_hall/0":
			# The fixed workbench keeps its old spot (placement already avoids it).
			l.append(it("workbench",-3.7,-3.1))
			l.append(back("tool_rack",-3.7,f,1.75))
			l.append(it("crate_stack",-hw+0.55,-hd+0.5))
			l.append(back("barrel",-1.95,f))
			l.append(back("bookshelf",1.35,f))
			l.append(back("wall_clock",1.35,f,2.62))
			l.append(back("banner",0.1,f,2.2))
			l.append(back("banner",2.6,f,2.2))
			l.append(link(it("staircase",hw-0.78,-hd+1.4,0.0,{"size":Vector3(1.4,h,2.7),"variant":"left"}),1,Vector2.ZERO))
			l.append(wall("notice_board",f,0,1,0.6,1.75))
			l.append(wall("crate_stack",f,0,-1,1.2))
			l.append(wall("barrel",f,0,-1,2.6))
			l.append(it("potted_plant",-hw+0.42,hd-0.95))
			l.append(it("potted_plant",hw-0.42,hd-0.95))
			l.append(it("rug",0.6,0.2,0.0,{"size":Vector3(3.4,0.02,2.4)}))
		"09_town_hall/1":
			l.append(link(it("stair_hatch",r[1].y-0.95,-hd+1.05,0.0,{"size":Vector3(1.5,0.95,1.8)}),0,Vector2.ZERO))
			for x in [r[0].x+0.75,r[0].x+2.05,r[0].x+3.35]: l.append(back("bookshelf",x,f))
			l.append(it("map_table",(r[0].x+r[0].y)*0.5,0.6))
			l.append(it("globe",r[0].x+0.55,2.3))
			l.append(wall("crate_stack",f,0,-1,0.2))
			l.append(it("chest",r[0].y-0.65,-hd+0.45))
			l.append(it("floor_lamp",r[0].y-0.45,2.7))
			l.append(back("desk",r[1].x+1.25,f))
			l.append(it("wooden_chair",r[1].x+1.25,-hd+1.2,180.0))
			l.append(wall("wall_clock",f,1,1,0.2,2.2))
			l.append(wall("notice_board",f,1,1,2.1,1.7))
			l.append(it("armchair",r[1].x+0.6,1.9,90.0))
			l.append(wall("wardrobe_closet",f,1,-1,-hd+0.9))
			l.append(it("potted_plant",r[1].y-0.45,hd-0.75))
		"01_cafe/0":
			var hall_x := (r[0].x+r[0].y)*0.5
			l.append(back("piano",r[0].x+0.85,f))
			l.append(back("cafe_counter",hall_x+0.45,f))
			l.append(back("menu_board",hall_x+0.45,f,2.35))
			for table in [Vector2(r[0].x+1.25,0.0),Vector2(hall_x+1.5,0.9),Vector2(r[0].x+1.25,2.35)]:
				l.append(it("round_cafe_table",table.x,table.y))
				l.append(it("wooden_chair",table.x-0.78,table.y,90.0,{"variant":"cafe","prop":"cafe_chair"}))
				l.append(it("wooden_chair",table.x+0.78,table.y,-90.0,{"variant":"cafe","prop":"cafe_chair"}))
			l.append(wall("wall_clock",f,0,-1,-1.9,2.25))
			l.append(it("potted_plant",r[0].y-0.45,hd-0.62))
			l.append(it("rug",hall_x,0.6,0.0,{"size":Vector3(1.6,0.02,1.2),"color":"b85a48"}))
			l.append(back("kitchen_counter",r[1].x+0.9,f))
			l.append(wall("cooking_stove",f,1,-1,-2.6))
			l.append(link(it("staircase",r[1].y-0.78,-hd+1.4,0.0,{"size":Vector3(1.4,h,2.7),"variant":"left"}),1,Vector2.ZERO))
			l.append(wall("display_shelf",f,1,1,0.35,0.0,{"variant":"jars"}))
			l.append(wall("wall_shelf",f,1,1,2.85,1.8))
			l.append(wall("flour_sacks",f,1,-1,2.3))
			l.append(it("barrel",r[1].x+1.9,2.85))
			l.append(it("basket",r[1].x+1.6,0.75))
		"02_timber_house/0":
			l.append(back("fireplace",0,f))
			l.append(back("bookshelf",-3.25,f))
			l.append(back("potted_plant",2.0,f))
			l.append(it("rug",0,-2.0,0.0,{"size":Vector3(3.0,0.02,2.0)}))
			l.append(it("sofa",0,-1.25,180.0))
			l.append(it("floor_lamp",1.45,-1.25))
			l.append(wall("kitchen_counter",f,0,-1,0.2))
			l.append(wall("cooking_stove",f,0,-1,-1.55))
			l.append(wall("wall_shelf",f,0,-1,0.2,1.75))
			l.append(it("dining_table",2.15,1.45,90.0))
			for z in [0.95,1.95]:
				l.append(it("wooden_chair",2.15-0.82,z,90.0))
				l.append(it("wooden_chair",2.15+0.82,z,-90.0))
			l.append(link(it("staircase",hw-0.78,-hd+1.4,0.0,{"size":Vector3(1.4,h,2.7),"variant":"left"}),1,Vector2.ZERO))
			l.append(wall("wall_clock",f,0,1,0.0,2.2))
			l.append(it("coat_rack",-hw+0.4,hd-0.75))
			l.append(it("potted_plant",hw-0.42,hd-0.95))
		"02_timber_house/1":
			l.append(link(it("stair_hatch",hw-1.05,-hd+1.05,0.0,{"size":Vector3(1.5,0.95,1.8)}),0,Vector2.ZERO))
			l.append(back("bed",-2.75,f))
			l.append(back("side_table",-1.55,f))
			l.append(back("bed",-0.35,f))
			l.append(it("chest",-2.75,-0.55))
			l.append(wall("wardrobe_closet",f,0,1,1.0))
			l.append(wall("armchair",f,0,-1,1.5))
			l.append(it("floor_lamp",-hw+0.42,hd-0.62))
			l.append(it("potted_plant",hw-0.42,hd-0.62))
			l.append(it("rug",-0.4,0.8,0.0,{"size":Vector3(2.4,0.02,1.6)}))
		"03_teal_cottage/0":
			var shop_x := (r[0].x+r[0].y)*0.5
			l.append(back("shop_counter",shop_x+0.6,f))
			l.append(back("shop_sign",shop_x+0.6,f,2.12))
			l.append(back("barrel",r[0].x+0.45,f))
			l.append(wall("display_shelf",f,0,-1,-1.25,0.0,{"variant":"seeds"}))
			l.append(wall("seedling_bench",f,0,-1,1.0))
			l.append(it("planter",shop_x+0.6,-0.4))
			l.append(it("potted_plant",r[0].y-0.42,hd-0.62))
			l.append(it("basket",r[0].x+1.35,2.4))
			l.append(back("crate_stack",r[1].x+0.6,f))
			l.append(back("barrel",r[1].y-0.45,f))
			l.append(wall("flour_sacks",f,1,1,0.25))
			l.append(link(wall("ladder",f,1,1,1.65,0.0,{"size":Vector3(0.6,h,0.3)}),1,Vector2.ZERO))
			l.append(back("wall_shelf",r[1].x+0.6,f,1.95))
			l.append(it("chest",r[1].x+0.85,2.55))
			l.append(it("basket",r[1].y-0.45,2.65))
		"04_windmill/0":
			l.append(it("millstone",0,-0.75))
			l.append(it("flour_sacks",-hw+0.85,-hd+0.6))
			l.append(link(back("ladder",-1.85,f,0.0,{"size":Vector3(0.6,h,0.3)}),1,Vector2.ZERO))
			l.append(it("crate_stack",hw-0.6,-hd+0.55))
			l.append(it("barrel",hw-0.45,0.25))
			l.append(wall("workbench",f,0,-1,0.9,0.0,{"variant":"mill"}))
			l.append(wall("flour_sacks",f,0,1,1.5))
			l.append(wall("wall_shelf",f,0,1,1.5,1.9))
			l.append(it("wooden_chair",-hw+1.3,0.9,-90.0))
			l.append(it("potted_plant",-hw+0.42,hd-0.62))
			l.append(back("wall_clock",-0.85,f,2.6))
		"04_windmill/1":
			l.append(link(it("stair_hatch",-2.75,-hd+0.75,0.0,{"size":Vector3(1.0,0.95,1.2)}),0,Vector2.ZERO))
			l.append(it("gear_wheel",-0.4,-hd+0.75,0.0,{"size":Vector3(2.0,2.6,0.7)}))
			l.append(wall("hoist",f,0,-1,0.9,0.0,{"size":Vector3(0.9,h,0.9)}))
			l.append(it("flour_sacks",-1.6,1.65))
			l.append(it("crate_stack",0.05,1.95))
			l.append(it("chest",-1.25,0.15))
			l.append(it("basket",-2.85,2.2))
			l.append(back("bed",r[1].x+0.95,f))
			l.append(back("side_table",r[1].y-0.4,f))
			l.append(back("picture_frame",r[1].y-0.4,f,1.8))
			l.append(it("chest",r[1].x+0.95,-0.3))
			l.append(wall("wardrobe_closet",f,1,1,1.4))
			l.append(wall("wall_clock",f,1,-1,2.0,2.0))
			l.append(it("potted_plant",r[1].x+0.45,hd-0.55))
			l.append(it("floor_lamp",r[1].y-0.45,2.35))
		"05_observatory/0":
			l.append(link(it("spiral_stair",r[0].x+1.15,-hd+1.25,0.0,{"size":Vector3(2.1,h,2.1)}),1,Vector2.ZERO))
			l.append(back("bookshelf",-1.45,f))
			l.append(back("desk",r[0].y-0.95,f))
			l.append(it("wooden_chair",r[0].y-0.95,-hd+1.2,180.0))
			l.append(it("globe",r[0].x+0.55,0.2))
			l.append(wall("star_chart",f,0,-1,1.6,2.05))
			l.append(wall("armchair",f,0,-1,1.6))
			l.append(it("map_table",-1.2,1.0))
			l.append(it("floor_lamp",r[0].x+0.45,hd-0.62))
			l.append(wall("wall_clock",f,0,1,2.4,2.2))
			l.append(it("potted_plant",r[0].y-0.45,hd-0.62))
			l.append(it("rug",-1.2,0.9,0.0,{"size":Vector3(2.6,0.02,1.8),"color":"3c6a5a"}))
			l.append(back("bed",r[1].x+0.95,f))
			l.append(back("side_table",r[1].y-0.4,f))
			l.append(back("picture_frame",r[1].y-0.4,f,1.9))
			l.append(it("chest",r[1].x+0.95,-1.3))
			l.append(wall("wardrobe_closet",f,1,1,1.6))
			l.append(wall("star_chart",f,1,-1,2.3,2.0))
			l.append(it("potted_plant",r[1].x+0.45,hd-0.62))
			l.append(it("floor_lamp",r[1].y-0.45,0.3))
		"05_observatory/1":
			l.append(it("telescope",0,-0.9))
			l.append(it("rug",0,-0.9,0.0,{"size":Vector3(3.2,0.02,3.2),"color":"2f3c6e","variant":"round"}))
			l.append(link(it("stair_hatch",2.0,-1.6,0.0,{"size":Vector3(1.3,0.95,1.4)}),0,Vector2.ZERO))
			l.append(wall("star_chart",f,0,-1,2.0,2.2))
			l.append(wall("desk",f,0,1,2.2))
			l.append(it("wooden_chair",hw-1.35,2.2,90.0))
			l.append(it("globe",-hw+0.75,1.0))
			l.append(it("armchair",-1.2,2.4,0.0))
			l.append(it("floor_lamp",hw-0.5,0.9))
		"06_orange_cottage/0":
			var kitchen_x := (r[0].x+r[0].y)*0.5
			l.append(back("kitchen_counter",r[0].x+1.0,f))
			l.append(back("cooking_stove",r[0].x+2.45,f))
			l.append(back("wall_shelf",r[0].x+2.45,f,1.95))
			l.append(wall("display_shelf",f,0,-1,-0.6,0.0,{"variant":"bread"}))
			l.append(it("dining_table",kitchen_x+0.35,0.6))
			for x in [kitchen_x-0.1,kitchen_x+0.8]:
				l.append(it("wooden_chair",x,0.6-0.72))
				l.append(it("wooden_chair",x,0.6+0.72,180.0))
			l.append(wall("flour_sacks",f,0,-1,1.75))
			l.append(back("bed",r[1].x+0.88,f))
			l.append(back("bed",r[1].y-0.65,f,0.0,{"size":Vector3(1.1,0.9,1.7),"primitive":true}))
			l.append(back("picture_frame",r[1].x+0.88,f,1.9))
			l.append(it("chest",r[1].x+0.88,-0.75))
			l.append(wall("wardrobe_closet",f,1,1,1.4))
			l.append(wall("wall_clock",f,1,-1,1.9,2.0))
			l.append(it("potted_plant",r[1].x+0.5,hd-0.62))
			l.append(it("rug",(r[1].x+r[1].y)*0.5,0.7,0.0,{"size":Vector3(1.8,0.02,1.2)}))
		"07_greenhouse/0":
			l.append(back("seedling_bench",-3.0,f))
			l.append(back("seedling_bench",0.2,f))
			l.append(wall("seedling_bench",f,0,-1,0.0))
			l.append(it("soil_bed",-1.4,-0.9))
			l.append(it("bench",-3.2,2.3))
			l.append(it("barrel",r[0].y-0.5,hd-0.95))
			for p in [Vector2(-hw+0.45,-hd+0.45),Vector2(r[0].y-0.45,-hd+0.45),Vector2(-hw+0.45,hd-0.95)]:
				l.append(it("potted_plant",p.x,p.y))
			l.append(it("planter",r[0].y-0.5,-1.0))
			l.append(it("basket",0.0,1.2))
			l.append(it("window",(r[0].x+r[0].y)*0.5,-hd+0.02,0.0,{"at_y":1.9}))
			l.append(back("bed",r[1].x+1.0,f))
			l.append(back("side_table",r[1].y-0.4,f))
			l.append(back("picture_frame",r[1].y-0.4,f,1.9))
			l.append(it("chest",r[1].x+1.0,-1.75))
			l.append(wall("wardrobe_closet",f,1,1,1.6))
			l.append(wall("tool_rack",f,1,-1,2.6,1.6))
			l.append(it("potted_plant",r[1].x+0.45,hd-0.62))
			l.append(it("floor_lamp",r[1].y-0.45,0.4))
		"11_purple_house/0":
			l.append(back("piano",r[0].x+0.9,f))
			l.append(back("wall_clock",r[0].x+0.9,f,2.2))
			l.append(it("floor_lamp",r[0].x+2.0,-hd+0.42))
			l.append(link(it("staircase",r[0].y-0.83,-hd+1.4,0.0,{"size":Vector3(1.4,h,2.7),"variant":"left"}),1,Vector2.ZERO))
			l.append(wall("sofa",f,0,-1,0.8))
			l.append(it("round_cafe_table",r[0].x+1.95,0.8,0.0,{"variant":"tea"}))
			l.append(it("armchair",r[0].x+3.2,0.8,-90.0))
			l.append(it("rug",r[0].x+2.3,0.7,0.0,{"size":Vector3(2.8,0.02,2.0)}))
			l.append(wall("picture_frame",f,0,-1,-1.9,1.95))
			l.append(it("potted_plant",r[0].x+0.42,hd-0.95))
			l.append(it("potted_plant",r[0].y-0.42,hd-0.95))
			l.append(back("bookshelf",r[1].x+0.75,f))
			l.append(back("bookshelf",r[1].x+2.0,f))
			l.append(wall("desk",f,1,1,0.9))
			l.append(it("wooden_chair",r[1].y-1.2,0.9,90.0))
			l.append(it("globe",r[1].x+0.6,2.6))
			l.append(it("floor_lamp",r[1].y-0.45,hd-0.62))
			l.append(it("potted_plant",r[1].x+0.45,-0.6))
		"12_blue_house/0":
			l.append(back("bed",r[0].x+0.85,f))
			l.append(back("bed",r[0].x+2.45,f))
			l.append(wall("picture_frame",f,0,1,2.3,1.9))
			l.append(wall("wardrobe_closet",f,0,-1,1.3))
			l.append(wall("wall_clock",f,0,-1,2.45,2.0))
			l.append(it("floor_lamp",r[0].y-0.38,-hd+0.42))
			l.append(it("rug",(r[0].x+r[0].y)*0.5,0.4,0.0,{"size":Vector3(2.4,0.02,1.6)}))
			l.append(it("round_cafe_table",r[0].y-0.85,1.75))
			l.append(it("wooden_chair",r[0].y-1.6,1.75,90.0))
			l.append(it("potted_plant",r[0].x+0.42,hd-0.62))
			l.append(back("bathtub",(r[1].x+r[1].y)*0.5+0.2,f))
			l.append(back("wall_shelf",r[1].x+0.55,f,1.75))
			l.append(wall("washstand",f,1,1,0.3))
			l.append(wall("side_table",f,1,-1,2.3))
			l.append(it("coat_rack",r[1].y-0.4,hd-0.65))
			l.append(it("basket",r[1].x+1.35,2.6))
			l.append(it("potted_plant",r[1].y-0.42,-0.75))
			l.append(it("rug",(r[1].x+r[1].y)*0.5,0.9,0.0,{"size":Vector3(1.2,0.02,0.8),"color":"7fb0d0"}))
		"13_shop/0":
			l.append(back("shop_counter",r[0].x+1.6,f))
			l.append(back("shop_sign",r[0].x+1.6,f,2.08))
			l.append(back("display_shelf",r[0].y-0.85,f,0.0,{"variant":"goods"}))
			l.append(wall("display_shelf",f,0,-1,0.3,0.0,{"variant":"jars"}))
			l.append(it("barrel",r[0].x+0.45,1.75))
			l.append(it("crate_stack",r[0].x+0.55,2.75))
			l.append(it("planter",r[0].y-0.45,hd-0.75))
			l.append(it("basket",r[0].y-0.6,0.9))
			l.append(back("crate_stack",r[1].x+0.7,f))
			l.append(back("barrel",r[1].y-0.45,f))
			l.append(wall("flour_sacks",f,1,1,0.5))
			l.append(link(wall("ladder",f,1,1,1.75,0.0,{"size":Vector3(0.6,h,0.3)}),1,Vector2.ZERO))
			l.append(wall("wall_shelf",f,1,-1,1.7,1.8))
			l.append(it("chest",r[1].x+0.85,2.5))
			l.append(it("basket",r[1].y-0.45,2.7))
		"16_blue_cottage/0":
			var living_x := (r[0].x+r[0].y)*0.5
			l.append(back("fireplace",living_x,f))
			l.append(back("bookshelf",r[0].x+0.6,f))
			l.append(it("floor_lamp",r[0].y-0.45,-hd+0.42))
			l.append(it("rug",living_x,-1.5,0.0,{"size":Vector3(2.4,0.02,1.6)}))
			l.append(it("armchair",living_x-1.4,-1.15,90.0))
			l.append(it("armchair",living_x+1.4,-1.15,-90.0))
			l.append(wall("picture_frame",f,0,-1,2.4,1.9))
			l.append(wall("wall_clock",f,0,1,2.1,2.05))
			l.append(it("potted_plant",r[0].x+0.42,hd-0.95))
			l.append(back("bed",r[1].x+0.85,f))
			l.append(back("bed",r[1].y-0.8,f))
			l.append(wall("picture_frame",f,1,-1,2.2,1.9))
			l.append(it("chest",r[1].x+0.85,-1.3))
			l.append(wall("wardrobe_closet",f,1,1,1.35))
			l.append(it("potted_plant",r[1].x+0.45,hd-0.62))
			l.append(it("floor_lamp",r[1].y-0.45,hd-0.62))
		"17_lighthouse/0":
			l.append(link(it("spiral_stair",-1.55,-0.6,90.0,{"size":Vector3(2.1,h,2.1)}),1,Vector2.ZERO))
			l.append(it("map_table",1.95,0.85,-90.0))
			l.append(it("wooden_chair",1.2,0.85,90.0))
			l.append(it("barrel",2.1,-0.95))
			l.append(it("chest",0.75,-1.95))
			l.append(it("crate_stack",-hw+0.6,1.9))
			l.append(wall("ship_wheel",f,0,1,2.2,1.7))
			l.append(it("coat_rack",1.45,hd-0.6))
			l.append(it("basket",hw-0.45,hd-0.55))
		"17_lighthouse/1":
			l.append(link(it("spiral_stair",-1.55,-0.6,90.0,{"size":Vector3(2.1,h,2.1)}),2,Vector2.ZERO))
			l.append(link(it("stair_hatch",1.8,-1.05,0.0,{"size":Vector3(1.2,0.95,1.2)}),0,Vector2.ZERO))
			l.append(wall("bed",f,0,1,1.75))
			l.append(wall("bed",f,0,-1,1.75))
			l.append(it("desk",0.75,-2.2))
			l.append(it("wooden_chair",0.75,-1.45,180.0))
			l.append(it("cooking_stove",-0.6,-2.25))
			l.append(wall("wall_clock",f,0,1,0.6,2.3))
			l.append(it("potted_plant",0.0,hd-0.5))
			l.append(it("rug",0.0,1.4,0.0,{"size":Vector3(1.6,0.02,1.2)}))
		"17_lighthouse/2":
			l.append(it("lighthouse_lens",0,-0.55))
			l.append(link(it("stair_hatch",-1.75,0.6,0.0,{"size":Vector3(1.2,0.95,1.2)}),1,Vector2.ZERO))
			l.append(it("telescope",1.85,0.75,0.0,{"size":Vector3(0.9,1.6,0.9)}))
			l.append(it("wooden_chair",0.9,1.75,180.0))
		"01_cafe/1":
			owner_room(l,f,Vector2.ZERO,1.8,1.5)
		"03_teal_cottage/1":
			owner_room(l,f,Vector2(3.75-0.85,1.65),1.2)
		"11_purple_house/1":
			l.append(link(it("stair_hatch",r[0].y-0.88,-hd+1.05,0.0,{"size":Vector3(1.5,0.95,1.8)}),0,Vector2.ZERO))
			l.append(back("bed",r[0].x+0.8,f))
			l.append(back("bed",r[0].x+2.35,f))
			l.append(it("chest",r[0].x+0.8,-0.6))
			l.append(wall("wardrobe_closet",f,0,-1,1.4))
			l.append(wall("wall_clock",f,0,1,2.2,2.0))
			l.append(it("floor_lamp",r[0].y-0.5,2.6))
			l.append(it("potted_plant",r[0].x+1.9,hd-0.55))
			l.append(it("rug",(r[0].x+r[0].y)*0.5,0.7,0.0,{"size":Vector3(2.2,0.02,1.4)}))
			l.append(back("bed",r[1].x+1.0,f,0.0,{"owner_hint":"sora"}))
			l.append(back("side_table",r[1].y-0.45,f))
			l.append(back("picture_frame",r[1].y-0.45,f,1.9))
			l.append(wall("desk",f,1,1,1.2))
			l.append(it("wooden_chair",r[1].y-1.15,1.2,90.0))
			l.append(it("coat_rack",r[1].x+0.4,hd-0.5))
			l.append(it("floor_lamp",r[1].y-0.45,-0.45))
			l.append(it("potted_plant",r[1].x+1.6,hd-0.55))
		"13_shop/1":
			owner_room(l,f,Vector2(3.5-0.85,1.75),1.2)
	return l

## Windows per floor: [wall, position, width, style]. "back" runs along x, "left"
## and "right" are the outer side walls (position = z), "arc" the round wall (degrees).
static func windows(id: String, floor_index: int, f: Dictionary) -> Array:
	var w: float = f.size.x
	var d: float = f.size.y
	var h: float = f.height
	var r: Array[Vector2] = []
	for room in f.rooms: r.append(Vector2(room.x0,room.x1))
	var sill := 1.05 if h<3.5 else 1.25
	var list: Array = []
	match "%s/%d" % [id,floor_index]:
		"10_red_house/0": list=[["back",-1.05,1.2],["back",0.65,1.0],["left",-2.4],["right",2.6]]
		"10_red_house/1": list=[["back",-0.45,0.9,"round"],["left",-1.0],["right",2.1,1.0]]
		"09_town_hall/0": list=[["back",-1.95,1.2],["back",3.55,0.8],["left",-1.4],["right",2.4]]
		"09_town_hall/1": list=[["left",-1.2],["left",1.2],["back",r[1].x+1.25,1.1],["right",-1.0,1.0]]
		"01_cafe/0": list=[["back",r[0].x+0.85],["left",0.6,1.6],["back",r[1].x+0.95,1.1],["right",1.55,1.0]]
		"02_timber_house/0": list=[["back",-1.6,1.0],["back",2.4,1.0],["left",2.3],["right",1.9,1.0]]
		"02_timber_house/1": list=[["back",-1.55,0.7,"round"],["left",-0.4],["right",-0.6,1.0]]
		"03_teal_cottage/0": list=[["back",r[0].x+1.75,0.85],["left",-0.1,0.9],["right",-1.4,0.9]]
		"04_windmill/0": list=[["back",1.55,0.9,"round"],["left",-0.8,0.9,"round"],["right",-1.0,0.9,"round"]]
		"04_windmill/1": list=[["back",-2.75,0.8,"round"],["left",-1.0,0.8,"round"],["right",0.0,0.8,"round"]]
		"05_observatory/0": list=[["back",r[1].x+0.95,0.9],["left",-0.6,1.0],["right",0.3,0.8]]
		"05_observatory/1": list=[["arc",35.0,1.0],["arc",90.0,1.3],["arc",145.0,1.0]]
		"06_orange_cottage/0": list=[["back",r[0].x+3.75,0.9],["left",1.0,1.0],["right",-0.6,1.0]]
		"11_purple_house/0": list=[["back",r[0].x+2.55,1.2],["left",2.6,1.0],["right",-1.4,1.0]]
		"12_blue_house/0": list=[["left",-1.0],["back",(r[1].x+r[1].y)*0.5+0.2,0.7,"round"],["right",2.0,1.0]]
		"13_shop/0": list=[["left",-1.7,1.0],["back",r[1].x+0.7,0.9],["right",-0.9,0.9]]
		"16_blue_cottage/0": list=[["left",0.4,1.2],["back",r[0].y-1.1,0.8],["right",-0.5,1.0]]
		"01_cafe/1": list=[["back",-0.75,0.8,"round"],["left",-1.3,1.0],["right",0.2,0.9]]
		"03_teal_cottage/1": list=[["back",-0.75,0.8,"round"],["left",-1.2,0.9],["right",0.3,0.8]]
		"13_shop/1": list=[["back",-0.75,0.8,"round"],["left",-1.2,0.9],["right",0.3,0.8]]
		"07_greenhouse/0": list=[["right",0.0,0.9]]
		"11_purple_house/1": list=[["left",-0.4,1.0],["right",-1.2,0.9]]
		"17_lighthouse/0": list=[["arc",30.0],["arc",90.0],["arc",150.0]]
		"17_lighthouse/1": list=[["arc",32.0]]
		"17_lighthouse/2": list=[["arc",15.0],["arc",50.0],["arc",90.0],["arc",130.0],["arc",165.0]]
	var result: Array = []
	for entry in list:
		var width: float = entry[2] if entry.size()>2 else 1.4
		var style: String = entry[3] if entry.size()>3 else "square"
		if f.shape=="round":
			style="round"
			width=float(entry[2]) if entry.size()>2 else (1.1 if floor_index==2 else 0.85)
		result.append({"wall":entry[0],"u":float(entry[1]),"width":width,"height":width*1.05 if style=="round" else 1.35,"y":sill+0.72 if style!="round" else sill+0.95,"style":style})
	return result

# ---------------------------------------------------------------- shell

static func col(theme: Dictionary, key: String, fallback := "888888") -> Color:
	var value := str(theme.get(key,""))
	return Color(value if not value.is_empty() else fallback)

## Builds one floor under root and returns its furniture and window records.
static func build(root: Node3D, s: Dictionary) -> Array:
	var shell := Node3D.new()
	shell.name="InteriorShell"
	root.add_child(shell)
	var records: Array = build_shell(shell,s)
	var props := Node3D.new()
	props.name="InteriorFurniture"
	root.add_child(props)
	var index := 0
	for entry in s.furniture:
		index+=1
		if entry.kind=="window":
			records.append({"kind":"window","node":props,"center":Vector3(entry.at.x,0,entry.at.z),"yaw":0.0,"mounted":true,"solid":false,
				"interactive":true,"glb":false,"size":Vector3(2.0,0.2,0.1),"half":Vector2(1.0,0.05),"world_half":Vector2(1.0,0.05),"top":float(entry.get("at_y",1.9))})
			continue
		records.append(place(props,entry,s,index))
	return records

static func build_shell(root: Node3D, s: Dictionary) -> Array:
	var t: Dictionary = s.colors
	var w: float = s.size.x
	var d: float = s.size.y
	var h: float = s.height
	var hw := w*0.5
	var hd := d*0.5
	var cut := col(t,"cut")
	var trim := col(t,"trim")
	# Raised base: its cut front edge reads like a dollhouse section.
	Art.box(root,Vector3(0,-0.3,0.1),Vector3(w+2*WALL+0.3,0.56,d+WALL+0.5),cut)
	for room in s.rooms:
		var rt: Dictionary = room.colors
		var floor_node := Art.box(root,Vector3((room.x0+room.x1)*0.5,-0.02,0),Vector3(room.x1-room.x0,0.08,d),Color.WHITE)
		floor_node.name="Floor"
		floor_node.material_override=surface(str(rt.floor),col(rt,"floor_a"),col(rt,"floor_b"),2.0)
	Art.box(root,Vector3(0,-0.005,hd+0.06),Vector3(w+2*WALL,0.06,0.14),trim)
	if s.shape=="round":
		round_walls(root,s,wall_material(t))
	else:
		var rooms: Array = s.rooms
		for i in rooms.size():
			var room: Dictionary = rooms[i]
			var rs := s.duplicate()
			rs["colors"]=room.colors
			var length: float = room.x1-room.x0
			var extra_left := WALL if i==0 else 0.0
			var extra_right := WALL if i==rooms.size()-1 else 0.0
			var part := {"inner":Vector3(0,0,1),"len":length,"face":-hd,"cx":(room.x0+room.x1)*0.5}
			var wall_node := Art.box(root,Vector3((room.x0-extra_left+room.x1+extra_right)*0.5,h*0.5,-hd-WALL*0.5),Vector3(length+extra_left+extra_right,h,WALL),Color.WHITE)
			wall_node.name="Wall"
			wall_node.material_override=wall_material(room.colors)
			if str(room.colors.wall_tex)=="glass": wall_node.visible=false
			wall_trim(root,part,rs)
		for side in [-1,1]:
			var room: Dictionary = rooms[0] if side<0 else rooms[rooms.size()-1]
			var rs := s.duplicate()
			rs["colors"]=room.colors
			var part := {"inner":Vector3(-side,0,0),"len":d,"face":side*hw,"cz":0.0}
			var wall_node := Art.box(root,Vector3(side*(hw+WALL*0.5),h*0.5,0),Vector3(WALL,h,d),Color.WHITE)
			wall_node.name="Wall"
			wall_node.material_override=wall_material(room.colors)
			if str(room.colors.wall_tex)=="glass": wall_node.visible=false
			wall_trim(root,part,rs)
			Art.box(root,Vector3(side*(hw+WALL*0.5),h*0.5,hd+0.012),Vector3(WALL+0.04,h+0.06,0.03),cut)
		for door in s.doorways: partition(root,s,door)
		if str(t.wall_tex)=="glass": glass_walls(root,s)
		if t.get("beams",false): beams(root,s)
	front(root,s)
	var records: Array = []
	for window in s.windows: records.append(add_window(root,s,window))
	lights(root,s)
	return records

## A full-height partition between two rooms with a framed doorway.
static func partition(root: Node3D, s: Dictionary, door: Dictionary) -> void:
	var d: float = s.size.y
	var h: float = s.height
	var x: float = door.x
	var z0: float = door.z0
	var z1: float = door.z1
	var room := room_at(s,x-0.1)
	var t: Dictionary = s.rooms[room].colors
	var other: Dictionary = s.rooms[mini(room+1,s.rooms.size()-1)].colors
	var mat := wall_material(t)
	for span in [[-d*0.5,z0],[z1,d*0.5]]:
		var a: float = span[0]
		var b: float = span[1]
		var piece := Art.box(root,Vector3(x,h*0.5,(a+b)*0.5),Vector3(PART,h,b-a),Color.WHITE)
		piece.material_override=mat
		for sgn in [-1,1]:
			var colors: Dictionary = t if sgn<0 else other
			Art.box(root,Vector3(x+sgn*(PART*0.5+0.03),0.08,(a+b)*0.5),Vector3(0.06,0.16,b-a),col(colors,"trim"))
			if not str(colors.get("wainscot","")).is_empty() and str(colors.wall_tex)!="glass":
				var panel := Art.box(root,Vector3(x+sgn*(PART*0.5+0.02),0.5,(a+b)*0.5),Vector3(0.04,1.0,b-a),Color.WHITE)
				panel.material_override=surface("panels",col(colors,"wainscot"),col(colors,"wainscot").darkened(0.12),2.0)
				Art.box(root,Vector3(x+sgn*(PART*0.5+0.035),1.03,(a+b)*0.5),Vector3(0.07,0.07,b-a),col(colors,"trim"))
		Art.box(root,Vector3(x,h+0.035,(a+b)*0.5),Vector3(PART+0.05,0.07,b-a),col(t,"cut"))
	# Door frame and lintel.
	var frame := col(t,"trim")
	var top := minf(2.3,h-0.35)
	for z in [z0,z1]: Art.box(root,Vector3(x,top*0.5,z),Vector3(PART+0.1,top,0.1),frame)
	var lintel := Art.box(root,Vector3(x,top+(h-top)*0.5,(z0+z1)*0.5),Vector3(PART,h-top,z1-z0),Color.WHITE)
	lintel.material_override=mat
	Art.box(root,Vector3(x,top,(z0+z1)*0.5),Vector3(PART+0.12,0.1,z1-z0+0.2),frame)
	Art.box(root,Vector3(x,h+0.035,(z0+z1)*0.5),Vector3(PART+0.05,0.07,z1-z0),col(t,"cut"))
	Art.box(root,Vector3(x,0.012,(z0+z1)*0.5),Vector3(PART+0.2,0.03,z1-z0),col(t,"floor_a").lightened(0.1))
	Art.box(root,Vector3(x,h*0.5,d*0.5+0.012),Vector3(PART+0.04,h+0.06,0.03),col(t,"cut"))

static func wall_material(t: Dictionary) -> StandardMaterial3D:
	var style := str(t.wall_tex)
	var base := col(t,"wall")
	match style:
		"logs": return surface("logs",base,base.darkened(0.18),2.1)
		"stripes": return surface("stripes",base,col(t,"stripe"),2.0)
		"stars":
			# Stars are painted into the albedo; an emission texture is not applied
			# through triplanar mapping on the Compatibility renderer.
			return surface("stars",base,base.lightened(0.6),2.5)
		"tiles": return surface("tiles",base,col(t,"stripe",t.wall),1.2)
	return surface("plaster",base,base.darkened(0.05),2.0)

## Wainscot, chair rail, baseboard and a dark cut cap on top of one wall.
static func wall_trim(root: Node3D, part: Dictionary, s: Dictionary) -> void:
	var t: Dictionary = s.colors
	var h: float = s.height
	var cut := col(t,"cut")
	var trim := col(t,"trim")
	var glass := str(t.wall_tex)=="glass"
	if not str(t.get("wainscot","")).is_empty():
		var wainscot_height := 1.0 if not glass else 0.7
		var panel := wall_strip(root,part,wainscot_height,wainscot_height*0.5,0.05,col(t,"wainscot"))
		panel.material_override=surface("panels",col(t,"wainscot"),col(t,"wainscot").darkened(0.12),2.0)
		wall_strip(root,part,0.07,wainscot_height+0.03,0.09,trim)
	wall_strip(root,part,0.16,0.08,0.07,trim)
	# Cut cap along the top of the wall.
	wall_strip(root,part,0.07,h+0.035,WALL+0.05,cut,0.0,true)

## A strip lying against the inner face of a wall (or centred on it when on_wall).
static func wall_strip(root: Node3D, part: Dictionary, height: float, y: float, depth: float, color: Color, extra := 0.0, on_wall := false) -> MeshInstance3D:
	var inner: Vector3 = part.inner
	var face: float = part.face
	var length: float = part.len
	var offset := -WALL*0.5 if on_wall else depth*0.5
	if absf(inner.z)>0.5:
		return Art.box(root,Vector3(float(part.get("cx",0.0)),y,face+inner.z*offset),Vector3(length+extra,height,depth),color)
	return Art.box(root,Vector3(face+inner.x*offset,y,float(part.get("cz",0.0))),Vector3(depth,height,length+extra),color)

static func beams(root: Node3D, s: Dictionary) -> void:
	var w: float = s.size.x
	var d: float = s.size.y
	var h: float = s.height
	var wood := col(s.colors,"trim")
	var count := int(w/2.6)+1
	for i in count+1:
		var x := -w*0.5+0.12+i*(w-0.24)/count
		Art.box(root,Vector3(x,h*0.5,-d*0.5+0.09),Vector3(0.2,h,0.16),wood)
	for z_index in int(d/2.6)+1:
		var z := -d*0.5+2.6*(z_index+1)
		if z>d*0.5-0.4: break
		for x in [-1,1]: Art.box(root,Vector3(x*(w*0.5-0.09),h*0.5,z),Vector3(0.16,h,0.2),wood)
	Art.box(root,Vector3(0,h-0.32,-d*0.5+0.12),Vector3(w,0.24,0.2),wood)
	for x in [-1,1]: Art.box(root,Vector3(x*(w*0.5-0.12),h-0.32,0),Vector3(0.2,0.24,d),wood)

static func glass_walls(root: Node3D, s: Dictionary) -> void:
	var d: float = s.size.y
	var h: float = s.height
	var frame := col(s.colors,"trim")
	# Glass covers the glass rooms only (a potting room keeps solid walls).
	var x0: float = s.size.x*0.5
	var x1: float = -s.size.x*0.5
	for room in s.rooms:
		if str(room.colors.wall_tex)=="glass":
			x0=minf(x0,float(room.x0));x1=maxf(x1,float(room.x1))
	var w := x1-x0
	var shift := (x0+x1)*0.5
	var glass := StandardMaterial3D.new()
	glass.albedo_color=Color("d9f0ea",0.22)
	glass.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	glass.roughness=0.1
	glass.metallic_specular=0.8
	var walls := [[Vector3(shift,0,-d*0.5),Vector3(1,0,0),w]]
	if is_equal_approx(x0,-s.size.x*0.5): walls.append([Vector3(x0,0,0),Vector3(0,0,1),d])
	if is_equal_approx(x1,s.size.x*0.5): walls.append([Vector3(x1,0,0),Vector3(0,0,1),d])
	for entry in walls:
		var origin: Vector3 = entry[0]
		var along: Vector3 = entry[1]
		var length: float = entry[2]
		var outward := Vector3(0,0,-1) if along.x>0.5 else Vector3(signf(origin.x),0,0)
		var pane := Art.box(root,origin+Vector3(0,0.7+(h-0.7)*0.5,0),Vector3(length,h-0.7,0.03) if along.x>0.5 else Vector3(0.03,h-0.7,length),Color.WHITE)
		pane.material_override=glass
		pane.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		# The garden outside the glass follows the clock like any other window view.
		var view := MeshInstance3D.new()
		var quad := QuadMesh.new()
		var view_len := length+3.2 if along.x>0.5 else length+1.6
		quad.size=Vector2(view_len,h+0.6)
		view.mesh=quad
		view.material_override=view_material(str(s.outlook) if str(s.outlook)!="meadow" else "garden",false,0.0)
		view.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(view)
		if along.x>0.5: view.position=origin+outward*1.6+Vector3(0,h*0.5+0.2,0)
		else:
			view.position=Vector3(origin.x+outward.x*1.6,h*0.5+0.2,-0.8)
			view.rotation.y=-PI*0.5*signf(origin.x)
		view.add_to_group("window_view")
		var mullions := int(length/1.25)
		for i in mullions+1:
			var offset := -length*0.5+i*length/mullions
			Art.box(root,origin+along*offset+Vector3(0,h*0.5,0),Vector3(0.07,h,0.09) if along.x>0.5 else Vector3(0.09,h,0.07),frame)
		for y in [0.7,1.9,h-0.05]:
			Art.box(root,origin+Vector3(0,y,0),Vector3(length,0.07,0.1) if along.x>0.5 else Vector3(0.1,0.07,length),frame)
		var rng := RandomNumberGenerator.new()
		rng.seed=int(length*100)+int(origin.x*10)
		for i in int(length/0.9):
			var p := origin+along*(-length*0.5+0.4+i*0.9+rng.randf_range(-0.2,0.2))+outward*rng.randf_range(0.45,0.8)
			Art.sphere(root,p+Vector3(0,rng.randf_range(0.3,0.6),0),Vector3(1.0,rng.randf_range(0.8,1.3),0.8),Color("6f9e5a").lightened(rng.randf_range(0,0.15)))

static func round_walls(root: Node3D, s: Dictionary, wall_mat: Material) -> void:
	var t: Dictionary = s.colors
	var w: float = s.size.x
	var d: float = s.size.y
	var h: float = s.height
	var radius := w*0.5
	var centre := -d*0.5+radius
	var segments := 12
	var step := PI/segments
	var cut := col(t,"cut")
	var trim := col(t,"trim")
	var band := col(t,"wainscot")
	for i in segments:
		var a := step*(i+0.5)
		var chord := 2*(radius+WALL)*sin(step*0.5)+0.06
		var dir := Vector3(cos(a),0,-sin(a))
		var at := Vector3(0,0,centre)+dir*(radius+WALL*0.5)
		var wall_node := Art.box(root,Vector3(at.x,h*0.5,at.z),Vector3(chord,h,WALL),Color.WHITE)
		wall_node.material_override=wall_mat
		wall_node.rotation.y=a+PI*0.5
		var inner_at := Vector3(0,0,centre)+dir*(radius-0.02)
		var inner_chord := 2*radius*sin(step*0.5)+0.03
		for layer in [[0.08,0.16,0.07,trim],[0.5,1.0,0.04,band],[1.03,0.07,0.08,trim]]:
			var piece := Art.box(root,Vector3(inner_at.x,layer[0],inner_at.z),Vector3(inner_chord,layer[1],layer[2]),layer[3])
			piece.rotation.y=a+PI*0.5
		var cap := Art.box(root,Vector3(at.x,h+0.035,at.z),Vector3(chord,0.07,WALL+0.05),cut)
		cap.rotation.y=a+PI*0.5
	var length := d*0.5-centre
	for x in [-1,1]:
		var wall_node := Art.box(root,Vector3(x*(radius+WALL*0.5),h*0.5,centre+length*0.5),Vector3(WALL,h,length),Color.WHITE)
		wall_node.material_override=wall_mat
		Art.box(root,Vector3(x*(radius-0.035),0.08,centre+length*0.5),Vector3(0.07,0.16,length),trim)
		Art.box(root,Vector3(x*(radius-0.02),0.5,centre+length*0.5),Vector3(0.04,1.0,length),band)
		Art.box(root,Vector3(x*(radius-0.04),1.03,centre+length*0.5),Vector3(0.08,0.07,length),trim)
		Art.box(root,Vector3(x*(radius+WALL*0.5),h+0.035,centre+length*0.5),Vector3(WALL+0.05,0.07,length),cut)
		Art.box(root,Vector3(x*(radius+WALL*0.5),h*0.5,d*0.5+0.012),Vector3(WALL+0.04,h+0.06,0.03),cut)

## Knee-high cut front wall. The ground floor has the doorway (posts, threshold,
## doormat, open door); the lighthouse lantern room has a balcony rail instead.
static func front(root: Node3D, s: Dictionary) -> void:
	var t: Dictionary = s.colors
	var w: float = s.size.x
	var d: float = s.size.y
	var hw := w*0.5
	var hd := d*0.5
	var cut := col(t,"cut")
	var trim := col(t,"trim")
	var wall_color := col(t,"wainscot") if not str(t.get("wainscot","")).is_empty() else col(t,"wall")
	if str(t.wall_tex)=="glass": wall_color=col(t,"wainscot")
	if s.get("balcony",false):
		# Lantern gallery: a deck past the glass with an iron rail, the sea beyond.
		Art.box(root,Vector3(0,-0.04,hd+0.75),Vector3(w+0.6,0.1,1.5),Color("8a9198"))
		for i in int(w/0.45)+1:
			Art.box(root,Vector3(-hw-0.2+i*0.45,0.5,hd+1.45),Vector3(0.05,1.0,0.05),Color("2f3540"))
		Art.box(root,Vector3(0,1.0,hd+1.45),Vector3(w+0.6,0.07,0.08),Color("2f3540"))
		Art.box(root,Vector3(0,0.5,hd+1.45),Vector3(w+0.6,0.04,0.05),Color("2f3540"))
		Art.box(root,Vector3(0,KNEE*0.5,hd+WALL*0.5),Vector3(w+2*WALL,KNEE,WALL),wall_color)
		Art.box(root,Vector3(0,KNEE+0.035,hd+WALL*0.5),Vector3(w+2*WALL,0.07,WALL+0.05),cut)
		return
	if not s.get("has_door",false):
		Art.box(root,Vector3(0,KNEE*0.5,hd+WALL*0.5),Vector3(w+2*WALL,KNEE,WALL),wall_color)
		Art.box(root,Vector3(0,0.08,hd-0.035),Vector3(w,0.16,0.07),trim)
		Art.box(root,Vector3(0,KNEE+0.035,hd+WALL*0.5),Vector3(w+2*WALL,0.07,WALL+0.05),cut)
		return
	var dx: float = s.door_x
	for x in [-1,1]:
		var outer: float = hw+WALL if x>0 else -hw-WALL
		var inner: float = dx+x*(DOOR_HALF+0.12)
		var span := absf(outer-inner)
		var cx := (outer+inner)*0.5
		Art.box(root,Vector3(cx,KNEE*0.5,hd+WALL*0.5),Vector3(span,KNEE,WALL),wall_color)
		Art.box(root,Vector3(cx,0.08,hd-0.035),Vector3(span,0.16,0.07),trim)
		Art.box(root,Vector3(cx,KNEE+0.035,hd+WALL*0.5),Vector3(span,0.07,WALL+0.05),cut)
		Art.box(root,Vector3(dx+x*(DOOR_HALF+0.06),KNEE*0.5+0.12,hd+WALL*0.5),Vector3(0.14,KNEE+0.24,WALL+0.08),trim)
		Art.box(root,Vector3(dx+x*(DOOR_HALF+0.06),KNEE+0.27,hd+WALL*0.5),Vector3(0.2,0.06,WALL+0.14),cut)
	Art.box(root,Vector3(dx,0.02,hd+WALL*0.5),Vector3(DOOR_HALF*2,0.05,WALL+0.12),col(t,"floor_a").lightened(0.15))
	var mat_color := col(t,"accent").darkened(0.15)
	Art.box(root,Vector3(dx,0.03,hd-0.5),Vector3(1.35,0.02,0.72),mat_color.darkened(0.25))
	Art.box(root,Vector3(dx,0.036,hd-0.5),Vector3(1.15,0.02,0.54),mat_color)
	# A half-height cottage door stands open outward, hinged on the right post,
	# low enough that it never hides the walker in the doorway.
	var hinge := Node3D.new()
	hinge.name="FrontDoor"
	root.add_child(hinge)
	hinge.position=Vector3(dx+DOOR_HALF+0.02,0,hd+WALL+0.02)
	hinge.rotation.y=deg_to_rad(108)
	var leaf_w := DOOR_HALF*2-0.16
	var door_color := col(t,"accent").darkened(0.1) if s.theme!="lodge" else Color("7a5638")
	Art.box(hinge,Vector3(-leaf_w*0.5,0.56,0),Vector3(leaf_w,1.02,0.07),door_color)
	Art.box(hinge,Vector3(-leaf_w*0.5,1.08,0),Vector3(leaf_w+0.04,0.06,0.1),cut)
	for z in [-0.045,0.045]:
		Art.box(hinge,Vector3(-leaf_w*0.5,0.56,z),Vector3(leaf_w-0.28,0.66,0.02),door_color.lightened(0.14))
		Art.box(hinge,Vector3(-leaf_w*0.5,0.56,z*1.2),Vector3(0.05,0.66,0.02),door_color.darkened(0.12))
	for z in [-0.07,0.07]: Art.sphere(hinge,Vector3(-leaf_w+0.13,0.62,z),Vector3(0.07,0.07,0.07),Color("e3c06a"))
	for y in [0.25,0.85]: Art.box(hinge,Vector3(-0.12,y,0.0),Vector3(0.24,0.05,0.09),Color("3a3430"))
	for x in [-1,1]:
		var lantern := Art.box(root,Vector3(dx+x*(DOOR_HALF+0.06),KNEE+0.42,hd+WALL*0.5),Vector3(0.14,0.18,0.14),Color("ffe2a0"))
		lantern.material_override.emission_enabled=true
		lantern.material_override.emission=Color("ffc870")
		lantern.material_override.emission_energy_multiplier=0.9
		Art.box(root,Vector3(dx+x*(DOOR_HALF+0.06),KNEE+0.54,hd+WALL*0.5),Vector3(0.2,0.05,0.2),cut)
	var sign := Art.label3d(root,TranslationServer.translate("마을 →"),Vector3(dx,1.15,hd+0.3),Color("f6e7c3"))
	sign.font_size=26
	sign.name="ExitSign"

## A window on a wall: frame, curtains and a view of the outside that follows the
## real clock (see view_material). Returns its interaction record.
static func add_window(root: Node3D, s: Dictionary, window: Dictionary) -> Dictionary:
	var t: Dictionary = s.colors
	var w: float = s.size.x
	var d: float = s.size.y
	var width: float = window.width
	var height: float = window.height
	var y: float = window.y
	var pivot := Node3D.new()
	pivot.name="Window"
	root.add_child(pivot)
	var room_colors: Dictionary = t
	match str(window.wall):
		"back":
			pivot.position=Vector3(window.u,y,-d*0.5+0.02)
			room_colors=s.rooms[room_at(s,float(window.u))].colors
		"left":
			pivot.position=Vector3(-w*0.5+0.02,y,window.u);pivot.rotation.y=PI*0.5
			room_colors=s.rooms[0].colors
		"right":
			pivot.position=Vector3(w*0.5-0.02,y,window.u);pivot.rotation.y=-PI*0.5
			room_colors=s.rooms[s.rooms.size()-1].colors
		"arc":
			var radius := w*0.5
			var a := deg_to_rad(float(window.u))
			pivot.position=Vector3(cos(a)*(radius-0.02),y,-d*0.5+radius-sin(a)*(radius-0.02))
			pivot.rotation.y=a-PI*0.5
	var trim := col(room_colors,"trim").lightened(0.1) if s.theme!="observatory" else col(room_colors,"trim")
	var round_window: bool = window.style=="round"
	var view := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size=Vector2(width,width) if round_window else Vector2(width,height)
	view.mesh=quad
	view.position.z=0.02
	view.material_override=view_material(str(s.outlook),round_window,0.12*float(s.get("floor",0)))
	view.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	view.add_to_group("window_view")
	pivot.add_child(view)
	if round_window:
		for i in 16:
			var a := TAU*i/16.0
			var ring := Art.box(pivot,Vector3(cos(a)*width*0.52,sin(a)*width*0.52,0.05),Vector3(width*0.24,0.1,0.08),trim)
			ring.rotation.z=a+PI*0.5
		Art.box(pivot,Vector3(0,0,0.05),Vector3(width,0.05,0.04),trim)
		Art.box(pivot,Vector3(0,0,0.05),Vector3(0.05,width,0.04),trim)
	else:
		for x in [-1,1]: Art.box(pivot,Vector3(x*(width*0.5+0.05),0,0.05),Vector3(0.1,height+0.2,0.09),trim)
		for yy in [-1,1]: Art.box(pivot,Vector3(0,yy*(height*0.5+0.05),0.05),Vector3(width+0.2,0.1,0.09),trim)
		Art.box(pivot,Vector3(0,0,0.04),Vector3(0.05,height,0.05),trim)
		Art.box(pivot,Vector3(0,height*0.08,0.04),Vector3(width,0.05,0.05),trim)
		Art.box(pivot,Vector3(0,-height*0.5-0.12,0.1),Vector3(width+0.34,0.07,0.22),trim)
		var curtain := str(room_colors.get("curtain",""))
		if not curtain.is_empty():
			var cloth := Color(curtain)
			for x in [-1,1]:
				Art.box(pivot,Vector3(x*(width*0.5+0.12),-0.05,0.12),Vector3(0.3,height+0.35,0.06),cloth)
				Art.box(pivot,Vector3(x*(width*0.5+0.12),-0.05,0.155),Vector3(0.08,height+0.35,0.02),cloth.darkened(0.08))
			Art.box(pivot,Vector3(0,height*0.5+0.2,0.12),Vector3(width+0.7,0.22,0.08),cloth.darkened(0.05))
			var rod := Detail.cylinder(pivot,Vector3(0,height*0.5+0.32,0.14),0.025,width+0.9,trim.darkened(0.2),8)
			rod.rotation.z=PI*0.5
	var inward := -pivot.basis.z*-1.0
	var centre := pivot.position+pivot.basis.z*0.05
	return {"kind":"window","node":pivot,"center":Vector3(centre.x,0,centre.z),"yaw":pivot.rotation.y,"mounted":true,"solid":false,"interactive":true,"glb":false,
		"size":Vector3(width,height,0.1),"half":Vector2(width*0.5,0.05),"world_half":Vector2(absf(cos(pivot.rotation.y))*width*0.5+0.05,absf(sin(pivot.rotation.y))*width*0.5+0.05),
		"top":y,"window":window,"view":view,"inward":inward}

## Warm room lights: two per room. Their authored energy is kept so the studio can
## turn them up at night and down by day.
static func lights(root: Node3D, s: Dictionary) -> void:
	var d: float = s.size.y
	var h: float = s.height
	var warm := col(s.colors,"light")
	var energy := 0.5 if s.theme!="observatory" else 0.32
	for room in s.rooms:
		var x0: float = room.x0
		var x1: float = room.x1
		var width := x1-x0
		var spots := [Vector3(x0+width*0.3,h-0.35,-d*0.18),Vector3(x0+width*0.7,h-0.35,-d*0.18),Vector3((x0+x1)*0.5,h-0.2,d*0.22)]
		if width<4.5: spots=[Vector3((x0+x1)*0.5,h-0.35,-d*0.15),Vector3((x0+x1)*0.5,h-0.2,d*0.22)]
		for i in spots.size():
			var lamp := OmniLight3D.new()
			lamp.set_meta("room",s.rooms.find(room))
			lamp.position=spots[i]
			lamp.light_color=warm
			lamp.light_energy=energy*(0.7 if i==spots.size()-1 else 1.0)
			lamp.omni_range=maxf(width,d)*0.8
			lamp.omni_attenuation=1.2
			lamp.set_meta("base_energy",lamp.light_energy)
			lamp.add_to_group("room_lamp")
			root.add_child(lamp)

## A window view that follows the real clock: a painted landscape for the
## building's surroundings by day, tinted at dawn and dusk, and a night sky with
## moon and stars after dark (night/tint are set by the studio from Daylight).
static func view_material(outlook: String, round_window: bool, lift: float) -> ShaderMaterial:
	if window_shader==null:
		window_shader=Shader.new()
		window_shader.code=WINDOW_SHADER
	var m := ShaderMaterial.new()
	m.shader=window_shader
	m.set_shader_parameter("day_tex",texture("outlook_"+outlook,Color.WHITE,Color.WHITE))
	m.set_shader_parameter("night_tex",texture("outlook_"+outlook+"_night",Color.WHITE,Color.WHITE))
	m.set_shader_parameter("round_mask",1.0 if round_window else 0.0)
	m.set_shader_parameter("lift",lift)
	return m

# ---------------------------------------------------------------- furniture

static func manifest() -> Dictionary:
	if manifest_loaded: return manifest_cache
	manifest_loaded=true
	if not FileAccess.file_exists(MANIFEST): return manifest_cache
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
	var entries: Array = []
	if parsed is Array: entries=parsed
	elif parsed is Dictionary:
		for key in ["items","furniture","models","assets","entries"]:
			var value = parsed.get(key)
			if value is Array: entries=value;break
			if value is Dictionary:
				for id in value:
					if value[id] is Dictionary:
						var copy: Dictionary=value[id].duplicate();copy["id"]=copy.get("id",id);entries.append(copy)
				break
		if entries.is_empty():
			for id in parsed:
				if parsed[id] is Dictionary:
					var copy: Dictionary=parsed[id].duplicate();copy["id"]=copy.get("id",id);entries.append(copy)
	for entry in entries:
		if not entry is Dictionary: continue
		var id := str(entry.get("id",entry.get("name","")))
		if id.is_empty(): continue
		var path := ""
		for key in ["godot_path","res_path","path","model","glb","file"]:
			if entry.has(key) and str(entry[key]).ends_with(".glb"): path=str(entry[key]);break
		if path.is_empty(): path=INTERIOR_DIR+id+".glb"
		elif not path.begins_with("res://"): path=INTERIOR_DIR+path.get_file()
		var size = null
		for key in ["target_size_m","size_m","target_m","dimensions_m","target_size","size"]:
			if entry.has(key): size=entry[key];break
		var target := Vector3.ZERO
		if size is Array and size.size()>=3: target=Vector3(float(size[0]),float(size[1]),float(size[2]))
		elif size is Dictionary: target=Vector3(float(size.get("width_x",size.get("w",size.get("x",0)))),float(size.get("height_y",size.get("h",size.get("y",0)))),float(size.get("depth_z",size.get("d",size.get("z",0)))))
		elif size is float or size is int: target=Vector3(0,float(size),0)
		var reference: Dictionary = entry.get("scale_reference",{}) if entry.get("scale_reference") is Dictionary else {}
		var yaw_fix = entry.get("front_yaw_degrees")
		manifest_cache[id]={"path":path,"size":target,"measure":str(reference.get("measure","")),"metres":float(reference.get("metres",0.0)),"yaw":yaw_fix}
	return manifest_cache

## The GLB for a kind, if one is imported: a generated interior model first, then a village prop.
static func model_path(kind: String, prop := "") -> String:
	var listed: Dictionary = manifest().get(kind,{})
	var path := str(listed.get("path",INTERIOR_DIR+kind+".glb"))
	if ResourceLoader.exists(path): return path
	if ResourceLoader.exists(INTERIOR_DIR+kind+".glb"): return INTERIOR_DIR+kind+".glb"
	if not prop.is_empty() and ResourceLoader.exists(ENVIRONMENT_DIR+prop+".glb"): return ENVIRONMENT_DIR+prop+".glb"
	if PROP_FALLBACK.has(kind) and ResourceLoader.exists(ENVIRONMENT_DIR+str(PROP_FALLBACK[kind])+".glb"): return ENVIRONMENT_DIR+str(PROP_FALLBACK[kind])+".glb"
	return ""

## Each generated model is loaded once per session and kept as a light copy:
## its 2048 px lossless maps are scaled to 512 px (a room is seen from ~10 m), so
## the originals can be freed and later rooms only duplicate the copy.
static var prototypes: Dictionary = {}
const PROP_TEXTURE := 512

static func prototype(path: String) -> Node3D:
	if prototypes.has(path): return prototypes[path]
	var packed := load(path) as PackedScene
	if packed==null: return null
	var model := packed.instantiate() as Node3D
	if model==null: return null
	var small := {}
	for node in model.find_children("*","MeshInstance3D",true,false):
		var instance := node as MeshInstance3D
		if instance.mesh==null or not instance.mesh is ArrayMesh: continue
		var mesh := instance.mesh.duplicate() as ArrayMesh
		for surface in mesh.get_surface_count():
			var material := mesh.surface_get_material(surface)
			if material is BaseMaterial3D: mesh.surface_set_material(surface,light_material(material,small))
		instance.mesh=mesh
	prototypes[path]=model
	return model

static func light_material(source: BaseMaterial3D, small: Dictionary) -> BaseMaterial3D:
	var copy := source.duplicate() as BaseMaterial3D
	for slot in ["albedo_texture","normal_texture","orm_texture","roughness_texture","metallic_texture","emission_texture","ao_texture"]:
		var texture = copy.get(slot)
		if texture is Texture2D: copy.set(slot,light_texture(texture,small))
	return copy

static func light_texture(texture: Texture2D, small: Dictionary) -> Texture2D:
	var key := texture.get_instance_id()
	if small.has(key): return small[key]
	var result: Texture2D=texture
	if texture.get_width()>PROP_TEXTURE:
		var image := texture.get_image()
		if image!=null and not image.is_empty():
			if image.is_compressed(): image.decompress()
			image.resize(PROP_TEXTURE,maxi(1,int(PROP_TEXTURE*float(image.get_height())/image.get_width())),Image.INTERPOLATE_BILINEAR)
			image.generate_mipmaps()
			result=ImageTexture.create_from_image(image)
	small[key]=result
	return result

## Instances a GLB facing +z, scaled like the manifest asks (height or longest
## side in metres) or else to the requested height without outgrowing the
## footprint, standing on the origin. Returns the size it ended up with.
static func fit_model(parent: Node3D, path: String, kind: String, size: Vector3) -> Vector3:
	var proto := prototype(path)
	if proto==null: return Vector3.ZERO
	var model := proto.duplicate(Node.DUPLICATE_SIGNALS|Node.DUPLICATE_GROUPS|Node.DUPLICATE_SCRIPTS) as Node3D
	if model==null: return Vector3.ZERO
	var meshes: Array[MeshInstance3D]=[]
	Loader._collect_meshes(model,meshes)
	var bounds := AABB()
	var first := true
	for instance in meshes:
		var b: AABB=Loader._local_transform(instance,model)*instance.get_aabb()
		bounds=b if first else bounds.merge(b)
		first=false
	if first or bounds.size.y<=0.001 or maxf(bounds.size.x,bounds.size.z)<=0.001:
		model.free()
		return Vector3.ZERO
	var listed: Dictionary = manifest().get(kind,{}) if path.begins_with(INTERIOR_DIR) else {}
	var yaw := float(YAW_FIX.get(path.get_file().get_basename(),0))
	if listed.get("yaw")!=null: yaw=float(listed.yaw)
	var turned := absf(fmod(absf(yaw),180.0)-90.0)<1.0
	var extent := Vector3(bounds.size.z,bounds.size.y,bounds.size.x) if turned else bounds.size
	var scale := size.y/extent.y
	if float(listed.get("metres",0.0))>0.0:
		var measure := str(listed.get("measure",""))
		scale=float(listed.metres)/(extent.y if measure=="height" else maxf(extent.x,extent.z))
	else:
		scale=minf(scale,minf(size.x*1.2/extent.x,size.z*1.2/extent.z))
	var pivot := Node3D.new()
	pivot.name="Model"
	parent.add_child(pivot)
	pivot.rotation.y=deg_to_rad(yaw)
	pivot.scale=Vector3.ONE*scale
	pivot.add_child(model)
	model.position=-Vector3(bounds.get_center().x,bounds.position.y,bounds.get_center().z)
	var actual := extent*scale
	if kind in MOUNTED: pivot.position.y=-actual.y*0.5
	return actual

static func place(parent: Node3D, entry: Dictionary, s: Dictionary, index: int) -> Dictionary:
	var kind := str(entry.kind)
	var size: Vector3 = entry.get("size",size_of(kind))
	var node := Node3D.new()
	node.name="Furniture_"+kind
	parent.add_child(node)
	node.position=entry.at+(Vector3.ZERO if kind in MOUNTED else Vector3(0,0.02,0))
	node.rotation_degrees.y=float(entry.get("yaw",0.0))
	var actual := Vector3.ZERO
	var path := "" if (kind in PRIMITIVE_ONLY and not entry.get("model",false)) or entry.get("primitive",false) else model_path(kind,str(entry.get("prop","")))
	if not path.is_empty(): actual=fit_model(node,path,kind,size)
	var record := {"kind":kind,"node":node,"center":Vector3(node.position.x,0,node.position.z),"yaw":node.rotation.y,"mounted":kind in MOUNTED,
		"solid":not (kind in MOUNTED or kind in FLAT),"interactive":LINES.has(kind) or kind in ["bookshelf","piano","floor_lamp","wall_clock"] or entry.has("link"),"glb":not path.is_empty() and actual!=Vector3.ZERO}
	if actual==Vector3.ZERO:
		actual=size
		var t: Dictionary = s.colors.duplicate()
		if entry.has("color"): t["accent"]=entry.color
		var rng := RandomNumberGenerator.new()
		rng.seed=hash(str(s.building)+kind)+index*7919
		if not extra_primitive(node,kind,size,t,str(entry.get("variant","")),rng,record,s):
			primitive(node,kind,size,t,str(entry.get("variant","")),index,s,record)
	else:
		model_extras(node,kind,actual,record)
	# Wall pieces sit flush against their wall whatever size the model ended up.
	var gap := 0.01 if kind in MOUNTED else 0.07
	match str(entry.get("anchor","")):
		"back": node.position.z=-s.size.y*0.5+actual.z*0.5+gap
		"left": node.position.x=-s.size.x*0.5+actual.z*0.5+gap
		"right": node.position.x=s.size.x*0.5-actual.z*0.5-gap
		"wall": node.position.x=float(entry.wall_x)-float(entry.wall_side)*(actual.z*0.5+gap)
	record["floor"]=int(s.get("floor",0))
	record["room"]=room_at(s,node.position.x)
	if entry.has("link"): record["link"]=entry.link
	if entry.has("owner"): record["owner"]=entry.owner
	record["center"]=Vector3(node.position.x,0,node.position.z)
	record["size"]=actual
	record["half"]=Vector2(actual.x*0.5,actual.z*0.5)
	var turn := node.rotation.y
	record["world_half"]=Vector2(absf(cos(turn))*actual.x*0.5+absf(sin(turn))*actual.z*0.5,absf(sin(turn))*actual.x*0.5+absf(cos(turn))*actual.z*0.5)
	record["top"]=node.position.y+actual.y
	node.set_meta("size",actual)
	return record

static func primitive(p: Node3D, kind: String, s: Vector3, t: Dictionary, variant: String, seed_value: int, room: Dictionary, record: Dictionary) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed=hash(str(room.building)+kind)+seed_value*7919
	var accent := col(t,"accent")
	var wood := Color("8d6443")
	var dark := Color("5e4430")
	match kind:
		"bed":
			Art.box(p,Vector3(0,0.17,0),Vector3(s.x,0.2,s.z),wood)
			for x in [-1,1]:
				for z in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.07),0.05,z*(s.z*0.5-0.07)),Vector3(0.1,0.1,0.1),dark)
			Art.box(p,Vector3(0,0.36,0.02),Vector3(s.x-0.1,0.2,s.z-0.16),Color("f6f0e4"))
			Art.box(p,Vector3(0,0.43,s.z*0.13),Vector3(s.x-0.02,0.13,s.z*0.68),accent)
			Art.box(p,Vector3(0,0.505,-s.z*0.2),Vector3(s.x+0.005,0.035,0.24),accent.lightened(0.35))
			for x in [-0.25,0.25]: Art.box(p,Vector3(x*s.x,0.5,s.z*0.18),Vector3(0.04,0.02,s.z*0.5),accent.lightened(0.18))
			Art.sphere(p,Vector3(0,0.53,-s.z*0.5+0.36),Vector3(s.x*0.72,0.17,0.42),Color("fdfaf2"))
			Art.box(p,Vector3(0,s.y*0.55,-s.z*0.5+0.05),Vector3(s.x+0.08,s.y*1.1,0.1),wood)
			Art.box(p,Vector3(0,s.y*1.1+0.03,-s.z*0.5+0.05),Vector3(s.x+0.16,0.07,0.16),dark)
			Art.box(p,Vector3(0,0.34,s.z*0.5-0.04),Vector3(s.x+0.06,0.48,0.08),wood)
		"side_table":
			Art.box(p,Vector3(0,s.y-0.03,0),Vector3(s.x,0.06,s.z),wood)
			Art.box(p,Vector3(0,s.y*0.5-0.02,0),Vector3(s.x-0.06,s.y-0.1,s.z-0.06),wood.lightened(0.08))
			Art.box(p,Vector3(0,s.y*0.62,s.z*0.5-0.02),Vector3(s.x-0.12,0.16,0.02),wood.darkened(0.1))
			Art.sphere(p,Vector3(0,s.y*0.62,s.z*0.5+0.01),Vector3(0.04,0.04,0.04),Color("e3c06a"))
			small_lamp(p,Vector3(-0.08,s.y,0),record)
			Art.box(p,Vector3(0.13,s.y+0.03,0.05),Vector3(0.16,0.05,0.12),Color("c95f4f"))
		"wardrobe_closet":
			Art.box(p,Vector3(0,s.y*0.5+0.05,0),Vector3(s.x,s.y-0.1,s.z),wood)
			for x in [-1,1]:
				Art.box(p,Vector3(x*s.x*0.25,s.y*0.5+0.05,s.z*0.5+0.012),Vector3(s.x*0.5-0.07,s.y-0.32,0.03),wood.lightened(0.1))
				Art.box(p,Vector3(x*s.x*0.25,s.y*0.62,s.z*0.5+0.03),Vector3(s.x*0.5-0.24,s.y*0.42,0.02),accent.lightened(0.15))
				Art.sphere(p,Vector3(x*0.07,s.y*0.5,s.z*0.5+0.05),Vector3(0.05,0.05,0.05),Color("e3c06a"))
				Art.box(p,Vector3(x*(s.x*0.5-0.08),0.03,0),Vector3(0.1,0.06,s.z-0.06),dark)
			Art.box(p,Vector3(0,s.y+0.0,0),Vector3(s.x+0.1,0.07,s.z+0.08),dark)
		"bookshelf":
			bookcase(p,s,wood,rng)
		"dining_table":
			Art.box(p,Vector3(0,s.y-0.03,0),Vector3(s.x,0.06,s.z),wood)
			for x in [-1,1]:
				for z in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.08),(s.y-0.06)*0.5,z*(s.z*0.5-0.08)),Vector3(0.07,s.y-0.06,0.07),dark)
			Art.box(p,Vector3(0,s.y+0.003,0),Vector3(s.x*0.3,0.01,s.z+0.02),accent.lightened(0.25))
			Detail.cylinder(p,Vector3(0,s.y+0.1,0),0.06,0.18,Color("dfe8ef"),10)
			Art.sphere(p,Vector3(0,s.y+0.25,0),Vector3(0.18,0.14,0.18),Color("f2c04f"))
			for x in [-0.35,0.35]: Detail.cylinder(p,Vector3(x*s.x,s.y+0.04,0.12),0.05,0.08,Color("f6f2ea"),10)
		"wooden_chair":
			var chair_wood := Color("a0714a") if variant!="cafe" else Color("6e4a35")
			Art.box(p,Vector3(0,0.46,0.02),Vector3(s.x,0.06,s.z*0.92),chair_wood)
			if variant=="cafe": Art.box(p,Vector3(0,0.5,0.03),Vector3(s.x-0.08,0.03,s.z*0.8),accent)
			for x in [-1,1]:
				for z in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.04),0.22,z*(s.z*0.5-0.05)),Vector3(0.045,0.44,0.045),chair_wood.darkened(0.12))
				Art.box(p,Vector3(x*(s.x*0.5-0.04),0.48+(s.y-0.48)*0.5,-s.z*0.5+0.05),Vector3(0.05,s.y-0.48,0.05),chair_wood.darkened(0.12))
			for y in [0.72,s.y-0.06]: Art.box(p,Vector3(0,y,-s.z*0.5+0.05),Vector3(s.x-0.04,0.08,0.04),chair_wood)
		"sofa","armchair":
			var cloth := accent
			Art.box(p,Vector3(0,0.2,0),Vector3(s.x,0.28,s.z),cloth.darkened(0.12))
			var seats := 1 if kind=="armchair" else 2
			var inner := s.x-0.36
			for i in seats:
				var x := -inner*0.5+inner/seats*(i+0.5)
				Art.box(p,Vector3(x,0.41,0.06),Vector3(inner/seats-0.03,0.15,s.z-0.25),cloth.lightened(0.1))
			Art.box(p,Vector3(0,0.62,-s.z*0.5+0.12),Vector3(s.x,0.6,0.24),cloth)
			for x in [-1,1]:
				Art.box(p,Vector3(x*(s.x*0.5-0.09),0.46,0.02),Vector3(0.18,0.34,s.z-0.04),cloth)
				Art.sphere(p,Vector3(x*(s.x*0.5-0.09),0.64,0.02),Vector3(0.2,0.1,s.z-0.06),cloth)
			for x in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.1),0.03,0),Vector3(0.08,0.06,s.z-0.1),dark)
			if kind=="sofa":
				for x in [-1,1]:
					var pillow := Art.box(p,Vector3(x*(s.x*0.5-0.38),0.62,-s.z*0.5+0.32),Vector3(0.36,0.32,0.12),Color("f3e2b6"))
					pillow.rotation.z=x*0.12
			else:
				Art.box(p,Vector3(0,0.6,-s.z*0.5+0.3),Vector3(0.34,0.3,0.12),Color("f3e2b6"))
		"kitchen_counter":
			var cabinet := accent
			Art.box(p,Vector3(0,(s.y-0.05)*0.5,0),Vector3(s.x,s.y-0.05,s.z-0.04),cabinet)
			Art.box(p,Vector3(0,s.y-0.025,0.01),Vector3(s.x+0.04,0.05,s.z),Color("eee7dc"))
			var doors := maxi(2,int(s.x/0.6))
			for i in doors:
				var x := -s.x*0.5+s.x/doors*(i+0.5)
				Art.box(p,Vector3(x,(s.y-0.05)*0.45,s.z*0.5-0.01),Vector3(s.x/doors-0.06,s.y*0.62,0.02),cabinet.lightened(0.12))
				Art.box(p,Vector3(x,s.y*0.72,s.z*0.5),Vector3(0.12,0.025,0.03),Color("e3c06a"))
			Art.box(p,Vector3(-s.x*0.22,s.y-0.03,0),Vector3(0.5,0.03,s.z*0.6),Color("9aa7ab"))
			var tap := Detail.cylinder(p,Vector3(-s.x*0.22,s.y+0.12,-s.z*0.32),0.02,0.25,Color("c8cfd2"),8)
			Art.box(p,Vector3(s.x*0.2,s.y+0.01,0.02),Vector3(0.42,0.025,0.28),Color("c99a62"))
			Art.sphere(p,Vector3(s.x*0.2,s.y+0.06,0.02),Vector3(0.11,0.09,0.11),Color("d94a3a"))
			Art.sphere(p,Vector3(s.x*0.38,s.y+0.08,-0.1),Vector3(0.3,0.14,0.18),Color("d9a15c"))
		"cooking_stove":
			var iron := Color("3c3b3f")
			Art.box(p,Vector3(0,s.y*0.45,0),Vector3(s.x,s.y*0.9,s.z),iron)
			Art.box(p,Vector3(0,s.y*0.9+0.02,0),Vector3(s.x+0.06,0.04,s.z+0.06),Color("2a292c"))
			Art.box(p,Vector3(0,s.y*0.38,s.z*0.5+0.01),Vector3(s.x*0.7,s.y*0.42,0.03),Color("56545a"))
			Art.box(p,Vector3(0,s.y*0.62,s.z*0.5+0.04),Vector3(s.x*0.5,0.04,0.04),Color("c8a35c"))
			var glow := Art.box(p,Vector3(0,s.y*0.36,s.z*0.5+0.025),Vector3(s.x*0.36,s.y*0.12,0.01),Color("ff9a3c"))
			glow.material_override.emission_enabled=true
			glow.material_override.emission=Color("ff7a2a")
			glow.material_override.emission_energy_multiplier=1.4
			for x in [-1,1]: Detail.cylinder(p,Vector3(x*s.x*0.22,s.y*0.9+0.05,0.05),0.13,0.03,Color("1f1e21"),14)
			Detail.cylinder(p,Vector3(-s.x*0.22,s.y*0.9+0.15,0.05),0.13,0.18,Color("c27a4a"),14)
			Detail.cylinder(p,Vector3(s.x*0.3,s.y*0.9+0.6,-s.z*0.3),0.08,1.2,Color("47464b"),10)
		"potted_plant":
			plant(p,s,rng,accent)
		"floor_lamp":
			Detail.cylinder(p,Vector3(0,0.025,0),0.18,0.05,dark,14)
			Detail.cylinder(p,Vector3(0,(s.y-0.3)*0.5,0),0.025,s.y-0.3,Color("4a3b2f"),8)
			var shade := Detail.cylinder(p,Vector3(0,s.y-0.17,0),0.24,0.34,Color("f7e2b5"),16,0.15)
			shade.material_override.emission_enabled=true
			shade.material_override.emission=Color("ffcf86")
			shade.material_override.emission_energy_multiplier=0.65
			var light := OmniLight3D.new()
			light.position=Vector3(0,s.y-0.35,0)
			light.light_color=Color("ffcb84")
			light.light_energy=0.45
			light.omni_range=3.2
			p.add_child(light)
			record["light"]=light
			record["shade"]=shade
		"shop_counter":
			Art.box(p,Vector3(0,(s.y-0.05)*0.5,0),Vector3(s.x,s.y-0.05,s.z),wood)
			for i in 5:
				Art.box(p,Vector3(-s.x*0.5+s.x/5*(i+0.5),(s.y-0.05)*0.5,s.z*0.5+0.01),Vector3(s.x/5-0.08,s.y-0.25,0.02),accent if i%2==0 else Color("f2efe2"))
			Art.box(p,Vector3(0,s.y-0.025,0),Vector3(s.x+0.08,0.05,s.z+0.06),dark)
			Art.box(p,Vector3(-s.x*0.3,s.y+0.13,0),Vector3(0.42,0.26,0.32),Color("4f5b62"))
			Art.box(p,Vector3(-s.x*0.3,s.y+0.27,-0.06),Vector3(0.36,0.06,0.16),Color("e9e1c9"))
			Detail.cylinder(p,Vector3(s.x*0.12,s.y+0.13,0.05),0.1,0.26,Color("e8f3f1"),12)
			for i in 6: Art.sphere(p,Vector3(s.x*0.12+rng.randf_range(-0.05,0.05),s.y+0.06+i*0.03,0.05+rng.randf_range(-0.05,0.05)),Vector3(0.05,0.05,0.05),Color.from_hsv(rng.randf(),0.55,0.95))
			Detail.cylinder(p,Vector3(s.x*0.36,s.y+0.05,0.1),0.06,0.06,Color("e3c06a"),10,0.02)
		"display_shelf":
			shelf_unit(p,s,wood,rng,variant,accent)
		"crate_stack":
			var crate := Color("b88a58")
			var c := minf(s.x*0.5,0.55)
			for spot in [Vector3(-c*0.5,c*0.5,0),Vector3(c*0.5+0.02,c*0.5,0.04),Vector3(0,c*1.5,0.02)]:
				var box_node := Art.box(p,spot,Vector3(c,c,c),crate)
				box_node.rotation.y=rng.randf_range(-0.15,0.15)
				for y in [-0.3,0.0,0.3]: Art.box(box_node,Vector3(0,y*c,c*0.5+0.01),Vector3(c-0.04,c*0.18,0.02),crate.darkened(0.15))
				Art.box(box_node,Vector3(0,0,c*0.5+0.02),Vector3(0.06,c-0.02,0.02),crate.darkened(0.3))
		"barrel":
			var r := s.x*0.5
			Detail.cylinder(p,Vector3(0,s.y*0.25,0),r*0.88,s.y*0.5,Color("a8743f"),16,r)
			Detail.cylinder(p,Vector3(0,s.y*0.75,0),r,s.y*0.5,Color("a8743f"),16,r*0.88)
			for y in [0.14,0.5,0.86]: Detail.cylinder(p,Vector3(0,s.y*y,0),r*(0.92 if y!=0.5 else 1.02),0.05,Color("4f4a45"),16)
			Detail.cylinder(p,Vector3(0,s.y+0.005,0),r*0.84,0.02,Color("8f6338"),16)
			if room.theme=="greenhouse": Detail.cylinder(p,Vector3(0,s.y-0.04,0),r*0.8,0.02,Color("6fa8c8"),16)
			else:
				for i in 3: Art.sphere(p,Vector3(rng.randf_range(-0.12,0.12),s.y+0.06,rng.randf_range(-0.12,0.12)),Vector3(0.13,0.12,0.13),Color("d2453a") if i!=1 else Color("9bc24a"))
		"workbench","desk":
			var top := Color("b0844f") if kind=="workbench" else wood
			Art.box(p,Vector3(0,s.y-0.05,0),Vector3(s.x,0.1,s.z),top)
			for x in [-1,1]:
				for z in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.08),(s.y-0.1)*0.5,z*(s.z*0.5-0.08)),Vector3(0.09,s.y-0.1,0.09),dark)
			if kind=="workbench":
				Art.box(p,Vector3(0,0.2,0),Vector3(s.x-0.2,0.05,s.z-0.15),dark.lightened(0.1))
				Art.box(p,Vector3(s.x*0.5-0.12,s.y+0.08,s.z*0.3),Vector3(0.2,0.16,0.18),Color("596369"))
				Art.box(p,Vector3(-s.x*0.2,s.y+0.02,0.05),Vector3(0.36,0.025,0.1),Color("8b5e36"))
				Art.box(p,Vector3(-s.x*0.2+0.15,s.y+0.03,0.05),Vector3(0.08,0.05,0.14),Color("7d8790"))
				Art.box(p,Vector3(s.x*0.08,s.y+0.04,-0.12),Vector3(0.7,0.06,0.18),Color("d8b27e"))
				if variant=="mill":
					for i in 3: Art.sphere(p,Vector3(-0.4+i*0.35,s.y+0.12,-0.05),Vector3(0.28,0.22,0.24),Color("efe6d0"))
			else:
				Art.box(p,Vector3(0,s.y+0.006,0.02),Vector3(0.5,0.01,0.36),Color("f4ecd8"))
				Art.box(p,Vector3(-0.35,s.y+0.006,-0.05),Vector3(0.3,0.01,0.4),Color("d8e2f0"))
				small_lamp(p,Vector3(s.x*0.36,s.y,-0.12),record)
				Detail.cylinder(p,Vector3(0.28,s.y+0.06,0.1),0.04,0.12,Color("6b8fbf"),8)
		"telescope":
			Detail.cylinder(p,Vector3(0,0.05,0),0.5,0.1,Color("4c5578"),20)
			for i in 3:
				var a := TAU*i/3.0
				var leg := Detail.cylinder(p,Vector3(cos(a)*0.28,0.55,sin(a)*0.28),0.03,1.15,Color("8a6a45"),8)
				leg.rotation=Vector3(sin(a)*0.45,0,-cos(a)*0.45)
			Art.box(p,Vector3(0,1.1,0),Vector3(0.18,0.16,0.18),Color("c9a45c"))
			var tube_pivot := Node3D.new()
			p.add_child(tube_pivot)
			tube_pivot.position=Vector3(0,1.2,0)
			tube_pivot.rotation.x=-0.85
			var tube := Detail.cylinder(tube_pivot,Vector3(0,0,-0.2),0.13,1.5,Color("3e5c9a"),18)
			tube.rotation.x=PI*0.5
			for z in [-0.9,0.45]:
				var band := Detail.cylinder(tube_pivot,Vector3(0,0,z),0.145,0.08,Color("d8b45f"),18)
				band.rotation.x=PI*0.5
			var lens := Detail.cylinder(tube_pivot,Vector3(0,0,-0.96),0.115,0.02,Color("bfe3ff"),18)
			lens.rotation.x=PI*0.5
			lens.material_override.emission_enabled=true
			lens.material_override.emission=Color("9fd0ff")
			var eye := Detail.cylinder(tube_pivot,Vector3(0,0,0.62),0.04,0.18,Color("2b2b2e"),8)
			eye.rotation.x=PI*0.5
			var finder := Detail.cylinder(tube_pivot,Vector3(0,0.19,-0.1),0.035,0.45,Color("c9a45c"),8)
			finder.rotation.x=PI*0.5
		"seedling_bench":
			Art.box(p,Vector3(0,s.y-0.04,0),Vector3(s.x,0.06,s.z),Color("a77a4c"))
			for x in [-1,1]:
				for z in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.06),(s.y-0.07)*0.5,z*(s.z*0.5-0.06)),Vector3(0.06,s.y-0.07,0.06),dark)
			Art.box(p,Vector3(0,0.22,0),Vector3(s.x-0.12,0.04,s.z-0.12),Color("a77a4c"))
			var trays := maxi(2,int(s.x/0.55))
			for i in trays:
				var x := -s.x*0.5+s.x/trays*(i+0.5)
				Art.box(p,Vector3(x,s.y+0.03,0),Vector3(s.x/trays-0.06,0.07,s.z-0.12),Color("5b4334"))
				for j in 6:
					var sprout := Vector3(x+rng.randf_range(-0.16,0.16),s.y+0.1,rng.randf_range(-s.z*0.32,s.z*0.32))
					Art.sphere(p,sprout,Vector3(0.09,0.12,0.09),Color("7fbf5a").lightened(rng.randf_range(0,0.2)))
				Detail.cylinder(p,Vector3(x,0.27,0),0.1,0.14,Color("c77a52"),10,0.12)
				Art.sphere(p,Vector3(x,0.4,0),Vector3(0.2,0.18,0.2),Color("78a85a"))
		"cafe_counter":
			Art.box(p,Vector3(0,(s.y-0.05)*0.5,0),Vector3(s.x,s.y-0.05,s.z),Color("7a5438"))
			for i in int(s.x/0.3):
				Art.box(p,Vector3(-s.x*0.5+0.15+i*0.3,(s.y-0.05)*0.5,s.z*0.5+0.01),Vector3(0.22,s.y-0.25,0.02),Color("8c6342"))
			Art.box(p,Vector3(0,s.y-0.025,0),Vector3(s.x+0.08,0.05,s.z+0.08),Color("f3efe6"))
			Art.box(p,Vector3(0,0.06,s.z*0.5+0.03),Vector3(s.x,0.12,0.04),accent)
			var case_mat := StandardMaterial3D.new()
			case_mat.albedo_color=Color("e6f4f6",0.3)
			case_mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
			var display := Art.box(p,Vector3(-s.x*0.27,s.y+0.2,0.05),Vector3(s.x*0.4,0.4,s.z*0.62),Color.WHITE)
			display.material_override=case_mat
			display.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			for i in 3:
				var cake := Vector3(-s.x*0.27-0.3+i*0.3,s.y+0.07,0.05)
				Detail.cylinder(p,cake,0.1,0.12,[Color("f6d9e0"),Color("6b4430"),Color("fbefc7")][i],14)
				Art.sphere(p,cake+Vector3(0,0.08,0),Vector3(0.05,0.05,0.05),Color("d63b45"))
			Art.box(p,Vector3(s.x*0.25,s.y+0.22,-0.05),Vector3(0.45,0.44,0.4),Color("b8c2c7"))
			Art.box(p,Vector3(s.x*0.25,s.y+0.3,0.16),Vector3(0.4,0.12,0.04),Color("3a3a3f"))
			for x in [-0.08,0.08]: Detail.cylinder(p,Vector3(s.x*0.25+x,s.y+0.04,0.12),0.04,0.07,Color("f5f1e8"),10)
			for i in 3: Detail.cylinder(p,Vector3(s.x*0.42,s.y+0.04+i*0.07,0.05),0.05,0.06,Color("f5f1e8"),10)
		"round_cafe_table":
			Detail.cylinder(p,Vector3(0,0.02,0),0.22,0.04,Color("3d3a38"),14)
			Detail.cylinder(p,Vector3(0,s.y*0.5,0),0.035,s.y,Color("3d3a38"),8)
			Detail.cylinder(p,Vector3(0,s.y,0),s.x*0.5,0.04,Color("f2ece0") if variant!="tea" else wood.lightened(0.1),20)
			if variant=="tea":
				Art.sphere(p,Vector3(0,s.y+0.1,0),Vector3(0.2,0.16,0.2),Color("f3f0ea"))
				Detail.cylinder(p,Vector3(0.18,s.y+0.04,0.1),0.04,0.06,Color("f3f0ea"),10)
			else:
				Detail.cylinder(p,Vector3(0.1,s.y+0.04,0.05),0.045,0.07,Color("f5f1e8"),10)
				Detail.cylinder(p,Vector3(-0.12,s.y+0.04,-0.05),0.06,0.02,Color("f5f1e8"),12)
				Detail.cylinder(p,Vector3(-0.12,s.y+0.07,-0.05),0.04,0.05,Color("f7d9e3"),12)
		"piano":
			var lacquer := Color("2f2522")
			var depth := s.z*0.55
			Art.box(p,Vector3(0,s.y*0.5,-s.z*0.5+depth*0.5),Vector3(s.x,s.y,depth),lacquer)
			Art.box(p,Vector3(0,s.y+0.02,-s.z*0.5+depth*0.5),Vector3(s.x+0.06,0.04,depth+0.04),lacquer.lightened(0.08))
			var key_z := -s.z*0.5+depth+0.11
			Art.box(p,Vector3(0,0.7,key_z),Vector3(s.x*0.94,0.08,0.24),lacquer)
			Art.box(p,Vector3(0,0.75,key_z+0.01),Vector3(s.x*0.86,0.025,0.16),Color("f6f2e8"))
			for i in 22:
				if i%7 in [2,6]: continue
				Art.box(p,Vector3(-s.x*0.43+0.04+i*(s.x*0.86/22.0),0.775,key_z-0.03),Vector3(0.025,0.025,0.09),Color("161414"))
			for x in [-1,1]: Art.box(p,Vector3(x*(s.x*0.47),0.36,key_z),Vector3(0.07,0.72,0.07),lacquer)
			Art.box(p,Vector3(0,1.02,-s.z*0.5+depth+0.02),Vector3(0.5,0.3,0.02),Color("f4ecd6"))
			for x in [-0.42,0.42]:
				Detail.cylinder(p,Vector3(x*s.x,s.y+0.1,-s.z*0.35),0.025,0.16,Color("f6efe0"),8)
				var flame := Art.sphere(p,Vector3(x*s.x,s.y+0.21,-s.z*0.35),Vector3(0.035,0.06,0.035),Color("ffcf6a"))
				flame.material_override.emission_enabled=true
				flame.material_override.emission=Color("ffb347")
			Art.box(p,Vector3(0,0.44,s.z*0.5-0.18),Vector3(s.x*0.5,0.08,0.34),lacquer.lightened(0.05))
			for x in [-1,1]:
				for z in [-1,1]: Art.box(p,Vector3(x*s.x*0.22,0.2,s.z*0.5-0.18+z*0.13),Vector3(0.05,0.4,0.05),lacquer)
		"fireplace":
			fireplace(p,s,room,rng,record)
		"lighthouse_lens":
			Detail.cylinder(p,Vector3(0,0.25,0),s.x*0.42,0.5,Color("3f5c75"),20)
			Detail.cylinder(p,Vector3(0,0.52,0),s.x*0.46,0.06,Color("c9a45c"),20)
			var spinner := Node3D.new()
			p.add_child(spinner)
			spinner.name="Lens"
			var glass := StandardMaterial3D.new()
			glass.albedo_color=Color("fff4c8",0.45)
			glass.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
			glass.emission_enabled=true
			glass.emission=Color("ffe7a0")
			glass.emission_energy_multiplier=0.6
			var body := Detail.cylinder(spinner,Vector3(0,1.15,0),s.x*0.36,1.1,Color.WHITE,16)
			body.material_override=glass
			body.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			for y in [0.66,0.9,1.15,1.4,1.64]: Detail.cylinder(spinner,Vector3(0,y,0),s.x*0.375,0.035,Color("d9b45f"),16)
			for i in 4:
				var a := TAU*i/4.0
				var rib := Art.box(spinner,Vector3(cos(a)*s.x*0.36,1.15,sin(a)*s.x*0.36),Vector3(0.05,1.1,0.05),Color("c9a45c"))
				rib.rotation.y=-a
			var bulb := Art.sphere(spinner,Vector3(0,1.15,0),Vector3(0.3,0.36,0.3),Color("fff2b8"))
			bulb.material_override.emission_enabled=true
			bulb.material_override.emission=Color("ffe58a")
			bulb.material_override.emission_energy_multiplier=1.6
			Detail.cylinder(p,Vector3(0,1.78,0),s.x*0.3,0.12,Color("c4483e"),16,s.x*0.12)
			var lamp := OmniLight3D.new()
			lamp.position=Vector3(0,1.2,0)
			lamp.light_color=Color("ffe39a")
			lamp.light_energy=0.7
			lamp.omni_range=4.0
			p.add_child(lamp)
			spin(spinner,14.0)
		"rug":
			var base := accent
			if variant=="round":
				Detail.cylinder(p,Vector3(0,0.008,0),s.x*0.5,0.016,base.darkened(0.25),32)
				Detail.cylinder(p,Vector3(0,0.012,0),s.x*0.5-0.14,0.018,base,32)
				Detail.cylinder(p,Vector3(0,0.016,0),s.x*0.25,0.018,base.lightened(0.15),32)
				for i in 8:
					var a := TAU*i/8.0
					var star := Art.box(p,Vector3(cos(a)*s.x*0.36,0.024,sin(a)*s.x*0.36),Vector3(0.12,0.01,0.12),Color("e8c66a"))
					star.rotation.y=PI*0.25
			else:
				Art.box(p,Vector3(0,0.008,0),Vector3(s.x,0.016,s.z),base.darkened(0.28))
				Art.box(p,Vector3(0,0.012,0),Vector3(s.x-0.16,0.018,s.z-0.16),base)
				Art.box(p,Vector3(0,0.015,0),Vector3(s.x-0.42,0.018,s.z-0.42),Color("f1e3c0"))
				Art.box(p,Vector3(0,0.017,0),Vector3(s.x-0.54,0.018,s.z-0.54),base.lightened(0.08))
				var medallion := Art.box(p,Vector3(0,0.02,0),Vector3(minf(s.x,s.z)*0.42,0.018,minf(s.x,s.z)*0.42),base.darkened(0.12))
				medallion.rotation.y=PI*0.25
				var heart := Art.box(p,Vector3(0,0.023,0),Vector3(minf(s.x,s.z)*0.24,0.018,minf(s.x,s.z)*0.24),Color("f1e3c0"))
				heart.rotation.y=PI*0.25
				for x in [-1,1]:
					for i in int(s.z/0.22):
						Art.box(p,Vector3(x*(s.x*0.5+0.04),0.01,-s.z*0.5+0.11+i*0.22),Vector3(0.09,0.012,0.03),Color("f1e3c0"))
			for child in p.get_children():
				if child is GeometryInstance3D: child.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		"wall_clock":
			var face_node := Node3D.new()
			p.add_child(face_node)
			var rim := Detail.cylinder(face_node,Vector3(0,0,0),s.x*0.5,0.07,wood,24)
			rim.rotation.x=PI*0.5
			var dial := Detail.cylinder(face_node,Vector3(0,0,0.03),s.x*0.43,0.02,Color("f7f0de"),24)
			dial.rotation.x=PI*0.5
			for i in 12:
				var a := TAU*i/12.0
				var mark := Art.box(face_node,Vector3(sin(a)*s.x*0.36,cos(a)*s.x*0.36,0.045),Vector3(0.025,0.05 if i%3==0 else 0.03,0.01),Color("3a2e26"))
				mark.rotation.z=-a
			var now := Time.get_time_dict_from_system()
			var hour_hand := Node3D.new();face_node.add_child(hour_hand);hour_hand.position.z=0.05
			Art.box(hour_hand,Vector3(0,s.x*0.11,0),Vector3(0.035,s.x*0.22,0.01),Color("2b221c"))
			hour_hand.rotation.z=-TAU*(fmod(float(now.hour),12.0)+now.minute/60.0)/12.0
			var minute_hand := Node3D.new();face_node.add_child(minute_hand);minute_hand.position.z=0.055
			Art.box(minute_hand,Vector3(0,s.x*0.16,0),Vector3(0.025,s.x*0.32,0.01),Color("2b221c"))
			minute_hand.rotation.z=-TAU*now.minute/60.0
			var second_hand := Node3D.new();face_node.add_child(second_hand);second_hand.position.z=0.06
			Art.box(second_hand,Vector3(0,s.x*0.15,0),Vector3(0.01,s.x*0.34,0.01),Color("c4483e"))
			second_hand.rotation.z=-TAU*now.second/60.0
			spin(second_hand,60.0,Vector3(0,0,-1))
		"globe":
			Detail.cylinder(p,Vector3(0,0.03,0),0.2,0.06,dark,14)
			Detail.cylinder(p,Vector3(0,0.35,0),0.03,0.6,wood,8)
			var ball := Node3D.new()
			p.add_child(ball)
			ball.position=Vector3(0,0.82,0)
			ball.rotation.z=0.4
			Art.sphere(ball,Vector3.ZERO,Vector3(0.5,0.5,0.5),Color("5d93c4"))
			for i in 5: Art.sphere(ball,Vector3(cos(i*1.3)*0.18,sin(i*2.1)*0.15,sin(i*1.3)*0.18),Vector3(0.18,0.14,0.16),Color("8fbf6a"))
			var ring := Detail.cylinder(ball,Vector3.ZERO,0.28,0.02,Color("c9a45c"),20)
			ring.rotation.x=PI*0.5
			spin(ball,24.0)
		"star_chart":
			Art.box(p,Vector3(0,0,0),Vector3(s.x+0.1,s.y+0.1,0.04),col(t,"trim"))
			var sky := Art.box(p,Vector3(0,0,0.025),Vector3(s.x,s.y,0.02),Color("10173a"))
			sky.material_override.emission_enabled=true
			sky.material_override.emission=Color("0c1230")
			var points: Array[Vector3]=[]
			for i in 9:
				var point := Vector3(rng.randf_range(-s.x*0.42,s.x*0.42),rng.randf_range(-s.y*0.4,s.y*0.4),0.04)
				points.append(point)
				var star := Art.sphere(p,point,Vector3(0.05,0.05,0.02),Color("fff1c0"))
				star.material_override.emission_enabled=true
				star.material_override.emission=Color("ffe9a8")
				star.material_override.emission_energy_multiplier=1.5
			for i in points.size()-1:
				if i==4: continue
				var a: Vector3=points[i]
				var b: Vector3=points[i+1]
				var line := Art.box(p,(a+b)*0.5,Vector3((b-a).length(),0.01,0.005),Color("8d9ad6"))
				line.rotation.z=atan2(b.y-a.y,b.x-a.x)
		"menu_board","notice_board","shop_sign":
			var board := Color("2f4a3a") if kind=="menu_board" else (Color("b58a5a") if kind=="notice_board" else col(t,"accent"))
			Art.box(p,Vector3(0,0,0),Vector3(s.x+0.1,s.y+0.1,0.05),dark)
			Art.box(p,Vector3(0,0,0.03),Vector3(s.x,s.y,0.02),board)
			if kind=="notice_board":
				for i in 5:
					var note := Art.box(p,Vector3(rng.randf_range(-s.x*0.38,s.x*0.38),rng.randf_range(-s.y*0.32,s.y*0.32),0.045),Vector3(0.26,0.32,0.01),[Color("fbf6e6"),Color("f6e08c"),Color("cfe6f5")][i%3])
					note.rotation.z=rng.randf_range(-0.15,0.15)
			else:
				var text := TranslationServer.translate("오늘의 메뉴") if kind=="menu_board" else TranslationServer.translate(str(room.kind))
				var caption := Label3D.new()
				caption.text=text
				caption.font_size=48 if kind=="menu_board" else 56
				caption.pixel_size=0.005
				caption.position=Vector3(0,s.y*0.28 if kind=="menu_board" else 0.0,0.05)
				caption.modulate=Color("f4efe1") if kind=="menu_board" else Color("3a2b20")
				caption.outline_size=0
				p.add_child(caption)
				if kind=="menu_board":
					for i in 3: Art.box(p,Vector3(-0.1,s.y*0.02-i*0.18,0.045),Vector3(s.x*0.62,0.035,0.005),Color("e8e3d4"))
		"picture_frame":
			Art.box(p,Vector3(0,0,0),Vector3(s.x,s.y,0.05),Color("c9a45c"))
			var art := Art.box(p,Vector3(0,0,0.03),Vector3(s.x-0.12,s.y-0.12,0.01),Color.WHITE)
			var paint := StandardMaterial3D.new()
			paint.albedo_texture=texture("view_sea" if rng.randf()<0.5 else "view_day",Color("a9d6ea"),Color("86b46d"))
			art.material_override=paint
		"wall_shelf":
			Art.box(p,Vector3(0,-s.y*0.4,0),Vector3(s.x,0.05,s.z),wood)
			for x in [-1,1]: Art.box(p,Vector3(x*s.x*0.4,-s.y*0.5,-s.z*0.3),Vector3(0.04,0.18,0.04),dark)
			for i in 5:
				var x := -s.x*0.4+i*s.x*0.2
				if i%2==0: Detail.cylinder(p,Vector3(x,-s.y*0.4+0.08,0),0.05,0.12,Color.from_hsv(rng.randf(),0.35,0.95),10)
				else: Art.sphere(p,Vector3(x,-s.y*0.4+0.09,0),Vector3(0.14,0.14,0.14),Color.from_hsv(rng.randf(),0.4,0.9))
		"banner":
			var rod := Detail.cylinder(p,Vector3(0,s.y*0.5,0.04),0.025,s.x+0.2,dark,8)
			rod.rotation.z=PI*0.5
			Art.box(p,Vector3(0,0,0.02),Vector3(s.x,s.y,0.02),accent)
			Art.box(p,Vector3(0,0,0.032),Vector3(s.x*0.8,s.y*0.9,0.005),accent.lightened(0.15))
			var emblem := Art.sphere(p,Vector3(0,s.y*0.1,0.04),Vector3(0.3,0.3,0.02),Color("f1d27a"))
			emblem.name="Emblem"
			for x in [-1,1]:
				var tip := Art.box(p,Vector3(x*s.x*0.25,-s.y*0.5-0.06,0.02),Vector3(s.x*0.36,0.16,0.02),accent)
				tip.rotation.z=x*0.5
		"tool_rack":
			Art.box(p,Vector3(0,0,0),Vector3(s.x,s.y,0.04),Color("caa477"))
			for i in 5:
				var x := -s.x*0.4+i*s.x*0.2
				Art.box(p,Vector3(x,0.2,0.05),Vector3(0.04,0.4,0.03),Color("7a5232"))
				Art.box(p,Vector3(x,0.38,0.05),Vector3(0.14 if i%2==0 else 0.06,0.08,0.04),Color("7d8790"))
			Art.box(p,Vector3(0,-0.3,0.05),Vector3(s.x*0.7,0.06,0.04),Color("5e6a72"))
		"ship_wheel":
			var wheel := Node3D.new()
			p.add_child(wheel)
			for i in 8:
				var a := TAU*i/8.0
				var spoke := Art.box(wheel,Vector3(cos(a)*s.x*0.3,sin(a)*s.x*0.3,0.04),Vector3(s.x*0.62,0.05,0.04),wood)
				spoke.rotation.z=a
				var arc := Art.box(wheel,Vector3(cos(a+PI/8)*s.x*0.36,sin(a+PI/8)*s.x*0.36,0.04),Vector3(s.x*0.3,0.07,0.06),wood.darkened(0.1))
				arc.rotation.z=a+PI/8+PI*0.5
			var hub := Detail.cylinder(wheel,Vector3(0,0,0.06),0.08,0.08,Color("c9a45c"),12)
			hub.rotation.x=PI*0.5
		"millstone":
			millstone(p,s,room)
		"flour_sacks":
			for i in 3:
				var at := Vector3(-s.x*0.3+i*s.x*0.3,0.3,rng.randf_range(-0.1,0.1))
				var sack := Art.sphere(p,at,Vector3(0.48,0.62,0.42),Color("efe4cb"))
				sack.rotation.z=rng.randf_range(-0.2,0.2)
				Art.sphere(p,at+Vector3(0,0.32,0),Vector3(0.14,0.12,0.14),Color("d7c9a8"))
				Art.box(p,at+Vector3(0,0.05,0.2),Vector3(0.18,0.12,0.01),Color("c89a52"))
		"spiral_stair":
			var steps := 13
			Detail.cylinder(p,Vector3(0,s.y*0.5,0),0.09,s.y,col(t,"trim"),10)
			for i in steps:
				var a := PI*0.5+i*TAU*0.92/steps
				var step_node := Art.box(p,Vector3(cos(a)*s.x*0.27,0.2+i*(s.y-0.25)/steps,sin(a)*s.x*0.27),Vector3(s.x*0.48,0.06,0.34),Color("8d6443"))
				step_node.rotation.y=-a
				Detail.cylinder(p,Vector3(cos(a)*s.x*0.5,0.65+i*(s.y-0.25)/steps,sin(a)*s.x*0.5),0.015,0.85,Color("2f2f33"),6)
		"map_table":
			Art.box(p,Vector3(0,s.y-0.03,0),Vector3(s.x,0.06,s.z),wood)
			for x in [-1,1]:
				for z in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.07),(s.y-0.06)*0.5,z*(s.z*0.5-0.07)),Vector3(0.07,s.y-0.06,0.07),dark)
			var chart := Art.box(p,Vector3(0,s.y+0.005,0),Vector3(s.x*0.8,0.01,s.z*0.75),Color.WHITE)
			var sea := StandardMaterial3D.new()
			sea.albedo_texture=texture("view_sea",Color("a6d3ec"),Color("3f86b0"))
			chart.material_override=sea
			Detail.cylinder(p,Vector3(s.x*0.3,s.y+0.03,s.z*0.25),0.06,0.04,Color("c9a45c"),12)
			small_lamp(p,Vector3(-s.x*0.38,s.y,-s.z*0.3),record)
		"soil_bed":
			Art.box(p,Vector3(0,s.y*0.5,0),Vector3(s.x,s.y,s.z),Color("8d6443"))
			Art.box(p,Vector3(0,s.y+0.01,0),Vector3(s.x-0.14,0.04,s.z-0.14),Color("5b4334"))
			for i in 14:
				var spot := Vector3(rng.randf_range(-s.x*0.42,s.x*0.42),s.y+0.1,rng.randf_range(-s.z*0.36,s.z*0.36))
				Art.sphere(p,spot,Vector3(0.22,0.2,0.22),Color("6f9e55").lightened(rng.randf_range(0,0.12)))
				Art.sphere(p,spot+Vector3(0,0.14,0),Vector3(0.1,0.08,0.1),[Color("f28ca2"),Color("f5d55a"),Color("f7f4ee"),Color("b28ae0")][i%4])
		"ladder":
			for x in [-1,1]: Art.box(p,Vector3(x*s.x*0.42,s.y*0.5,0),Vector3(0.06,s.y,0.06),wood)
			for i in int(s.y/0.32):
				Art.box(p,Vector3(0,0.28+i*0.32,0),Vector3(s.x*0.84,0.05,0.05),wood.lightened(0.1))
		"bench":
			Art.box(p,Vector3(0,0.45,0.05),Vector3(s.x,0.06,s.z*0.7),Color("a0714a"))
			Art.box(p,Vector3(0,0.72,-s.z*0.4),Vector3(s.x,0.25,0.05),Color("a0714a"))
			for x in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.08),0.36,0),Vector3(0.06,0.72,s.z*0.8),dark)
		"planter","signboard":
			if kind=="planter":
				Detail.cylinder(p,Vector3(0,s.y*0.25,0),s.x*0.38,s.y*0.5,Color("c77a52"),14,s.x*0.48)
				for i in 5: Art.sphere(p,Vector3(rng.randf_range(-0.15,0.15),s.y*0.6+rng.randf_range(0,0.2),rng.randf_range(-0.15,0.15)),Vector3(0.22,0.2,0.22),[Color("f28ca2"),Color("f5d55a"),Color("78a85a")][i%3])
			else:
				for z in [-1,1]:
					var plank := Art.box(p,Vector3(0,s.y*0.5,z*0.12),Vector3(s.x,s.y,0.05),Color("2f4a3a"))
					plank.rotation.x=z*0.2

## Light and motion that generated models cannot carry themselves.
static func model_extras(p: Node3D, kind: String, s: Vector3, record: Dictionary) -> void:
	match kind:
		"floor_lamp":
			var light := OmniLight3D.new()
			light.position=Vector3(0,s.y-0.3,0)
			light.light_color=Color("ffcb84")
			light.light_energy=0.5
			light.omni_range=3.2
			p.add_child(light)
			record["light"]=light
		"fireplace":
			var glow := OmniLight3D.new()
			glow.position=Vector3(0,0.4,s.z*0.5+0.35)
			glow.light_color=Color("ff9a4a")
			glow.light_energy=0.8
			glow.omni_range=3.6
			p.add_child(glow)
			flicker(glow,null)
		"lighthouse_lens":
			var lamp := OmniLight3D.new()
			lamp.position=Vector3(0,s.y*0.6,0)
			lamp.light_color=Color("ffe39a")
			lamp.light_energy=0.7
			lamp.omni_range=4.0
			p.add_child(lamp)
			var model := p.get_node_or_null("Model") as Node3D
			if model: spin(model,16.0)
		"cooking_stove":
			var heat := OmniLight3D.new()
			heat.position=Vector3(0,0.35,s.z*0.5+0.3)
			heat.light_color=Color("ff9a4a")
			heat.light_energy=0.3
			heat.omni_range=1.8
			p.add_child(heat)

static func small_lamp(p: Node3D, at: Vector3, record: Dictionary) -> void:
	Detail.cylinder(p,at+Vector3(0,0.12,0),0.02,0.24,Color("6b5a48"),8)
	var shade := Detail.cylinder(p,at+Vector3(0,0.27,0),0.11,0.14,Color("f7e2b5"),12,0.07)
	shade.material_override.emission_enabled=true
	shade.material_override.emission=Color("ffcf86")
	shade.material_override.emission_energy_multiplier=0.6
	if not record.has("light"):
		var light := OmniLight3D.new()
		light.position=at+Vector3(0,0.3,0.1)
		light.light_color=Color("ffcb84")
		light.light_energy=0.25
		light.omni_range=1.8
		p.add_child(light)

static func plant(p: Node3D, s: Vector3, rng: RandomNumberGenerator, accent: Color) -> void:
	var pot_h := s.y*0.32
	Detail.cylinder(p,Vector3(0,pot_h*0.5,0),s.x*0.3,pot_h,Color("c47650"),14,s.x*0.38)
	Detail.cylinder(p,Vector3(0,pot_h,0),s.x*0.4,0.05,Color("b1683f"),14)
	Detail.cylinder(p,Vector3(0,pot_h+0.02,0),s.x*0.35,0.02,Color("4f3a2b"),14)
	var leaf := Color("5f9a4f")
	for i in 7:
		var a := i*2.4+rng.randf()*0.4
		var r := s.x*rng.randf_range(0.12,0.3)
		var at := Vector3(cos(a)*r,pot_h+s.y*rng.randf_range(0.2,0.6),sin(a)*r)
		var blob := Art.sphere(p,at,Vector3(s.x*0.5,s.y*0.28,s.x*0.5),leaf.lightened(rng.randf_range(-0.05,0.18)))
		blob.rotation.y=a
	Art.sphere(p,Vector3(0,s.y*0.92,0),Vector3(s.x*0.45,s.y*0.22,s.x*0.45),leaf.lightened(0.12))

static func bookcase(p: Node3D, s: Vector3, wood: Color, rng: RandomNumberGenerator) -> void:
	for x in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.03),s.y*0.5,0),Vector3(0.06,s.y,s.z),wood)
	Art.box(p,Vector3(0,s.y*0.5,-s.z*0.5+0.02),Vector3(s.x,s.y,0.04),wood.darkened(0.2))
	Art.box(p,Vector3(0,s.y-0.03,0),Vector3(s.x+0.06,0.06,s.z+0.04),wood.darkened(0.1))
	var shelves := 4
	var gap := (s.y-0.12)/shelves
	var palette := [Color("c4483e"),Color("3f6f8f"),Color("e0a24c"),Color("5f8f5a"),Color("8c6aa3"),Color("e9dcc0"),Color("2f4a5c"),Color("b86a4a")]
	for i in shelves:
		var y := 0.06+i*gap
		Art.box(p,Vector3(0,y,0),Vector3(s.x-0.06,0.04,s.z-0.04),wood.darkened(0.05))
		var x := -s.x*0.5+0.1
		while x<s.x*0.5-0.14:
			var bw := rng.randf_range(0.05,0.1)
			var bh := gap*rng.randf_range(0.55,0.82)
			if rng.randf()<0.12:
				x+=bw;continue
			var book := Art.box(p,Vector3(x+bw*0.5,y+0.02+bh*0.5,0.02),Vector3(bw-0.008,bh,s.z*0.7),palette[rng.randi()%palette.size()])
			if rng.randf()<0.1: book.rotation.z=0.18
			x+=bw

static func shelf_unit(p: Node3D, s: Vector3, wood: Color, rng: RandomNumberGenerator, variant: String, accent: Color) -> void:
	for x in [-1,1]: Art.box(p,Vector3(x*(s.x*0.5-0.03),s.y*0.5,0),Vector3(0.06,s.y,s.z),wood)
	Art.box(p,Vector3(0,s.y*0.5,-s.z*0.5+0.02),Vector3(s.x,s.y,0.03),accent.lightened(0.25))
	Art.box(p,Vector3(0,s.y-0.03,0),Vector3(s.x+0.06,0.06,s.z+0.04),wood.darkened(0.1))
	var shelves := 4
	var gap := (s.y-0.1)/shelves
	for i in shelves:
		var y := 0.05+i*gap
		Art.box(p,Vector3(0,y,0.02),Vector3(s.x-0.06,0.04,s.z-0.02),wood.darkened(0.05))
		var count := int((s.x-0.2)/0.2)
		for j in count:
			var x := -s.x*0.5+0.16+j*(s.x-0.3)/maxf(1,count-1)
			var hue := rng.randf()
			match variant:
				"seeds":
					var packet := Art.box(p,Vector3(x,y+0.13,0.04),Vector3(0.14,0.2,0.02),Color.from_hsv(hue,0.5,0.95))
					packet.rotation.x=-0.15
					Art.sphere(p,Vector3(x,y+0.16,0.06),Vector3(0.06,0.06,0.01),Color.from_hsv(fmod(hue+0.5,1.0),0.6,0.9))
				"bread":
					var loaf := Art.sphere(p,Vector3(x,y+0.08,0.03),Vector3(0.17,0.11,0.12),Color("d49a55").lightened(rng.randf_range(-0.1,0.1)))
					loaf.rotation.y=rng.randf_range(-0.4,0.4)
				"jars":
					Detail.cylinder(p,Vector3(x,y+0.1,0.03),0.06,0.16,Color.from_hsv(hue,0.4,0.95),10)
					Detail.cylinder(p,Vector3(x,y+0.19,0.03),0.065,0.03,Color("8d6443"),10)
				_:
					if j%2==0: Art.box(p,Vector3(x,y+0.09,0.03),Vector3(0.15,0.14,0.15),Color.from_hsv(hue,0.45,0.9))
					else: Detail.cylinder(p,Vector3(x,y+0.1,0.03),0.05,0.16,Color.from_hsv(hue,0.5,0.85),8)

static func fireplace(p: Node3D, s: Vector3, room: Dictionary, rng: RandomNumberGenerator, record: Dictionary) -> void:
	var stone := Color("a39a8e")
	var body_h := s.y*0.8
	Art.box(p,Vector3(0,body_h*0.5,0),Vector3(s.x,body_h,s.z),stone)
	for i in 14:
		var brick := Art.box(p,Vector3(rng.randf_range(-s.x*0.45,s.x*0.45),rng.randf_range(0.1,body_h-0.1),s.z*0.5+0.005),Vector3(rng.randf_range(0.18,0.32),rng.randf_range(0.1,0.16),0.02),stone.darkened(rng.randf_range(0.05,0.15)))
		brick.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var opening := Art.box(p,Vector3(0,body_h*0.36,s.z*0.5-0.08),Vector3(s.x*0.56,body_h*0.6,0.18),Color("1d1714"))
	opening.name="Hearth"
	Art.box(p,Vector3(0,0.04,s.z*0.5+0.1),Vector3(s.x+0.1,0.08,0.3),stone.darkened(0.2))
	Art.box(p,Vector3(0,body_h+0.04,0.02),Vector3(s.x+0.2,0.08,s.z+0.14),Color("7a5638"))
	Art.box(p,Vector3(0,body_h+0.04+(room.height-body_h)*0.5,-0.05),Vector3(s.x*0.72,room.height-body_h,s.z*0.75),stone.lightened(0.05))
	for i in 3:
		var log_node := Detail.cylinder(p,Vector3(-0.15+i*0.15,0.12,s.z*0.5-0.1),0.06,s.x*0.38,Color("6e4a2e"),8)
		log_node.rotation=Vector3(0,0.3*(i-1),PI*0.5)
	var fire := Node3D.new()
	fire.name="Fire"
	p.add_child(fire)
	for i in 4:
		var flame := Art.sphere(fire,Vector3(-0.18+i*0.12,0.3,s.z*0.5-0.06),Vector3(0.14,0.36-absf(i-1.5)*0.08,0.1),Color("ffb347") if i%2==0 else Color("ff7a2a"))
		flame.material_override.emission_enabled=true
		flame.material_override.emission=flame.material_override.albedo_color
		flame.material_override.emission_energy_multiplier=2.0
		flame.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		flame.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var glow := OmniLight3D.new()
	glow.position=Vector3(0,0.45,s.z*0.5+0.35)
	glow.light_color=Color("ff9a4a")
	glow.light_energy=0.8
	glow.omni_range=3.6
	p.add_child(glow)
	flicker(glow,fire)
	for x in [-0.4,0.4]: Detail.cylinder(p,Vector3(x*s.x,body_h+0.16,0.05),0.03,0.16,Color("f6efe0"),8)
	Art.box(p,Vector3(0,body_h+0.2,-0.02),Vector3(0.3,0.26,0.1),Color("7a5638"))

static func millstone(p: Node3D, s: Vector3, room: Dictionary) -> void:
	var r := s.x*0.5
	Detail.cylinder(p,Vector3(0,0.2,0),r,0.4,Color("8d6443"),20)
	Detail.cylinder(p,Vector3(0,0.41,0),r*0.98,0.04,Color("6e4a2e"),20)
	Detail.cylinder(p,Vector3(0,0.55,0),r*0.8,0.24,Color("9b968d"),20)
	var turning := Node3D.new()
	turning.name="Runner"
	p.add_child(turning)
	Detail.cylinder(turning,Vector3(0,0.8,0),r*0.78,0.26,Color("aaa59b"),20)
	for i in 6:
		var a := TAU*i/6.0
		var groove := Art.box(turning,Vector3(cos(a)*r*0.4,0.935,sin(a)*r*0.4),Vector3(r*0.7,0.01,0.04),Color("7f7a71"))
		groove.rotation.y=-a
	Detail.cylinder(turning,Vector3(0,(room.height+1.2)*0.5,0),0.11,room.height+0.2,Color("6e4a2e"),10)
	var gear_y: float = room.height-0.55
	Detail.cylinder(turning,Vector3(0,gear_y,0),r*0.75,0.16,Color("7a5638"),24)
	for i in 16:
		var a := TAU*i/16.0
		var tooth := Art.box(turning,Vector3(cos(a)*r*0.8,gear_y,sin(a)*r*0.8),Vector3(0.14,0.14,0.1),Color("5b3f2a"))
		tooth.rotation.y=-a
	var hopper := Detail.cylinder(p,Vector3(0,1.25,0),0.38,0.45,Color("a07a50"),4,0.12)
	hopper.rotation.y=PI*0.25
	Art.box(p,Vector3(r*0.85,0.45,0.0),Vector3(0.4,0.12,0.25),Color("8d6443"))
	Art.sphere(p,Vector3(r*1.02,0.3,0.0),Vector3(0.38,0.3,0.36),Color("f2ead6"))
	spin(turning,18.0)

## Endless slow turn (lens, millstone, globe, clock hand) bound to the node.
static func spin(node: Node3D, seconds: float, axis := Vector3.UP) -> void:
	if not node.is_inside_tree(): return
	var tween := node.create_tween().set_loops()
	var start := node.rotation
	tween.tween_property(node,"rotation",start+axis*TAU,seconds).from(start)

static func flicker(light: OmniLight3D, fire: Node3D) -> void:
	if not light.is_inside_tree(): return
	var tween := light.create_tween().set_loops()
	for value in [0.95,0.7,0.88,0.62,0.8]:
		tween.tween_property(light,"light_energy",value,0.18+randf()*0.15)
	if fire==null: return
	var dance := fire.create_tween().set_loops()
	dance.tween_property(fire,"scale",Vector3(1.05,1.15,1),0.22)
	dance.tween_property(fire,"scale",Vector3(0.96,0.9,1),0.26)

# ---------------------------------------------------------------- materials

static func surface(kind: String, a: Color, b: Color, tile_m: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_texture=texture(kind,a,b)
	m.uv1_triplanar=true
	m.uv1_world_triplanar=true
	m.uv1_scale=Vector3.ONE/tile_m
	m.roughness=0.88
	m.texture_filter=BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return m

## Small procedural textures (planks, tiles, plaster, logs, views) built once per colour pair.
static func texture(kind: String, a: Color, b: Color) -> ImageTexture:
	var key := kind+a.to_html()+b.to_html()
	if texture_cache.has(key): return texture_cache[key]
	if kind.begins_with("outlook_"):
		var name := kind.trim_prefix("outlook_")
		var painted := paint_outlook(name.trim_suffix("_night"),name.ends_with("_night"))
		painted.generate_mipmaps()
		var view_texture := ImageTexture.create_from_image(painted)
		texture_cache[key]=view_texture
		return view_texture
	var size := 256
	var image := Image.create_empty(size,size,false,Image.FORMAT_RGB8)
	var rng := RandomNumberGenerator.new()
	rng.seed=hash(key)
	match kind:
		"planks","wide_planks":
			image.fill(a.darkened(0.35))
			var row_h := 32 if kind=="planks" else 48
			for row in int(size/float(row_h))+1:
				var x := -rng.randi_range(0,160)
				while x<size:
					var length := rng.randi_range(110,220)
					var tone := a.lerp(b,rng.randf()).lightened(rng.randf_range(-0.04,0.04))
					image.fill_rect(Rect2i(x+1,row*row_h+1,length-2,row_h-2),tone)
					for g in 3:
						var gy := row*row_h+rng.randi_range(4,row_h-5)
						image.fill_rect(Rect2i(x+rng.randi_range(4,30),gy,rng.randi_range(30,length-30),1),tone.darkened(0.06))
					x+=length
		"checker":
			image.fill(a.lightened(0.1))
			for ty in 4:
				for tx in 4:
					var tone := a if (tx+ty)%2==0 else b
					image.fill_rect(Rect2i(tx*64+1,ty*64+1,62,62),tone.lightened(rng.randf_range(-0.03,0.03)))
		"tiles":
			image.fill(b.darkened(0.15))
			for ty in 5:
				for tx in 5:
					image.fill_rect(Rect2i(tx*51+2,ty*51+2,48,48),a.lerp(b,rng.randf_range(0,0.5)))
		"terracotta":
			image.fill(Color("e8dccb"))
			for ty in 6:
				for tx in 6:
					image.fill_rect(Rect2i(tx*43+2,ty*43+2,40,40),a.lerp(b,rng.randf()))
		"flags":
			image.fill(b.darkened(0.3))
			for row in 4:
				var x := -rng.randi_range(0,60)
				while x<size:
					var length := rng.randi_range(56,120)
					image.fill_rect(Rect2i(x+2,row*64+2,length-4,60),a.lerp(b,rng.randf()).lightened(rng.randf_range(-0.05,0.05)))
					x+=length
		"plaster":
			image.fill(a)
			for i in 260:
				image.fill_rect(Rect2i(rng.randi_range(0,size),rng.randi_range(0,size),rng.randi_range(6,26),rng.randi_range(4,16)),a.lerp(b,rng.randf_range(0.3,1.0)))
		"panels":
			image.fill(a)
			for px in 4:
				image.fill_rect(Rect2i(px*64,0,3,size),b)
				image.fill_rect(Rect2i(px*64+10,20,44,size-40),a.lightened(0.04))
		"logs":
			for row in 7:
				var y0 := row*37
				for y in 37:
					var t := absf(float(y)/36.0-0.5)*2.0
					image.fill_rect(Rect2i(0,y0+y,size,1),a.lerp(b,t*t).lightened(0.05-t*0.05))
				image.fill_rect(Rect2i(0,y0,size,2),b.darkened(0.35))
		"stripes":
			image.fill(a)
			for i in 8:
				if i%2==1: image.fill_rect(Rect2i(i*32,0,32,size),b)
			for i in 8: image.fill_rect(Rect2i(i*32+15,0,2,size),b.lerp(a,0.5))
		"stars","star_mask":
			image.fill(a if kind=="stars" else Color.BLACK)
			if kind=="stars":
				for i in 120: image.fill_rect(Rect2i(rng.randi_range(0,size),rng.randi_range(0,size),rng.randi_range(8,30),rng.randi_range(8,30)),a.lerp(Color("3a4a80"),rng.randf_range(0.1,0.4)))
			var stars := RandomNumberGenerator.new()
			stars.seed=77
			for i in 46:
				var p := Vector2i(stars.randi_range(6,size-7),stars.randi_range(6,size-7))
				var r := 1 if stars.randf()<0.65 else 2
				var star_color := Color("fff3c8") if kind=="stars" else Color.WHITE
				image.fill_rect(Rect2i(p.x-r,p.y-r,r*2+1,r*2+1),star_color)
				if i%6==0:
					image.fill_rect(Rect2i(p.x-5,p.y,11,1),star_color)
					image.fill_rect(Rect2i(p.x,p.y-5,1,11),star_color)
		"view_day","view_sea","view_garden","view_night":
			size=128
			image=Image.create_empty(size,size,false,Image.FORMAT_RGB8)
			for y in size:
				var v := float(y)/size
				var sky := Color("8ec5e6").lerp(Color("eaf5f2"),v*1.2) if kind!="view_night" else a.lerp(b,v)
				image.fill_rect(Rect2i(0,y,size,1),sky)
			if kind=="view_night":
				for i in 40: image.set_pixel(rng.randi_range(0,size-1),rng.randi_range(0,size-1),Color("fff3c8"))
				image.fill_rect(Rect2i(90,18,12,12),Color("fbf2cf"))
			elif kind=="view_sea":
				image.fill_rect(Rect2i(0,int(size*0.58),size,size),b)
				for i in 30: image.fill_rect(Rect2i(rng.randi_range(0,size),rng.randi_range(int(size*0.6),size),rng.randi_range(6,16),1),b.lightened(0.3))
			else:
				for x in size:
					var hill := int(size*(0.62+0.08*sin(x*0.07+1.3)+0.04*sin(x*0.21)))
					image.fill_rect(Rect2i(x,hill,1,size-hill),b.lightened(0.08))
					var near := int(size*(0.8+0.05*sin(x*0.13+0.4)))
					image.fill_rect(Rect2i(x,near,1,size-near),b.darkened(0.12))
				if kind=="view_garden":
					for i in 26:
						var c := Vector2i(rng.randi_range(0,size),rng.randi_range(int(size*0.55),size))
						image.fill_rect(Rect2i(c.x-6,c.y-6,12,10),Color("6f9e5a").lightened(rng.randf_range(-0.1,0.15)))
					for i in 20: image.fill_rect(Rect2i(rng.randi_range(0,size),rng.randi_range(int(size*0.7),size),3,3),[Color("f28ca2"),Color("f5d55a"),Color("ffffff")][i%3])
				for i in 3:
					var cx := rng.randi_range(10,size-30)
					var cy := rng.randi_range(8,40)
					image.fill_rect(Rect2i(cx,cy,22,6),Color("fbfdfc"))
					image.fill_rect(Rect2i(cx+5,cy-4,12,5),Color("fbfdfc"))
	image.generate_mipmaps()
	var result := ImageTexture.create_from_image(image)
	texture_cache[key]=result
	return result

# ---------------------------------------------------------------- interactions

## A few soft piano notes, synthesised (no audio files needed).
static func piano_stream(tune_index: int) -> AudioStreamWAV:
	var notes: Array = PIANO_TUNES[tune_index%PIANO_TUNES.size()]
	var rate := 22050
	var note_len := 0.26
	var total := note_len*(notes.size()-1)+1.1
	var frames := int(total*rate)
	var samples := PackedFloat32Array()
	samples.resize(frames)
	for n in notes.size():
		var frequency: float = notes[n]
		var start := int(n*note_len*rate)
		var length := int(1.1*rate)
		for i in length:
			var index := start+i
			if index>=frames: break
			var t := float(i)/rate
			var envelope := minf(t*180.0,1.0)*exp(-t*3.2)
			var wave := sin(TAU*frequency*t)*0.6+sin(TAU*frequency*2.0*t)*0.22*exp(-t*2.0)+sin(TAU*frequency*3.0*t)*0.08*exp(-t*4.0)
			samples[index]+=wave*envelope*0.42
	var data := PackedByteArray()
	data.resize(frames*2)
	for i in frames: data.encode_s16(i*2,int(clampf(samples[i],-1,1)*24000))
	var stream := AudioStreamWAV.new()
	stream.format=AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate=rate
	stream.data=data
	return stream

# ---------------------------------------------------------------- extra pieces

## Stairs, hatches and the small household pieces that have no generated model.
static func extra_primitive(p: Node3D, kind: String, s: Vector3, t: Dictionary, variant: String, rng: RandomNumberGenerator, record: Dictionary, room: Dictionary) -> bool:
	var wood := Color("8d6443")
	var dark := Color("5e4430")
	match kind:
		"staircase":
			var steps := maxi(8,int(s.y/0.24))
			var rise := s.y/steps
			var run := s.z/steps
			for i in steps:
				var step := Art.box(p,Vector3(0,(i+1)*rise*0.5,s.z*0.5-(i+0.5)*run),Vector3(s.x,(i+1)*rise,run+0.01),wood.lightened(0.06 if i%2==0 else 0.0))
				step.name="Step"
				Art.box(p,Vector3(0,(i+1)*rise+0.012,s.z*0.5-(i+0.5)*run+run*0.4),Vector3(s.x+0.02,0.025,0.08),dark)
			var side := -1.0 if variant=="left" else 1.0
			var rail_x := side*(s.x*0.5-0.04)
			for i in range(0,steps,3):
				Detail.cylinder(p,Vector3(rail_x,(i+1)*rise+0.45,s.z*0.5-(i+0.5)*run),0.025,0.9,dark,6)
			var rail := Art.box(p,Vector3(rail_x,s.y*0.5+0.9,0),Vector3(0.06,0.06,sqrt(s.z*s.z+s.y*s.y)),dark)
			rail.rotation.x=atan2(s.y,s.z)
			Art.box(p,Vector3(0,0.02,s.z*0.5+0.18),Vector3(s.x*0.8,0.02,0.3),col(t,"accent").darkened(0.2))
		"stair_hatch":
			var pit := Art.box(p,Vector3(0,0.03,0),Vector3(s.x-0.12,0.025,s.z-0.12),Color("1c1612"))
			pit.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			for i in 3:
				Art.box(p,Vector3(0,0.045,s.z*0.5-0.2-i*0.28),Vector3(s.x-0.2,0.02,0.22),wood.darkened(0.25+i*0.12))
			var rim := Art.box(p,Vector3(0,0.015,0),Vector3(s.x+0.08,0.03,s.z+0.08),col(t,"trim"))
			rim.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			for x in [-1,1]:
				for z in [-1,0,1]: Detail.cylinder(p,Vector3(x*(s.x*0.5),0.47,z*(s.z*0.5)),0.03,0.94,dark,6)
				Art.box(p,Vector3(x*s.x*0.5,0.92,0),Vector3(0.06,0.06,s.z),dark)
				Art.box(p,Vector3(x*s.x*0.5,0.5,0),Vector3(0.04,0.04,s.z),dark)
			Art.box(p,Vector3(0,0.92,-s.z*0.5),Vector3(s.x,0.06,0.06),dark)
			Art.box(p,Vector3(0,0.5,-s.z*0.5),Vector3(s.x,0.04,0.04),dark)
			var arrow := Art.label3d(p,"▼",Vector3(0,1.2,s.z*0.5),Color("f6e7c3"))
			arrow.font_size=30
		"chest":
			Art.box(p,Vector3(0,s.y*0.33,0),Vector3(s.x,s.y*0.66,s.z),Color("a8743f"))
			var lid := Node3D.new()
			lid.name="Lid"
			p.add_child(lid)
			lid.position=Vector3(0,s.y*0.66,-s.z*0.5)
			Art.box(lid,Vector3(0,s.y*0.16,s.z*0.5),Vector3(s.x+0.02,s.y*0.32,s.z+0.02),Color("b5804a"))
			for x in [-0.32,0.32]:
				Art.box(p,Vector3(x*s.x,s.y*0.33,s.z*0.5+0.005),Vector3(0.06,s.y*0.66,0.02),Color("4f4a45"))
				Art.box(lid,Vector3(x*s.x,s.y*0.16,s.z+0.015),Vector3(0.06,s.y*0.32,0.02),Color("4f4a45"))
			Art.box(p,Vector3(0,s.y*0.58,s.z*0.5+0.02),Vector3(0.1,0.12,0.03),Color("e3c06a"))
			record["lid"]=lid
		"washstand":
			Art.box(p,Vector3(0,0.4,0),Vector3(s.x,0.8,s.z),Color("f1ece2"))
			Art.box(p,Vector3(0,0.82,0.02),Vector3(s.x+0.04,0.04,s.z+0.04),Color("d9d2c4"))
			var basin := Detail.cylinder(p,Vector3(0,0.87,0.04),s.x*0.32,0.1,Color("fbfbfb"),18,s.x*0.36)
			basin.name="Basin"
			Detail.cylinder(p,Vector3(0,0.92,0.04),s.x*0.27,0.02,Color("9fd0ea"),18)
			Detail.cylinder(p,Vector3(0,0.98,-s.z*0.32),0.025,0.22,Color("c8cfd2"),8)
			var mirror := Art.box(p,Vector3(0,1.45,-s.z*0.5+0.03),Vector3(s.x*0.8,0.7,0.03),Color("cfe6ef"))
			mirror.material_override.metallic=0.6
			mirror.material_override.roughness=0.15
			Art.box(p,Vector3(0,1.45,-s.z*0.5+0.015),Vector3(s.x*0.8+0.08,0.78,0.02),Color("c9a45c"))
			Art.box(p,Vector3(0,1.85,-s.z*0.5+0.08),Vector3(s.x*0.7,0.03,0.12),wood)
			for i in 3: Detail.cylinder(p,Vector3(-0.15+i*0.15,1.92,-s.z*0.5+0.08),0.03,0.1,Color.from_hsv(rng.randf(),0.3,0.95),8)
		"bathtub":
			Art.box(p,Vector3(0,s.y*0.55,0),Vector3(s.x,s.y*0.7,s.z),Color("fbfbf8"))
			Art.box(p,Vector3(0,s.y*0.87,0),Vector3(s.x+0.06,0.06,s.z+0.06),Color("f1efe8"))
			var water := Art.box(p,Vector3(0,s.y*0.86,0),Vector3(s.x-0.16,0.02,s.z-0.16),Color("8ccbe6"))
			water.name="Water"
			for x in [-1,1]:
				for z in [-1,1]: Art.sphere(p,Vector3(x*(s.x*0.5-0.1),0.08,z*(s.z*0.5-0.1)),Vector3(0.1,0.16,0.1),Color("c9a45c"))
			Detail.cylinder(p,Vector3(-s.x*0.5+0.1,s.y+0.12,0),0.025,0.25,Color("c8cfd2"),8)
			for i in 4: Art.sphere(p,Vector3(rng.randf_range(-0.4,0.4),s.y*0.9,rng.randf_range(-0.2,0.2)),Vector3(0.12,0.08,0.12),Color("ffffff"))
			Art.sphere(p,Vector3(0.3,s.y*0.92,0.05),Vector3(0.12,0.1,0.1),Color("f2c94c"))
		"coat_rack":
			Detail.cylinder(p,Vector3(0,0.03,0),0.22,0.06,dark,12)
			Detail.cylinder(p,Vector3(0,s.y*0.5,0),0.035,s.y,wood,8)
			for i in 4:
				var a := TAU*i/4.0
				var hook := Art.box(p,Vector3(cos(a)*0.12,s.y-0.12,sin(a)*0.12),Vector3(0.2,0.03,0.03),dark)
				hook.rotation.y=-a
			Art.box(p,Vector3(0.14,s.y-0.55,0),Vector3(0.12,0.75,0.32),col(t,"accent"))
			Art.sphere(p,Vector3(-0.1,s.y-0.02,0),Vector3(0.3,0.12,0.3),Color("e0c27a"))
			Art.box(p,Vector3(-0.12,s.y-0.45,0.08),Vector3(0.06,0.55,0.12),Color("d9826b"))
		"basket":
			Detail.cylinder(p,Vector3(0,s.y*0.3,0),s.x*0.42,s.y*0.6,Color("c9a06a"),14,s.x*0.5)
			for y in [0.12,0.3,0.48]: Detail.cylinder(p,Vector3(0,s.y*y,0),s.x*(0.44+y*0.1),0.025,Color("a8804c"),14)
			var handle := Detail.cylinder(p,Vector3(0,s.y*0.75,0),0.02,s.x*0.9,Color("a8804c"),6)
			handle.rotation.z=PI*0.5
			for i in 5: Art.sphere(p,Vector3(rng.randf_range(-0.12,0.12),s.y*0.62,rng.randf_range(-0.1,0.1)),Vector3(0.12,0.11,0.12),[Color("d2453a"),Color("9bc24a"),Color("f2c04f")][i%3])
		"gear_wheel":
			# The big face wheel turns toward the room on an axle from the back wall.
			var centre_y := s.y*0.52
			var radius := minf(s.x*0.42,s.y*0.45)
			Art.box(p,Vector3(0,centre_y,-s.z*0.25),Vector3(0.16,0.16,s.z*1.5),dark)
			for x in [-1,1]: Art.box(p,Vector3(x*(radius*0.55),centre_y*0.5,-s.z*0.3),Vector3(0.14,centre_y,0.16),dark)
			var wheel := Node3D.new()
			wheel.name="Wheel"
			p.add_child(wheel)
			wheel.position=Vector3(0,centre_y,s.z*0.15)
			var disc := Detail.cylinder(wheel,Vector3.ZERO,radius,0.14,Color("9a6e45"),28)
			disc.rotation.x=PI*0.5
			var hub := Detail.cylinder(wheel,Vector3(0,0,0.08),0.18,0.1,dark,12)
			hub.rotation.x=PI*0.5
			for i in 20:
				var a := TAU*i/20.0
				var cog := Art.box(wheel,Vector3(cos(a)*(radius+0.07),sin(a)*(radius+0.07),0),Vector3(0.14,0.14,0.16),dark)
				cog.rotation.z=a
			for i in 4:
				var spoke := Art.box(wheel,Vector3(0,0,0.075),Vector3(radius*1.9,0.09,0.03),dark.lightened(0.1))
				spoke.rotation.z=PI*i/4.0
			spin(wheel,22.0,Vector3(0,0,1))
			Detail.cylinder(p,Vector3(radius+0.45,room.height*0.5,-s.z*0.2),0.1,room.height,Color("6e4a2e"),10)
		"hoist":
			Art.box(p,Vector3(0,s.y-0.1,0),Vector3(s.x,0.14,0.14),dark)
			var pulley := Detail.cylinder(p,Vector3(0,s.y-0.28,0),0.14,0.06,Color("8a6a45"),14)
			pulley.rotation.x=PI*0.5
			var rope := Detail.cylinder(p,Vector3(0.12,s.y*0.5,0),0.015,s.y-0.6,Color("c9b48a"),6)
			rope.name="Rope"
			var sack := Node3D.new()
			sack.name="Sack"
			p.add_child(sack)
			sack.position=Vector3(0.12,0.75,0)
			Art.sphere(sack,Vector3.ZERO,Vector3(0.45,0.6,0.4),Color("efe4cb"))
			Art.sphere(sack,Vector3(0,0.32,0),Vector3(0.14,0.12,0.14),Color("d7c9a8"))
			record["bob"]=sack
		_:
			return false
	return true

# ---------------------------------------------------------------- interactions

## A line for what the windows show, from the real hour (and a mood for the day).
static func window_line(hour: float, outlook: String) -> String:
	var weather: Array = ["바람이 살랑살랑 불어요.","구름이 몽실몽실 떠 있어요.","하늘이 맑고 푸르러요.","멀리서 새소리가 들려요."]
	var mood: String = weather[int(Time.get_date_dict_from_system().day)%weather.size()]
	var line := ""
	if hour<5.0 or hour>=21.5: line="깊은 밤이에요. 달빛이 바다에 비쳐요." if outlook=="sea" else "깊은 밤이에요. 마을이 고요히 잠들었어요."
	elif hour<7.0: line="창밖이 희뿌옇게 밝아 와요. 새벽이에요."
	elif hour<11.0: line="아침 햇살이 창으로 쏟아져요."
	elif hour<15.0: line="한낮의 해가 높이 떴어요. 마을이 환해요."
	elif hour<17.5: line="오후 햇살이 길게 늘어져요."
	elif hour<19.5: line="창밖이 노을로 붉게 물들고 있어요."
	else: line="창밖에 별이 하나둘 떠오르고 있어요."
	var text := TranslationServer.translate(line)
	if hour>=7.0 and hour<19.5: text+=" "+TranslationServer.translate(mood)
	return text

## What using a piece of furniture does: a line, a sound and a small effect the
## studio plays ("sit", "lie", "open", "steam", "drops", "embers", "spin", "travel"...).
static func interact(record: Dictionary, count: int, hour := 12.0, outlook := "meadow") -> Dictionary:
	var kind := str(record.kind)
	var action: String = ACTIONS.get(kind,"look")
	if record.has("link"): action="travel"
	# Most furniture answers with an effect; words stay where they inform.
	var result := {"action":action,"sound":SOUNDS.get(action,"pop"),"quiet":not kind in ["bookshelf","menu_board","notice_board"]}
	match kind:
		"window":
			result["text"]=window_line(hour,outlook)
			result["chip"]=("☾ " if hour<5.5 or hour>=19.5 else "☀ ")+"%02d:%02d" % [int(hour),int(fmod(hour,1.0)*60.0)]
			return result
		"bookshelf":
			var title: String = BOOKS[count%BOOKS.size()]
			result["text"]=TranslationServer.translate("책 한 권을 펼쳤어요 · %s")%TranslationServer.translate(title)
			return result
		"piano":
			result["text"]=TranslationServer.translate("♪ 건반을 눌러 봤어요. 맑은 소리가 울려요.")
			result["sound"]="piano"
			return result
		"wall_clock":
			var now := Time.get_time_dict_from_system()
			result["text"]=TranslationServer.translate("태엽을 감았어요. 째깍째깍, 지금은 %d시 %02d분이에요.")%[int(now.hour),int(now.minute)]
			result["chip"]="◷ %02d:%02d" % [int(now.hour),int(now.minute)]
			return result
		"floor_lamp":
			var light = record.get("light")
			if light is OmniLight3D:
				light.visible=not light.visible
				var shade = record.get("shade")
				if shade is MeshInstance3D: shade.material_override.emission_energy_multiplier=0.65 if light.visible else 0.0
				result["text"]=TranslationServer.translate("스탠드를 켰어요. 방이 아늑해졌어요.") if light.visible else TranslationServer.translate("스탠드를 껐어요.")
				return result
	if action=="travel":
		var up: bool = int(record.link.to)>int(record.get("floor",0))
		result["text"]=TranslationServer.translate("계단을 올라가요.") if up else TranslationServer.translate("계단을 내려가요.")
		return result
	var lines: Array = LINES.get(kind,[])
	if lines.is_empty(): return {}
	result["text"]=TranslationServer.translate(str(lines[count%lines.size()]))
	return result

## Little synthesised effect sounds, built once.
static func sfx(kind: String) -> AudioStreamWAV:
	if sound_cache.has(kind): return sound_cache[kind]
	var rate := 22050
	var length: float = {"click":0.08,"creak":0.55,"splash":0.6,"sizzle":0.9,"ding":1.3,"tick":0.95,"page":0.32,"knock":0.42,"crackle":0.9,"steps":1.0,"cushion":0.3,"whoosh":0.9,"chime":1.2,"rumble":1.1,"clink":0.45,"pop":0.16}.get(kind,0.2)
	var frames := int(length*rate)
	var data := PackedByteArray()
	data.resize(frames*2)
	var rng := RandomNumberGenerator.new()
	rng.seed=hash(kind)
	var smooth := 0.0
	for i in frames:
		var t := float(i)/rate
		var u := t/length
		var noise := rng.randf_range(-1.0,1.0)
		var wave := 0.0
		match kind:
			"click": wave=sin(TAU*1400*t)*exp(-t*90)+noise*exp(-t*160)*0.4
			"creak":
				var f := 180.0+140.0*u+sin(t*40.0)*25.0
				wave=(sin(TAU*f*t)*0.5+sin(TAU*f*2.0*t)*0.2)*sin(PI*u)*0.6+noise*0.04
			"splash","whoosh":
				smooth=lerpf(smooth,noise,0.18 if kind=="splash" else 0.05)
				var env := sin(PI*minf(u*3.0,1.0))*pow(1.0-u,1.4) if kind=="splash" else sin(PI*u)
				wave=smooth*env*(1.6 if kind=="splash" else 2.4)
				if kind=="splash" and rng.randf()<0.004: wave+=sin(TAU*900*t)*0.4
			"sizzle":
				smooth=lerpf(smooth,noise,0.6)
				wave=smooth*0.35*minf(u*6.0,1.0)*(1.0-u)+(noise*0.8 if rng.randf()<0.01 else 0.0)
			"ding": wave=(sin(TAU*1318.5*t)*0.5+sin(TAU*2637.0*t)*0.18+sin(TAU*3955.0*t)*0.06)*exp(-t*3.2)
			"chime": wave=(sin(TAU*1046.5*t)*0.4*exp(-t*3.0)+sin(TAU*1568.0*maxf(t-0.18,0.0))*0.4*exp(-maxf(t-0.18,0.0)*3.0)*(1.0 if t>0.18 else 0.0))
			"tick":
				var k := fmod(t,0.3)
				wave=sin(TAU*(2200.0 if int(t/0.3)%2==0 else 1700.0)*k)*exp(-k*120)*0.7
			"page":
				smooth=lerpf(smooth,noise,0.3)
				wave=smooth*sin(PI*u)*0.7
			"knock":
				var k := fmod(t,0.18)
				wave=(sin(TAU*170*k)*0.8+noise*0.25)*exp(-k*38)*(1.0 if t<0.36 else 0.0)
			"crackle":
				smooth=lerpf(smooth,noise,0.2)
				wave=smooth*0.15+(noise*0.9*exp(-fmod(t,0.07)*90) if rng.randf()<0.02 else 0.0)
			"steps":
				var k := fmod(t,0.25)
				wave=(sin(TAU*(95.0-40.0*k)*k)*0.9+noise*0.3)*exp(-k*30)
			"cushion":
				smooth=lerpf(smooth,noise,0.08)
				wave=(sin(TAU*70*t)*0.5+smooth*1.2)*exp(-t*14)
			"rumble":
				smooth=lerpf(smooth,noise,0.03)
				wave=(sin(TAU*55*t)*0.4+smooth*1.6)*sin(PI*u)
			"clink":
				var k := fmod(t,0.17)
				wave=(sin(TAU*2600*k)*0.4+sin(TAU*3900*k)*0.2)*exp(-k*40)*(1.0 if t<0.34 else 0.0)
			_: wave=sin(TAU*(520.0+300.0*u)*t)*exp(-t*28)
		data.encode_s16(i*2,int(clampf(wave,-1,1)*20000))
	var stream := AudioStreamWAV.new()
	stream.format=AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate=rate
	stream.data=data
	sound_cache[kind]=stream
	return stream

# ---------------------------------------------------------------- daylight

## Sunbeams through the windows of one floor for a Daylight sample: a soft shaft
## from each window down to a bright patch on the floor, angled by the sun's
## height and the time of day. Moonlight leaves a faint blue patch at night.
static func sunbeams(root: Node3D, s: Dictionary, sample: Dictionary) -> void:
	var old := root.get_node_or_null("Sunbeams")
	if old: old.free()
	var holder := Node3D.new()
	holder.name="Sunbeams"
	root.add_child(holder)
	var day: float = sample.daylight
	var night: float = sample.night
	var hour: float = sample.hour
	var strength := 0.0
	var tint := Color.WHITE
	if day>0.02:
		strength=0.16+0.2*day
		tint=(sample.sun_color as Color).lerp(Color("ffcf8a"),0.35)
	elif night>0.7:
		strength=0.07
		tint=Color("9fb4ff")
	else: return
	var elevation := clampf(float(Daylight.sun_elevation(hour)),14.0,60.0) if day>0.02 else 38.0
	var reach := 1.0/tan(deg_to_rad(elevation))
	var slant := clampf((hour-12.4)/6.0,-0.9,0.9) if day>0.02 else 0.2
	var d: float = s.size.y
	var w: float = s.size.x
	for window in s.windows:
		if window.style=="round" or window.wall=="arc": continue
		if window.wall=="left" and hour>13.0 and day>0.02: continue
		if window.wall=="right" and hour<11.0 and day>0.02: continue
		var origin: Vector3
		var inward: Vector3
		var along: Vector3
		match str(window.wall):
			"back":
				origin=Vector3(window.u,0,-d*0.5);inward=Vector3(0,0,1);along=Vector3(1,0,0)
			"left":
				origin=Vector3(-w*0.5,0,window.u);inward=Vector3(1,0,0);along=Vector3(0,0,-1)
			_:
				origin=Vector3(w*0.5,0,window.u);inward=Vector3(-1,0,0);along=Vector3(0,0,1)
		var half: float = float(window.width)*0.5
		var bottom: float = float(window.y)-float(window.height)*0.5
		var top: float = float(window.y)+float(window.height)*0.5
		var limit := (d if window.wall=="back" else w*0.6)-0.4
		var near := minf(bottom*reach,limit)
		var far := minf(top*reach,limit)
		var shift := clampf(slant*reach,-0.45,0.45)
		var corners := [
			origin+along*(-half)+Vector3(0,top,0),origin+along*half+Vector3(0,top,0),
			origin+along*(half+top*shift)+inward*far+Vector3(0,0.03,0),origin+along*(-half+top*shift)+inward*far+Vector3(0,0.03,0)]
		var low := [
			origin+along*(-half)+Vector3(0,bottom,0),origin+along*half+Vector3(0,bottom,0),
			origin+along*(half+bottom*shift)+inward*near+Vector3(0,0.03,0),origin+along*(-half+bottom*shift)+inward*near+Vector3(0,0.03,0)]
		for list in [corners,low]:
			for i in [2,3]:
				var c: Vector3=list[i]
				list[i]=Vector3(clampf(c.x,-w*0.5+0.1,w*0.5-0.1),c.y,clampf(c.z,-d*0.5+0.1,d*0.5-0.4))
		beam_sheet(holder,corners,tint,strength*0.55)
		beam_sheet(holder,low,tint,strength*0.45)
		beam_patch(holder,[low[3],low[2],corners[2],corners[3]],tint,strength*1.6)

static func beam_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode=BaseMaterial3D.BLEND_MODE_ADD
	m.cull_mode=BaseMaterial3D.CULL_DISABLED
	m.vertex_color_use_as_albedo=true
	m.no_depth_test=false
	return m

## A light shaft: bright at the window, fading toward the floor.
static func beam_sheet(parent: Node3D, c: Array, tint: Color, alpha: float) -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var bright := Color(tint.r,tint.g,tint.b,alpha)
	var faint := Color(tint.r,tint.g,tint.b,0.0)
	for index in [0,1,2,0,2,3]:
		st.set_color(bright if index<2 else faint)
		st.add_vertex(c[index])
	var node := MeshInstance3D.new()
	node.mesh=st.commit()
	node.material_override=beam_material()
	node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(node)

## The patch of light on the floor, soft at its edges.
static func beam_patch(parent: Node3D, c: Array, tint: Color, alpha: float) -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var centre: Vector3 = (c[0]+c[1]+c[2]+c[3])*0.25
	var glow := Color(tint.r,tint.g,tint.b,alpha)
	var edge := Color(tint.r,tint.g,tint.b,alpha*0.25)
	for i in 4:
		var a: Vector3=c[i]
		var b: Vector3=c[(i+1)%4]
		st.set_color(glow);st.add_vertex(centre)
		st.set_color(edge);st.add_vertex(a)
		st.set_color(edge);st.add_vertex(b)
	var node := MeshInstance3D.new()
	node.mesh=st.commit()
	node.material_override=beam_material()
	node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(node)

## Painted outdoor views (day and night) for each kind of surroundings.
static func paint_outlook(kind: String, night: bool) -> Image:
	var wide := 192
	var tall := 128
	var image := Image.create_empty(wide,tall,false,Image.FORMAT_RGB8)
	var rng := RandomNumberGenerator.new()
	rng.seed=hash(kind)
	var sky_top := Color("10183c") if night else Color("78b9e4")
	var sky_low := Color("2e3a6e") if night else Color("e6f3f0")
	for y in tall: image.fill_rect(Rect2i(0,y,wide,1),sky_top.lerp(sky_low,minf(1.0,float(y)/(tall*0.62))))
	var shade := func(c: Color) -> Color: return c.darkened(0.72).lerp(Color("1b2550"),0.45) if night else c
	if night:
		for i in 46: image.set_pixel(rng.randi_range(0,wide-1),rng.randi_range(0,int(tall*0.5)),Color("fff3c8") if i%3 else Color("b9c6ff"))
		for y in 13:
			for x in 13:
				var dist := Vector2(x-6,y-6).length()
				if dist<6.2: image.set_pixel(150+x,12+y,Color("fbf2cf").lerp(Color("e6dcae"),dist/7.0))
	else:
		for i in 4:
			var cx := rng.randi_range(0,wide-30)
			var cy := rng.randi_range(8,40)
			image.fill_rect(Rect2i(cx,cy,26,7),Color("fbfdfc"))
			image.fill_rect(Rect2i(cx+6,cy-4,14,5),Color("fbfdfc"))
	var horizon := int(tall*0.6)
	match kind:
		"sea":
			image.fill_rect(Rect2i(0,horizon,wide,tall-horizon),shade.call(Color("3f86b0")))
			for i in 40: image.fill_rect(Rect2i(rng.randi_range(0,wide),rng.randi_range(horizon+2,tall),rng.randi_range(6,16),1),shade.call(Color("8cc4dc")))
			for x in 50: image.fill_rect(Rect2i(120+x,horizon-int(6*sin(x/50.0*PI)),1,int(6*sin(x/50.0*PI))+1),shade.call(Color("6f9a6a")))
			if night: for i in 20: image.fill_rect(Rect2i(150+rng.randi_range(-8,8),horizon+rng.randi_range(2,tall-horizon-2),rng.randi_range(4,10),1),Color("d8d0a0"))
		"town":
			for x in wide:
				var hill := int(tall*(0.66+0.05*sin(x*0.05+1.0)))
				image.fill_rect(Rect2i(x,hill,1,tall-hill),shade.call(Color("8fb873")))
			for i in 9:
				var bx := 6+i*21+rng.randi_range(-3,3)
				var by := int(tall*0.66)-rng.randi_range(4,14)
				var roof: Color = [Color("c4483e"),Color("4f7fb0"),Color("e0a24c"),Color("8c6aa3")][i%4]
				image.fill_rect(Rect2i(bx,by,16,14),shade.call(Color("efe2c8")))
				for k in 6: image.fill_rect(Rect2i(bx-1+k,by-k,18-2*k,1),shade.call(roof))
				image.fill_rect(Rect2i(bx+5,by+5,4,4),Color("ffd27a") if night else Color("7fa8c0"))
			for x in wide:
				var near := int(tall*(0.84+0.04*sin(x*0.11)))
				image.fill_rect(Rect2i(x,near,1,tall-near),shade.call(Color("6f9a55")))
		"camp":
			for x in wide:
				var hill := int(tall*(0.64+0.06*sin(x*0.04+2.0)))
				image.fill_rect(Rect2i(x,hill,1,tall-hill),shade.call(Color("86ad6a")))
			for i in 11:
				var px := rng.randi_range(0,wide)
				var py := int(tall*0.7)+rng.randi_range(-6,10)
				var size := rng.randi_range(10,18)
				for k in size: image.fill_rect(Rect2i(px-k/2,py-size+k,k+1,1),shade.call(Color("3f6f55")))
			for k in 10: image.fill_rect(Rect2i(60-k,int(tall*0.82)-10+k,2*k+1,1),shade.call(Color("e08a3c")))
			if night: image.fill_rect(Rect2i(58,int(tall*0.82)-2,5,4),Color("ffb347"))
		_:
			for x in wide:
				var hill := int(tall*(0.62+0.08*sin(x*0.06+1.3)+0.03*sin(x*0.2)))
				image.fill_rect(Rect2i(x,hill,1,tall-hill),shade.call(Color("94bd73")))
				var near := int(tall*(0.8+0.05*sin(x*0.12+0.4)))
				image.fill_rect(Rect2i(x,near,1,tall-near),shade.call(Color("6f9e55")))
			for i in 8:
				var tx := rng.randi_range(0,wide)
				var ty := int(tall*0.7)+rng.randi_range(-4,8)
				image.fill_rect(Rect2i(tx-6,ty-10,12,10),shade.call(Color("4f7f45")))
				image.fill_rect(Rect2i(tx-1,ty,2,4),shade.call(Color("6b4e36")))
			if kind=="garden":
				for i in 40: image.fill_rect(Rect2i(rng.randi_range(0,wide),rng.randi_range(int(tall*0.82),tall),2,2),shade.call([Color("f28ca2"),Color("f5d55a"),Color("ffffff")][i%3]))
				image.fill_rect(Rect2i(0,int(tall*0.6),wide,2),shade.call(Color("5f9ac0")))
	return image

## Sitting or lying: bends the hips and knees of the walker's skeleton on top of
## whatever the animation is doing (the body itself is moved by the studio).
class RestPose extends SkeletonModifier3D:
	var mode := ""
	var body: Node3D
	var amount := 0.0

	func rotate_bone(skeleton: Skeleton3D, bone: String, angles: Vector3, basis: Basis) -> void:
		var index := skeleton.find_bone(bone)
		if index<0: return
		for component in 3:
			if absf(angles[component])<0.0001: continue
			var axis := Vector3.ZERO
			axis[component]=1
			var world_axis := basis*axis
			var bone_world := skeleton.global_basis*skeleton.get_bone_global_pose(index).basis
			var local_axis := (bone_world.inverse()*world_axis).normalized()
			var pose := skeleton.get_bone_pose_rotation(index)
			skeleton.set_bone_pose_rotation(index,pose*Quaternion(local_axis,angles[component]))

	func _process_modification_with_delta(delta: float) -> void:
		amount=move_toward(amount,1.0 if mode=="sit" else 0.0,delta*5.0)
		if amount<=0.0 or not is_instance_valid(body): return
		var skeleton := get_skeleton()
		if not skeleton: return
		var basis := body.global_basis.orthonormalized()
		for side in ["L","R"]:
			rotate_bone(skeleton,side+"_Thigh",Vector3(1.5*amount,0,0),basis)
			rotate_bone(skeleton,side+"_Calf",Vector3(-1.55*amount,0,0),basis)
			rotate_bone(skeleton,side+"_Upperarm",Vector3(0.35*amount,0,0),basis)
			rotate_bone(skeleton,side+"_Forearm",Vector3(0.7*amount,0,0),basis)

# ---------------------------------------------------------------- residents

## Spot words from residents.gd mapped to furniture kinds, best first.
const SPOT_KINDS := {"bed":["bed"],"table":["dining_table","round_cafe_table","map_table","desk"],"stove":["cooking_stove","kitchen_counter","fireplace"],
	"armchair":["armchair","sofa","wooden_chair","bench"],"sofa":["sofa","armchair","bench","wooden_chair"],"fireplace":["fireplace","armchair","sofa"],
	"desk":["desk","map_table","dining_table"],"bookshelf":["bookshelf","display_shelf","wall_shelf"],"piano":["piano"],"sink":["kitchen_counter","washstand","bathtub"],
	"window":["window"],"counter":["cafe_counter","shop_counter","kitchen_counter","workbench"],"telescope":["telescope"],"millstone":["millstone","gear_wheel"],
	"garden_bed":["soil_bed","seedling_bench","planter","potted_plant"],"lens":["lighthouse_lens"],"workbench":["workbench","desk"]}
const SEATS := ["armchair","sofa","wooden_chair","bench"]
## Activities done sitting down when the spot offers a seat (or a table with chairs).
const SITTING := ["read","relax","chat","visit","coffee","eat","fireplace"]
## Shadow folk titles (the outdoor roster uses the same text).
const SHADOW_TITLES := {"postman":"수상한 그림자 · 우편배달부","fisher":"수상한 그림자 · 낚시꾼","farmer":"수상한 그림자 · 농부","sweeper":"수상한 그림자 · 청소부",
	"gentleman":"수상한 그림자 · 우산 신사","stargazer":"수상한 그림자 · 별지기","lamplighter":"수상한 그림자 · 등불지기","gardener":"수상한 그림자 · 정원사",
	"scout":"수상한 그림자 · 탐험가","regular":"수상한 그림자 · 카페 단골","kid":"수상한 그림자 · 꼬마","stroller":"수상한 그림자 · 밤 산책자","poet":"수상한 그림자 · 시인",
	"miller":"수상한 그림자 · 방앗간지기","shopkeeper":"수상한 그림자 · 잡화점 주인"}
const ACTIVITY_LINES := {
	"cook":["보글보글, 수프를 끓이는 중이에요.","배고프면 한 숟갈 맛볼래요?"],
	"eat":["냠냠, 식사 중이에요.","오늘 반찬이 참 맛있어요."],
	"read":["이 책 정말 재미있어요. 다 읽으면 빌려줄게요.","책장을 넘기는 소리가 좋아요."],
	"tidy":["책장을 정리하고 있어요. 먼지가 폴폴!"],
	"wash":["설거지 중이에요. 뽀득뽀득!"],
	"fireplace":["불가에 앉아 있으니 노곤노곤해요."],
	"piano":["♪ 새로 배운 곡이에요. 들어 볼래요?"],
	"chat":["오늘 하루는 어땠어요?","마을에 새 소식 있어요?"],
	"relax":["잠깐 쉬는 중이에요."],
	"coffee":["여기 코코아가 정말 맛있어요.","카페에 오면 하루가 느긋해져요."],
	"browse":["구경하러 왔어요. 뭘 살지 고민이에요."],
	"barista":["어서 오세요! 오늘은 별빛 라테가 잘 나가요.","창가 자리가 비었어요. 천천히 쉬다 가요."],
	"mill":["오늘은 바람이 좋아서 맷돌이 신나게 돌아요.","밀가루가 고우면 빵이 폭신해져요."],
	"tend":["새싹은 아침 햇살을 제일 좋아해요.","물은 흙이 마를 때 듬뿍 주는 게 좋아요."],
	"stargaze":["오늘 밤은 하늘이 맑아서 별이 잘 보여요.","저기, 고래자리가 떠올랐어요."],
}
const SHOP_LINES := {"farmer":["씨앗 보러 왔어요? 오늘은 별사탕 씨앗이 싱싱해요.","새싹이 자라는 걸 보면 마음이 몽글몽글해져요."],
	"shopkeeper":["어서 오세요, 마을 잡화점이에요!","필요한 게 있으면 뭐든 말해요."]}
const FISHING_LINES := ["물때가 바뀔 때 입질이 좋아요.","등대 부두는 새벽이 제일 좋아요."]

static func resident_title(id: String) -> String:
	var entry: Dictionary = Residents.resident(id)
	if entry.has("title"): return str(entry.title)
	return str(SHADOW_TITLES.get(id,"수상한 그림자"))

## "나루" for the cast, the role ("정원사") for shadow folk.
static func short_name(id: String) -> String:
	var parts := TranslationServer.translate(resident_title(id)).split(" · ")
	if str(Residents.resident(id).get("kind",""))=="cast" or parts.size()<2: return parts[0]
	return parts[1]

static func portrait(id: String) -> String:
	if str(Residents.resident(id).get("kind",""))=="cast": return "res://assets/portraits/%s.png" % id
	return "res://assets/ui/shadow_%s.png" % id

## The piece of furniture an occupant uses: their own bed when asleep, otherwise
## the closest match for their spot word, never one somebody else already uses.
## Returns {floor, record} (empty when nothing fits).
static func choose_spot(occupant: Dictionary, floors: Array, taken: Dictionary) -> Dictionary:
	var id := str(occupant.id)
	var spot := str(occupant.get("spot",""))
	if occupant.get("asleep",false) or spot=="bed":
		for pass_index in 2:
			for index in floors.size():
				for record in floors[index]:
					if record.kind!="bed" or taken.has(record.node.get_instance_id()): continue
					if pass_index==0 and str(record.get("owner",""))!=id: continue
					if pass_index==1 and not str(record.get("owner","")).is_empty(): continue
					return {"floor":index,"record":record}
	var kinds: Array = SPOT_KINDS.get(spot,[])
	var sitting: bool = str(occupant.get("activity","")) in SITTING
	for index in floors.size():
		for kind in kinds:
			for record in floors[index]:
				if record.kind!=kind or taken.has(record.node.get_instance_id()) or record.has("link"): continue
				# Eating or visiting at a table: take a chair beside it when there is one.
				if sitting and kind in ["dining_table","round_cafe_table","map_table","desk"]:
					var chair := nearest_free(floors[index],["wooden_chair","bench","armchair","sofa"],record.center,1.7,taken)
					if not chair.is_empty(): return {"floor":index,"record":chair}
				return {"floor":index,"record":record}
	var fallback: Array = SEATS if sitting else ["bookshelf","display_shelf","window","kitchen_counter","potted_plant","wardrobe_closet","chest"]
	for index in floors.size():
		for record in floors[index]:
			if record.kind in fallback and not taken.has(record.node.get_instance_id()): return {"floor":index,"record":record}
	return {}

static func nearest_free(records: Array, kinds: Array, at: Vector3, within: float, taken: Dictionary) -> Dictionary:
	var best := {}
	var best_gap := within
	for record in records:
		if not record.kind in kinds or taken.has(record.node.get_instance_id()): continue
		var gap: float = Vector2(record.center.x-at.x,record.center.z-at.z).length()
		if gap<best_gap: best_gap=gap;best=record
	return best

## A free standing point in front of a piece (or beside it), on the floor.
static func stand_spot(record: Dictionary, f: Dictionary, records: Array, others: Array) -> Vector3:
	var front := Vector3(0,0,1).rotated(Vector3.UP,float(record.yaw))
	var side := Vector3(1,0,0).rotated(Vector3.UP,float(record.yaw))
	for distance in [0.55,0.75,0.95,1.2,1.5]:
		for lateral in [0.0,0.45,-0.45,0.9,-0.9]:
			var at: Vector3=record.center+front*(float(record.half.y)+distance)+side*lateral
			at.y=0
			if not walkable(f,at): continue
			var clear := true
			for other in records:
				if not other.solid: continue
				var local: Vector3=(at-other.center).rotated(Vector3.UP,-float(other.yaw))
				if absf(local.x)<float(other.half.x)+0.3 and absf(local.z)<float(other.half.y)+0.3: clear=false;break
			for point in others:
				if (point as Vector3).distance_to(at)<0.65: clear=false
			if clear: return at
	return spawn_point(f)

## What a resident says (and offers) when the walker talks to them.
static func resident_talk(id: String, occupant: Dictionary, building: Dictionary, hour: float) -> Dictionary:
	var activity := str(occupant.get("activity",""))
	var greeting := "좋은 아침이에요!" if hour>=5.0 and hour<11.0 else ("안녕하세요!" if hour<17.0 else ("좋은 저녁이에요." if hour<21.5 else "이 밤에 웬일이에요?"))
	var lines: Array = []
	var pool: Array = ACTIVITY_LINES.get(activity,ACTIVITY_LINES.chat)
	if activity=="shopkeep": pool=SHOP_LINES.get(id,ACTIVITY_LINES.browse)
	lines.append(TranslationServer.translate(greeting)+" "+TranslationServer.translate(str(pool[randi()%pool.size()])))
	var choices: Array = []
	match activity:
		"barista": choices.append(["따뜻한 코코아 한 잔","coffee"])
		"shopkeep": choices.append(["추천 물건 물어보기","seed_tip" if id=="farmer" else "shop_tip"])
		"mill": choices.append(["밀가루 한 줌 얻기","flour"])
		"tend": choices.append(["꽃 한 송이 받기","flower"])
		"stargaze": choices.append(["망원경 들여다보기","telescope"])
		"visit":
			var host := ""
			for resident in Residents.residents_of(str(building.building)):
				if resident!=id: host=short_name(resident);break
			if not host.is_empty(): lines.append(TranslationServer.translate("%s네 집에 놀러 왔어요. 차 한 잔 얻어 마시는 중이에요.") % host)
	if id in ["haeru","fisher"]:
		lines.append(TranslationServer.translate(str(FISHING_LINES[randi()%FISHING_LINES.size()])))
		choices.append(["낚시 요령 더 듣기","fish_tip"])
	if id=="stargazer" and activity!="stargaze":
		lines.append(TranslationServer.translate("낮에는 별이 숨어 있어요. 밤에 다시 놀러 와요."))
	choices.append(["또 봐요","bye"])
	return {"lines":lines,"choices":choices}

## Simple stand-in silhouette when the shadow figure script cannot be used.
static func stand_in_figure(id: String) -> Node3D:
	var root := Node3D.new()
	root.name="Shadow_"+id
	var dark := Color("17161c")
	var body := Detail.cylinder(root,Vector3(0,0.62,0),0.24,0.95,dark,10,0.2)
	body.name="Body"
	Art.sphere(root,Vector3(0,1.3,0),Vector3(0.42,0.46,0.42),dark)
	for x in [-0.08,0.08]:
		var eye := Art.sphere(root,Vector3(x,1.34,0.19),Vector3(0.07,0.05,0.03),Color.WHITE)
		eye.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	for x in [-0.1,0.1]: Detail.cylinder(root,Vector3(x,0.08,0),0.06,0.16,dark,6)
	return root
