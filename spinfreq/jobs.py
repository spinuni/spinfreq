"""Reproducible small-signal calculation; no HTTP or queue dependencies."""
from dataclasses import asdict
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import platform
import os
import time
import zipfile

import numpy as np
import scipy
from scipy.linalg import norm, svdvals

from .config import JobConfig, presets
from .confined import ConfinedFilm
from .equilibrium import refine_equilibrium
from .linear_response import ModalResponse
from .model import Film, MU0, skyrmion_lattice
from .ovf import write_ovf


ARTIFACTS = ("configuration.json", "summary.json", "equilibrium.npy", "equilibrium.ovf",
             "modes.npz", "response.npz", "response.csv", "modes.csv", "spectrum.png",
             "equilibrium.png", "mode.png", "manifest.json", "results.zip")


class NumericalFailure(RuntimeError):
    """Configuration is valid, but numerical or small-signal checks failed."""


def write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False)+"\n")
    for attempt in range(10):
        try:
            temporary.replace(path)
            break
        except PermissionError as error:
            # Windows readers/antivirus can briefly hold a destination without
            # FILE_SHARE_DELETE. Preserve atomic publication; never truncate it.
            if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 9:
                raise
            time.sleep(.02)


def run_job(config: JobConfig, output, progress=None):
    """Run one job in an empty directory. Failure never exports spectra."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError("Use an empty output directory to avoid mixing results")
    progress = progress or (lambda stage: None)
    start = time.perf_counter()
    write_json(output/"configuration.json", config.to_dict())
    encoded = json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    summary = {"schema_version": 1, "configuration_sha256": hashlib.sha256(encoded).hexdigest(),
               "package_version": version("spinfreq"), "python": platform.python_version(),
               "numpy": np.__version__, "scipy": scipy.__version__, "status": "running",
               "model": config.model, "units": "SI", "time_convention": "exp(+i omega t)",
               "validation_scope": "edited research configuration; independent convergence required",
               "limits": ["Uniform magnetization through z; no thickness modes or multilayers.",
                          "Linear small-signal response; no nonlinear frequency-comb validation.",
                          "A stable discrete equilibrium does not establish mesh convergence."]}
    summary["solver_source_sha256"] = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("model.py", "confined.py", "equilibrium.py", "linear_response.py", "config.py", "jobs.py")
    }
    summary["thread_environment"] = {key: os.environ.get(key) for key in
                                     ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}
    summary['worker_runtime'] = os.environ.get('SPINFREQ_WORKER_RUNTIME', 'direct-python')
    for name, preset in presets().items():
        if config == preset:
            summary["preset"] = name
            summary["validation_scope"] = {
                "periodic-fmr": "Periodic discrete FMR; analytic uniform-mode tests, not finite-edge physics.",
                "prism-fmr": "Single-cell Gilbert susceptibility; not a resolved finite-film mode spectrum.",
                "confined-skyrmion": "2 nm matched OOMMF model; frequencies need spatial refinement for continuum accuracy."
            }[name]
    try:
        progress("relaxation")
        kwargs = dict(nx=config.nx, ny=config.ny, dx=config.dx_m, dy=config.dy_m,
                      thickness=config.thickness_m, material=config.material, field_T=config.field_T)
        film = (Film(**kwargs) if config.model == "periodic" else
                ConfinedFilm(**kwargs, dmi_boundary=config.dmi_boundary))
        initial = np.zeros(film.shape); initial[..., 2] = 1
        if config.seed == "skyrmion":
            initial = skyrmion_lattice(film, config.seed_radius_m, config.seed_wall_m)
        relaxed = film.relax(initial, maxiter=config.maxiter, tolerance_T=max(config.torque_tolerance_T, 1e-6))
        if relaxed.torque_T > config.torque_tolerance_T:
            relaxed = refine_equilibrium(film, relaxed.m, tolerance_T=config.torque_tolerance_T)
        summary.update(energy_J=relaxed.energy_J, torque_T=relaxed.torque_T,
                       converged=relaxed.converged, iterations=relaxed.iterations,
                       message=relaxed.message, topological_charge=film.topological_charge(relaxed.m),
                       geometry=dict(nx=film.nx, ny=film.ny, dx_m=film.dx, dy_m=film.dy, thickness_m=film.thickness),
                       material=asdict(film.material), field_T=list(config.field_T))
        np.save(output/"equilibrium.npy", relaxed.m)
        write_ovf(output/"equilibrium.ovf", relaxed.m, film.dx, film.dy, film.thickness)
        if not relaxed.converged or relaxed.torque_T > config.torque_tolerance_T:
            raise NumericalFailure("Static torque did not converge; spectra withheld")
        progress("eigenmodes")
        prepared = ModalResponse(film, relaxed.m, config.torque_tolerance_T)
        values, vectors, matrix = prepared.values, prepared.vectors, prepared.matrix
        residual = matrix@vectors-vectors*values
        scale = max(norm(matrix, "fro"), 1.)
        eigen_residual = float(np.max(np.linalg.norm(residual, axis=0))/scale)
        singular = svdvals(vectors)
        condition = float(singular[0]/singular[-1])
        # Conservative numeric sign margin, not a rigorous stability certificate
        # for the discretized physics or a neutral-mode error bound.
        # Retain a physical operator scale when large terms cancel near a
        # neutral point: the small assembled J alone underestimates roundoff.
        p = film.material
        field_scale = (np.linalg.norm(film.field_T)+2*abs(p.K)/p.Ms+MU0*p.Ms
                       +2*np.pi**2*p.A/p.Ms*(film.dx**-2+film.dy**-2)
                       +4*np.pi*abs(p.D)/p.Ms*(film.dx**-1+film.dy**-1))
        physical_scale = 4*p.gamma*(1+p.alpha)/(1+p.alpha**2)*field_scale*np.sqrt(len(values))
        margin = float(condition*(norm(residual, "fro")+100*np.finfo(float).eps*max(scale, physical_scale)))
        growth = float(values.real.max())
        stability = "unstable" if growth > margin else "uncertain" if growth >= -margin else "stable"
        summary.update(stability=stability, max_growth_rate_per_s=growth,
                       numerical_sign_margin_per_s=margin, eigenbasis_condition=condition,
                       max_relative_eigen_residual=eigen_residual, mode_count=len(values),
                       stability_is_rigorous_certificate=False)
        if not np.isfinite(margin) or eigen_residual > 1e-7 or stability != "stable":
            raise NumericalFailure("Eigen residual or stability check failed; spectra withheld")
        progress("frequency response")
        frequencies = np.linspace(config.fmin_Hz, config.fmax_Hz, config.points)
        response = prepared.response(frequencies, config.drive_T)
        amplitude = float(np.linalg.norm(response, axis=-1).max())
        summary.update(max_delta_m=amplitude, max_response_residual=float(prepared.last_response_residuals.max()),
                       max_basis_residual=prepared.last_basis_residual)
        if amplitude > .05:
            raise NumericalFailure("Predicted perturbation exceeds 0.05; reduce the drive before using linear response")
        power = film.absorbed_power(frequencies, response, config.drive_T)
        if not np.all(np.isfinite(power)):
            raise NumericalFailure("Nonfinite power; spectra withheld")
        order = np.argsort(values.imag)
        modes = np.einsum('...ci,...ik->k...c', prepared.basis, vectors.reshape(film.ny, film.nx, 2, -1))[order]
        values = values[order]
        np.savez_compressed(output/"modes.npz", eigenvalues=values, modes=modes)
        np.savez_compressed(output/"response.npz", frequencies_Hz=frequencies, delta_m=response,
                            absorbed_power_W=power, drive_T=config.drive_T)
        mean = response.mean(axis=(1, 2))
        np.savetxt(output/"response.csv", np.column_stack((frequencies, power, mean.real, mean.imag)),
                   delimiter=",", header="frequency_Hz,power_W,mx_real,my_real,mz_real,mx_imag,my_imag,mz_imag", comments="")
        np.savetxt(output/"modes.csv", np.column_stack((values.imag/(2*np.pi), values.real)),
                   delimiter=",", header="signed_frequency_Hz,growth_rate_per_s", comments="")
        progress("plots and exports")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(); ax.plot(frequencies/1e9, power)
        ax.set(xlabel="Frequency (GHz)", ylabel="Absorbed power (W)")
        fig.savefig(output/"spectrum.png", dpi=130); plt.close(fig)
        extent = [0, film.nx*film.dx*1e9, 0, film.ny*film.dy*1e9]
        fig, ax = plt.subplots(); im = ax.imshow(relaxed.m[..., 2], origin="lower", extent=extent, vmin=-1, vmax=1, cmap="RdBu_r")
        ax.set(xlabel="x (nm)", ylabel="y (nm)", title="Equilibrium mz"); fig.colorbar(im, ax=ax)
        fig.savefig(output/"equilibrium.png", dpi=130); plt.close(fig)
        visible = np.flatnonzero(values.imag > 0)
        if not len(visible):
            raise NumericalFailure("No positive-frequency mode found")
        selected = visible[0]
        fig, ax = plt.subplots(); im = ax.imshow(np.linalg.norm(modes[selected], axis=-1), origin="lower", extent=extent)
        ax.set(xlabel="x (nm)", ylabel="y (nm)", title=f"Lowest positive mode: {values[selected].imag/2/np.pi/1e9:.4g} GHz")
        fig.colorbar(im, ax=ax, label="Mode amplitude (arbitrary normalization)")
        fig.savefig(output/"mode.png", dpi=130); plt.close(fig)
        summary.update(status="succeeded", wall_s=time.perf_counter()-start)
        if platform.system() == "Linux":
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            summary.update(process_peak_rss_MiB=usage.ru_maxrss/1024, process_CPU_s=usage.ru_utime+usage.ru_stime)
        write_json(output/"summary.json", summary)
        manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.name in ARTIFACTS}
        write_json(output/"manifest.json", manifest)
        with zipfile.ZipFile(output/"results.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name in (*manifest, "manifest.json"):
                archive.write(output/name, name)
        progress("complete")
        return summary
    except Exception as error:
        # A partially computed response must not survive a failed check/export.
        for name in ARTIFACTS:
            if name not in ("configuration.json", "summary.json", "equilibrium.npy", "equilibrium.ovf"):
                (output/name).unlink(missing_ok=True)
        summary.update(status="failed", error=str(error), wall_s=time.perf_counter()-start)
        write_json(output/"summary.json", summary)
        raise
