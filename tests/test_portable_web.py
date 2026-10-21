"""Portable app imports, preview and config export; also runs on native Windows."""
import pytest
import json
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from spinfreq.config import presets
from spinfreq.web.app import create_app
from spinfreq.web.platforms import capabilities


@pytest.mark.parametrize('platform,enabled', [('linux',True),('win32',False),('darwin',False)])
def test_auto_platform_capabilities(platform, enabled):
    assert capabilities(platform_name=platform)['simulation_enabled'] is enabled
    assert not capabilities('landing', platform)['simulation_enabled']


def test_explicit_compute_rejects_unsupported_platform():
    with pytest.raises(ValueError, match='landing'):
        capabilities('compute', 'darwin')


def test_windows_compute_requires_explicit_experimental_opt_in():
    assert not capabilities('auto', 'win32')['simulation_enabled']
    support = capabilities('compute', 'win32')
    assert support['simulation_enabled'] and support['experimental']


@pytest.mark.parametrize('platform', ['linux','win32','darwin'])
def test_preview_never_initializes_worker_and_exports_exact_config(tmp_path, monkeypatch, platform):
    monkeypatch.setattr('spinfreq.web.app.capabilities', lambda mode: capabilities(mode, platform))
    def forbidden(*args, **kwargs):
        pytest.fail('Preview must never initialize the Linux job manager')
    monkeypatch.setattr('spinfreq.web.app.JobManager', forbidden)
    mode = 'landing' if platform == 'linux' else 'auto'
    directory = tmp_path/'must-not-create'
    with TestClient(create_app(directory, mode=mode)) as client:
        assert client.get('/').status_code == 200
        assert client.get('/workbench').status_code == 200
        assert client.get('/static/spinfreq-logo.png').headers['content-type'] == 'image/png'
        assert client.get('/api/jobs').json() == []
        assert not client.get('/api/capabilities').json()['simulation_enabled']
        config = presets()['confined-skyrmion'].to_dict()
        normalized = client.post('/api/config/validate', json=config)
        assert normalized.status_code == 200 and normalized.json() == json.loads(json.dumps(config))
        assert client.post('/api/jobs', json=config).status_code == 503
        assert client.get('/api/jobs/unknown').status_code == 503
        assert client.post('/api/config/validate', json={'nx':True}).status_code == 422
        assert client.post('/api/config/validate', content='x'*17000, headers={'Content-Type':'application/json'}).status_code == 413
    assert not directory.exists()
