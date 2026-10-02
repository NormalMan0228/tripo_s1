"""Replaceable design provider. Codex is development-only, Responses is production."""
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
from .structured_design import SCHEMA,prompt_for_structured,parse_structured

MODELS=('gpt-6-luna','gpt-5.6-terra','gpt-6-sol','gpt-6-astra')
EFFORTS=('low','medium','high','xhigh')

def usage_total(attempts):
    combined={}
    for record in attempts:
        for key,value in record['usage'].items():
            if type(value) in (int,float):combined[key]=combined.get(key,0)+value
    return combined

class DesignFailure(ProviderError):
    def __init__(self,attempts):
        super().__init__('llm_invalid_design')
        self.attempts=attempts
        self.usage=usage_total(attempts)

async def terminate_owned_process(proc):
    if proc.returncode is not None:return
    if os.name=='nt':
        killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(proc.pid),'/T','/F',
            stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,creationflags=0x08000000)
        await killer.wait()
    elif proc.returncode is None:proc.kill()
    await proc.wait()

class DesignProvider:
    def __init__(self,settings,transport=None):
        self.settings,self.transport=settings,transport

    async def generate(self,prompt,model,effort,image=None):
        feedback='';attempts=[]
        for attempt in range(2):
            if self.settings.studio_llm=='codex':
                raw,usage=await self._codex(prompt,model,effort,image,feedback)
            else:raw,usage=await self._openai(prompt,model,effort,image,feedback)
            entry={'usage':usage};attempts.append(entry)
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
            return plan,program,dict(provider='codex_subscription_development' if self.settings.studio_llm=='codex' else 'openai',
                model=model,effort=effort,format=self.settings.studio_design_format,usage=combined,attempts=attempts,validation=report)

    async def _openai(self,prompt,model,effort,image,feedback):
        if self.settings.studio_llm!='openai' or not self.settings.llm_key:
            raise ProviderError('llm_not_configured')
        structured=self.settings.studio_design_format=='structured'
        content=[{'type':'input_text','text':(prompt_for_structured if structured else prompt_for)(prompt,feedback)}]
        if image:content.append({'type':'input_image','image_url':image})
        try:
            async with httpx.AsyncClient(transport=self.transport,timeout=180,follow_redirects=False) as client:
                response=await client.post('https://api.openai.com/v1/responses',
                    headers={'Authorization':'Bearer '+self.settings.llm_key},json={
                        'model':model,'reasoning':{'effort':effort},'store':False,
                        'max_output_tokens':12000,'input':[{'role':'user','content':content}],
                        'text':{'format':{'type':'json_schema','name':'furniture_design','strict':True,'schema':SCHEMA} if structured else {'type':'json_object'}}})
            if response.status_code!=200 or len(response.content)>500000:raise ProviderError('llm_request_failed')
            body=response.json()
            if body.get('status')!='completed':raise ProviderError('llm_incomplete')
            raw=''.join(c.get('text','') for item in body.get('output',[]) for c in item.get('content',[]) if c.get('type')=='output_text')
            return raw,body.get('usage',{})
        except ProviderError:raise
        except Exception:raise ProviderError('llm_invalid_design') from None

    async def _codex(self,prompt,model,effort,image,feedback):
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
            proc=await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
                  stderr=asyncio.subprocess.DEVNULL,cwd=folder,creationflags=0x08000000 if os.name=='nt' else 0)
            try:stdout,_=await asyncio.wait_for(proc.communicate((prompt_for_structured if structured else prompt_for)(prompt,feedback).encode()),timeout=480)
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
