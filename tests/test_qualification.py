"""Synthetic parser fixtures test rejection; they are never native evidence."""
from dataclasses import replace
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest
from spinfreq.config import presets
from spinfreq.jobs import ARTIFACTS
from spinfreq.qualification import (BASE_REQUIRED, WINDOWS_REQUIRED, REQUIRED_FILES, TEST_FILES,
    EvidenceError, package_fingerprint, procedure_fingerprint, sha256, verify_evidence)


def put_json(path, value):
    path.write_text(json.dumps(value))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    source = tmp_path/'source'; (source/'spinfreq').mkdir(parents=True)
    (source/'spinfreq/core.py').write_text('# synthetic fixture\n')
    for name in [*(f'tests/{name}' for name in TEST_FILES), 'scripts/qualify_platform.py', 'scripts/browser_smoke.py', 'pyproject.toml']:
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('# fixture\n')
    monkeypatch.setattr('spinfreq.qualification.source_revision', lambda path: 'a'*40)
    monkeypatch.setattr('spinfreq.qualification.source_is_dirty', lambda path: False)
    directory = tmp_path/'evidence'; (directory/'browser').mkdir(parents=True)
    config = replace(presets()['prism-fmr'], points=21).to_dict()
    digest = sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode())
    summary = dict(status='succeeded', stability='stable', configuration_sha256=digest,
                   qualification_session='1'*32,
                   worker_runtime='linux-rlimit', package_version='0.1.0rc2', torque_T=0.,
                   max_delta_m=1e-5, max_response_residual=1e-12, max_relative_eigen_residual=1e-12, max_basis_residual=1e-12)
    contents = {name:b'fixture bytes' for name in set(ARTIFACTS)-{'results.zip', 'manifest.json'}}
    contents['configuration.json'] = json.dumps(config).encode()
    contents['summary.json'] = json.dumps(summary).encode()
    def result_zip(updates=None):
        contents.update(updates or {})
        manifest = {name:sha256(data) for name, data in contents.items()}
        with zipfile.ZipFile(directory/'browser/results.zip', 'w') as archive:
            for name, data in contents.items(): archive.writestr(name, data)
            archive.writestr('manifest.json', json.dumps(manifest))
    result_zip()
    for name in REQUIRED_FILES-{'browser/results.zip', 'package.whl', 'tests.xml', 'browser/summary.json'}:
        (directory/name).write_bytes(b'fixture bytes')
    with zipfile.ZipFile(directory/'package.whl', 'w') as archive:
        archive.writestr('spinfreq/core.py', (source/'spinfreq/core.py').read_bytes())
        archive.writestr('spinfreq-0.1.0rc2.dist-info/METADATA', 'Name: spinfreq\nVersion: 0.1.0rc2\n')
    root = ET.Element('testsuites'); suite = ET.SubElement(root, 'testsuite')
    for name in sorted(BASE_REQUIRED | WINDOWS_REQUIRED):
        runtime = name in WINDOWS_REQUIRED or name.startswith(('test_job_object_', 'test_startup_gate_'))
        module = 'test_runtime' if runtime else 'test_web'
        case = ET.SubElement(suite, 'testcase', classname='tests.'+module, name=name)
        if name in WINDOWS_REQUIRED: ET.SubElement(case, 'skipped')
    ET.ElementTree(root).write(directory/'tests.xml')
    browser = dict(ui_worker_download_passed=True, images_loaded=3, javascript_errors=[],
                   qualification_session='1'*32,
                   mobile_horizontal_overflow=False, server_platform='linux', worker_runtime='linux-rlimit', configuration_sha256=digest)
    put_json(directory/'browser/summary.json', browser)
    report = dict(schema_version=1, platform='linux', installation='wheel', package_version='0.1.0rc2',
                  qualification_session='1'*32,
                  package_fingerprint=package_fingerprint(source/'spinfreq'), procedure_fingerprint=procedure_fingerprint(source),
                  revision='a'*40, source_dirty=False, phases={'entrypoints':0,'pytest':0,'browser':0})
    def seal():
        report['files'] = {name:sha256((directory/name).read_bytes()) for name in REQUIRED_FILES}
        put_json(directory/'report.json', report)
    seal()
    def verify(platform='linux', **kwargs):
        return verify_evidence(directory, source, platform, expected_revision='a'*40, **kwargs)
    return directory, source, report, browser, summary, seal, verify, result_zip


def test_linux_report_cannot_close_windows_gate(bundle):
    *_, verify, result_zip = bundle
    result = verify()
    assert result['checks_passed'] and not result['native_windows_gate_passed']
    with pytest.raises(EvidenceError, match='platform'):
        verify('win32')


def make_windows(bundle):
    directory, source, report, browser, summary, seal, verify, result_zip = bundle
    report['platform'] = browser['server_platform'] = 'win32'
    browser['worker_runtime'] = summary['worker_runtime'] = 'windows-job-object-experimental'
    tree = ET.parse(directory/'tests.xml')
    for case in tree.findall('.//testcase'):
        for child in list(case): case.remove(child)
    tree.write(directory/'tests.xml')
    put_json(directory/'browser/summary.json', browser)
    result_zip({'summary.json':json.dumps(summary).encode()}); seal()


