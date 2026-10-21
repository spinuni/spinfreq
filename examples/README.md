# Runnable SI configurations

| File | Purpose | Scope |
| --- | --- | --- |
| `periodic-fmr.json` | Uniform periodic film, weak x drive | Uniform mode checked analytically; no finite edges |
| `prism-fmr.json` | Elliptical single-cell prism response | Analytic damped Gilbert susceptibility, not spatially resolved film modes |
| `confined-skyrmion.json` | 40 × 40 × 1 nm square, 2 nm cells, bond DMI | Matched independent OOMMF model; coarse grid requires refinement for continuum values |

```bash
spinfreq --config examples/prism-fmr.json --output results/prism
spinfreq --preset confined-skyrmion --write-config my-skyrmion.json
# Edit SI quantities in my-skyrmion.json, then:
spinfreq --config my-skyrmion.json --output results/my-skyrmion
```

Outputs must use an empty directory. Configurations have `schema_version: 1`;
unknown properties, duplicate JSON keys, nonfinite values and unsupported model
settings fail explicitly. `model` is `periodic` or `confined`; the latter selects
`bond` or `mumax` DMI edges. The web queue applies stricter computation bounds than
the core dense solvers. Edited inputs are research configurations; check their
equilibrium, stability, amplitude and mesh convergence.
