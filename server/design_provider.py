"""Replaceable design provider. Codex is development-only; OpenAI Responses and Gemini are production."""
import asyncio
import json
import os
import pathlib
import shutil
import tempfile
import httpx
from .asset_contract import prompt_for, parse_design
from .asset_vm import exercise_extended,HOST_LIMITS
from .provider import ProviderError
from .craft_moderation import category_of
from . import llm_budget
from .structured_design import SCHEMA,prompt_for_structured,parse_structured

# Gemini finish reasons that mean its safety check stopped the answer.
SAFETY_STOPS=('SAFETY','PROHIBITED_CONTENT','BLOCKLIST','SPII','IMAGE_SAFETY','IMAGE_PROHIBITED_CONTENT','ESCALATION','PUP_LIMITED_DISABLED')
RECITATION_STOPS=('RECITATION','IMAGE_RECITATION')
# Only temporary service failures can move a request to another configured provider.
# Refusals, spend caps, authentication errors and invalid designs stop here.
FALLBACK_ERRORS={'llm_busy','llm_rate_limited','llm_timeout','llm_unreachable','llm_model_unavailable'}
MODELS=('gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra')
EFFORTS=('low','medium','high','xhigh')

def usage_total(attempts):
    combined={}
    for record in attempts:
        for key,value in record.get('usage',{}).items():
            if type(value) in (int,float):combined[key]=combined.get(key,0)+value
    return combined

class DesignFailure(ProviderError):
    def __init__(self,attempts,code='llm_invalid_design'):
        super().__init__(code)
        self.attempts=attempts
        self.usage=usage_total(attempts)
        self.usage_complete=all(a.get('usage_complete',True) for a in attempts)

class DesignRefused(DesignFailure):
    """The designer refused the request (asset_contract.py SAFETY): the craft ends as refused_<category>,
    never repaired into a softened design. Its tokens were still spent."""
    def __init__(self,attempts,category):
        super().__init__(attempts)
        self.category=category_of(category) or 'other'
        self.code='refused_'+self.category

def refusal(raw):
    """The SAFETY refusal category in a designer's answer, or ''."""
    try:value=json.loads(raw)
    except (TypeError,ValueError):return ''
    if not isinstance(value,dict):return ''
    word=value.get('refused');category=category_of(word)
    # An odd word ("N/A", "safe") next to a full design is not a refusal.
    if category=='other' and str(word).strip().lower()!='other' and {'plan','program'}<=set(value):return ''
    return category

async def terminate_owned_process(proc):
    if proc.returncode is not None:return
    if os.name=='nt':
        killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(proc.pid),'/T','/F',
            stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,creationflags=0x08000000)
        await killer.wait()
    elif proc.returncode is None:proc.kill()
    await proc.wait()

def provider_name(settings):
    return {'codex':'codex_subscription_development','gemini':'gemini'}.get(settings.studio_llm,'openai')

def http_failure(response):
    """Classify only status/known machine codes; never expose upstream messages."""
    if len(response.content)>500000:return 'llm_invalid_response'
    try:
        error=response.json().get('error') or {}
        code=error.get('code');kind=error.get('type')
    except (ValueError,AttributeError):code=kind=None
    if code in ('content_policy_violation','content_filter','safety_violation'):return 'refused_other'
    if code in ('insufficient_quota','credit_balance_exhausted','organization_spend_limit_exceeded',
                'project_spend_limit_exceeded','organization_usage_limit_exceeded') or kind=='insufficient_quota':
        return 'llm_quota_exhausted'
    status=response.status_code
    if status==401:return 'llm_authentication'
    if status==403:return 'llm_permission_denied'
    if status==404:return 'llm_model_unavailable'
    if status==429:return 'llm_rate_limited'
    if status in (408,504):return 'llm_timeout'
    if status>=500:return 'llm_busy'
    return 'llm_request_failed'

