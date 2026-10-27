"""One installed-wheel platform qualification, including a real browser.

Run from a checkout after building and installing its wheel. No publishing,
default-mode changes, or native-Windows claims are inferred from Linux results.
"""
import argparse
from importlib.metadata import version, distribution
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid

import spinfreq
from spinfreq.qualification import (TEST_FILES, package_fingerprint, procedure_fingerprint,
                                    sha256, source_revision, verify_evidence)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--expect-platform', choices=('linux', 'win32'), required=True)
    parser.add_argument('--require-clean', action='store_true')
    args = parser.parse_args()
    source, output, wheel = args.source_root.resolve(), args.output.resolve(), args.wheel.resolve()
    if wheel.is_dir():
        wheels = list(wheel.glob('*.whl'))
        if len(wheels) != 1:
            parser.error('Wheel directory must contain exactly one wheel')
        wheel = wheels[0]
    if sys.platform != args.expect_platform:
        parser.error('Run on the expected native platform; cross-platform reports are refused')
    installed = Path(spinfreq.__file__).resolve().parent
    dist = distribution('spinfreq')
    distribution_package = Path(dist.locate_file('spinfreq/__init__.py')).resolve().parent
    if installed == (source/'spinfreq').resolve() or installed != distribution_package or not dist.read_text('WHEEL'):
        parser.error('Install the built wheel first; checkout/editable imports cannot qualify a distribution')
    fingerprint = package_fingerprint(source/'spinfreq')
    if package_fingerprint(installed) != fingerprint:
        parser.error('Installed package does not match this source tree')
    if not wheel.is_file():
        parser.error('Wheel file does not exist')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error('Use an empty output directory')
    dirty = bool(subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True).strip())
    report = {'schema_version':1, 'platform':sys.platform, 'installation':'wheel',
              'package_version':version('spinfreq'), 'package_fingerprint':fingerprint,
              'procedure_fingerprint':procedure_fingerprint(source), 'revision':source_revision(source),
              'source_dirty':dirty, 'python':sys.version, 'phases':{},
              'qualification_session':uuid.uuid4().hex,
              'ci':{key:os.environ.get(key) for key in ('GITHUB_RUN_ID', 'GITHUB_SHA', 'RUNNER_OS')}}
    shutil.copyfile(wheel, output/'package.whl')
    environment = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', MPLBACKEND='Agg')
    environment.pop('PYTHONPATH', None)
    environment['SPINFREQ_QUALIFICATION_SESSION'] = report['qualification_session']
    tests = [str(source/'tests'/name) for name in TEST_FILES]
    def run(name, command, cwd, timeout):
        with (output/(name+'.log')).open('wb') as log:
            try:
                result = subprocess.run(command, cwd=cwd, env=environment, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=timeout)
                report['phases'][name] = result.returncode
                return result.returncode == 0
            except subprocess.TimeoutExpired:
                report['phases'][name] = 'timeout'
                return False
    with tempfile.TemporaryDirectory(prefix='spinfreq-qualification-') as cwd:
        probe_code = '''import os,subprocess,sys,sysconfig
from pathlib import Path
for name in ('spinfreq','spinfreq-web','spinfreq-verify-evidence','spinfreq-examples'):
 path=Path(sysconfig.get_path('scripts'))/(name+('.exe' if os.name=='nt' else ''))
 subprocess.run([str(path),'--help'],check=True,timeout=20)
'''
        passed = run('entrypoints', [sys.executable, '-c', probe_code], cwd, 100)
        if passed:
            passed = run('pytest', [sys.executable, '-m', 'pytest', '--import-mode=importlib', '-q',
                                    *tests, '--junitxml', str(output/'tests.xml')], cwd, 240)
        if passed:
            # Bind only to loopback; closing this probe before launch leaves a
            # small port-allocation race. A unique session rejects other servers.
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
            with (output/'server.log').open('wb') as log:
                server = subprocess.Popen([sys.executable, '-u', '-m', 'spinfreq.web.app', '--mode', 'compute',
                                           '--port', str(port), '--data-dir', str(output/'jobs')],
                                          cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT)
                try:
                    passed = run('browser', [sys.executable, str(source/'scripts/browser_smoke.py'),
                                             '--url', f'http://127.0.0.1:{port}', '--output', str(output/'browser'),
                                             '--session', report['qualification_session']], cwd, 180)
                    if server.poll() is not None:
                        report['phases']['unexpected_server_exit'] = server.returncode
                        passed = False
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill(); server.wait(timeout=5)
    # The recorded inputs must still be the same after the subprocesses finish.
    if package_fingerprint(source/'spinfreq') != fingerprint:
        report['phases']['source_changed_during_run'] = True
        passed = False
    paths = [output/'package.whl', output/'tests.xml', *output.glob('*.log'), *(output/'browser').glob('*')]
    report['files'] = {p.relative_to(output).as_posix():sha256(p.read_bytes()) for p in paths if p.is_file()}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    try:
        if not passed:
            raise ValueError('One or more qualification phases failed; inspect logs')
        result = verify_evidence(output, source, args.expect_platform,
                                  expected_revision=report['revision'], require_clean=args.require_clean)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Qualification failed: {error}\nEvidence retained at {output}\n')
    (output/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
