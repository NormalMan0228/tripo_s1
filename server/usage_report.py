"""Read-only usage totals for the PC cost monitor (tools/cost_monitor/).

GET /v1/ops/usage answers only with ``Authorization: Bearer <usage key>``. The key comes from
TRIPOTHON_USAGE_KEY or TRIPOTHON_USAGE_KEY_FILE (a server creates it with
``sudo bash ops/usage_key.sh``). It is not a player or admin login, and while no key is
configured the route does not exist (404).

The reply holds aggregates only: counts, Tripo credits and LLM token sums per UTC day and
model. Account names and ids, prompts, descriptions, job ids and keys never leave this module.
Days are UTC days, the same days the server's daily craft limits count.
"""
import hashlib
import json
import math
import re
import secrets
import time
from fastapi import HTTPException, Request
from .asset_studio import billing, tripo_credits_committed
from .interactions import DESCRIBE_DAILY_LIMIT
from .tripo_budget import job_billing

DAY = 86400
HISTORY_DAYS = 14
# The monitor polls every 30 s; a short cache keeps repeated calls cheap.
CACHE_SECONDS = 5
WINDOWS = ('today', 'last_7_days', 'total')
# Token fields the design providers record (server/design_provider.py), as named in the reply.
TOKEN_FIELDS = {'input_tokens': 'input', 'cached_input_tokens': 'cached_input',
                'output_tokens': 'output', 'reasoning_output_tokens': 'reasoning'}
LLM_PROVIDERS = ('gemini', 'openai', 'codex_subscription_development')
SETTING_PROVIDER = {'gemini': 'gemini', 'openai': 'openai', 'codex': 'codex_subscription_development'}
FINISHED = ('ready', 'failed', 'cancelled')
MODEL_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')


def no_tokens():
    return dict.fromkeys(TOKEN_FIELDS.values(), 0)


def tokens_of(usage):
    out = no_tokens()
    if isinstance(usage, dict):
        for key, name in TOKEN_FIELDS.items():
            value = usage.get(key)
            if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1e9:
                out[name] += int(value)
    return out


def add_tokens(target, tokens):
    for name, value in tokens.items():
        target[name] = target.get(name, 0) + value


def loads(text):
    try:
        value = json.loads(text or '{}')
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def llm_run(provenance, default_provider):
    """(provider, model) when a designer call made this record, else None. Fixture and
    direct-prompt designs used no model. Failed interaction designs keep only their usage."""
    provider = provenance.get('provider')
    if provider is None and 'usage' in provenance:
        provider = default_provider
    if provider not in LLM_PROVIDERS:
        return None
    model = provenance.get('model')
    model = model if isinstance(model, str) and MODEL_NAME.match(model) else ''
    # A failed Gemini design records the request's OpenAI model name, not the Gemini one.
    if provider == 'gemini' and not model.startswith('gemini'):
        model = ''
    return provider, model or 'unknown'


