# Grouped-pole reconstruction

[Report](report.json) · [PNG comparison](group-reconstruction.png) ·
[PDF comparison](group-reconstruction.pdf)

```bash
python benchmarks/pole_groups.py --check --output results/pole-groups
python -m pytest tests/test_pole_groups.py -q
```

The benchmark uses a periodic 4 × 4 square film with 8 nm cells, 1 nm thickness,
perpendicular bias and a one-cell source/detector. Its 32 signed poles are
partitioned into 12 groups at the documented default tolerance. Summing the
exact group contributions reproduces the full complex tensor with **2.18e-16**
relative error over 401 frequencies from 0 to 180 GHz. The report records full
geometry/material settings, groups, tolerances, runtime versions and source
hashes. Acceptance requires reconstruction error below 1e-9, shifted-system
residual below 1e-7 and at least one multi-pole group.

Tests additionally exercise complete-link diameter limits, separation of
frequency signs and damping rates, permutation invariance away from ambiguous
ties, basis-rotation invariance of coincident-group residues, and nearby poles
whose cancellation makes a mean-pole approximation wrong. The grouping
algorithm is a deterministic reporting convention, not proof of degeneracy.

This verifies reconstruction of the **same discrete linear operator**. It does
not add independent temporal, continuum or nonlinear physics validation. The
analytical uniform/finite-k tensor comparison remains in
[the susceptibility evidence](../susceptibility/README.md).
