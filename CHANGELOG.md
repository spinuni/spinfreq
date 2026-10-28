# Changelog

## Unreleased — draft release handoff

- Manual GitHub draft-release workflow verifies a successful main-branch CI run,
  matching source/distributions, candidate checksums and native platform evidence.
- Prepares an installable ZIP and attaches the exact wheel/source archive,
  version-matched notes, installation guide and checksums. Read-only verification
  is separated from narrowly scoped tag/draft creation; existing tags are refused.
- Versioned release notes document scope and platform limits. No automatic
  publication, PyPI upload or worker-default promotion is performed.

## Unreleased — candidate installation

- Candidate bundles include a stdlib integrity checker/installer and Windows
  Install/Demo/Web-preview shortcuts. Setup uses a local environment and the
  exact wheel, including repeated candidates with the same version string.
- Installation records are written only after the CPU self-check; results are
  preserved on reinstall. Read-only verification needs no package dependencies.
- Native desktop CI installs the actual wheel and runs a CPU demo in explicitly
  marked installer-only fixtures, separate from platform qualification.

## Unreleased — installed editable example gallery

- All eight FMR/skyrmion/spectroscopy/study templates are bundled in the wheel;
  `spinfreq-examples` lists them or creates an editable project without a checkout.
- Generated guides, byte-stable starter manifests and portable `run.py` runners
  support validation, edited inputs, relocated projects and fresh result folders.
- Source/gallery synchronization checks and JSON resource fingerprint coverage;
  installed example execution added to desktop and distribution CI.

## Unreleased — first-release assembly and grouped poles

- Conservative same-sign complex-pole groups, summed tensor residues and exact
  all-pole reconstruction; coincident and nearby-distinct poles are distinguished.
  Grouped CSV/JSON/NPZ exports and configurable reporting tolerances.
- A final CI candidate gate requires scientific, distribution, onboarding,
  application and native platform checks. It verifies clean source, wheel/sdist
  contents and Linux/Windows evidence before exporting a review bundle with
  checksums and Windows/Linux/macOS installation commands. No publication or
  platform-default changes are performed.

## Unreleased — polarization tensors and modal coupling

- Optional `spinfreq-susceptibility` analysis of verified completed CPU jobs,
  with x/y/z B-based transfer tensors, signed non-Hermitian modal residues,
  original-drive reconstruction, CSV/NPZ and PNG/PDF comparisons.
- Uniform/finite-k analytical Gilbert checks, phase/scale and degenerate-group
  invariance tests, source/probe coupling and provenance checks.
- Guided Windows/Linux/macOS usage and explicit normalization, small-signal
  and modal-interference limits. Normal demo/job outputs remain unchanged.

## Unreleased — guided first run and mode matching

- `spinfreq-doctor --check` and `spinfreq-demo` provide an installation self-check,
  a guided CPU example, safe new result folders and optional image opening.
- Windows source-install/demo/browser helper scripts and native Windows/macOS/Linux
  onboarding CI. Native worker qualification remains separate and pending.
- A single canonical Start-here tutorial is rendered for the website; README,
  landing and downloads guide new users from installation to their first spectrum.
- Phase/scale-invariant spatial MAC matching and `spinfreq-track` analysis with
  global assignments, near-frequency/alternative-match flags, persistent lineage
  uncertainty, verified inputs and chain breaks at failed cases.

## Unreleased — spatial spectroscopy

- Uniform, rectangular, Gaussian and complex plane-wave excitation profiles in
  reproducible jobs, with real/imaginary polarization components in tesla.
- Named spatial/Fourier probes with explicit conjugated L1-weighted observation,
  exact drive-field export, complex observation NPZ/CSV and manifest coverage.
- Legacy uniform-real JSON meanings and configuration hashes are preserved.
  Added source/detector and wavevector examples, analytical polarized/finite-k
  validation, Fourier cancellation and local weak-drive scaling checks.

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
