# Code, data and citation provenance

The original SpinFreq code and project documentation are MIT licensed, as chosen
by the repository owner. `CITATION.cff` identifies this software. Credit the papers
and reference software relevant to each scientific result as well.

An MIT license for this project does **not** relicense third-party reference
inputs, publications, solver source or executables. Their original authors,
license terms and citation requirements remain applicable. Upstream runtimes and
downloaded source trees stay in ignored `results/`; they are not part of the wheel.

| Evidence family | Source and reproducibility record |
| --- | --- |
| FMR standard | Baker et al.; author data URLs, pinned hashes, geometry and fit procedure in [report](../validation/fmr_standard_problem/README.md) |
| DMI standard | Cortés-Ortuño et al.; published reference data and solver comparisons in [report](../validation/dmi_standard_problem/README.md) |
| Independent DMI temporal | Executed CPU OOMMF references, source/executable and native-file hashes in [report](../validation/dmi_temporal/README.md) |
| Independent skyrmion temporal | Executed OOMMF profiles and spatial snapshots in [coarse](../validation/skyrmion_temporal/README.md) and [fine](../validation/skyrmion_fine/README.md) reports |
| Driven response | Executed OOMMF multitone runs, numerical controls and native hashes in [report](../validation/driven_response/README.md) |
| Liu comparison | Literature figures/settings and remaining disagreements in [report](../validation/liu2024/README.md) |

Native OOMMF archives contain the simulation inputs, outputs and provenance of
our executed reference runs, not an OOMMF installation. Inspect each family’s
`summary.json` and README before reuse. Published third-party data are attributed
and should be retrieved/reused under their upstream terms; project MIT metadata
does not assert additional rights over those data. The small wheel contains
the package and web assets; the sdist additionally includes scientific reports,
benchmark scripts, tests and archived reference results for reproducibility.
