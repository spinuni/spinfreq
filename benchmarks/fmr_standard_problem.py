"""Baker et al. FMR: linear ringdown versus published OOMMF reference data.

This is a single-z-layer approximation of the authors' two-layer problem,
not an exact reproduction of its 3D discretization. No OOMMF installation is
needed: --fetch-reference retrieves two hash-checked files from a pinned commit.
"""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import scipy
from scipy.linalg import eig, solve
from scipy.optimize import least_squares
from scipy.signal import find_peaks

from spinfreq import ConfinedFilm, Material, refine_equilibrium
from spinfreq.model import MU0


REFERENCE_COMMIT = 'c7051885417864508bfe6bb3511adad361395b87'
REFERENCE_REPOSITORY = 'https://github.com/fangohr/micromagnetic-standard-problem-ferromagnetic-resonance'
REFERENCE_BASE = (f'https://raw.githubusercontent.com/fangohr/'
                  f'micromagnetic-standard-problem-ferromagnetic-resonance/{REFERENCE_COMMIT}/'
                  'micromagnetic_simulation_data/reference_data/oommf/')
REFERENCE_HASHES = {
    'dynamic_txyz.txt': '4e45feb9b7e335d44c8c95e979f53c40c091fb1d7a25e2f5a9eb66fc5969d35e',
    'mys.npy': 'f3956266eb289c198c818e48eb8eb7fe899d5a7162fc5c1a6df5c2de51694dca',
}


def reference_files(directory, fetch=False):
    directory = Path(directory)
    for name, expected in REFERENCE_HASHES.items():
        path = directory / name
        if not path.exists():
            if not fetch:
                raise FileNotFoundError(f'{path}: supply the authors\' reference directory or --fetch-reference')
            with urlopen(REFERENCE_BASE + name, timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f'Reference checksum mismatch: {name}')
            directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Reference checksum mismatch: {path}')
    return directory


def modal_assurance(a, b):
    """Phase- and amplitude-independent squared overlap (MAC)."""
    a, b = np.ravel(a), np.ravel(b)
    denominator = np.vdot(a, a).real * np.vdot(b, b).real
    return float(abs(np.vdot(a, b))**2 / denominator) if denominator > 0 else 0.0


def linear_ringdown(matrix, initial_coordinates, observation, times_s):
    """Observe exp(J t) u0 using all right eigenvectors and their inverse.

    The inverse, rather than a Hermitian transpose, matters for damped,
    nonnormal LLG matrices. observation has shape (number of signals, 2N).
    """
    values, vectors = eig(matrix)
    coefficients = solve(vectors, initial_coordinates)
    signals = ((observation @ vectors) * coefficients) @ np.exp(values[:, None] * times_s)
    if np.max(abs(signals.imag)) > 1e-9 * max(np.max(abs(signals.real)), 1e-20):
        raise RuntimeError('Linear ringdown failed its real-signal check')
    return signals.real, values, vectors, coefficients


def strongest_peaks(frequencies, power, count=2):
    indices, _ = find_peaks(power)
    indices = indices[(frequencies[indices] > 1e9) & (frequencies[indices] < 20e9)]
    if len(indices) < count:
        raise RuntimeError('Too few resolved FMR reference peaks')
    return np.sort(indices[np.argsort(power[indices])[-count:]])


def fit_reference_poles(times, mean_y, guesses_GHz):
    """Three damped sinusoids with linear offset/quadrature coefficients.

    Two visible FMR poles are the comparison targets; the third accounts for
    the weaker ~13.9 GHz mode. Repeat the fit after discarding 0, .1, .3 and
    .5 ns. This sensitivity study is not a statistical confidence interval.
    """
    records=[]
    for start_ns in [0., .1, .3, .5]:
        keep=(times >= start_ns*1e-9) & (times <= 8e-9)
        t=times[keep]/1e-9; y=mean_y[keep]
        def residual(parameters):
            waves=np.exp(-t[:,None]*parameters[3:])*np.exp(2j*np.pi*t[:,None]*parameters[:3])
            design=np.column_stack([np.ones(len(t)),waves.real,waves.imag])
            coefficients=np.linalg.lstsq(design,y,rcond=None)[0]
            return (design@coefficients-y)/np.std(y)
        result=least_squares(residual,np.r_[guesses_GHz,[.65,.7,.75]],
            bounds=(np.r_[guesses_GHz-.35,[.01,.01,.01]],np.r_[guesses_GHz+.35,[3.,3.,3.]]),
            xtol=1e-12,gtol=1e-12,ftol=1e-12)
        if not result.success:
            raise RuntimeError('Reference damped-pole fit failed')
        records.append(dict(start_ns=start_ns,stop_ns=8.,
            frequencies_GHz=result.x[:3].tolist(),
            decay_rates_per_s=(result.x[3:]*1e9).tolist(),
            pole_FWHM_GHz=(result.x[3:]/np.pi).tolist(),
            residual_RMS_over_signal_std=float(np.sqrt(np.mean(residual(result.x)**2)))))
    return records