def test_complete_synthetic_windows_parser_fixture(bundle):
    make_windows(bundle)
    assert bundle[6]('win32')['native_windows_gate_passed']


@pytest.mark.parametrize('change', ['skip', 'missing', 'failure', 'duplicate'])
def test_native_test_defects_are_rejected(bundle, change):
    make_windows(bundle)
    directory, _, _, _, _, seal, verify, _ = bundle
    tree = ET.parse(directory/'tests.xml'); suite = tree.find('testsuite')
    case = next(c for c in suite if c.get('name') in WINDOWS_REQUIRED)
    if change == 'skip': ET.SubElement(case, 'skipped')
    elif change == 'failure': ET.SubElement(case, 'failure')
    elif change == 'missing': suite.remove(case)
    else: ET.SubElement(suite, 'testcase', case.attrib)
    tree.write(directory/'tests.xml'); seal()
    with pytest.raises(EvidenceError): verify('win32')


@pytest.mark.parametrize('field,value', [('worker_runtime','direct-python'),('javascript_errors',['bad JS']),('images_loaded',0),('qualification_session','wrong')])
def test_bad_browser_evidence_is_rejected(bundle, field, value):
    directory, _, _, browser, _, seal, verify, _ = bundle
    browser[field] = value; put_json(directory/'browser/summary.json', browser); seal()
    with pytest.raises(EvidenceError, match='Browser'):
        verify()


@pytest.mark.parametrize('target', ['spinfreq/core.py', 'tests/test_runtime.py'])
def test_stale_sources_and_procedures_are_rejected(bundle, target):
    _, source, _, _, _, _, verify, _ = bundle
    (source/target).write_text('# changed\n')
    with pytest.raises(EvidenceError, match='stale|mismatched'): verify()


def test_corrupt_artifact_is_rejected(bundle):
    directory, _, _, _, _, _, verify, _ = bundle
    (directory/'pytest.log').write_bytes(b'changed')
    with pytest.raises(EvidenceError, match='checksum'): verify()


@pytest.mark.parametrize('field,value', [('revision','b'*40),('source_dirty',True),('phases',{'pytest':1,'browser':0})])
def test_revision_dirty_and_phase_gates(bundle, field, value):
    _, _, report, _, _, seal, verify, _ = bundle
    report[field] = value; seal()
    with pytest.raises(EvidenceError): verify(require_clean=True)


def test_manifest_path_traversal_is_rejected(bundle):
    directory, _, report, _, _, _, verify, _ = bundle
    report['files']['../outside'] = '0'*64; put_json(directory/'report.json', report)
    with pytest.raises(EvidenceError, match='Unsafe'): verify()


def test_wrong_result_diagnostics_are_rejected_even_with_valid_hashes(bundle):
    _, _, _, _, summary, seal, verify, result_zip = bundle
    summary['max_delta_m'] = 1.
    result_zip({'summary.json':json.dumps(summary).encode()}); seal()
    with pytest.raises(EvidenceError, match='diagnostic'): verify()


def test_missing_archive_file_is_rejected(bundle):
    directory, _, _, _, _, seal, verify, _ = bundle
    with zipfile.ZipFile(directory/'browser/results.zip', 'w') as archive:
        archive.writestr('summary.json', '{}')
    seal()
    with pytest.raises(EvidenceError, match='missing'): verify()


def test_clean_source_claim_does_not_hide_a_dirty_checkout(bundle, monkeypatch):
    monkeypatch.setattr('spinfreq.qualification.source_is_dirty', lambda path: True)
    with pytest.raises(EvidenceError, match='clean'): bundle[6](require_clean=True)


def test_archive_from_another_server_session_is_rejected(bundle):
    _, _, _, _, summary, seal, verify, result_zip = bundle
    summary['qualification_session'] = '2'*32
    result_zip({'summary.json':json.dumps(summary).encode()}); seal()
    with pytest.raises(EvidenceError, match='different server'): verify()


def test_nested_result_checksum_is_checked_after_outer_checksum(bundle):
    directory, _, _, _, _, seal, verify, _ = bundle
    path = directory/'browser/results.zip'
    with zipfile.ZipFile(path) as archive:
        contents = {name:archive.read(name) for name in archive.namelist()}
    contents['response.csv'] = b'changed data'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in contents.items(): archive.writestr(name, data)
    seal()
    with pytest.raises(EvidenceError, match='Result checksum'): verify()


def test_wheel_version_must_match_the_report(bundle):
    directory, _, _, _, _, seal, verify, _ = bundle
    path = directory/'package.whl'
    with zipfile.ZipFile(path) as archive:
        contents = {name:archive.read(name) for name in archive.namelist()}
    contents['spinfreq-0.1.0rc2.dist-info/METADATA'] = b'Name: spinfreq\nVersion: 9.0\n'
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in contents.items(): archive.writestr(name, data)
    seal()
    with pytest.raises(EvidenceError, match='Wheel name/version'): verify()
