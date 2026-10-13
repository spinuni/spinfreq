"""Nonlinear paper protocols. Full 40 ns runs can be expensive on a CPU."""
import argparse
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from spinfreq.confined import ConfinedFilm,lattice_seed
from spinfreq.dynamics import integrate,sinc_drive,harmonic_drive,left_strip,cell_spectrum
from liu2024 import paper_material,write_table,savefig


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=['single-sinc-x','single-sinc-z','chain-sinc','chain-comb','array-sinc','array-comb'],default='single-sinc-x')
    parser.add_argument('--columns',type=int,help='Required for chain: total skyrmion count is not specified in PDF')
    parser.add_argument('--cell-nm',type=float,default=1)
    parser.add_argument('--duration-ns',type=float,default=40)
    parser.add_argument('--sample-ps',type=float,default=5)
    parser.add_argument('--amplitude-mt',type=float,default=5)
    parser.add_argument('--components',type=int,nargs='+',choices=[0,1,2],help='Recorded components; defaults x,z for single/chain and z for large 2D arrays')
    parser.add_argument('--discard-ns',type=float,default=0)
    parser.add_argument('--window',choices=['hann','rectangular'],default='rectangular')
    parser.add_argument('--output',type=Path,default=Path('results/liu2024_dynamics'))
    args=parser.parse_args()
    if args.case.startswith('chain') and (args.columns is None or args.columns<2):
        parser.error('Set --columns explicitly (chain length is not specified in the PDF)')
    if not 0<args.cell_nm<=10 or args.duration_ns<=0 or args.sample_ps<=0 or args.amplitude_mt<0:
        parser.error('Require positive duration/sample interval, 0<cell-nm<=10 and nonnegative amplitude')
    cells=round(40/args.cell_nm)
    if not np.isclose(cells*args.cell_nm,40):
        parser.error('cell-nm must divide 40 nm')
    columns,rows=(args.columns,1) if args.case.startswith('chain') else ((19,19) if args.case.startswith('array') else (1,1))
    sample_count=int(np.ceil(args.duration_ns*1e3/args.sample_ps-1e-10))
    times=np.arange(sample_count)*args.sample_ps*1e-12
    if len(times)<3:
        parser.error('Need at least three samples')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').unlink(missing_ok=True)
    components=args.components or ([2] if args.case.startswith('array') else [0,2])
    shape=(len(times),rows*cells,columns*cells,len(components))
    estimated_bytes=int(np.prod(shape))*4
    if estimated_bytes>shutil.disk_usage(args.output).free*.8:
        raise RuntimeError(f'Trajectory needs {estimated_bytes/1e9:.2f} GB; not enough free storage')
    film=ConfinedFilm(nx=columns*cells,ny=rows*cells,dx=args.cell_nm*1e-9,
                      material=paper_material(),field_T=(0,0,0))
    start=time.monotonic()
    result=film.relax(lattice_seed(film,columns,rows),maxiter=10000)
    if not result.converged:
        raise RuntimeError(f'Relaxation failed: residual {result.torque_T:g} T')
    np.save(args.output/'equilibrium.npy',result.m)
    mask=left_strip(film) if (columns>1) else np.ones((film.ny,film.nx))
    amplitude=args.amplitude_mt*1e-3
    if 'comb' in args.case:
        excitation_Hz=13.4e9 if args.case.startswith('chain') else 20e9
        drive=harmonic_drive(amplitude,excitation_Hz,mask=mask)
    else:
        excitation_Hz=30e9 if args.case.startswith('array') else 50e9
        drive=sinc_drive(amplitude,excitation_Hz,axis=2 if args.case.endswith('-z') else 0,mask=mask)
    trace=np.lib.format.open_memmap(args.output/'trajectory.npy',mode='w+',dtype=np.float32,shape=shape)
    def record(indices,fields):
        trace[indices]=fields[...,components]
    print(f'Running {args.case}, {film.nx}×{film.ny} cells, {len(times)} samples; trajectory {estimated_bytes/1e9:.2f} GB',flush=True)
    trajectory=integrate(film,result.m,times,drive,recorder=record,chunk_samples=128)
    trace.flush()
    for column,component in enumerate(components):
        f,amplitude_fft,power=cell_spectrum(times,trace[...,column],component=None,discard_s=args.discard_ns*1e-9,window=args.window)
        write_table(args.output/f'spectrum_{component}.csv',['frequency_Hz','mean_cell_amplitude','mean_cell_power'],zip(f,amplitude_fft,power))
        fig,ax=plt.subplots(figsize=(8,4))
        ax.semilogy(f/1e9,np.maximum(amplitude_fft,1e-15))
        ax.set(xlabel='Frequency (GHz)',ylabel='Mean per-cell FFT amplitude',xlim=(0,50),title=f'{args.case}, component {component}')
        savefig(fig,args.output,f'spectrum_{component}')
    summary=dict(recorded_components=components,case=args.case,material=asdict(film.material),columns=columns,rows=rows,cell_nm=args.cell_nm,
                 duration_ns=args.duration_ns,sample_ps=args.sample_ps,frequency_bin_Hz=1/(len(times)*(times[1]-times[0])),
                 drive_amplitude_mT=args.amplitude_mt,drive_frequency_or_cutoff_Hz=excitation_Hz,
                 residual_torque_T=result.torque_T,max_norm_error=trajectory.max_norm_error,
                 rhs_evaluations=trajectory.evaluations,seconds=time.monotonic()-start,
                 window=args.window,discard_ns=args.discard_ns,
                 assumptions=['Open rectangular boundaries; no static field','Array source width assumed 40 nm; PDF does not give numeric width','Duration 40 ns and sample 5 ps default copied from single-skyrmion protocol; comb-specific duration not stated'],
                 nonlinear_comb_validated=False,
                 note='Spectral output alone does not validate a comb. Identify teeth and spacing, confirm mode mixing, and check run-length/time-step convergence.')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
