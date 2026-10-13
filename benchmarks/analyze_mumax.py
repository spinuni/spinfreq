"""Read cell-resolved MuMax3 snapshots, validate timestamps, and compute FFTs."""
import argparse
import json
import re
import shutil
from pathlib import Path
import numpy as np
from spinfreq.ovf import read_ovf
from spinfreq.dynamics import cell_spectrum
from liu2024 import write_table


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,default=Path('results/mumax_spectra'))
    parser.add_argument('--component',type=int,choices=[0,1,2],default=2)
    parser.add_argument('--window',choices=['hann','rectangular'],default='rectangular')
    parser.add_argument('--discard-ns',type=float,default=0)
    args=parser.parse_args()
    snapshots=sorted([p for p in args.directory.glob('m*.ovf') if re.fullmatch(r'm\d+\.ovf',p.name)],key=lambda p:int(re.search(r'\d+',p.name)[0]))
    if len(snapshots)<3:
        raise RuntimeError('Need at least three numbered m*.ovf snapshots, not just equilibrium or table averages')
    args.output.mkdir(parents=True,exist_ok=True)
    field,metadata=read_ovf(snapshots[0])
    shape=(len(snapshots),*field.shape[:2])
    if np.prod(shape)*4>shutil.disk_usage(args.output).free*.8:
        raise RuntimeError('Insufficient space to assemble scalar cell trace')
    trace=np.lib.format.open_memmap(args.output/'cell_trace.npy',mode='w+',dtype=np.float32,shape=shape)
    times=[]
    cell_keys=['xstepsize','ystepsize','zstepsize']
    for index,path in enumerate(snapshots):
        field,current=read_ovf(path)
        if field.shape[:2]!=shape[1:] or any(current.get(key)!=metadata.get(key) for key in cell_keys):
            raise ValueError('Snapshot mesh changed during run')
        if 'time_s' not in current:
            raise ValueError('Missing OVF simulation timestamps; cannot infer actual sampling from filenames')
        times.append(current['time_s'])
        trace[index]=field[...,args.component]
    trace.flush()
    times=np.asarray(times)
    f,a,p=cell_spectrum(times,trace,component=None,discard_s=args.discard_ns*1e-9,window=args.window)
    write_table(args.output/'spectrum.csv',['frequency_Hz','mean_cell_amplitude','mean_cell_power'],zip(f,a,p))
    (args.output/'summary.json').write_text(json.dumps(dict(snapshots=len(snapshots),mesh_shape=shape[1:],component=args.component,
        start_s=float(times[0]),end_s=float(times[-1]),sample_interval_s=float(times[1]-times[0]),
        window=args.window,discard_ns=args.discard_ns,source_directory=str(args.directory.resolve()),nonlinear_comb_validated=False),indent=2))
    print(f'Wrote {args.output}/spectrum.csv using actual OVF timestamps.')

if __name__=='__main__': main()
