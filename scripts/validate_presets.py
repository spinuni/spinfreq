"""Execute all first-release examples through the installed CLI, outside source.

Reports timings and process peak RSS; numerical targets are independent analytic
FMR frequencies and archived OOMMF skyrmion poles. Not a new continuum claim.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from spinfreq.config import presets
from spinfreq.jobs import write_json
from spinfreq.model import MU0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('results/release-presets'))
    parser.add_argument('--reference', type=Path, default=Path(__file__).resolve().parents[1]/'validation/skyrmion_temporal/field_0mT/summary.json')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    reference = json.loads(args.reference.read_text())
    report = {'scope': 'First-release example regression, not thickness/continuum qualification', 'presets': {}}
    environment = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', MPLBACKEND='Agg')
    for name, config in presets().items():
        destination = output/name
        request = output/(name+'.json'); write_json(request, config.to_dict())
        with tempfile.TemporaryDirectory() as cwd:
            with (output/(name+'.log')).open('w') as log:
                subprocess.run([sys.executable, '-m', 'spinfreq.cli', '--config', str(request), '--output', str(destination)],
                               cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        summary = json.loads((destination/'summary.json').read_text())
        values = np.load(destination/'modes.npz')['eigenvalues']
        positive = values[values.imag > 0].imag/(2*np.pi)
        p = config.material
        if name == 'periodic-fmr':
            targets = [p.gamma/(1+p.alpha**2)*(config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms)/(2*np.pi)]
            tolerance = 1e-10
        elif name == 'prism-fmr':
            from spinfreq import ConfinedFilm
            film = ConfinedFilm(nx=1, ny=1, dx=config.dx_m, dy=config.dy_m, thickness=config.thickness_m, material=p)
            n = film.demag_self_tensor
            b = config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms*n[2]
            hx, hy = b+MU0*p.Ms*n[0], b+MU0*p.Ms*n[1]
            factor = p.gamma/(1+p.alpha**2)
            targets = [factor*np.sqrt((1+p.alpha**2)*hx*hy-p.alpha**2*(hx+hy)**2/4)/(2*np.pi)]
            tolerance = 1e-10
        else:
            targets = [mode['OOMMF_fitted_frequency_GHz']*1e9 for mode in reference['modes']]
            tolerance = .002
        errors = [float(min(abs(positive-target))/target) for target in targets]
        passed = (summary['status'] == 'succeeded' and summary['stability'] == 'stable'
                  and max(errors) < tolerance and summary['max_response_residual'] < 1e-7
                  and summary['max_delta_m'] < .05 and summary['wall_s'] < 120
                  and summary['process_peak_rss_MiB'] < 1024)
        report['presets'][name] = {key: summary[key] for key in ('wall_s', 'process_CPU_s', 'process_peak_rss_MiB', 'torque_T', 'max_delta_m', 'max_response_residual', 'configuration_sha256', 'package_version')}
        report['presets'][name].update(target_frequencies_Hz=targets, relative_frequency_errors=errors,
                                      frequency_error_limit=tolerance, passed=bool(passed))
    report['all_executed_gates_passed'] = all(r['passed'] for r in report['presets'].values())
    write_json(output/'summary.json', report)
    print(json.dumps(report, indent=2))
    if not report['all_executed_gates_passed']:
        raise SystemExit('Preset qualification failed')


if __name__ == '__main__':
    main()
