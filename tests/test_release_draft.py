"""Draft preparation fixtures test policy/data parsing, not native execution."""
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
from urllib.error import HTTPError
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('prepare_release_draft', Path(__file__).resolve().parents[1]/'scripts/prepare_release_draft.py')
draft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draft)


def run_metadata():
    return {'id': 42, 'repository': {'full_name': 'spinuni/spinfreq'},
            'head_repository': {'full_name': 'spinuni/spinfreq'}, 'head_sha': 'a'*40,
            'head_branch': 'main', 'event': 'push', 'status': 'completed',
            'conclusion': 'success', 'path': '.github/workflows/ci.yml'}


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    source, candidate = tmp_path/'source', tmp_path/'candidate'
    source.mkdir(); candidate.mkdir()
    for name in ('README.md', 'LICENSE', 'CHANGELOG.md', 'CITATION.cff', 'spinfreq/core.py'):
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('# fixture\n')
    (source/'pyproject.toml').write_text('[project]\nname="spinfreq"\nversion="0.1.0rc2"\n')
    notes = source/'docs/releases/NOTES.md'; notes.parent.mkdir(parents=True)
    notes.write_text('# SpinFreq 0.1.0rc2\n\nSynthetic release fixture, not native evidence.\n')
    shutil.copytree(Path(__file__).resolve().parents[1]/'scripts/release_assets', source/'scripts/release_assets',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in draft.bootstrap.ASSETS:
        shutil.copyfile(source/'scripts/release_assets'/name, candidate/name)
    (candidate/'INSTALL.md').write_text('Synthetic fixture\n')
    with zipfile.ZipFile(candidate/'spinfreq-0.1.0rc2-py3-none-any.whl', 'w') as archive:
        archive.writestr('spinfreq/core.py', '# fixture\n')
        archive.writestr('spinfreq-0.1.0rc2.dist-info/METADATA', 'Name: spinfreq\nVersion: 0.1.0rc2\n')
    with tarfile.open(candidate/'spinfreq-0.1.0rc2.tar.gz', 'w:gz') as archive:
        for path in source.rglob('*'):
            if path.is_file(): archive.add(path, arcname='spinfreq-0.1.0rc2/'+path.relative_to(source).as_posix())
        data = b'Name: spinfreq\nVersion: 0.1.0rc2\n'
        info = tarfile.TarInfo('spinfreq-0.1.0rc2/PKG-INFO'); info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    report = {'schema_version': 1, 'status': 'candidate_checks_passed_review_required', 'version': '0.1.0rc2',
              'revision': 'a'*40, 'ci_run_id': '42', 'publication_performed': False,
              'ci_results': {name: {'result': 'success'} for name in draft.assembly.REQUIRED_JOBS},
              'evidence_report_sha256': {}}
    for platform in ('linux', 'win32'):
        path = candidate/'evidence'/platform/'report.json'; path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'ci': {'GITHUB_RUN_ID': '42', 'GITHUB_SHA': 'a'*40}}))
        report['evidence_report_sha256'][platform] = draft.bootstrap.digest(path)
    def seal():
        (candidate/'candidate.json').write_text(json.dumps(report))
        files = {p.relative_to(candidate).as_posix(): draft.bootstrap.digest(p) for p in candidate.rglob('*')
                 if p.is_file() and p.name != 'checksums.json'}
        (candidate/'checksums.json').write_text(json.dumps(files))
    seal()
    monkeypatch.setattr(draft, 'source_revision', lambda _: 'a'*40)
    monkeypatch.setattr(draft, 'source_is_dirty', lambda _: False)
    monkeypatch.setattr(draft, 'verify_evidence', lambda *args, **kwargs:
                        {'package_version': '0.1.0rc2', 'native_windows_gate_passed': True})
    output = tmp_path/'payload'
    def prepare(run=None, check_tag=lambda _: False):
        return draft.prepare_draft(source, candidate, output, run or run_metadata(), repository='spinuni/spinfreq',
                                   revision='a'*40, run_id='42', check_tag=check_tag)
    return source, candidate, output, report, seal, prepare


def test_draft_payload_preserves_installable_bundle_and_hashes(bundle):
    _, candidate, output, _, _, prepare = bundle
    plan = prepare()
    assert plan['draft'] and plan['prerelease'] and not plan['publication_performed']
    assert plan['tag'] == 'v0.1.0rc2'
    for name, digest in plan['assets_sha256'].items():
        assert draft.bootstrap.digest(output/name) == digest
    with zipfile.ZipFile(output/'SpinFreq-v0.1.0rc2.zip') as archive:
        assert set(archive.namelist()) == {p.relative_to(candidate).as_posix() for p in candidate.rglob('*') if p.is_file()}
        checksums = json.loads(archive.read('checksums.json'))
        for name, digest in checksums.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    assert 'actions/runs/42' in (output/'release-notes.md').read_text()
    assert (output/'SHA256SUMS.txt').is_file()


@pytest.mark.parametrize('key,value', [('event', 'pull_request'), ('head_branch', 'feature'), ('conclusion', 'failure'),
                                      ('status', 'in_progress'), ('head_sha', 'b'*40), ('id', 43),
                                      ('path', '.github/workflows/other.yml'),
                                      ('head_repository', {'full_name': 'fork/spinfreq'})])
def test_untrusted_or_wrong_ci_run_rejected(bundle, key, value):
    _, _, output, _, _, prepare = bundle
    run = run_metadata(); run[key] = value
    with pytest.raises(ValueError, match='successful Package checks'):
        prepare(run)
    assert not output.exists()


@pytest.mark.parametrize('change', ['wrong-run', 'failed-job', 'extra-file', 'damaged-wheel', 'missing-native', 'existing-tag'])
def test_invalid_candidate_never_produces_release_payload(bundle, change, monkeypatch):
    _, candidate, output, report, seal, prepare = bundle
    if change == 'wrong-run': report['ci_run_id'] = '43'; seal()
    elif change == 'failed-job': report['ci_results']['test']['result'] = 'skipped'; seal()
    elif change == 'extra-file': (candidate/'installation.json').write_text('{}')
    elif change == 'damaged-wheel': (candidate/'spinfreq-0.1.0rc2-py3-none-any.whl').write_bytes(b'bad')
    elif change == 'missing-native':
        monkeypatch.setattr(draft, 'verify_evidence', lambda *a, **kw: (_ for _ in ()).throw(ValueError('Missing native execution')))
    with pytest.raises(ValueError):
        prepare(check_tag=lambda _: change == 'existing-tag')
    assert not output.exists()


def test_only_http_404_is_treated_as_an_unused_tag(monkeypatch):
    def not_found(*args): raise HTTPError('https://api.github.com', 404, 'missing', {}, None)
    monkeypatch.setattr(draft, 'github_get', not_found)
    assert not draft.tag_exists('spinuni/spinfreq', 'v0.1.0rc2', 'fixture')
    def forbidden(*args): raise HTTPError('https://api.github.com', 403, 'forbidden', {}, None)
    monkeypatch.setattr(draft, 'github_get', forbidden)
    with pytest.raises(HTTPError):
        draft.tag_exists('spinuni/spinfreq', 'v0.1.0rc2', 'fixture')
