"""Assemble a reviewable candidate from passing CI and native platform evidence.

This does not create tags, GitHub Releases, PyPI uploads or change worker modes.
Run only with artifacts from a trusted CI run of the reviewed source revision.
"""
import argparse
from email.parser import BytesParser
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tomllib

from spinfreq.qualification import (EvidenceError, package_fingerprint, sha256,
                                    source_is_dirty, source_revision,
                                    verify_evidence, verify_wheel)


REQUIRED_JOBS = {'test', 'research-workflows', 'desktop-onboarding', 'fmr-reference',
                 'dmi-static-reference', 'dmi-temporal-reference', 'skyrmion-reference',
                 'fine-skyrmion-reference', 'driven-response-reference',
                 'platform-workers', 'application', 'distribution'}


def verify_sdist(path, source, version):
    """Read without extraction; verify package and shipped tutorial/test content."""
    with tarfile.open(path, 'r:gz') as archive:
        files = {}
        entries = archive.getmembers()
        if sum(e.size for e in entries) > 512*1024**2:
            raise EvidenceError('Source distribution exceeds candidate size bounds')
        for entry in entries:
            parts = PurePosixPath(entry.name)
            if parts.is_absolute() or '..' in parts.parts or '\\' in entry.name:
                raise EvidenceError('Unsafe source distribution path')
            if entry.isdir():
                continue
            if not entry.isfile() or not parts.parts or parts.parts[0] != f'spinfreq-{version}':
                raise EvidenceError('Unexpected source distribution root or entry type')
            name = PurePosixPath(*parts.parts[1:]).as_posix()
            if name in files:
                raise EvidenceError('Duplicate source distribution file')
            files[name] = archive.extractfile(entry).read()
    metadata = BytesParser().parsebytes(files.get('PKG-INFO', b''))
    if metadata['Name'] != 'spinfreq' or metadata['Version'] != version:
        raise EvidenceError('Source distribution name/version mismatch')
    # Exact source comparisons include all tracked-facing package code/assets,
    # tutorials, helper scripts and tests, with CRLF normalized like native evidence.
    required = ['README.md', 'LICENSE', 'pyproject.toml', 'CHANGELOG.md', 'CITATION.cff']
    for directory in ('spinfreq', 'docs', 'examples', 'windows', 'tests', 'scripts', 'benchmarks'):
        required.extend(p.relative_to(source).as_posix() for p in (source/directory).rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts
                        and p.suffix in ('.py', '.md', '.json', '.cmd', '.html', '.css', '.js', '.png', '.mx3'))
    for name in required:
        def digest(data):
            return sha256(data if Path(name).suffix == '.png' else data.replace(b'\r\n', b'\n'))
        if name not in files or digest(files[name]) != digest((source/name).read_bytes()):
            raise EvidenceError(f'Source distribution missing or changed: {name}')


