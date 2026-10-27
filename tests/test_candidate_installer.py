"""Installer fixtures check integrity/behavior; they are not native worker evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

ASSETS = Path(__file__).resolve().parents[1]/'scripts/release_assets'
spec = importlib.util.spec_from_file_location('candidate_install', ASSETS/'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path/'candidate with spaces'; root.mkdir()
    for name in installer.ASSETS:
        shutil.copyfile(ASSETS/name, root/name)
    (root/'candidate.json').write_text(json.dumps({'version': '0.1.0rc2', 'status': 'synthetic_installer_fixture'}))
    (root/'INSTALL.md').write_text('Synthetic installer fixture; not native execution evidence.\n')
    wheel = root/'spinfreq-0.1.0rc2-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('spinfreq-0.1.0rc2.dist-info/METADATA', 'Name: spinfreq\nVersion: 0.1.0rc2\n')
    def seal():
        files = {p.name: installer.digest(p) for p in root.iterdir() if p.is_file() and p.name != 'checksums.json'}
        (root/'checksums.json').write_text(json.dumps(files))
    seal()
    return root, seal


def test_verify_only_is_readonly_and_accepts_later_results(bundle):
    root, _ = bundle
    original = {p.name: p.read_bytes() for p in root.iterdir()}
    subprocess.run([__import__('sys').executable, str(root/'install.py'), '--verify-only'], cwd=root.parent,
                   check=True, capture_output=True)
    assert {p.name: p.read_bytes() for p in root.iterdir()} == original
    (root/'results').mkdir(); (root/'results/keep.txt').write_text('keep')
    assert installer.verify_bundle(root)['verified_files'] == len(original)-1
    assert not (root/'.venv').exists()


@pytest.mark.parametrize('change', ['damaged', 'missing', 'missing-checksum', 'extra-wheel', 'version', 'traversal', 'duplicate-key'])
def test_bad_bundle_stops_before_environment_creation(bundle, change):
    root, seal = bundle
    if change == 'damaged': (root/'INSTALL.md').write_text('changed')
    elif change == 'missing': (root/'Run-Demo.cmd').unlink()
    elif change == 'extra-wheel': (root/'extra.whl').write_bytes(b'not recorded')
    elif change == 'version':
        (root/'candidate.json').write_text('{"version":"0.1.0"}'); seal()
    else:
        path = root/'checksums.json'; checksums = json.loads(path.read_text())
        if change == 'missing-checksum': del checksums['install.py']
        elif change == 'traversal': checksums['../outside'] = '0'*64
        if change == 'duplicate-key':
            path.write_text('{"candidate.json":"'+checksums['candidate.json']+'","candidate.json":"'+'0'*64+'"}')
        else: path.write_text(json.dumps(checksums))
    with pytest.raises((ValueError, OSError)):
        installer.install(root)
    assert not (root/'.venv').exists()
    assert not (root/'installation.json').exists()


def fake_processes(root, monkeypatch, fail_doctor=False):
    created, commands = [], []
    class Builder:
        def __init__(self, **kwargs): pass
        def create(self, path):
            created.append(path)
            python = installer._venv_python(path); python.parent.mkdir(parents=True)
            python.write_bytes(b'fixture')
    monkeypatch.setattr(installer.venv, 'EnvBuilder', Builder)
    monkeypatch.setattr(installer.subprocess, 'check_output', lambda *args, **kw:
                        json.dumps({'prefix': str(root/'.venv'), 'bits': 64, 'version': [3, 12]}))
    def run(command, **kwargs):
        commands.append(command)
        if fail_doctor and 'from spinfreq.onboarding import doctor_main; doctor_main()' in command:
            raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(installer.subprocess, 'run', run)
    return created, commands


def test_reinstall_forces_exact_wheel_and_preserves_results(bundle, monkeypatch):
    root, _ = bundle
    created, commands = fake_processes(root, monkeypatch)
    first = installer.install(root)
    (root/'results').mkdir(); sentinel = root/'results/keep.txt'; sentinel.write_text('keep')
    second = installer.install(root)
    assert len(created) == 1 and sentinel.read_text() == 'keep'
    assert first['status'] == second['status'] == 'installed_and_cpu_check_passed'
    assert json.loads((root/'installation.json').read_text())['wheel_sha256'] == first['wheel_sha256']
    assert sum('--force-reinstall' in command and '--no-deps' in command for command in commands) == 2
    assert all('-I' in command for command in commands)
    assert second['browser_worker_promotion'] is False


def test_failed_check_removes_old_success_marker(bundle, monkeypatch):
    root, _ = bundle
    fake_processes(root, monkeypatch, fail_doctor=True)
    (root/'installation.json').write_text('{"status":"previous success"}')
    with pytest.raises(subprocess.CalledProcessError):
        installer.install(root)
    assert not (root/'installation.json').exists()
