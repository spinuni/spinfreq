"""Cortes-Ortuno 2018 interfacial DMI: profiles, signed bands and fit bias.

Published static data are compared pointwise. Dynamic comparisons use the
authors' saved notebook summaries: raw time/space spectra are not in that
repository. A Bloch strip represents its translation-invariant interior,
not the finite 2 um pulse-driven experiment.
"""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import re
import time
from urllib.request import urlopen

import numpy as np
import scipy
from scipy.integrate import solve_bvp
from scipy.linalg import eig, eigvals, solve

from spinfreq import BlochChain, ConfinedFilm, Film, Material, refine_equilibrium
from spinfreq.model import MU0

COMMIT='1d9390c06c13cda29b0eb2f38f7e132be05e97f4'
REPOSITORY='https://github.com/fangohr/paper-supplement-standard-problem-dmi'
RAW=f'https://raw.githubusercontent.com/fangohr/paper-supplement-standard-problem-dmi/{COMMIT}/'
PREFIX='notebooks/data/results_1d/result_1d_x-'
HASHES={
    PREFIX+'mx_interfacial_ODE.txt':'fc0d3fa49a8f57fc04a4468bf821808a127a06aba241bb465fcd0b26c05281f9',
    PREFIX+'mz_interfacial_ODE.txt':'1c2efeb1f3e5d4093ebfb5f2786c7c3d54efac17f10a3b72faa9d5d7ad4b83e4',
    PREFIX+'mx_interfacial_fidimag.txt':'76ac9903508376164da4b5151804fc8692b41646cab55d99b767d2c5defc8eb3',
    PREFIX+'mz_interfacial_fidimag.txt':'121d6e7c064abc5a1796a18878037a0fc58ac355c4c35305fc8f81267fc59c88',
    PREFIX+'mx_interfacial_oommf.txt':'eae8e4baf76ec17a127d129e20dc75b46f61594ee438f8fd644fb9a2f3d36f3d',
    PREFIX+'mz_interfacial_oommf.txt':'0c99580467a153fa69c0611963badd061ee29953489cf0278f8aa293ba8315ce',
    PREFIX+'mx_interfacial_mumax3.txt':'fc3c387128e58943db9821454a6eed0bb93170749ca94de6511c35b78872b63a',
    PREFIX+'mz_interfacial_mumax3.txt':'527fee1d2b9810b8bdf66104c8f202c4ef83131e1a91dc67fe0e2dabededa6fd',
    'sims/MUMAX3/1D/one_dim_inter.ovf':'93732e2f37cdfb7bb0ad6b635690ddb831a9fac7fc60997ddb526ef21dfdfb1d',
    'notebooks/spin_waves_dmi.ipynb':'cd2fafd80c6511eea21a5069138e888c7386123418766c061ad46ec030f40fe6',
}


def references(directory,fetch=False):
    directory=Path(directory)
    for name,expected in HASHES.items():
        path=directory/name
        if not path.exists():
            if not fetch:raise FileNotFoundError(f'{path}: supply the author checkout or --fetch-reference')
            with urlopen(RAW+name,timeout=60) as response:data=response.read()
            if hashlib.sha256(data).hexdigest()!=expected:raise ValueError(f'Reference checksum mismatch: {name}')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError(f'Reference checksum mismatch: {path}')
    return directory


def continuum_wire(A,K,D,length_nm=100):
    """Independent natural-boundary BVP in nm: theta''=sin(theta)cos(theta)/Delta²."""
    delta=np.sqrt(A/K)*1e9;q=-D/(2*A)*1e-9
    x=np.linspace(-length_nm/2,length_nm/2,501)
    left=np.exp(-(x+length_nm/2)/delta);right=np.exp(-(length_nm/2-x)/delta)
    guess=np.array([q*delta*(-left+right),q*(left+right)])
    solution=solve_bvp(lambda x,y:np.array([y[1],np.sin(y[0])*np.cos(y[0])/delta**2]),
        lambda a,b:np.array([a[1]-q,b[1]-q]),x,guess,tol=1e-9,max_nodes=10000)
    if not solution.success:raise RuntimeError(solution.message)
    return solution


