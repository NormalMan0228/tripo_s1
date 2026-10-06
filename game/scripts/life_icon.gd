extends Control
## Flat 2D icon for a village-life item, drawn from simple shapes so every crop,
## fish and forage find has one. `shadow` draws an unknown fish as a silhouette.
const Art=preload("res://scripts/life_art.gd")
var item := ""
var shadow := false

static func make(id: String, edge: float, unknown := false) -> Control:
	var icon: Control=load("res://scripts/life_icon.gd").new()
	icon.item=id
	icon.shadow=unknown
	icon.custom_minimum_size=Vector2(edge,edge)
	icon.size=Vector2(edge,edge)
	icon.mouse_filter=Control.MOUSE_FILTER_IGNORE
	return icon

func blob(c: Vector2, r: Vector2, color: Color, points := 18) -> void:
	var p := PackedVector2Array()
	for i in points: p.append(c+Vector2(cos(TAU*i/points)*r.x,sin(TAU*i/points)*r.y))
	draw_colored_polygon(p,color)

func outline_blob(c: Vector2, r: Vector2, color: Color, line: Color) -> void:
	blob(c,r+Vector2(2,2),line)
	blob(c,r,color)

func _draw() -> void:
	var s := minf(size.x,size.y)/64.0
	draw_set_transform(Vector2((size.x-64*s)*0.5,(size.y-64*s)*0.5),0,Vector2(s,s))
	var ink := Color("3b2a1c")
	var kind := item.trim_suffix("_seed")
	if item.ends_with("_seed"):
		draw_rect(Rect2(14,10,36,46),Color("f4e6c4"))
		draw_rect(Rect2(14,10,36,46),ink,false,2)
		draw_rect(Rect2(14,10,36,10),Color("b98a52"))
		_crop(kind,Vector2(32,40),0.55)
		return
	if Art.FISH_LOOK.has(item):
		_fish(Vector2(32,32),shadow)
		return
	match item:
		"turnip","carrot","pumpkin","strawberry","sunflower": _crop(item,Vector2(32,34),1.0)
		"bait":
			for i in 5: blob(Vector2(16+i*8,34+sin(i*1.4)*6),Vector2(6,5),Color("d9897a"))
			blob(Vector2(52,30),Vector2(4,4),Color("c26f62"))
		"apple":
			outline_blob(Vector2(32,36),Vector2(17,16),Color("de4b3e"),ink)
			draw_line(Vector2(32,22),Vector2(34,12),ink,3)
			blob(Vector2(40,15),Vector2(7,4),Color("6ea84e"))
			blob(Vector2(26,30),Vector2(4,6),Color(1,1,1,0.45))
		"pinecone":
			draw_line(Vector2(32,12),Vector2(32,6),ink,3)
			outline_blob(Vector2(32,34),Vector2(13,21),Color("8d5e36"),ink)
			for row in 4:
				for k in 3:
					var p := Vector2(24+k*8+(row%2)*4-2,22+row*8)
					draw_colored_polygon(PackedVector2Array([p+Vector2(-4,-2),p+Vector2(4,-2),p+Vector2(0,4)]),Color("b4834f"))
		"coconut":
			outline_blob(Vector2(32,36),Vector2(19,18),Color("7a5230"),ink)
			blob(Vector2(25,29),Vector2(6,4),Color("a37549"))
			for p in [Vector2(28,26),Vector2(36,26),Vector2(32,32)]: blob(p,Vector2(2.6,2.6),Color("2e2015"),8)
		"herb":
			for i in 5: _leaf(Vector2(32,54),-PI/2+(i-2)*0.4,30,9,Color("7cc062").lerp(Color("4f9a48"),i*0.2))
		"stone":
			outline_blob(Vector2(32,38),Vector2(22,14),Color("a7aaa8"),ink)
			blob(Vector2(26,32),Vector2(8,4),Color("c9cbc8"))
		"copper_ore":
			outline_blob(Vector2(32,38),Vector2(22,15),Color("8d8f8c"),ink)
			for p in [Vector2(24,34),Vector2(36,30),Vector2(40,42)]: draw_colored_polygon(PackedVector2Array([p+Vector2(0,-7),p+Vector2(5,0),p+Vector2(0,6),p+Vector2(-5,0)]),Color("e38f4c"))
		"shell":
			for i in 7:
				var a := PI+0.35+i*0.38
				_leaf(Vector2(32,48),a,28,6,Color("f6c8b6").lerp(Color("fbeee4"),float(i%2)))
			blob(Vector2(32,48),Vector2(7,4),Color("e2a993"))
		"conch":
			draw_colored_polygon(PackedVector2Array([Vector2(12,40),Vector2(46,20),Vector2(54,34),Vector2(40,52)]),Color("f0d2a8"))
			for i in 3: draw_line(Vector2(22+i*9,36-i*5),Vector2(28+i*9,48-i*4),Color("c99a6a"),2)
			blob(Vector2(48,36),Vector2(8,10),Color("f6b6a6"))
		"pearl":
			blob(Vector2(32,40),Vector2(20,9),Color("8bc2d6"))
			outline_blob(Vector2(32,32),Vector2(12,12),Color("f7f3fb"),Color("b7aecb"))
			blob(Vector2(28,28),Vector2(4,4),Color.WHITE)
		"flower":
			draw_line(Vector2(32,58),Vector2(32,32),Color("5f9c47"),3)
			for k in 5: blob(Vector2(32,26)+Vector2.from_angle(TAU*k/5-PI/2)*10,Vector2(8,8),Color("f28fb6"))
			blob(Vector2(32,26),Vector2(6,6),Color("f6cf47"))
		"mushroom","gold_mushroom":
			var cap := Color("d9473d") if item=="mushroom" else Color("f0bf3a")
			draw_rect(Rect2(26,32,12,22),Color("f3e8d2"))
			draw_colored_polygon(PackedVector2Array([Vector2(8,36),Vector2(16,18),Vector2(32,12),Vector2(48,18),Vector2(56,36)]),cap)
			for p in [Vector2(22,24),Vector2(38,20),Vector2(44,30)]: blob(p,Vector2(4,3),Color("fff7ec"))
		"branch":
			draw_line(Vector2(10,46),Vector2(54,22),Color("8a6443"),6)
			draw_line(Vector2(34,35),Vector2(42,48),Color("8a6443"),4)
			_leaf(Vector2(42,48),PI*0.35,14,5,Color("9bbf5c"))
		_:
			outline_blob(Vector2(32,34),Vector2(16,16),Color("c9d58f"),ink)

