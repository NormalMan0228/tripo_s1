"""Operator-only reconciliation. Never expose these operations through HTTP."""
import json
import re
import time
import uuid


class OperationError(Exception):
    pass


def evidence(value):
    # Store an operator's ticket/record reference, not copied provider responses or keys.
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{2,119}',value):
        raise OperationError('evidence_reference_required')


def held_job(conn,job_id):
    row=conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if not row: raise OperationError('job_not_found')
    if row['state']!='unknown': raise OperationError('job_not_held')
    return row


def audit(conn,action,job_id,reference,task_id=None):
    detail={'evidence':reference}
    if task_id: detail['provider_task']=task_id
    conn.execute('INSERT INTO audit(user_id,action,target,outcome,created) VALUES (NULL,?,?,?,?)',
                 (action,job_id,json.dumps(detail),time.time()))


def attach_task(db,job_id,task_id,verified_status,reference):
    evidence(reference)
    if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',task_id):
        raise OperationError('invalid_provider_task')
    if verified_status not in ('queued','running','success','failed','cancelled'):
        raise OperationError('provider_task_not_verified')
    with db.transaction() as conn:
        job=held_job(conn,job_id)
        if job['provider_task'] and job['provider_task']!=task_id:
            raise OperationError('recorded_task_mismatch')
        if conn.execute('SELECT 1 FROM jobs WHERE provider_task=? AND id<>?',(task_id,job_id)).fetchone():
            raise OperationError('task_already_attached')
        if conn.execute("SELECT 1 FROM jobs WHERE id<>? AND state IN ('queued','submitting','generating','downloading')",(job_id,)).fetchone():
            raise OperationError('another_provider_job_active')
        conn.execute("UPDATE jobs SET provider_task=?,state='generating',error_code=NULL,updated=? WHERE id=?",(task_id,time.time(),job_id))
        audit(conn,'operator_attach_task',job_id,reference,task_id)
    return {'id':job_id,'state':'generating','action':'poll_existing_task_only'}


def refund_not_submitted(db,job_id,reference,verified=False):
    evidence(reference)
    if not verified: raise OperationError('confirm_provider_non_submission_required')
    with db.transaction() as conn:
        job=held_job(conn,job_id)
        if job['provider_task']: raise OperationError('recorded_task_must_be_reconciled')
        charge=conn.execute("SELECT amount FROM ledger WHERE user_id=? AND reason='generation_charge' AND reference=?",(job['owner_id'],job_id)).fetchone()
        if not charge or charge['amount']!=-job['cost']:
            raise OperationError('charge_ledger_mismatch')
        conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',
                     (str(uuid.uuid4()),job['owner_id'],job['cost'],'generation_refund',job_id,time.time()))
        conn.execute('UPDATE users SET shards=shards+? WHERE id=?',(job['cost'],job['owner_id']))
        conn.execute("UPDATE jobs SET state='failed',error_code='operator_verified_not_submitted',updated=? WHERE id=?",(time.time(),job_id))
        audit(conn,'operator_refund_not_submitted',job_id,reference)
    return {'id':job_id,'state':'failed','action':'game_currency_refunded_once'}


def refund_studio_not_submitted(db,job_id,reference,verified=False):
    """Release a restored/ambiguous studio reservation only after external review."""
    evidence(reference)
    if not verified:raise OperationError('confirm_provider_non_submission_required')
    with db.transaction() as conn:
        job=conn.execute('SELECT * FROM studio_jobs WHERE id=?',(job_id,)).fetchone()
        if not job:raise OperationError('job_not_found')
        if job['state']!='unknown':raise OperationError('job_not_held')
        if conn.execute('SELECT 1 FROM studio_leases WHERE job_id=? AND expires>?',(job_id,time.time())).fetchone():
            raise OperationError('worker_still_holds_lease')
        parts=json.loads(job['parts'])
        provenance=json.loads(job['provenance'] or '{}')
        if any(p.get('task') or p.get('image_task') or p.get('credits_consumed') or p.get('image_credits_consumed') for p in parts.values()) or provenance.get('tripo_credits_consumed'):
            raise OperationError('recorded_task_must_be_reconciled')
        entries=conn.execute("SELECT amount FROM ledger WHERE user_id=? AND reference=? AND reason IN ('studio_charge','studio_quote_charge','studio_refund','studio_resume_charge','studio_resume_refund')",(job['owner_id'],job_id)).fetchall()
        outstanding=-sum(r['amount'] for r in entries)
        if outstanding!=job['cost'] or outstanding<=0:raise OperationError('charge_ledger_mismatch')
        conn.execute('INSERT INTO ledger VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),job['owner_id'],outstanding,'studio_refund',job_id,time.time()))
        conn.execute('UPDATE users SET shards=shards+? WHERE id=?',(outstanding,job['owner_id']))
        conn.execute("UPDATE studio_jobs SET state='failed',error='operator_verified_not_submitted',updated=? WHERE id=?",(time.time(),job_id))
        audit(conn,'studio_operator_refund_not_submitted',job_id,reference)
    return {'id':job_id,'state':'failed','action':'game_currency_refunded_once','amount':outstanding}