def equilibrium(film,axis=2,initial=None):
    if initial is None:
        initial=np.zeros(film.shape);initial[...,axis]=1
    relaxed=film.relax(initial,tolerance_T=1e-7)
    refined=refine_equilibrium(film,relaxed.m,tolerance_T=1e-8)
    if not refined.converged:raise RuntimeError(f'Static residual did not converge: {refined.torque_T:g} T')
    return refined


def static_comparison(output,reference):
    material=Material(Ms=.86e6,A=13e-12,D=-3e-3,K=.4e6,alpha=.01,gamma=2.21e5/MU0)
    continuum=continuum_wire(material.A,material.K,material.D)
    profiles={name:np.column_stack([np.loadtxt(reference/(PREFIX+f'mx_interfacial_{name}.txt')),
                                   np.loadtxt(reference/(PREFIX+f'mz_interfacial_{name}.txt'))[:,1]])
              for name in ['mumax3','oommf','fidimag']}
    records=[];fields=[];coordinates=[]
    # Rotate the reference x-wire to model y, with x periodic. This exactly
    # implements the reference's transverse PBC without removing open ghosts.
    for n in [100,200,400]:
        film=BlochChain(nx=1,ny=n,dx=1e-9,dy=100e-9/n,thickness=1e-9,
            material=material,field_T=(0,0,0),demag=False,images=1)
        state=equilibrium(film)
        original=np.stack([state.m[:,0,1],-state.m[:,0,0],state.m[:,0,2]],axis=-1)
        x=(np.arange(n)+.5)*100/n-50
        theta=continuum.sol(x)[0];bvp=np.column_stack([np.sin(theta),np.zeros(n),np.cos(theta)])
        matrix,_=film.bloch_operator(state.m,0,assemble=True);values=eigvals(matrix)
        positive=np.sort(values.imag[values.imag>0]/(2*np.pi*1e9))
        record=dict(cells=n,cell_nm=100/n,torque_T=state.torque_T,
            max_component_error_to_continuum=float(abs(original-bvp).max()),
            energy_J=state.energy_J,max_growth_rate_per_s=float(values.real.max()),
            lowest_three_frequencies_GHz=positive[:3].tolist())
        if n==100:
            record['published_profile_errors']={name:dict(mx_max=float(abs(original[:,0]-a[:,1]).max()),
                mz_max=float(abs(original[:,2]-a[:,2]).max())) for name,a in profiles.items()}
            plus=BlochChain(nx=1,ny=n,dx=1e-9,dy=100e-9/n,thickness=1e-9,
                material=replace(material,D=-material.D),field_T=(0,0,0),demag=False,images=1)
            mirrored=equilibrium(plus)
            record['D_reversal_mirror_error']=float(max(abs(mirrored.m[...,1]+state.m[...,1]).max(),
                                                       abs(mirrored.m[...,2]-state.m[...,2]).max()))
        np.savetxt(output/f'wire_{n}.csv',np.column_stack([x,original,bvp]),delimiter=',',comments='',
            header='x_nm,mx,my,mz,continuum_mx,continuum_my,continuum_mz')
        records.append(record);fields.append(original);coordinates.append(x)
        print('wire',json.dumps(record),flush=True)
    # The literal open-y MuMax input is a different model from the PBC reference.
    opened=ConfinedFilm(nx=100,ny=1,dx=1e-9,thickness=1e-9,material=material,field_T=(0,0,0),demag=False)
    opened_state=equilibrium(opened);raw=np.loadtxt(reference/'sims/MUMAX3/1D/one_dim_inter.ovf')
    open_error=float(abs(opened_state.m[0]-raw[:,3:]).max())
    np.savetxt(output/'wire_open_y.csv',np.column_stack([coordinates[0],opened_state.m[0],raw[:,3:]]),
        delimiter=',',comments='',header='x_nm,mx,my,mz,published_mx,published_my,published_mz')
    ode_errors={}
    for component,fun in [('mx',np.sin),('mz',np.cos)]:
        data=np.loadtxt(reference/(PREFIX+f'{component}_interfacial_ODE.txt'))
        ode_errors[component]=float(abs(fun(continuum.sol(data[:,0])[0])-data[:,1]).max())
    summary=dict(material=vars(material),geometry_nm=[100,1,1],demag=False,
        model='Reference x-wire rotated onto model y; nx=1, x periodic, y open; m_ref=(m_model_y,-m_model_x,m_model_z)',
        meshes=records,continuum_BVP_max_residual=float(continuum.rms_residuals.max()),
        continuum_vs_published_ODE_max_errors=ode_errors,
        literal_open_y_MuMax_max_component_error=open_error,
        open_y_vs_periodic_y_max_component_difference=float(abs(opened_state.m[0]-fields[0]).max()),
        open_single_cell_transverse_ghost_effective_K_J_m3=material.D**2/(2*material.A),
        source_D_conventions=dict(spinfreq_J_m2=-.003,mumax_J_m2=-.003,notebook_oommf_J_m2=.003,fidimag_J_m2=.003),
        gates=dict(published_profiles_below_1e_4=bool(max(v for a in records[0]['published_profile_errors'].values() for v in a.values())<1e-4),
            open_y_MuMax_profile_below_1e_4=bool(open_error<1e-4),
            D_reversal_below_1e_7=bool(records[0]['D_reversal_mirror_error']<1e-7),
            continuum_error_below_5e_4_and_refines=bool(records[-1]['max_component_error_to_continuum']<5e-4 and
                all(b['max_component_error_to_continuum']<.4*a['max_component_error_to_continuum'] for a,b in zip(records,records[1:])))))
    plot_static(output,coordinates,fields,profiles,continuum,opened_state.m[0],raw[:,3:])
    return summary


