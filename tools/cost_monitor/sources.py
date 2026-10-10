"""What the cost monitor reads. Each source is one small class registered with
@source_type('name'); default_config.json (or the dashboard's settings) lists the sources that run.

Every source returns a Reading: the one shape the dashboard draws as a card (name, big value,
unit, remaining, spent today / 7 days, when it was measured, status and a note, plus optional
detail rows, a small series for the sparkline and recent history).

Adding a service:
  1. write a class here with @source_type('my_service'), `fields` for its settings and
     `async def read(self)` returning (Reading, raw_or_None);
  2. add an entry with "type": "my_service" to default_config.json.
A web account without an API needs no code: add a "manual" source in the dashboard settings.

Keys never appear in a Reading, a note or a log line. Only free, read-only calls are made.
"""
import fnmatch
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

import store

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from server.config import read_tripo_keys  # noqa: E402  (the server's own key-file reader)

SOURCE_TYPES = {}
SEVERITY = {'off': 0, 'ok': 1, 'warn': 2, 'alert': 3, 'error': 3}
DAY = 86400


def source_type(name):
    def register(cls):
        cls.type = name
        SOURCE_TYPES[name] = cls
        return cls
    return register


@dataclass
class Reading:
    id: str
    name: str
    type: str
    value: float | None = None
    unit: str = ''
    remaining: float | None = None
    total: float | None = None
    spent_today: float | None = None
    spent_7d: float | None = None
    updated: float | None = None   # when the number was measured (or checked by hand)
    status: str = 'ok'             # ok | warn | alert | error | off
    note: str = ''
    caption: str = ''              # the line under the big number
    estimated: bool = False
    money: bool = False            # value is US dollars
    manual: bool = False           # the card offers hand entry
    link: str = ''
    meter: dict | None = None      # {'used', 'total'} draws a bar
    rows: list = field(default_factory=list)      # [{'label', 'value', 'hint'?, 'level'?}]
    series: dict | None = None     # {'kind': 'line'|'bars', 'label', 'points': [[ts, value]]}
    history: list = field(default_factory=list)   # recent entries, newest first

    def to_dict(self):
        return asdict(self)


def worse(a, b):
    return a if SEVERITY.get(a, 0) >= SEVERITY.get(b, 0) else b


def level_below(value, warn, alert):
    if value is None:
        return 'ok'
    if alert is not None and value < alert:
        return 'alert'
    if warn is not None and value < warn:
        return 'warn'
    return 'ok'


def number(value, default=None):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def fmt(value, digits=0):
    if value is None:
        return '-'
    if digits:
        return f'{value:,.{digits}f}'
    return f'{round(value):,}'


def fmt_tokens(value):
    value = value or 0
    if value >= 1_000_000:
        return f'{value / 1_000_000:.2f}M'
    if value >= 10_000:
        return f'{value / 1000:.1f}K'
    return f'{round(value):,}'


class Context:
    """What a source may use: the history store, the clock, an HTTP client factory and the
    latest results of other sources (derived sources such as the Gemini estimate read those)."""

    def __init__(self, history, clock=time.time, transport=None, latest_raw=None, settings=None):
        self.history, self.clock, self.transport = history, clock, transport
        self.latest_raw = latest_raw if latest_raw is not None else {}
        self.settings = settings or {}

    def client(self):
        return httpx.AsyncClient(transport=self.transport, timeout=12, follow_redirects=False,
                                 headers={'User-Agent': 'villagen-cost-monitor/1'})

    def days(self):
        now = self.clock()
        today = store.day_start(now)
        return now, today, today - 6 * DAY


class Source:
    type = ''
    title = ''
    interval = 30          # seconds between reads
    min_interval = 15      # the settings cannot go below this
    fields = ()            # settings form: (name, label, kind, hint); kinds in monitor.FIELD_KINDS

    def __init__(self, cfg, ctx):
        self.cfg, self.ctx = cfg, ctx
        self.id = cfg['id']
        self.name = cfg.get('label') or self.id

    @property
    def every(self):
        return max(self.min_interval, number(self.cfg.get('interval_seconds'), self.interval))

    def depends(self):
        return ()

    def reading(self, **values):
        return Reading(id=self.id, name=self.name, type=self.type, **values)

    def failed(self, note, **values):
        return self.reading(status='error', note=note, updated=self.ctx.clock(), **values)

    async def read(self):
        raise NotImplementedError


