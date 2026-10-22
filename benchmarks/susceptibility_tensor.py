"""Independent uniform/finite-k Gilbert transfer tensor checks and plots."""
import argparse
from dataclasses import replace
import hashlib
import platform
from pathlib import Path

import numpy as np
import scipy

from spinfreq import Film, ModalResponse, SpatialProfile, susceptibility
from spinfreq.config import presets
from spinfreq.jobs import write_json
from spinfreq.model import MU0


def analytic(config, frequencies, k):
    p = config.material
    h = config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms+2*p.A*k*k/p.Ms
    n = -np.expm1(-abs(k)*config.thickness_m)/(abs(k)*config.thickness_m) if k else 1.
    hx, hy = h+MU0*p.Ms*(1-n), h
    rate = p.gamma/(1+p.alpha**2)
    matrix = rate*np.array([[-p.alpha*hx, -hy], [hx, -p.alpha*hy]])
    force = rate*np.array([[p.alpha, 1], [-1, p.alpha]])
    tensor = np.zeros((len(frequencies), 3, 3), complex)
    for index, f in enumerate(frequencies):
        tensor[index, :2, :2] = np.linalg.solve(2j*np.pi*f*np.eye(2)-matrix, force)
    return tensor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/tensor-validation'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(9, 6), constrained_layout=True)
    rows = []
    config = replace(presets()['periodic-fmr'], nx=8, ny=2, dx_m=8e-9, dy_m=8e-9,
                     fmin_Hz=0., fmax_Hz=150e9, points=501)
    film = Film(nx=config.nx, ny=config.ny, dx=config.dx_m, dy=config.dy_m, thickness=config.thickness_m,
                material=config.material, field_T=config.field_T)
    m = np.zeros(film.shape); m[..., 2] = 1
    prepared = ModalResponse(film, m)
    frequencies = np.linspace(config.fmin_Hz, config.fmax_Hz, config.points)
    for row, k in enumerate([0., 2*np.pi/(film.nx*film.dx)]):
        source = SpatialProfile('plane_wave', k_rad_m=(float(k), 0)).evaluate(film.nx, film.ny, film.dx, film.dy)
        data = susceptibility(prepared, frequencies, source, source[None])
        expected = analytic(config, frequencies, k)
        computed = data['tensor_per_T'][:, 0]
        reconstructed = np.einsum('fn,npij->fpij', 1/(2j*np.pi*frequencies[:, None]-data['eigenvalues_per_s']), data['residues_per_T_s'])
        error = float(np.linalg.norm(computed-expected)/np.linalg.norm(expected))
        residue_error = float(np.linalg.norm(reconstructed-data['tensor_per_T'])/np.linalg.norm(data['tensor_per_T']))
        rows.append({'case': 'uniform' if not k else 'finite-k', 'k_rad_m': k,
                     'tensor_relative_error': error, 'residue_reconstruction_relative_error': residue_error,
                     'max_response_residual': float(data['response_residuals'].max())})
        for col, (i, j) in enumerate([(0, 0), (0, 1)]):
            ax = axes[row, col]
            ax.plot(frequencies/1e9, computed[:, i, j].imag, label='SpinFreq imaginary')
            ax.plot(frequencies[::10]/1e9, expected[::10, i, j].imag, 'o', ms=2, label='Analytical Gilbert')
            ax.set(xlabel='Frequency (GHz)', ylabel='Transfer (1/T)', title=f'{rows[-1]["case"]}: {"xyz"[i]} from {"xyz"[j]}')
        np.savez_compressed(args.output/f'{rows[-1]["case"]}.npz', frequencies_Hz=frequencies, computed_per_T=computed, analytical_per_T=expected)
    axes[0, 0].legend(fontsize=8)
    fig.savefig(args.output/'tensor-validation.png', dpi=150)
    fig.savefig(args.output/'tensor-validation.pdf')
    plt.close(fig)
    sources = {name: hashlib.sha256((Path(__file__).resolve().parents[1]/'spinfreq'/name).read_bytes()).hexdigest()
               for name in ['model.py', 'linear_response.py', 'profiles.py', 'susceptibility.py']}
    report = {'cases': rows, 'configuration': config.to_dict(), 'source_sha256': sources,
              'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
              'benchmark_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Independent analytical linear periodic uniform/finite-k tensors; not temporal-code or nonlinear validation.'}
    write_json(args.output/'report.json', report)
    if args.check and any(r['tensor_relative_error'] > 1e-9 or r['residue_reconstruction_relative_error'] > 1e-9 or r['max_response_residual'] > 1e-7 for r in rows):
        raise SystemExit('Tensor validation failed')
    print(rows)


if __name__ == '__main__':
    main()
