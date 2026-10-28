# Assemble the first release candidate

The package is currently **0.1.0rc2**. A push is not a package release. The
`Package checks` workflow now finishes with **Assemble candidate for review**,
which requires all twelve prerequisite jobs to succeed, including the Python
matrix, scientific references, desktop onboarding, distribution tests,
application checks and both native worker platforms. A failing or skipped
prerequisite prevents assembly.

## Download and inspect

Open [GitHub Actions → Package checks](https://github.com/spinuni/spinfreq/actions/workflows/ci.yml),
select the run for the intended commit, and inspect its job conclusions. When
the final assembly passes, download **release-candidate-review** from Artifacts.
Artifact availability and retention depend on GitHub and repository access.
This is a candidate download, not a published stable installer or PyPI release.

The bundle contains one wheel, one source archive, **INSTALL.md** with Windows
and Linux/macOS commands, **candidate.json**, **checksums.json**, and the
original Linux/Windows evidence files. It also contains **install.py** and
Windows **Install.cmd**, **Run-Demo.cmd** and **Open-Web.cmd** shortcuts.
The assembler verifies the distribution
contents against the clean reviewed source revision and independently verifies
both evidence bundles with the existing platform checker. Source archives must
include the current code, tutorials, examples, Windows helpers, scripts and tests.
Missing or stale content blocks assembly.

## Install the candidate download

Extract the complete artifact into a writable folder before installing. Install
64-bit Python 3.11–3.13. On Windows, double-click **Install.cmd**, wait for the
CPU self-check, then double-click **Run-Demo.cmd**. **Open-Web.cmd** starts the
local configuration preview. These helpers use a local `.venv`; they do not
change PowerShell execution policy or Windows browser computation defaults.

On Linux/macOS, run `python3 install.py` in the extracted folder. The same
installer is available as `python install.py` on Windows. It verifies all
recorded files before creating an environment or installing the exact wheel,
then installs dependencies and checks the CPU solver. Dependency installation
needs internet. `python install.py --verify-only` checks integrity without
installing or accessing the network.

Successful installation writes `installation.json` with the wheel hash and
Python details. Reinstallation preserves results and replaces the package even
when a development candidate has the same version string. A failed installation
or CPU check does not write a new success record. The wheel still requires
Python; this is not a standalone executable application.

The desktop CI matrix exercises the installer and a real CPU demo on each
native host using an installer-only test bundle. Such fixtures are explicitly
marked and do not qualify a release or replace native worker evidence.

Review the source revision, originating trusted workflow, native evidence and
checksums. A hash is not an authenticity signature. Synthetic unit-test parser
fixtures are not platform qualification. The assembly job itself has only
`contents: read` permissions and does not create tags, GitHub Releases or PyPI
uploads. It does not promote experimental Windows browser computation.

## Reproduce assembly locally

Download `distributions`, `platform-qualification-linux` and
`platform-qualification-win32` from the **same** intended workflow run. Use the
exact clean checkout, install its Python dependencies, and retain that run's
GitHub `needs` job-results object as `results/ci-results.json`. The workflow
captures it automatically; do not invent successful results for missing jobs.

```bash
python scripts/prepare_release_candidate.py --distributions results/distributions --linux-evidence results/linux-evidence --windows-evidence results/windows-evidence --ci-results results/ci-results.json --expect-revision FULL_COMMIT_SHA --expect-run-id GITHUB_RUN_ID --output results/release-candidate
```

The same command works in Windows PowerShell using the environment's Python.
Use an empty output directory. Assembly stops before producing a candidate if
required checks fail. For the individual evidence procedure, see
[platform qualification](PLATFORM_EVIDENCE.md).

## Remaining publication steps

### Stage a GitHub draft

Once the intended `Package checks` push run on `main` is successful and contains
`release-candidate-review`, open
[Actions → Prepare draft release](https://github.com/spinuni/spinfreq/actions/workflows/release-draft.yml).
Choose **Run workflow** on `main`, enter its numeric **run_id** and full
40-character **revision** SHA, then run it. No local GitHub API setup is needed.

The workflow checks the original CI run, matching clean source, candidate
checksums, both native evidence bundles, distribution contents and release
notes. Pull-request, fork, failed and mismatched runs are refused. It downloads
the original candidate rather than rebuilding a replacement. The notes in
`docs/releases/NOTES.md` must name the tested package version.

Only the final job has `contents: write`: it creates the version tag at the
verified commit and a **draft GitHub release**. The draft includes the complete
installable ZIP, wheel, source archive, installation guide, notes and SHA-256
checksums. Alpha/beta/rc versions are marked as prereleases. Existing tags are
never replaced. Nothing is automatically published to GitHub Releases or PyPI.

Review the resulting draft and its originating CI evidence, then use GitHub's
**Publish release** control when ready. If creation/upload fails after the tag
or draft is created, inspect that state manually; reruns do not overwrite it.
Repository policy must permit the workflow's explicit contents-write permission.

### Publish a stable package

Observe the trusted hosted CI results and review the candidate. Resolve failures
before changing the version to stable `0.1.0`; that version change needs a new
candidate built and tested from its own revision. Then publish the reviewed
artifacts with release notes and a version tag. PyPI distribution additionally
needs an owner-configured publishing identity. These publication steps remain
pending; local Linux checks do not establish native Windows success.
