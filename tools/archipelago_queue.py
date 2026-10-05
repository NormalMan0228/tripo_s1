"""Serialize queue updates and enforce the user's review batch boundary."""
import contextlib
import json
import msvcrt
from pathlib import Path
import time

BASE = Path(__file__).resolve().parents[1]/'art/maps/archipelago_objects_v1'

@contextlib.contextmanager
def locked_queue():
    with (BASE/'queue.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        while True:
            try:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(.05)
        try:
            path = BASE/'queue.json'
            queue = json.loads(path.read_text(encoding='utf-8'))
            yield queue
            temp = BASE/'queue.json.tmp'
            temp.write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(path)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def assert_authorized(queue, asset):
    index = next(i for i,item in enumerate(queue['items']) if item['id']==asset)
    batch = queue.get('active_batch',{})
    ids = batch.get('assets',[])
    if ids:
        assert asset in ids, 'outside_authorized_batch'
        assert len(ids)<=15 and batch['max_concurrent']==3
        previous_ids = {ident for prior in queue.get('batch_history',[]) for ident in prior['assets']}
        assert all(item['review_status']=='approved' for item in queue['items'] if item['id'] in previous_ids), 'previous_batch_awaiting_review'
    else:
        assert all(item['review_status']=='approved' for item in queue['items'][:index]), 'previous_batch_awaiting_review'

def set_status(asset,status):
    with locked_queue() as queue:
        next(item for item in queue['items'] if item['id']==asset)['review_status']=status