def analytic_nonreciprocity(output):
    """Full spectral Jacobian versus independent uniform-thickness formula."""
    p=Material(Ms=.86e6,A=13e-12,D=-3e-3,K=0,alpha=0,gamma=2.21e5/MU0)
    film=Film(nx=64,ny=1,dx=1000e-9/64,thickness=1e-9,material=p,field_T=(0,.4,0))
    m=np.zeros(film.shape);m[...,1]=1
    matrix,_=film.linearize(m);rows=[]
    for winding in range(1,16):
        q=2*np.pi*winding/(film.nx*film.dx);pair=[]
        for sign in [-1,1]:
            k=sign*q;phase=np.exp(1j*k*np.arange(film.nx)*film.dx)/np.sqrt(film.nx)
            projection=np.kron(phase[:,None],np.eye(2))
            reduced=projection.conj().T@matrix@projection;values=eigvals(reduced)
            frequency=float(-values[values.imag<0][0].imag/(2*np.pi))
            F=-np.expm1(-abs(k)*film.thickness)/(abs(k)*film.thickness)
            h=.4+2*p.A*k*k/p.Ms
            expected=p.gamma/(2*np.pi)*(np.sqrt((h+MU0*p.Ms*(1-F))*(h+MU0*p.Ms*F))-2*p.D*k/p.Ms)
            residual=float(np.linalg.norm(matrix@projection-projection@reduced)/np.linalg.norm(matrix@projection))
            rows.append([k/1e9,frequency/1e9,expected/1e9,residual]);pair.append(frequency)
    rows=np.array(rows);error=float(np.max(abs(rows[:,1]/rows[:,2]-1)))
    positive=rows[rows[:,0]>0];negative=rows[rows[:,0]<0]
    delta=positive[:,1]-negative[:,1];slope=float(np.dot(positive[:,0],delta)/np.dot(positive[:,0],positive[:,0]))
    D=-slope*np.pi*p.Ms/(2*p.gamma)
    np.savetxt(output/'analytic_nonreciprocity.csv',rows,delimiter=',',comments='',
        header='k_rad_nm,numerical_frequency_GHz,analytical_frequency_GHz,invariant_subspace_residual')
    return dict(material=vars(p),max_frequency_relative_error=error,
        inferred_D_J_m2=D,relative_D_error=abs(D/p.D-1),max_subspace_residual=float(rows[:,3].max()),
        passed=bool(error<1e-10 and abs(D/p.D-1)<1e-10),
        note='Analytical identity for uniform-through-thickness periodic film, not external strip data')


