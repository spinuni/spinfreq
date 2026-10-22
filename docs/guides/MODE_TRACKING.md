# Follow a mode through a parameter sweep

A mode is a spatial pattern of magnetic motion. Sorting frequencies at every
field gives a frequency rank; the same mode can change rank when two
frequencies cross. SpinFreq can compare saved spatial patterns between
neighboring scan steps and report both the assignment and its uncertainty.

## Try it

First run the three-step skyrmion example, then analyze its lowest three modes.
In Windows PowerShell, from an installed source checkout:

```powershell
.\.venv\Scripts\spinfreq-study.exe --config examples/studies/skyrmion-field-path.json --output results/skyrmion-path
.\.venv\Scripts\spinfreq-track.exe --study results/skyrmion-path --output results/skyrmion-tracking --max-modes 3
```

On Linux/macOS, use:

```bash
.venv/bin/spinfreq-study --config examples/studies/skyrmion-field-path.json --output results/skyrmion-path
.venv/bin/spinfreq-track --study results/skyrmion-path --output results/skyrmion-tracking --max-modes 3
```

Open `results/skyrmion-tracking/branches.png` and `branches.csv`. Teal points
have a clear lineage under the selected thresholds. Orange points have a
provisional lineage: inspect the spatial modes, parameter spacing and flags
before attaching a physical identity. The scan uses the coarse matched 2 nm
model; it does not establish continuum convergence.

## What is compared?

The modal assurance criterion (MAC) measures spatial-shape similarity:

```text
MAC(a,b) = |sum(conj(a) b)|² / (sum(|a|²) sum(|b|²)).
```

It is invariant to arbitrary overall mode phase and scale. A value near one
means similar shapes; it is not a probability. SpinFreq uses a global assignment
that maximizes total MAC, rather than independently picking each nearest
frequency or best partner. Both row and column competitors are checked.

These are Euclidean overlaps of the saved three-component spatial modes on a
fixed mesh. Damped modes can be nonnormal; these overlaps are not biorthogonal
excitation weights or an energy normalization. Changing the magnetic state can
also change mode character. The analysis does not assign CW/CCW/breathing labels
or align arbitrary mode phases for subsequent vector averaging.

## When is a branch provisional?

Defaults mark a local assignment ambiguous when its MAC is below 0.5, when its
advantage over a row/column alternative is below 0.1, or when either endpoint
has nearby frequencies within `1 MHz + 1e-4 * max(f1,f2)`. Frequency proximity
is a conservative heuristic, not a numerical error bar or linewidth test.

At an exact degeneracy, multiple bases can describe the same mode subspace.
Individual identities need additional symmetry/subspace information. If a
lineage encounters ambiguity, its later rows stay provisional even if local
matches improve. Coarse parameter steps and the selected mode-count window can
also create ambiguous assignments. Refine the scan and increase the mode window
before interpreting apparent branch changes.

## Output files

| File | Read it for |
| --- | --- |
| `branches.csv` | Case/parameter, branch ID, frequency rank, frequency, decay, MAC, alternative margins and uncertainty flags |
| `branches.png`, `branches.pdf` | Frequencies along scan order, with clear/provisional lineages distinguished |
| `tracking.json` | Thresholds, skipped cases, input hashes, original implementation and analysis source hash |

Branch IDs start at zero and describe the algorithm's assignment, not a
universal physical label. The plot uses scan-step order, preserving paths that
reverse direction. The CSV contains the actual parameter values. An ambiguous
analysis still completes successfully; its flags are part of the result.

## Input integrity and limitations

Use a one-axis study with fixed model, mesh, cell dimensions and DMI boundaries.
Every recorded artifact of each successful case is hash-checked, including the
saved archive, before use. Historical compatible jobs can be analyzed without
rerunning them; their original numerical implementation remains in the report.

Failed or unfinished cases break the tracking chain. The next successful case
starts a new segment with new branch IDs. The analysis never matches across a
failure or changes the original modes. A study lock prevents a simultaneous
study writer; after a hard kill, verify that no writer remains before removing
the stale lock, as for study resume.

Output must be a new/empty analysis folder; `study/tracking` is allowed, while
the study root and case-artifact folders are protected. Matching defaults to
the lowest 12 positive-frequency modes, at most 128. It reads one complete saved
compressed mode array at a time and retains adjacent selected modes; large dense
NPZ files can still require substantial memory. Modes leaving the selected
window can lose a reliable assignment. The report does not claim completeness
or unique identities at degeneracy.

## Python API

```python
from spinfreq import match_modes, track_study

# old_modes/new_modes have a leading mode axis and identical spatial shape.
# pairs = match_modes(old_modes, new_modes, min_overlap=0.7, min_margin=0.15)
report = track_study("results/skyrmion-path", "results/custom-tracking",
                     max_modes=3, min_overlap=0.7, min_margin=0.15)
```

`match_modes` also supports unequal mode counts, returning only assigned pairs.
`track_study` gives unmatched current modes new branch IDs. See
[tracking qualification](../../validation/mode_tracking/README.md) for phase,
scale, crossing, ambiguity and real-skyrmion checks.
