"""Candidate assembly parser/unit fixtures; never evidence of native execution."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest
from spinfreq.qualification import EvidenceError, sha256

spec = importlib.util.spec_from_file_location('prepare_release_candidate', Path(__file__).resolve().parents[1]/'scripts/prepare_release_candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    source, dist = tmp_path/'source', tmp_path/'dist'
    source.mkdir(); dist.mkdir()
    for name in ['README.md', 'LICENSE', 'CHANGELOG.md', 'CITATION.cff', 'spinfreq/core.py', 'docs/first.md', 'tests/test_first.py']:
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture\n')
    (source/'pyproject.toml').write_text('[project]\nname="spinfreq"\nversion="0.1.0rc2"\n')
    shutil.copytree(Path(__file__).resolve().parents[1]/'scripts/release_assets', source/'scripts/release_assets',
                    ignore=shutil.ignore_patterns('__pycache__'))
    wheel = dist/'spinfreq-0.1.0rc2-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('spinfreq/core.py', b'fixture\n')
        archive.writestr('spinfreq-0.1.0rc2.dist-info/METADATA', 'Name: spinfreq\nVersion: 0.1.0rc2\n')
    def sdist(omit=None, extra=None):
        with tarfile.open(dist/'spinfreq-0.1.0rc2.tar.gz', 'w:gz') as archive:
            for path in source.rglob('*'):
                if path.is_file() and path.relative_to(source).as_posix() != omit:
                    archive.add(path, arcname='spinfreq-0.1.0rc2/'+path.relative_to(source).as_posix())
            contents = b'Name: spinfreq\nVersion: 0.1.0rc2\n'
            info = tarfile.TarInfo('spinfreq-0.1.0rc2/PKG-INFO'); info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))
            if extra:
                info = tarfile.TarInfo(extra); info.size = 1
                archive.addfile(info, io.BytesIO(b'x'))
    sdist()
    linux, windows = tmp_path/'linux', tmp_path/'windows'
    for directory in (linux, windows):
        directory.mkdir()
        (directory/'report.json').write_text(json.dumps({'files': {}, 'ci': {
            'GITHUB_RUN_ID': '42', 'GITHUB_SHA': 'a'*40,
            'RUNNER_OS': 'Linux' if directory == linux else 'Windows'}}))
    monkeypatch.setattr(candidate, 'source_revision', lambda _: 'a'*40)
    monkeypatch.setattr(candidate, 'source_is_dirty', lambda _: False)
    # Only the orchestration boundary is stubbed. Actual evidence parsing and
    # native-test requirements have rejection coverage in test_qualification.
    monkeypatch.setattr(candidate, 'verify_evidence', lambda directory, source, platform, **kw:
                        {'package_version': '0.1.0rc2', 'native_windows_gate_passed': platform == 'win32'})
    jobs = {name: {'result': 'success'} for name in candidate.REQUIRED_JOBS}
    output = tmp_path/'candidate'
    def run():
        return candidate.prepare_candidate(source, dist, linux, windows, jobs, output,
                                           expected_revision='a'*40, expected_run_id='42')
    return source, dist, jobs, output, run, sdist, windows


def test_candidate_bundle_checksums_and_no_publication(inputs):
    _, _, _, output, run, _, _ = inputs
    report = run()
    assert report['publication_performed'] is False
    assert report['status'] == 'candidate_checks_passed_review_required'
    assert '.venv\\Scripts\\spinfreq-demo.exe' in (output/'INSTALL.md').read_text()
    for name, checksum in json.loads((output/'checksums.json').read_text()).items():
        assert sha256((output/name).read_bytes()) == checksum
    subprocess.run([sys.executable, str(output/'install.py'), '--verify-only'],
                   capture_output=True, text=True, check=True)
    with pytest.raises(FileExistsError):
        run()


@pytest.mark.parametrize('result', ['failure', 'cancelled', 'skipped'])
def test_unsuccessful_ci_job_blocks_candidate(inputs, result):
    _, _, jobs, output, run, _, _ = inputs
    jobs['test']['result'] = result
    with pytest.raises(EvidenceError, match='did not succeed'):
        run()
    assert not output.exists()


def test_missing_ci_result_blocks_candidate(inputs):
    _, _, jobs, output, run, _, _ = inputs
    del jobs['platform-workers']
    with pytest.raises(EvidenceError, match='missing'):
        run()
    assert not output.exists()


def test_stale_wheel_blocks_candidate(inputs):
    source, _, _, output, run, _, _ = inputs
    (source/'spinfreq/core.py').write_text('changed\n')
    with pytest.raises(EvidenceError, match='Wheel contents'):
        run()
    assert not output.exists()


@pytest.mark.parametrize('change', ['missing-doc', 'traversal'])
def test_invalid_sdist_blocks_candidate(inputs, change):
    _, _, _, output, run, sdist, _ = inputs
    sdist(omit='docs/first.md') if change == 'missing-doc' else sdist(extra='../escape')
    with pytest.raises(EvidenceError, match='distribution'):
        run()
    assert not output.exists()


def test_missing_actual_windows_evidence_blocks_candidate(inputs, monkeypatch):
    from spinfreq.qualification import verify_evidence
    _, _, _, output, run, _, windows = inputs
    real = verify_evidence
    stub = candidate.verify_evidence
    monkeypatch.setattr(candidate, 'verify_evidence', lambda directory, source, platform, **kw:
                        real(directory, source, platform, **kw) if platform == 'win32' else stub(directory, source, platform, **kw))
    (windows/'report.json').unlink()
    with pytest.raises(FileNotFoundError):
        run()
    assert not output.exists()


def test_dirty_source_blocks_candidate(inputs, monkeypatch):
    _, _, _, output, run, _, _ = inputs
    monkeypatch.setattr(candidate, 'source_is_dirty', lambda _: True)
    with pytest.raises(EvidenceError, match='clean'):
        run()
    assert not output.exists()


def test_other_ci_run_evidence_blocks_candidate(inputs):
    _, _, _, output, run, _, windows = inputs
    report = json.loads((windows/'report.json').read_text())
    report['ci']['GITHUB_RUN_ID'] = '41'
    (windows/'report.json').write_text(json.dumps(report))
    with pytest.raises(EvidenceError, match='intended CI run'):
        run()
    assert not output.exists()