def prepare_candidate(source, distributions, linux, windows, ci_results, output, *, expected_revision, expected_run_id):
    source, distributions, output = Path(source).resolve(), Path(distributions), Path(output)
    if source_revision(source) != expected_revision or source_is_dirty(source) is not False:
        raise EvidenceError('Candidate requires the expected revision and a clean source tree')
    if not isinstance(ci_results, dict) or not REQUIRED_JOBS <= ci_results.keys():
        raise EvidenceError('Required CI job results are missing')
    failed = sorted(name for name in REQUIRED_JOBS if not isinstance(ci_results[name], dict)
                    or ci_results[name].get('result') != 'success')
    if failed:
        raise EvidenceError('Required CI jobs did not succeed: '+', '.join(failed))
    version = tomllib.loads((source/'pyproject.toml').read_text())['project']['version']
    wheels, sdists = list(distributions.glob('*.whl')), list(distributions.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sdists) != 1:
        raise EvidenceError('Provide exactly one wheel and one source distribution')
    verify_wheel(wheels[0], package_fingerprint(source/'spinfreq'), version)
    verify_sdist(sdists[0], source, version)
    platforms = {}
    for platform, directory in [('linux', linux), ('win32', windows)]:
        platforms[platform] = verify_evidence(directory, source, platform,
                                              expected_revision=expected_revision, require_clean=True)
        if platforms[platform]['package_version'] != version:
            raise EvidenceError('Platform evidence version differs from candidate')
    if not platforms['win32']['native_windows_gate_passed']:
        raise EvidenceError('Native Windows qualification did not pass')
    for platform, directory in [('linux', Path(linux)), ('win32', Path(windows))]:
        provenance = json.loads((directory/'report.json').read_text()).get('ci', {})
        if (provenance.get('GITHUB_RUN_ID') != expected_run_id
                or provenance.get('GITHUB_SHA') != expected_revision
                or provenance.get('RUNNER_OS') != {'linux': 'Linux', 'win32': 'Windows'}[platform]):
            raise EvidenceError('Native evidence must come from the intended CI run and revision')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError('Use an empty candidate output directory')
    output.mkdir(parents=True, exist_ok=True)
    for path in (wheels[0], sdists[0]):
        shutil.copyfile(path, output/path.name)
    for name in ('install.py', 'Install.cmd', 'Run-Demo.cmd', 'Open-Web.cmd'):
        data = (source/'scripts/release_assets'/name).read_bytes()
        if name.endswith('.cmd'):
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        (output/name).write_bytes(data)
    evidence_reports = {}
    for platform, directory in [('linux', Path(linux)), ('win32', Path(windows))]:
        report = json.loads((directory/'report.json').read_text())
        evidence_reports[platform] = sha256((directory/'report.json').read_bytes())
        for name in ['report.json', *report['files']]:
            target = output/'evidence'/platform/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(directory/name, target)
    report = {'schema_version': 1, 'status': 'candidate_checks_passed_review_required',
              'version': version, 'revision': expected_revision, 'ci_run_id': expected_run_id, 'ci_results': ci_results,
              'platforms': platforms, 'evidence_report_sha256': evidence_reports,
              'publication_performed': False,
              'limits': ['Native Windows browser computation remains experimental opt-in.',
                         'Native macOS browser computation remains preview only.',
                         'Checksums ensure integrity; review trusted CI run provenance before release.']}
    (output/'candidate.json').write_text(json.dumps(report, indent=2)+'\n')
    (output/'INSTALL.md').write_text(f'''# SpinFreq {version} candidate

Source revision: `{expected_revision}`. Review `candidate.json`, native evidence,
and the originating GitHub Actions run before publication. No release was published.

Install 64-bit Python 3.11–3.13, then open a terminal in this folder:

On **Windows**, extract the complete candidate ZIP into a writable folder,
double-click **Install.cmd**, wait for the CPU check, then double-click
**Run-Demo.cmd**. **Open-Web.cmd** starts configuration preview on localhost.
No PowerShell activation or execution-policy change is needed.

On **Linux/macOS**, run `python3 install.py`. The same installer can also be
called as `python install.py` from Windows. It checks all recorded files,
creates a local `.venv`, installs this exact wheel and runs a CPU self-check.
Existing result folders are preserved. `installation.json` records success
only after that check. Reinstallation keeps the local environment and replaces
the package with the exact candidate wheel, even if its version is unchanged.

To check integrity without installing or accessing the network:

```text
python install.py --verify-only
```

For manual installation instead:

```text
python -m venv .venv
```

Windows PowerShell (no activation required):

```powershell
.\\.venv\\Scripts\\python.exe -m pip install "{wheels[0].name}[web]"
.\\.venv\\Scripts\\spinfreq-doctor.exe --check
.\\.venv\\Scripts\\spinfreq-demo.exe --open
.\\.venv\\Scripts\\spinfreq-examples.exe --list
```

Linux/macOS:

```bash
.venv/bin/python -m pip install "{wheels[0].name}[web]"
.venv/bin/spinfreq-doctor --check
.venv/bin/spinfreq-demo --open
.venv/bin/spinfreq-examples --list
```

Dependencies require internet for this installation. CPU simulations use local
resources; GPU execution is not implemented. The wheel is a Python package,
not a standalone Windows installer. The source archive includes manuals,
examples and Windows helper scripts. Check `checksums.json` for file integrity.
''')
    checksums = {p.relative_to(output).as_posix(): sha256(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'checksums.json').write_text(json.dumps(checksums, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--distributions', type=Path, required=True)
    parser.add_argument('--linux-evidence', type=Path, required=True)
    parser.add_argument('--windows-evidence', type=Path, required=True)
    parser.add_argument('--ci-results', type=Path, required=True, help='GitHub needs JSON from this workflow run')
    parser.add_argument('--expect-revision', required=True)
    parser.add_argument('--expect-run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare_candidate(args.source_root, args.distributions, args.linux_evidence,
                                   args.windows_evidence, json.loads(args.ci_results.read_text()),
                                   args.output, expected_revision=args.expect_revision, expected_run_id=args.expect_run_id)
    except (ValueError, OSError, tarfile.TarError) as error:
        parser.exit(1, f'Candidate not assembled: {error}\n')
    print(f"Candidate {report['version']} ready for review at {args.output}; no publication performed.")


if __name__ == '__main__':
    main()
