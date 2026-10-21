"""Inspect platform evidence without executing or extracting its contents.

Hashes detect damaged/mismatched artifacts, not a maliciously forged report.
Native execution still requires a trusted runner and review of its provenance.
"""
import argparse
from dataclasses import replace
from email.parser import BytesParser
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from .config import JobConfig, presets
from .jobs import ARTIFACTS


TEST_FILES = ('test_runtime.py', 'test_web.py', 'test_jobs.py', 'test_portable_web.py')
WINDOWS_REQUIRED = {
    'test_windows_memory_limit_rejects_large_allocation',
    'test_windows_cpu_limit_terminates_busy_worker',
    'test_windows_failed_assignment_never_releases_gate',
    'test_windows_cancellation_and_completion_remove_descendants[cancel]',
    'test_windows_cancellation_and_completion_remove_descendants[complete]',
}
BASE_REQUIRED = {
    'test_job_object_abi_uses_windows_integer_widths',
    'test_startup_gate_requires_owner_token_and_preserves_standard_input',
    'test_browser_api_to_real_worker_download_and_isolation',
    'test_malformed_oversized_and_cross_origin_requests',
    'test_queue_capacity_cancel_delete_and_exclusive_owner',
    'test_restart_marks_incomplete_work_interrupted',
    'test_corrupt_journal_releases_storage_lease',
    'test_status_publication_failure_terminates_new_worker',
    'test_timeout_kills_worker_and_queue_recovers',
    'test_disk_limit_terminates_an_active_worker',
    'test_server_crash_kills_worker_and_restart_recovers',
    'test_job_analytic_periodic_fmr_and_download_manifest',
    'test_large_response_fails_without_exporting_spectra',
    'test_failed_equilibrium_does_not_reach_spectral_solver',
    'test_unstable_and_neutral_macrospins_withhold_spectra[unstable]',
    'test_unstable_and_neutral_macrospins_withhold_spectra[uncertain]',
    'test_windows_compute_requires_explicit_experimental_opt_in',
}
REQUIRED_FILES = {'tests.xml', 'pytest.log', 'browser.log', 'server.log', 'entrypoints.log', 'package.whl',
                  'browser/summary.json', 'browser/results.zip',
                  'browser/desktop.png', 'browser/mobile.png', 'browser/landing.png'}


