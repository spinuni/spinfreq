# API reference

The CPU Python library, CLI and local HTTP workbench share the same `JobConfig` and `run_job` workflow. Local parameter studies add `StudyConfig` and `run_study`. Version **0.1.0rc2** is a pre-release: record the exact revision and `schema_version`, and review changes before upgrading. Advanced Python APIs can change before 1.0.

## Reproducible Python jobs

```python
from spinfreq import JobConfig, run_job

config = JobConfig.load("prism-fmr.json")
summary = run_job(config, "results/prism-api")
print(summary["status"], summary["stability"])
```

Download [prism-fmr.json](downloads/prism-fmr.json) first. The output directory must be empty. `JobConfig.from_dict(data)` validates a Python dictionary; `config.to_dict()` exports it. Defaults follow schema version 1. Invalid configuration raises `ValueError`; an occupied directory raises `FileExistsError`; numerical rejection raises `spinfreq.jobs.NumericalFailure` and saves a failure summary when the numerical stage has started. These direct calls do not run inside the protected web worker.

## Core numerical objects

| Public object or method | Contract |
| --- | --- |
| `Material(Ms, A, D, K, alpha, gamma)` | SI material parameters; keyword arguments recommended |
| `Film(nx, ny, dx, dy, thickness, material, field_T)` | Periodic film; `dy=None` uses dx |
| `ConfinedFilm(..., dmi_boundary="mumax")` | Finite rectangle; choose boundary explicitly for comparisons |
| `film.relax(initial, maxiter=2000, tolerance_T=1e-5)` | Returns `Relaxation`: `m`, `converged`, `torque_T`, `energy_J`, `iterations`, `message` |
| `refine_equilibrium(film, m, ...)` | Refine a nearly stationary texture; inspect convergence before spectra |
| `film.modes(m, equilibrium_tolerance_T=1e-4)` | Returns `Spectrum` containing eigenvalues and spatial `modes`; `frequencies_Hz` includes signed branches |
| `film.response(m, frequencies_Hz, drive_T=..., equilibrium_tolerance_T=...)` | Complex field array `(nf, ny, nx, 3)` |
| `film.absorbed_power(frequencies_Hz, response, drive_T)` | Total watts at each frequency |
| `ModalResponse(film, equilibrium, equilibrium_tolerance_T=1e-6)` | Snapshot dense eigenbasis; rebuild after changing material, geometry, field or equilibrium |
| `prepared.response(frequencies_Hz, drive_T=...)` | Reuses the basis and checks true residuals |
| `BlochChain.bloch_modes(m, k_rad_m, count=12, target_Hz=15e9, tolerance=1e-9)` | Targeted chain modes; wavevector is angular, in rad/m |

