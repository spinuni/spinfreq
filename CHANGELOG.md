# Changelog

## Unreleased — local research experiments

- Reusable NPY/mesh-matched OVF initial states in the CLI/Python runner; every
  job records and exports its actual starting texture and hash.
- `StudyConfig`, `run_study` and `spinfreq-study` for independent parameter grids
  and single-axis equilibrium continuation. Continuation stops on failure;
  resume verifies artifacts and numerical implementation and retains attempts.
- Aggregate parameter/pole CSVs, PNG/PDF spectra, field/damping examples and an
  independent analytical Gilbert frequency/linewidth/complex-response check.
- Local research guide and prioritized model-development roadmap. GitHub About
  metadata and an authenticated update command are prepared separately.

## Unreleased — product website and handbook

- Original SpinFreq navigation for Manual, Theory, API, Downloads, Validation
  and About, linked from the homepage and simulation workbench.
- Detailed installation/first-run manual, SI configuration and artifacts,
  equations and numerical conventions, Python/CLI/HTTP API contracts and
  evidence grouped by physical model.
- Local documentation and preset downloads work without a computation worker
  or internet access. `/docs` uses a self-contained reference compatible with
  the content security policy; `/openapi.json` remains available.
- Canonical Markdown renders to packaged HTML; CI checks consistency and
  exports a static product website. Source install and experimental platform
  status are explicit; no unpublished binary or stable release is advertised.

## 0.1.0rc2 — experimental native Windows computation

- Installed-wheel platform evidence collector and standalone verifier, with
  revision/source/procedure hashes, mandatory native JUnit cases, browser session
  binding, result-manifest verification and negative-case tests. CI now qualifies
  the exact wheel on Ubuntu and Windows and uploads reviewable evidence bundles.

- Explicit `--mode compute` on Windows uses Job Objects with gated worker
  startup, committed-memory/user-CPU limits and process-tree termination on
  cancellation, server death and normal parent completion.
- Runtime backends separate Linux process groups/rlimits from Windows APIs;
  storage ownership uses a native exclusive lease on each platform.
- Supervisor monitors both per-file and total disk limits on every platform.
- Native Windows lifecycle, resource-limit and descendant-process checks are
  added to CI. Local Linux verification does not qualify the Windows backend;
  Windows automatic startup remains preview-only until native evidence passes.

## 0.1.0rc1 — release candidate

- Hierarchical documentation and grouped analytical baseline, with updated links.
- Provisional SpinFreq logo and project landing page.
- Portable Windows/macOS configuration preview and validated JSON export; Linux/WSL2 simulation workers retain resource controls.
- Explicit auto/landing/compute modes and Ubuntu/Windows preview CI checks.

- Shared, versioned SI `JobConfig` and `run_job` API for Python, CLI and web.
- Strict configuration validation, equilibrium/eigen/response residual checks,
  numerical stability classification and a small-response guard. Failed jobs
  withhold spectral artifacts.
- Three reproducible presets, configuration/source hashes, CSV/NPZ/OVF exports,
  SHA-256 manifests and downloadable result archives.
- Optional local Linux web workbench with a bounded serial process queue,
  progress, cancellation, time/memory/disk controls and restart recovery.
- MIT license, citation metadata, contributor guide and explicit release gates.
- Retained FMR, DMI, two-field skyrmion and driven OOMMF validations, including
  1 nm external ringdowns, complex mode fields and timestep refinement.
- Reusable dense `ModalResponse` and exact linear raised-cosine startup response.

This candidate does not claim public hosted-service readiness, universal thickness
accuracy, scalable large-array eigenanalysis or nonlinear frequency-comb validation.