@source_type('tripo_api')
class TripoApiBalance(Source):
    """Tripo API wallet: GET /v3/account/balance (free). At most one call a minute per key."""
    title = 'Tripo API 잔액'
    URL = 'https://openapi.tripo3d.ai/v3/account/balance'
    interval = 60
    min_interval = 60
    fields = (('key_file', '키 파일 경로', 'path', '한 줄에 키 하나. 키는 이 PC에서 Tripo로만 가요'),
              ('warn_below', '경고: 이보다 적으면', 'number', '크레딧'),
              ('alert_below', '위험: 이보다 적으면', 'number', '크레딧'))

    async def read(self):
        unit = '크레딧'
        path = os.path.expandvars(str(self.cfg.get('key_file') or ''))
        try:
            keys = read_tripo_keys(path)
        except ValueError:
            return self.failed('키 파일을 읽지 못했어요. 설정에서 경로를 확인해 주세요.', unit=unit), None
        balances, frozen = [], 0.0
        async with self.ctx.client() as client:
            for key in keys[:8]:
                try:
                    response = await client.get(self.URL, headers={'Authorization': 'Bearer ' + key})
                except httpx.HTTPError:
                    return self.failed('Tripo에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.', unit=unit), None
                if response.status_code in (401, 403):
                    return self.failed('Tripo가 키를 거절했어요 (만료되었거나 지워진 키).', unit=unit), None
                if response.status_code == 429:
                    return self.failed('Tripo 요청이 잠시 막혔어요. 1분 뒤 다시 읽어요.', unit=unit), None
                data = None
                try:
                    data = response.json()
                    value = number(data['data']['balance'])
                    held = number(data['data'].get('frozen'), 0.0)
                except (ValueError, KeyError, TypeError):
                    value = held = None
                if response.status_code != 200 or not isinstance(data, dict) or data.get('code') != 0 or value is None:
                    return self.failed(f'Tripo 응답을 읽지 못했어요 (HTTP {response.status_code}).', unit=unit), None
                balances.append(value)
                frozen += held or 0.0
        total = sum(balances)
        now, today, week = self.ctx.days()
        history = self.ctx.history
        history.add_sample(self.id, total, now)
        points = history.series(self.id, week)
        rows = []
        if len(balances) > 1:
            rows += [{'label': f'키 {i + 1}', 'value': fmt(v) + ' 크레딧'} for i, v in enumerate(balances)]
        if frozen:
            rows.append({'label': '진행 중 작업에 묶인 크레딧', 'value': fmt(frozen), 'hint': 'Tripo의 frozen 값'})
        added = store.topped_up(points, week)
        if added:
            rows.append({'label': '7일 동안 충전', 'value': '+' + fmt(added)})
        status = level_below(total, number(self.cfg.get('warn_below')), number(self.cfg.get('alert_below')))
        note = {'alert': '잔액이 매우 적어요. 충전하거나 생성을 멈춰 주세요.',
                'warn': '잔액이 경고 기준보다 적어요.'}.get(status, '1분마다 Tripo에서 직접 읽어요 (무료 조회).')
        return self.reading(value=total, unit=unit, remaining=total, spent_today=store.spend(points, today),
                            spent_7d=store.spend(points, week), updated=now, status=status, note=note,
                            caption=f'키 {len(keys)}개' if len(keys) > 1 else 'Tripo 개발자 API 지갑',
                            rows=rows, series={'kind': 'line', 'label': '7일 잔액', 'points': [[t, v] for t, v in points if t >= week]}), None


