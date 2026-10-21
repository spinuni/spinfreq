"""Sequential local parameter studies with explicit magnetic-state history.

Independent cases start from their configured seed. A one-axis continuation
instead starts from the preceding successful equilibrium, stopping on failure.
No mode-branch identification or continuum qualification is implied.
"""
import argparse
import csv
from dataclasses import dataclass
import hashlib
from importlib.metadata import version
from itertools import product
import json
import math
import os
from pathlib import Path
import platform

import numpy as np
import scipy

from .config import JobConfig
from .jobs import ARTIFACTS, run_job, write_json


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _set_parameter(data, name, value):
    numeric = {"nx", "ny", "dx_m", "dy_m", "thickness_m", "seed_radius_m", "seed_wall_m",
               "fmin_Hz", "fmax_Hz", "points", "torque_tolerance_T", "maxiter"}
    numeric.update("material."+key for key in ("Ms", "A", "D", "K", "alpha", "gamma"))
    numeric.update(f"{key}.{i}" for key in ("field_T", "drive_T") for i in range(3))
    if name not in numeric:
        raise ValueError(f"Unsupported numeric study parameter: {name}")
    parts = name.split(".")
    if len(parts) == 1:
        data[name] = value
    elif isinstance(data[parts[0]], list):
        data[parts[0]][int(parts[1])] = value
    else:
        data[parts[0]][parts[1]] = value


@dataclass(frozen=True)
class StudyConfig:
    base: JobConfig
    axes: dict
    continuation: bool = False

    def __post_init__(self):
        if not isinstance(self.base, JobConfig) or not isinstance(self.axes, dict) or not self.axes:
            raise ValueError("Require a base JobConfig and nonempty axes object")
        if type(self.continuation) is not bool:
            raise ValueError("continuation must be boolean")
        axes = {}
        count = 1
        for key, values in self.axes.items():
            if not isinstance(key, str) or not isinstance(values, (list, tuple)) or not values:
                raise ValueError("Each axis requires a name and nonempty values")
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
                raise ValueError("Axis values must be finite real numbers")
            count *= len(values)
            axes[key] = tuple(values)
        if count > 1024:
            raise ValueError("Study limit: 1024 sequential cases")
        if self.continuation and (len(axes) != 1 or not next(iter(axes)).startswith(("field_T.", "material."))):
            raise ValueError("Continuation requires one field/material axis with a fixed mesh")
        object.__setattr__(self, "axes", dict(sorted(axes.items())))
        # Validate every configuration before creating any output or executing.
        self.cases()

    def cases(self):
        result = []
        for values in product(*self.axes.values()):
            parameters = dict(zip(self.axes, values))
            data = json.loads(json.dumps(self.base.to_dict()))
            for name, value in parameters.items():
                _set_parameter(data, name, value)
            result.append((parameters, JobConfig.from_dict(data)))
        return result

    def to_dict(self):
        return {"schema_version": 1, "base": json.loads(json.dumps(self.base.to_dict())),
                "axes": {key: list(values) for key, values in self.axes.items()},
                "continuation": self.continuation}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data)-{"schema_version", "base", "axes", "continuation"}:
            raise ValueError("Unknown or malformed study configuration")
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise ValueError("Study schema_version must be integer 1")
        if "base" not in data or "axes" not in data:
            raise ValueError("Study requires base and axes")
        return cls(JobConfig.from_dict(data["base"]), data["axes"], data.get("continuation", False))

    @classmethod
    def load(cls, path):
        def unique(pairs):
            data = {}
            for key, value in pairs:
                if key in data:
                    raise ValueError(f"Duplicate study JSON key: {key}")
                data[key] = value
            return data
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique))


def _implementation():
    sources = ("model.py", "confined.py", "equilibrium.py", "linear_response.py",
               "config.py", "jobs.py", "ovf.py", "studies.py")
    return {"package_version": version("spinfreq"), "python": platform.python_version(),
            "numpy": np.__version__, "scipy": scipy.__version__,
            "sources": {name: hashlib.sha256(Path(__file__).with_name(name).read_text(encoding="utf-8").encode()).hexdigest()
                        for name in sources}}


