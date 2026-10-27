"""Exercise actual wheel installation in a synthetic installer-only bundle.

The fixture does not qualify a release or substitute for native worker evidence.
"""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    if wheel.is_dir():
        wheels = list(wheel.glob('*.whl'))
        if len(wheels) != 1: parser.error('Provide exactly one wheel')
        wheel = wheels[0]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ('install.py', 'Install.cmd', 'Run-Demo.cmd', 'Open-Web.cmd'):
        data = (ROOT/'scripts/release_assets'/name).read_bytes()
        if name.endswith('.cmd'):
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        (output/name).write_bytes(data)
    shutil.copyfile(wheel, output/wheel.name)
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
        version = BytesParser().parsebytes(archive.read(metadata_name))['Version']
    (output/'candidate.json').write_text(json.dumps({'version': version, 'status': 'installer_smoke_fixture',
                                                   'release_qualified': False})+'\n')
    (output/'INSTALL.md').write_text('Installer smoke fixture only; not a qualified release candidate.\n')
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output/'checksums.json').write_text(json.dumps(checksums, indent=2)+'\n')
    subprocess.run([sys.executable, str(output/'install.py'), '--verify-only'], check=True)
    if sys.platform == 'win32':
        subprocess.run(['cmd', '/c', 'Install.cmd', '--ci'], cwd=output, check=True)
        subprocess.run(['cmd', '/c', 'Run-Demo.cmd', '--ci'], cwd=output, check=True)
        python = output/'.venv/Scripts/python.exe'
    else:
        subprocess.run([sys.executable, str(output/'install.py')], check=True)
        python = output/'.venv/bin/python'
        subprocess.run([str(output/'.venv/bin/spinfreq-demo'), '--output', str(output/'results/demo')], check=True)
    # Integrity still passes after installation and result creation.
    subprocess.run([str(python), str(output/'install.py'), '--verify-only'], check=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    with (output/'preview.log').open('wb') as log:
        process = subprocess.Popen([str(python), '-I', '-m', 'spinfreq.web.app', '--mode', 'landing', '--port', str(port)],
                                   cwd=output, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic()+30
            while True:
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/capabilities', timeout=2) as response:
                        capabilities = json.load(response)
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('Installed preview did not start; inspect preview.log')
                    time.sleep(.1)
            if capabilities['simulation_enabled'] is not False:
                raise RuntimeError('Installer preview unexpectedly enabled protected computation')
            if process.poll() is not None:
                raise RuntimeError('Installed preview process exited unexpectedly')
            with urlopen(f'http://127.0.0.1:{port}/start.html', timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError('Installed handbook is unavailable')
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
    (output/'installer-smoke.json').write_text(json.dumps({'platform': sys.platform, 'installer_and_cpu_demo_passed': True,
                                                         'web_preview_passed': True, 'release_qualified': False}, indent=2)+'\n')
    print(f'Installer and CPU demo passed on {sys.platform}. Fixture does not qualify native workers.')


if __name__ == '__main__':
    main()
