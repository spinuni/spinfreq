"""Mode-character crossing checks and a verified real-skyrmion study analysis."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from spinfreq import match_modes, track_study
from spinfreq.jobs import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True, help="Completed three-step skyrmion-field-path study")
    parser.add_argument("--output", type=Path, default=Path("results/mode-tracking"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    physical = track_study(args.study, args.output, max_modes=3)
    with (args.output/"branches.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    scores = [float(r["overlap"]) for r in rows if r["overlap"]]
    min_mac = min(scores)
    # Two independent oscillators: spatial eigenvectors are fixed while their
    # positive frequencies exchange rank. The sample grid omits exact crossing.
    parameter = np.array([-1., -.5, .5, 1.])
    character = np.array([10+2*parameter, 10-2*parameter]).T
    sorted_frequency = np.sort(character, axis=1)
    tracked = [character[0].copy()]
    previous = np.eye(2, dtype=complex)
    assignment_ambiguous = False
    for i in range(1, len(parameter)):
        order = np.argsort(character[i])
        current = np.eye(2)[order]*np.array([np.exp(.71j*i), -3j])[:, None]
        matched = match_modes(previous, current)
        assignment_ambiguous |= bool(matched.ambiguous.any())
        tracked.append(sorted_frequency[i][matched.current_indices])
        previous = current[matched.current_indices]
    tracked = np.array(tracked)
    crossing_error = float(np.max(np.abs(tracked-character)))
    rotation = np.array([[1, 1], [1, -1]])/np.sqrt(2)
    degenerate = match_modes(np.eye(2), rotation)
    report = {"physical_study": physical, "minimum_skyrmion_step_MAC": min_mac,
              "synthetic_crossing_max_frequency_error_GHz": crossing_error,
              "synthetic_clear_crossing_flagged": assignment_ambiguous,
              "degenerate_rotation_ambiguous_pair_count": int(degenerate.ambiguous.sum()),
              "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "Synthetic assignment behavior plus spatial continuity of an existing coarse skyrmion model; no unique identity at degeneracy"}
    report["passed"] = bool(physical["row_count"] == 9 and physical["provisional_lineage_rows"] == 0
                            and min_mac > .9 and crossing_error == 0 and not assignment_ambiguous
                            and degenerate.ambiguous.all())
    write_json(args.output/"qualification.json", report)
    with (args.output/"crossing.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["parameter", "rank0_GHz", "rank1_GHz", "character0_GHz", "character1_GHz"])
        for t, ranked, modes in zip(parameter, sorted_frequency, tracked):
            writer.writerow([t, *ranked, *modes])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.4), sharey=True)
    for ax, data, title in zip(axes, (sorted_frequency, tracked), ("Frequency rank", "Spatial mode character")):
        for i in range(2):
            ax.plot(parameter, data[:, i], "o-", label=f"{i}")
        ax.set(xlabel="Synthetic parameter", title=title)
        ax.legend()
    axes[0].set_ylabel("Frequency (GHz)")
    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(args.output/f"crossing.{suffix}", dpi=160)
    plt.close(fig)
    print(json.dumps({"passed": report["passed"], "minimum_skyrmion_MAC": min_mac,
                      "crossing_error_GHz": crossing_error, "ambiguous_degenerate_pairs": int(degenerate.ambiguous.sum())}, indent=2))
    if args.check and not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