def _case_path(output, index, attempt):
    return output / "cases" / f"{index:04d}" / f"attempt-{attempt:04d}"


def _verify(output, record):
    attempt = record["attempts"][-1]
    directory = _case_path(output, record["index"], len(record["attempts"])-1)
    hashes = attempt.get("sha256", {})
    if set(hashes) != set(ARTIFACTS):
        raise ValueError(f"Incomplete artifact hashes for case {record['index']}")
    for name, digest in hashes.items():
        if not (directory/name).is_file() or _digest(directory/name) != digest:
            raise ValueError(f"Artifact integrity failed: case {record['index']} / {name}")
    return directory


def _tables(output, ledger):
    axes = list(ledger["configuration"]["axes"])
    case_fields = ["case", *axes, "status", "attempts", "lowest_frequency_Hz", "torque_T",
                   "max_delta_m", "energy_J", "topological_charge", "mean_mx", "mean_my", "mean_mz", "error"]
    with (output/"cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=case_fields)
        writer.writeheader()
        for record in ledger["cases"]:
            row = {"case": record["index"], **record["parameters"], "status": record["status"],
                   "attempts": len(record["attempts"])}
            if record["attempts"]:
                row.update(record["attempts"][-1].get("observables", {}))
                row["error"] = record["attempts"][-1].get("error", "")
            writer.writerow(row)
    with (output/"poles.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case", *axes, "frequency_rank", "frequency_Hz", "decay_rate_per_s", "isolated_pole_width_Hz"])
        for record in ledger["cases"]:
            if record["status"] != "succeeded":
                continue
            directory = _case_path(output, record["index"], len(record["attempts"])-1)
            with np.load(directory/"modes.npz", allow_pickle=False) as data:
                positive = data["eigenvalues"][data["eigenvalues"].imag > 0]
            for rank, value in enumerate(positive):
                writer.writerow([record["index"], *record["parameters"].values(), rank,
                                 value.imag/(2*np.pi), -value.real, -value.real/np.pi])


def _plot(output, ledger):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    try:
        for record in ledger["cases"]:
            if record["status"] != "succeeded":
                continue
            directory = _case_path(output, record["index"], len(record["attempts"])-1)
            with np.load(directory/"response.npz", allow_pickle=False) as data:
                label = f"{record['index']}: " + ", ".join(f"{key}={value:g}" for key, value in record["parameters"].items())
                ax.plot(data["frequencies_Hz"]/1e9, data["absorbed_power_W"], label=label)
        ax.set(xlabel="Frequency (GHz)", ylabel="Absorbed power (W)", title="Parameter study · sampled linear response")
        if 0 < sum(r["status"] == "succeeded" for r in ledger["cases"]) <= 12:
            ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(output/"spectra.png", dpi=150)
        fig.savefig(output/"spectra.pdf")
    finally:
        plt.close(fig)


