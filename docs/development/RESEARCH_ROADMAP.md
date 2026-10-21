# Research development priorities

SpinFreq's first research scope is deterministic single-layer linear
micromagnetics. A useful comparison to MuMax3, OOMMF and Fidimag is the ability to
express an experiment, inspect its physics, rerun it and exchange data. We do
not copy their language or claim the same physical coverage. Python experiment
files, SI JSON, command-line execution, NumPy/CSV/OVF and independent reference
problems are the current foundation. Online interface development is secondary.

## R1 · Reproducible experiments — implemented baseline

Saved initial textures, strict input files, independent parameter grids,
single-axis magnetic-state continuation, preserved failure attempts, verified
resume and aggregate data/plots are implemented. Analytical FMR checks exercise
field/damping scans and complex response. This improves experimental workflow;
it does not widen the validated physical model.

The [workflow qualification](../../validation/research_workflows/README.md)
also compares a three-point confined-skyrmion continuation with archived
independent OOMMF endpoint poles, retaining the original coarse-mesh limits.

## R2 · Spectroscopy and mode analysis — next priority

Expose spatial excitation and observation profiles in reproducible jobs; the
low-level response already accepts spatial complex drives. Add complex
susceptibility tensors, drive visibility and phase-invariant spatial mode
overlaps. Branch tracking needs ambiguity reports at degeneracies and crossings,
not just nearest-frequency matching. Validate against analytic polarized FMR,
symmetry selection rules and independent temporal spatial recordings.

## R3 · Patterned devices and material regions

Add magnetic masks and cell-dependent materials with explicitly derived
exchange/DMI interface rules. Propagate masks through energy, fields,
demagnetization, tangent coordinates and import/export. A zero-Ms shortcut
through the current scalar-material code is not adequate. Validate isolated
strips, holes/notches, interface boundary conditions, energy derivatives and
independent finite-device spectra before claiming realistic device coverage.

## R4 · Large systems and robust convergence

Promote existing confined matrix-free response and targeted Bloch solvers into
the reproducible runner. Report actual Krylov residuals, preconditioning,
targeted-mode completeness and memory. Benchmark dense versus iterative results
on the same model and measure scaling. Add fixed-geometry mesh studies and
branch-aware mode comparisons; frequency rank alone fails at crossings.

## R5 · Driven spintronics

Derive STT/SOT terms, units, signs and their full tangent Jacobians. Under current,
energy minimization alone generally does not find the correct stationary state;
solve the torque-balance problem and analyze stability around it. Validate
macrospin limits and independent temporal thresholds before adding current-driven
oscillator or device claims. The existing field-driven solver cannot stand in
for electron transport, spin diffusion or current-induced torques.

## R6 · Physics beyond the current model

Thermal fluctuations, nonlinear mode coupling/combs, z-dependent modes and
multilayers each require new models and validation. Linear startup and multitone
superposition do not validate nonlinear mixing. Maintain a separate nonlinear
temporal workflow and qualify it against independent trajectories. Consider
3D/multilayer discretization only with explicit magnetostatic and interface tests.

For each stage: document equations and scope, validate derivatives and analytic
limits, compare independent temporal results, demonstrate convergence, and only
then present a device or frontier-physics example. A package release and a
research paper require different acceptance evidence.