def notebook_metrics(reference):
    notebook=json.loads((reference/'notebooks/spin_waves_dmi.ipynb').read_text())
    text='\n'.join(''.join(o.get('text',[])) for c in notebook['cells'] for o in c.get('outputs',[]))
    result={}
    for name in ['MuMax3','OOMMF','Fidimag']:
        metrics={}
        for key,pattern in [('k_min_rad_nm',rf'{name}\s+Simulation k_min =\s*([-\d.]+)'),
                            ('f_min_GHz',rf'{name}\s+Simulation f_min =\s*([-\d.]+)'),
                            ('quadratic_inferred_D_mJ_m2',rf'DMI predicted by {name}:\s*([-\d.]+)')]:
            match=re.search(pattern,text)
            if not match:raise ValueError(f'Missing saved reference metric: {name} {key}')
            metrics[key]=float(match.group(1))
        result[name]=metrics
    return result


def strip(cell_nm,images,boundary='mumax'):
    p=Material(Ms=.86e6,A=13e-12,D=-3e-3,K=0,alpha=.01,gamma=2.21e5/MU0)
    film=BlochChain(nx=1,ny=round(200/cell_nm),dx=cell_nm*1e-9,dy=cell_nm*1e-9,
        thickness=1e-9,images=images,material=p,field_T=(0,.4,0),dmi_boundary=boundary)
    state=equilibrium(film,axis=1)
    basis=film.tangent_basis(state.m)
    c=np.cross(state.m,[1,0,0]);force=-p.gamma/(1+p.alpha**2)*(c+p.alpha*np.cross(state.m,c))
    force=np.einsum('...ci,...c->...i',basis,force).ravel()
    observation=np.zeros(2*film.ny)
    center=(film.ny//2-1);observation[2*center:2*center+2]=basis[center,0,0,:]
    return film,state,force,observation


def visible_pole(film,m,k_rad_nm,force,observation):
    matrix,_=film.bloch_operator(m,k_rad_nm*1e9,assemble=True)
    values,vectors=eig(matrix)
    if values.real.max()>=0:raise RuntimeError('Unstable strip spectrum: cannot interpret resonant strengths')
    coefficients=solve(vectors,force)
    score=abs((observation@vectors)*coefficients)/(-values.real)
    frequencies=-values.imag/(2*np.pi*1e9)
    candidates=np.flatnonzero((frequencies>0)&(frequencies<60))
    if not len(candidates):raise RuntimeError('No pole below the reference excitation cutoff')
    choice=candidates[np.argmax(score[candidates])]
    absolute=float(np.linalg.norm(matrix@vectors[:,choice]-values[choice]*vectors[:,choice])/np.linalg.norm(vectors[:,choice]))
    relative=absolute/(np.linalg.norm(matrix,ord=np.inf)+abs(values[choice]))
    if relative>1e-9:raise RuntimeError('Selected eigenpair failed its residual check')
    return dict(frequency_GHz=float(frequencies[choice]),pole_FWHM_GHz=float(-values[choice].real/np.pi/1e9),
        resonant_residue_per_T=float(score[choice]),absolute_residual_per_s=absolute,
        relative_residual=relative,max_growth_rate_per_s=float(values.real.max()))


def refine_low_band(output,ks,one_nm_frequencies):
    """Extra 0.5 nm check after the 2-to-1 nm refinement fails the target."""
    start=time.perf_counter();keep=(ks>=-.14)&(ks<=-.06);wavevectors=ks[keep]
    film,state,force,observation=strip(.5,2048)
    poles=[visible_pole(film,state.m,k,force,observation) for k in wavevectors]
    frequencies=np.array([p['frequency_GHz'] for p in poles])
    changes=abs(frequencies/one_nm_frequencies[keep]-1)
    np.savetxt(output/'low_band_refinement_0.5nm.csv',np.column_stack([wavevectors,
        one_nm_frequencies[keep],frequencies,changes]),delimiter=',',comments='',
        header='k_rad_nm,one_nm_frequency_GHz,half_nm_frequency_GHz,relative_change')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(9,3.5),layout='constrained')
    axes[0].plot(wavevectors,one_nm_frequencies[keep],label='1 nm')
    axes[0].plot(wavevectors,frequencies,label='0.5 nm')
    axes[0].set(xlabel='k (rad/nm)',ylabel='Visible pole (GHz)');axes[0].legend()
    axes[1].plot(wavevectors,100*changes)
    axes[1].axhline(.5,ls='--',color='black',label='0.5% project target')
    axes[1].set(xlabel='k (rad/nm)',ylabel='Refinement change (%)');axes[1].legend()
    for ext in ['png','pdf']:fig.savefig(output/f'low_band_refinement.{ext}',dpi=180)
    plt.close(fig)
    result=dict(cell_nm=.5,nx=1,ny=400,images=2048,torque_T=state.torque_T,
        k_interval_rad_nm=[float(wavevectors.min()),float(wavevectors.max())],
        samples=len(wavevectors),max_1nm_to_half_nm_relative_frequency_change=float(changes.max()),
        max_eigen_relative_residual=max(p['relative_residual'] for p in poles),
        elapsed_s=time.perf_counter()-start)
    print('extra refinement',json.dumps(result),flush=True)
    return result


