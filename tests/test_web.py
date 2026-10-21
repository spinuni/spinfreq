"""Actual subprocess lifecycle checks; optional web dependencies."""
from dataclasses import replace
import json
import time

import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient

from spinfreq.config import presets
from spinfreq.jobs import write_json
from spinfreq.web.app import create_app
from spinfreq.web.queue import JobManager, QueueFull


def wait_for(predicate, timeout=25):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.03)
    raise AssertionError('Job did not reach expected state')


def test_browser_api_to_real_worker_download_and_isolation(tmp_path):
    with TestClient(create_app(tmp_path, mode='compute')) as client:
        configs = client.get('/api/presets').json()
        ids = []
        for preset in ('prism-fmr', 'periodic-fmr'):
            config = configs[preset]; config['points'] = 5
            response = client.post('/api/jobs', json=config)
            assert response.status_code == 202
            ids.append(response.json()['id'])
        for identifier in ids:
            url = '/api/jobs/'+identifier
            wait_for(lambda: client.get(url).json()['status'] not in ('queued', 'running'))
            record = client.get(url).json()
            if record['status'] != 'succeeded':
                pytest.fail(str(record)+'\n'+(tmp_path/identifier/'worker.log').read_text())
            summary = client.get(url+'/artifacts/summary.json').json()
            assert summary['stability'] == 'stable' and summary['max_delta_m'] < .05
            assert summary['worker_runtime'] == record['runtime']
            assert client.get(url+'/artifacts/results.zip').content.startswith(b'PK')
            assert client.get(url+'/artifacts/worker.log').status_code == 404
        assert client.get('/api/jobs/'+ids[0]+'/artifacts/configuration.json').json() != client.get('/api/jobs/'+ids[1]+'/artifacts/configuration.json').json()
        assert client.get('/api/jobs/unknown').status_code == 404
        assert client.delete('/api/jobs/'+ids[0]).status_code == 204
        assert client.get('/api/jobs/'+ids[0]).status_code == 404
        assert client.get('/api/jobs/'+ids[1]).json()['status'] == 'succeeded'


def test_malformed_oversized_and_cross_origin_requests(tmp_path):
    with TestClient(create_app(tmp_path, mode='compute')) as client:
        config = presets()['prism-fmr'].to_dict()
        assert client.post('/api/jobs', json={**config, 'nx': 100000}).status_code == 422
        assert client.post('/api/jobs', content='x'*17000, headers={'Content-Type':'application/json'}).status_code == 413
        assert client.post('/api/jobs', content='{}').status_code == 415
        assert client.post('/api/jobs', content='{"nx":1,"nx":2}', headers={'Content-Type':'application/json'}).status_code == 422
        assert client.post('/api/jobs', json=config, headers={'Origin':'https://external.example'}).status_code == 403
        assert client.get('/', headers={'Host':'external.example'}).status_code == 400


def test_queue_capacity_cancel_delete_and_exclusive_owner(tmp_path):
    manager = JobManager(tmp_path, max_pending=1, max_retained=1)
    try:
        with pytest.raises(RuntimeError, match='already has a supervisor'):
            JobManager(tmp_path)
        with manager._lock:
            identifier = manager.submit(presets()['prism-fmr'])['id']
            with pytest.raises(QueueFull):
                manager.submit(presets()['prism-fmr'])
            with pytest.raises(ValueError, match='Cancel'):
                manager.delete(identifier)
            assert manager.cancel(identifier)['status'] == 'cancelled'
        manager.delete(identifier)
        identifier = manager.submit(presets()['confined-skyrmion'])['id']
        wait_for(lambda: manager.get(identifier)['status'] == 'running')
        process = manager._active[1]
        assert manager.cancel(identifier)['status'] == 'cancelled'
        assert process.poll() is not None
        manager.delete(identifier)
        assert not manager.list()
    finally:
        manager.close()


def test_restart_marks_incomplete_work_interrupted(tmp_path):
    directory = tmp_path/('a'*32); directory.mkdir()
    write_json(directory/'status.json', {'id':directory.name, 'status':'running', 'created':0})
    manager = JobManager(tmp_path)
    try:
        assert manager.get(directory.name)['status'] == 'interrupted'
        assert manager._active is None
    finally:
        manager.close()


