# SpinFreq handbook and product website

Original user-facing documentation, rendered into the installed application:

1. [User manual](manual.md): installation, first simulation, configuration, outputs and troubleshooting.
2. [Theory](theory.md): energy, discretization, LLG, tangent-space modes, response and limits.
3. [API](api.md): shared jobs, numerical Python objects, CLI and HTTP contracts.
4. [Downloads](downloads.md): actual distribution status, platform instructions and presets.
5. [Validation](validation.md): evidence by physical family and unsupported cases.
6. [About](about.md): purpose, independence, citation and contribution.

Links between handbook pages use their rendered `.html` destinations. Detailed
research documents stay in their existing locations and are linked to GitHub.

## Maintain and export

```bash
python -m pip install -e '.[docs]'
python scripts/build_site.py
python scripts/build_site.py --check
python scripts/build_site.py --export results/site
python scripts/site_smoke.py results/site  # requires .[web-test] and Chromium
```

Commit source Markdown and generated HTML together. Rendering uses a pinned
Markdown version and reads the package version from `pyproject.toml`. The wheel
ships generated pages; there is no runtime Markdown or internet dependency.
CI verifies that pages match their sources and exports a static-site artifact.

The static export works under a subdirectory or offline, includes validated
preset JSON and local assets, and clearly identifies itself as documentation.
Its simulator link targets a separately launched localhost service. Hosting
the static export does not deploy a calculation backend. Public hosting has
not been enabled by this change.

MuMax3 inspired the choice to make installation, examples, theory and API easy
to find. All handbook text, site layout and branding are SpinFreq's own. No
MuMax3 assets or source were copied. The official site was inaccessible from
this workspace during this work, so this is not a current-page design audit.