def dispersion_comparison(output,reference):
    reported=notebook_metrics(reference)
    # Exactly the first 100 k points used by the author notebook's quadratic
    # fit: dk=2*pi/(2000 nm), -95 <= winding <= 4. No fitted material constants.
    ks=np.arange(-95,5)*2*np.pi/2000
    results=[];curves=[]
    for cell_nm,images,boundary in [(4.,256,'mumax'),(2.,512,'mumax'),(1.,1024,'mumax'),(2.,512,'bond')]:
        start=time.perf_counter();film,state,force,observation=strip(cell_nm,images,boundary)
        poles=[visible_pole(film,state.m,k,force,observation) for k in ks]
        frequencies=np.array([p['frequency_GHz'] for p in poles])
        polynomial=np.polyfit(ks,frequencies,2)
        minimum=-polynomial[1]/(2*polynomial[0])
        fit_D=polynomial[1]*np.pi*film.material.Ms/film.material.gamma*1e3
        pairs=[]
        for k in [.02,.04,.06]:
            minus=visible_pole(film,state.m,-k,force,observation)
            plus=visible_pole(film,state.m,k,force,observation)
            delta=plus['frequency_GHz']-minus['frequency_GHz']
            signed_D=-delta/k*np.pi*film.material.Ms/(2*film.material.gamma)
            pairs.append(dict(k_rad_nm=k,minus_frequency_GHz=minus['frequency_GHz'],plus_frequency_GHz=plus['frequency_GHz'],
                delta_f_GHz=delta,inferred_D_J_m2=signed_D,relative_D_error=abs(signed_D/film.material.D-1)))
        record=dict(cell_nm=cell_nm,nx=1,ny=film.ny,images=images,boundary=boundary,torque_T=state.torque_T,
            max_growth_rate_per_s=max(p['max_growth_rate_per_s'] for p in poles),
            max_eigen_relative_residual=max(p['relative_residual'] for p in poles),
            quadratic_k_min_rad_nm=float(minimum),quadratic_f_min_GHz=float(np.polyval(polynomial,minimum)),
            quadratic_inferred_abs_D_mJ_m2=float(fit_D),quadratic_coefficients=polynomial.tolist(),
            sampled_minimum_GHz=float(frequencies.min()),sampled_minimum_k_rad_nm=float(ks[frequencies.argmin()]),
            signed_pairs=pairs,elapsed_s=time.perf_counter()-start)
        label=f'{boundary}_{cell_nm:g}nm'
        np.savetxt(output/f'dispersion_{label}.csv',np.column_stack([ks,frequencies,
            [p['pole_FWHM_GHz'] for p in poles],[p['resonant_residue_per_T'] for p in poles],
            [p['absolute_residual_per_s'] for p in poles]]),delimiter=',',comments='',
            header='k_rad_nm,visible_pole_GHz,pole_FWHM_GHz,resonant_residue_per_T,eigen_absolute_residual_per_s')
        results.append(record);curves.append(frequencies)
        print('strip',json.dumps(record),flush=True)
    nominal=results[1];target=reported['MuMax3']
    errors=dict(k_min=abs(nominal['quadratic_k_min_rad_nm']/target['k_min_rad_nm']-1),
        f_min=abs(nominal['quadratic_f_min_GHz']/target['f_min_GHz']-1),
        quadratic_inferred_D=abs(nominal['quadratic_inferred_abs_D_mJ_m2']/target['quadratic_inferred_D_mJ_m2']-1))
    low=(ks>=-.14)&(ks<=-.06)
    refinement=float(np.max(abs(curves[2][low]/curves[1][low]-1)))
    extra=refine_low_band(output,ks,curves[2])
    # Image convergence uses freshly refined equilibria, not just dynamic fields.
    film,state,force,observation=strip(2.,1024)
    image_records=[]
    for k in [-.1,0.,.1]:
        fine=visible_pole(film,state.m,k,force,observation)
        image_records.append(dict(k_rad_nm=k,images_1024_frequency_GHz=fine['frequency_GHz']))
    base_film,base_state,base_force,base_obs=strip(2.,512)
    for record in image_records:
        base=visible_pole(base_film,base_state.m,record['k_rad_nm'],base_force,base_obs)
        record['images_512_frequency_GHz']=base['frequency_GHz']
        record['relative_change']=abs(record['images_1024_frequency_GHz']/base['frequency_GHz']-1)
    summary=dict(geometry='Infinite x-periodic, open-y 200 nm strip, 1 nm thickness; compare its interior bands with a finite 2000 nm reference',
        reference_metrics_source='Saved stdout in the pinned author notebook; raw spectra absent from the source repository',
        frequency_convention='m = Re[u exp(i k x + lambda t)], compare f=-Im(lambda)/(2*pi)>0 to exp(i k x-i omega t)',
        observable='Pole residue for uniform-y Bx drive, mx at the negative-y central row; inverse right eigenbasis, divided by pole decay',
        reported_notebook_metrics=reported,meshes=results,nominal_MuMax_summary_relative_errors=errors,
        max_2nm_to_1nm_relative_frequency_change_near_minimum=refinement,
        extra_low_band_refinement=extra,
        image_convergence=image_records,
        gates=dict(nominal_MuMax_summary_errors_below_2_percent=bool(max(errors.values())<.02),
            low_k_signed_D_error_below_2_percent=bool(max(p['relative_D_error'] for p in results[2]['signed_pairs'])<.02),
            near_minimum_refinement_below_half_percent=bool(extra['max_1nm_to_half_nm_relative_frequency_change']<.005),
            image_refinement_below_tenth_percent=bool(max(r['relative_change'] for r in image_records)<.001)),
        full_temporal_dispersion_validated=False,
        limitations=['Printed summary metrics do not substitute for raw f-k FFT curves or mode maps.',
            'The finite strip ends, pulse protocol, amplitude and transient spectra are not reproduced.',
            'The bond variant is exploratory; it is not certified as the authors\' OOMMF implementation.',
            'The quadratic fitted D is an analysis-dependent apparent value, not a fitted material constant.',
            'Refinement gate covers only the low band around the minimum, not the entire sampled k range.'])
    plot_dispersion(output,ks,curves,results,reported)
    return summary


