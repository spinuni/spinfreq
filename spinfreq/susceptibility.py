"""B-based source/probe transfer tensors and non-Hermitian modal residues."""
import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path

import numpy as np

from .profiles import SpatialProfile, Probe, observe
from .linear_response import ModalResponse
from .pole_groups import group_poles, grouped_response


def susceptibility(prepared, frequencies_Hz, source_weights=None, probe_weights=None):
    """Return tensor (nf,np,3,3) in 1/T and residues (nm,np,3,3) in 1/(T s).

    Rows are observed xyz; columns are source xyz. Source weights are NOT
    normalized. Probes use observe's conjugated L1 normalization. All signed
    poles are retained. Individual residues within a degenerate eigenspace
    depend on the eigenbasis; only their sum has an invariant interpretation.
    This low-level linear calculation does not certify stability or amplitudes.
    """
    shape = prepared.m.shape[:2]
    frequencies_Hz = np.atleast_1d(np.asarray(frequencies_Hz, dtype=float))
    if frequencies_Hz.ndim != 1 or not len(frequencies_Hz) or not np.all(np.isfinite(frequencies_Hz)) or np.any(frequencies_Hz < 0):
        raise ValueError("Require a nonempty finite nonnegative frequency vector")
    source = np.ones(shape, complex) if source_weights is None else np.asarray(source_weights, complex)
    probes = np.ones((1, *shape), complex) if probe_weights is None else np.asarray(probe_weights, complex)
    if source.shape != shape or not np.all(np.isfinite(source)) or not np.any(abs(source) > 0):
        raise ValueError("Source must be finite, nonzero and match (ny,nx)")
    # Validate probes through the same observation function used by jobs.
    observe(np.zeros((1, *shape, 3)), probes)
    modes = np.einsum("yxci,yxin->nyxc", prepared.basis,
                      prepared.vectors.reshape(*shape, 2, -1))
    observed_modes = observe(modes, probes)
    tensors, residues, residuals, full_norms = [], [], [], []
    for component in range(3):
        drive = source[..., None]*np.eye(3)[component]
        response = prepared.response(frequencies_Hz, drive)
        full_norms.append(float(np.linalg.norm(response)))
        tensors.append(observe(response, probes))
        residuals.append(prepared.last_response_residuals.copy())
        coefficients = prepared._weights(prepared._force(drive))
        residues.append(observed_modes*coefficients[:, None, None])
    tensor = np.stack(tensors, axis=-1)
    residue = np.stack(residues, axis=-1)
    if not np.all(np.isfinite(tensor)) or not np.all(np.isfinite(residue)):
        raise RuntimeError("Susceptibility exceeded finite numerical range")
    return {"frequencies_Hz": np.atleast_1d(np.asarray(frequencies_Hz, float)),
            "tensor_per_T": tensor, "residues_per_T_s": residue,
            "eigenvalues_per_s": prepared.values.copy(),
            "full_field_response_norm_per_T": float(np.linalg.norm(full_norms)),
            "response_residuals": np.stack(residuals, axis=-1)}


