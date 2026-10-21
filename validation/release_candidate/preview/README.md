# Portable landing and configuration preview

The web server now starts in preview mode on native Windows/macOS; Linux/WSL2
can run the protected worker or explicitly choose `--mode landing`. Linux-only
`fcntl` is imported inside supervisor construction, not while importing the web
application. Preview never constructs that supervisor or creates its job folder.

Local validation on Linux includes 105 passing tests, including seven portable
cases, plus real Chromium tests for both compute and preview flows. The preview
browser test opens the [landing page](landing.png), navigates to the workbench,
changes sampling, exports JSON and checks that the downloaded config contains
those exact changes. Simulation buttons remain disabled and no jobs are created.
There are no JavaScript errors or horizontal overflow at 390 px. See
[desktop](desktop.png), [mobile](mobile.png) and [machine-readable results](summary.json).

The Ubuntu/Windows CI job runs the portable tests on native hosts. This workspace
runs Linux; mocked platform selection and Linux browser evidence do not establish
that the native Windows CI job has passed. Native Windows simulation workers are
still unavailable and remain a separate development milestone.

```bash
spinfreq-web --mode landing --port 8001
# Another shell:
python scripts/browser_smoke.py --url http://127.0.0.1:8001 --landing
```
