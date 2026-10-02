extends RefCounted
## Numeric data interpreter. Generated programs never become GDScript source.
const LIMITS := {"rotate_x":Vector2(-180,180),"rotate_y":Vector2(-360,360),"rotate_z":Vector2(-180,180),"offset_y":Vector2(-2,2),"emission":Vector2(0,4),"hue":Vector2(0,1)}
var program: Dictionary = {}
var state: Dictionary = {}
var inputs: Dictionary = {}
var commands: Array = []
var targets: Array = []
var fuel := 0
var depth := 0
var failed := false

func setup(value: Dictionary, ids: Array, initial: Dictionary = {}) -> void:
	program=value.duplicate(true)
	state=program.get("state",{}).duplicate(true)
	for key in initial:
		if state.has(key): state[key]=initial[key]
	targets=ids

func run(event: String, values: Dictionary = {}) -> Dictionary:
	var before := state.duplicate(true)
	if event not in ["spawn","tick","click","near","leave"]:
		return {"ok":false,"commands":[]}
	for key in values:
		if key not in ["dt","time","near"] or not (values[key] is int or values[key] is float):
			return {"ok":false,"commands":[]}
		if not is_finite(float(values[key])) or absf(float(values[key]))>1000000:
			return {"ok":false,"commands":[]}
	inputs={"dt":clampf(float(values.get("dt",0)),0,0.1),"time":fposmod(float(values.get("time",0)),100000),"near":clampf(float(values.get("near",0)),0,1)}
	fuel=8192; depth=0; failed=false; commands=[]
	_body(program.get("events",{}).get(event,[]),{})
	if failed:
		state=before
		commands=[]
	return {"ok":not failed,"commands":commands}

func _spend() -> bool:
	fuel-=1
	if fuel<0: failed=true
	return not failed

func _num(value: Variant) -> float:
	if not (value is int or value is float) or not is_finite(float(value)) or absf(float(value))>1000000:
		failed=true
		return 0
	return float(value)

func _expr(e: Variant, local: Dictionary) -> float:
	if not _spend(): return 0
	if e is int or e is float: return _num(e)
	if not e is Array or e.size()<2 or not e[0] is String:
		failed=true
		return 0
	var op: String=e[0]
	if op=="state": return _num(state.get(e[1],null))
	if op=="var": return _num(local.get(e[1],null))
	if op=="input": return _num(inputs.get(e[1],null))
	if op=="call":
		depth+=1
		if depth>16 or not program.get("functions",{}).has(e[1]):
			failed=true
			return 0
		var f: Dictionary=program.functions[e[1]]
		if e.size()-2!=f.params.size():
			failed=true
			return 0
		var scope := {}
		for i in f.params.size(): scope[f.params[i]]=_expr(e[i+2],local)
		_body(f.body,scope)
		var result := _expr(f["return"],scope)
		depth-=1
		return result
	var args: Array[float]=[]
	for i in range(1,e.size()): args.append(_expr(e[i],local))
	var arity: int={"sin":1,"cos":1,"abs":1,"not":1,"clamp":3}.get(op,2)
	if args.size()!=arity:
		failed=true
		return 0
	var a: float=args[0]
	var b: float=args[1] if args.size()>1 else 0.0
	var result := 0.0
	match op:
		"add": result=a+b
		"sub": result=a-b
		"mul": result=a*b
		"div":
			if b==0: failed=true
			else: result=a/b
		"mod":
			if b==0: failed=true
			else:
				# Avoid quotient rounding/cancellation (e.g. 1 % 0.1). Python's
				# modulo has the divisor's sign; fmod has the dividend's sign.
				result=fmod(a,b)
				if result!=0 and (result<0)!=(b<0):result+=b
		"min": result=minf(a,b)
		"max": result=maxf(a,b)
		"sin": result=sin(a)
		"cos": result=cos(a)
		"abs": result=absf(a)
		"not": result=1.0 if a==0 else 0.0
		"lt": result=1.0 if a<b else 0.0
		"gt": result=1.0 if a>b else 0.0
		"eq": result=1.0 if a==b else 0.0
		"clamp": result=maxf(b,minf(args[2],a))
		_: failed=true
	return _num(result)

func _body(body: Variant, local: Dictionary) -> void:
	if not body is Array or body.size()>128:
		failed=true
		return
	for s in body:
		if not _spend(): return
		if not s is Array or s.size()<2:
			failed=true
			return
		match s[0]:
			"set","store":
				if s.size()!=3: failed=true; return
				var value := _expr(s[2],local)
				if s[0]=="store":
					if not state.has(s[1]): failed=true; return
					state[s[1]]=value
				else:
					if not local.has(s[1]) and local.size()>=64: failed=true; return
					local[s[1]]=value
			"if":
				if s.size()!=4: failed=true; return
				_body(s[2] if _expr(s[1],local)!=0 else s[3],local)
			"repeat":
				if s.size()!=4: failed=true; return
				var count := _expr(s[2],local)
				if count!=floor(count) or count<0 or count>64 or (not local.has(s[1]) and local.size()>=64): failed=true; return
				for i in int(count):
					if not _spend(): return
					local[s[1]]=i
					_body(s[3],local)
			"do": _expr(s[1],local)
			"emit":
				if s.size()!=4 or not LIMITS.has(s[1]) or not targets.has(s[2]): failed=true; return
				var value := _expr(s[3],local)
				var bounds: Vector2=LIMITS[s[1]]
				if value<bounds.x or value>bounds.y or commands.size()>=128: failed=true; return
				commands.append({"op":s[1],"target":s[2],"value":value})
			_: failed=true; return
