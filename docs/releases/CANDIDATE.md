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
original Linux/Windows evidence files. The assembler verifies the distribution
contents against the clean reviewed source revision and independently verifies
both evidence bundles with the existing platform checker. Source archives must
include the current code, tutorials, examples, Windows helpers, scripts and tests.
Missing or stale content blocks assembly.

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

Observe the trusted hosted CI results and review the candidate. Resolve failures
before changing the version to stable `0.1.0`; that version change needs a new
candidate built and tested from its own revision. Then publish the reviewed
artifacts with release notes and a version tag. PyPI distribution additionally
needs an owner-configured publishing identity. These publication steps remain
pending; local Linux checks do not establish native Windows success.
