"""Controlled boundary/width sensitivity; paper material is never fitted."""
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.sparse.linalg import LinearOperator
from spinfreq import BlochChain
from spinfreq.model import Relaxation
from liu2024 import paper_material,write_table,savefig
from liu2024_fig2 import branch_values
from spinfreq import refine_equilibrium as refine
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


class PinnedChain(BlochChain):
    """Frozen +z transverse boundary rows, reduced tangent degrees of freedom.

    Only relaxation and Bloch modes are supported by this benchmark subclass.
    Its frozen layer is an explicit alternative geometry, not an author setting.
    """
    def __init__(self,*args,pinned_nm=2,**kwargs):
        super().__init__(*args,**kwargs)
        rows=round(pinned_nm*1e-9/self.dy)
        if rows<1 or 2*rows>=self.ny or not np.isclose(rows*self.dy,pinned_nm*1e-9,atol=1e-18):
            raise ValueError('Pinned thickness must be cell resolved and leave free rows')
        self.free=np.ones((self.ny,self.nx),dtype=bool)
        self.free[:rows]=False;self.free[-rows:]=False
        self.free_coordinates=np.repeat(self.free.ravel(),2)

    def torque(self,m):
        return float(np.linalg.norm(np.cross(m,self.effective_field(m))[self.free],axis=-1).max())

    def relax(self,initial,maxiter=6000,tolerance_T=1e-5):
        initial=self.check(initial).copy();initial[~self.free]=(0,0,1)
        scale=max(self.material.Ms,abs(self.material.K),1.)
        volume=self.dx*self.dy*self.thickness
        def objective(x):
            raw=x.reshape(-1,3);norms=np.linalg.norm(raw,axis=-1,keepdims=True)
            if np.any(norms<1e-12): raise ValueError('Zero free spin in relaxation')
            m=initial.copy();m[self.free]=raw/norms
            b=self.effective_field(m)[self.free];spins=m[self.free]
            gradient=-self.material.Ms*(b-(b*spins).sum(axis=-1,keepdims=True)*spins)/norms/scale
            return self.energy(m)/volume/scale,gradient.ravel()
        result=minimize(objective,initial[self.free].ravel(),jac=True,method='L-BFGS-B',
            options={'maxiter':maxiter,'gtol':tolerance_T*self.material.Ms/scale/10,'ftol':1e-15,'maxls':50})
        spins=result.x.reshape(-1,3);initial[self.free]=spins/np.linalg.norm(spins,axis=-1,keepdims=True)
        torque=self.torque(initial)
        return Relaxation(initial,self.energy(initial),torque,torque<=tolerance_T,result.nit,str(result.message))

    def bloch_operator(self,m,k_rad_m,equilibrium_tolerance_T=1e-4,assemble=False):
        full,basis=super().bloch_operator(m,k_rad_m,equilibrium_tolerance_T,assemble=False)
        if not np.allclose(m[~self.free],(0,0,1),atol=1e-10): raise ValueError('Frozen spins must remain +z')
        n=int(self.free_coordinates.sum())
        def matvec(v):
            expanded=np.zeros(full.shape[0],dtype=np.result_type(v,complex))
            expanded[self.free_coordinates]=v
            return (full@expanded)[self.free_coordinates]
        operator=LinearOperator((n,n),matvec=matvec,dtype=complex)
        if not assemble: return operator,basis
        if n>8192: raise ValueError('Reduced dense matrix too large')
        matrix=np.empty((n,n),dtype=complex);unit=np.zeros(n)
        for j in range(n):
            unit[j]=1;matrix[:,j]=matvec(unit);unit[j]=0
        return matrix,basis

    def _mode_coordinates(self,vectors):
        full=np.zeros((2*self.nx*self.ny,vectors.shape[1]),dtype=vectors.dtype)
        full[self.free_coordinates]=vectors
        return full.reshape(self.ny,self.nx,2,-1)