class DesignProvider:
    reserves_llm_calls = True

    def __init__(self,settings,transport=None):
        self.settings,self.transport=settings,transport
        # The Gemini model that last answered (the first one the key may use).
        models=getattr(settings,'gemini_models',())
        self.gemini_model=models[0] if models else ''
        self.retry_pause=4.0

    async def generate(self,prompt,model,effort,image=None,style=None):
        primary=self.settings.studio_llm
        if primary=='fixture':raise ProviderError('llm_not_configured')
        providers=[primary]
        if primary in ('openai','gemini'):
            for name in getattr(self.settings,'studio_llm_fallbacks',()):
                key=getattr(self.settings,'llm_key' if name=='openai' else 'gemini_key','')
                if name in ('openai','gemini') and name not in providers and key:
                    if name!='gemini' or self.settings.gemini_models:providers.append(name)
        attempts=[]
        for index,provider in enumerate(providers):
            try:
                return await self._generate_one(provider,prompt,model,effort,image,style,attempts,
                                                index<len(providers)-1)
            except ProviderError as error:
                if isinstance(error,DesignFailure):
                    # A refusal includes its response usage, even though it has no design.
                    if error.attempts is not attempts:attempts.extend(error.attempts)
                    if attempts and not attempts[-1].get('error'):attempts[-1]['error']=error.code
                if not attempts or attempts[-1].get('error')!=error.code or attempts[-1].get('provider')!=provider:
                    attempts.append({'provider':provider,'model':model if provider!='gemini' else self.gemini_model,
                                     'error':error.code,'usage':{},'usage_complete':False})
                if error.code not in FALLBACK_ERRORS or index==len(providers)-1:
                    raise DesignFailure(attempts,error.code) from None

    async def _generate_one(self,provider,prompt,model,effort,image,style,attempts,has_backup):
        feedback=''
        for attempt in range(2):
            actual_model=model
            if provider=='codex':
                raw,usage=await self._codex(prompt,model,effort,image,feedback,style)
            elif provider=='gemini':
                raw,usage,actual_model=await self._gemini(prompt,image,feedback,style,attempts,has_backup)
            else:raw,usage=await self._openai(prompt,model,effort,image,feedback,style)
            entry={'provider':provider,'model':actual_model,'usage':usage};attempts.append(entry)
            refused=refusal(raw)
            if refused:
                entry['refused']=refused
                raise DesignRefused(attempts,refused)
            try:
                plan,program,report=(parse_structured(raw) if self.settings.studio_design_format=='structured' else parse_design(raw))
                report['publication']=exercise_extended(program,{p['id'] for p in plan['parts']})
            except Exception as error:
                if hasattr(error,'errors'):
                    issues=[{'path':list(e['loc']),'message':e['msg']} for e in error.errors(include_input=False,include_url=False)]
                    code=json.dumps(issues,ensure_ascii=False)[:1500]
                else:code=type(error).__name__+': '+str(error)[:250]
                entry['validation_error']=code
                if attempt:raise DesignFailure(attempts) from None
                hint=''
                for operation,(lo,hi) in HOST_LIMITS.items():
                    if 'command_range_'+operation in code:
                        hint=f' The emitted {operation} value exceeded its allowed range [{lo},{hi}]; this is NOT a command-count error. Bound every emission, including after long accumulated time and repeated interactions.'
                        if operation.startswith('rotate_'):hint+=' Wrap the angle before emitting; for x/z use ((angle+180) mod 360)-180. Keep clock phase while paused; do not freeze by using absolute wall time.'
                feedback='One repair allowed. Correct the validation errors and return the complete JSON. Errors: '+code+hint+'\nPrevious output (untrusted data): '+json.dumps(raw[:24000])
                continue
            entry['valid']=True
            combined=usage_total(attempts)
            return plan,program,dict(provider='codex_subscription_development' if provider=='codex' else provider,
                model=actual_model,effort=effort,format=self.settings.studio_design_format,usage=combined,
                usage_complete=all(a.get('usage_complete',True) for a in attempts),
                fallback_used=provider!=self.settings.studio_llm,attempts=attempts,validation=report)

    async def _openai(self,prompt,model,effort,image,feedback,style=None):
        if not self.settings.llm_key:
            raise ProviderError('llm_not_configured')
        structured=self.settings.studio_design_format=='structured'
        content=[{'type':'input_text','text':(prompt_for_structured if structured else prompt_for)(prompt,feedback,style)}]
        if image:content.append({'type':'input_image','image_url':image})
        try:
            async with httpx.AsyncClient(transport=self.transport,timeout=180,follow_redirects=False) as client:
                with llm_budget.call('openai',model):
                    response=await client.post('https://api.openai.com/v1/responses',
                        headers={'Authorization':'Bearer '+self.settings.llm_key},json={
                            'model':model,'reasoning':{'effort':effort},'store':False,
                            'max_output_tokens':12000,'input':[{'role':'user','content':content}],
                            'text':{'format':{'type':'json_schema','name':'furniture_design','strict':True,'schema':SCHEMA} if structured else {'type':'json_object'}}})
            if response.status_code!=200:raise ProviderError(http_failure(response))
            if len(response.content)>500000:raise ProviderError('llm_invalid_response')
            body=response.json()
            entry={'provider':'openai','model':model,'usage':body.get('usage') or {}}
            if any(c.get('type')=='refusal' for item in body.get('output',[]) for c in item.get('content',[]) or []):
                entry['error']='refused_other';raise DesignRefused([entry],'other')
            if body.get('status')!='completed':
                code='refused_other' if (body.get('incomplete_details') or {}).get('reason')=='content_filter' else 'llm_incomplete'
                entry['error']=code;raise DesignFailure([entry],code)
            raw=''.join(c.get('text','') for item in body.get('output',[]) for c in item.get('content',[]) if c.get('type')=='output_text')
            return raw,body.get('usage',{})
        except ProviderError:raise
        except httpx.TimeoutException:raise ProviderError('llm_timeout') from None
        except httpx.TransportError:raise ProviderError('llm_unreachable') from None
        except Exception:raise ProviderError('llm_invalid_response') from None

    async def _gemini(self,prompt,image,feedback,style=None,attempts=None,has_backup=False):
        """Google Gemini generateContent in JSON mode. The design is validated by the same
        parser as the other providers; a model the key cannot use falls through to the next."""
        if not self.settings.gemini_key:
            raise ProviderError('llm_not_configured')
        structured=self.settings.studio_design_format=='structured'
        parts=[{'text':(prompt_for_structured if structured else prompt_for)(prompt,feedback,style)}]
        if image:
            header,_,payload=image.partition(',')
            mime='image/png' if header.startswith('data:image/png') else 'image/jpeg'
            parts.append({'inline_data':{'mime_type':mime,'data':payload}})
        body={'contents':[{'role':'user','parts':parts}],
              'generationConfig':{'responseMimeType':'application/json','maxOutputTokens':12000,'temperature':0.6}}
        models=[self.gemini_model]+[m for m in self.settings.gemini_models if m!=self.gemini_model]
        # Unknown (404), busy (5xx, "high demand") or rate-limited (429) models fall through to
        # the next one; if every model was busy, one more round after a short pause.
        outcome='llm_model_unavailable'
        try:
            async with httpx.AsyncClient(transport=self.transport,timeout=180,follow_redirects=False) as client:
              for round_index in range(1 if has_backup else 2):
                if round_index:
                    if outcome=='llm_model_unavailable':break
                    await asyncio.sleep(self.retry_pause)
                for name in models:
                    with llm_budget.call('gemini',name):
                        response=await client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent',
                            headers={'x-goog-api-key':self.settings.gemini_key},json=body)
                    if response.status_code!=200:
                        code=http_failure(response)
                        if attempts is not None:attempts.append({'provider':'gemini','model':name,'error':code,'usage':{},'usage_complete':False})
                        if code not in FALLBACK_ERRORS:raise ProviderError(code)
                        if code!='llm_model_unavailable' and outcome!='llm_rate_limited':outcome=code
                        continue
                    if len(response.content)>500000:raise ProviderError('llm_invalid_response')
                    self.gemini_model=name
                    reply=response.json()
                    candidates=reply.get('candidates') or []
                    meta=reply.get('usageMetadata',{})
                    usage={'input_tokens':meta.get('promptTokenCount',0),'cached_input_tokens':meta.get('cachedContentTokenCount',0),
                           'output_tokens':meta.get('candidatesTokenCount',0),'reasoning_output_tokens':meta.get('thoughtsTokenCount',0)}
                    entry={'provider':'gemini','model':name,'usage':usage}
                    finish=candidates[0].get('finishReason') if candidates else None
                    # Gemini's own safety check stopped the description or the photo.
                    if (reply.get('promptFeedback') or {}).get('blockReason') or (candidates and candidates[0].get('finishReason') in SAFETY_STOPS):
                        entry['error']='refused_other';raise DesignRefused([entry],'other')
                    if finish in RECITATION_STOPS:
                        entry['error']='llm_recitation';raise DesignFailure([entry],'llm_recitation')
                    if not candidates or candidates[0].get('finishReason') not in (None,'STOP','MAX_TOKENS'):
                        entry['error']='llm_incomplete';raise DesignFailure([entry],'llm_incomplete')
                    raw=''.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[]) if not p.get('thought'))
                    return raw,usage,name
            raise ProviderError(outcome)
        except ProviderError:raise
        except httpx.TimeoutException:raise ProviderError('llm_timeout') from None
        except httpx.TransportError:raise ProviderError('llm_unreachable') from None
        except Exception:raise ProviderError('llm_invalid_response') from None

    async def _codex(self,prompt,model,effort,image,feedback,style=None):
        if self.settings.mode!='demo':raise ProviderError('developer_provider_forbidden')
        cli=pathlib.Path(os.environ.get('APPDATA',''))/'npm/node_modules/@openai/codex/bin/codex.js'
        node=shutil.which('node')
        if not node or not cli.is_file():raise ProviderError('codex_unavailable')
        with tempfile.TemporaryDirectory(prefix='tripothon-design-') as folder:
            output=pathlib.Path(folder)/'design.json'
            structured=self.settings.studio_design_format=='structured'
            args=[node,str(cli),'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','-s','read-only',
                  '--disable','shell_tool','--disable','multi_agent','--disable','tool_suggest',
                  '-c','web_search="disabled"','-c',f'model_reasoning_effort="{effort}"','-m',model,'--json','-o',str(output)]
            if structured:
                schema=pathlib.Path(folder)/'response-schema.json';schema.write_text(json.dumps(SCHEMA),encoding='utf-8')
                args+=['--output-schema',str(schema)]
            if image:
                import base64
                reference=pathlib.Path(folder)/('reference.png' if image.startswith('data:image/png;') else 'reference.jpg')
                reference.write_bytes(base64.b64decode(image.split(',',1)[1],validate=True))
                args+=['--image',str(reference)]
            args+=['-']
            with llm_budget.call('codex',model):
                proc=await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
                      stderr=asyncio.subprocess.DEVNULL,cwd=folder,creationflags=0x08000000 if os.name=='nt' else 0)
                try:stdout,_=await asyncio.wait_for(proc.communicate((prompt_for_structured if structured else prompt_for)(prompt,feedback,style).encode()),timeout=480)
                except asyncio.CancelledError:
                    await terminate_owned_process(proc);raise
                except asyncio.TimeoutError:
                    await terminate_owned_process(proc);raise ProviderError('llm_timeout') from None
            if proc.returncode or not output.exists():raise ProviderError('codex_request_failed')
            usage={}
            for line in stdout.decode('utf-8',errors='replace').splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                if event.get('type')=='turn.completed':usage=event.get('usage',{})
            if output.stat().st_size>500000:raise ProviderError('llm_invalid_design')
            return output.read_text(encoding='utf-8'),usage
