"""Independent CPU OOMMF skyrmion profiles, ringdowns and complex mode fields.

The square-film material follows Liu 2024; the matched modern OOMMF bond
boundary is an explicit variation of that paper's MuMax boundary prescription.
Run external simulations serially: OOMMF's archive service is shared.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import time

import numpy as np
import scipy
from scipy.linalg import eig, eigvals, solve
from scipy.optimize import least_squares
from scipy.signal import find_peaks

from spinfreq import ConfinedFilm, Material, lattice_seed, refine_equilibrium
from spinfreq.model import MU0
from spinfreq.ovf import read_ovf, write_ovf
from dmi_temporal import read_odt, runtime_source_hashes
from fmr_standard_problem import modal_assurance


def prepare(directory,field_T=0.,cells=20,duration_ns=4.,amplitude=1e-4):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    if any(directory.iterdir()):raise FileExistsError('Use an empty run directory; analyze or restore existing references separately')
    if cells<8 or cells>64 or int(cells)!=cells:raise ValueError('Require 8..64 cells per axis')
    if not np.isfinite(field_T) or abs(field_T)>.2:raise ValueError('Field outside this benchmark range')
    if not np.isfinite(duration_ns) or duration_ns<=0 or abs(duration_ns*500-round(duration_ns*500))>1e-6:
        raise ValueError('Duration must be a positive integer multiple of 2 ps')
    if not np.isfinite(amplitude) or not 0<amplitude<=1e-3:raise ValueError('Require 0 < amplitude <= 1e-3')
    dx=40e-9/cells
    material=dict(Ms=580e3,A=15e-12,D=.003,K=.6e6,alpha=.01,gamma=1.7595e11)
    film=ConfinedFilm(nx=cells,ny=cells,dx=dx,thickness=1e-9,material=Material(**material),dmi_boundary='bond')
    write_ovf(directory/'seed.ovf',lattice_seed(film),dx,dx,1e-9)
    common=f'''# MIF 2.2
SetOptions {{basename @NAME@ vector_field_output_format {{binary 8}} scalar_output_format %.17g}}
Specify Oxs_BoxAtlas:atlas {{name film xrange {{0 40e-9}} yrange {{0 40e-9}} zrange {{0 1e-9}}}}
Specify Oxs_RectangularMesh:mesh {{cellsize {{{dx:.17g} {dx:.17g} 1e-9}} atlas :atlas}}
Specify Oxs_UniformExchange {{A 15e-12}}
Specify Oxs_Demag {{}}
Specify Oxs_UniaxialAnisotropy {{K1 0.6e6 axis {{0 0 1}}}}
Specify Oxs_DMI_Cnv_z {{atlas :atlas default_D -3e-3 D {{film film -3e-3}}}}
Specify Oxs_FixedZeeman {{field {{0 0 {field_T/MU0:.17g}}}}}
'''
    static=common.replace('@NAME@','equilibrium')+'''Specify Oxs_CGEvolve:evolver {}
Specify Oxs_MinDriver {evolver :evolver mesh :mesh Ms 580e3 m0 {Oxs_FileVectorField {atlas :atlas file seed.ovf norm 1}} stopping_mxHxm 0.0001 checkpoint_interval -1}
Destination archive mmArchive
Schedule DataTable archive Stage 1
Schedule Oxs_MinDriver::Spin archive Stage 1
'''
    dynamic=common.replace('@NAME@','ringdown')+f'''Specify Oxs_RungeKuttaEvolve:evolver {{alpha .01 gamma_G {material['gamma']*MU0:.17g} method rkf54 absolute_step_error 1e-7 relative_step_error 1e-7}}
Specify Oxs_TimeDriver {{evolver :evolver mesh :mesh Ms 580e3 m0 {{Oxs_FileVectorField {{atlas :atlas file initial.ovf norm 1}}}} stopping_time 2e-12 stage_count {round(duration_ns*500)} checkpoint_interval -1}}
Destination archive mmArchive
Schedule DataTable archive Stage 1
Schedule Oxs_TimeDriver::Spin archive Stage 5
'''
    (directory/'equilibrium.mif').write_text(static);(directory/'ringdown.mif').write_text(dynamic)
    config=dict(nx=cells,ny=cells,dx_m=dx,dy_m=dx,thickness_m=1e-9,width_m=40e-9,
        field_T=[0,0,field_T],material=material,dmi_boundary='bond',oommf_D_J_m2=-.003,
        amplitude=amplitude,perturbation_direction=[1,0,1],duration_ns=duration_ns,sample_ps=2.,spatial_sample_ps=10.)
    (directory/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
    return config


def execute(directory,runtime_file):
    directory=Path(directory).resolve();runtime=json.loads(Path(runtime_file).read_text())
    config=json.loads((directory/'configuration.json').read_text())
    if any(directory.glob('*.odt')):raise FileExistsError('Use a fresh run directory')
    env=os.environ.copy();env.update(runtime.get('env',{}));start=time.perf_counter()
    for stage in ['equilibrium','ringdown']:
        if stage=='ringdown':
            m,_=read_ovf(next(directory.glob('equilibrium-*Spin*.omf')))
            m+=config['amplitude']*np.array(config['perturbation_direction'])
            m/=np.linalg.norm(m,axis=-1,keepdims=True)
            write_ovf(directory/'initial.ovf',m,config['dx_m'],config['dy_m'],config['thickness_m'])
        print(f'Running independent OOMMF {directory.name}: {stage}',flush=True)
        with (directory/f'{stage}.log').open('w') as log:
            subprocess.run([runtime['tclsh'],runtime['oommf_tcl'],'boxsi','-exitondone','1','-kill','archive',
                '-threads','1','-logfile',str(directory/f'{stage}.errors'),str(directory/f'{stage}.mif')],
                cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        read_odt(directory/f'{stage}.odt')
    (directory/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
    hashes=runtime_source_hashes(runtime)
    anisotropy=Path(runtime['oommf_tcl']).parent/'app/oxs/ext/uniaxialanisotropy.cc'
    hashes['app/oxs/ext/uniaxialanisotropy.cc']=hashlib.sha256(anisotropy.read_bytes()).hexdigest()
    execution=dict(runtime=runtime,threads=1,elapsed_s=time.perf_counter()-start,source_sha256=hashes)
    (directory/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')


def fit_poles(times,signals,start_ns=0.):
    """Fit three visible poles using only independent OOMMF mean signals.

    Frequencies and decay rates are nonlinear parameters; offsets and sine/cosine
    amplitudes are eliminated by linear least squares. No spinfreq poles enter.
    """
    keep=times>=start_ns*1e-9;t=times[keep]/1e-9;y=signals[keep]
    # Separate symmetry channels avoid a large in-plane mode hiding breathing.
    f=np.fft.rfftfreq(len(t),np.mean(np.diff(t)))
    spectral=abs(np.fft.rfft((y-y.mean(axis=0))*np.hanning(len(t))[:,None],axis=0))**2
    windows=[(.5,5.,0),(8.,25.,2),(28.,45.,0)];guesses=[]
    for low,high,axis in windows:
        candidates,_=find_peaks(spectral[:,axis]);candidates=candidates[(f[candidates]>low)&(f[candidates]<high)]
        if not len(candidates):raise RuntimeError('No independent reference peak in the predeclared mode window')
        guesses.append(f[candidates[np.argmax(spectral[candidates,axis])]])
    scale=np.maximum(np.std(y,axis=0),1e-30)
    def residual(parameters):
        waves=np.exp((-parameters[3:]+2j*np.pi*parameters[:3])[None,:]*t[:,None])
        design=np.column_stack([np.ones(len(t)),waves.real,waves.imag])
        coefficients=np.linalg.lstsq(design,y,rcond=None)[0]
        return ((design@coefficients-y)/scale).ravel()
    bounds=(np.r_[np.array(guesses)-.6,[.001]*3],np.r_[np.array(guesses)+.6,[8.]*3])
    result=least_squares(residual,np.r_[guesses,[.15,.8,1.8]],bounds=bounds,
        xtol=1e-11,ftol=1e-11,gtol=1e-11,max_nfev=300)
    if not result.success:raise RuntimeError('Independent OOMMF pole fit failed')
    return dict(start_ns=start_ns,frequencies_GHz=result.x[:3].tolist(),decay_rates_per_ns=result.x[3:].tolist(),
        pole_FWHM_GHz=(result.x[3:]/np.pi).tolist(),residual_RMS_over_channel_std=float(np.sqrt(np.mean(residual(result.x)**2))),
        FFT_initial_guesses_GHz=guesses)


def extract_mode_fields(times,fields,fit,start_ns=.2):
    keep=times>=start_ns*1e-9;t=times[keep]/1e-9
    waves=np.exp((-np.array(fit['decay_rates_per_ns'])+2j*np.pi*np.array(fit['frequencies_GHz']))[None,:]*t[:,None])
    design=np.column_stack([np.ones(len(t)),waves.real,waves.imag])
    values=fields[keep].reshape(len(t),-1)
    coefficients=np.linalg.lstsq(design,values,rcond=None)[0]
    residues=(coefficients[1:4]-1j*coefficients[4:7])/2
    return residues.reshape(3,*fields.shape[1:]),float(np.linalg.norm(design@coefficients-values)/np.linalg.norm(values))


def archive_reference(directory,output):
    files=[p for p in Path(directory).iterdir() if p.suffix in ('.mif','.odt','.omf','.ovf','.json','.log','.errors')]
    hashes={};output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with (output/'oommf_reference.tar.gz').open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for p in sorted(files):
                    content=p.read_bytes();hashes[p.name]=hashlib.sha256(content).hexdigest()
                    info=tarfile.TarInfo(p.name);info.size=len(content);info.mode=0o644
                    archive.addfile(info,io.BytesIO(content))
    return hashes,hashlib.sha256((output/'oommf_reference.tar.gz').read_bytes()).hexdigest()


def restore_reference(reference,directory):
    reference=Path(reference);directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):raise FileExistsError('Restore requires an empty directory')
    summary=json.loads((reference/'summary.json').read_text());raw=(reference/'oommf_reference.tar.gz').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=summary['reference_archive_sha256']:raise ValueError('Reference archive hash mismatch')
    contents={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
        for member in archive:
            if not member.isfile() or Path(member.name).name!=member.name or member.name in contents:
                raise ValueError('Require unique regular-file basenames in reference archive')
            content=archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest()!=summary['raw_reference_sha256'].get(member.name):
                raise ValueError('Native reference file hash mismatch')
            contents[member.name]=content
    if set(contents)!=set(summary['raw_reference_sha256']):raise ValueError('Missing native reference files')
    directory.mkdir(parents=True,exist_ok=True)
    for name,content in contents.items():(directory/name).write_bytes(content)


def mesh_refinement(output,cells=(20,30,40),fields=(0.,.05)):
    """Fixed-size linear mesh study, separate from external-solver agreement."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True);records=[]
    for field in fields:
        for n in sorted(set(cells)):
            start=time.perf_counter()
            film=ConfinedFilm(nx=n,ny=n,dx=40e-9/n,thickness=1e-9,
                material=Material(Ms=580e3,A=15e-12,D=.003,K=.6e6,alpha=.01,gamma=1.7595e11),
                field_T=(0,0,field),dmi_boundary='bond')
            state=refine_equilibrium(film,film.relax(lattice_seed(film),maxiter=10000,tolerance_T=1e-7).m,tolerance_T=1e-9)
            if not state.converged:raise RuntimeError('Mesh-study equilibrium failed')
            matrix,_=film.linear_operator(state.m,assemble=True);values=eigvals(matrix)
            frequencies=np.sort(values.imag[values.imag>2*np.pi*1e6])[:3]/(2*np.pi*1e9)
            record=dict(field_T=field,cells=n,cell_nm=40/n,frequencies_GHz=frequencies.tolist(),
                torque_T=state.torque_T,converged=bool(state.converged),max_growth_rate_per_s=float(values.real.max()),
                seconds=time.perf_counter()-start)
            records.append(record);print(json.dumps(record),flush=True)
    refinements=[]
    for field in fields:
        same=[r for r in records if r['field_T']==field]
        changes=[(100*abs(np.array(a['frequencies_GHz'])/b['frequencies_GHz']-1)).tolist() for a,b in zip(same,same[1:])]
        refinements.append(dict(field_T=field,pair_changes_percent=changes,
            finest_pair_change_below_1_percent=bool(len(changes) and max(changes[-1])<1)))
    summary=dict(results=records,refinements=refinements,project_finest_pair_threshold_percent=1.,
        continuum_error_bound=False,external_fine_mesh_run_executed=False)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    np.savetxt(output/'frequencies.csv',np.array([[r['field_T'],r['cells'],r['cell_nm'],*r['frequencies_GHz']] for r in records]),
        delimiter=',',comments='',header='field_T,cells_per_axis,cell_nm,f1_GHz,f2_GHz,f3_GHz')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(11,3.4),layout='constrained')
    for field in fields:
        same=[r for r in records if r['field_T']==field]
        for j,ax in enumerate(axes):
            ax.plot([r['cell_nm'] for r in same],[r['frequencies_GHz'][j] for r in same],'o-',label=f'{field*1e3:g} mT')
            ax.set(xlabel='Cell width (nm)',ylabel=f'Mode {j+1} frequency (GHz)');ax.legend()
    for ext in ['png','pdf']:fig.savefig(output/f'mesh_convergence.{ext}',dpi=180)
    plt.close(fig)
    return summary


