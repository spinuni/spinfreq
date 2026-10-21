# Collect and verify installed-package platform evidence

The first release needs actual native execution evidence. Linux checks do not
qualify Windows. These tools collect the required installed-wheel, lifecycle and
browser evidence in a reviewable bundle without requiring access to GitHub's API.
They do not publish a package or change Windows automatic startup.

## 1. Build and install the wheel

Run in a clean checkout of the exact revision to qualify:

```bash
python -m pip install '.[test,web,web-test]' build
python -m build --wheel
python -m pip install --force-reinstall --no-deps dist/spinfreq-0.1.0rc2-py3-none-any.whl
```

Install the wheel from `dist/`, with its extras. If a wheel was already installed,
use `--force-reinstall --no-deps` for the exact file you just built. The collector
refuses editable/checkout imports and refuses an installed package whose files
are different from the checkout. Chromium is needed for the browser check:

```bash
python -m playwright install chromium
```

On Windows use 64-bit Python. Linux CI uses Playwright's `--with-deps` option to
install the browser's system libraries. An installed system Chromium also works.

## 2. Collect on the native host

Windows / PowerShell:

```powershell
python scripts/qualify_platform.py --wheel dist --expect-platform win32 --output results/windows-evidence --require-clean
```

Linux:

```bash
python scripts/qualify_platform.py --wheel dist --expect-platform linux --output results/linux-evidence --require-clean
```

`--wheel` accepts an exact wheel path or a directory containing exactly one wheel.
Use an empty output directory. Omit `--require-clean` only for development checks;
a dirty-source report cannot satisfy release verification with that flag.

The collector first exercises the installed `spinfreq`, `spinfreq-web` and
`spinfreq-verify-evidence` launchers with `--help`. It then runs selected
numerical/lifecycle tests from a temporary working
directory, using importlib loading so the checkout cannot shadow the installed
package. It then starts that installed web server, submits a real Chromium job,
checks the three images and downloads the result archive. A unique session binds
the collector, server, browser and worker result, rejecting a wrong server on the
chosen loopback port before submitting a job. The server is stopped afterward.

The bundle includes `report.json`, the exact `package.whl`, `tests.xml`, phase
logs, browser JSON, screenshots and `browser/results.zip`. Failed attempts retain
their available logs and return a failing exit code. `verification.json` is written
only after successful independent checks.

## 3. Verify against the reviewed source

After downloading a trusted Windows CI artifact or a native Windows run:

```bash
spinfreq-verify-evidence results/windows-evidence --source-root . --expect-platform win32 --require-clean
```

Use `--expect-revision <full-commit-sha>` to pin the intended revision explicitly;
the checkout must also be at that revision. The equivalent module invocation is
`python -m spinfreq.qualification ...`. A Git checkout is required for revision
review, not just an unpacked source archive.

Verification checks source/procedure fingerprints, wheel contents/version,
artifact checksums, required JUnit cases, phase exit status, server platform,
worker runtime, session binding, numerical diagnostics, configuration and the
nested result manifest. Missing or skipped native tests reject the Windows gate.
A valid Linux bundle reports its Linux checks passed and **cannot** close Windows.

Hashes check consistency and corruption; they are not signatures or proof against
fabricated reports. Review the trusted runner, CI run/revision and logs before
accepting evidence. No tool automatically edits platform support defaults.

## CI and the remaining gate

The `platform-workers` matrix builds and installs its exact wheel on Ubuntu and
Windows, collects the bundle and verifies it against `${{ github.sha }}`. Artifacts
are named `platform-qualification-linux` and `platform-qualification-win32`.
Other scientific-reference and Python-version jobs remain separate required checks.

The GitHub Actions API is currently unavailable in this workspace. Until actual
Windows evidence has passed and been reviewed, `--mode compute` on Windows remains
experimental and default startup remains preview. Publication and public hosting
retain their separate [release milestones](RELEASE_PLAN.md).