func _leaf(base: Vector2, angle: float, length: float, width: float, color: Color) -> void:
	var dir := Vector2.from_angle(angle)
	var side := dir.orthogonal()
	draw_colored_polygon(PackedVector2Array([base,base+dir*length*0.5+side*width,base+dir*length,base+dir*length*0.5-side*width]),color)

func _crop(kind: String, c: Vector2, k: float) -> void:
	var ink := Color("3b2a1c")
	match kind:
		"turnip":
			for i in 3: _leaf(c+Vector2(0,-10)*k,-PI/2+(i-1)*0.5,22*k,6*k,Color("6aac5a"))
			outline_blob(c+Vector2(0,4)*k,Vector2(14,13)*k,Color("f1ece6"),ink)
			blob(c+Vector2(0,-3)*k,Vector2(13,6)*k,Color("b05aa0"))
		"carrot":
			for i in 3: _leaf(c+Vector2(0,-12)*k,-PI/2+(i-1)*0.35,20*k,4*k,Color("4f9a48"))
			draw_colored_polygon(PackedVector2Array([c+Vector2(-9,-12)*k,c+Vector2(9,-12)*k,c+Vector2(0,22)*k]),Color("ee8a2f"))
		"pumpkin":
			for i in 3: outline_blob(c+Vector2((i-1)*9,2)*k,Vector2(11,14)*k,Color("e8862e").lerp(Color("f29a3a"),float(i%2)),ink)
			draw_rect(Rect2(c+Vector2(-2,-17)*k,Vector2(4,7)*k),Color("6b5a2c"))
		"strawberry":
			draw_colored_polygon(PackedVector2Array([c+Vector2(-14,-6)*k,c+Vector2(14,-6)*k,c+Vector2(0,20)*k]),Color("e0333f"))
			blob(c+Vector2(0,-6)*k,Vector2(14,5)*k,Color("e0333f"))
			for i in 3: _leaf(c+Vector2(0,-9)*k,-PI/2+(i-1)*0.8,10*k,4*k,Color("56a043"))
			for p in [Vector2(-5,0),Vector2(4,3),Vector2(0,10)]: blob(c+p*k,Vector2(1.5,1.5)*k,Color("fbe6a0"),6)
		"sunflower":
			for i in 12: blob(c+Vector2.from_angle(TAU*i/12)*13*k,Vector2(6,6)*k,Color("f6c531"))
			blob(c,Vector2(9,9)*k,Color("6a4325"))

