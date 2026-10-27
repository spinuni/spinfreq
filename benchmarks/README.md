# Scientific benchmark index

Run commands from the repository root; accepted settings, plots, native hashes
and exact reproduction commands live in the linked reports. External solver runs
and downloaded runtimes belong in ignored `results/`. Existing script locations
are retained to keep report commands and cross-script imports working.

| Purpose | Main scripts | Accepted evidence |
| --- | --- | --- |
| Analytic/operator checks | `validate.py`, `standard_checks.py` | [Physics assessment](../docs/science/VALIDATION_AND_RELEASE.md) |
| Finite-film FMR | `fmr_standard_problem.py` | [FMR standard](../validation/fmr_standard_problem/README.md) |
| DMI static/dispersion | `dmi_standard_problem.py` | [DMI standard](../validation/dmi_standard_problem/README.md) |
| Independent CPU OOMMF DMI | `dmi_temporal.py`, `setup_oommf_reference.py` | [DMI temporal](../validation/dmi_temporal/README.md) |
| Skyrmion profiles/modes/mesh | `skyrmion_temporal.py` | [Coarse dynamics and refinement](../validation/skyrmion_temporal/README.md), [fine-grid qualification](../validation/skyrmion_fine/README.md) |
| Complex forced response | `driven_response.py` | [Multitone response](../validation/driven_response/README.md) |
| Prepared dense response reuse | `response_reuse.py` | [Accuracy and measured CPU reuse](../validation/response_reuse/README.md) |
| Liu single-skyrmion/array research | `liu2024.py`, `liu2024_fig2.py`, `liu2024_dynamics.py`, `liu2024_conditions.py` | [Liu study](../validation/liu2024/README.md) |
| Temporal solver interchange | `export_mumax.py`, `analyze_mumax.py` | [Usage](../docs/guides/USAGE.md) |
| Local research studies | `research_studies.py`, `research_continuation.py` | [Analytical susceptibility and OOMMF continuation endpoints](../validation/research_workflows/README.md) |
| Spatial spectroscopy | `spatial_spectroscopy.py` | [Analytical polarization/finite-k response and source/probe checks](../validation/spatial_spectroscopy/README.md) |
| Mode analysis | `mode_tracking.py` | [Spatial-character tracking and ambiguity checks](../validation/mode_tracking/README.md) |
| Polarization tensors | `susceptibility_tensor.py` | [Uniform/finite-k analytical transfer](../validation/susceptibility/README.md) |
| Grouped poles | `pole_groups.py` | [Exact grouped reconstruction](../validation/pole_groups/README.md) |

Application release checks live separately in `scripts/validate_presets.py` and
`scripts/browser_smoke.py`; they do not replace independent physics validation.
