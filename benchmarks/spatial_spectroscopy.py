"""Analytical polarized/finite-k FMR and localized source/probe checks."""
import argparse
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np

from spinfreq import Film, Probe, SpatialProfile, run_job
from spinfreq.config import presets
from spinfreq.jobs import write_json
from spinfreq.model import MU0
from spinfreq.profiles import excitation_field
from spinfreq.studies import _implementation


def analytic(config, frequencies, k=0.):
    """Physical x/y Gilbert susceptibility, independent of the tangent solver."""
    p = config.material
    base = config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms+2*p.A/p.Ms*k*k
    nzz = -np.expm1(-abs(k)*config.thickness_m)/(abs(k)*config.thickness_m) if k else 1.
    hx, hy = base+MU0*p.Ms*(1-nzz), base
    rate = p.gamma/(1+p.alpha**2)
    matrix = rate*np.array([[-p.alpha*hx, -hy], [hx, -p.alpha*hy]])
    b = np.asarray(config.drive_T)+1j*np.asarray(config.drive_imag_T)
    force = rate*np.array([p.alpha*b[0]+b[1], -b[0]+p.alpha*b[1]])
    response = np.array([np.r_[np.linalg.solve(2j*np.pi*f*np.eye(2)-matrix, force), 0j] for f in frequencies])
    volume = config.nx*config.ny*config.dx_m*config.dy_m*config.thickness_m
    power = -.5*p.Ms*volume*(2*np.pi*frequencies)*np.imag(np.sum(b.conj()*response, axis=1))
    return response, power


