# About SpinFreq

SpinFreq is a CPU research package for frequency-domain micromagnetics in thin films. Its central workflow is **equilibrium → modes → driven response → reproducible evidence**. The Python package, CLI and local browser application share a calculation engine.

## An independent scientific tool

Scientific software such as MuMax3 demonstrates the value of clear installation instructions, examples, theory, API documentation and citations. SpinFreq adopts those organizational principles with original documentation, visual identity and workflows. It does not reuse MuMax3's website, logo or scripting language, and is not affiliated with the MuMax3 authors.

SpinFreq focuses on direct linear frequency response. Temporal solvers remain essential independent references and are better suited to many nonlinear problems. Comparisons must match energy conventions, boundary conditions, discretization, damping, excitation and observables; no general speed or accuracy superiority is claimed.

## Product priorities

- One configuration across Python, CLI and browser.
- Visible equations, units and solver assumptions beside the workflow.
- Mode poles, complex response and numerical diagnostics in exportable results.
- Validation organized by physical question and independent evidence.
- Documentation available locally without internet access.

## Cite and contribute

The code is MIT licensed. See [CITATION.cff](https://github.com/spinuni/spinfreq/blob/main/CITATION.cff) for current software citation metadata; cite an exact version or source commit. Cite reference papers and external data independently when using their benchmarks. Provisional logo artwork is original generated branding, not a calculated magnetic configuration.

Report issues with the full configuration, package/source version, platform, failure summary and a minimal reproducer. See [contributing](https://github.com/spinuni/spinfreq/blob/main/CONTRIBUTING.md), [data provenance](https://github.com/spinuni/spinfreq/blob/main/docs/science/DATA_PROVENANCE.md), and [release milestones](https://github.com/spinuni/spinfreq/blob/main/docs/releases/RELEASE_PLAN.md).
