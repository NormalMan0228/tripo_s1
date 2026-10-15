"""Durable call-count budget shared by crafting and behaviour design.

Reservations are deliberately independent of users, jobs and star refunds. A failed,
cancelled or interrupted request still consumes one call for the UTC day it started.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import uuid

from .provider import ProviderError


SCHEMA = '''
CREATE TABLE IF NOT EXISTS llm_call_reservations (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, source TEXT NOT NULL,
 reference TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('reserved','unknown','responded')),
 created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS llm_calls_created ON llm_call_reservations(created);
CREATE INDEX IF NOT EXISTS llm_calls_owner_created ON llm_call_reservations(owner_id,created);
'''

_current = ContextVar('llm_call_budget', default=None)


def reserve(db, settings, clock, owner_id, source, reference, provider, model):
    """Check both daily caps and commit a call before any provider request is sent."""
    now = clock()
    day = int(now // 86400) * 86400
    with db.transaction() as conn:
        account_calls = conn.execute(
            'SELECT count(*) FROM llm_call_reservations WHERE owner_id=? AND created>=? AND created<?',
            (owner_id, day, day + 86400)).fetchone()[0]
        if account_calls >= settings.llm_user_daily_call_limit:
            raise ProviderError('llm_account_daily_limit')
        server_calls = conn.execute(
            'SELECT count(*) FROM llm_call_reservations WHERE created>=? AND created<?',
            (day, day + 86400)).fetchone()[0]
        if server_calls >= settings.llm_server_daily_call_limit:
            raise ProviderError('llm_server_daily_limit')
        attempt_id = str(uuid.uuid4())
        conn.execute('INSERT INTO llm_call_reservations '
                     '(id,owner_id,source,reference,provider,model,state,created) VALUES (?,?,?,?,?,?,?,?)',
                     (attempt_id, owner_id, source, reference, provider, model, 'reserved', now))
    return attempt_id


class _Scope:
    def __init__(self, db, settings, clock, owner_id, source, reference, provider, model):
        self.db, self.settings, self.clock = db, settings, clock
        self.owner_id, self.source, self.reference = owner_id, source, reference
        self.first = reserve(db, settings, clock, owner_id, source, reference, provider, model)

    def begin(self, provider, model):
        attempt_id = self.first
        if attempt_id is None:
            attempt_id = reserve(self.db, self.settings, self.clock, self.owner_id, self.source,
                                 self.reference, provider, model)
        self.first = None
        # Commit unknown before sending. A process crash or ambiguous response cannot
        # erase this attempt or return its capacity to another request.
        with self.db.transaction() as conn:
            conn.execute("UPDATE llm_call_reservations SET state='unknown',provider=?,model=? WHERE id=?",
                         (provider, model, attempt_id))
        return attempt_id

    def responded(self, attempt_id):
        with self.db.transaction() as conn:
            conn.execute("UPDATE llm_call_reservations SET state='responded' WHERE id=?", (attempt_id,))


@contextmanager
def call(provider, model):
    """Wrap one actual provider call, including each retry and model fallback.

Standalone provider contract tests may run without an application budget scope;
application entry points always use generate() below.
"""
    scope = _current.get()
    attempt_id = scope.begin(provider, model) if scope else None
    yield
    if scope:
        scope.responded(attempt_id)


async def generate(db, settings, clock, owner_id, source, reference, designer, *args):
    """Run an attributed design without changing the replaceable designer interface."""
    provider = settings.studio_llm
    model = args[1]
    scope = _Scope(db, settings, clock, owner_id, source, reference, provider, model)
    token = _current.set(scope)
    try:
        if getattr(designer, 'reserves_llm_calls', False):
            return await designer.generate(*args)
        # Injected/offline designers expose only generate(); count their invocation
        # conservatively too, so replacing a designer never disables the guard.
        with call(provider, model):
            return await designer.generate(*args)
    finally:
        _current.reset(token)
