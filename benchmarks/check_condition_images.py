"""Image convergence of the provisional pinned-strip hypothesis."""
import argparse
import json
from pathlib import Path
import numpy as np
from liu2024_conditions import CASES,make_film
from liu2024_fig2 import branch_values
from spinfreq import refine_equilibrium


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=CASES,default='pinned2_w45')
    parser.add_argument('--source',type=Path,default=Path('validation/liu2024/conditions/midpoint'))
    parser.add_argument('--images',type=int,default=64)
    args=parser.parse_args()
    records=json.loads((args.source/'summary_1nm.json').read_text())
    baseline=next(r for r in records if r['case']==args.case)
    raw=np.load(args.source/f'{args.case}_1nm.npz')
    film=make_film(CASES[args.case],1,args.images)
    refined=refine_equilibrium(film,raw['m'],tolerance_T=1e-9)
    if not refined.converged: raise RuntimeError('Image-check equilibrium did not converge')
    changes=[]
    for reduced in [0,.5,1]:
        spectrum=film.bloch_modes(refined.m,reduced*np.pi/film.period_m,count=12,target_Hz=15e9)
        actual=branch_values(spectrum)
        old=next(row for row in baseline['frequency_samples'] if np.isclose(row['reduced_ka_over_pi'],reduced))
        differences={band:abs(actual[band+'_GHz']-old[band+'_GHz']) for band in ['gyration','breathing','upper_branch']}
        changes.append(dict(reduced_ka_over_pi=reduced,changes_GHz=differences,max_growth_per_s=actual['maximum_growth_per_s']))
    result=dict(case=args.case,baseline_images=baseline['images'],refined_images=args.images,
                residual_torque_T=refined.torque_T,checks=changes,
                max_frequency_change_GHz=max(v for row in changes for v in row['changes_GHz'].values()))
    (args.source/'image_convergence.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
