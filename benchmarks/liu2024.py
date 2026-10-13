"""Liu et al., PRB 110 184413 (2024): Fig.1 independent micromagnetic benchmark."""
import argparse
import csv
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
import numpy as np
from scipy.linalg import solve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from spinfreq import Material
from spinfreq.confined import ConfinedFilm,lattice_seed
from spinfreq.model import MU0

REFERENCE_GHZ=np.array([1.9,17.2,39.1])


def paper_material():
    return Material(Ms=5.8e5,A=1.5e-11,D=3e-3,K=.6e6,alpha=.001,gamma=1.7595e11)


def savefig(fig,folder,name):
    fig.tight_layout()
    for ext in ('png','pdf'):
        fig.savefig(folder/f'{name}.{ext}',dpi=180)
    plt.close(fig)


def write_table(path,columns,rows):
    with path.open('w',newline='') as file:
        writer=csv.writer(file,lineterminator='\n')
        writer.writerow(columns)
        writer.writerows(rows)


def run_single(n):
    film=ConfinedFilm(nx=n,ny=n,dx=40e-9/n,thickness=1e-9,
                      material=paper_material(),field_T=(0,0,0),dmi_boundary='mumax')
    result=film.relax(lattice_seed(film),maxiter=5000)
    if not result.converged:
        raise RuntimeError(f'Relaxation failed at {n} cells: {result.torque_T:g} T')
    spectrum=film.modes(result.m)
    if np.max(spectrum.eigenvalues.real)>0:
        raise RuntimeError('Relaxed single-skyrmion state has an unstable mode')
    indices=np.flatnonzero(spectrum.frequencies_Hz>1e6)[:3]
    return film,result,spectrum,indices


