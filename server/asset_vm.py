"""Bounded numeric bytecode interpreter for generated APIs and behaviors.

Programs are data. No Python/GDScript eval, object reflection, imports, filesystem,
network or database capability is available to them. Host commands are proposals.
"""
import copy
import json
import math
import re


class ProgramError(ValueError):
    # Runtime callers receive the stable public code. Generation validation can
    # additionally use an allowlisted reason without exposing exception contents.
    def __init__(self, code, reason=None):
        super().__init__(code)
        self.reason = reason


def rejection_reason(error):
    if isinstance(error, ProgramError):
        if str(error) in {'command_range_'+operation for operation in HOST_LIMITS}:return str(error)
        return str(error) if str(error) in {'fuel_exhausted','call_depth','locals_limit','loop_limit','command_limit','invalid_number'} else 'invalid_operation'
    if isinstance(error, ZeroDivisionError): return 'division_by_zero'
    if isinstance(error, KeyError): return 'undefined_local'
    return 'invalid_operation'


NAME = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,47}$')
HOST_LIMITS = {'rotate_x': (-180, 180), 'rotate_y': (-360, 360),
               'rotate_z': (-180, 180), 'offset_y': (-2, 2),
               'emission': (0, 4), 'hue': (0, 1)}
ARITY = {'add': 2, 'sub': 2, 'mul': 2, 'div': 2, 'mod': 2,
         'min': 2, 'max': 2, 'lt': 2, 'gt': 2, 'eq': 2,
         'sin': 1, 'cos': 1, 'abs': 1, 'not': 1, 'clamp': 3}
INPUTS = {'dt', 'time', 'near'}
EVENTS = {'spawn', 'tick', 'click', 'near', 'leave'}


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e6:
        raise ProgramError('invalid_number')
    return float(value)


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ProgramError('invalid_identifier')
    return value