def seed(film,offset_cells=0):
    x=((np.arange(film.nx)+.5+offset_cells)*film.dx)%film.period_m-film.period_m/2
    y=(np.arange(film.ny)+.5)*film.dy-film.ny*film.dy/2
    x,y=np.meshgrid(x,y);r=np.hypot(x,y)
    theta=2*np.arctan(np.exp(np.clip((8e-9-r)/3e-9,-700,700)))
    theta=np.where(r<1e-20,np.pi,theta);phi=np.arctan2(y,x)
    return np.stack((np.sin(theta)*np.cos(phi),np.sin(theta)*np.sin(phi),np.cos(theta)),axis=-1)


CASES={
 'natural_w30':dict(width_nm=30,boundary='mumax',pinned_nm=0),
 'natural_w40':dict(width_nm=40,boundary='mumax',pinned_nm=0),
 'natural_w60':dict(width_nm=60,boundary='mumax',pinned_nm=0),
 'open_dmi_w40':dict(width_nm=40,boundary='bond',pinned_nm=0),
 'pinned2_w40':dict(width_nm=40,boundary='mumax',pinned_nm=2),
 'pinned2_w50':dict(width_nm=50,boundary='mumax',pinned_nm=2),
 'pinned2_w44':dict(width_nm=44,boundary='mumax',pinned_nm=2),
 'pinned2_w46':dict(width_nm=46,boundary='mumax',pinned_nm=2),
 'pinned2_w45':dict(width_nm=45,boundary='mumax',pinned_nm=2),
}


def make_film(case,cell_nm,images):
    params=dict(nx=round(40/cell_nm),ny=round(case['width_nm']/cell_nm),dx=cell_nm*1e-9,
                thickness=1e-9,material=paper_material(),field_T=(0,0,0),images=images,dmi_boundary=case['boundary'])
    if not np.isclose(params['nx']*cell_nm,40) or not np.isclose(params['ny']*cell_nm,case['width_nm']):
        raise ValueError('Cell size must divide period and width')
    return PinnedChain(**params,pinned_nm=case['pinned_nm']) if case['pinned_nm'] else BlochChain(**params)


