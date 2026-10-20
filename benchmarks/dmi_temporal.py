"""Executed CPU OOMMF ringdown versus the frequency-domain Bloch strip.

This reduced, periodic benchmark resolves two signed wavevector pairs. It is
distinct from the paper's finite 2 um strip and localized 40 mT pulse.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time

import numpy as np
import scipy
from scipy.linalg import eig, solve

from spinfreq import BlochChain,Material,refine_equilibrium
from spinfreq.model import MU0
from spinfreq.ovf import read_ovf,write_ovf
from spinfreq.dynamics import space_time_spectrum


def prepare(directory,duration_ns=4.,amplitude=1e-4):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    if any(directory.glob('*.odt')):
        raise FileExistsError('Use a fresh run directory, or analyze the existing reference')
    if not np.isfinite(duration_ns) or duration_ns<=0 or abs(duration_ns*1000-round(duration_ns*1000))>1e-6:
        raise ValueError('Duration must be a positive integer number of ps')
    if not np.isfinite(amplitude) or not 0<amplitude<=1e-3:
        raise ValueError('Initial amplitude must be positive and <=1e-3')
    common='''# MIF 2.2
set mu0 [expr {4*acos(-1)*1e-7}]
SetOptions {basename @BASENAME@ vector_field_output_format {text %.17g} scalar_output_format %.17g}
Specify Oxs_BoxAtlas:atlas {name film xrange {0 128e-9} yrange {0 200e-9} zrange {0 1e-9}}
Specify Oxs_PeriodicRectangularMesh:mesh {cellsize {2e-9 2e-9 1e-9} atlas :atlas periodic x}
Specify Oxs_UniformExchange {A 13e-12}
Specify Oxs_Demag {}
Specify Oxs_DMI_Cnv_z {atlas :atlas default_D 3e-3 D {film film 3e-3}}
Specify Oxs_FixedZeeman [subst {field {0 [expr {.4/$mu0}] 0}}]
'''
    static=common.replace('@BASENAME@','equilibrium')+'''Specify Oxs_CGEvolve:evolver {}
Specify Oxs_MinDriver {evolver :evolver mesh :mesh Ms 860e3 m0 {0 1 0} stopping_mxHxm 0.001 checkpoint_interval 0}
Destination archive mmArchive
Schedule DataTable archive Stage 1
Schedule Oxs_MinDriver::Spin archive Stage 1
'''
    dynamic=common.replace('@BASENAME@','ringdown')+'''Specify Oxs_RungeKuttaEvolve:evolver {alpha .01 gamma_G 2.21e5 method rkf54 absolute_step_error 1e-7 relative_step_error 1e-7}
proc Weight {j trig x y z} {
 set w 0.0
 if {$y >= 98e-9 && $y < 100e-9} {
  set angle [expr {2*acos(-1)*$j*$x/128e-9}]
  if {$trig eq "cos"} {set w [expr {100*cos($angle)}]} else {set w [expr {100*sin($angle)}]}
 }
 return [list $w 0 0]
}
'''
    outputs=[]
    for j in [1,2]:
        for trig in ['cos','sin']:
            dynamic+=f'Specify Oxs_ScriptVectorField:w{j}{trig} {{atlas :atlas script_args rawpt script {{Weight {j} {trig}}}}}\n'
            outputs.append(f'user_output {{name q{j}_{trig} source_field Spin select_field :w{j}{trig} normalize 0}}')
    dynamic+='''Specify Oxs_TimeDriver {
 evolver :evolver mesh :mesh Ms 860e3
 m0 {Oxs_FileVectorField {atlas :atlas file initial.ovf norm 1}}
 stopping_time 1e-12 stage_count @STAGES@ checkpoint_interval 0
'''.replace('@STAGES@',str(round(duration_ns*1000)))+'\n'.join(outputs)+'''\n}
Destination archive mmArchive
Schedule DataTable archive Stage 1
'''
    (directory/'equilibrium.mif').write_text(static);(directory/'ringdown.mif').write_text(dynamic)
    config=dict(nx=64,ny=100,dx_m=2e-9,dy_m=2e-9,thickness_m=1e-9,period_m=128e-9,
        width_m=200e-9,harmonics=[1,2],duration_ns=duration_ns,sample_ps=1.,amplitude=amplitude,
        observed_y_row=49,material=dict(Ms=860e3,A=13e-12,D=-3e-3,K=0,alpha=.01,gamma=2.21e5/MU0),
        field_T=[0,.4,0],oommf_D_J_m2=.003,oommf_D_class='Oxs_DMI_Cnv_z',spinfreq_boundary='bond',
        oommf_gamma_convention='gamma_G 2.21e5 m/(A s)',images=1024)
    (directory/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    return config


def execute(directory,runtime):
    directory=Path(directory).resolve();runtime=json.loads(Path(runtime).read_text())
    config=json.loads((directory/'configuration.json').read_text())
    if (directory/'ringdown.odt').exists():raise FileExistsError('Use a fresh run directory, or analyze the existing reference')
    env=os.environ.copy();env.update(runtime.get('env',{}))
    start=time.perf_counter()
    for stage in ['equilibrium','ringdown']:
        if stage=='ringdown':
            files=list(directory.glob('equilibrium-*Spin*.omf'))
            if len(files)!=1:raise RuntimeError('Expected exactly one independent OOMMF equilibrium')
            m,_=read_ovf(files[0]);x=(np.arange(config['nx'])+.5)*config['dx_m']
            perturbation=sum(np.cos(2*np.pi*j*x/config['period_m']) for j in config['harmonics'])
            m[...,0]+=config['amplitude']*perturbation
            m/=np.linalg.norm(m,axis=-1,keepdims=True)
            write_ovf(directory/'initial.ovf',m,config['dx_m'],config['dy_m'],config['thickness_m'])
        args=[runtime['tclsh'],runtime['oommf_tcl'],'boxsi','-exitondone','1','-kill','archive',
              '-threads','2','-logfile',str(directory/f'{stage}.errors'),str(directory/f'{stage}.mif')]
        print(f'Running OOMMF {stage}',flush=True)
        with (directory/f'{stage}.log').open('w') as log:
            subprocess.run(args,cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        if not (directory/f'{stage}.odt').exists():raise RuntimeError(f'Missing OOMMF {stage} output; inspect its log')
    provenance=dict(runtime=runtime,elapsed_s=time.perf_counter()-start,source_sha256=runtime_source_hashes(runtime))
    (directory/'execution.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (directory/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')


def runtime_source_hashes(runtime):
    root=Path(runtime['oommf_tcl']).parent
    paths=['app/oxs/local/oommf-extension-dmi-cnv/DMI_Cnv_z.cc',
           'app/oxs/local/oommf-extension-dmi-cnv/DMI_Cnv_z.h',
           'app/oxs/ext/uniformexchange.cc','app/oxs/ext/demag.cc',
           'app/oxs/ext/rungekuttaevolve.cc','app/oxs/linux-x86_64/oxs']
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths if (root/name).exists()}


def read_odt(path):
    """Read one complete OOMMF scalar table with ordinary braced labels."""
    path=Path(path)
    text=gzip.open(path,'rt').read() if path.suffix=='.gz' else path.read_text()
    if text.count('# Table Start')!=1 or '# Table End' not in text:
        raise ValueError('Require exactly one complete ODT table')
    lines=text.splitlines();headers=[i for i,line in enumerate(lines) if line.startswith('# Columns:')]
    if len(headers)!=1:raise ValueError('Require one ODT Columns header')
    i=headers[0];header=lines[i].partition('# Columns:')[2]
    while header.rstrip().endswith('\\'):
        i+=1;header=header.rstrip()[:-1]+' '+lines[i].lstrip('# ')
    columns=[a or b for a,b in re.findall(r'\{([^{}]*)\}|([^\s{}]+)',header)]
    if len(columns)!=len(set(columns)):raise ValueError('Duplicate ODT column labels')
    rows=[np.fromstring(line,sep=' ') for line in lines if line.strip() and not line.startswith('#')]
    if not rows or any(len(row)!=len(columns) for row in rows):raise ValueError('ODT data/header size mismatch')
    values=np.array(rows)
    if not np.all(np.isfinite(values)):raise ValueError('Nonfinite ODT data')
    return {name:values[:,index] for index,name in enumerate(columns)}


def negative_branch_peaks(times,trace,dx,harmonics):
    """Correct physical exp(-i omega t) peaks and the legacy flipped-row labels."""
    q,f,power=space_time_spectrum(times,trace[:,None,:],dx,time_window='hann',
                                 space_window='rectangular',temporal_sign=-1)
    raw=abs(np.fft.fftshift(np.fft.fft2(trace*np.hanning(len(times))[:,None])))**2
    old_f=np.fft.fftshift(np.fft.fftfreq(len(times),times[1]-times[0]))
    old=raw[::-1]
    records=[]
    for k in harmonics:
        column=int(np.argmin(abs(q-k)))
        indices=np.flatnonzero((f>1e9)&(f<60e9));peak=indices[np.argmax(power[indices,column])]
        old_indices=np.flatnonzero((old_f>1e9)&(old_f<60e9));old_peak=old_indices[np.argmax(old[old_indices,column])]
        records.append(dict(k_rad_m=float(q[column]),correct_peak_GHz=float(f[peak]/1e9),
                            legacy_peak_GHz=float(old_f[old_peak]/1e9)))
    return records,q,f,power


def fft_audit(output):
    records=[]
    for nt in [4000,4001]:
        times=np.arange(nt)*1e-12;x=np.arange(64)*2e-9;q=2*np.pi*3/(64*2e-9)
        frequency=50/(nt*1e-12)
        trace=np.cos(q*x[None,:]-2*np.pi*frequency*times[:,None])
        peaks,_,_,_=negative_branch_peaks(times,trace,2e-9,[q])
        records.append(dict(samples=nt,true_frequency_GHz=frequency/1e9,bin_GHz=1/(nt*1e-12)/1e9,
            **peaks[0],legacy_error_GHz=peaks[0]['legacy_peak_GHz']-frequency/1e9))
    (Path(output)/'fft_parity_audit.json').write_text(json.dumps(records,indent=2)+'\n')
    return records


def amplitude_scaling(output,half_output):
    """Compare independent nonlinear trajectories at two prescribed amplitudes."""
    output=Path(output);half_output=Path(half_output)
    full=json.loads((output/'summary.json').read_text())['configuration']
    half=json.loads((half_output/'summary.json').read_text())['configuration']
    ratio=full['amplitude']/half['amplitude']
    if ratio!=2 or {k:v for k,v in full.items() if k!='amplitude'}!={k:v for k,v in half.items() if k!='amplitude'}:
        raise ValueError('Require identical configurations with exactly halved amplitude')
    a=np.loadtxt(output/'complex_traces.csv',delimiter=',',skiprows=1)
    b=np.loadtxt(half_output/'complex_traces.csv',delimiter=',',skiprows=1)
    if a.shape!=b.shape or not np.allclose(a[:,0],b[:,0],rtol=0,atol=1e-10):
        raise ValueError('Require matching sample times')
    records=[]
    for j,harmonic in enumerate(full['harmonics']):
        x=a[:,1+4*j]+1j*a[:,2+4*j];y=b[:,1+4*j]+1j*b[:,2+4*j]
        records.append(dict(harmonic=harmonic,
            relative_complex_trace_L2_error=float(np.linalg.norm(x-ratio*y)/np.linalg.norm(x)),
            integrated_power_ratio=float(np.vdot(y,y).real/np.vdot(x,x).real)))
    result=dict(amplitude_ratio=ratio,harmonics=records,
        all_executed_gates_passed=bool(all(r['relative_complex_trace_L2_error']<.01 and
            abs(r['integrated_power_ratio']-.25)<.0025 for r in records)),
        scope='Initial-perturbation free ringdown; forced-response amplitude sweeps remain open')
    (output/'amplitude_scaling.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def restore_reference(reference,directory):
    """Unpack the archived native reference after checking its recorded hashes."""
    reference=Path(reference);directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError('Restore requires an empty directory')
    summary=json.loads((reference/'summary.json').read_text())
    contents={}
    for name,digest in summary['raw_reference_sha256'].items():
        if Path(name).name!=name:raise ValueError('Reference filename must be a basename')
        path=reference/'oommf'/name
        content=path.read_bytes() if path.exists() else gzip.decompress(Path(str(path)+'.gz').read_bytes())
        if hashlib.sha256(content).hexdigest()!=digest:raise ValueError(f'Reference hash mismatch: {name}')
        contents[name]=content
    directory.mkdir(parents=True,exist_ok=True)
    for name,content in contents.items():(directory/name).write_bytes(content)


def analyze(directory,output):
    directory=Path(directory).resolve();output=Path(output);output.mkdir(parents=True,exist_ok=True)
    config=json.loads((directory/'configuration.json').read_text())
    table=read_odt(directory/'ringdown.odt');times=table['Oxs_TimeDriver::Simulation time']
    if np.any(np.diff(times)<=0) or not np.allclose(np.diff(times),config['sample_ps']*1e-12,rtol=1e-7,atol=1e-20):
        raise ValueError('Unexpected OOMMF sampling')
    complete=len(times)>=round(config['duration_ns']*1000) and times[-1]>=config['duration_ns']*1e-9*(1-1e-8)
    external,meta=read_ovf(next(directory.glob('equilibrium-*Spin*.omf')))
    initial,_=read_ovf(directory/'initial.ovf')
    material=Material(**config['material'])
    film=BlochChain(nx=1,ny=config['ny'],dx=config['dx_m'],dy=config['dy_m'],thickness=config['thickness_m'],
        material=material,images=config['images'],field_T=config['field_T'],dmi_boundary=config['spinfreq_boundary'])
    m=np.zeros(film.shape);m[...,1]=1
    state=refine_equilibrium(film,film.relax(m,tolerance_T=1e-7).m,tolerance_T=1e-9)
    if not state.converged:raise RuntimeError('Frequency-domain equilibrium failed')
    profile_error=float(abs(state.m[:,0]-external.mean(axis=1)).max())
    x=(np.arange(config['nx'])+.5)*config['dx_m'];basis=film.tangent_basis(state.m)
    actual_traces=[];predicted_traces=[];records=[];spatial_ks=[]
    for harmonic in config['harmonics']:
        q=2*np.pi*harmonic/config['period_m']
        matrix,basis=film.bloch_operator(state.m,q,assemble=True);values,vectors=eig(matrix)
        delta=np.mean((initial-external)*np.exp(-1j*q*x)[None,:,None],axis=1)[:,None,:]
        u0=np.einsum('...ci,...c->...i',basis,delta).ravel();coefficients=solve(vectors,u0)
        observation=np.zeros(2*config['ny']);row=config['observed_y_row']
        observation[2*row:2*row+2]=basis[row,0,0,:]
        residues=(observation@vectors)*coefficients
        predicted=residues@np.exp(values[:,None]*times)
        actual=table[f'Oxs_TimeDriver::q{harmonic}_cos']-1j*table[f'Oxs_TimeDriver::q{harmonic}_sin']
        record=dict(harmonic=harmonic,k_rad_nm=q/1e9,
            relative_complex_trace_L2_error=float(np.linalg.norm(actual-predicted)/np.linalg.norm(predicted)),
            max_complex_error_over_peak=float(abs(actual-predicted).max()/abs(predicted).max()),
            coefficient_reconstruction_residual=float(np.linalg.norm(vectors@coefficients-u0)/np.linalg.norm(u0)),
            max_growth_rate_per_s=float(values.real.max()),poles=[])
        for sign in [-1,1]:
            candidates=np.flatnonzero((sign*values.imag>0)&(abs(values.imag)/(2*np.pi)<60e9))
            choice=candidates[np.argmax(abs(residues[candidates])/(-values.real[candidates]))]
            absolute=float(np.linalg.norm(matrix@vectors[:,choice]-values[choice]*vectors[:,choice])/np.linalg.norm(vectors[:,choice]))
            record['poles'].append(dict(physical_k_rad_nm=-sign*q/1e9,
                frequency_GHz=float(abs(values[choice].imag)/(2*np.pi*1e9)),
                pole_FWHM_GHz=float(-values[choice].real/(np.pi*1e9)),absolute_eigen_residual_per_s=absolute))
        actual_traces.append(actual);predicted_traces.append(predicted);spatial_ks.extend([-q,q]);records.append(record)
        print(json.dumps(record),flush=True)
    actual_space=sum(2*np.real(z[:,None]*np.exp(1j*2*np.pi*j*x/config['period_m'])[None,:])
                     for j,z in zip(config['harmonics'],actual_traces))
    predicted_space=sum(2*np.real(z[:,None]*np.exp(1j*2*np.pi*j*x/config['period_m'])[None,:])
                        for j,z in zip(config['harmonics'],predicted_traces))
    peaks,q,f,actual_power=negative_branch_peaks(times,actual_space,config['dx_m'],spatial_ks)
    model_peaks,_,_,predicted_power=negative_branch_peaks(times,predicted_space,config['dx_m'],spatial_ks)
    for a,b in zip(peaks,model_peaks):a['frequency_domain_FFT_peak_GHz']=b['correct_peak_GHz']
    data=[times/1e-9]
    labels=['time_ns']
    for harmonic,actual,predicted in zip(config['harmonics'],actual_traces,predicted_traces):
        data.extend([actual.real,actual.imag,predicted.real,predicted.imag])
        labels.extend([f'oommf_q{harmonic}_real',f'oommf_q{harmonic}_imag',f'spinfreq_q{harmonic}_real',f'spinfreq_q{harmonic}_imag'])
    np.savetxt(output/'complex_traces.csv',np.column_stack(data),delimiter=',',comments='',header=','.join(labels))
    columns=[int(np.argmin(abs(q-k))) for k in spatial_ks];keep=f<60e9
    np.savetxt(output/'spectra.csv',np.column_stack([f[keep]/1e9,*[actual_power[keep,c] for c in columns],
        *[predicted_power[keep,c] for c in columns]]),delimiter=',',comments='',
        header='frequency_GHz,'+','.join([f'OOMMF_k={k/1e9:.8g}' for k in spatial_ks]+[f'spinfreq_k={k/1e9:.8g}' for k in spatial_ks]))
    raw=output/'oommf';raw.mkdir(exist_ok=True);hashes={}
    files=[directory/'configuration.json',directory/'equilibrium.mif',directory/'ringdown.mif',
           directory/'equilibrium.odt',directory/'ringdown.odt',directory/'initial.ovf',
           next(directory.glob('equilibrium-*Spin*.omf'))]
    for name in ['execution.json','runtime.json','equilibrium.log','ringdown.log']:
        if (directory/name).exists():files.append(directory/name)
    for path in files:
        content=path.read_bytes();hashes[path.name]=hashlib.sha256(content).hexdigest()
        if path.suffix in ['.odt','.ovf','.omf']:
            (raw/(path.name+'.gz')).write_bytes(gzip.compress(content,mtime=0))
        else:shutil.copyfile(path,raw/path.name)
    audit=fft_audit(output)
    summary=dict(configuration=config,reference_type='Independently executed nonlinear CPU OOMMF, periodic x, open y',
        analysis_environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
            platform=platform.platform()),
        samples=len(times),first_time_s=float(times[0]),last_time_s=float(times[-1]),
        frequency_bin_GHz=float((f[1]-f[0])/1e9),static_max_component_difference=profile_error,
        spinfreq_torque_T=state.torque_T,harmonics=records,FFT_peaks=peaks,parity_audit=audit,
        raw_reference_sha256=hashes,gates=dict(complete_four_ns_run=bool(complete and config['duration_ns']>=4),
            static_profile_error_below_1e_5=bool(profile_error<1e-5),
            complex_trace_errors_below_1_percent=bool(max(r['relative_complex_trace_L2_error'] for r in records)<.01),
            FFT_peak_discrepancy_within_one_bin=bool(max(abs(p['correct_peak_GHz']-p['frequency_domain_FFT_peak_GHz']) for p in peaks)<=(f[1]-f[0])/1e9*1.01)),
        paper_finite_pulse_reproduction=False,full_P4_release_gate_closed=False,
        limitations=['Two signed wavevector pairs in a periodic 128 nm strip, not a continuous dispersion map.',
            'Small initial perturbation and free ringdown, not the finite 2000 nm, 40 mT localized pulse.',
            'Modern Oxs_DMI_Cnv_z bond-boundary operator, not proof of the exact historical solver version.',
            'The even-FFT row-reversal bias is proven; historical MuMax snapshot parity is not known.',
            'Published OOMMF/Fidimag fitted-band discrepancies are only partly explained by this audit.'])
    summary['all_executed_gates_passed']=bool(all(summary['gates'].values()))
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    plot(output,times,actual_traces,predicted_traces,f,actual_power,predicted_power,columns,spatial_ks)
    return summary


def plot(output,times,actual,predicted,f,power,model,columns,ks):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,6),layout='constrained')
    for row,(a,b) in enumerate(zip(actual,predicted)):
        axes[row,0].plot(times/1e-9,a.real,label='OOMMF Re',color='black')
        axes[row,0].plot(times/1e-9,b.real,'--',label='spinfreq Re')
        axes[row,0].plot(times/1e-9,a.imag,label='OOMMF Im',alpha=.7)
        axes[row,0].plot(times/1e-9,b.imag,'--',label='spinfreq Im',alpha=.7)
        axes[row,0].set(xlim=(0,.5),xlabel='Time (ns)',ylabel=f'Complex Fourier mx, harmonic {row+1}')
        for col in [2*row,2*row+1]:
            ix=columns[col];scale=power[:,ix].max()
            axes[row,1].semilogy(f/1e9,power[:,ix]/scale,label=f'OOMMF k={ks[col]/1e9:.4f}')
            axes[row,1].semilogy(f/1e9,model[:,ix]/scale,'--',label='spinfreq same window')
        axes[row,1].set(xlim=(5,60),ylim=(1e-5,2),xlabel='Frequency (GHz)',ylabel='Normalized power')
        for ax in axes[row]:ax.legend(fontsize=7)
    for ext in ['png','pdf']:fig.savefig(output/f'comparison.{ext}',dpi=180)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','analyze','audit','scaling','restore'])
    parser.add_argument('--workdir',type=Path,default=Path('results/dmi_temporal'))
    parser.add_argument('--runtime',type=Path)
    parser.add_argument('--duration-ns',type=float,default=4.)
    parser.add_argument('--amplitude',type=float,default=1e-4)
    parser.add_argument('--output',type=Path,default=Path('validation/dmi_temporal'))
    parser.add_argument('--half-output',type=Path,default=Path('validation/dmi_temporal/half_amplitude'))
    parser.add_argument('--reference',type=Path,default=Path('validation/dmi_temporal'))
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.action=='restore':restore_reference(args.reference,args.workdir)
    if args.action in ['prepare','run']:
        if args.action=='run' and args.runtime is None:parser.error('--runtime is required to execute OOMMF')
        prepare(args.workdir,args.duration_ns,args.amplitude)
        if args.action=='run':execute(args.workdir,args.runtime)
    if args.action in ['analyze','run']:
        result=analyze(args.workdir,args.output)
        if args.check and not result['all_executed_gates_passed']:raise SystemExit('Temporal comparison gate failed')
    if args.action=='audit':args.output.mkdir(parents=True,exist_ok=True);print(json.dumps(fft_audit(args.output),indent=2))
    if args.action=='scaling':
        result=amplitude_scaling(args.output,args.half_output);print(json.dumps(result,indent=2))
        if args.check and not result['all_executed_gates_passed']:raise SystemExit('Amplitude scaling gate failed')
