"""Verify and install the adjacent SpinFreq candidate using only stdlib initially.

Checksums detect corruption; obtain the bundle from the trusted project workflow.
This installer never qualifies native workers or changes their default mode.
"""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import venv
import zipfile


ASSETS = {'install.py', 'Install.cmd', 'Run-Demo.cmd', 'Open-Web.cmd'}


def _json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key in {path.name}: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_bundle(directory):
    """Check every recorded file and select the sole root wheel, without writes."""
    directory = Path(directory).resolve()
    checksums = _json(directory/'checksums.json')
    if not isinstance(checksums, dict) or not ASSETS.union({'candidate.json', 'INSTALL.md'}) <= checksums.keys():
        raise ValueError('Incomplete candidate checksums; download and extract the complete bundle')
    for name, expected in checksums.items():
        if not isinstance(name, str) or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('Malformed candidate checksum entry')
        parts = PurePosixPath(name)
        path = (directory/name).resolve()
        if (parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name
                or not path.is_relative_to(directory) or name == 'checksums.json'):
            raise ValueError('Unsafe candidate artifact path')
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'Candidate file missing or damaged: {name}')
    wheel_names = [name for name in checksums if name.endswith('.whl') and len(PurePosixPath(name).parts) == 1]
    if len(wheel_names) != 1 or {p.name for p in directory.glob('*.whl')} != set(wheel_names):
        raise ValueError('Candidate must contain exactly one recorded root wheel')
    candidate = _json(directory/'candidate.json')
    if not isinstance(candidate, dict) or not isinstance(candidate.get('version'), str):
        raise ValueError('Candidate version metadata is missing')
    wheel = directory/wheel_names[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = [name for name in names if name.endswith('.dist-info/METADATA')]
        if len(metadata) != 1 or len(names) != len(set(names)):
            raise ValueError('Ambiguous wheel metadata or duplicate files')
        info = BytesParser().parsebytes(archive.read(metadata[0]))
        if info['Name'] != 'spinfreq' or info['Version'] != candidate['version']:
            raise ValueError('Wheel name/version differs from candidate metadata')
    return {'version': candidate['version'], 'revision': candidate.get('revision'),
            'wheel': wheel.name, 'wheel_sha256': checksums[wheel.name], 'verified_files': len(checksums)}


def _venv_python(directory):
    return directory/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def install(directory):
    directory = Path(directory).resolve()
    report = verify_bundle(directory)
    print(f"Verified {report['verified_files']} candidate files for SpinFreq {report['version']}.", flush=True)
    if not (3, 11) <= sys.version_info[:2] <= (3, 13) or sys.maxsize <= 2**32:
        raise ValueError('Install with 64-bit Python 3.11, 3.12 or 3.13')
    environment = directory/'.venv'
    if environment.is_symlink():
        raise ValueError('Use a local .venv directory, not a symbolic link')
    if not environment.exists():
        print('Creating a local Python environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    python = _venv_python(environment)
    if not python.is_file():
        raise ValueError('Existing .venv is incomplete; use a fresh candidate folder')
    probe = subprocess.check_output([str(python), '-I', '-c',
        'import json,sys; print(json.dumps({"prefix":sys.prefix,"version":list(sys.version_info[:2]),"bits":64 if sys.maxsize>2**32 else 32}))'],
        cwd=directory, text=True)
    runtime = json.loads(probe)
    if (Path(runtime['prefix']).resolve() != environment.resolve() or runtime['bits'] != 64
            or not [3, 11] <= runtime['version'] <= [3, 13]):
        raise ValueError('Existing .venv is not a supported local 64-bit Python environment')
    # A failed reinstall must not leave an older success record claiming success.
    marker = directory/'installation.json'
    if marker.exists():
        marker.unlink()
    wheel = directory/report['wheel']
    print('Installing dependencies and the exact candidate wheel (internet required)...', flush=True)
    # Version equality alone must not skip changed candidate bytes.
    subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--no-deps', '--force-reinstall', str(wheel)],
                   cwd=directory, check=True)
    # Resolve dependencies after replacing the metadata, including same-version
    # development candidates whose dependency requirements have changed.
    subprocess.run([str(python), '-I', '-m', 'pip', 'install', str(wheel)+'[web]'], cwd=directory, check=True)
    print('Checking the installed CPU solver...', flush=True)
    subprocess.run([str(python), '-I', '-c', 'from spinfreq.onboarding import doctor_main; doctor_main()', '--check'],
                   cwd=directory, check=True)
    report.update(status='installed_and_cpu_check_passed', python=runtime, browser_worker_promotion=False)
    marker.write_bytes((json.dumps(report, indent=2)+'\n').encode('utf-8'))
    print('Ready. On Windows double-click Run-Demo.cmd for a CPU simulation or Open-Web.cmd for preview.', flush=True)
    print(f'Installation record: {marker}', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description='Verify and install this SpinFreq candidate in its local .venv')
    parser.add_argument('--verify-only', action='store_true', help='Check file integrity; do not create environments or install')
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    try:
        if args.verify_only:
            report = verify_bundle(directory)
            print(f"Verified {report['verified_files']} files: SpinFreq {report['version']}. Nothing installed.")
        else:
            install(directory)
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Installation stopped: {error}\nNo successful installation is recorded until the CPU check passes.\n')


if __name__ == '__main__':
    main()