def evaluate(name,cell_nm,images,kpoints,folder,refine_equilibrium=True):
    start=time.monotonic();case=CASES[name];film=make_film(case,cell_nm,images)
    candidates=[]
    for offset in [0,.25,.5]:
        result=film.relax(seed(film,offset),maxiter=6000)
        if not result.converged:
            candidates.append(dict(offset=offset,converged=False,torque_T=result.torque_T));continue
        original_torque=result.torque_T
        if refine_equilibrium:
            result=refine(film,result.m)
            if not result.converged:
                candidates.append(dict(offset=offset,converged=False,torque_T=result.torque_T,
                                       original_torque_T=original_torque,refinement_message=result.message));continue
        spectrum=film.bloch_modes(result.m,0,count=12,target_Hz=15e9)
        candidates.append(dict(offset=offset,converged=True,original_torque_T=original_torque,equilibrium_refined=refine_equilibrium,energy_J=result.energy_J,torque_T=result.torque_T,
                               growth_per_s=float(spectrum.eigenvalues.real.max()),result=result))
    stable=[entry for entry in candidates if entry.get('converged') and entry['growth_per_s']<=0]
    selected=min(stable,key=lambda entry:entry['energy_J']) if stable else None
    diagnostics=[{key:value for key,value in entry.items() if key!='result'} for entry in candidates]
    if selected is None:
        return dict(case=name,cell_nm=cell_nm,assumptions=case,status='no stable converged k=0 candidate',seed_diagnostics=diagnostics)
    result=selected['result']
    rows=[];selected_modes=[];residuals=[]
    for reduced in np.linspace(0,1,kpoints):
        spectrum=film.bloch_modes(result.m,reduced*np.pi/film.period_m,count=12,target_Hz=15e9)
        branches=branch_values(spectrum)
        residuals.append(float(film.last_eigen_residuals.max()))
        rows.append(dict(reduced_ka_over_pi=float(reduced),**branches))
        selected_modes.append(spectrum)
    write_table(folder/f'{name}_{cell_nm:g}nm.csv',list(rows[0]),[list(row.values()) for row in rows])
    np.savez_compressed(folder/f'{name}_{cell_nm:g}nm.npz',m=result.m,
        eigenvalues=np.array([s.eigenvalues for s in selected_modes]),modes=np.array([s.modes for s in selected_modes]))
    ranges={band:[min(row[band+'_GHz'] for row in rows),max(row[band+'_GHz'] for row in rows)]
            for band in ['gyration','breathing'] if all(row[band+'_GHz'] is not None for row in rows)}
    breathing=ranges.get('breathing')
    endpoint_error=(abs(np.array(breathing)/[13.4,20.4]-1)*100).tolist() if breathing else None
    return dict(case=name,cell_nm=cell_nm,images=images,assumptions=case,status='computed',seed_diagnostics=diagnostics,
        selected_offset_cells=selected['offset'],torque_T=result.torque_T,energy_J=result.energy_J,
        minimum_mz=float(result.m[...,2].min()),Q_open_y=film.topological_charge(result.m),bands_GHz=ranges,
        k0_upper_GHz=rows[0]['upper_branch_GHz'],breathing_endpoint_errors_percent=endpoint_error,
        max_growth_per_s=max(row['maximum_growth_per_s'] for row in rows),max_eigen_residual=max(residuals),
        seconds=time.monotonic()-start,frequency_samples=rows,
        material=asdict(film.material),paper_validation_passed=False,
        note='Alternative geometry/boundary; closeness alone does not establish the author setup')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cases',nargs='+',choices=CASES,default=None)
    parser.add_argument('--no-refine',action='store_true',help='Reproduce the initial low-accuracy equilibrium diagnostics')
    parser.add_argument('--cell-nm',type=float,default=2);parser.add_argument('--images',type=int,default=32)
    parser.add_argument('--k-points',type=int,default=3);parser.add_argument('--output',type=Path,default=Path('validation/liu2024/conditions'))
    args=parser.parse_args()
    if args.cell_nm<=0 or args.k_points<3 or args.images<1: parser.error('Require positive cells/images and >=3 k points')
    args.output.mkdir(parents=True,exist_ok=True)
    records=[]
    cases=args.cases or [name for name,case in CASES.items() if np.isclose(case['width_nm']/args.cell_nm,round(case['width_nm']/args.cell_nm))]
    for name in cases:
        record=evaluate(name,args.cell_nm,args.images,args.k_points,args.output,not args.no_refine)
        records.append(record)
        (args.output/f'summary_{args.cell_nm:g}nm.json').write_text(json.dumps(records,indent=2))
        print(json.dumps(record),flush=True)
    computed=[r for r in records if r['status']=='computed']
    if computed:
        fig,axes=plt.subplots(1,2,figsize=(10,4))
        for r in computed:
            q=[row['reduced_ka_over_pi'] for row in r['frequency_samples']]
            for ax,band in zip(axes,['gyration','breathing']):
                ax.plot(q,[row[band+'_GHz'] for row in r['frequency_samples']],'o-',label=r['case'])
        for ax,band,interval in zip(axes,['Gyration','Breathing'],[[.1,4],[13.4,20.4]]):
            ax.axhspan(*interval,color='gray',alpha=.12,label='Paper quoted interval')
            ax.set(xlabel='k a / π',ylabel='Frequency (GHz)',title=f'{band}, {args.cell_nm:g} nm cells');ax.legend(fontsize=7)
        savefig(fig,args.output,f'conditions_{args.cell_nm:g}nm')

if __name__=='__main__':main()
