"""Diagnostic open-end chains; not a paper-resolution Fig.2 reproduction."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.linalg import lu_factor,lu_solve
from scipy.sparse.linalg import LinearOperator,eigs
from spinfreq import ConfinedFilm,lattice_seed
from liu2024 import paper_material


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('validation/liu2024/fig2/finite_chain_diagnostic.json'))
    args=parser.parse_args()
    records=[]
    for count in (3,5):
        film=ConfinedFilm(nx=20*count,ny=20,dx=2e-9,material=paper_material(),field_T=(0,0,0))
        relaxed=film.relax(lattice_seed(film,columns=count),maxiter=8000)
        if not relaxed.converged: raise RuntimeError('Finite-chain relaxation failed')
        matrix,_=film.linearize(relaxed.m)
        n=len(matrix);shift=15e9*2j*np.pi
        factors=lu_factor(matrix-shift*np.eye(n))
        inverse=LinearOperator((n,n),matvec=lambda v:lu_solve(factors,v),dtype=complex)
        values,vectors=eigs(matrix,k=6*count,sigma=shift,OPinv=inverse,v0=np.random.default_rng(17).normal(size=n))
        residuals=np.linalg.norm(matrix@vectors-vectors*values,axis=0)/(np.linalg.norm(matrix,ord=np.inf)+abs(values))
        if residuals.max()>1e-8: raise RuntimeError('Finite-chain eigenvalue residual check failed')
        f=np.sort(values.imag/(2*np.pi*1e9))
        breathing=f[(f>8)&(f<25)]
        record=dict(columns=count,cell_nm=2,residual_torque_T=relaxed.torque_T,
                    breathing_candidates_GHz=breathing.tolist(),max_eigen_residual=float(residuals.max()),
                    note='Targeted finite-chain diagnostic at 2 nm; not full 1 nm paper validation')
        records.append(record)
        print(record,flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(records,indent=2))

if __name__=='__main__':main()
