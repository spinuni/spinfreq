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
| M6. Publish package release | Review candidate evidence; green hosted CI; reproducible release artifacts and tag; configure PyPI trusted publishing if PyPI delivery is wanted | Pending |
| M7. Public hosted application | Select host; authentication/TLS/access and retention policy; load/restart tests and quotas measured there; deployment/runbook and service smoke check | Pending; current launcher binds loopback only |

M1–M5 advance the first usable version. M6/M7 are publication milestones, not
claims implied by a GitHub push. No PyPI release, version tag or public web
deployment is created by the candidate checks.

## Candidate acceptance procedure

```bash
python -m pip install -e '.[test,web,web-test]' build
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

- Single z layer: general thickness/parameter qualification remains open.
- The 2 nm skyrmion preset reproduces the matched discrete OOMMF model; the
  independent 1 nm report and 1 to 0.8 nm study show why finer grids matter.
- Near-neutral modes lack rigorous certification; sign-uncertain jobs are rejected.
- Edited configurations are research inputs, not automatically validated presets.
- Full-strip historical DMI bands, scalable large-array modes, automatic branch
  tracking and nonlinear comb generation remain distinct future milestones.

The detailed [physics assessment](../science/VALIDATION_AND_RELEASE.md) remains the source
for P1–P8 evidence. Scope changes must update both this plan and user-facing claims.