def run_study(config: StudyConfig, output, *, resume=False):
    """Run a study serially; resume only verified results from identical code.

    Failed/interrupted attempts are retained and retried in new directories.
    A lock prevents simultaneous writers. After a hard process kill, verify
    that no writer remains before manually removing .study.lock.
    """
    cases = config.cases()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if not resume and any(output.iterdir()):
        raise FileExistsError("Use an empty study directory, or --resume for the same study")
    lock = output/".study.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError("Study is locked; ensure no writer remains before removing .study.lock") from None
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        fingerprint = _implementation()
        plan = config.to_dict()
        if resume:
            ledger = json.loads((output/"study.json").read_text(encoding="utf-8"))
            if ledger.get("configuration") != plan or ledger.get("implementation") != fingerprint:
                raise ValueError("Study configuration or numerical implementation changed; use a new output directory")
            if len(ledger["cases"]) != len(cases):
                raise ValueError("Study case ledger does not match its configuration")
            for index, (record, (parameters, _)) in enumerate(zip(ledger["cases"], cases)):
                if record["index"] != index or record["parameters"] != parameters:
                    raise ValueError("Study case identity mismatch")
                if record["status"] == "succeeded":
                    directory = _verify(output, record)
                    if JobConfig.load(directory/"configuration.json") != cases[index][1]:
                        raise ValueError("Saved case configuration does not match the study")
        else:
            ledger = {"schema_version": 1, "configuration": plan, "configuration_sha256": _canonical(plan),
                      "implementation": fingerprint, "status": "running",
                      "cases": [{"index": i, "parameters": parameters, "status": "pending", "attempts": []}
                                for i, (parameters, _) in enumerate(cases)]}
        write_json(output/"study.json", ledger)
        previous = None
        for index, (parameters, job_config) in enumerate(cases):
            record = ledger["cases"][index]
            if record["status"] == "succeeded":
                previous = _verify(output, record)
                continue
            if record["attempts"] and record["attempts"][-1]["status"] == "running":
                record["attempts"][-1]["status"] = "interrupted"
            initial = np.load(previous/"equilibrium.npy", allow_pickle=False) if config.continuation and previous else None
            directory = _case_path(output, index, len(record["attempts"]))
            attempt = {"status": "running", "directory": directory.relative_to(output).as_posix(),
                       "initial_from_case": index-1 if initial is not None else None}
            record["attempts"].append(attempt)
            record["status"] = "running"
            ledger["status"] = "running"
            write_json(output/"study.json", ledger)
            try:
                summary = run_job(job_config, directory, initial_m=initial)
                with np.load(directory/"modes.npz", allow_pickle=False) as data:
                    frequencies = data["eigenvalues"].imag/(2*np.pi)
                mean = np.load(directory/"equilibrium.npy", allow_pickle=False).mean(axis=(0, 1))
                attempt["observables"] = {"lowest_frequency_Hz": float(min(frequencies[frequencies > 0])),
                                          "torque_T": summary["torque_T"], "max_delta_m": summary["max_delta_m"],
                                          "energy_J": summary["energy_J"], "topological_charge": summary["topological_charge"],
                                          **dict(zip(("mean_mx", "mean_my", "mean_mz"), map(float, mean)))}
                attempt["sha256"] = {name: _digest(directory/name) for name in ARTIFACTS}
                record["status"] = attempt["status"] = "succeeded"
                previous = directory
            except Exception as error:
                record["status"] = attempt["status"] = "failed"
                attempt["error"] = str(error)
            write_json(output/"study.json", ledger)
            _tables(output, ledger)
            if config.continuation and record["status"] != "succeeded":
                break
        ledger["status"] = "succeeded" if all(r["status"] == "succeeded" for r in ledger["cases"]) else "failed"
        write_json(output/"study.json", ledger)
        _tables(output, ledger)
        _plot(output, ledger)
        return ledger
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Local reproducible parameter studies; all inputs in SI")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print case parameters without calculations or output files")
    parser.add_argument("--version", action="version", version=f"SpinFreq {version('spinfreq')}")
    args = parser.parse_args()
    if not args.output and not args.dry_run:
        parser.error("--output is required unless --dry-run is used")
    if args.resume and args.dry_run:
        parser.error("--resume and --dry-run cannot be combined")
    try:
        spec = StudyConfig.load(args.config)
        if args.dry_run:
            print(json.dumps({"case_count": len(spec.cases()), "continuation": spec.continuation,
                              "cases": [{"index": i, "parameters": values}
                                        for i, (values, _) in enumerate(spec.cases())]}, indent=2))
            return
        result = run_study(spec, args.output, resume=args.resume)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{result['status']}: {sum(r['status'] == 'succeeded' for r in result['cases'])}/{len(result['cases'])} cases; {args.output}")
    if result["status"] != "succeeded":
        parser.exit(1)


if __name__ == "__main__":
    main()