def relative(computed, reference):
    return float(np.linalg.norm(computed-reference)/np.linalg.norm(reference))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/spatial-spectroscopy"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, powers, spectra, definitions = [], {}, {}, {}
    base = replace(presets()["periodic-fmr"], nx=1, ny=1, fmin_Hz=40e9, fmax_Hz=140e9, points=101)
    cases = [
        ("circular_co", replace(base, drive_imag_T=(0., -1e-6, 0.)), 0.),
        ("circular_counter", replace(base, drive_imag_T=(0., 1e-6, 0.)), 0.),
        ("elliptical", replace(base, drive_T=(1e-6, .3e-6, 0.), drive_imag_T=(.2e-6, -.8e-6, 0.)), 0.),
    ]
    k0 = 2*np.pi/(8*8e-9)
    for name, k in (("wave_plus", k0), ("wave_minus", -k0)):
        profile = SpatialProfile("plane_wave", k_rad_m=(k, 0.), phase_rad=.3)
        config = replace(base, nx=8, dx_m=8e-9, drive_profile=profile,
                         probes=(Probe("matched", profile), Probe("mean"),
                                 Probe("opposite", SpatialProfile("plane_wave", k_rad_m=(-k, 0.), phase_rad=.3))))
        cases.append((name, config, k))
    for name, config, k in cases:
        directory = args.output/name
        run_job(config, directory)
        definitions[name] = config.to_dict()
        with np.load(directory/"response.npz") as data, np.load(directory/"observations.npz") as observation:
            f = data["frequencies_Hz"]
            expected, power = analytic(config, f, k)
            sampled = excitation_field(config)[..., 0]/config.drive_T[0] if k else np.ones((1, 1))
            field = expected[:, None, None, :]*sampled[None, ..., None]
            response_error = relative(data["delta_m"], field)
            power_error = relative(data["absorbed_power_W"], power)
            probe_error = relative(observation["delta_m"][:, 0], expected)
            leakage = float(np.linalg.norm(observation["delta_m"][:, 1:])/np.linalg.norm(expected)) if k else None
            rows.append({"case": name, "response_relative_error": response_error,
                         "power_relative_error": power_error, "probe_relative_error": probe_error,
                         "forbidden_probe_relative_amplitude": leakage})
            powers[name] = data["absorbed_power_W"].copy()
            spectra[name] = (f.copy(), data["absorbed_power_W"].copy())
    # A spatially local experiment checks distinct detectors and drive scaling.
    root = Path(__file__).resolve().parents[1]
    from spinfreq import JobConfig
    localized = JobConfig.load(root/"examples/spectroscopy/localized-source.json")
    local_fields = []
    for name, scale in (("localized", 1.), ("localized_half", .5)):
        config = replace(localized, drive_T=tuple(scale*v for v in localized.drive_T))
        directory = args.output/name
        run_job(config, directory)
        definitions[name] = config.to_dict()
        m = np.load(directory/"equilibrium.npy")
        film = Film(nx=config.nx, ny=config.ny, dx=config.dx_m, dy=config.dy_m,
                    thickness=config.thickness_m, material=config.material, field_T=config.field_T)
        with np.load(directory/"response.npz") as data, np.load(directory/"observations.npz") as obs:
            f = data["frequencies_Hz"]
            direct = film.response(m, f, excitation_field(config))
            b = excitation_field(config)
            direct_power = -.5*config.material.Ms*config.dx_m*config.dy_m*config.thickness_m*(2*np.pi*f)*np.imag(
                np.sum(b.conj()*direct, axis=(1, 2, 3)))
            row = {"case": name, "response_relative_error": relative(data["delta_m"], direct),
                   "power_relative_error": relative(data["absorbed_power_W"], direct_power),
                   "probe_relative_error": 0., "forbidden_probe_relative_amplitude": None}
            # Deliberately independent loops verify the conjugation and L1 weights.
            measured = np.empty_like(obs["delta_m"])
            for p, weights in enumerate(obs["weights"]):
                for i, field in enumerate(data["delta_m"]):
                    measured[i, p] = (weights.conj()[..., None]*field).sum(axis=(0, 1))/np.abs(weights).sum()
            row["probe_relative_error"] = relative(obs["delta_m"], measured)
            rows.append(row)
            spectra[name] = (f.copy(), data["absorbed_power_W"].copy())
            local_fields.append((data["delta_m"].copy(), data["absorbed_power_W"].copy(), obs["delta_m"].copy()))
    scaling = {"field": relative(local_fields[1][0], .5*local_fields[0][0]),
               "power": relative(local_fields[1][1], .25*local_fields[0][1]),
               "probes": relative(local_fields[1][2], .5*local_fields[0][2])}
    peak = int(np.argmax(powers["circular_co"]))
    helicity_ratio = float(powers["circular_co"][peak]/powers["circular_counter"][peak])
    report = {"case_count": len(rows), "cases": rows, "amplitude_scaling_errors": scaling,
              "circular_power_ratio_at_co_peak": helicity_ratio, "relative_tolerance": 1e-10,
              "configuration": definitions, "implementation": _implementation(),
              "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "Analytical linear uniform and finite-k periodic FMR; localized numerical cross-check, not device/current physics"}
    report["passed"] = bool(helicity_ratio > 100 and all(value < 1e-10 for row in rows for key, value in row.items()
                                                       if key != "case" and value is not None)
                            and all(value < 1e-10 for value in scaling.values()))
    write_json(args.output/"report.json", report)
    with (args.output/"comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, names in ((axes[0], ("circular_co", "circular_counter", "elliptical")),
                      (axes[1], ("wave_plus", "localized", "localized_half"))):
        for name in names:
            f, power = spectra[name]
            ax.plot(f/1e9, power, label=name)
        ax.set(xlabel="Frequency (GHz)", ylabel="Absorbed power (W)")
        ax.legend(fontsize=8)
    fig.tight_layout()
    for suffix in ("png", "pdf"):
        fig.savefig(args.output/f"spectra.{suffix}", dpi=160)
    plt.close(fig)
    with np.load(args.output/"localized/observations.npz") as data:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
        for i, name in enumerate(data["probe_names"]):
            signal = data["delta_m"][:, i, 0]
            axes[0].plot(data["frequencies_Hz"]/1e9, np.abs(signal)/localized.drive_T[0], label=str(name))
            axes[1].plot(data["frequencies_Hz"]/1e9, np.unwrap(np.angle(signal))*180/np.pi, label=str(name))
        axes[0].set(xlabel="Frequency (GHz)", ylabel="|detected delta mx / source prefactor| (1/T)")
        axes[1].set(xlabel="Frequency (GHz)", ylabel="Unwrapped phase of delta mx (degrees)")
        for ax in axes:
            ax.legend(fontsize=8)
        fig.tight_layout()
        for suffix in ("png", "pdf"):
            fig.savefig(args.output/f"detectors.{suffix}", dpi=160)
        plt.close(fig)
        fig, axes = plt.subplots(1, len(data["probe_names"])+1, figsize=(12, 2.8))
        extent = (0, localized.nx*localized.dx_m*1e9, 0, localized.ny*localized.dy_m*1e9)
        drive = np.load(args.output/"localized/excitation.npy")
        samples = [np.linalg.norm(drive, axis=-1)*1e6, *np.abs(data["weights"])]
        titles = ["Drive |b| (microtesla)", *[str(name)+" |weight|" for name in data["probe_names"]]]
        for ax, sample, title in zip(axes, samples, titles):
            im = ax.imshow(sample, origin="lower", extent=extent, interpolation="nearest")
            ax.set(xlabel="x (nm)", ylabel="y (nm)", title=title)
            fig.colorbar(im, ax=ax, shrink=.65)
        fig.tight_layout()
        for suffix in ("png", "pdf"):
            fig.savefig(args.output/f"profiles.{suffix}", dpi=160)
        plt.close(fig)
    print(json.dumps({"passed": report["passed"], "cases": len(rows), "helicity_power_ratio": helicity_ratio,
                      "max_relative_error": max(value for row in rows for key, value in row.items()
                                                if key != "case" and value is not None),
                      "amplitude_scaling_errors": scaling}, indent=2))
    if args.check and not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
