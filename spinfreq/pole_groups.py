"""Conservative groups of nearby complex poles; no merged-pole approximation."""
from numbers import Real

import numpy as np


def group_poles(eigenvalues_per_s, residues, *, atol_Hz=1e6, rtol=1e-4):
    """Group same-sign poles by full complex separation (lambda / 2 pi).

    Each pair in a group must satisfy atol + rtol*max(abs(pole)). This avoids
    transitive chains merging widely separated poles. Ordering is deterministic
    by imaginary then real part. Greedy complete-link groups are a reporting
    convention, not a unique physical partition. Residues' first axis is mode.
    Summed residues are invariant under basis changes only at coincident poles;
    nearby distinct poles MUST keep their individual denominators.
    """
    values = np.asarray(eigenvalues_per_s, complex)
    residues = np.asarray(residues, complex)
    if values.ndim != 1 or not len(values) or not np.all(np.isfinite(values)):
        raise ValueError("Require nonempty finite complex eigenvalues")
    if residues.ndim < 1 or len(residues) != len(values) or not np.all(np.isfinite(residues)):
        raise ValueError("Require finite residues with one first-axis entry per pole")
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Real)
           or not np.isfinite(v) or v < 0 for v in (atol_Hz, rtol)):
        raise ValueError("Grouping tolerances must be finite nonnegative real numbers")
    poles = values/(2*np.pi)
    groups = []
    for n in np.lexsort((values.real, values.imag)):
        for members in groups:
            other = poles[members]
            same_sign = np.sign(values[n].imag) == np.sign(values[members].imag)
            close = abs(poles[n]-other) <= atol_Hz+rtol*np.maximum(abs(poles[n]), abs(other))
            if np.all(same_sign & close):
                members.append(int(n))
                break
        else:
            groups.append([int(n)])
    labels = np.empty(len(values), dtype=int)
    records = []
    for g, members in enumerate(groups):
        labels[members] = g
        selected = poles[members]
        diameter = float(np.max(abs(selected[:, None]-selected)))
        roundoff_scale = 64*np.finfo(float).eps*max(float(np.max(abs(selected))), 1.)
        records.append({"group": g, "members": members, "count": len(members),
                        "kind": "single" if len(members) == 1 else
                        ("numerically_coincident" if diameter <= roundoff_scale else "nearby_distinct"),
                        "complex_diameter_Hz": diameter,
                        "signed_frequency_min_Hz": float(selected.imag.min()),
                        "signed_frequency_max_Hz": float(selected.imag.max()),
                        "growth_min_per_s": float(values[members].real.min()),
                        "growth_max_per_s": float(values[members].real.max())})
    return {"mode_group": labels, "groups": records,
            "summed_residues": np.array([residues[members].sum(axis=0) for members in groups]),
            "atol_Hz": float(atol_Hz), "rtol": float(rtol)}


def grouped_response(frequencies_Hz, eigenvalues_per_s, residues, grouping):
    """Yield (group, response) using every original pole, bounding temporary RAM.

    Output shape per group is (nf, *residue.shape[1:]). A near-degenerate group
    is evaluated exactly; its summed residue is never put over a mean pole.
    """
    frequencies = np.atleast_1d(np.asarray(frequencies_Hz, float))
    values, residues = np.asarray(eigenvalues_per_s, complex), np.asarray(residues, complex)
    if frequencies.ndim != 1 or not len(frequencies) or not np.all(np.isfinite(frequencies)) or np.any(frequencies < 0):
        raise ValueError("Require finite nonnegative frequencies")
    members = [n for record in grouping['groups'] for n in record['members']]
    if sorted(members) != list(range(len(values))) or len(residues) != len(values):
        raise ValueError("Groups must partition every supplied mode exactly once")
    for record in grouping['groups']:
        indices = record['members']
        denominator = 2j*np.pi*frequencies[:, None]-values[indices]
        if np.any(denominator == 0):
            raise RuntimeError("Singular pole in grouped response")
        result = np.tensordot(1/denominator, residues[indices], axes=(1, 0))
        if not np.all(np.isfinite(result)):
            raise RuntimeError("Grouped response exceeded finite numerical range")
        yield record['group'], result