@source_type('villagen_server')
class VillagenServer(Source):
    """A Villagen game server: public /health (budget) and, with the usage key, /v1/ops/usage."""
    title = 'Villagen 서버'
    interval = 30
    fields = (('url', '서버 주소', 'url', 'https://로 시작하는 주소'),
              ('usage_key', '사용량 키', 'secret', '서버에서 sudo bash ops/usage_key.sh 로 만든 키'),
              ('warn_ratio', '예산 경고 비율', 'ratio', '0.8 = 80% 썼을 때'),
              ('alert_ratio', '예산 위험 비율', 'ratio', '0.95 = 95% 썼을 때'))

    async def read(self):
        url = str(self.cfg.get('url') or '').rstrip('/')
        if not url.startswith(('https://', 'http://127.0.0.1', 'http://localhost')):
            return self.failed('설정에서 서버 주소를 넣어 주세요.'), None
        key = str(self.cfg.get('usage_key') or '')
        usage, usage_note = None, ''
        async with self.ctx.client() as client:
            try:
                response = await client.get(url + '/health')
                health = response.json() if response.status_code == 200 else None
            except (httpx.HTTPError, ValueError):
                return self.failed('서버에 연결하지 못했어요. 서버가 꺼져 있거나 주소가 바뀌었을 수 있어요.'), None
            if not isinstance(health, dict) or not health.get('ok'):
                return self.failed(f'서버가 정상 응답을 하지 않아요 (HTTP {response.status_code}).'), None
            if key:
                try:
                    response = await client.get(url + '/v1/ops/usage', headers={'Authorization': 'Bearer ' + key})
                    if response.status_code == 200:
                        usage = response.json()
                        if not isinstance(usage, dict) or usage.get('schema') != 1:
                            usage, usage_note = None, '사용량 응답 형식을 알 수 없어요. 모니터를 업데이트해 주세요.'
                    elif response.status_code == 401:
                        usage_note = '사용량 키가 맞지 않아요. 설정에서 다시 붙여넣어 주세요.'
                    elif response.status_code == 404:
                        usage_note = '서버에 사용량 키가 아직 없어요. 서버에서 sudo bash ops/usage_key.sh 를 실행해 주세요.'
                    else:
                        usage_note = f'사용량을 읽지 못했어요 (HTTP {response.status_code}).'
                except (httpx.HTTPError, ValueError):
                    usage_note = '사용량을 읽지 못했어요 (연결 오류).'
            else:
                usage_note = '설정에 사용량 키를 넣으면 제작 수, 크레딧, 토큰 통계가 보여요.'
        return self.build(health, usage, usage_note), usage

    def build(self, health, usage, usage_note):
        now, today, week = self.ctx.days()
        budget = (usage or {}).get('budget') or health.get('tripo_budget')
        values = {'updated': now, 'unit': '크레딧', 'rows': [], 'status': 'ok'}
        rows = values['rows']
        credits = (usage or {}).get('tripo_credits') or {}
        if budget and number(budget.get('total')):
            used, total = number(budget.get('used'), 0.0), number(budget.get('total'))
            remaining = max(0.0, total - used)
            ratio = used / total
            values.update(value=remaining, remaining=remaining, total=total, meter={'used': used, 'total': total},
                          caption=f'예산 {fmt(used)} / {fmt(total)} 사용 ({ratio * 100:.0f}%) · 남은 크레딧')
            warn, alert = number(self.cfg.get('warn_ratio'), 0.8), number(self.cfg.get('alert_ratio'), 0.95)
            if ratio >= alert:
                values.update(status='alert', note='예산을 거의 다 썼어요. 늘리려면 서버에서 --budget 값을 바꿔요.')
            elif ratio >= warn:
                values.update(status='warn', note=f'예산의 {ratio * 100:.0f}%를 썼어요.')
            self.ctx.history.add_sample(self.id, used, now)
        elif usage:
            values.update(value=number(credits.get('total')), caption='Tripo 크레딧 누적 사용 (예산 없음)', unit='크레딧 사용')
            self.ctx.history.add_sample(self.id, number(credits.get('total'), 0.0), now)
        else:
            values.update(value=None, caption='서버 정상 · 예산 없음', unit='')
        if usage:
            values.update(spent_today=number(credits.get('today')), spent_7d=number(credits.get('last_7_days')))
            crafts, limits = usage.get('crafts') or {}, usage.get('limits') or {}
            llm, described = usage.get('llm') or {}, usage.get('interactions') or {}
            daily_limit = number(limits.get('daily_crafts'))
            today_crafts = number(crafts.get('today'), 0)
            rows.append({'label': '오늘 제작 / 하루 한도', 'value': f'{fmt(today_crafts)} / {fmt(daily_limit)}',
                         'hint': '서버 전체 · 한국 시간 오전 9시에 초기화',
                         'level': 'warn' if daily_limit and today_crafts >= 0.8 * daily_limit else ''})
            rows.append({'label': '진행 중 · 오늘 완성 · 오늘 실패',
                         'value': f"{fmt(crafts.get('pending'))} · {fmt(crafts.get('today_ready'))} · {fmt(crafts.get('today_failed'))}"})
            rows.append({'label': 'Tripo 크레딧 (오늘 · 7일 · 전체)',
                         'value': f"{fmt(credits.get('today'))} · {fmt(credits.get('last_7_days'))} · {fmt(credits.get('total'))}",
                         'hint': 'Tripo가 알려 준 실제 사용량'})
            if credits.get('incomplete_bills'):
                rows.append({'label': '청구액 미확인 제작', 'value': fmt(credits['incomplete_bills']), 'level': 'warn',
                             'hint': '예산에는 견적으로 잡혀 있어요'})
            runs, tokens = llm.get('runs') or {}, llm.get('tokens') or {}
            if llm.get('provider') not in (None, 'fixture') or runs.get('total'):
                rows.append({'label': 'LLM 설계 (오늘 · 7일 · 전체)',
                             'value': f"{fmt(runs.get('today'))} · {fmt(runs.get('last_7_days'))} · {fmt(runs.get('total'))}",
                             'hint': f"{llm.get('provider') or '-'} · 제작 설계 + 상호작용 설명"})
                rows.append({'label': 'LLM 토큰 (오늘 · 7일 · 전체)',
                             'value': ' · '.join(fmt_tokens(sum((tokens.get(w) or {}).values())) for w in ('today', 'last_7_days', 'total')),
                             'hint': '입력 + 출력 + 생각 토큰'})
            rows.append({'label': '상호작용 설명 (오늘 · 7일 · 전체)',
                         'value': f"{fmt(described.get('today'))} · {fmt(described.get('last_7_days'))} · {fmt(described.get('total'))}",
                         'hint': f"성공 {fmt(described.get('ready'))} · 실패 {fmt(described.get('failed'))}"})
            accounts = usage.get('accounts') or {}
            rows.append({'label': '계정', 'value': f"{fmt(accounts.get('total'))} (오늘 +{fmt(accounts.get('new_today'))})"})
            rows.append({'label': '한도', 'value': f"계정당 하루 {fmt(limits.get('account_daily_crafts'))}회 · 제작당 최대 "
                                                  f"{fmt(limits.get('max_credits_per_craft')) if limits.get('max_credits_per_craft') else '제한 없음'} 크레딧"})
            values['series'] = {'kind': 'bars', 'label': '일별 Tripo 크레딧 (14일, UTC)',
                                'points': [[day.get('day'), number(day.get('tripo_credits'), 0.0)] for day in usage.get('daily') or []]}
        else:
            values['note'] = ' '.join(n for n in (values.get('note'), usage_note) if n)
            if values.get('meter'):
                points = self.ctx.history.series(self.id, week)
                values['series'] = {'kind': 'line', 'label': '7일 예산 사용', 'points': [[t, v] for t, v in points if t >= week]}
        per_craft = number(((usage or {}).get('limits') or {}).get('max_credits_per_craft'))
        if values.get('meter') and per_craft and values['remaining'] < per_craft:
            values.update(status='alert', note='남은 예산이 제작 한 번 최대치보다 적어요. 큰 제작부터 막혀요.')
        if usage_note and not usage and key_problem(usage_note):
            values['status'] = worse(values['status'], 'warn')
        rows.append({'label': '서버', 'value': f"v{health.get('version', '?')} · LLM {health.get('studio_llm', '-')}"
                                              f" · Tripo 제작 {'켜짐' if health.get('studio_tripo_enabled') else '꺼짐'}"})
        return self.reading(**values)


