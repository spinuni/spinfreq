"""Check noncollinear continuation against archived independent OOMMF poles."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from spinfreq import StudyConfig, run_study
from spinfreq.jobs import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/research-continuation"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec = StudyConfig.load(root/"examples/studies/skyrmion-field-path.json")
    result = run_study(spec, args.output/"study", resume=args.resume)
    if result["status"] != "succeeded":
        raise RuntimeError("Skyrmion continuation did not succeed")
    rows = []
    initial_states_match = True
    previous = None
    for record in result["cases"]:
        directory = args.output/"study"/record["attempts"][-1]["directory"]
        if previous:
            initial_states_match &= (directory/"initial.npy").read_bytes() == (previous/"equilibrium.npy").read_bytes()
        previous = directory
        field = record["parameters"]["field_T.2"]
        if field not in (0., .05):
            continue
        reference = root/"validation/skyrmion_temporal"/f"field_{round(field*1000)}mT"/"summary.json"
        summary = json.loads(reference.read_text())
        with np.load(directory/"modes.npz", allow_pickle=False) as data:
            values = data["eigenvalues"]
            frequencies = values[values.imag > 0].imag[:3]/(2*np.pi)
        for frequency, mode in zip(frequencies, summary["modes"]):
            expected = mode["OOMMF_fitted_frequency_GHz"]*1e9
            rows.append({"field_T": field, "mode": mode["mode"], "frequency_Hz": float(frequency),
                         "OOMMF_frequency_Hz": expected, "relative_error": float(abs(frequency/expected-1)),
                         "reference": str(reference.relative_to(root))})
    maximum = max(row["relative_error"] for row in rows)
    report = {"scope": "Coarse 2 nm single-layer confined skyrmion; archived OOMMF endpoints only; 25 mT is numerical continuation",
              "case_count": len(result["cases"]), "reference_pole_count": len(rows),
              "max_frequency_relative_error": maximum, "frequency_relative_tolerance": .0003,
              "initial_states_match_predecessors": bool(initial_states_match),
              "passed": bool(initial_states_match and len(rows) == 6 and maximum < .0003),
              "configuration": result["configuration"], "implementation": result["implementation"]}
    write_json(args.output/"report.json", report)
    with (args.output/"endpoint_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({key: value for key, value in report.items() if key not in ("configuration", "implementation")}, indent=2))
    if args.check and not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
