# Changelog

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