def key_problem(note):
    return '맞지 않아요' in note or '형식' in note


def price_for(model, prices):
    """The most specific pattern of the price table that matches the model name."""
    best = None
    for pattern, price in (prices or {}).items():
        if isinstance(price, dict) and fnmatch.fnmatchcase(model or '', pattern):
            score = (pattern == model, len(pattern.replace('*', '')))
            if best is None or score > best[0]:
                best = (score, pattern, price)
    return (best[1], best[2]) if best else (None, None)


def token_cost(tokens, price):
    """US dollars for one token bundle. Prices are per million tokens; cached input is billed at
    the cached rate, and 'thinking' tokens are billed as output (Gemini reports them apart)."""
    if not price:
        return 0.0
    tokens = tokens or {}
    used_in = number(tokens.get('input'), 0.0)
    cached = min(used_in, number(tokens.get('cached_input'), 0.0))
    out = number(tokens.get('output'), 0.0) + number(tokens.get('reasoning'), 0.0)
    rate_in = number(price.get('input'), 0.0)
    rate_cached = number(price.get('cached_input'), rate_in)
    return ((used_in - cached) * rate_in + cached * rate_cached + out * number(price.get('output'), 0.0)) / 1_000_000


@source_type('gemini_estimate')
class GeminiEstimate(Source):
    """Gemini cost estimated from the tokens the servers record, times the price table in settings."""
    title = 'Gemini 비용 (추정)'
    interval = 30
    min_interval = 0    # reads the servers' last results, no network
    fields = (('servers', '읽을 서버 (설정 id, 쉼표로 구분)', 'list', '예: school, judging'),
              ('prices', '요금표 (USD / 100만 토큰)', 'prices', '모델 이름 패턴별. Google AI 요금표를 보고 고쳐 주세요'),
              ('free_tier', '무료 등급 키', 'bool', '무료 등급이면 실제 청구는 0원이에요'),
              ('warn_7d_usd', '경고: 7일 비용이 이 이상 (USD)', 'number', ''))

    def depends(self):
        return tuple(self.cfg.get('servers') or ())

    async def read(self):
        prices = self.cfg.get('prices') or {}
        windows = ('today', 'last_7_days', 'total')
        cost = dict.fromkeys(windows, 0.0)
        by_day, rows, missing, others, used_prices = {}, [], [], 0, {}
        servers = self.depends()
        names = self.ctx.settings.get('names', {})
        for server in servers:
            raw = self.ctx.latest_raw.get(server)
            if not raw:
                missing.append(names.get(server, server))
                continue
            llm = raw.get('llm') or {}
            server_cost = dict.fromkeys(windows, 0.0)
            for model in llm.get('by_model') or []:
                if model.get('provider') != 'gemini':
                    others += (model.get('runs') or {}).get('total') or 0
                    continue
                pattern, price = price_for(model.get('model'), prices)
                if pattern:
                    used_prices[pattern] = price
                for w in windows:
                    server_cost[w] += token_cost((model.get('tokens') or {}).get(w), price)
            for day in raw.get('daily') or []:
                for model in day.get('models') or []:
                    if model.get('provider') == 'gemini':
                        by_day[day.get('day')] = by_day.get(day.get('day'), 0.0) + token_cost(model, price_for(model.get('model'), prices)[1])
                by_day.setdefault(day.get('day'), 0.0)
            for w in windows:
                cost[w] += server_cost[w]
            rows.append({'label': names.get(server, server), 'value': f"오늘 ${server_cost['today']:.3f} · 7일 ${server_cost['last_7_days']:.2f} · 전체 ${server_cost['total']:.2f}"})
        now = self.ctx.clock()
        if not rows:
            return self.reading(status='off', updated=None, estimated=True, money=True, unit='USD',
                                note='서버 카드에 사용량 키를 넣으면 토큰으로 비용을 추정해요.'), None
        for pattern, price in sorted(used_prices.items()):
            rows.append({'label': f'요금 {pattern}', 'value': f"입력 ${number(price.get('input'), 0):g} · 캐시 ${number(price.get('cached_input'), 0):g} · 출력 ${number(price.get('output'), 0):g}",
                         'hint': '100만 토큰당 (설정에서 바꿔요)'})
        if others:
            rows.append({'label': '다른 LLM 설계', 'value': f'{others}회', 'hint': 'Gemini가 아니라 이 추정에 넣지 않았어요'})
        note = '추정: 서버가 기록한 토큰 × 요금표. 실제 청구는 Google Cloud 결제 화면이 기준이에요.'
        if self.cfg.get('free_tier'):
            note = '무료 등급 키: 실제 청구는 0원이에요. 유료였다면 이만큼이라는 추정치예요.'
        if missing:
            note += f" ({', '.join(missing)} 사용량 없음)"
        warn = number(self.cfg.get('warn_7d_usd'))
        status = 'warn' if warn and cost['last_7_days'] >= warn and not self.cfg.get('free_tier') else 'ok'
        return self.reading(value=cost['total'], unit='USD', money=True, estimated=True, spent_today=cost['today'],
                            spent_7d=cost['last_7_days'], updated=now, status=status, note=note,
                            caption='전체 추정 비용', rows=rows,
                            series={'kind': 'bars', 'label': '일별 추정 비용 (14일, UTC)',
                                    'points': [[day, round(value, 4)] for day, value in sorted(by_day.items()) if day]}), None


