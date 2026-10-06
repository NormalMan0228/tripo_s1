import asyncio,json
import httpx,pytest
from server.design_provider import DesignProvider
from server.asset_assembly import demo_design
from server.config import Settings
from server.provider import ProviderError

def reply(plan,program,**extra):
    return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'thinking','thought':True},{'text':json.dumps({'plan':plan,'program':program})}]}}],
            'usageMetadata':{'promptTokenCount':11000,'candidatesTokenCount':900,'thoughtsTokenCount':300},**extra}

def test_gemini_contract_falls_back_on_unknown_model_and_keeps_key_in_header(tmp_path):
    plan,program=demo_design('chest');seen=[]
    def handle(request):
        seen.append(request)
        assert request.url.host=='generativelanguage.googleapis.com'
        assert 'test-gemini-key' not in str(request.url) and 'test-gemini-key' not in request.content.decode()
        body=json.loads(request.content)
        assert body['generationConfig']['responseMimeType']=='application/json'
        if 'gemini-new' in str(request.url):return httpx.Response(404,json={'error':{'message':'not found for API version'}})
        return httpx.Response(200,json=reply(plan,program))
    settings=Settings(data_dir=tmp_path,studio_llm='gemini',gemini_key='test-gemini-key',gemini_models=('gemini-new','gemini-old'))
    provider=DesignProvider(settings,httpx.MockTransport(handle))
    _,_,meta=asyncio.run(provider.generate('wooden chest','gpt-6-luna','high'))
    assert meta['provider']=='gemini' and meta['model']=='gemini-old'
    assert meta['usage']['input_tokens']==11000 and meta['usage']['output_tokens']==900
    assert all(r.headers['x-goog-api-key']=='test-gemini-key' for r in seen)
    assert 'test-gemini-key' not in repr(settings)
    # The model that answered is remembered: the next design asks it first.
    seen.clear()
    asyncio.run(provider.generate('lamp','gpt-6-luna','high'))
    assert 'gemini-old' in str(seen[0].url)

def test_gemini_reference_image_is_inline(tmp_path):
    from server.asset_assembly import _png
    import base64
    plan,program=demo_design('chest');bodies=[]
    def handle(request):
        bodies.append(json.loads(request.content));return httpx.Response(200,json=reply(plan,program))
    image='data:image/png;base64,'+base64.b64encode(_png()).decode()
    settings=Settings(data_dir=tmp_path,studio_llm='gemini',gemini_key='k',gemini_models=('gemini-x',))
    asyncio.run(DesignProvider(settings,httpx.MockTransport(handle)).generate('chest','gpt-6-luna','high',image))
    inline=bodies[0]['contents'][0]['parts'][1]['inline_data']
    assert inline['mime_type']=='image/png' and inline['data']==image.split(',',1)[1]

@pytest.mark.parametrize('response,code',[
    (httpx.Response(429,text='quota exceeded for sensitive project'),'llm_rate_limited'),
    (httpx.Response(503,text='sensitive: model is experiencing high demand'),'llm_busy'),
    (httpx.Response(403,text='sensitive upstream body'),'llm_request_failed'),
    (httpx.Response(200,json={'candidates':[{'finishReason':'SAFETY'}]}),'llm_incomplete'),
    (httpx.Response(404,json={}),'llm_model_unavailable')])
def test_gemini_errors_are_sanitized(tmp_path,response,code):
    settings=Settings(data_dir=tmp_path,studio_llm='gemini',gemini_key='secret',gemini_models=('gemini-x',))
    provider=DesignProvider(settings,httpx.MockTransport(lambda r:response));provider.retry_pause=0
    with pytest.raises(ProviderError) as error:
        asyncio.run(provider.generate('a chest','gpt-6-luna','high'))
    assert str(error.value)==code and 'sensitive' not in str(error.value) and 'secret' not in str(error.value)


def test_gemini_busy_or_limited_models_fall_through_and_retry(tmp_path):
    plan,program=demo_design('chest');calls=[]
    def handle(request):
        name=str(request.url).rsplit('/',1)[1].split(':')[0];calls.append(name)
        if name=='busy-model':return httpx.Response(503,json={'error':{'message':'high demand'}})
        if name=='limited-model':return httpx.Response(429,json={})
        if name=='gone-model':return httpx.Response(404,json={})
        # The good model is busy the first time, then answers on the retry round.
        if calls.count('good-model')==1:return httpx.Response(503,json={})
        return httpx.Response(200,json=reply(plan,program))
    settings=Settings(data_dir=tmp_path,studio_llm='gemini',gemini_key='k',
                      gemini_models=('busy-model','gone-model','limited-model','good-model'))
    provider=DesignProvider(settings,httpx.MockTransport(handle));provider.retry_pause=0
    _,_,meta=asyncio.run(provider.generate('chest','gpt-6-luna','high'))
    assert meta['model']=='good-model'
    assert calls==['busy-model','gone-model','limited-model','good-model','busy-model','gone-model','limited-model','good-model']

def test_live_paid_gemini_requires_key(tmp_path):
    settings=Settings(data_dir=tmp_path,mode='live',registration_code='x'*30,paid_enabled=True,tripo_key='t',studio_llm='gemini',gemini_key='')
    with pytest.raises(ValueError):settings.validate()
    Settings(data_dir=tmp_path,mode='live',registration_code='x'*30,paid_enabled=True,tripo_key='t',studio_llm='gemini',gemini_key='g').validate()
