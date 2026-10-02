import asyncio,json
import httpx,pytest
from server.design_provider import DesignProvider
from server.asset_assembly import demo_design
from server.config import Settings
from server.provider import ProviderError,TripoProvider

def test_responses_contract_and_secret_stays_in_server_header(tmp_path):
    plan,program=demo_design('chest');seen=[]
    def handle(request):
        seen.append(request)
        assert request.url=='https://api.openai.com/v1/responses'
        body=json.loads(request.content)
        assert body['store'] is False and body['max_output_tokens']==12000
        assert body['reasoning']=={'effort':'medium'}
        assert body['text']['format']['type']=='json_object'
        assert 'test-private-key' not in request.content.decode()
        return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'plan':plan,'program':program})}]}],'usage':{'input_tokens':400,'output_tokens':300}})
    settings=Settings(data_dir=tmp_path,studio_llm='openai',llm_key='test-private-key')
    a,b,meta=asyncio.run(DesignProvider(settings,httpx.MockTransport(handle)).generate('wooden chest','gpt-6-luna','medium'))
    assert meta['provider']=='openai' and meta['usage']['output_tokens']==300
    assert seen[0].headers['authorization']=='Bearer test-private-key'
    assert 'test-private-key' not in repr(settings)

@pytest.mark.parametrize('response',[httpx.Response(401,text='sensitive upstream body'),httpx.Response(200,json={'status':'incomplete'}),httpx.Response(200,json={'status':'completed','output':[]})])
def test_provider_errors_are_sanitized(tmp_path,response):
    settings=Settings(data_dir=tmp_path,studio_llm='openai',llm_key='secret')
    with pytest.raises(ProviderError) as error:
        asyncio.run(DesignProvider(settings,httpx.MockTransport(lambda r:response)).generate('a chest','gpt-6-luna','low'))
    assert 'sensitive' not in str(error.value) and 'secret' not in str(error.value)

def test_reference_upload_uses_private_api_header_and_no_download_auth(tmp_path):
    from server.asset_assembly import _png
    import base64
    image='data:image/png;base64,'+base64.b64encode(_png()).decode()
    def handle(request):
        assert request.url.path=='/v3/files' and request.headers['authorization']=='Bearer private'
        assert b'reference.png' in request.content
        return httpx.Response(200,json={'code':0,'data':{'file_token':'file_test'}})
    provider=TripoProvider(Settings(data_dir=tmp_path,tripo_key='private'),httpx.MockTransport(handle))
    assert asyncio.run(provider.upload_image(image))=='file_test'

def test_invalid_design_gets_one_repair_and_counts_both_calls(tmp_path):
    plan,program=demo_design('clock');calls=[]
    def handle(request):
        body=json.loads(request.content);calls.append(body)
        raw='{"plan":{},"program":{}}' if len(calls)==1 else json.dumps({'plan':plan,'program':program})
        if len(calls)==2:assert 'VALIDATION FEEDBACK' in body['input'][0]['content'][0]['text']
        return httpx.Response(200,json={'status':'completed','output':[{'content':[{'type':'output_text','text':raw}]}],'usage':{'input_tokens':100,'output_tokens':50}})
    settings=Settings(data_dir=tmp_path,studio_llm='openai',llm_key='private')
    _,_,meta=asyncio.run(DesignProvider(settings,httpx.MockTransport(handle)).generate('clock','gpt-6-luna','low'))
    assert len(calls)==2 and meta['usage']=={'input_tokens':200,'output_tokens':100}
    assert 'validation_error' in meta['attempts'][0] and meta['attempts'][1]['valid']

def test_invalid_design_repair_has_hard_limit(tmp_path):
    calls=[]
    def handle(request):
        calls.append(1)
        return httpx.Response(200,json={'status':'completed','output':[{'content':[{'type':'output_text','text':'{}'}]}]})
    settings=Settings(data_dir=tmp_path,studio_llm='openai',llm_key='private')
    with pytest.raises(ProviderError,match='llm_invalid_design') as failed:
        asyncio.run(DesignProvider(settings,httpx.MockTransport(handle)).generate('clock','gpt-6-luna','low'))
    assert len(calls)==2
    assert len(failed.value.attempts)==2
    assert all('validation_error' in row for row in failed.value.attempts)


def test_long_running_failure_repairs_before_any_geometry_request(tmp_path):
    plan,good=demo_design('clock');bad=json.loads(json.dumps(good));calls=[]
    bad['events']={'tick':[['emit','rotate_z',plan['parts'][1]['id'],['input','time']]]}
    def handle(request):
        body=json.loads(request.content);calls.append(body)
        if len(calls)==2:
            feedback=body['input'][0]['content'][0]['text']
            assert 'publication_check:tick' in feedback and 'command_range_rotate_z' in feedback
            assert 'NOT a command-count error' in feedback and '[-180,180]' in feedback
        return httpx.Response(200,json={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'plan':plan,'program':bad if len(calls)==1 else good})}]}],'usage':{'input_tokens':200,'output_tokens':150}})
    settings=Settings(data_dir=tmp_path,studio_llm='openai',llm_key='private')
    _,_,meta=asyncio.run(DesignProvider(settings,httpx.MockTransport(handle)).generate('clock','gpt-6-luna','high'))
    assert meta['usage']=={'input_tokens':400,'output_tokens':300}
    assert meta['validation']['publication']['events_evaluated']==754