def plot_static(output,coordinates,fields,profiles,continuum,opened,published_open):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
    x=np.linspace(-50,50,1001);theta=continuum.sol(x)[0]
    for axis,component,fun in [(axes[0],0,np.sin),(axes[1],2,np.cos)]:
        axis.plot(x,fun(theta),color='black',label='Continuum BVP')
        for n,xx,m in zip([100,200,400],coordinates,fields):axis.plot(xx,m[:,component],label=f'spinfreq {100/n:g} nm')
        for name,a in profiles.items():axis.plot(a[::4,0],a[::4,1 if component==0 else 2],'.',label=f'Published {name}')
        axis.set(xlabel='Wire coordinate (nm)',ylabel=f'm{"x" if component==0 else "z"}')
    for xx,m in zip(coordinates,fields):axes[2].semilogy(xx,abs(m[:,0]-np.sin(continuum.sol(xx)[0])),label=f'{100/len(xx):g} nm')
    axes[2].set(xlabel='Wire coordinate (nm)',ylabel='|mx − continuum mx|')
    axes[0].legend(fontsize=7);axes[2].legend(fontsize=8)
    for ext in ['png','pdf']:fig.savefig(output/f'wire_profiles.{ext}',dpi=180)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
    ax.plot(coordinates[0],fields[0][:,0],label='Transverse PBC: spinfreq')
    ax.plot(profiles['mumax3'][:,0],profiles['mumax3'][:,1],'.',label='Transverse PBC: published MuMax3')
    ax.plot(coordinates[0],opened[:,0],label='Open transverse axis: spinfreq')
    ax.plot(coordinates[0][::3],published_open[::3,0],'x',label='Open transverse axis: published MuMax3')
    ax.set(xlim=(-50,-25),xlabel='Wire coordinate (nm)',ylabel='mx');ax.legend(fontsize=8)
    for ext in ['png','pdf']:fig.savefig(output/f'boundary_comparison.{ext}',dpi=180)
    plt.close(fig)


