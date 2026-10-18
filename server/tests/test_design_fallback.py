"""No live APIs: provider failover, refusal boundaries and durable call accounting."""
import asyncio
import json

import httpx
import pytest

from server import llm_budget
from server.asset_assembly import demo_design
from server.config import Settings
from server.craft_moderation import failure_reason
from server.database import Database
from server.design_provider import DesignProvider
from server.provider import ProviderError


def good(provider):
    plan, program = demo_design('chest')
    raw = json.dumps({'plan': plan, 'program': program})
    if provider == 'openai':
        return httpx.Response(200, json={'status': 'completed', 'output': [
            {'content': [{'type': 'output_text', 'text': raw}]}],
            'usage': {'input_tokens': 12, 'output_tokens': 7}})
    return httpx.Response(200, json={'candidates': [
        {'finishReason': 'STOP', 'content': {'parts': [{'text': raw}]}}],
        'usageMetadata': {'promptTokenCount': 12, 'candidatesTokenCount': 7}})


def settings_for(tmp_path, primary='openai', **extra):
    return Settings(data_dir=tmp_path, studio_llm=primary, studio_llm_fallbacks=('gemini', 'openai'),
                    llm_key='private-openai', gemini_key='private-google', gemini_models=('test-model',), **extra)


def run(settings, handler, db=None):
    designer = DesignProvider(settings, httpx.MockTransport(handler))
    designer.retry_pause = 0
    if db:
        return asyncio.run(llm_budget.generate(db, settings, lambda: 86400100, 'alice',
            'craft_design', 'test-job', designer, 'a wooden chest', 'gpt-6-luna', 'high'))
    return asyncio.run(designer.generate('a wooden chest', 'gpt-6-luna', 'high'))


@pytest.mark.parametrize('primary', ['openai', 'gemini'])
@pytest.mark.parametrize('status', [429, 503, 404])
def test_cross_provider_fallback_keeps_provenance_and_call_budget(tmp_path, primary, status):
    settings = settings_for(tmp_path, primary)
    db = Database(tmp_path / 'fallback.db', 'demo')
    seen = []

    def handle(request):
        provider = 'openai' if request.url.host == 'api.openai.com' else 'gemini'
        seen.append(provider)
        # Each actual HTTP request was durably reserved BEFORE it was sent.
        with db.read() as conn:
            rows = conn.execute('SELECT provider,state FROM llm_call_reservations ORDER BY rowid').fetchall()
        assert len(rows) == len(seen) and rows[-1]['state'] == 'unknown'
        assert rows[-1]['provider'] == provider
        return httpx.Response(status, text='sensitive provider body') if provider == primary else good(provider)

    try:
        _, _, meta = run(settings, handle, db)
        assert seen == [primary, 'gemini' if primary == 'openai' else 'openai']
        assert meta['provider'] == seen[-1] and meta['fallback_used']
        assert meta['attempts'][0]['provider'] == primary
        assert meta['usage']['output_tokens'] == 7
        assert meta['usage_complete'] is False
        assert 'sensitive' not in json.dumps(meta) and 'private-' not in json.dumps(meta)
    finally:
        db.close()


@pytest.mark.parametrize('interrupt,code', [
    (httpx.ReadTimeout('secret timeout'), 'llm_timeout'),
    (httpx.ConnectError('secret network'), 'llm_unreachable')])
def test_network_failure_falls_back_but_does_not_claim_first_call_was_free(tmp_path, interrupt, code):
    seen = []

    def handle(request):
        seen.append(request.url.host)
        if len(seen) == 1: raise interrupt
        return good('gemini')

    _, _, meta = run(settings_for(tmp_path), handle)
    assert len(seen) == 2 and meta['attempts'][0]['error'] == code
    assert meta['usage_complete'] is False


@pytest.mark.parametrize('primary,response,code', [
    ('openai', httpx.Response(200, json={'status':'completed', 'output':[
        {'content':[{'type':'refusal','refusal':'private reason'}]}], 'usage':{'input_tokens':9}}), 'refused_other'),
    ('openai', httpx.Response(400, json={'error':{'code':'content_policy_violation'}}), 'refused_other'),
    ('openai', httpx.Response(429, json={'error':{'code':'credit_balance_exhausted'}}), 'llm_quota_exhausted'),
    ('openai', httpx.Response(401), 'llm_authentication'),
    ('gemini', httpx.Response(403), 'llm_permission_denied'),
    ('gemini', httpx.Response(200, json={'candidates':[{'finishReason':'SAFETY'}]}), 'refused_other'),
    ('gemini', httpx.Response(200, json={'candidates':[{'finishReason':'RECITATION'}]}), 'llm_recitation'),
    ('gemini', httpx.Response(200, json={'candidates':[{'finishReason':'IMAGE_RECITATION'}]}), 'llm_recitation'),
])
def test_nontransient_failures_never_route_to_another_provider(tmp_path, primary, response, code):
    seen = []

    def handle(request):
        seen.append(request.url.host)
        return response

    with pytest.raises(ProviderError) as caught:
        run(settings_for(tmp_path, primary), handle)
    assert caught.value.code == code and len(seen) == 1
    if primary == 'openai' and response.status_code == 200:
        assert caught.value.usage['input_tokens'] == 9


def test_daily_budget_stops_backup_before_transport(tmp_path):
    db = Database(tmp_path / 'budget.db', 'demo')
    seen = []
    try:
        with pytest.raises(ProviderError, match='llm_account_daily_limit'):
            run(settings_for(tmp_path, llm_user_daily_call_limit=1),
                lambda request: seen.append(request.url.host) or httpx.Response(503), db)
        assert seen == ['api.openai.com']
    finally:
        db.close()


def test_missing_backup_key_never_sends_request(tmp_path):
    settings = settings_for(tmp_path)
    settings.gemini_key = ''
    seen = []
    with pytest.raises(ProviderError, match='llm_busy'):
        run(settings, lambda request: seen.append(request.url.host) or httpx.Response(503))
    assert seen == ['api.openai.com']


def test_both_providers_busy_are_recorded_without_a_routing_loop(tmp_path):
    seen = []
    with pytest.raises(ProviderError, match='llm_busy') as caught:
        run(settings_for(tmp_path, 'gemini'),
            lambda request: seen.append(request.url.host) or httpx.Response(503))
    assert len(seen) == 2
    assert [a['provider'] for a in caught.value.attempts] == ['gemini', 'openai']


def test_invalid_design_repairs_once_without_switching_provider(tmp_path):
    seen = []

    def handle(request):
        seen.append(request.url.host)
        return httpx.Response(200, json={'status':'completed', 'output':[
            {'content':[{'type':'output_text','text':'{}'}]}], 'usage':{'input_tokens':3}})

    with pytest.raises(ProviderError, match='llm_invalid_design') as caught:
        run(settings_for(tmp_path), handle)
    assert seen == ['api.openai.com'] * 2 and caught.value.usage['input_tokens'] == 6


@pytest.mark.parametrize('code,reason', [
    ('llm_rate_limited','rate'), ('llm_unreachable','connection'), ('llm_timeout','timeout'),
    ('llm_busy','busy'), ('llm_recitation','recitation'), ('llm_authentication','setup'),
    ('llm_quota_exhausted','credit'), ('llm_invalid_design','design'), ('llm_account_daily_limit','limit')])
def test_failure_reasons_distinguish_service_failure_from_content_rejection(code, reason):
    assert failure_reason(code) == (reason, '')
