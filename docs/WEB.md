# Local web application

Install and start on Linux:

```bash
python -m pip install -e '.[web]'
spinfreq-web --data-dir results/web --port 8000
```

Open **http://127.0.0.1:8000** in a browser. Select periodic FMR, a single-cell
prism or a confined skyrmion. Edit labelled nm/T/GHz/microtesla fields and click
**Run field configuration**. Advanced users can edit the full SI JSON and use
**Run JSON configuration**; that button submits exactly that JSON. Results show
equilibrium, lowest positive-frequency mode amplitude and absorbed power.
Download the full archive, response CSV, summary JSON or equilibrium OVF.
Refresh/reopen the page to select retained jobs. Cancel pending calculations;
delete finished jobs to reclaim capacity.

The JSON configuration, physical calculation and exports are the same as
`spinfreq --config ...` and `spinfreq.run_job(...)`. For example:

```bash
spinfreq --config examples/confined-skyrmion.json --output results/skyrmion-job
```

An error displays the failed numerical/resource check. Failed jobs do not expose
spectra. For diagnosis, summary/configuration files remain downloadable when
written; private worker logs are under `<data-dir>/<job-id>/worker.log` on disk.
The status and progress endpoints are polled; progress reports stages rather
than an invented percentage. An uncertain or unstable equilibrium is rejected.
The stable label means the implemented numerical checks pass, not a proof of
continuum stability or of finding the ground state.

## Local operating limits

| Resource | Default limit |
| --- | --- |
| Active workers | 1, one BLAS/OpenMP thread |
| Running + queued jobs | 4 total |
| Retained job records | 16; delete terminal jobs to free slots |
| Mesh / frequency samples | 400 cells / 201 frequencies |
| Worker wall / CPU time | 120 s / 60 s CPU, hard CPU kill at 61 s |
| Worker virtual address space | 2 GiB |
| Individual worker file | 32 MiB |
| Per-job disk | 96 MiB, checked by supervisor every 0.1 s |
| Configuration HTTP body | 16 KiB, including streamed requests |

Disk is checked periodically, so a short-lived overshoot can occur; the fixed
artifact set and per-file limits provide an additional bound. The user controls
only configuration values, not paths, code, subprocess commands or filenames.
Completed-job deletion is explicit. Data are local and not uploaded elsewhere.
Only one server can own a data directory. Keep the default single server process;
multiple Uvicorn workers are not supported. A server crash kills its worker on
Linux; incomplete status records become `interrupted` at restart.

## Verify and troubleshoot

```bash
python -m pip install -e '.[test,web,web-test]'
python -m pytest -q tests/test_jobs.py tests/test_web.py
python -m playwright install chromium
python scripts/browser_smoke.py --url http://127.0.0.1:8000
```

The browser script also accepts `--browser /usr/bin/chromium` when a system
browser is available. Use a new output/data directory for independent checks.
If startup reports another supervisor, stop that server or choose another data
directory. If a job fails, inspect its summary/log before changing physical
constants. A smaller drive can resolve the linear-amplitude guard; a finer mesh
addresses spatial accuracy and increases computational cost.

The launcher binds **127.0.0.1**. This is a local single-user research workbench,
with same-origin/host checks but no user authentication. A public hosted service
requires the separate [M7 deployment milestone](RELEASE_PLAN.md), including access
control and host-specific resource measurements. The current worker is a resource
control for trusted local use, not an operating-system sandbox for hostile code.
