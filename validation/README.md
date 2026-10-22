# Validation evidence

| Category | Report | What it establishes |
| --- | --- | --- |
| Analytical baseline | [Kittel, dispersion and susceptibility](analytical/README.md) | Foundational analytic checks and original periodic-grid study |
| FMR | [Baker standard](fmr_standard_problem/README.md) | Independent finite-film frequencies, linewidths and complex mode fields |
| DMI | [Cortés-Ortuño standard](dmi_standard_problem/README.md) | Static profiles, chirality and signed dispersion |
| Temporal DMI | [Independent OOMMF](dmi_temporal/README.md) | Complex Fourier ringdown and amplitude scaling |
| Noncollinear dynamics | [Two-field skyrmions](skyrmion_temporal/README.md) | Profiles, full spatial traces and complex modes; mesh study |
| Refined dynamics | [1 nm independent references](skyrmion_fine/README.md) | Two-field fine-grid agreement and joint mesh qualification |
| Driven susceptibility | [Multitone OOMMF](driven_response/README.md) | Complex amplitude/phase, turn-on, drive halving and temporal refinement |
| Implementation performance | [Modal reuse](response_reuse/README.md) | Accuracy and measured small-system reuse, not independent physics |
| Candidate application | [Release checks](release_candidate/README.md) | Example frequencies, measured resources and browser delivery |
| Local research workflow | [Parameter studies and continuation](research_workflows/README.md) | Analytical field/damping response, verified state reuse and archived OOMMF endpoint poles |
| Spatial spectroscopy | [Polarized drives and local/Fourier probes](spatial_spectroscopy/README.md) | Analytical finite-k/complex response, source/detector definitions, cancellation and weak-drive scaling |
| Mode analysis | [Spatial MAC and ambiguity](mode_tracking/README.md) | Synthetic rank reversal/degeneracy checks and a real skyrmion scan |
| Literature exploration | [Liu 2024](liu2024/README.md) | Single-skyrmion/array studies; nonlinear comb remains unvalidated |

Accepted data and settings are versioned. Intermediate arrays, exploratory
failures and downloaded solver installations remain in ignored `results/`.
Scientific reports describe their own scope; a passing matched discrete problem
does not imply a general thickness or continuum-accuracy guarantee. See the
[release plan](../docs/releases/RELEASE_PLAN.md) and [full assessment](../docs/science/VALIDATION_AND_RELEASE.md).
