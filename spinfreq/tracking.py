"""Phase-invariant spatial mode matching and cautious one-axis study analysis.

MAC is a Euclidean spatial-shape diagnostic, not a biorthogonal modal weight.
Assignments near degeneracy, with low overlap or with close alternatives remain
provisional. Uncertainty in a lineage is retained after subsequent good matches.
"""
import argparse
import csv
from dataclasses import dataclass
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from .jobs import ARTIFACTS, write_json
from .studies import StudyConfig, _case_path, _digest


@dataclass(frozen=True)
class ModeMatch:
    previous_indices: np.ndarray
    current_indices: np.ndarray
    overlaps: np.ndarray
    row_margins: np.ndarray
    column_margins: np.ndarray
    ambiguous: np.ndarray


def _normalized(modes):
    modes = np.asarray(modes, dtype=complex)
    if modes.ndim < 2 or not len(modes) or not np.all(np.isfinite(modes)):
        raise ValueError("Require nonempty finite spatial modes with a leading mode axis")
    vectors = modes.reshape(len(modes), -1)
    peak = np.abs(vectors).max(axis=1)
    if not np.all(peak > 0) or not np.all(np.isfinite(peak)):
        raise ValueError("Mode vectors must be nonzero and finite")
    vectors = vectors.real/peak[:, None]+1j*(vectors.imag/peak[:, None])
    return vectors/np.linalg.norm(vectors, axis=1)[:, None]


def match_modes(previous, current, *, min_overlap=.5, min_margin=.1):
    """Maximum-total-MAC assignment, with row and column competition checks.

    MAC = |v_old^H v_new|^2/(||v_old||^2 ||v_new||^2). Mode arrays must share
    their spatial shape. Counts may differ; only assigned pairs are returned.
    """
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
           for v in (min_overlap, min_margin)):
        raise ValueError("Overlap and margin thresholds must lie in [0, 1]")
    a, b = _normalized(previous), _normalized(current)
    if np.shape(previous)[1:] != np.shape(current)[1:]:
        raise ValueError("Spatial mode shapes must match")
    mac = np.clip(np.abs(a.conj()@b.T)**2, 0, 1)
    rows, columns = linear_sum_assignment(-mac)
    scores = mac[rows, columns]
    row_margins, column_margins = [], []
    for row, column, score in zip(rows, columns, scores):
        row_other = np.delete(mac[row], column)
        col_other = np.delete(mac[:, column], row)
        row_margins.append(float(score-row_other.max()) if len(row_other) else 1.)
        column_margins.append(float(score-col_other.max()) if len(col_other) else 1.)
    row_margins, column_margins = np.array(row_margins), np.array(column_margins)
    ambiguous = (scores < min_overlap) | (row_margins < min_margin) | (column_margins < min_margin)
    return ModeMatch(rows, columns, scores, row_margins, column_margins, ambiguous)


def _near_frequency(frequencies, absolute_Hz, relative):
    f = np.asarray(frequencies)
    distance = np.abs(f[:, None]-f[None, :])
    threshold = absolute_Hz+relative*np.maximum(np.abs(f[:, None]), np.abs(f[None, :]))
    mask = distance <= threshold
    np.fill_diagonal(mask, False)
    return mask.any(axis=1)