def validate_program(program, targets):
    try:
        encoded = json.dumps(program, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        raise ProgramError('invalid_program') from None
    if len(encoded) > 65536 or not isinstance(program, dict):
        raise ProgramError('program_too_large')
    if set(program) != {'version', 'state', 'functions', 'events'} or type(program['version']) is not int or program['version'] != 1:
        raise ProgramError('invalid_program_header')
    for key, limit in [('state', 64), ('functions', 32), ('events', 5)]:
        if not isinstance(program[key], dict) or len(program[key]) > limit:
            raise ProgramError('invalid_program_header')
    for k, v in program['state'].items():
        name(k); number(v)
    if set(program['events']) - EVENTS:
        raise ProgramError('unsupported_event')
    nodes = [0]

    def budget(depth):
        nodes[0] += 1
        if depth > 24 or nodes[0] > 2048:
            raise ProgramError('program_complexity')

    def expr(e, depth=0):
        budget(depth)
        if type(e) in (float, int):
            number(e); return
        if not isinstance(e, list) or not e or not isinstance(e[0], str):
            raise ProgramError('invalid_expression')
        op = e[0]
        if op in ('state', 'var', 'input'):
            if len(e) != 2: raise ProgramError('invalid_expression')
            name(e[1])
            if op == 'state' and e[1] not in program['state']: raise ProgramError('unknown_state')
            if op == 'input' and e[1] not in INPUTS: raise ProgramError('unknown_input')
        elif op == 'call':
            if len(e) < 2: raise ProgramError('unknown_function')
            name(e[1])
            if e[1] not in program['functions']: raise ProgramError('unknown_function')
            f = program['functions'][e[1]]
            if len(e) - 2 != len(f['params']): raise ProgramError('argument_count')
            for a in e[2:]: expr(a, depth + 1)
        elif op in ARITY and len(e) == ARITY[op] + 1:
            for a in e[1:]: expr(a, depth + 1)
        else:
            raise ProgramError('unsupported_expression')

    def statements(body, depth=0):
        budget(depth)
        if not isinstance(body, list) or len(body) > 128: raise ProgramError('invalid_body')
        for s in body:
            if not isinstance(s, list) or not s: raise ProgramError('invalid_statement')
            op = s[0]
            if op in ('set', 'store') and len(s) == 3:
                name(s[1])
                if op == 'store' and s[1] not in program['state']: raise ProgramError('unknown_state')
                expr(s[2], depth + 1)
            elif op == 'if' and len(s) == 4:
                expr(s[1], depth + 1); statements(s[2], depth + 1); statements(s[3], depth + 1)
            elif op == 'repeat' and len(s) == 4:
                name(s[1]); expr(s[2], depth + 1); statements(s[3], depth + 1)
            elif op == 'emit' and len(s) == 4:
                name(s[1]); name(s[2])
                if s[1] not in HOST_LIMITS or s[2] not in targets: raise ProgramError('capability_denied')
                expr(s[3], depth + 1)
            elif op == 'do' and len(s) == 2:
                expr(s[1], depth + 1)
            else:
                raise ProgramError('unsupported_statement')

    # Validate all signatures before following cross-function calls.
    for k, f in program['functions'].items():
        name(k)
        if not isinstance(f, dict) or set(f) != {'params', 'body', 'return'}: raise ProgramError('invalid_function')
        if not isinstance(f['params'], list) or len(f['params']) > 8: raise ProgramError('invalid_parameters')
        for p in f['params']: name(p)
        if len(set(f['params'])) != len(f['params']): raise ProgramError('duplicate_parameter')
    for f in program['functions'].values():
        statements(f['body']); expr(f['return'])
    for b in program['events'].values(): statements(b)
    return program


class AssetVM:
    def __init__(self, program, targets, state=None):
        self.program = copy.deepcopy(validate_program(program, set(targets)))
        self.state = dict(program['state'])
        if state is not None:
            if set(state) != set(self.state): raise ProgramError('state_mismatch')
            self.state = {k: number(v) for k, v in state.items()}

    def run(self, event, inputs=None, fuel=8192):
        if event not in EVENTS: raise ProgramError('unsupported_event')
        self.inputs = {'dt': 0, 'time': 0, 'near': 0}
        for k, v in (inputs or {}).items():
            if k not in INPUTS: raise ProgramError('unknown_input')
            self.inputs[k] = number(v)
        self.inputs['dt'] = max(0, min(.1, self.inputs['dt']))
        self.inputs['time'] = self.inputs['time'] % 100000
        self.inputs['near'] = max(0, min(1, self.inputs['near']))
        self.fuel, self.depth, self.commands = min(fuel, 8192), 0, []
        before = self.state.copy()
        try:
            self._body(self.program['events'].get(event, []), {})
            return self.commands
        except (ProgramError, ArithmeticError, KeyError, TypeError, ValueError, RecursionError) as error:
            self.state = before
            self.commands = []
            raise ProgramError('execution_rejected', rejection_reason(error)) from None

    def _spend(self):
        self.fuel -= 1
        if self.fuel < 0: raise ProgramError('fuel_exhausted')

    def invoke(self,function,args):
        """Object-local generated API call with numeric arguments and atomic rollback."""
        name(function)
        if function not in self.program['functions']:raise ProgramError('unknown_function')
        if not isinstance(args,list) or len(args)!=len(self.program['functions'][function]['params']):raise ProgramError('argument_count')
        args=[number(value) for value in args]
        self.inputs={'dt':0,'time':0,'near':0};self.fuel,self.depth,self.commands=8192,0,[]
        before=self.state.copy()
        try:return self._expr(['call',function,*args],{})
        except (ProgramError,ArithmeticError,KeyError,TypeError,ValueError,RecursionError) as error:
            self.state=before;self.commands=[]
            raise ProgramError('execution_rejected', rejection_reason(error)) from None

    def _expr(self, e, local):
        self._spend()
        if type(e) in (int, float): return number(e)
        op = e[0]
        if op == 'state': return self.state[e[1]]
        if op == 'var': return local[e[1]]
        if op == 'input': return self.inputs[e[1]]
        if op == 'call':
            self.depth += 1
            if self.depth > 16: raise ProgramError('call_depth')
            f = self.program['functions'][e[1]]
            scope = dict(zip(f['params'], [self._expr(a, local) for a in e[2:]]))
            self._body(f['body'], scope)
            result = self._expr(f['return'], scope)
            self.depth -= 1
            return result
        a = [self._expr(v, local) for v in e[1:]]
        functions = {'add': lambda: a[0]+a[1], 'sub': lambda: a[0]-a[1],
            'mul': lambda: a[0]*a[1], 'div': lambda: a[0]/a[1], 'mod': lambda: a[0]%a[1],
            'min': lambda: min(a), 'max': lambda: max(a), 'sin': lambda: math.sin(a[0]),
            'cos': lambda: math.cos(a[0]), 'abs': lambda: abs(a[0]),
            'lt': lambda: float(a[0]<a[1]), 'gt': lambda: float(a[0]>a[1]),
            'eq': lambda: float(a[0]==a[1]), 'not': lambda: float(not a[0]),
            'clamp': lambda: max(a[1], min(a[2], a[0]))}
        return number(functions[op]())

    def _body(self, body, local):
        for s in body:
            self._spend(); op = s[0]
            if op == 'set':
                if s[1] not in local and len(local) >= 64: raise ProgramError('locals_limit')
                local[s[1]] = self._expr(s[2], local)
            elif op == 'store': self.state[s[1]] = self._expr(s[2], local)
            elif op == 'if': self._body(s[2] if self._expr(s[1], local) else s[3], local)
            elif op == 'repeat':
                if s[1] not in local and len(local) >= 64: raise ProgramError('locals_limit')
                count = self._expr(s[2], local)
                if count != int(count) or not 0 <= count <= 64: raise ProgramError('loop_limit')
                for i in range(int(count)):
                    self._spend(); local[s[1]] = i; self._body(s[3], local)
            elif op == 'do': self._expr(s[1], local)
            elif op == 'emit':
                value = self._expr(s[3], local)
                lo, hi = HOST_LIMITS[s[1]]
                if not lo <= value <= hi:raise ProgramError('command_range_'+s[1])
                if len(self.commands) >= 128:raise ProgramError('command_limit')
                self.commands.append({'op': s[1], 'target': s[2], 'value': value})


def exercise(program, targets):
    """Reject obvious failures before publication; not a proof of visual correctness."""
    vm = AssetVM(program, targets)
    count = len(vm.run('spawn'))
    for i in range(120):
        if i % 30 == 0: count += len(vm.run('click'))
        if i == 10: count += len(vm.run('near', {'near': 1}))
        if i == 90: count += len(vm.run('leave'))
        count += len(vm.run('tick', {'dt': 1/60, 'time': i/60, 'near': float(10<=i<90)}))
    return {'events_evaluated': 127, 'commands_checked': count, 'finite': True}


def exercise_extended(program, targets):
    """A bounded publication gate, not proof of arbitrary program correctness.

    Simulates 60 seconds of accumulated state, repeated interactions and time
    boundaries. Jumping the clock does not simulate a day of accumulated state.
    Historical model benchmarks deliberately retain the original short gate.
    """
    vm = AssetVM(program, targets)
    events = commands = 0
    def step(event, inputs=None):
        nonlocal events, commands
        events += 1
        try: commands += len(vm.run(event, inputs))
        except ProgramError as error:
            raise ProgramError(f'publication_check:{event}:{events}:{error.reason or "execution_rejected"}') from None
    step('spawn')
    for i in range(600):
        near = float((i // 75) % 2)
        if i % 75 == 0: step('near' if near else 'leave', {'near':near})
        if i % 10 == 0: step('click', {'near':near})
        step('tick', {'dt':.1,'time':i*.1,'near':near})
    for t in (3600,86400,99999.95,100000,100000.05):
        for dt in (0,1/120,1/30,.1):
            step('tick', {'dt':dt,'time':t,'near':1})
    for i in range(64):step('click', {'near':float(i%2)})
    step('leave')
    return {'suite':'publication_v2','events_evaluated':events,'commands_checked':commands,
            'accumulated_seconds':60,'clock_boundary_seconds':100000,'finite':True}