def qualify_suite(reference,mesh_reference,output):
    """Combine two executed fine-grid cases with the fixed-size mesh study.

    This qualifies only the stated thin-film model and first three modes. It
    does not qualify a thickness envelope, general stability or deployment.
    """
    reference=Path(reference);mesh_reference=Path(mesh_reference);output=Path(output)
    study=json.loads(mesh_reference.read_text());records=[]
    expected_material=dict(Ms=580e3,A=15e-12,D=.003,K=.6e6,alpha=.01,gamma=1.7595e11)
    for name,field in [('field_0mT',0.),('field_50mT',.05)]:
        path=reference/name/'summary.json';case=json.loads(path.read_text());config=case['configuration']
        if config['material']!=expected_material or config['field_T']!=[0,0,field] or config['dmi_boundary']!='bond':
            raise ValueError('Mesh qualification requires the identical specified material, field and boundary')
        n=config['nx']
        if config['ny']!=n or not np.allclose([n*config['dx_m'],n*config['dy_m'],config['thickness_m']],
            [40e-9,40e-9,1e-9],rtol=1e-12,atol=0):raise ValueError('Mesh qualification geometry mismatch')
        mesh=sorted([r for r in study['results'] if r['field_T']==field],key=lambda r:r['cells'])
        if len(mesh)<2:raise ValueError('Need at least two fixed-size mesh points per field')
        pair=mesh[-2:];changes=100*abs(np.array(pair[0]['frequencies_GHz'])/pair[1]['frequencies_GHz']-1)
        matched=[r for r in pair if r['cells']==n]
        if not matched:raise ValueError('Executed dynamics must use a mesh in the finest qualified pair')
        frequencies=np.array([m['linear_frequency_GHz'] for m in case['modes']])
        same_poles=np.max(abs(frequencies/np.array(matched[0]['frequencies_GHz'])-1))<1e-6
        gates=dict(independent_case_passed=bool(case['all_executed_gates_passed']),
            complete_at_least_four_ns=config['duration_ns']>=4,
            full_trace_within_2_percent=case['relative_full_spatial_trace_L2_error']<.02,
            frequencies_within_2_percent=max(m['frequency_difference_percent'] for m in case['modes'])<2,
            complex_mode_MAC_above_0_95=min(m['complex_vector_MAC'] for m in case['modes'])>.95,
            finest_pair_changes_below_1_percent=bool(max(changes)<1),same_linear_poles=bool(same_poles),
            equilibria_converged_and_stable=bool(case['spinfreq_torque_T']<1e-8 and case['maximum_growth_rate_per_s']<0 and
                all(r['converged'] and r['max_growth_rate_per_s']<0 for r in pair)))
        records.append(dict(case=name,cells=n,cell_nm=config['dx_m']/1e-9,finest_pair_changes_percent=changes.tolist(),
            gates=gates,passed=bool(all(gates.values())),case_summary_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            native_reference_archive_sha256=case['reference_archive_sha256']))
    summary=dict(scope='40 x 40 x 1 nm square, specified material, bond DMI, Bz=0/50 mT, first three modes',
        results=records,mesh_reference_sha256=hashlib.sha256(mesh_reference.read_bytes()).hexdigest(),
        P5_two_field_fine_mesh_evidence_passed=bool(all(r['passed'] for r in records)),
        continuum_error_bound=False,general_thickness_envelope_qualified=False,full_simulator_release_qualified=False)
    output.mkdir(parents=True,exist_ok=True)
    (output/'qualification.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def analyze(directory,output):
    directory=Path(directory);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    config=json.loads((directory/'configuration.json').read_text());table=read_odt(directory/'ringdown.odt')
    times=table['Oxs_TimeDriver::Simulation time']
    expected=round(config['duration_ns']*1e3/config['sample_ps'])
    if len(times)!=expected or not np.isclose(times[-1],config['duration_ns']*1e-9,rtol=1e-8,atol=0):
        raise ValueError('Incomplete scalar reference duration')
    if not np.allclose(np.diff(times),config['sample_ps']*1e-12,rtol=1e-8,atol=1e-20):raise ValueError('Unexpected reference sampling')
    external,_=read_ovf(next(directory.glob('equilibrium-*Spin*.omf')));initial,_=read_ovf(directory/'initial.ovf')
    film=ConfinedFilm(nx=config['nx'],ny=config['ny'],dx=config['dx_m'],dy=config['dy_m'],thickness=config['thickness_m'],
        material=Material(**config['material']),field_T=config['field_T'],dmi_boundary=config['dmi_boundary'])
    state=refine_equilibrium(film,film.relax(lattice_seed(film),maxiter=10000,tolerance_T=1e-7).m,tolerance_T=1e-9)
    if not state.converged:raise RuntimeError('Independent spinfreq equilibrium failed')
    matrix,basis=film.linear_operator(state.m,assemble=True);values,vectors=eig(matrix)
    if values.real.max()>=0:raise RuntimeError('Selected skyrmion has a growing linear mode')
    u0=np.einsum('...ci,...c->...i',basis,initial-external).ravel();coefficients=solve(vectors,u0)
    cartesian=np.einsum('yxci,yxik->yxck',basis,vectors.reshape(config['ny'],config['nx'],2,-1)).reshape(-1,len(values))
    mean_observation=cartesian.reshape(config['ny'],config['nx'],3,-1).mean(axis=(0,1))
    predicted_mean=(((mean_observation*coefficients)@np.exp(values[:,None]*times)).T).real
    actual_mean=np.column_stack([table[f'Oxs_TimeDriver::m{axis}'] for axis in 'xyz'])-external.mean(axis=(0,1))
    snapshots=[]
    for p in directory.glob('ringdown-*Spin*.omf'):
        m,meta=read_ovf(p);snapshots.append((meta['time_s'],m))
    snapshots.sort(key=lambda item:item[0]);spatial_times=np.array([t for t,m in snapshots])
    if len(spatial_times)!=len(range(0,expected,5)) or not np.allclose(np.diff(spatial_times),config['spatial_sample_ps']*1e-12,rtol=1e-8,atol=1e-20):
        raise ValueError('Incomplete spatial snapshot series')
    # Stage sampling begins with stage zero's endpoint, then every fifth stage.
    if not np.allclose(spatial_times,times[::5],rtol=1e-8,atol=1e-20):raise ValueError('Spatial/scalar timestamps disagree')
    actual=np.array([m for t,m in snapshots])-external
    predicted=((cartesian*coefficients)@np.exp(values[:,None]*spatial_times)).T.real.reshape(actual.shape)
    fits=[fit_poles(times,actual_mean,start) for start in [0.,.2,.5]]
    mode_fields,spatial_fit_residual=extract_mode_fields(spatial_times,actual,fits[1])
    positive=np.flatnonzero(values.imag>2*np.pi*1e6);indices=positive[np.argsort(values[positive].imag)[:3]]
    mode_records=[]
    for j,index in enumerate(indices):
        linear=cartesian[:,index].reshape(film.shape);fit=mode_fields[j]
        frequency=values[index].imag/(2*np.pi*1e9);frequency_fit=fits[1]['frequencies_GHz'][j]
        phase_fit=fit*np.exp(-1j*np.angle(np.vdot(linear,fit)))
        phase_fit/=np.linalg.norm(phase_fit);linear=linear/np.linalg.norm(linear)
        mode_records.append(dict(mode=j+1,linear_frequency_GHz=float(frequency),OOMMF_fitted_frequency_GHz=frequency_fit,
            frequency_difference_percent=float(abs(frequency/frequency_fit-1)*100),
            linear_pole_FWHM_GHz=float(-values[index].real/(np.pi*1e9)),
            OOMMF_fitted_pole_FWHM_GHz=fits[1]['pole_FWHM_GHz'][j],complex_vector_MAC=modal_assurance(linear,fit),
            absolute_eigen_residual_per_s=float(np.linalg.norm(matrix@vectors[:,index]-values[index]*vectors[:,index])/np.linalg.norm(vectors[:,index])),
            fit_start_frequency_spread_GHz=float(np.ptp([f['frequencies_GHz'][j] for f in fits]))))
        yy,xx=np.indices((config['ny'],config['nx']))
        np.savetxt(output/f'mode_{j+1}.csv',np.column_stack([xx.ravel(),yy.ravel(),linear.reshape(-1,3).real,
            linear.reshape(-1,3).imag,phase_fit.reshape(-1,3).real,phase_fit.reshape(-1,3).imag]),delimiter=',',comments='',
            header='ix,iy,linear_re_x,linear_re_y,linear_re_z,linear_im_x,linear_im_y,linear_im_z,OOMMF_re_x,OOMMF_re_y,OOMMF_re_z,OOMMF_im_x,OOMMF_im_y,OOMMF_im_z')
    profile_error=float(abs(state.m-external).max());trace_error=float(np.linalg.norm(actual_mean-predicted_mean)/np.linalg.norm(predicted_mean))
    field_error=float(np.linalg.norm(actual-predicted)/np.linalg.norm(predicted))
    hashes,archive_hash=archive_reference(directory,output)
    summary=dict(configuration=config,reference_type='Independently executed nonlinear CPU OOMMF',
        analysis_environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
        scalar_samples=len(times),spatial_samples=len(spatial_times),static_max_component_difference=profile_error,
        topological_charge_spinfreq=film.topological_charge(state.m),topological_charge_OOMMF=film.topological_charge(external),
        spinfreq_torque_T=state.torque_T,maximum_growth_rate_per_s=float(values.real.max()),
        relative_mean_trace_L2_error=trace_error,relative_full_spatial_trace_L2_error=field_error,
        coefficient_reconstruction_residual=float(np.linalg.norm(vectors@coefficients-u0)/np.linalg.norm(u0)),
        OOMMF_only_pole_fits=fits,spatial_three_mode_fit_relative_residual=spatial_fit_residual,modes=mode_records,
        raw_reference_sha256=hashes,reference_archive_sha256=archive_hash,
        gates=dict(complete_at_least_four_ns=config['duration_ns']>=4,static_error_below_1e_5=profile_error<1e-5,
            full_spatial_trace_error_below_2_percent=field_error<.02,mean_trace_error_below_2_percent=trace_error<.02,
            three_frequencies_within_2_percent=max(m['frequency_difference_percent'] for m in mode_records)<2,
            three_complex_mode_MAC_above_0_95=min(m['complex_vector_MAC'] for m in mode_records)>.95),
        full_P5_release_gate_closed=False,mesh_convergence_qualified=False,nonlinear_comb_validated=False,
        limitations=['Matched single-z-layer bond discretization; this is not the Liu MuMax ghost-boundary replication.',
            'Small initial perturbation free ringdown; forced response and drive-amplitude qualification are separate.',
            'Only the first three visible modes; no claim of general branch tracking or a complete experimental spectrum.',
            'Continuum mesh/thickness convergence and the validated deployment envelope remain separate gates.'])
    summary['all_executed_gates_passed']=bool(all(summary['gates'].values()))
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    np.savetxt(output/'mean_traces.csv',np.column_stack([times/1e-9,actual_mean,predicted_mean]),delimiter=',',comments='',
        header='time_ns,OOMMF_dx,OOMMF_dy,OOMMF_dz,spinfreq_dx,spinfreq_dy,spinfreq_dz')
    yy,xx=np.indices(external.shape[:2])
    np.savetxt(output/'equilibrium.csv',np.column_stack([xx.ravel(),yy.ravel(),external.reshape(-1,3),state.m.reshape(-1,3)]),
        delimiter=',',comments='',header='ix,iy,OOMMF_x,OOMMF_y,OOMMF_z,spinfreq_x,spinfreq_y,spinfreq_z')
    plot(output,config,state.m,external,times,actual_mean,predicted_mean,mode_records)
    print(json.dumps({k:v for k,v in summary.items() if k!='raw_reference_sha256'},indent=2),flush=True)
    return summary


def plot(output,config,m,external,times,actual,predicted,records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    axes[0,0].imshow(external[...,2],origin='lower',extent=[0,40,0,40],vmin=-1,vmax=1,cmap='RdBu_r')
    axes[0,0].set(title=f'OOMMF mz, Bz={config["field_T"][2]*1e3:g} mT',xlabel='x (nm)',ylabel='y (nm)')
    x=(np.arange(config['nx'])+.5)*config['dx_m']/1e-9;row=config['ny']//2
    for axis,label in [(0,'mx'),(2,'mz')]:
        axes[0,1].plot(x,external[row,:,axis],label=f'OOMMF {label}')
        axes[0,1].plot(x,m[row,:,axis],'--',label=f'spinfreq {label}')
    axes[0,1].set(xlabel='x at central row (nm)',ylabel='Magnetization');axes[0,1].legend(fontsize=8)
    for axis,label in [(0,'x'),(2,'z')]:
        axes[1,0].plot(times/1e-9,actual[:,axis],label=f'OOMMF delta m{label}')
        axes[1,0].plot(times/1e-9,predicted[:,axis],'--',label=f'spinfreq delta m{label}')
    axes[1,0].set(xlim=(0,1),xlabel='Time (ns)',ylabel='Mean response');axes[1,0].legend(fontsize=7)
    f=np.fft.rfftfreq(len(times),np.mean(np.diff(times)))/1e9
    window=np.hanning(len(times))[:,None];a=(actual-actual.mean(axis=0))*window;b=(predicted-predicted.mean(axis=0))*window
    for axis,label in [(0,'x'),(2,'z')]:
        pa=abs(np.fft.rfft(a[:,axis]))**2;pb=abs(np.fft.rfft(b[:,axis]))**2
        axes[1,1].semilogy(f,pa/pa.max(),label=f'OOMMF {label}')
        axes[1,1].semilogy(f,pb/pa.max(),'--',label=f'spinfreq {label}')
    axes[1,1].set(xlim=(0,45),ylim=(1e-6,2),xlabel='Frequency (GHz)',ylabel='Normalized mean power');axes[1,1].legend(fontsize=7)
    for ext in ['png','pdf']:fig.savefig(output/f'comparison.{ext}',dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(3,4,figsize=(11,8),layout='constrained')
    for j,record in enumerate(records):
        data=np.loadtxt(output/f'mode_{j+1}.csv',delimiter=',',skiprows=1)
        linear=(data[:,2:5]+1j*data[:,5:8]).reshape(m.shape)
        reference=(data[:,8:11]+1j*data[:,11:14]).reshape(m.shape)
        scale=max(abs(linear[...,2]).max(),abs(reference[...,2]).max())
        for offset,field in [(0,linear),(2,reference)]:
            amplitude=abs(field[...,2])/scale;phase=np.ma.masked_where(amplitude<.03,np.angle(field[...,2]))
            axes[j,offset].imshow(amplitude,origin='lower',extent=[0,40,0,40],vmin=0,vmax=1,cmap='viridis')
            axes[j,offset+1].imshow(phase,origin='lower',extent=[0,40,0,40],vmin=-np.pi,vmax=np.pi,cmap='twilight')
        axes[j,0].set_ylabel(f'{record["linear_frequency_GHz"]:.3f} GHz\ny (nm)')
    for ax,title in zip(axes[0],['Linear |delta mz|','Linear phase','OOMMF |delta mz|','OOMMF phase']):ax.set_title(title)
    for ax in axes[-1]:ax.set_xlabel('x (nm)')
    for column in range(4):
        fig.colorbar(axes[0,column].images[0],ax=axes[:,column].tolist(),location='bottom',shrink=.8,
            label='Normalized |delta mz|' if column%2==0 else 'Phase (rad)')
    for ext in ['png','pdf']:fig.savefig(output/f'complex_modes.{ext}',dpi=180)
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','analyze','restore','mesh','qualify'])
    parser.add_argument('--workdir',type=Path,default=Path('results/skyrmion-temporal'))
    parser.add_argument('--output',type=Path,default=Path('validation/skyrmion_temporal/field_0mT'))
    parser.add_argument('--reference',type=Path,default=Path('validation/skyrmion_temporal/field_0mT'))
    parser.add_argument('--mesh-reference',type=Path,default=Path('validation/skyrmion_temporal/mesh_fine/summary.json'))
    parser.add_argument('--runtime',type=Path)
    parser.add_argument('--field-mT',type=float,default=0.)
    parser.add_argument('--cells',type=int,default=20)
    parser.add_argument('--mesh-cells',type=int,nargs='+',default=[20,30,40])
    parser.add_argument('--duration-ns',type=float,default=4.)
    parser.add_argument('--amplitude',type=float,default=1e-4)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.action=='qualify':
        result=qualify_suite(args.reference,args.mesh_reference,args.output)
        print(json.dumps(result,indent=2))
        if args.check and not result['P5_two_field_fine_mesh_evidence_passed']:raise SystemExit('Fine-mesh qualification failed')
    if args.action=='mesh':
        result=mesh_refinement(args.output,args.mesh_cells)
        if args.check and not all(r['finest_pair_change_below_1_percent'] for r in result['refinements']):
            raise SystemExit('Mesh qualification failed; retain failed result and refine further')
    if args.action=='restore':restore_reference(args.reference,args.workdir)
    if args.action in ['prepare','run']:
        if args.action=='run' and args.runtime is None:parser.error('--runtime is required for OOMMF execution')
        prepare(args.workdir,args.field_mT*1e-3,args.cells,args.duration_ns,args.amplitude)
        if args.action=='run':execute(args.workdir,args.runtime)
    if args.action in ['analyze','run']:
        result=analyze(args.workdir,args.output)
        if args.check and not result['all_executed_gates_passed']:raise SystemExit('Skyrmion comparison gate failed')