func _fish(c: Vector2, dark: bool) -> void:
	var look: Array=Art.FISH_LOOK[item]
	var body: Color=look[0]; var belly: Color=look[1]; var accent: Color=look[2]
	var ratio: float=look[3]; var shape: String=look[4]
	if dark:
		body=Color("3a4650"); belly=body; accent=body
	var length := 44.0 if shape!="eel" else 56.0
	var h := clampf(length/ratio,8,30)
	if shape=="squid":
		draw_colored_polygon(PackedVector2Array([c+Vector2(-26,0),c+Vector2(4,-12),c+Vector2(8,12)]),body)
		for i in 5: draw_line(c+Vector2(6,-8+i*4),c+Vector2(26,-12+i*6),accent,3)
		if not dark: blob(c+Vector2(2,-3),Vector2(3,3),Color("1c1c22"))
		return
	var tail := c+Vector2(-length*0.5,0)
	if shape!="eel": draw_colored_polygon(PackedVector2Array([tail+Vector2(6,0),tail+Vector2(-8,-h*0.6),tail+Vector2(-5,0),tail+Vector2(-8,h*0.6)]),body.darkened(0.15))
	blob(c+Vector2(0,-h*0.42),Vector2(length*0.2,h*0.25),accent if shape!="puffer" else body)
	blob(c,Vector2(length*0.5,h*0.5),body,24)
	if not dark:
		blob(c+Vector2(2,h*0.15),Vector2(length*0.4,h*0.28),belly,20)
		match shape:
			"striped":
				for i in 4: draw_line(c+Vector2(-12+i*8,-h*0.42),c+Vector2(-14+i*8,h*0.05),accent,3)
			"spotted":
				for i in 6: blob(c+Vector2(-14+i*6,-h*0.2+(i%2)*4),Vector2(2.5,2.5),accent,8)
			"rainbow": draw_line(c+Vector2(-length*0.4,0),c+Vector2(length*0.42,-2),accent,4)
			"puffer":
				for i in 10:
					var d := Vector2.from_angle(TAU*i/10)
					draw_line(c+d*Vector2(length*0.5,h*0.5),c+d*Vector2(length*0.62,h*0.62),belly.darkened(0.3),2)
			"whisker":
				for s in [-1,1]: draw_line(c+Vector2(length*0.45,2),c+Vector2(length*0.62,2+s*8),accent,2)
		blob(c+Vector2(length*0.32,-h*0.12),Vector2(3.4,3.4),Color.WHITE,10)
		blob(c+Vector2(length*0.33,-h*0.12),Vector2(2,2),Color("1c1c22"),8)
