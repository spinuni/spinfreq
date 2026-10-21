# Validation and supported scope

Validation belongs to specific physical models, meshes and observables. Passing one skyrmion example does not qualify every material or geometry. SpinFreq retains input files, reference attribution, plots and numerical comparisons in its [evidence index](https://github.com/spinuni/spinfreq/tree/main/validation).

## Evidence families

| Family | What is tested | Evidence |
| --- | --- | --- |
| Analytical | Uniform FMR, susceptibility, exchange dispersion, damping and operators | [Analytical baseline](https://github.com/spinuni/spinfreq/tree/main/validation/analytical) |
| Research studies | Field/damping grids, state continuation and archived OOMMF endpoint poles | [Local workflow qualification](https://github.com/spinuni/spinfreq/tree/main/validation/research_workflows) |
| Baker FMR standard | Independent OOMMF poles, linewidths and spatial mode overlaps | [FMR standard](https://github.com/spinuni/spinfreq/tree/main/validation/fmr_standard_problem) |
| Cortés-Ortuño DMI | Static profiles, signed-k dispersion and independent OOMMF ringdowns | [DMI standard](https://github.com/spinuni/spinfreq/tree/main/validation/dmi_standard_problem), [temporal comparison](https://github.com/spinuni/spinfreq/tree/main/validation/dmi_temporal) |
| Confined skyrmions | Two bias fields, complex spatial modes and mesh refinement | [Fine-grid comparison](https://github.com/spinuni/spinfreq/tree/main/validation/skyrmion_fine) |
| Driven response | Multiple tones near resonances, phase, startup and amplitude scaling | [Driven comparison](https://github.com/spinuni/spinfreq/tree/main/validation/driven_response) |
| Liu 2024 | Single-skyrmion modes and exploratory collective-excitation conditions | [Paper comparison and open disagreements](https://github.com/spinuni/spinfreq/tree/main/validation/liu2024) |

Each report states the tested configuration, tolerances, reference source and remaining differences. Liu is one comparison family; matching its isolated-skyrmion modes does not establish nonlinear comb reproduction or agreement for every collective band.

## What the first candidate supports

Deterministic, single-layer micromagnetics with exchange, interfacial DMI, perpendicular anisotropy, static fields and demagnetization. Reproducible small dense jobs expose stable linear eigenmodes and weak harmonic response. Advanced Python workflows add Bloch bands, iterative response and nonlinear integration with their own assumptions.

## Remaining boundaries

General thickness-dependent modes, multilayers, temperature and current torques are outside the implemented models. Nonlinear frequency-comb validation remains open. Parameter and thickness envelopes are not generally qualified. Native Windows worker qualification requires actual Windows evidence; Linux tests do not establish it. Hosted authentication and multi-user operation remain deployment work.

For a new result, perform mesh and solver convergence, check stationarity and stability, compare drive/observation symmetry, and retain phase conventions and complete provenance. See [Theory](theory.html), the [manual](manual.html#diagnose-and-refine), and the [full assessment](https://github.com/spinuni/spinfreq/blob/main/docs/science/VALIDATION_AND_RELEASE.md).
