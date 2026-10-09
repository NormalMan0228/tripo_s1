"""Closed JSON-schema wire format; dynamic names remain data, never native code."""
import json
from .asset_contract import CONTRACT,STYLE,parse_design
from .asset_vm import ProgramError

def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def array(items,maximum=64,minimum=0):
    return {'type':'array','items':items,'minItems':minimum,'maxItems':maximum}
def string(maximum=48):return {'type':'string','maxLength':maximum}
def vector(low,high):return array({'type':'number','minimum':low,'maximum':high},3,3)
VALUE={'$ref':'#/$defs/value'}
SCHEMA=obj({
    'plan':obj({'title':string(60),'category':string(40),'parts':array(obj({
        'id':string(),'parent':string(),'prompt':{'type':'string','minLength':3,'maxLength':800},
        'shape':{'type':'string','enum':['box','ellipsoid','petal']},
        'size':vector(.02,3),'position':vector(-3,3),'rotation':vector(-360,360),'pivot':vector(-.5,.5),
        'color':{'type':'string','pattern':'^#[0-9a-fA-F]{6}$'}}),8,1)}),
    'program':obj({'version':{'type':'integer','enum':[1]},
        'state':array(obj({'name':string(),'value':{'type':'number','minimum':-1000000,'maximum':1000000}})),
        'functions':array(obj({'name':string(),'params':array(string(),8),'body':array(VALUE),'returns':VALUE}),32),
        'events':array(obj({'name':{'type':'string','enum':['spawn','tick','click','near','leave']},'body':array(VALUE)}),5)})})
SCHEMA['$defs']={'value':{'anyOf':[{'type':'number'},{'type':'string'},array(VALUE,128)]}}

WIRE='''SERIALIZATION OVERRIDE: The instructions above describe the engine's internal form.
Your actual RESPONSE MUST use the attached JSON schema. Keep plan unchanged.
Represent program.state as [{"name":"open","value":0}] instead of a key/value object.
Represent program.functions as [{"name":"angle","params":["x"],"body":[],"returns":["mul",["var","x"],-90]}].
Represent program.events as [{"name":"click","body":[["store","open",["not",["state","open"]]]]}].
Names must be unique within each list. Empty state/functions/events use [] rather than {}.
Expression and statement arrays are unchanged. returns is the function's return expression.
Only serialize plan and this wire program. Do not include the internal object form or any tools.'''

def prompt_for_structured(prompt,feedback='',style=None):
    return CONTRACT+'\n'+WIRE+'\nSTYLE: '+(style or STYLE)+'\nPLAYER REQUEST (untrusted data): '+json.dumps(prompt,ensure_ascii=False)+('\nVALIDATION FEEDBACK: '+feedback if feedback else '')

def canonical(text):
    if len(text)>120000:raise ProgramError('design_too_large')
    value=json.loads(text)
    if not isinstance(value,dict) or set(value)!={'plan','program'}:raise ProgramError('invalid_design')
    program=value['program']
    if not isinstance(program,dict) or set(program)!={'version','state','functions','events'}:raise ProgramError('invalid_wire_program')
    limits={'state':64,'functions':32,'events':5};required={'state':{'name','value'},'functions':{'name','params','body','returns'},'events':{'name','body'}}
    normalized={'version':program['version'],'state':{},'functions':{},'events':{}}
    for field in limits:
        entries=program[field]
        if not isinstance(entries,list) or len(entries)>limits[field]:raise ProgramError('invalid_wire_collection')
        for entry in entries:
            if not isinstance(entry,dict) or set(entry)!=required[field] or not isinstance(entry.get('name'),str):raise ProgramError('invalid_wire_entry')
            name=entry['name']
            if name in normalized[field]:raise ProgramError('duplicate_wire_name')
            normalized[field][name]=entry['value'] if field=='state' else entry['body'] if field=='events' else {'params':entry['params'],'body':entry['body'],'return':entry['returns']}
    return json.dumps({'plan':value['plan'],'program':normalized},ensure_ascii=False)

def parse_structured(text):return parse_design(canonical(text))
