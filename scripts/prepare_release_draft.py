"""Verify a trusted main-branch CI candidate and prepare draft-release assets.

Reads GitHub metadata/tag state; never creates tags or releases. The separate
workflow publish job creates a draft only after this verifier succeeds.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tomllib
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from spinfreq.qualification import (EvidenceError, package_fingerprint, source_is_dirty,
                                    source_revision, verify_evidence, verify_wheel)


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


assembly = _module('draft_assembly', Path(__file__).with_name('prepare_release_candidate.py'))
bootstrap = _module('draft_bootstrap', Path(__file__).parent/'release_assets/install.py')


def validate_run(run, repository, revision, run_id):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise EvidenceError('Invalid repository')
    if not re.fullmatch(r'[0-9a-f]{40}', revision) or not re.fullmatch(r'[1-9][0-9]*', run_id):
        raise EvidenceError('Require a full lowercase commit SHA and numeric CI run ID')
    if (not isinstance(run, dict) or str(run.get('id')) != run_id
            or run.get('repository', {}).get('full_name') != repository
            or run.get('head_repository', {}).get('full_name') != repository
            or run.get('head_sha') != revision or run.get('head_branch') != 'main'
            or run.get('event') != 'push' or run.get('status') != 'completed'
            or run.get('conclusion') != 'success'
            or run.get('path') not in ('.github/workflows/ci.yml', '.github/workflows/ci.yml@refs/heads/main')):
        raise EvidenceError('Require a successful Package checks push run on this repository main branch at the intended revision')


def github_get(path, token):
    request = Request('https://api.github.com/'+path,
                      headers={'Authorization': 'Bearer '+token, 'Accept': 'application/vnd.github+json',
                               'X-GitHub-Api-Version': '2022-11-28'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def tag_exists(repository, tag, token):
    try:
        github_get(f'repos/{repository}/git/ref/tags/{tag}', token)
        return True
    except HTTPError as error:
        if error.code == 404:
            return False
        raise


def prepare_draft(source, candidate, output, run, *, repository, revision, run_id, check_tag):
    validate_run(run, repository, revision, run_id)
    source, candidate, output = Path(source).resolve(), Path(candidate).resolve(), Path(output)
    if source_revision(source) != revision or source_is_dirty(source) is not False:
        raise EvidenceError('Require a clean candidate source checkout at the intended revision')
    verified = bootstrap.verify_bundle(candidate)
    report = json.loads((candidate/'candidate.json').read_text())
    version = tomllib.loads((source/'pyproject.toml').read_text())['project']['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?', version):
        raise EvidenceError('Unsupported release version; use major.minor.patch with an optional a/b/rc suffix')
    if (report.get('schema_version') != 1 or report.get('status') != 'candidate_checks_passed_review_required'
            or report.get('version') != version or verified['version'] != version
            or report.get('revision') != revision or report.get('ci_run_id') != run_id
            or report.get('publication_performed') is not False):
        raise EvidenceError('Candidate provenance/version differs from the intended CI source')
    jobs = report.get('ci_results', {})
    if not isinstance(jobs, dict) or not assembly.REQUIRED_JOBS <= jobs.keys() or any(
            not isinstance(jobs[name], dict) or jobs[name].get('result') != 'success' for name in assembly.REQUIRED_JOBS):
        raise EvidenceError('Candidate prerequisite job conclusions are incomplete or unsuccessful')
    checksums = json.loads((candidate/'checksums.json').read_text())
    actual = {p.relative_to(candidate).as_posix() for p in candidate.rglob('*') if p.is_file()}
    if actual != set(checksums).union({'checksums.json'}):
        raise EvidenceError('Use the original candidate artifact; unrecorded files or installation results are present')
    wheel = candidate/f'spinfreq-{version}-py3-none-any.whl'
    sdist = candidate/f'spinfreq-{version}.tar.gz'
    if verified['wheel'] != wheel.name or not sdist.is_file() or sdist.name not in checksums:
        raise EvidenceError('Candidate distributions have unexpected names or are missing')
    verify_wheel(wheel, package_fingerprint(source/'spinfreq'), version)
    assembly.verify_sdist(sdist, source, version)
    for platform in ('linux', 'win32'):
        directory = candidate/'evidence'/platform
        result = verify_evidence(directory, source, platform, expected_revision=revision, require_clean=True)
        provenance = json.loads((directory/'report.json').read_text())
        if (result['package_version'] != version or (platform == 'win32' and not result['native_windows_gate_passed'])
                or provenance.get('ci', {}).get('GITHUB_RUN_ID') != run_id
                or provenance.get('ci', {}).get('GITHUB_SHA') != revision
                or report.get('evidence_report_sha256', {}).get(platform) != bootstrap.digest(directory/'report.json')):
            raise EvidenceError('Native evidence disagrees with the intended candidate run')
    tag = 'v'+version
    notes = (source/'docs/releases/NOTES.md').read_text(encoding='utf-8')
    if (notes.splitlines() or [''])[0] != '# SpinFreq '+version:
        raise EvidenceError('Release notes do not match the candidate version')
    if check_tag(tag):
        raise EvidenceError('Version tag already exists; existing releases/tags are never replaced')
    output.mkdir(parents=True, exist_ok=False)
    for path in (wheel, sdist, candidate/'INSTALL.md'):
        shutil.copyfile(path, output/path.name)
    run_url = f'https://github.com/{repository}/actions/runs/{run_id}'
    notes += f'\nSource revision: `{revision}`. [Verified CI run]({run_url}).\n'
    (output/'release-notes.md').write_bytes(notes.encode('utf-8'))
    archive_name = f'SpinFreq-{tag}.zip'
    with zipfile.ZipFile(output/archive_name, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(actual):
            archive.write(candidate/name, name)
    uploads = [wheel.name, sdist.name, archive_name, 'INSTALL.md', 'release-notes.md']
    hashes = {name: bootstrap.digest(output/name) for name in uploads}
    (output/'SHA256SUMS.txt').write_bytes(''.join(f'{digest}  {name}\n' for name, digest in hashes.items()).encode())
    plan = {'schema_version': 1, 'tag': tag, 'revision': revision, 'run_id': run_id,
            'repository': repository, 'prerelease': bool(re.search(r'(?:a|b|rc)\d+$', version)),
            'draft': True, 'publication_performed': False, 'assets_sha256': hashes}
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--run-metadata', type=Path, required=True)
    parser.add_argument('--fetch-run', action='store_true', help='Read and validate GitHub run metadata, then stop')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    token = os.environ.get('GH_TOKEN')
    if not token: parser.error('GH_TOKEN with repository contents/actions read access is required')
    try:
        if args.fetch_run:
            # Reject malformed input before using it in an API path.
            if not re.fullmatch(r'[1-9][0-9]*', args.run_id) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
                raise EvidenceError('Invalid repository or run ID')
            run = github_get(f'repos/{args.repository}/actions/runs/{args.run_id}', token)
            validate_run(run, args.repository, args.revision, args.run_id)
            args.run_metadata.write_text(json.dumps(run, indent=2)+'\n')
            print('Trusted main-branch CI run verified')
            return
        if not all((args.source_root, args.candidate, args.output)):
            parser.error('--source-root, --candidate and --output are required to prepare assets')
        plan = prepare_draft(args.source_root, args.candidate, args.output, json.loads(args.run_metadata.read_text()),
                             repository=args.repository, revision=args.revision, run_id=args.run_id,
                             check_tag=lambda tag: tag_exists(args.repository, tag, token))
    except (ValueError, OSError, zipfile.BadZipFile, tarfile.TarError) as error:
        parser.exit(1, f'Draft not prepared: {error}\n')
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as stream:
            stream.write(f"tag={plan['tag']}\nrevision={plan['revision']}\nprerelease={str(plan['prerelease']).lower()}\n")
    print(f"Prepared {plan['tag']} draft assets at {args.output}; no GitHub release was created by this command.")


if __name__ == '__main__':
    main()