def run(output, reference_directory, cells=(24, 30, 40), fetch=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    reference = reference_files(reference_directory, fetch)
    table = np.loadtxt(reference / 'dynamic_txyz.txt')
    spatial_y = np.load(reference / 'mys.npy', mmap_mode='r', allow_pickle=False)
    times = table[:, 0]
    dt = float(np.mean(np.diff(times)))
    if not np.allclose(np.diff(times), dt, rtol=1e-8, atol=1e-20):
        raise ValueError('Reference sampling is not uniform')
    frequencies = np.fft.rfftfreq(len(times), dt)
    reference_fft = np.fft.rfft(table[:, 2] - table[:, 2].mean())
    reference_power = abs(reference_fft)**2
    peaks = strongest_peaks(frequencies, reference_power)
    reference_fits=fit_reference_poles(times,table[:,2],frequencies[strongest_peaks(frequencies,reference_power,3)]/1e9)
    # Same rectangular time window as the authors; z layers already averaged
    # in their .npy files. Spatial ordering follows their OOMMF postprocessor.
    reference_maps = np.fft.rfft(spatial_y - spatial_y.mean(axis=0), axis=0)[peaks]
    material = Material(Ms=8e5, A=13e-12, D=0, K=0, alpha=.008,
                        gamma=2.210173e5 / MU0)
    old_direction = np.array([.81345856316858023, .58162287266553481, 0])
    new_direction = np.array([.81923192051904048, .57346234436332832, 0])
    records, traces, spectra, maps = [], [], [], []
    for n in cells:
        start = time.perf_counter()
        film = ConfinedFilm(nx=n, ny=n, dx=120e-9/n, thickness=10e-9,
                            material=material, field_T=MU0*8e4*old_direction)
        initial = np.broadcast_to(old_direction, film.shape).copy()
        relaxed_old = film.relax(initial, tolerance_T=1e-7)
        relaxed_old = refine_equilibrium(film, relaxed_old.m, tolerance_T=1e-9)
        film.field_T = MU0*8e4*new_direction
        relaxed = film.relax(relaxed_old.m, tolerance_T=1e-7)
        relaxed = refine_equilibrium(film, relaxed.m, tolerance_T=1e-9)
        if not (relaxed_old.converged and relaxed.converged):
            raise RuntimeError(f'FMR equilibrium did not converge on {n}x{n} mesh')
        matrix, basis = film.linearize(relaxed.m, equilibrium_tolerance_T=1e-9)
        assembly_s = time.perf_counter() - start
        u0 = np.einsum('...ci,...c->...i', basis, relaxed_old.m-relaxed.m).ravel()
        observation = basis[..., 1, :].reshape(1, -1)/(n*n)
        start = time.perf_counter()
        signal, values, vectors, coefficients = linear_ringdown(matrix, u0, observation, times)
        modal_s = time.perf_counter()-start
        signal = signal[0] + relaxed.m[..., 1].mean()
        power = abs(np.fft.rfft(signal-signal.mean()))**2
        residuals = np.linalg.norm(matrix@vectors-vectors*values, axis=0) / np.linalg.norm(vectors, axis=0)
        positive = np.flatnonzero(values.imag > 0)
        comparisons, cell_maps = [], []
        for number,(index, reference_map) in enumerate(zip(peaks, reference_maps)):
            target = frequencies[index]
            mode = positive[np.argmin(abs(values[positive].imag/(2*np.pi)-target))]
            field_y = np.einsum('...i,...i->...', basis[..., 1, :], vectors[:, mode].reshape(n, n, 2))
            # Interpolate complex mode components to reference cell centers.
            # No rotation, reflection, translation or phase fit is applied.
            from scipy.interpolate import RegularGridInterpolator
            xy = (np.arange(n)+.5)/n
            y, x = np.meshgrid((np.arange(24)+.5)/24, (np.arange(24)+.5)/24, indexing='ij')
            interpolated = RegularGridInterpolator((xy, xy), field_y, bounds_error=False,
                                                   fill_value=None)(np.stack((y, x), axis=-1))
            frequency = float(values[mode].imag/(2*np.pi))
            comparisons.append(dict(reference_FFT_peak_GHz=float(target/1e9),
                eigenfrequency_GHz=frequency/1e9, relative_peak_error=abs(frequency/target-1),
                reference_fitted_frequency_GHz=reference_fits[0]['frequencies_GHz'][number],
                relative_fitted_frequency_error=abs(frequency/1e9/reference_fits[0]['frequencies_GHz'][number]-1),
                y_component_MAC=modal_assurance(interpolated, reference_map),
                pole_FWHM_GHz=float(-values[mode].real/np.pi/1e9),
                reference_fitted_FWHM_GHz=reference_fits[0]['pole_FWHM_GHz'][number],
                relative_fitted_FWHM_error=abs(-values[mode].real/np.pi/1e9/reference_fits[0]['pole_FWHM_GHz'][number]-1),
                eigen_absolute_residual_per_s=float(residuals[mode])))
            cell_maps.append(interpolated)
        records.append(dict(nx=n, ny=n, cell_nm=120/n, thickness_nm=10,
            torque_T=relaxed.torque_T, max_growth_rate_per_s=float(values.real.max()),
            max_initial_tangent_amplitude=float(np.linalg.norm(u0.reshape(n,n,2),axis=-1).max()),
            real_matrix_MiB=matrix.nbytes/2**20, equilibrium_and_assembly_s=assembly_s,
            eigendecomposition_and_ringdown_s=modal_s,
            mean_my_equilibrium=float(relaxed.m[...,1].mean()), comparisons=comparisons))
        traces.append(signal); spectra.append(power); maps.append(cell_maps)
        print(json.dumps(records[-1]), flush=True)
    # These are proposed project gates, not tolerances specified by the paper.
    fine_change = [abs(a['eigenfrequency_GHz']/b['eigenfrequency_GHz']-1)
                   for a,b in zip(records[-1]['comparisons'], records[-2]['comparisons'])] if len(records)>1 else None
    fit_width_sensitivity=[max(abs(r['pole_FWHM_GHz'][i]/reference_fits[0]['pole_FWHM_GHz'][i]-1) for r in reference_fits)
                           for i in range(2)]
    linewidth_passed=bool(all(c['relative_fitted_FWHM_error']<.05 for c in records[-1]['comparisons'])
        and max(fit_width_sensitivity)<.05 and max(r['residual_RMS_over_signal_std'] for r in reference_fits)<.01)
    summary = dict(paper_DOI='10.1016/j.jmmm.2016.08.009', reference_repository=REFERENCE_REPOSITORY,
        reference_commit=REFERENCE_COMMIT, reference_sha256=REFERENCE_HASHES,
        reference_solver='OOMMF 1.2 alpha 6 (per author repository)',
        reference_geometry_nm=[120,120,10], reference_cell_nm=[5,5,5],
        spinfreq_z_cells=1, reference_z_cells=2,
        reference_FFT_spacing_GHz=float((frequencies[1]-frequencies[0])/1e9),
        reference_window='rectangular, 4000 samples at 5 ps, times 5 ps to 20 ns',
        protocol='All-mode linearized ringdown after the specified small in-plane field rotation; no nonlinear time integration',
        H_A_per_m=8e4, old_field_direction=old_direction.tolist(), new_field_direction=new_direction.tolist(),
        material=vars(material), meshes=records,
        reference_pole_fit=dict(method='Three damped sinusoids, variable projection; frequency bounds FFT peak +/- 0.35 GHz, decay bounds 0.01 to 3 per ns',
            runs=reference_fits,first_two_linewidth_relative_window_sensitivity=fit_width_sensitivity,
            interpretation='Window sensitivity is empirical; these are not statistical confidence intervals'),
        finest_pair_relative_frequency_change=fine_change,
        proposed_gate_frequency_error_below_1_percent=bool(all(c['relative_peak_error']<.01 for c in records[-1]['comparisons'])),
        proposed_gate_finest_pair_change_below_half_percent=bool(fine_change is not None and max(fine_change)<.005),
        proposed_gate_y_MAC_above_095=bool(all(c['y_component_MAC']>.95 for c in records[-1]['comparisons'])),
        proposed_gate_fitted_frequency_error_below_1_percent=bool(all(c['relative_fitted_frequency_error']<.01 for c in records[-1]['comparisons'])),
        proposed_gate_fitted_linewidth_error_and_window_sensitivity_below_5_percent=linewidth_passed,
        exact_3D_standard_problem_validated=False,
        linewidth_validated=linewidth_passed,
        linewidth_scope='Two visible low FMR poles, using a three-sinusoid fit to the published OOMMF mean-my trace',
        limitations=['Uniform-through-thickness approximation: no z-dependent eigenmodes.',
            'Raw peak positions have 0.05 GHz FFT bins; sub-bin frequencies use a three-pole damped-trace fit.',
            'MAC compares the y component at a finite-window reference FFT peak, not full-vector eigenmodes.',
            'Fitted linewidths have empirical window sensitivity, not statistical confidence bounds; higher modes are not validated.',
            'Nmag data are available upstream but are not compared in this run.'],
        runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                     platform=platform.platform()))
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    np.savetxt(output/'ringdown.csv', np.column_stack([times/1e-9,table[:,2],*traces]), delimiter=',',
               header='time_ns,OOMMF_mean_my,'+','.join(f'spinfreq_{n}x{n}_mean_my' for n in cells), comments='')
    keep=frequencies<=20e9
    np.savetxt(output/'spectra.csv', np.column_stack([frequencies[keep]/1e9,reference_power[keep],*[s[keep] for s in spectra]]),
               delimiter=',',header='frequency_GHz,OOMMF_FFT_power,'+','.join(f'spinfreq_{n}x{n}_FFT_power' for n in cells),comments='')
    make_plots(output,times,table[:,2],traces,frequencies,reference_power,spectra,reference_maps,maps,cells)
    return summary


