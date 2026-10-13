import argparse
from pathlib import Path
import json
import numpy as np
from .model import Film, skyrmion_lattice

def main():
    parser = argparse.ArgumentParser(description='Periodic thin-film eigenmodes and driven response (SI)')
    parser.add_argument('--nx', type=int, default=12)
    parser.add_argument('--ny', type=int, default=12)
    parser.add_argument('--cell-nm', type=float, default=4)
    parser.add_argument('--thickness-nm', type=float, default=1)
    parser.add_argument('--field-t', type=float, default=0.1)
    parser.add_argument('--seed', choices=['skyrmion','uniform'], default='skyrmion')
    parser.add_argument('--fmin-ghz', type=float, default=0.1)
    parser.add_argument('--fmax-ghz', type=float, default=100)
    parser.add_argument('--points', type=int, default=101)
    parser.add_argument('--maxiter', type=int, default=2000)
    parser.add_argument('--output', type=Path, default=Path('results'))
    args = parser.parse_args()
    if args.points < 2 or not 0 <= args.fmin_ghz < args.fmax_ghz:
        parser.error('Require points >= 2 and 0 <= fmin < fmax')
    film = Film(args.nx, args.ny, args.cell_nm*1e-9, thickness=args.thickness_nm*1e-9, field_T=(0,0,args.field_t))
    if args.seed == 'skyrmion':
        initial = skyrmion_lattice(film)
    else:
        initial = np.zeros(film.shape)
        initial[...,2] = 1
    result = film.relax(initial, maxiter=args.maxiter)
    args.output.mkdir(parents=True, exist_ok=True)
    summary = dict(energy_J=result.energy_J, torque_T=result.torque_T,
                   converged=result.converged, iterations=result.iterations,
                   topological_charge=film.topological_charge(result.m), message=result.message,
                   geometry=dict(nx=film.nx, ny=film.ny, dx_m=film.dx, dy_m=film.dy, thickness_m=film.thickness),
                   material=vars(film.material), field_T=film.field_T.tolist())
    np.save(args.output/'equilibrium.npy', result.m)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    if not result.converged:
        raise SystemExit('Relaxation did not reach torque tolerance; equilibrium saved, spectrum not computed.')
    spectrum = film.modes(result.m)
    np.savez_compressed(args.output/'modes.npz', eigenvalues=spectrum.eigenvalues, modes=spectrum.modes)
    frequencies = np.linspace(args.fmin_ghz, args.fmax_ghz, args.points)*1e9
    drive = (1e-4,0,0)
    response = film.response(result.m, frequencies, drive)
    power = film.absorbed_power(frequencies, response, drive)
    np.savez_compressed(args.output/'response.npz', frequencies_Hz=frequencies, delta_m=response, absorbed_power_W=power, drive_T=drive)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(frequencies/1e9, power)
    ax.set(xlabel='Frequency (GHz)', ylabel='Absorbed power (W)')
    fig.savefig(args.output/'spectrum.png', dpi=150)
    plt.close(fig)
    print(f'Saved equilibrium, modes, response and spectrum to {args.output}')

if __name__ == '__main__':
    main()