def analyze_job(job, output, *, group_atol_Hz=1e6, group_rtol=1e-4):
    """Analyze an intact successful job made by the current numerical sources.

    Rebuild one dense basis from the saved equilibrium, without relaxing again.
    The original job and its manifest are never modified. A manifest provides
    integrity/provenance, not authentication of untrusted input.
    """
    from .config import JobConfig
    from .model import Film
    from .confined import ConfinedFilm
    from .jobs import ARTIFACTS, write_json

    job, output = Path(job), Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Use an empty tensor output directory")
    manifest = json.loads((job/"manifest.json").read_text())
    required = set(ARTIFACTS)-{"manifest.json", "results.zip"}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("Incomplete job manifest; create a fresh completed simulation")
    for name, digest in manifest.items():
        if hashlib.sha256((job/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Job artifact failed integrity check: {name}")
    summary = json.loads((job/"summary.json").read_text())
    if summary.get("status") != "succeeded":
        raise ValueError("A successful simulation is required")
    sources = summary.get("solver_source_sha256", {})
    expected_sources = {"model.py", "confined.py", "equilibrium.py", "linear_response.py",
                        "config.py", "profiles.py", "jobs.py"}
    if set(sources) != expected_sources or any(
        hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != digest
        for name, digest in sources.items()
    ):
        raise ValueError("Numerical sources changed; run a fresh simulation before tensor analysis")
    config = JobConfig.load(job/"configuration.json")
    m = np.load(job/"equilibrium.npy", allow_pickle=False)
    kwargs = dict(nx=config.nx, ny=config.ny, dx=config.dx_m, dy=config.dy_m,
                  thickness=config.thickness_m, material=config.material, field_T=config.field_T)
    film = Film(**kwargs) if config.model == "periodic" else ConfinedFilm(**kwargs, dmi_boundary=config.dmi_boundary)
    prepared = ModalResponse(film, m, config.torque_tolerance_T)
    source = (config.drive_profile or SpatialProfile()).evaluate(config.nx, config.ny, config.dx_m, config.dy_m)
    probes = config.probes or (Probe("mean"),)
    weights = np.array([p.profile.evaluate(config.nx, config.ny, config.dx_m, config.dy_m) for p in probes])
    frequencies = np.linspace(config.fmin_Hz, config.fmax_Hz, config.points)
    data = susceptibility(prepared, frequencies, source, weights)
    grouping = group_poles(data['eigenvalues_per_s'], data['residues_per_T_s'],
                           atol_Hz=group_atol_Hz, rtol=group_rtol)
    reconstructed = np.zeros_like(data['tensor_per_T'])
    for _, contribution in grouped_response(frequencies, prepared.values, data['residues_per_T_s'], grouping):
        reconstructed += contribution
    difference = np.linalg.norm(reconstructed-data['tensor_per_T'])
    # A Fourier probe may cancel the full signal. Scale the guard with the
    # full spatial response and modal contributions, not a vanishing tensor.
    modal_bound = sum(np.linalg.norm(residue)*np.linalg.norm(1/(2j*np.pi*frequencies-value))
                      for value, residue in zip(prepared.values, data['residues_per_T_s']))
    if not np.isfinite(modal_bound) or not np.isfinite(difference):
        raise RuntimeError('Grouped reconstruction exceeded finite numerical range')
    full_scale = data['full_field_response_norm_per_T']*np.sqrt(len(probes))
    group_error = float(difference/max(np.linalg.norm(data['tensor_per_T']), modal_bound, full_scale, 1e-300))
    if not np.isfinite(group_error) or group_error > 1e-7:
        raise RuntimeError('Grouped poles failed tensor reconstruction')
    drive = np.asarray(config.drive_T)+1j*np.asarray(config.drive_imag_T)
    predicted = np.einsum("fpij,j->fpi", data["tensor_per_T"], drive)
    with np.load(job/"observations.npz", allow_pickle=False) as saved:
        reference = saved["delta_m"]
    # Use the full-field response scale if the chosen observation cancels.
    with np.load(job/"response.npz", allow_pickle=False) as saved:
        scale = max(float(np.linalg.norm(saved["delta_m"])), 1e-300)
    error = float(np.linalg.norm(predicted-reference)/scale)
    if not np.isfinite(error) or error > 1e-7:
        raise RuntimeError("Tensor failed saved-drive reconstruction")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError("Use an empty tensor output directory")
    names = np.array([p.name for p in probes])
    np.savez_compressed(output/'pole_groups.npz', mode_group=grouping['mode_group'],
                        summed_residues_per_T_s=grouping['summed_residues'])
    write_json(output/'pole_groups.json', {key: value for key, value in grouping.items()
                                         if key not in ('mode_group', 'summed_residues')})
    with (output/'pole_groups.csv').open('w', newline='') as stream:
        columns = ['group', 'kind', 'count', 'signed_frequency_min_Hz', 'signed_frequency_max_Hz',
                   'growth_min_per_s', 'growth_max_per_s', 'complex_diameter_Hz', 'members']
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in grouping['groups']:
            writer.writerow({**record, 'members': ' '.join(map(str, record['members']))})
    np.savez_compressed(output/"susceptibility.npz", **data, probe_names=names,
                        source_weights=source, probe_weights=weights, drive_T=drive,
                        predicted_delta_m=predicted)
    with (output/"susceptibility.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["frequency_Hz", "probe", "observed_component", "drive_component", "real_per_T", "imag_per_T"])
        for f, tensor in zip(frequencies, data["tensor_per_T"]):
            for p, name in enumerate(names):
                for i, row in enumerate(tensor[p]):
                    for j, value in enumerate(row):
                        writer.writerow([f, name, "xyz"[i], "xyz"[j], value.real, value.imag])
    selected_residues = np.einsum("npij,j->npi", data["residues_per_T_s"], drive)
    np.savez_compressed(output/"modal_coupling.npz", eigenvalues_per_s=prepared.values,
                        probe_names=names, drive_T=drive, residues_per_s=selected_residues)
    with (output/"modal_coupling.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["signed_mode", "signed_frequency_Hz", "growth_rate_per_s", "probe",
                         "observed_component", "residue_real_per_s", "residue_imag_per_s"])
        for n, value in enumerate(prepared.values):
            for p, name in enumerate(names):
                for i, residue in enumerate(selected_residues[n, p]):
                    writer.writerow([n, value.imag/(2*np.pi), value.real, name,
                                     "xyz"[i], residue.real, residue.imag])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), constrained_layout=True)
    for j, ax in enumerate(axes):
        for p, name in enumerate(names):
            ax.plot(frequencies/1e9, np.linalg.norm(data["tensor_per_T"][:, p, :, j], axis=-1), label=name)
        ax.set(xlabel="Frequency (GHz)", ylabel="Vector transfer norm (1/T)", title=f"{'xyz'[j]}-polarized source")
    axes[0].legend()
    fig.savefig(output/"susceptibility.png", dpi=150)
    fig.savefig(output/"susceptibility.pdf")
    plt.close(fig)
    import scipy
    from importlib.metadata import version
    report = {"schema_version": 1, "status": "succeeded", "time_convention": "exp(+i omega t)",
              "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
              "package_version": version("spinfreq"),
              "tensor_units": "1/T", "residue_units": "1/(T s)",
              "tensor_axes": ["frequency", "probe", "observed_xyz", "drive_xyz"],
              "residue_axes": ["signed_mode", "probe", "observed_xyz", "drive_xyz"],
              "reconstruction_error_full_field_scaled": error,
              "max_response_residual": float(np.max(data["response_residuals"])),
              "grouped_tensor_reconstruction_scaled_error": group_error,
              "grouped_tensor_reconstruction_absolute_error_per_T": float(difference),
              "pole_groups": len(grouping['groups']),
              "source_job_manifest_sha256": hashlib.sha256((job/"manifest.json").read_bytes()).hexdigest(),
              "source_artifacts_sha256": manifest,
              "solver_source_sha256": sources,
              "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "grouping_source_sha256": hashlib.sha256(Path(__file__).with_name('pole_groups.py').read_bytes()).hexdigest(),
              "limits": ["Weighted B-based transfer, not H-based dimensionless susceptibility.",
                         "Unit-tesla normalization is a linear derivative, not a finite-amplitude simulation.",
                         "Modal residues are complex, interfere, and are not independent absorbed powers.",
                         "At degenerate poles interpret summed residues; individual modes depend on basis."]}
    write_json(output/"summary.json", report)
    write_json(output/"manifest.json", {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()})
    return report


def main():
    parser = argparse.ArgumentParser(description="Compare x/y/z field polarizations for a completed local CPU simulation.")
    parser.add_argument("--job", required=True, type=Path, help="Completed simulation directory (not ZIP)")
    parser.add_argument("--output", required=True, type=Path, help="New, empty analysis directory")
    parser.add_argument('--group-atol-Hz', type=float, default=1e6, help='Absolute complex-pole grouping tolerance in Hz (default 1e6)')
    parser.add_argument('--group-rtol', type=float, default=1e-4, help='Relative complex-pole grouping tolerance (default 1e-4)')
    args = parser.parse_args()
    try:
        report = analyze_job(args.job, args.output, group_atol_Hz=args.group_atol_Hz, group_rtol=args.group_rtol)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Tensor analysis stopped: {error}\n")
    print(f"Polarization comparison ready: {args.output/'susceptibility.png'}")
    print(f"Complex tensor: {args.output/'susceptibility.npz'} (1/T)")
    print(f"Saved-drive reconstruction error: {report['reconstruction_error_full_field_scaled']:.3g}")
