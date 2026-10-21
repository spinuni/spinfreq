"""Independent OOMMF multitone susceptibility, turn-on and amplitude scaling.

Uses an independently relaxed OOMMF skyrmion as the common initial state.
Only scalar mean magnetization is recorded here; spatial mode validation is
provided separately by skyrmion_temporal.py. Execute OOMMF jobs serially.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import scipy

from spinfreq import ConfinedFilm,Material,ModalResponse,lattice_seed,refine_equilibrium
from spinfreq.model import MU0
from spinfreq.ovf import read_ovf
from skyrmion_temporal import archive_reference,restore_reference
from dmi_temporal import read_odt,runtime_source_hashes


def prepare(directory,equilibrium_directory,amplitude_T=1e-6,duration_ns=8.,ramp_ns=2.,steady_ns=4.,
            frequencies_GHz=(15.8,16.3,16.8,37.2,38.,38.8),absolute_step_error_deg=1e-7,max_step_ps=100.):
    directory=Path(directory).resolve();source=Path(equilibrium_directory).resolve()
    if directory.exists() and any(directory.iterdir()):raise FileExistsError('Use an empty run directory')
    if len(frequencies_GHz)!=6 or not np.all(np.isfinite(frequencies_GHz)) or min(frequencies_GHz)<=0 or len(set(frequencies_GHz))!=6:
        raise ValueError('Require six distinct positive tone frequencies')
    if not 0<amplitude_T<=1e-5 or not np.all(np.isfinite([amplitude_T,duration_ns,ramp_ns,steady_ns])):
        raise ValueError('Require finite timing and 0 < amplitude <= 10 microtesla per tone')
    if not 0<ramp_ns<steady_ns<duration_ns or abs(duration_ns*500-round(duration_ns*500))>1e-6:
        raise ValueError('Require 0 < ramp < measurement start < duration, with a multiple of 2 ps')
    if not np.isfinite(absolute_step_error_deg) or absolute_step_error_deg<=0:raise ValueError('Require positive angular error tolerance')
    if not np.isfinite(max_step_ps) or max_step_ps<=0:raise ValueError('Require positive maximum timestep')
    original=json.loads((source/'configuration.json').read_text())
    if original['dmi_boundary']!='bond':raise ValueError('This OOMMF reference uses the bond boundary')
    states=list(source.glob('equilibrium-*Spin*.omf'))
    if len(states)!=1:raise ValueError('Require exactly one independent OOMMF equilibrium')
    m,meta=read_ovf(states[0])
    if m.shape!=(original['ny'],original['nx'],3):raise ValueError('Equilibrium/configuration shape mismatch')
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'equilibrium.ovf').write_bytes(states[0].read_bytes())
    (directory/'source_configuration.json').write_bytes((source/'configuration.json').read_bytes())
    config={key:original[key] for key in ['nx','ny','dx_m','dy_m','thickness_m','width_m','material','field_T','dmi_boundary','oommf_D_J_m2']}
    config.update(amplitude_T=amplitude_T,duration_ns=duration_ns,ramp_ns=ramp_ns,steady_start_ns=steady_ns,
        frequencies_GHz=list(frequencies_GHz),axes=[2,2,2,0,0,0],sample_ps=2.,
        reference_equilibrium_sha256=hashlib.sha256(states[0].read_bytes()).hexdigest(),
        OOMMF_absolute_step_error_deg=absolute_step_error_deg,OOMMF_relative_step_error=-1.,
        OOMMF_max_timestep_s=max_step_ps*1e-12,
        source_configuration_sha256=hashlib.sha256((source/'configuration.json').read_bytes()).hexdigest())
    p=config['material'];L=config['width_m'];dz=config['thickness_m'];field=config['field_T']
    lines=f'''# MIF 2.2
SetOptions {{basename driven scalar_output_format %.17g}}
set mu0 {MU0:.17g}
set amplitude {amplitude_T:.17g}
set ramp {ramp_ns*1e-9:.17g}
set frequencies {{{' '.join(str(f*1e9) for f in frequencies_GHz)}}}
set axes {{2 2 2 0 0 0}}
proc Drive {{t}} {{
 global mu0 amplitude ramp frequencies axes
 set envelope 1.; set derivative 0.
 if {{$t < $ramp}} {{
  set envelope [expr {{.5*(1-cos(acos(-1)*$t/$ramp))}}]
  set derivative [expr {{.5*acos(-1)/$ramp*sin(acos(-1)*$t/$ramp)}}]
 }}
 set b {{0. 0. 0.}}; set db {{0. 0. 0.}}
 foreach f $frequencies axis $axes {{
  set w [expr {{2*acos(-1)*$f}}]
  lset b $axis [expr {{[lindex $b $axis]+$amplitude*$envelope*cos($w*$t)/$mu0}}]
  lset db $axis [expr {{[lindex $db $axis]+$amplitude*($derivative*cos($w*$t)-$envelope*$w*sin($w*$t))/$mu0}}]
 }}
 return [concat $b $db]
}}
Specify Oxs_BoxAtlas:atlas {{name film xrange {{0 {L:.17g}}} yrange {{0 {L:.17g}}} zrange {{0 {dz:.17g}}}}}
Specify Oxs_RectangularMesh:mesh {{cellsize {{{config['dx_m']:.17g} {config['dy_m']:.17g} {dz:.17g}}} atlas :atlas}}
Specify Oxs_UniformExchange {{A {p['A']:.17g}}}
Specify Oxs_Demag {{}}
Specify Oxs_UniaxialAnisotropy {{K1 {p['K']:.17g} axis {{0 0 1}}}}
Specify Oxs_DMI_Cnv_z {{atlas :atlas default_D {config['oommf_D_J_m2']:.17g} D {{film film {config['oommf_D_J_m2']:.17g}}}}}
Specify Oxs_FixedZeeman {{field {{{field[0]/MU0:.17g} {field[1]/MU0:.17g} {field[2]/MU0:.17g}}}}}
Specify Oxs_ScriptUZeeman {{script_args total_time script Drive}}
Specify Oxs_RungeKuttaEvolve:evolver {{alpha {p['alpha']:.17g} gamma_G {p['gamma']*MU0:.17g} method rkf54 absolute_step_error {absolute_step_error_deg:.17g} relative_step_error -1 max_timestep {max_step_ps*1e-12:.17g}}}
Specify Oxs_TimeDriver {{evolver :evolver mesh :mesh Ms {p['Ms']:.17g} m0 {{Oxs_FileVectorField {{atlas :atlas file equilibrium.ovf norm 1}}}} stopping_time 2e-12 stage_count {round(duration_ns*500)} checkpoint_interval -1}}
Destination archive mmArchive
Schedule DataTable archive Stage 1
'''
    (directory/'driven.mif').write_text(lines)
    (directory/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    return config


def execute(directory,runtime_file):
    directory=Path(directory).resolve();runtime=json.loads(Path(runtime_file).read_text())
    if (directory/'driven.odt').exists():raise FileExistsError('Use a fresh run directory')
    env=os.environ.copy();env.update(runtime.get('env',{}));start=time.perf_counter()
    with (directory/'driven.log').open('w') as log:
        subprocess.run([runtime['tclsh'],runtime['oommf_tcl'],'boxsi','-exitondone','1','-kill','archive','-threads','1',
            '-logfile',str(directory/'driven.errors'),str(directory/'driven.mif')],cwd=directory,env=env,
            stdout=log,stderr=subprocess.STDOUT,check=True)
    read_odt(directory/'driven.odt')
    hashes=runtime_source_hashes(runtime)
    for name in ['uniaxialanisotropy.cc','scriptuzeeman.cc']:
        relative='app/oxs/ext/'+name;hashes[relative]=hashlib.sha256((Path(runtime['oommf_tcl']).parent/relative).read_bytes()).hexdigest()
    (directory/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    (directory/'execution.json').write_text(json.dumps(dict(runtime=runtime,threads=1,
        elapsed_s=time.perf_counter()-start,source_sha256=hashes),indent=2)+'\n')


def demodulate(times,signals,frequencies_Hz,start_s):
    """Known-tone least squares: phasor=cosine coefficient-i*sine coefficient."""
    keep=times>=start_s;t=times[keep];y=signals[keep]
    phase=2*np.pi*t[:,None]*np.asarray(frequencies_Hz)[None,:]
    design=np.column_stack([np.ones(len(t)),np.cos(phase),np.sin(phase)])
    if len(t)<=design.shape[1]:raise ValueError('Too few demodulation samples')
    condition=float(np.linalg.cond(design))
    if condition>1e6:raise ValueError('Tone demodulation is ill-conditioned')
    coefficients=np.linalg.lstsq(design,y,rcond=None)[0];n=len(frequencies_Hz)
    return coefficients[1:n+1]-1j*coefficients[n+1:],dict(design_condition_number=condition,
        relative_residual=float(np.linalg.norm(design@coefficients-y)/np.linalg.norm(y)),samples=len(t))


def load_observation(directory):
    directory=Path(directory);config=json.loads((directory/'configuration.json').read_text())
    table=read_odt(directory/'driven.odt');times=table['Oxs_TimeDriver::Simulation time']
    expected=round(config['duration_ns']*1000/config['sample_ps'])
    if len(times)!=expected or not np.isclose(times[-1],config['duration_ns']*1e-9,rtol=1e-8,atol=0):raise ValueError('Incomplete driven observation')
    if not np.allclose(np.diff(times),config['sample_ps']*1e-12,rtol=1e-8,atol=1e-20):raise ValueError('Unexpected sample times')
    m,_=read_ovf(directory/'equilibrium.ovf')
    signals=np.column_stack([table[f'Oxs_TimeDriver::m{axis}'] for axis in 'xyz'])-m.mean(axis=(0,1))
    return config,times,signals,m


def check_tolerance(full_directory,tight_directory,output):
    config,times,actual,m=load_observation(full_directory)
    tight,t_tight,y_tight,m_tight=load_observation(tight_directory)
    key='OOMMF_absolute_step_error_deg'
    ignored={key,'OOMMF_max_timestep_s'}
    base_cap=config.get('OOMMF_max_timestep_s',1e-10);tight_cap=tight.get('OOMMF_max_timestep_s',1e-10)
    if not (tight[key]<=config[key] and tight_cap<=base_cap and (tight[key]<config[key] or tight_cap<base_cap)) or \
            {k:v for k,v in config.items() if k not in ignored}!={k:v for k,v in tight.items() if k not in ignored}:
        raise ValueError('Require identical physics and stricter angular error or timestep control without loosening either')
    if times.shape!=t_tight.shape or not np.allclose(times,t_tight,rtol=0,atol=1e-19) or not np.array_equal(m,m_tight):
        raise ValueError('Tolerance comparison must share sampling and equilibrium')
    frequencies=np.array(config['frequencies_GHz'])*1e9
    a,_=demodulate(times,actual,frequencies,config['steady_start_ns']*1e-9)
    b,_=demodulate(t_tight,y_tight,frequencies,config['steady_start_ns']*1e-9)
    errors=[float(np.linalg.norm(x-y)/np.linalg.norm(y)) for x,y in zip(a,b)]
    trace=float(np.linalg.norm(actual-y_tight)/np.linalg.norm(y_tight))
    base_steps=int(read_odt(Path(full_directory)/'driven.odt')['Oxs_TimeDriver::Iteration'][-1])
    tight_steps=int(read_odt(Path(tight_directory)/'driven.odt')['Oxs_TimeDriver::Iteration'][-1])
    capped=tight.get('OOMMF_max_timestep_s',1e-10)<config.get('OOMMF_max_timestep_s',1e-10)
    step_refined=tight_steps>1.5*base_steps
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    hashes,digest=archive_reference(tight_directory,output/'tight')
    (output/'tight/summary.json').write_text(json.dumps(dict(configuration=tight,raw_reference_sha256=hashes,
        reference_archive_sha256=digest),indent=2)+'\n')
    result=dict(base_absolute_error_deg=config[key],tight_absolute_error_deg=tight[key],
        base_integration_steps=base_steps,tight_integration_steps=tight_steps,
        timestep_cap_s=tight.get('OOMMF_max_timestep_s',1e-10),time_step_refinement_demonstrated=bool(step_refined),
        relative_complex_response_differences=errors,relative_full_trace_difference=trace,
        criterion_percent=.5,all_executed_gates_passed=bool(max(errors)<.005 and trace<.005 and (not capped or step_refined)),
        reference_archive_sha256=digest)
    (output/'tolerance_check.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def analyze(full_directory,half_directory,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    config,times,actual,external=load_observation(full_directory)
    half,t_half,actual_half,external_half=load_observation(half_directory)
    if config['amplitude_T']!=2*half['amplitude_T'] or {k:v for k,v in config.items() if k!='amplitude_T'}!={k:v for k,v in half.items() if k!='amplitude_T'}:
        raise ValueError('Require identical problems with exactly halved field amplitudes')
    if times.shape!=t_half.shape or not np.allclose(times,t_half,rtol=0,atol=1e-19) or not np.array_equal(external,external_half):
        raise ValueError('Independent runs must share input equilibrium and sampling')
    film=ConfinedFilm(nx=config['nx'],ny=config['ny'],dx=config['dx_m'],dy=config['dy_m'],thickness=config['thickness_m'],
        material=Material(**config['material']),field_T=config['field_T'],dmi_boundary=config['dmi_boundary'])
    state=refine_equilibrium(film,film.relax(lattice_seed(film),maxiter=10000,tolerance_T=1e-7).m,tolerance_T=1e-9)
    if not state.converged:raise RuntimeError('Independent frequency-domain equilibrium failed')
    prepared=ModalResponse(film,state.m)
    if prepared.values.real.max()>=0:raise RuntimeError('Unstable equilibrium')
    frequencies=np.array(config['frequencies_GHz'])*1e9;drives=np.eye(3)[config['axes']]*config['amplitude_T']
    stationary=[];residuals=[]
    for f,drive in zip(frequencies,drives):
        stationary.append(prepared.response([f],drive)[0].mean(axis=(0,1)))
        residuals.append(float(prepared.last_response_residuals[0]))
    stationary=np.array(stationary)
    predicted=prepared.ramped_mean_response(times,frequencies,drives,config['ramp_ns']*1e-9)
    measured,diagnostics=demodulate(times,actual,frequencies,config['steady_start_ns']*1e-9)
    measured_half,half_diagnostics=demodulate(times,actual_half,frequencies,config['steady_start_ns']*1e-9)
    window_prediction,_=demodulate(times,predicted,frequencies,config['steady_start_ns']*1e-9)
    volume=film.nx*film.ny*film.dx*film.dy*film.thickness;records=[]
    for j,(frequency,axis) in enumerate(zip(frequencies,config['axes'])):
        scale=.5*film.material.Ms*volume*2*np.pi*frequency
        p_actual=-scale*config['amplitude_T']*measured[j,axis].imag
        p_half=-scale*half['amplitude_T']*measured_half[j,axis].imag
        p_model=-scale*config['amplitude_T']*stationary[j,axis].imag
        record=dict(frequency_GHz=float(frequency/1e9),drive_axis=int(axis),
            relative_complex_vector_error=float(np.linalg.norm(measured[j]-stationary[j])/np.linalg.norm(stationary[j])),
            driven_component_amplitude_error_percent=float(100*abs(abs(measured[j,axis])/abs(stationary[j,axis])-1)),
            driven_component_phase_error_deg=float(np.angle(measured[j,axis]/stationary[j,axis])*180/np.pi),
            finite_window_linear_bias=float(np.linalg.norm(window_prediction[j]-stationary[j])/np.linalg.norm(stationary[j])),
            relative_halving_error=float(np.linalg.norm(2*measured_half[j]-measured[j])/np.linalg.norm(measured[j])),
            response_squared_ratio=float(np.linalg.norm(measured_half[j])**2/np.linalg.norm(measured[j])**2),
            OOMMF_absorbed_power_W=float(p_actual),linear_absorbed_power_W=float(p_model),
            absorbed_power_ratio_half_over_full=float(p_half/p_actual),shifted_system_relative_residual=residuals[j])
        records.append(record)
    trace_error=float(np.linalg.norm(actual-predicted)/np.linalg.norm(predicted))
    half_trace_error=float(np.linalg.norm(actual_half-.5*predicted)/np.linalg.norm(.5*predicted))
    scaling_error=float(np.linalg.norm(2*actual_half-actual)/np.linalg.norm(actual))
    references={}
    for name,directory,c in [('full',full_directory,config),('half',half_directory,half)]:
        hashes,digest=archive_reference(directory,output/name)
        reference=dict(configuration=c,raw_reference_sha256=hashes,reference_archive_sha256=digest)
        (output/name/'summary.json').write_text(json.dumps(reference,indent=2)+'\n');references[name]=digest
    gates=dict(six_complex_responses_within_2_percent=max(r['relative_complex_vector_error'] for r in records)<.02,
        phase_errors_below_1_degree=max(abs(r['driven_component_phase_error_deg']) for r in records)<1,
        full_and_half_transient_errors_below_2_percent=max(trace_error,half_trace_error)<.02,
        halving_errors_below_1_percent=max(r['relative_halving_error'] for r in records)<.01,
        squared_response_ratios_within_1_percent_of_quarter=max(abs(r['response_squared_ratio']/.25-1) for r in records)<.01,
        absorption_ratios_within_1_percent_of_quarter=max(abs(r['absorbed_power_ratio_half_over_full']/.25-1) for r in records)<.01,
        absorption_positive=all(r['OOMMF_absorbed_power_W']>0 and r['linear_absorbed_power_W']>0 for r in records))
    gates['centers_stronger_than_side_tones']=bool(all(abs(measured[group+1,config['axes'][group]])>max(abs(measured[group,config['axes'][group]]),abs(measured[group+2,config['axes'][group]])) for group in [0,3]))
    summary=dict(configuration=config,analysis_environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        static_max_component_difference=float(abs(state.m-external).max()),relative_full_transient_L2_error=trace_error,
        relative_half_transient_L2_error=half_trace_error,relative_time_trace_halving_error=scaling_error,
        demodulation=diagnostics,half_demodulation=half_diagnostics,tones=records,reference_archive_sha256=references,
        gates=gates,all_executed_gates_passed=bool(all(gates.values())),
        limitations=['Mean magnetization response to six simultaneous weak tones; spatial forced-response fields are not measured here.',
            'This matched discrete problem does not establish continuum mesh or thickness accuracy.',
            'Small-signal susceptibility and startup transients; nonlinear frequency-comb generation is not validated.'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    np.savetxt(output/'mean_traces.csv',np.column_stack([times/1e-9,actual,predicted,actual_half]),delimiter=',',comments='',
        header='time_ns,OOMMF_x,OOMMF_y,OOMMF_z,linear_x,linear_y,linear_z,OOMMF_half_x,OOMMF_half_y,OOMMF_half_z')
    rows=[]
    for j,f in enumerate(frequencies):rows.append([f/1e9,config['axes'][j],*measured[j].real,*measured[j].imag,*stationary[j].real,*stationary[j].imag,*measured_half[j].real,*measured_half[j].imag])
    np.savetxt(output/'complex_response.csv',np.array(rows),delimiter=',',comments='',header='frequency_GHz,drive_axis,OOMMF_re_x,OOMMF_re_y,OOMMF_re_z,OOMMF_im_x,OOMMF_im_y,OOMMF_im_z,linear_re_x,linear_re_y,linear_re_z,linear_im_x,linear_im_y,linear_im_z,half_re_x,half_re_y,half_re_z,half_im_x,half_im_y,half_im_z')
    plot(output,config,times,actual,predicted,measured,stationary,records)
    print(json.dumps(summary,indent=2),flush=True)
    return summary


def plot(output,config,times,actual,predicted,measured,stationary,records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,6),layout='constrained')
    for group,(offset,axis) in enumerate([(0,2),(3,0)]):
        ix=np.arange(offset,offset+3);f=np.array(config['frequencies_GHz'])[ix]
        axes[0,group].plot(f,abs(measured[ix,axis])/config['amplitude_T'],'o-',label='OOMMF')
        axes[0,group].plot(f,abs(stationary[ix,axis])/config['amplitude_T'],'x--',label='Frequency solver')
        axes[0,group].set(xlabel='Frequency (GHz)',ylabel='Mean response amplitude / B (1/T)');axes[0,group].legend()
        axes[1,group].plot(f,np.angle(measured[ix,axis])*180/np.pi,'o-',label='OOMMF')
        axes[1,group].plot(f,np.angle(stationary[ix,axis])*180/np.pi,'x--',label='Frequency solver')
        axes[1,group].set(xlabel='Frequency (GHz)',ylabel='Drive-relative phase (deg)');axes[1,group].legend()
    for ext in ['png','pdf']:fig.savefig(output/f'complex_response.{ext}',dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,5),layout='constrained')
    for ax,axis in zip(axes,[0,2]):
        ax.plot(times/1e-9,actual[:,axis],label='OOMMF');ax.plot(times/1e-9,predicted[:,axis],'--',label='Exact linear turn-on')
        ax.set(xlim=(0,3),xlabel='Time (ns)',ylabel=f'Mean delta m{"xyz"[axis]}');ax.legend()
    for ext in ['png','pdf']:fig.savefig(output/f'turn_on.{ext}',dpi=180)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','analyze','restore','tolerance'])
    parser.add_argument('--workdir',type=Path,default=Path('results/driven-full'))
    parser.add_argument('--half-workdir',type=Path,default=Path('results/driven-half'))
    parser.add_argument('--tight-workdir',type=Path,default=Path('results/driven-tight'))
    parser.add_argument('--equilibrium-directory',type=Path)
    parser.add_argument('--runtime',type=Path)
    parser.add_argument('--amplitude-uT',type=float,default=1.)
    parser.add_argument('--absolute-step-error-deg',type=float,default=1e-7)
    parser.add_argument('--max-step-ps',type=float,default=100.)
    parser.add_argument('--frequencies-GHz',type=float,nargs=6,default=[15.8,16.3,16.8,37.2,38.,38.8])
    parser.add_argument('--output',type=Path,default=Path('validation/driven_response'))
    parser.add_argument('--reference',type=Path,default=Path('validation/driven_response/full'))
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.action in ['prepare','run']:
        if args.equilibrium_directory is None:parser.error('--equilibrium-directory is required')
        if args.action=='run' and args.runtime is None:parser.error('--runtime is required')
        prepare(args.workdir,args.equilibrium_directory,args.amplitude_uT*1e-6,frequencies_GHz=args.frequencies_GHz,
                absolute_step_error_deg=args.absolute_step_error_deg,max_step_ps=args.max_step_ps)
        if args.action=='run':execute(args.workdir,args.runtime)
    if args.action=='restore':restore_reference(args.reference,args.workdir)
    if args.action=='tolerance':
        result=check_tolerance(args.workdir,args.tight_workdir,args.output);print(json.dumps(result,indent=2))
        if args.check and not result['all_executed_gates_passed']:raise SystemExit('Time-integrator tolerance check failed')
    if args.action=='analyze':
        result=analyze(args.workdir,args.half_workdir,args.output)
        if args.check and not result['all_executed_gates_passed']:raise SystemExit('Driven response validation failed')
