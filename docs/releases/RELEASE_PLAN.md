# First-version release plan

The target is **v0.1.0: a bounded thin-film research package and local web
application**, prepared as `0.1.0rc2`. It computes discrete equilibria, complete
dense linear eigenmodes and weak-field frequency response. This scope is useful
without requiring a large-array solver, 3D thickness modes or a nonlinear comb.
Those remain separate development tracks. Liu is one comparison among FMR,
DMI, noncollinear dynamics and driven response.

## Milestones

| Milestone | Acceptance evidence | State |
| --- | --- | --- |
| M1. Repository and provenance | Documentation/benchmark/validation indexes; stable script paths; examples; MIT license chosen by owner; citation and changelog | Implemented |
| M2. Shared reproducible execution | Versioned strict SI configuration; Python/CLI equivalence; source/config hashes; numerical failures withhold spectra; CSV/NPZ/OVF/ZIP | Implemented and tested |
| M3. Bounded example scope | Three examples checked against analytic FMR or independent OOMMF poles; record actual CPU/RSS/time; reject oversized web requests | Implemented; measured report under `validation/release_candidate/` |
| M4. Local web lifecycle | Separate worker; bounded queue/storage/resources; progress/cancel/delete; process isolation; restart recovery; browser-to-download check | Linux qualified locally; Windows experimental opt-in, native CI review pending |
| M5. Distribution and CI | Wheel/sdist with code, static assets, examples and tests; installed CLI/web outside source; Python 3.11–3.13 jobs, archived reference regressions | Local checks plus CI configuration; hosted results must be observed |
| M5a. Product website and handbook | Original homepage; offline manual, theory, Python/HTTP API, downloads and validation pages; preset downloads; deterministic rendering; static export and browser checks | Implemented and locally tested; public hosting pending |
| M6. Publish package release | Review candidate evidence; green hosted CI; reproducible release artifacts and tag; configure PyPI trusted publishing if PyPI delivery is wanted | Automated candidate assembly implemented; hosted review and publication pending |
| M7. Public hosted application | Select host; authentication/TLS/access and retention policy; load/restart tests and quotas measured there; deployment/runbook and service smoke check | Pending; current launcher binds loopback only |

M1–M5 advance the first usable version. M6/M7 are publication milestones, not
claims implied by a GitHub push. No PyPI release, version tag or public web
deployment is created by the candidate checks.

The wheel includes all eight editable example templates. `spinfreq-examples`
creates portable job/study projects with validation, original-template hashes
and local instructions; a source checkout is no longer needed for the gallery.

Candidate downloads also include a stdlib bootstrap installer and Windows
shortcuts, with exact-wheel replacement, checksum checks, CPU self-test and an
installation record. Native desktop CI exercises the bootstrap and CPU demo;
this does not promote Windows browser computation or imply a standalone binary.

The [candidate assembly guide](CANDIDATE.md) explains the final CI gate and
downloadable review bundle. It requires successful prerequisite jobs, clean
matching source/distributions and independently verified Linux/Windows evidence.

## Candidate acceptance procedure

```bash
python -m pip install -e '.[test,web,web-test,docs]' build
python scripts/build_site.py --check --export results/site-check
python scripts/site_smoke.py results/site-check
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q
python scripts/validate_presets.py --output results/preset-check
spinfreq-web --data-dir results/web-check --port 8000
# In another shell, with Chromium installed:
python scripts/browser_smoke.py --output results/browser-check
python -m build
```

The preset check launches the installed CLI from a temporary working directory.
The browser check drives real Chromium through the UI, waits for the subprocess,
checks three rendered images and the downloaded result archive, and checks mobile
horizontal overflow. CI repeats both checks. The distribution job installs a
wheel in an independent environment and runs tests from the unpacked sdist.

Accept supported examples only if static/eigen/forced-response checks pass,
mode frequencies meet independent targets, predicted perturbations remain below
0.05, runtime stays under 120 s and measured process RSS under 1 GiB on the test
host. The Linux worker has a 2 GiB **virtual address-space** cap; RSS and address space
are different quantities. These measurements are a starting budget, not a claim
about production-host capacity. Saved API presets match `examples/*.json`.

## Platform follow-up

Windows/macOS automatic startup provides the landing and configuration preview.
Experimental native Windows workers are now implemented with Job Objects, gated
startup, committed-memory/user-CPU limits, native owner locking and process-tree
cleanup. They require `--mode compute` and 64-bit Windows Python. The native CI
suite must demonstrate memory/CPU enforcement, cancellation including descendants,
server-crash recovery, isolation and numerical output before enabling Windows
computation automatically. Linux evidence is not a substitute. macOS compute
remains unimplemented. See [Windows qualification](../development/WINDOWS.md).

## Scientific scope that remains open

Local research experiment files, equilibrium continuation, restart textures and
verified study resume are implemented; see the [research guide](../guides/RESEARCH.md).
The [research roadmap](../development/RESEARCH_ROADMAP.md) prioritizes spatial
spectroscopy, mode analysis, material regions, matrix-free execution and
current-driven physics. These are distinct from public web deployment.

- Single z layer: general thickness/parameter qualification remains open.
- The 2 nm skyrmion preset reproduces the matched discrete OOMMF model; the
  independent 1 nm report and 1 to 0.8 nm study show why finer grids matter.
- Near-neutral modes lack rigorous certification; sign-uncertain jobs are rejected.
- Edited configurations are research inputs, not automatically validated presets.
- Full-strip historical DMI bands, scalable large-array modes, subspace branch
  tracking and nonlinear comb generation remain distinct future milestones.
  Spatial MAC branch tracking and conservative pole grouping are implemented.

The detailed [physics assessment](../science/VALIDATION_AND_RELEASE.md) remains the source
for P1–P8 evidence. Scope changes must update both this plan and user-facing claims.

## Evidence handoff

[Platform qualification](PLATFORM_EVIDENCE.md) now collects installed-wheel tests,
real browser results, JUnit and checksums tied to a source revision on both hosts.
The standalone checker supports offline review of the downloaded CI artifact;
GitHub API access is not required for that review. Windows promotion still
requires actual trusted native evidence and a separate default-mode change.
