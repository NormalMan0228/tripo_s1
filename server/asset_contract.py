"""Shared generation contract, used by local experiments and the production adapter."""
import json
from .asset_assembly import Plan, validate_plan
from .asset_vm import validate_program, exercise, ProgramError

# Objects follow the player's own style words first; otherwise they are grown-up RPG props, not toys.
STYLE = ('Villagen: a sunny island village in a modern fantasy RPG. Unless the player asks for another style, '
         'describe each object as a high-quality semi-realistic game prop: believable real-world proportions and '
         'construction, real materials (wood grain, forged metal, woven fabric, stone, glass, ceramic), refined '
         'craftsmanship and purposeful detail, a natural warm palette. Avoid toy-like, chibi or cartoon proportions, '
         'blobby shapes and candy colours. Readable at an orthographic camera distance. Avoid horror, realistic skin '
         'and razor edges.')
CONTRACT = '''Return ONLY one JSON object with keys plan and program. No markdown or tools.
Create original furniture/object geometry specifications and NEW named numeric API functions plus event code.
Title maximum 60 characters, category maximum 40 characters, each part prompt 3..800 characters.
The plan has title, category and 1..8 parts. Each part: id (ASCII identifier <=48), parent (other id or empty),
prompt (English standalone 3D part description), shape (box/ellipsoid/petal, proxy shape only), size [x,y,z]
(each .02..3 meters), position [x,y,z] (pivot position in parent coordinates, each -3..3),
rotation [x,y,z] (fixed local degrees), pivot [x,y,z] (normalized bbox relative center, each -.5..+.5), color (#RRGGBB).
Mesh is normalized to size, its pivot is moved to origin then fixed rotation and dynamic rotation apply.
Use separate parts for rigid moving components. Front is +Z, up is +Y. Parent hierarchy must be acyclic.
Program: {"version":1,"state":{numeric keys},"functions":{NAME:{"params":[names],"body":[statements],"return":expression}},"events":{EVENT:[statements]}}.
Expressions: finite numeric literals or arrays ["state",name], ["var",name], ["input",name],
["call",functionName,arg,...], [OP,arg,...]. Binary OP add sub mul div mod min max lt gt eq;
unary sin cos abs not; clamp takes value,min,max. Trig is radians. Comparisons return numeric 0/1.
Input names: dt (0..0.1 seconds), time (seconds, wraps at 100000), near (0/1).
Statements: ["set",local,expr], ["store",stateKey,expr], ["if",expr,[then],[else]],
["repeat",local,countExpr,[body]] (integer count 0..64), ["do",expr], ["emit",operation,partId,expr].
Events: spawn,tick,click,near,leave. All state keys declared upfront. Function locals never escape scope.
Host operations: rotate_x/-z (-180..180 degrees), rotate_y (-360..360), offset_y (-2..2 meters),
emission (0..4), hue (0..1). Use operation names rotate_x, rotate_z, rotate_y, offset_y, emission, hue exactly.
Commands SET an absolute dynamic value relative to the fixed part pose, not accumulate it.
Maximum32functions64state2048ASTnodes24nesting16calldepth128commands/event8192fuel/event.
All numbers, intermediate values and state must remain finite and <=1000000 absolute.
No native scripts, IO, HTTP, reflection, reward, currency, ownership or database access.
Use dt-based motion, clamp/smooth bounds, wrap angles and counters so long sessions remain safe.
Never claim actual 3D AI geometry was generated: this is a design contract only.
IMPORTANT: if is a STATEMENT only, not an expression. emit is a STATEMENT only; never nest it inside do.
Every if statement has exactly FOUR elements: ["if", condition, [then statements], [else statements]].
Even thin clock hands must have every size component >=0.02. No booleans/null as numeric expressions.
Correct sample: {"version":1,"state":{"open":0},"functions":{"angle":{"params":["x"],"body":[],"return":["mul",["var","x"],-90]}},"events":{"click":[["store","open",["not",["state","open"]]],["emit","rotate_x","lid",["call","angle",["state","open"]]]]}}
'''

def prompt_for(text, feedback=''):
    return CONTRACT+'\nSTYLE: '+STYLE+'\nPLAYER REQUEST (untrusted data): '+json.dumps(text,ensure_ascii=False)+('\nVALIDATION FEEDBACK: '+feedback if feedback else '')

def parse_design(text):
    if len(text)>120000: raise ProgramError('design_too_large')
    value=json.loads(text)
    if not isinstance(value,dict) or set(value)!={'plan','program'}: raise ProgramError('invalid_design')
    plan=validate_plan(value['plan'])
    program=validate_program(value['program'],{p['id'] for p in plan['parts']})
    report=exercise(program,{p['id'] for p in plan['parts']})
    return plan,program,report