def budget_safety_report(conn, now, include_accounts=False):
    """Durable cost ledgers. Account identities are available only to the local CLI.

    Charged is the actual bill reported by Tripo. Reserved/unknown are the remaining
    conservative liability above that bill; unsubmitted holds cover future parts.
    The legacy remainder is kept visible rather than presented as reconciled billing.
    """
    from .tripo_budget import committed_credits
    today = int(now // DAY) * DAY
    accounts = {}

    def account(owner_id):
        return accounts.setdefault(owner_id, {'owner_id': owner_id, 'tripo_committed': 0.0,
                                              'tripo_charged': 0.0, 'llm_calls_today': 0})

    tripo = {'charged': 0.0, 'reserved': 0.0, 'unknown': 0.0, 'unsubmitted': 0.0,
             'attempts': dict.fromkeys(('unknown', 'reserved', 'charged', 'released'), 0)}
    for row in conn.execute('SELECT * FROM tripo_attempts'):
        tripo['attempts'][row['state']] += 1
        if row['state'] == 'released':
            continue
        actual = float(row['actual_credits'] or 0)
        liability = max(float(row['reserved_credits']), actual)
        tripo['charged'] += actual
        tripo['unknown' if row['state'] == 'unknown' else 'reserved'] += liability - actual
        item = account(row['owner_id'])
        item['tripo_committed'] += liability
        item['tripo_charged'] += actual
    for row in conn.execute('SELECT owner_id,credits FROM tripo_job_holds'):
        tripo['unsubmitted'] += row['credits']
        account(row['owner_id'])['tripo_committed'] += row['credits']
    tripo['committed'] = committed_credits(conn)
    tripo['tester_committed'] = committed_credits(conn, tester=True)
    tripo['legacy_committed'] = max(0.0, tripo['committed'] - sum(tripo[key] for key in (
        'charged', 'reserved', 'unknown', 'unsubmitted')))
    llm = {'calls_today': 0, 'states_today': dict.fromkeys(('reserved', 'unknown', 'responded'), 0)}
    for row in conn.execute('SELECT owner_id,state,count(*) AS calls FROM llm_call_reservations '
                            'WHERE created>=? AND created<? GROUP BY owner_id,state', (today, today + DAY)):
        llm['calls_today'] += row['calls']
        llm['states_today'][row['state']] += row['calls']
        account(row['owner_id'])['llm_calls_today'] += row['calls']
    report = {'day_start_utc': today, 'tripo': tripo, 'llm': llm}
    if include_accounts:
        names = {row['id']: row['username'] for row in conn.execute('SELECT id,username FROM users')}
        for owner_id, item in accounts.items():
            item.update(username=names.get(owner_id), deleted=owner_id not in names)
        report['top_10_tripo_accounts'] = sorted(
            (item for item in accounts.values() if item['tripo_committed']),
            key=lambda item: (-item['tripo_committed'], item['owner_id']))[:10]
        report['top_10_llm_accounts_today'] = sorted(
            (item for item in accounts.values() if item['llm_calls_today']),
            key=lambda item: (-item['llm_calls_today'], item['owner_id']))[:10]
    return report


class UsageReport:
    def __init__(self, app, db, settings, clock=time.time):
        self.db, self.settings, self.clock = db, settings, clock
        self.cached = (0.0, None)

        @app.get('/v1/ops/usage')
        def usage(request: Request):
            self.authorize(request)
            now = self.clock()
            at, data = self.cached
            if data is None or not 0 <= now - at < CACHE_SECONDS:
                data = self.report(now)
                self.cached = (now, data)
            return data

    def authorize(self, request):
        expected = getattr(self.settings, 'usage_key', '') or ''
        if not expected:
            raise HTTPException(404, 'Not Found')
        value = request.headers.get('authorization', '')
        given = value[7:] if value.startswith('Bearer ') and len(value) <= 2100 else ''
        if not secrets.compare_digest(hashlib.sha256(given.encode()).digest(),
                                      hashlib.sha256(expected.encode()).digest()):
            raise HTTPException(401, 'usage_key_required')

    def report(self, now):
        settings = self.settings
        today = int(now // DAY) * DAY
        week = today - 6 * DAY
        first = today - (HISTORY_DAYS - 1) * DAY

        def windows(created):
            if not isinstance(created, (int, float)):
                return ('total',)
            return ('total',) + (('last_7_days',) if created >= week else ()) + (('today',) if created >= today else ())

        days = {first + i * DAY: {'crafts': 0, 'failed': 0, 'tripo_credits': 0.0, 'llm_runs': 0, 'interactions': 0,
                                  'tokens': no_tokens(), 'models': {}} for i in range(HISTORY_DAYS)}

        def day_of(created):
            if isinstance(created, (int, float)) and created >= first:
                return days.get(int(created // DAY) * DAY)
            return None

        crafts = dict.fromkeys(WINDOWS, 0)
        credits = dict.fromkeys(WINDOWS, 0.0)
        craft_runs = dict.fromkeys(WINDOWS, 0)
        interaction_runs = dict.fromkeys(WINDOWS, 0)
        tokens = {w: no_tokens() for w in WINDOWS}
        models = {}
        pending = today_ready = today_failed = incomplete = 0
        described = dict.fromkeys(WINDOWS, 0)
        described_states = {'ready': 0, 'failed': 0, 'designing': 0}
        default_provider = SETTING_PROVIDER.get(settings.studio_llm, 'unknown')

        incomplete_usage = dict.fromkeys(WINDOWS, 0)

        def count_llm(provenance, created, runs):
            run = llm_run(provenance, default_provider)
            if not run:
                return
            # Total runs remain jobs. Model runs count one participation per model
            # per job; tokens follow the actual provider, including before failover.
            groups = {}
            attempts = provenance.get('attempts')
            if isinstance(attempts, list) and attempts and all(
                    isinstance(a, dict) and llm_run(a, 'unknown') for a in attempts):
                for attempt in attempts:
                    slot = groups.setdefault(llm_run(attempt, 'unknown'), no_tokens())
                    add_tokens(slot, tokens_of(attempt.get('usage')))
            else:
                groups[run] = tokens_of(provenance.get('usage'))
            day = day_of(created)
            for w in windows(created):
                runs[w] += 1
                if provenance.get('usage_complete') is False: incomplete_usage[w] += 1
            if day is not None: day['llm_runs'] += 1
            for model_run, used in groups.items():
                entry = models.setdefault(model_run, {'provider': model_run[0], 'model': model_run[1],
                    'runs': dict.fromkeys(WINDOWS, 0), 'tokens': {w: no_tokens() for w in WINDOWS}})
                for w in windows(created):
                    entry['runs'][w] += 1
                    add_tokens(tokens[w], used)
                    add_tokens(entry['tokens'][w], used)
                if day is not None:
                    add_tokens(day['tokens'], used)
                    slot = day['models'].setdefault(model_run,
                        {'provider': model_run[0], 'model': model_run[1], 'runs': 0, **no_tokens()})
                    slot['runs'] += 1
                    add_tokens(slot, used)

        with self.db.read() as conn:
            managed_jobs = {row[0] for row in conn.execute('SELECT job_id FROM tripo_job_holds')}
            for row in conn.execute('SELECT id,state,created,parts,provenance FROM studio_jobs'):
                created, state = row['created'], row['state']
                for w in windows(created):
                    crafts[w] += 1
                if state not in FINISHED:
                    pending += 1
                if isinstance(created, (int, float)) and created >= today:
                    today_ready += state == 'ready'
                    today_failed += state == 'failed'
                if row['id'] in managed_jobs:
                    bill = job_billing(conn, row['id'])
                    # Count each durable bill below, including deleted jobs and redraws.
                    known = 0.0
                else:
                    try:
                        bill = billing(loads(row['parts']))
                    except (AttributeError, TypeError):
                        bill = {'known_tripo_credits': 0, 'billing_complete': False}
                    known = float(bill['known_tripo_credits'])
                if not bill['billing_complete'] and state in FINISHED:
                    incomplete += 1
                for w in windows(created):
                    credits[w] += known
                day = day_of(created)
                if day is not None:
                    day['crafts'] += 1
                    day['failed'] += state == 'failed'
                    day['tripo_credits'] += known
                count_llm(loads(row['provenance']), created, craft_runs)
            for row in conn.execute("SELECT created,actual_credits FROM tripo_attempts WHERE state!='released'"):
                actual = float(row['actual_credits'] or 0)
                for w in windows(row['created']):
                    credits[w] += actual
                day = day_of(row['created'])
                if day is not None:
                    day['tripo_credits'] += actual
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='interaction_designs'").fetchone():
                for row in conn.execute('SELECT state,created,provenance FROM interaction_designs'):
                    created = row['created']
                    for w in windows(created):
                        described[w] += 1
                    if row['state'] in described_states:
                        described_states[row['state']] += 1
                    day = day_of(created)
                    if day is not None:
                        day['interactions'] += 1
                    count_llm(loads(row['provenance']), created, interaction_runs)
            committed = tripo_credits_committed(conn)
            accounts_today = conn.execute('SELECT count(DISTINCT owner_id) FROM studio_jobs WHERE created>=?', (today,)).fetchone()[0]
            users = conn.execute('SELECT count(*), sum(created>=?) FROM users', (today,)).fetchone()
            budget_safety = budget_safety_report(conn, now)

        budget = settings.tripo_credit_budget
        used = round(committed)
        return {
            'schema': 1, 'service': 'tripothon', 'generated': round(now), 'day_start_utc': today,
            'mode': settings.mode,
            'budget_safety': budget_safety,
            'limits': {'daily_crafts': settings.daily_generation_limit,
                       'account_daily_crafts': settings.user_daily_generation_limit,
                       'account_total_crafts': settings.user_total_generation_limit,
                       'max_credits_per_craft': settings.max_credits_per_craft,
                       'tripo_credit_budget': budget, 'welcome_stars': settings.welcome_stars,
                       'llm_account_daily_calls': settings.llm_user_daily_call_limit,
                       'llm_server_daily_calls': settings.llm_server_daily_call_limit,
                       'describe_daily_per_account': DESCRIBE_DAILY_LIMIT,
                       'open_registration': bool(settings.mode == 'live' and settings.open_registration)},
            'budget': {'used': used, 'total': budget, 'remaining': max(0, budget - used)} if budget else None,
            'crafts': {**crafts, 'pending': pending, 'today_ready': today_ready, 'today_failed': today_failed,
                       'accounts_today': accounts_today},
            'tripo_credits': {**{w: round(v, 2) for w, v in credits.items()}, 'committed': round(committed, 2),
                              'incomplete_bills': incomplete},
            'llm': {'provider': settings.studio_llm,
                    'fallbacks_configured': list(settings.studio_llm_fallbacks),
                    'incomplete_usage_runs': incomplete_usage,
                    'models_configured': list(settings.gemini_models) if settings.studio_llm == 'gemini' else [],
                    'runs': {w: craft_runs[w] + interaction_runs[w] for w in WINDOWS},
                    'craft_runs': craft_runs, 'interaction_runs': interaction_runs, 'tokens': tokens,
                    'by_model': sorted(models.values(), key=lambda m: (-m['runs']['total'], m['model']))},
            'interactions': {**described, 'ready': described_states['ready'], 'failed': described_states['failed'],
                             'in_progress': described_states['designing']},
            'accounts': {'total': users[0] or 0, 'new_today': users[1] or 0},
            'daily': [{'day': time.strftime('%Y-%m-%d', time.gmtime(start)), **{k: v for k, v in day.items() if k != 'models'},
                       'tripo_credits': round(day['tripo_credits'], 2),
                       'models': sorted(day['models'].values(), key=lambda m: m['model'])}
                      for start, day in sorted(days.items())],
        }
