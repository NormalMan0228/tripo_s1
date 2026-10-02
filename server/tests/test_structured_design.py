import asyncio,copy,json
import httpx,pytest
from server.structured_design import SCHEMA,canonical,parse_structured
from server.asset_assembly import demo_design
from server.asset_vm import ProgramError
from server.config import Settings
from server.design_provider import DesignProvider

def wire_fixture():
    plan,program=demo_design('flower')
    wire={'plan':plan,'program':{'version':program['version'],
        'state':[{'name':name,'value':value} for name,value in program['state'].items()],
        'functions':[{'name':name,'params':value['params'],'body':value['body'],'returns':value['return']} for name,value in program['functions'].items()],
        'events':[{'name':name,'body':body} for name,body in program['events'].items()]}}
    return wire,plan,program

def test_structured_wire_preserves_generated_names_and_program_exactly():
    wire,plan,program=wire_fixture()
    result=json.loads(canonical(json.dumps(wire)))
    assert result=={'plan':plan,'program':program}
    p,v,report=parse_structured(json.dumps(wire))
    assert p==plan and v==program and report
    def inspect(schema):
        if isinstance(schema,dict):
            if schema.get('type')=='object':
                assert schema['additionalProperties'] is False
                assert set(schema['required'])==set(schema['properties'])
            for value in schema.values():inspect(value)
        elif isinstance(schema,list):
            for value in schema:inspect(value)
    inspect(SCHEMA)

@pytest.mark.parametrize('collection',['state','functions','events'])
def test_wire_rejects_duplicate_names_instead_of_silently_overwriting(collection):
    wire,_,_=wire_fixture();wire['program'][collection].append(copy.deepcopy(wire['program'][collection][0]))
    with pytest.raises(ProgramError,match='duplicate_wire_name'):parse_structured(json.dumps(wire))

def test_wire_does_not_bypass_vm_capabilities_or_numeric_validation():
    wire,_,_=wire_fixture();wire['program']['events'][0]['body']=[['emit','grant_currency','stem',100]]
    with pytest.raises(ProgramError):parse_structured(json.dumps(wire))
    wire,_,_=wire_fixture();wire['program']['state'][0]['value']=True
    with pytest.raises(ProgramError):parse_structured(json.dumps(wire))

def test_responses_uses_strict_schema_and_converts_before_vm_validation(tmp_path):
    wire,plan,program=wire_fixture();seen=[]
    def handle(request):
        body=json.loads(request.content);seen.append(body)
        assert body['text']['format']=={'type':'json_schema','name':'furniture_design','strict':True,'schema':SCHEMA}
        assert 'SERIALIZATION OVERRIDE' in body['input'][0]['content'][0]['text']
        assert 'private-test-key' not in request.content.decode()
        return httpx.Response(200,json={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(wire)}]}],'usage':{'input_tokens':100,'output_tokens':200}})
    settings=Settings(data_dir=tmp_path,studio_llm='openai',studio_design_format='structured',llm_key='private-test-key')
    p,v,meta=asyncio.run(DesignProvider(settings,httpx.MockTransport(handle)).generate('flower','gpt-6-luna','high'))
    assert len(seen)==1 and p==plan and v==program and meta['format']=='structured'