class EvidenceError(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_digest(name, data):
    # Git may check the same revision out with CRLF on Windows. Normalize text
    # only; artifact/wheel/result checksums above remain exact byte hashes.
    if Path(name).suffix in ('.py', '.html', '.js', '.css', '.toml'):
        data = data.replace(b'\r\n', b'\n')
    return sha256(data)


def package_fingerprint(directory):
    directory = Path(directory)
    records = {p.relative_to(directory).as_posix(): source_digest(p.name, p.read_bytes())
               for p in sorted(directory.rglob('*')) if p.is_file()
               and '__pycache__' not in p.parts and p.suffix in ('.py', '.html', '.js', '.css', '.png')}
    if not records:
        raise EvidenceError('No package files found')
    return sha256(json.dumps(records, sort_keys=True).encode())


def procedure_fingerprint(source):
    source = Path(source)
    names = [f'tests/{name}' for name in TEST_FILES]
    names += ['scripts/qualify_platform.py', 'scripts/browser_smoke.py', 'pyproject.toml']
    return sha256(json.dumps({name: source_digest(name, (source/name).read_bytes()) for name in names}, sort_keys=True).encode())


def source_revision(source):
    try:
        return subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def source_is_dirty(source):
    try:
        return bool(subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'],
                                            text=True, stderr=subprocess.DEVNULL).strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def junit_results(path, expected_platform):
    root = ET.parse(path).getroot()
    cases = root.findall('.//testcase')
    if not cases:
        raise EvidenceError('JUnit contains no tests')
    passed, skipped, identities = set(), set(), set()
    for case in cases:
        identity = (case.get('classname'), case.get('name'))
        if identity in identities:
            raise EvidenceError('Duplicate JUnit testcase')
        identities.add(identity)
        if case.find('failure') is not None or case.find('error') is not None:
            raise EvidenceError(f'Failed JUnit case: {identity}')
        # Bind required names to the selected test modules, not arbitrary classes.
        module = (identity[0] or '').rsplit('.', 1)[-1]+'.py'
        if module not in TEST_FILES:
            raise EvidenceError(f'Unexpected JUnit module: {identity[0]}')
        runtime_cases = WINDOWS_REQUIRED | {'test_job_object_abi_uses_windows_integer_widths',
                                           'test_startup_gate_requires_owner_token_and_preserves_standard_input'}
        if identity[1] in runtime_cases and module != 'test_runtime.py':
            raise EvidenceError('Required runtime test appeared under the wrong module')
        (skipped if case.find('skipped') is not None else passed).add(identity[1])
    required = BASE_REQUIRED | (WINDOWS_REQUIRED if expected_platform == 'win32' else set())
    if not required <= passed:
        raise EvidenceError(f'Missing/pending required tests: {sorted(required-passed)}')
    allowed_skips = WINDOWS_REQUIRED if expected_platform.startswith('linux') else set()
    if skipped-allowed_skips:
        raise EvidenceError(f'Unexpected skipped tests: {sorted(skipped-allowed_skips)}')
    return {'passed':len(cases)-len(skipped), 'skipped':len(skipped),
            'native_windows_required_passed':WINDOWS_REQUIRED <= passed}


def verify_result_archive(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = {item.filename for item in infos}
        expected = set(ARTIFACTS)-{'results.zip'}
        if names != expected or len(names) != len(infos):
            raise EvidenceError('Result archive has missing, duplicate or unexpected files')
        if sum(item.file_size for item in infos) > 96*1024**2 or max(item.file_size for item in infos) > 32*1024**2:
            raise EvidenceError('Result archive exceeds file/job bounds')
        manifest = json.loads(archive.read('manifest.json'))
        if set(manifest) != names-{'manifest.json'}:
            raise EvidenceError('Result manifest coverage is incomplete')
        for name, digest in manifest.items():
            if sha256(archive.read(name)) != digest:
                raise EvidenceError(f'Result checksum mismatch: {name}')
        config = JobConfig.from_dict(json.loads(archive.read('configuration.json')))
        if config != replace(presets()['prism-fmr'], points=21):
            raise EvidenceError('Browser did not run the prescribed prism configuration')
        summary = json.loads(archive.read('summary.json'))
        encoded = json.dumps(config.to_dict(), sort_keys=True, separators=(',', ':')).encode()
        if summary.get('configuration_sha256') != sha256(encoded):
            raise EvidenceError('Result configuration hash mismatch')
        if summary.get('status') != 'succeeded' or summary.get('stability') != 'stable':
            raise EvidenceError('Browser numerical job did not pass')
        for name, limit in [('torque_T', config.torque_tolerance_T), ('max_delta_m', .05),
                            ('max_response_residual', 1e-7), ('max_relative_eigen_residual', 1e-7),
                            ('max_basis_residual', 1e-7)]:
            value = summary.get(name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= limit:
                raise EvidenceError(f'Result numerical diagnostic failed: {name}')
        return summary


def verify_wheel(path, fingerprint, package_version):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or sum(i.file_size for i in archive.infolist()) > 96*1024**2:
            raise EvidenceError('Wheel contains duplicate entries or exceeds evidence bounds')
        metadata_names = [name for name in names if name.endswith('.dist-info/METADATA')]
        if len(metadata_names) != 1:
            raise EvidenceError('Wheel metadata missing or ambiguous')
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        if metadata['Name'] != 'spinfreq' or metadata['Version'] != package_version:
            raise EvidenceError('Wheel name/version mismatch')
        records = {name.removeprefix('spinfreq/'):source_digest(name, archive.read(name)) for name in names
                   if name.startswith('spinfreq/') and Path(name).suffix in ('.py', '.html', '.js', '.css', '.png')}
        if sha256(json.dumps(records, sort_keys=True).encode()) != fingerprint:
            raise EvidenceError('Wheel contents disagree with qualified package source')


def verify_evidence(directory, source, expected_platform, *, expected_revision=None, require_clean=False):
    directory, source = Path(directory).resolve(), Path(source).resolve()
    if expected_platform not in ('linux', 'win32'):
        raise EvidenceError('Require expected platform linux or win32')
    report = json.loads((directory/'report.json').read_text())
    if not isinstance(report, dict):
        raise EvidenceError('Report must be an object')
    if type(report.get('schema_version')) is not int or report.get('schema_version') != 1 or report.get('platform') != expected_platform:
        raise EvidenceError('Evidence platform/schema mismatch')
    if report.get('phases') != {'entrypoints':0, 'pytest':0, 'browser':0}:
        raise EvidenceError('Evidence contains an incomplete or failed execution phase')
    if report.get('installation') != 'wheel' or report.get('package_version') is None:
        raise EvidenceError('Evidence must exercise an installed wheel')
    if report.get('package_fingerprint') != package_fingerprint(source/'spinfreq'):
        raise EvidenceError('Evidence package source is stale or mismatched')
    if report.get('procedure_fingerprint') != procedure_fingerprint(source):
        raise EvidenceError('Evidence tests/procedure are stale or mismatched')
    current_revision = source_revision(source)
    if expected_revision and expected_revision != current_revision:
        raise EvidenceError('Requested revision does not match the source checkout')
    revision = expected_revision or current_revision
    if revision is None or report.get('revision') != revision:
        raise EvidenceError('Evidence revision mismatch or unavailable')
    if require_clean and (report.get('source_dirty') is not False or source_is_dirty(source) is not False):
        raise EvidenceError('Release evidence requires a clean source tree')
    manifest = report.get('files', {})
    if not isinstance(manifest, dict) or not REQUIRED_FILES <= manifest.keys():
        raise EvidenceError('Evidence bundle is incomplete')
    for name, digest in manifest.items():
        parts = PurePosixPath(name)
        path = (directory/name).resolve()
        if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name or not path.is_relative_to(directory):
            raise EvidenceError('Unsafe evidence artifact path')
        if not path.is_file() or sha256(path.read_bytes()) != digest:
            raise EvidenceError(f'Evidence checksum mismatch: {name}')
    tests = junit_results(directory/'tests.xml', expected_platform)
    verify_wheel(directory/'package.whl', report['package_fingerprint'], report['package_version'])
    browser = json.loads((directory/'browser/summary.json').read_text())
    session = report.get('qualification_session')
    if not isinstance(session, str) or len(session) != 32 or browser.get('qualification_session') != session:
        raise EvidenceError('Browser/server session mismatch')
    runtime = 'windows-job-object-experimental' if expected_platform == 'win32' else 'linux-rlimit'
    if (browser.get('server_platform') != expected_platform or browser.get('worker_runtime') != runtime
            or browser.get('ui_worker_download_passed') is not True or browser.get('images_loaded') != 3
            or browser.get('javascript_errors') != [] or browser.get('mobile_horizontal_overflow') is not False):
        raise EvidenceError('Browser/runtime qualification failed or used the wrong platform')
    summary = verify_result_archive(directory/'browser/results.zip')
    if summary.get('qualification_session') != session:
        raise EvidenceError('Downloaded result belongs to a different server session')
    if (summary.get('worker_runtime') != runtime or summary.get('package_version') != report['package_version']
            or summary.get('configuration_sha256') != browser.get('configuration_sha256')):
        raise EvidenceError('Downloaded result provenance disagrees with the report')
    return {'platform':expected_platform, 'revision':revision, 'checks_passed':True,
            'clean_source_required':require_clean,
            'package_version':report['package_version'], 'tests':tests,
            'native_windows_gate_passed':expected_platform == 'win32' and tests['native_windows_required_passed'],
            'trusted_runner_review_required':True}


def main():
    parser = argparse.ArgumentParser(description='Check installed-package platform evidence against a source checkout')
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--expect-platform', choices=('linux', 'win32'), required=True)
    parser.add_argument('--expect-revision')
    parser.add_argument('--require-clean', action='store_true')
    args = parser.parse_args()
    try:
        result = verify_evidence(args.directory, args.source_root, args.expect_platform,
                                 expected_revision=args.expect_revision, require_clean=args.require_clean)
    except (ValueError, OSError, ET.ParseError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Qualification rejected: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