def track_study(study, output, *, max_modes=12, min_overlap=.5, min_margin=.1,
                near_Hz=1e6, near_relative=1e-4):
    """Analyze verified completed cases of a fixed-mesh, one-axis study.

    Failed/unfinished cases break the tracking chain. No output is overwritten.
    A study lock prevents a simultaneous study writer from changing inputs.
    """
    if type(max_modes) is not int or not 1 <= max_modes <= 128:
        raise ValueError("max_modes must be an integer from 1 to 128")
    for name, value, maximum in (("min_overlap", min_overlap, 1), ("min_margin", min_margin, 1),
                                  ("near_Hz", near_Hz, math.inf), ("near_relative", near_relative, 1)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
            raise ValueError(f"Invalid {name}")
    study, output = Path(study).resolve(), Path(output).resolve()
    if output == study or output.is_relative_to(study/"cases"):
        raise ValueError("Use a separate analysis directory, such as study/tracking")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Tracking output must be empty")
    lock = study/".study.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeError("Study is locked; finish the running study before analysis") from None
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        ledger = json.loads((study/"study.json").read_text(encoding="utf-8"))
        spec = StudyConfig.from_dict(ledger["configuration"])
        cases = spec.cases()
        if len(spec.axes) != 1 or len(ledger["cases"]) != len(cases):
            raise ValueError("Tracking requires a one-axis study with a complete case ledger")
        axis = next(iter(spec.axes))
        geometry = lambda c: (c.model, c.nx, c.ny, c.dx_m, c.dy_m, c.thickness_m, c.dmi_boundary)
        if any(geometry(c) != geometry(cases[0][1]) for _, c in cases):
            raise ValueError("Tracking requires the same model, mesh and boundaries at every step")
        snapshots, skipped, hashes = [], [], {}
        for index, (record, (parameters, config)) in enumerate(zip(ledger["cases"], cases)):
            if record["index"] != index or record["parameters"] != parameters:
                raise ValueError("Case identity differs from the study plan")
            if record["status"] != "succeeded":
                skipped.append({"case": index, "status": record["status"]})
                snapshots.append(None)
                continue
            if not record["attempts"] or record["attempts"][-1]["status"] != "succeeded":
                raise ValueError("Completed case has no successful attempt")
            attempt = record["attempts"][-1]
            directory = _case_path(study, index, len(record["attempts"])-1)
            saved = attempt.get("sha256", {})
            required = {"configuration.json", "summary.json", "modes.npz"}
            # Historical job versions may have fewer optional artifacts.
            if not required <= set(saved) or set(saved)-set(ARTIFACTS):
                raise ValueError("Incomplete or unsupported artifact manifest")
            for name, digest in saved.items():
                if not (directory/name).is_file() or _digest(directory/name) != digest:
                    raise ValueError(f"Artifact integrity failed: case {index} / {name}")
            from .config import JobConfig
            if JobConfig.load(directory/"configuration.json") != config:
                raise ValueError("Saved configuration differs from the planned case")
            snapshots.append((directory, config))
            hashes[str(index)] = saved
        if not any(snapshot is not None for snapshot in snapshots):
            raise ValueError("Study has no successful cases to analyze")
        rows, previous, previous_state = [], None, None
        next_branch, segment = 0, -1
        for index, snapshot in enumerate(snapshots):
            if snapshot is None:
                previous = previous_state = None
                continue
            directory, config = snapshot
            with np.load(directory/"modes.npz", allow_pickle=False) as data:
                values = data["eigenvalues"]
                full_modes = data["modes"]
            if (values.ndim != 1 or full_modes.shape != (len(values), config.ny, config.nx, 3)
                    or not np.all(np.isfinite(values))):
                raise ValueError("Invalid saved eigenmode dimensions or values")
            selected = np.flatnonzero(values.imag > 0)
            selected = selected[np.argsort(values[selected].imag)][:max_modes]
            if not len(selected):
                raise ValueError("Successful case has no positive-frequency modes")
            values, modes = values[selected], full_modes[selected]
            del full_modes
            _normalized(modes)
            f = values.imag/(2*np.pi)
            near = _near_frequency(f, near_Hz, near_relative)
            inherited = {}
            if previous is not None:
                matched = match_modes(previous[1], modes, min_overlap=min_overlap, min_margin=min_margin)
                for n, (old, new) in enumerate(zip(matched.previous_indices, matched.current_indices)):
                    ambiguous = bool(matched.ambiguous[n] or near[new] or previous_state[old]["near_frequency"])
                    inherited[int(new)] = (previous_state[old]["branch"], float(matched.overlaps[n]),
                                           float(matched.row_margins[n]), float(matched.column_margins[n]),
                                           ambiguous, bool(ambiguous or previous_state[old]["lineage_ambiguous"]))
            else:
                segment += 1
            current_state = []
            for rank, value in enumerate(values):
                if rank in inherited:
                    branch, score, row_margin, col_margin, ambiguous, lineage = inherited[rank]
                    status = "ambiguous" if ambiguous else "matched"
                else:
                    branch, next_branch = next_branch, next_branch+1
                    score = row_margin = col_margin = None
                    ambiguous = lineage = bool(near[rank])
                    status = "initial" if previous is None else "new"
                row = {"case": index, axis: cases[index][0][axis], "segment": segment, "branch": branch,
                       "frequency_rank": rank, "frequency_Hz": float(value.imag/(2*np.pi)),
                       "decay_rate_per_s": float(-value.real), "overlap": score,
                       "row_margin": row_margin, "column_margin": col_margin, "match_status": status,
                       "near_frequency": bool(near[rank]), "local_ambiguous": ambiguous, "lineage_ambiguous": lineage}
                rows.append(row)
                current_state.append(row)
            previous, previous_state = (values, modes), current_state
        report = {"schema_version": 1, "package_version": version("spinfreq"),
                  "study_sha256": _digest(study/"study.json"), "source_implementation": ledger.get("implementation"),
                  "analysis_sha256": _digest(Path(__file__)), "input_artifact_sha256": hashes,
                  "axis": axis, "max_modes": max_modes, "min_overlap": min_overlap, "min_margin": min_margin,
                  "near_Hz": near_Hz, "near_relative": near_relative, "skipped_cases": skipped,
                  "row_count": len(rows), "locally_ambiguous_rows": sum(r["local_ambiguous"] for r in rows),
                  "provisional_lineage_rows": sum(r["lineage_ambiguous"] for r in rows),
                  "scope": "Euclidean spatial mode-character assignment; provisional lineages remain flagged; no unique identity at degeneracies"}
        output.mkdir(parents=True, exist_ok=True)
        with (output/"branches.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        write_json(output/"tracking.json", report)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        for branch in sorted({r["branch"] for r in rows}):
            selected = [r for r in rows if r["branch"] == branch]
            ax.plot([r["case"] for r in selected], [r["frequency_Hz"]/1e9 for r in selected], color=".75", linewidth=.8)
        for provisional, color, label in ((False, "#176c68", "Clear lineage"), (True, "#c29137", "Provisional lineage")):
            selected = [r for r in rows if r["lineage_ambiguous"] == provisional]
            if selected:
                ax.scatter([r["case"] for r in selected], [r["frequency_Hz"]/1e9 for r in selected], s=20, c=color, label=label)
        ax.set(xlabel=f"Scan step ({axis} values in CSV)", ylabel="Frequency (GHz)", title="Spatial mode-character matches")
        ax.legend(); fig.tight_layout()
        for suffix in ("png", "pdf"):
            fig.savefig(output/f"branches.{suffix}", dpi=150)
        plt.close(fig)
        return report
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Match spatial modes along a verified one-axis study")
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-modes", type=int, default=12)
    args = parser.parse_args()
    try:
        report = track_study(args.study, args.output, max_modes=args.max_modes)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Saved branches.csv and branches.png to {args.output}")
    print(f"Provisional lineage rows: {report['provisional_lineage_rows']} / {report['row_count']}; inspect their flags before assigning identities.")


if __name__ == "__main__":
    main()
