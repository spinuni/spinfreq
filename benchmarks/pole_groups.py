"""Check grouped transfer reconstruction on a symmetric periodic film."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from spinfreq import Film, Material, ModalResponse, group_poles, grouped_response, susceptibility


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    film = Film(nx=4, ny=4, dx=8e-9, thickness=1e-9,
                material=Material(D=0), field_T=(0, 0, .1))
    m = np.zeros(film.shape); m[..., 2] = 1
    source = np.zeros(m.shape[:2]); source[0, 0] = 1
    prepared = ModalResponse(film, m)
    frequencies = np.linspace(0, 180e9, 401)
    data = susceptibility(prepared, frequencies, source, source[None])
    grouping = group_poles(prepared.values, data['residues_per_T_s'])
    reconstructed = sum(response for _, response in grouped_response(frequencies, prepared.values, data['residues_per_T_s'], grouping))
    error = float(np.linalg.norm(reconstructed-data['tensor_per_T'])/np.linalg.norm(data['tensor_per_T']))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    ax.plot(frequencies/1e9, data['tensor_per_T'][:, 0, 0, 0].imag, label='Full tensor')
    ax.plot(frequencies[::8]/1e9, reconstructed[::8, 0, 0, 0].imag, 'o', ms=3, label='Summed exact group responses')
    ax.set(xlabel='Frequency (GHz)', ylabel='Imaginary x-from-x transfer (1/T)', title='Single-cell source/probe in a periodic 4 × 4 film')
    ax.legend()
    fig.savefig(args.output/'group-reconstruction.png', dpi=150)
    fig.savefig(args.output/'group-reconstruction.pdf')
    plt.close(fig)
    report = {'schema_version': 1, 'python': platform.python_version(), 'numpy': np.__version__,
              'scipy': scipy.__version__, 'relative_tensor_reconstruction_error': error,
              'max_response_residual': float(data['response_residuals'].max()),
              'mode_count': len(prepared.values), 'group_count': len(grouping['groups']),
              'groups': grouping['groups'],
              'geometry': {'nx': 4, 'ny': 4, 'dx_m': 8e-9, 'dy_m': 8e-9, 'thickness_m': 1e-9},
              'material': vars(film.material), 'field_T': [0., 0., .1],
              'frequencies_Hz': {'min': 0., 'max': 180e9, 'points': 401},
              'source_and_probe': 'one nonzero cell at iy=0, ix=0; amplitude one',
              'atol_Hz': grouping['atol_Hz'], 'rtol': grouping['rtol'],
              'source_sha256': {name: hashlib.sha256((Path(__file__).resolve().parents[1]/'spinfreq'/name).read_bytes()).hexdigest()
                                for name in ['model.py', 'linear_response.py', 'profiles.py', 'susceptibility.py', 'pole_groups.py']},
              'benchmark_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Algebraic reconstruction of the same discrete linear operator; not independent temporal or continuum validation.'}
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if args.check and (error > 1e-9 or report['max_response_residual'] > 1e-7 or not any(g['count'] > 1 for g in grouping['groups'])):
        raise SystemExit('Grouped reconstruction failed')
    print(f'{len(prepared.values)} signed modes, {len(grouping["groups"])} groups; reconstruction relative error {error:.3g}')


if __name__ == '__main__':
    main()
