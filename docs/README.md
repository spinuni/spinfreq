# Documentation map

The application now ships an offline handbook: launch `spinfreq-web` and use
Manual, Theory, API, Downloads and Validation in the navigation. Its canonical
sources are in [handbook/](handbook/README.md). This is the primary user-facing
reading path; the levels below retain detailed research and development references.

Start with the [first-result tutorial](getting-started/README.md), also available
as **Start here** in the installed website. Then choose an example or topic below.
Scientific reports and development notes are kept
separate from installation and daily use.

## Level 1 · Start

- [Quick start](getting-started/README.md): Windows, Linux/WSL2 and macOS.
- [Windows helper scripts](../windows/README.md): install, run a CPU demo and start the optional browser interface.
- [Example configurations](../examples/README.md): three small reproducible inputs.

## Level 2 · Use

- [Web interface](guides/WEB.md): landing, configuration preview and Linux workers.
- [Python and CLI guide](guides/USAGE.md): units, APIs, outputs and research workflows.
- [Local research studies](guides/RESEARCH.md): parameter grids, magnetic-state continuation, restart textures and verified resume.
- [Spatial spectroscopy](guides/SPECTROSCOPY.md): complex polarized drives, local source/detector profiles and Fourier probes.
- [Mode tracking](guides/MODE_TRACKING.md): spatial shape matching across a sweep, with explicit uncertainty flags.

## Level 3 · Understand and validate

- [Physics and solvers](reference/PHYSICS.md).
- [Validation index](../validation/README.md): accepted data, plots and provenance.
- [Scientific assessment](science/VALIDATION_AND_RELEASE.md).
- [Data attribution](science/DATA_PROVENANCE.md).
- [Benchmark index](../benchmarks/README.md).

## Level 4 · Develop and publish

- [Architecture](development/ARCHITECTURE.md), [Windows backend](development/WINDOWS.md) and [contributing](../CONTRIBUTING.md).
- [Research roadmap](development/RESEARCH_ROADMAP.md): spectroscopy, patterned devices, scalable solvers and current-driven physics.
- [Release plan](releases/RELEASE_PLAN.md), [platform evidence](releases/PLATFORM_EVIDENCE.md) and [changelog](../CHANGELOG.md).
- [Branding](branding/README.md): provisional SpinFreq logo.

This hierarchy changes navigation and file locations; numerical reference data
and accepted scientific results are retained. `validation/analytical/` now groups
the original analytical baseline that previously occupied the validation root.