def make_plots(output,times,reference,traces,frequencies,reference_power,spectra,reference_maps,maps,cells):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].plot(times/1e-9,reference-reference[-1],label='Published OOMMF (2 z layers)',color='black',lw=2)
    for n,trace in zip(cells,traces):
        axes[0].plot(times/1e-9,trace-trace[-1],label=f'spinfreq {n}×{n} (1 z layer)',alpha=.8)
    axes[0].set(xlim=(0,2.5),xlabel='Time (ns)',ylabel=r'$\langle m_y\rangle-\langle m_y\rangle_{20\,ns}$')
    axes[0].legend(fontsize=8)
    axes[1].semilogy(frequencies/1e9,reference_power/reference_power.max(),label='Published OOMMF',color='black',lw=2)
    for n,spectrum in zip(cells,spectra):
        axes[1].semilogy(frequencies/1e9,spectrum/spectrum.max(),label=f'spinfreq {n}×{n}')
    axes[1].set(xlim=(6,15),ylim=(1e-5,1.2),xlabel='Frequency (GHz)',ylabel='Normalized rectangular-window FFT power')
    axes[1].legend(fontsize=8);fig.tight_layout()
    for extension in ['png','pdf']:fig.savefig(output/f'comparison.{extension}',dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(8,7),layout='constrained')
    for column in range(2):
        for row,field in enumerate([reference_maps[column],maps[-1][column]]):
            image=axes[row,column].imshow(abs(field)/abs(field).max(),origin='lower',extent=(0,120,0,120),vmin=0,vmax=1)
            axes[row,column].set(xlabel='x (nm)',ylabel='y (nm)')
            axes[row,column].set_title(f'{"OOMMF FFT" if row==0 else "spinfreq eigenmode"}, peak {column+1}',fontsize=11)
    fig.colorbar(image,ax=list(axes.flat),label='Normalized |δmy|',shrink=.7)
    for extension in ['png','pdf']:fig.savefig(output/f'mode_amplitudes.{extension}',dpi=180,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-directory',type=Path,default=Path('results/reference/baker2017/oommf'))
    parser.add_argument('--fetch-reference',action='store_true')
    parser.add_argument('--check',action='store_true',help='Exit with an error if any proposed FMR acceptance gate fails')
    parser.add_argument('--cells',type=int,nargs='+',default=[24,30,40])
    parser.add_argument('--output',type=Path,default=Path('validation/fmr_standard_problem'))
    args=parser.parse_args()
    if any(n<3 or n>64 for n in args.cells):parser.error('Require 3 <= cells <= 64 (dense confined solver cap)')
    if args.cells!=sorted(set(args.cells)):parser.error('cells must increase strictly')
    summary=run(args.output,args.reference_directory,args.cells,args.fetch_reference)
    if args.check:
        failed=[key for key,value in summary.items() if key.startswith('proposed_gate_') and not value]
        if failed:raise SystemExit('FMR acceptance gates failed: '+', '.join(failed))