def modal_absorption(film,m,spectrum,frequencies):
    """Reuse complete eigenbasis for small-system frequency sweeps.

    Not valid with a truncated set of modes. Returns average response and power.
    """
    basis=film.tangent_basis(m)
    vectors=np.einsum('...ci,k...c->...ik',basis,spectrum.modes).reshape(2*film.nx*film.ny,-1)
    if vectors.shape[0]!=vectors.shape[1]:
        raise ValueError('Modal response requires the complete eigenbasis')
    p=film.material
    forces=[]
    for axis in (0,2):
        drive=np.eye(3)[axis]*1e-6
        c=np.cross(m,drive)
        force=-p.gamma/(1+p.alpha**2)*(c+p.alpha*np.cross(m,c))
        forces.append(np.einsum('...ci,...c->...i',basis,force).ravel())
    coefficients=solve(vectors,np.array(forces).T)
    readouts=spectrum.modes.mean(axis=(1,2))
    denominator=2j*np.pi*frequencies[:,None]-spectrum.eigenvalues[None,:]
    result={}
    volume=film.nx*film.ny*film.dx*film.dy*film.thickness
    for column,axis in enumerate((0,2)):
        average=(coefficients[:,column][None,:]/denominator)@readouts
        power=-.5*p.Ms*volume*2*np.pi*frequencies*1e-6*average[:,axis].imag
        result[axis]=(average,power)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('validation/liu2024'))
    parser.add_argument('--meshes',nargs='+',type=int,default=[20,40])
    args=parser.parse_args()
    if any(n<3 or n>64 for n in args.meshes):
        parser.error('Dense reference benchmark supports 3..64 cells per axis')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').unlink(missing_ok=True)
    records=[]
    for n in sorted(set(args.meshes)):
        start=time.monotonic()
        film,result,spectrum,indices=run_single(n)
        f=spectrum.frequencies_Hz[indices]/1e9
        error=abs(f/REFERENCE_GHZ-1)*100
        record=dict(cells_per_axis=n,cell_nm=40/n,frequencies_GHz=f.tolist(),relative_errors_percent=error.tolist(),
                    residual_torque_T=result.torque_T,energy_J=result.energy_J,
                    topological_charge_open_domain=film.topological_charge(result.m),
                    maximum_growth_rate_per_s=float(spectrum.eigenvalues.real.max()),seconds=time.monotonic()-start)
        records.append(record)
        np.savez_compressed(args.output/f'single_{n}.npz',m=result.m,eigenvalues=spectrum.eigenvalues,modes=spectrum.modes)
        print(json.dumps(record),flush=True)
    finest=records[-1]
    write_table(args.output/'frequencies.csv',['cells_per_axis','cell_nm','mode','paper_GHz','simulation_GHz','relative_error_percent'],
                [[r['cells_per_axis'],r['cell_nm'],j+1,REFERENCE_GHZ[j],r['frequencies_GHz'][j],r['relative_errors_percent'][j]] for r in records for j in range(3)])
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    x=np.arange(3)
    axes[0].bar(x-.18,REFERENCE_GHZ,.36,label='Liu 2024, Fig.1')
    axes[0].bar(x+.18,finest['frequencies_GHz'],.36,label=f"spinfreq, {finest['cell_nm']:g} nm mesh")
    axes[0].set(xticks=x,xticklabels=['CCW gyration','Breathing','CW gyration'],ylabel='Frequency (GHz)')
    axes[0].legend(fontsize=8)
    for j in range(3):
        axes[1].plot([r['cell_nm'] for r in records],[r['relative_errors_percent'][j] for r in records],'o-',label=f'Mode {j+1}')
    axes[1].set(xlabel='Cell size (nm)',ylabel='Difference from reported frequency (%)')
    axes[1].legend()
    savefig(fig,args.output,'fig1_frequencies')
    fig,axes=plt.subplots(2,4,figsize=(12,6))
    extent=[0,40,0,40]
    for row in range(2):
        axes[row,0].imshow(result.m[...,2],origin='lower',extent=extent,cmap='RdBu_r',vmin=-1,vmax=1)
        axes[row,0].set_title('Equilibrium mz')
    for column,index in enumerate(indices,1):
        mode=spectrum.modes[index,...,2]
        maximum=abs(mode).max()
        amplitude=abs(mode)/maximum
        phase=np.angle(mode*np.exp(-1j*np.angle(mode.ravel()[np.argmax(abs(mode))])))
        phase=np.ma.masked_where(amplitude<.03,phase)
        im=axes[0,column].imshow(amplitude,origin='lower',extent=extent,cmap='viridis',vmin=0,vmax=1)
        axes[0,column].set_title(f'{spectrum.frequencies_Hz[index]/1e9:.3f} GHz')
        fig.colorbar(im,ax=axes[0,column],shrink=.75)
        im=axes[1,column].imshow(phase,origin='lower',extent=extent,cmap='twilight',vmin=-np.pi,vmax=np.pi)
        fig.colorbar(im,ax=axes[1,column],shrink=.75)
    for ax in axes.ravel(): ax.set(xlabel='x (nm)',ylabel='y (nm)')
    savefig(fig,args.output,'fig1_amplitude_phase')
    frequencies=np.arange(1,2001)*.025e9
    response=modal_absorption(film,result.m,spectrum,frequencies)
    fig,ax=plt.subplots(figsize=(8,4))
    for axis,label in [(0,'In-plane x'),(2,'Out-of-plane z')]:
        _,power=response[axis]
        ax.semilogy(frequencies/1e9,np.maximum(power,1e-35),label=label)
        write_table(args.output/f'linear_absorption_{axis}.csv',['frequency_Hz','power_W'],zip(frequencies,power))
    for j,f in enumerate(REFERENCE_GHZ):
        ax.axvline(f,color='k',ls='--',alpha=.5,label='Paper eigenfrequency' if j==0 else None)
    ax.set(xlabel='Frequency (GHz)',ylabel='Absorbed power (W), 1 μT linear drive',title='Single-skyrmion linear response; not the nonlinear comb')
    ax.legend()
    savefig(fig,args.output,'fig1_linear_absorption')
    p=paper_material()
    fmr=p.gamma*(2*p.K/p.Ms-MU0*p.Ms)/(2*np.pi)/1e9
    summary=dict(paper=dict(doi='10.1103/PhysRevB.110.184413',figure=1,reference_frequencies_GHz=REFERENCE_GHZ.tolist(),reported_FMR_GHz=37.5),
                 material=asdict(p),geometry=dict(width_m=40e-9,height_m=40e-9,thickness_m=1e-9),
                 assumptions=['No static field: none stated in paper','Open finite geometry with MuMax3 default DMI ghost boundary','gamma=1.7595e11 rad/(s T), matching inspected MuMax3 GammaLL default; paper does not give value','Mode identities inferred from frequencies and spatial maps; not automatic chirality classification'],
                 calculated_infinite_film_FMR_GHz=fmr,results=records,
                 fig1_frequency_validation_passed=bool(finest['cell_nm']==1 and max(finest['relative_errors_percent'])<1),
                 fig1_frequency_acceptance_percent=1,acceptance_note='Project validation criterion, not a tolerance stated by the authors',
                 nonlinear_comb_validated=False,mumax3_executed=False)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
