"""Measure prepared-modal versus direct dense response on the same problem.

Reports CPU and wall time for one measured sweep, including preparation.
This is an implementation/performance comparison, not external physics data.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import time

import numpy as np
import scipy

from spinfreq import ConfinedFilm,Material,ModalResponse,lattice_seed,refine_equilibrium


def measured(function):
    cpu=time.process_time();wall=time.perf_counter();result=function()
    return result,dict(cpu_s=time.process_time()-cpu,wall_s=time.perf_counter()-wall)


def run(output,points=201):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    material=Material(Ms=580e3,A=15e-12,D=.003,K=.6e6,alpha=.01,gamma=1.7595e11)
    film=ConfinedFilm(nx=20,ny=20,dx=2e-9,thickness=1e-9,material=material,field_T=(0,0,0),dmi_boundary='bond')
    state=refine_equilibrium(film,film.relax(lattice_seed(film),maxiter=10000,tolerance_T=1e-7).m,tolerance_T=1e-9)
    if not state.converged:raise RuntimeError('Equilibrium failed')
    frequencies=np.linspace(1e9,45e9,points);drive=(0,0,1e-6)
    prepared,prepare_timing=measured(lambda:ModalResponse(film,state.m))
    modal,modal_timing=measured(lambda:prepared.response(frequencies,drive))
    direct,direct_timing=measured(lambda:film.response(state.m,frequencies,drive))
    error=float(np.linalg.norm(modal-direct)/np.linalg.norm(direct))
    summary=dict(material=asdict(material),cells=[20,20,1],cell_nm=[2,2,1],points=points,
        frequency_GHz=[1,45],drive_T=list(drive),timings=dict(preparation=prepare_timing,modal_queries=modal_timing,direct_queries=direct_timing),
        direct_over_prepared_total_CPU_ratio=direct_timing['cpu_s']/(prepare_timing['cpu_s']+modal_timing['cpu_s']),
        direct_over_reused_query_CPU_ratio=direct_timing['cpu_s']/modal_timing['cpu_s'],
        relative_full_field_difference=error,max_true_residual=float(prepared.last_response_residuals.max()),
        all_executed_gates_passed=bool(error<1e-7 and prepared.last_response_residuals.max()<1e-7),
        environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
        limitations=['One measured sweep on this cloud CPU with one BLAS thread; timings are not a general speed guarantee.',
            'Both methods remain dense; all-mode preparation is not a matrix-free large-array solver.'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    np.savetxt(output/'mean_response.csv',np.column_stack([frequencies/1e9,modal.mean(axis=(1,2)).real,
        modal.mean(axis=(1,2)).imag,direct.mean(axis=(1,2)).real,direct.mean(axis=(1,2)).imag]),
        delimiter=',',comments='',header='frequency_GHz,modal_re_x,modal_re_y,modal_re_z,modal_im_x,modal_im_y,modal_im_z,direct_re_x,direct_re_y,direct_re_z,direct_im_x,direct_im_y,direct_im_z')
    print(json.dumps(summary,indent=2));return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('validation/response_reuse'))
    parser.add_argument('--points',type=int,default=201)
    parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.points<2:parser.error('At least two frequency points are required')
    result=run(args.output,args.points)
    if args.check and not result['all_executed_gates_passed']:raise SystemExit('Response reuse comparison failed')