def plot_dispersion(output,ks,curves,results,reported):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for curve,r in zip(curves,results):
        axes[0].plot(ks,curve,label=f'{r["boundary"]}, {r["cell_nm"]:g} nm')
        axes[1].plot(ks,curve)
    axes[0].plot(ks,np.polyval(results[1]['quadratic_coefficients'],ks),'k--',label='2 nm quadratic fit')
    axes[0].set(xlabel='k (rad/nm)',ylabel='Visible pole (GHz)');axes[0].legend(fontsize=7)
    for name,r in reported.items():axes[1].plot(r['k_min_rad_nm'],r['f_min_GHz'],'x',ms=8,label=f'Published {name} fit minimum')
    axes[1].plot(results[1]['quadratic_k_min_rad_nm'],results[1]['quadratic_f_min_GHz'],'o',
        markerfacecolor='none',markeredgecolor='black',ms=7,label='spinfreq 2 nm fit minimum')
    axes[1].set(xlim=(-.125,-.08),ylim=(11.9,13.3),xlabel='k (rad/nm)',ylabel='Visible pole (GHz)');axes[1].legend(fontsize=7)
    for r in results[:3]:
        axes[2].plot([p['k_rad_nm'] for p in r['signed_pairs']],
            [abs(p['inferred_D_J_m2'])*1e3 for p in r['signed_pairs']],'o-',label=f'Direct ±k, {r["cell_nm"]:g} nm')
    axes[2].axhline(3,color='black',label='Nominal |D|')
    axes[2].axhline(results[1]['quadratic_inferred_abs_D_mJ_m2'],color='gray',ls='--',label='2 nm asymmetric quadratic fit')
    axes[2].set(xlabel='|k| (rad/nm)',ylabel='Inferred |D| (mJ/m²)',ylim=(2.5,3.05));axes[2].legend(fontsize=7)
    for ext in ['png','pdf']:fig.savefig(output/f'dispersion_comparison.{ext}',dpi=180)
    plt.close(fig)


def run(output,reference_directory,fetch=False,skip_dispersion=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    reference=references(reference_directory,fetch)
    summary=dict(paper_DOI='10.1088/1367-2630/aaea1c',reference_repository=REPOSITORY,
        reference_commit=COMMIT,reference_sha256=HASHES,
        static=static_comparison(output,reference),analytic=analytic_nonreciprocity(output),
        dispersion=None if skip_dispersion else dispersion_comparison(output,reference),
        runtime=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))
    gates=list(summary['static']['gates'].values())+[summary['analytic']['passed']]
    if summary['dispersion'] is not None:gates+=list(summary['dispersion']['gates'].values())
    summary['all_executed_gates_passed']=bool(all(gates))
    summary['full_P4_release_gate_closed']=False
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-directory',type=Path,default=Path('results/reference/dmi2018'))
    parser.add_argument('--fetch-reference',action='store_true')
    parser.add_argument('--skip-dispersion',action='store_true',help='Run static profiles and the analytical signed-k check only')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('validation/dmi_standard_problem'))
    args=parser.parse_args()
    result=run(args.output,args.reference_directory,args.fetch_reference,args.skip_dispersion)
    if args.check and not result['all_executed_gates_passed']:raise SystemExit('DMI acceptance gate failed; inspect summary.json')
