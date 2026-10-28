# SpinFreq 0.1.0rc2

First research release candidate for CPU frequency-domain micromagnetics of thin
films. This is a pre-release; retain exact configurations and source revisions.

- Periodic and confined single-layer models with exchange, interfacial DMI,
  perpendicular uniaxial anisotropy, Zeeman and film demagnetization fields.
- Relaxed equilibria, damped linear eigenmodes and weak-field complex response,
  with numerical residual, stability and small-signal checks.
- Spatial sources/probes, polarized transfer tensors, conservative pole groups,
  parameter studies, state continuation and cautious spatial mode tracking.
- Eight installed editable examples, CPU self-check and guided first simulation.
- Local web interface and offline handbook covering usage, theory, API and scope.
- NumPy, CSV, OVF, plots and checksummed archives with reproducible provenance.

The complete ZIP contains the package wheel, source archive, verified native
platform evidence and installation helpers. Extract it before installing. On
Windows use Install.cmd, then Run-Demo.cmd; Open-Web.cmd starts preview. On
Linux/macOS use `python3 install.py`, then `.venv/bin/spinfreq-demo --open`.
Python 3.11–3.13 (64-bit) and internet for dependencies are required.

Analytical tests and independent OOMMF comparisons qualify specific discrete
models and observables. Consult the included validation reports before applying
new geometries or materials. The coarse 2 nm skyrmion example needs refinement
for continuum frequencies. Mesh and solver convergence remain the researcher's
responsibility.

The solver assumes uniform magnetization through thickness and linear response.
It has no GPU backend, general multilayers, material masks, thermal noise or
current torques. Linear response does not reproduce nonlinear frequency combs.
Dense problems have resource limits. Native Windows browser computation remains
experimental opt-in; macOS supports browser preview rather than protected
computation. Direct CPU commands are separate from the browser queue.

MIT licensed. This draft does not publish a PyPI package or provide a standalone
native executable. Inspect the candidate evidence and attached checksums before
publishing or installing from a trusted project release.
