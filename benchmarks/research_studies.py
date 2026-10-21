"""Independently check research field/damping studies against Gilbert FMR."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from spinfreq import StudyConfig, run_study
from spinfreq.jobs import write_json
from spinfreq.model import MU0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/research-workflow"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=True)
    rows, studies = [], {}
    for family in ("fmr-field-sweep", "fmr-damping-sweep"):
        spec = StudyConfig.load(root/"examples/studies"/f"{family}.json")
        output = args.output/family
        result = run_study(spec, output, resume=args.resume)
        if result["status"] != "succeeded":
            raise RuntimeError(f"{family} did not succeed")
        studies[family] = {"configuration_sha256": result["configuration_sha256"],
                           "configuration": result["configuration"], "implementation": result["implementation"]}
        for record, (_, config) in zip(result["cases"], spec.cases()):
            directory = output/record["attempts"][-1]["directory"]
            p = config.material
            field = config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms
            rate = p.gamma/(1+p.alpha**2)
            omega0 = rate*field
            frequency = omega0/(2*np.pi)
            width = 2*p.alpha*frequency
            with np.load(directory/"modes.npz", allow_pickle=False) as modes:
                value = modes["eigenvalues"][modes["eigenvalues"].imag > 0].item()
            with np.load(directory/"response.npz", allow_pickle=False) as data:
                omega = 2*np.pi*data["frequencies_Hz"]
                s = 1j*omega+p.alpha*omega0
                # Closed 2x2 Gilbert susceptibility in physical x/y coordinates.
                # It does not use the simulator's tangent basis or Jacobian.
                denominator = s*s+omega0*omega0
                drive = config.drive_T[0]
                mx = rate*drive*(p.alpha*s+omega0)/denominator
                my = rate*drive*(p.alpha*omega0-s)/denominator
                expected = np.stack((mx, my, np.zeros_like(mx)), axis=-1)[:, None, None, :]
                response_error = np.linalg.norm(data["delta_m"]-expected)/np.linalg.norm(expected)
                power = -p.Ms*config.dx_m*config.dy_m*config.thickness_m*omega*drive*mx.imag/2
                power_error = np.linalg.norm(data["absorbed_power_W"]-power)/np.linalg.norm(power)
            rows.append({"study": family, "case": record["index"], "field_T": config.field_T[2], "alpha": p.alpha,
                         "frequency_Hz": value.imag/(2*np.pi), "analytic_frequency_Hz": frequency,
                         "pole_width_Hz": -value.real/np.pi, "analytic_pole_width_Hz": width,
                         "frequency_relative_error": abs(value.imag/(2*np.pi)/frequency-1),
                         "width_relative_error": abs(-value.real/np.pi/width-1),
                         "complex_response_relative_error": float(response_error),
                         "power_relative_error": float(power_error)})
    errors = {key: max(row[key] for row in rows) for key in rows[0] if key.endswith("error")}
    report = {"scope": "Single-cell periodic perpendicular FMR; no device or noncollinear qualification",
              "case_count": len(rows), "tolerance": 1e-10, "max_errors": errors,
              "passed": all(error < 1e-10 for error in errors.values()), "studies": studies}
    write_json(args.output/"report.json", report)
    with (args.output/"analytic_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
    for ax, family, x, computed, expected, xlabel, ylabel in (
        (axes[0], "fmr-field-sweep", "field_T", "frequency_Hz", "analytic_frequency_Hz", "Bias Bz (T)", "Pole frequency (GHz)"),
        (axes[1], "fmr-damping-sweep", "alpha", "pole_width_Hz", "analytic_pole_width_Hz", "Gilbert damping", "Isolated-pole width (GHz)"),
    ):
        selected = [row for row in rows if row["study"] == family]
        ax.plot([r[x] for r in selected], [r[expected]/1e9 for r in selected], label="Analytical Gilbert")
        ax.plot([r[x] for r in selected], [r[computed]/1e9 for r in selected], "o", mfc="none", label="SpinFreq study")
        ax.set(xlabel=xlabel, ylabel=ylabel)
        ax.legend(fontsize=8)
    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(args.output/f"analytic_comparison.{suffix}", dpi=160)
    plt.close(fig)
    print(json.dumps({"passed": report["passed"], "cases": len(rows), "max_errors": errors}, indent=2))
    if args.check and not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
