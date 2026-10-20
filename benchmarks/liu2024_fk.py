"""Turn recorded finite-chain nonlinear data into a genuine time/space FFT map."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from spinfreq.dynamics import space_time_spectrum
from liu2024 import write_table,savefig


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('trajectory',type=Path)
    parser.add_argument('--summary',type=Path,required=True)
    parser.add_argument('--component',type=int,choices=[0,1,2],default=2)
    parser.add_argument('--discard-ns',type=float,default=0)
    parser.add_argument('--time-window',choices=['hann','rectangular'],default='hann')
    parser.add_argument('--space-window',choices=['hann','rectangular'],default='hann')
    parser.add_argument('--temporal-sign',type=int,choices=[-1,1],default=1,
                        help='Select exp(+i omega t) (+1) or exp(-i omega t) (-1), at positive returned f')
    parser.add_argument('--output',type=Path,default=Path('results/liu2024_fk'))
    args=parser.parse_args()
    metadata=json.loads(args.summary.read_text())
    components=metadata['recorded_components']
    if args.component not in components: parser.error('Selected component was not recorded')
    trace=np.load(args.trajectory,mmap_mode='r')
    if trace.ndim!=4 or trace.shape[-1]!=len(components): parser.error('Trajectory shape does not match recorded components')
    dt=metadata['sample_ps']*1e-12
    times=np.arange(len(trace))*dt
    q,f,power=space_time_spectrum(times,trace[...,components.index(args.component)],metadata['cell_nm']*1e-9,
                                 discard_s=args.discard_ns*1e-9,time_window=args.time_window,space_window=args.space_window,
                                 temporal_sign=args.temporal_sign)
    args.output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(args.output/'space_time_fft.npz',k_rad_m=q,frequency_Hz=f,power=power)
    visible=f<=55e9
    write_table(args.output/'fk.csv',['frequency_GHz',*[f'k={k/1e9:.8g}_rad_per_nm' for k in q]],[[frequency/1e9,*row] for frequency,row in zip(f[visible],power[visible])])
    fig,ax=plt.subplots(figsize=(8,5))
    relative=power[visible]/max(power[visible].max(),1e-300)
    im=ax.pcolormesh(q/1e9,f[visible]/1e9,np.log10(np.maximum(relative,1e-8)),shading='auto',cmap='magma',vmin=-5,vmax=0)
    ax.set(xlabel='kx (rad/nm)',ylabel='Frequency (GHz)',xlim=(-.5,.5),ylim=(0,55),title='Finite-array time/space FFT, per-row powers averaged')
    fig.colorbar(im,ax=ax,label='log₁₀ normalized power')
    savefig(fig,args.output,'fk')
    (args.output/'summary.json').write_text(json.dumps(dict(source_trajectory=str(args.trajectory),source_summary=str(args.summary),
        component=args.component,time_window=args.time_window,space_window=args.space_window,discard_ns=args.discard_ns,
        temporal_sign=args.temporal_sign,
        frequency_bin_Hz=float(f[1]-f[0]),wavevector_bin_rad_m=float(q[1]-q[0]),full_paper_validation_passed=False),indent=2))

if __name__=='__main__':main()