def test_corrupt_journal_releases_storage_lease(tmp_path):
    directory = tmp_path/('a'*32); directory.mkdir()
    (directory/'status.json').write_text('broken JSON')
    with pytest.raises(ValueError):
        JobManager(tmp_path)
    (directory/'status.json').unlink()
    manager = JobManager(tmp_path)
    manager.close()


def test_status_publication_failure_terminates_new_worker(tmp_path, monkeypatch):
    manager = JobManager(tmp_path)
    processes = []
    original_start, original_save = manager.runtime.start, manager._save
    def start(*args):
        process = original_start(*args)
        processes.append(process)
        return process
    def save(record):
        if record['status'] == 'running':
            raise OSError('simulated journal write failure')
        return original_save(record)
    monkeypatch.setattr(manager.runtime, 'start', start)
    monkeypatch.setattr(manager, '_save', save)
    try:
        identifier = manager.submit(presets()['prism-fmr'])['id']
        wait_for(lambda: manager.get(identifier)['status'] == 'failed')
        assert processes and processes[0].poll() is not None
        assert manager._active is None
    finally:
        manager.close()


def test_timeout_kills_worker_and_queue_recovers(tmp_path):
    manager = JobManager(tmp_path, timeout_s=1)
    try:
        identifier = manager.submit(presets()['confined-skyrmion'])['id']
        wait_for(lambda: manager.get(identifier)['status'] not in ('queued', 'running'))
        assert manager.get(identifier)['status'] == 'failed'
        assert not manager._active or manager._active[1].poll() is not None
        manager.delete(identifier)
    finally:
        manager.close()


def test_disk_limit_terminates_an_active_worker(tmp_path):
    manager = JobManager(tmp_path)
    try:
        identifier = manager.submit(presets()['confined-skyrmion'])['id']
        wait_for(lambda: manager.get(identifier)['status'] == 'running')
        process = manager._active[1]
        with (tmp_path/identifier/'oversized-test-file').open('wb') as stream:
            stream.truncate(97*1024**2)
        wait_for(lambda: manager.get(identifier)['status'] == 'failed')
        assert 'disk limit' in manager.get(identifier)['error']
        assert process.poll() is not None
    finally:
        manager.close()


def test_server_crash_kills_worker_and_restart_recovers(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    handshake = tmp_path/'worker-pid.json'
    directory = tmp_path/'jobs'
    script = '''
import json,sys,time
from pathlib import Path
from spinfreq.config import presets
from spinfreq.web.queue import JobManager
m=JobManager(sys.argv[1])
identifier=m.submit(presets()['confined-skyrmion'])['id']
while not m._active: time.sleep(.01)
Path(sys.argv[2]).write_text(json.dumps({'pid':m._active[1].pid,'id':identifier}))
time.sleep(50)
'''
    environment = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    with (tmp_path/'owner.log').open('w') as log:
        owner = subprocess.Popen([sys.executable, '-c', script, str(directory), str(handshake)], env=environment, stdout=log, stderr=log)
        try:
            wait_for(handshake.exists)
            worker = json.loads(handshake.read_text())
            owner.kill(); owner.wait(timeout=5)
            def no_live_worker():
                if sys.platform == 'win32':
                    from spinfreq.runtime.windows import is_process_running
                    return not is_process_running(worker['pid'])
                path = Path('/proc')/str(worker['pid'])/'stat'
                return not path.exists() or path.read_text().split(') ')[1].startswith('Z')
            wait_for(no_live_worker, timeout=5)
            manager = JobManager(directory)
            try:
                assert manager.get(worker['id'])['status'] == 'interrupted'
                next_job = manager.submit(presets()['prism-fmr'])['id']
                wait_for(lambda: manager.get(next_job)['status'] not in ('queued', 'running'))
                assert manager.get(next_job)['status'] == 'succeeded'
            finally:
                manager.close()
        finally:
            if owner.poll() is None:
                owner.kill(); owner.wait(timeout=5)