@source_type('manual')
class ManualBalance(Source):
    """A web account without an API (Tripo Studio, Scenario, ...): balances entered by hand in the
    dashboard or with `monitor.py record`. Spending is the sum of drops between entries."""
    title = '직접 입력'
    interval = 30
    min_interval = 0    # local history only
    fields = (('unit', '단위', 'text', '예: 크레딧, CU'),
              ('warn_below', '경고: 이보다 적으면', 'number', ''),
              ('alert_below', '위험: 이보다 적으면', 'number', ''),
              ('stale_days', '며칠 지나면 다시 확인하라고 알려 줄까요', 'number', ''),
              ('link', '잔액을 확인하는 웹 주소', 'link', ''))

    async def read(self):
        unit = str(self.cfg.get('unit') or '')
        link = str(self.cfg.get('link') or '')
        entries = self.ctx.history.manual(self.id)
        if not entries:
            return self.reading(status='off', unit=unit, manual=True, link=link,
                                note='아직 기록이 없어요. [잔액 입력]으로 지금 잔액을 넣어 주세요.'), None
        now, today, week = self.ctx.days()
        last = entries[-1]
        points = [(e['checked_at'], e['balance']) for e in entries]
        balance = last['balance']
        status = level_below(balance, number(self.cfg.get('warn_below')), number(self.cfg.get('alert_below')))
        note = {'alert': '잔액이 매우 적어요.', 'warn': '잔액이 경고 기준보다 적어요.'}.get(status, '')
        age = (now - last['checked_at']) / DAY
        stale = number(self.cfg.get('stale_days'), 7.0)
        if stale and age >= stale:
            status = worse(status, 'warn')
            note = (note + ' ' if note else '') + f'{int(age)}일 전에 확인한 값이에요. 사이트에서 다시 확인해 주세요.'
        history, previous = [], None
        for entry in entries[-9:]:
            delta = None if previous is None else entry['balance'] - previous
            history.append({'id': entry['id'], 'ts': entry['checked_at'], 'value': entry['balance'], 'delta': delta,
                            'note': entry['note'], 'origin': entry['origin']})
            previous = entry['balance']
        rows = []
        added = store.topped_up(points, week)
        if added:
            rows.append({'label': '7일 동안 충전', 'value': '+' + fmt(added, 0) + (' ' + unit if unit else '')})
        month = today - 29 * DAY
        return self.reading(value=balance, unit=unit, remaining=balance, spent_today=store.spend(points, today),
                            spent_7d=store.spend(points, week), updated=last['checked_at'], status=status,
                            note=note or (last['note'] and '메모: ' + last['note']) or '',
                            caption='직접 입력한 잔액', manual=True, link=link, rows=rows,
                            series={'kind': 'line', 'label': '30일 잔액',
                                    'points': [[t, v] for t, v in points if t >= month] or [[last['checked_at'], balance]]},
                            history=list(reversed(history[-8:]))), None
