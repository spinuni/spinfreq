"""Command-line adapter for the shared reproducible job runner."""
import argparse
import json
from pathlib import Path
import sys

from .config import JobConfig, presets
from .jobs import run_job, write_json


def main():
    parser = argparse.ArgumentParser(description='Thin-film small-signal modes and driven response (SI)')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--config', type=Path, help='Versioned SI JSON configuration')
    source.add_argument('--preset', choices=list(presets()))
    parser.add_argument('--list-presets', action='store_true')
    parser.add_argument('--write-config', type=Path, help='Write resolved configuration and exit')
    parser.add_argument('--nx', type=int, default=12)
    parser.add_argument('--ny', type=int, default=12)
    parser.add_argument('--cell-nm', type=float, default=4)
    parser.add_argument('--thickness-nm', type=float, default=1)
    parser.add_argument('--field-t', type=float, default=.1)
    parser.add_argument('--seed', choices=['skyrmion', 'uniform'], default='skyrmion')
    parser.add_argument('--fmin-ghz', type=float, default=.1)
    parser.add_argument('--fmax-ghz', type=float, default=100)
    parser.add_argument('--points', type=int, default=101)
    parser.add_argument('--maxiter', type=int, default=2000)
    parser.add_argument('--output', type=Path, default=Path('results/run'))
    args = parser.parse_args()
    if args.list_presets:
        print(json.dumps({name: config.to_dict() for name, config in presets().items()}, indent=2))
        return
    legacy = ('--nx', '--ny', '--cell-nm', '--thickness-nm', '--field-t', '--seed', '--fmin-ghz', '--fmax-ghz', '--points', '--maxiter')
    if (args.config or args.preset) and any(arg.split('=')[0] in legacy for arg in sys.argv[1:]):
        parser.error('Edit the JSON to change a config/preset; do not combine it with legacy geometry flags')
    try:
        if args.config:
            config = JobConfig.load(args.config)
        elif args.preset:
            config = presets()[args.preset]
        else:
            width = min(args.nx, args.ny)*args.cell_nm*1e-9
            config = JobConfig(nx=args.nx, ny=args.ny, dx_m=args.cell_nm*1e-9, dy_m=args.cell_nm*1e-9,
                               thickness_m=args.thickness_nm*1e-9, field_T=(0, 0, args.field_t), seed=args.seed,
                               seed_radius_m=.23*width, seed_wall_m=.23*width/3,
                               fmin_Hz=args.fmin_ghz*1e9, fmax_Hz=args.fmax_ghz*1e9,
                               points=args.points, maxiter=args.maxiter)
        if args.write_config:
            write_json(args.write_config, config.to_dict())
            return
        summary = run_job(config, args.output)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(summary, indent=2))
    print(f'Saved reproducible results to {args.output}')


if __name__ == '__main__':
    main()