Arrays of unit magnetization have shape `(ny, nx, 3)`, with x/y/z in the last axis. Low-level spectral calls enforce equilibrium checks, but do not provide all `run_job` stability and amplitude gates. See [advanced examples](https://github.com/spinuni/spinfreq/blob/main/docs/guides/USAGE.md) for matrix-free response, OVF, nonlinear dynamics and Bloch workflows.

## Minimal low-level example

```python
import numpy as np
from spinfreq import Film, Material, ModalResponse

film = Film(nx=2, ny=2, dx=4e-9, thickness=1e-9,
            material=Material(D=0), field_T=(0, 0, 0.1))
m = np.zeros(film.shape)
m[..., 2] = 1
prepared = ModalResponse(film, m)
f = np.linspace(1e9, 60e9, 21)
drive = (1e-6, 0, 0)
delta_m = prepared.response(f, drive)
power_W = film.absorbed_power(f, delta_m, drive)
```

## Local research API

`SpatialProfile(kind="uniform", ...)` defines a sampled source/probe envelope. `Probe(name, profile=SpatialProfile())` defines a named observation. `JobConfig` accepts optional `drive_imag_T`, `drive_profile` and `probes`, with full JSON roundtrip. The default probe is the whole-film mean. Spatial profiles are shared across the three drive-polarization components; probe outputs are dimensionless complex vectors with conjugated L1 normalization. See the [spectroscopy API examples](https://github.com/spinuni/spinfreq/blob/main/docs/guides/SPECTROSCOPY.md).

`run_job(config, output, progress=None, *, initial_m=None)` accepts a real unit-vector starting texture with shape `(ny, nx, 3)`. `load_initial_state(path, config)` reads NPY or mesh-matched OVF2. The supplied texture overrides the seed, then undergoes normal relaxation and spectral checks. All jobs save `initial.npy` with a hash in their summary.

`StudyConfig(base, axes, continuation=False)` expands numeric dotted parameter paths into validated cases. `run_study(config, output, *, resume=False)` returns a case/attempt ledger and writes aggregate CSVs and plots. Independent studies use Cartesian products; continuation supports exactly one field/material axis, reuses the preceding equilibrium and stops on failure. Resume checks configuration, numerical implementation and completed artifact hashes. It preserves failed attempts and retries in new directories. See the [research guide](https://github.com/spinuni/spinfreq/blob/main/docs/guides/RESEARCH.md).

## CLI

```bash
spinfreq --help
spinfreq --preset periodic-fmr --write-config film.json
spinfreq --config film.json --output results/film
spinfreq-web --help
spinfreq-web --mode landing --port 8000
spinfreq-study --config examples/studies/fmr-field-sweep.json --output results/field-sweep
```

`--preset` and `--config` select the shared reproducible runner. Legacy geometry flags remain available for exploratory periodic-film runs; their overwrite behavior differs. Prefer the shared configuration workflow for recorded studies.

## Local HTTP API

Base URL: `http://127.0.0.1:8000`. JSON requests require `Content-Type: application/json`. This is a local, single-user service; it does not provide public authentication or multi-user isolation. Cross-origin requests and untrusted hosts are rejected. Preview mode offers docs, presets and input validation without starting workers.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/capabilities` | Platform, simulation availability and experimental status |
| GET | `/api/presets` | Complete preset configurations |
| POST | `/api/config/validate` | Normalize a schema-valid configuration; does not guarantee web resource bounds or physical validity |
| GET | `/api/jobs` | Retained records; empty in preview |
| POST | `/api/jobs` | Apply web bounds and enqueue; 202 with an `id` |
| GET | `/api/jobs/{id}` | Job status and available progress stage |
| POST | `/api/jobs/{id}/cancel` | Cancel queued/running work |
| DELETE | `/api/jobs/{id}` | Delete an inactive job and its data; 204 |
| GET | `/api/jobs/{id}/artifacts/{name}` | Allowlisted result download; spectra require success |
| GET | `/openapi.json` | Route-level OpenAPI description; configuration fields are documented in the manual, not inferred by this schema |

`/docs` opens this self-contained reference; it does not depend on a CDN. The standard OpenAPI JSON remains available to client generators.

```python
import json
from urllib.request import Request, urlopen

base = "http://127.0.0.1:8000"
with urlopen(base + "/api/presets") as response:
    config = json.load(response)["prism-fmr"]
request = Request(base + "/api/jobs", data=json.dumps(config).encode(),
                  headers={"Content-Type": "application/json"}, method="POST")
with urlopen(request) as response:
    job = json.load(response)
print(job["id"])  # Poll GET /api/jobs/{id}; download only after success.
```

Statuses: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`. A 202 response means accepted, not completed. A server restart marks incomplete work interrupted. Download `summary.json` for diagnostics and `results.zip` for a successful bundle.

Errors include 413 (input over 16 KiB), 415 (wrong content type), 422 (invalid input/resource bounds), 429 (queue/storage capacity), 503 (computation disabled), 404 (unknown job or unavailable artifact) and 409 (deletion conflict). Clients should inspect `detail` and avoid blindly retrying numerical failures. The API is local and currently has no job-expiration scheduler; delete completed records when finished.
