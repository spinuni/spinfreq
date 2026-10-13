"""Liu 2024 Fig.2: independent FM check and 1D Bloch-chain dispersion.

This evaluates agreement rather than assuming the paper's bands are reproduced.
"""
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
import numpy as np
from scipy.linalg import eigvals
from spinfreq import Film,BlochChain,lattice_seed
from spinfreq.model import MU0,Spectrum
from liu2024 import paper_material,savefig,write_table
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


PAPER=dict(FMR_GHz=37.5,shifted_continuum_GHz=34.5,gyration_band_GHz=[.1,4.0],breathing_band_GHz=[13.4,20.4])


def fm_reference(folder):
    p=paper_material()
    film=Film(nx=41,ny=3,dx=5e-9,dy=10e-9,thickness=1e-9,material=p,field_T=(0,0,0))
    m=np.zeros(film.shape);m[...,2]=1
    matrix,_=film.linearize(m)
    values=eigvals(matrix)
    numeric=np.sort(values.imag[values.imag>0]/(2*np.pi))
    h=2*p.K/p.Ms-MU0*p.Ms+2*p.A/p.Ms*film.k2
    a=h+MU0*p.Ms*(1-film.nzz)
    b=h
    reference=p.gamma/(1+p.alpha**2)*np.sqrt(a*b-p.alpha**2*(a-b)**2/4)/(2*np.pi)
    expected=np.sort(reference.ravel())
    error=float(np.max(abs(numeric/expected-1)))
    if error>1e-8: raise RuntimeError('Independent FM dispersion check failed')
    write_table(folder/'fm_eigenvalues.csv',['sorted_numerical_Hz','sorted_analytical_Hz'],zip(numeric,expected))
    # Mapping by sorted frequency ranks after the independent full-spectrum check.
    ranks=np.argsort(np.argsort(reference.ravel())).reshape(film.ny,film.nx)
    row=0
    q=film.kx[row]
    frequencies=numeric[ranks[row]]
    write_table(folder/'fm_kx.csv',['k_rad_per_nm','numerical_GHz','analytical_GHz'],zip(q/1e9,frequencies/1e9,reference[row]/1e9))
    return dict(max_relative_error=error,FMR_GHz=float(numeric.min()/1e9),paper_FMR_GHz=37.5,
                FMR_difference_percent=float(abs(numeric.min()/1e9/37.5-1)*100)),q/1e9,frequencies/1e9


def branch_values(spectrum):
    f=spectrum.frequencies_Hz/1e9
    def minimum(lower,upper):
        selected=f[(f>=lower)&(f<upper)]
        return float(selected.min()) if len(selected) else None
    gyro=minimum(.001,8)
    overdamped=gyro is None and np.any(abs(f)<.001)
    if overdamped: gyro=0.0
    return dict(gyration_GHz=gyro,breathing_GHz=minimum(8,25),upper_branch_GHz=minimum(25,60),
                near_zero_nonoscillatory=bool(overdamped),maximum_growth_per_s=float(spectrum.eigenvalues.real.max()))


def chain_scan(n,kpoints,images,folder,reuse=False):
    film=BlochChain(nx=n,ny=n,dx=40e-9/n,images=images,material=paper_material(),field_T=(0,0,0))
    cache=folder/f'bloch_{n}.npz'
    cached=np.load(cache) if reuse and cache.exists() else None
    if cached is not None:
        if cached['m'].shape!=film.shape or not np.allclose(cached['k_rad_m'],np.linspace(-1,1,kpoints)*np.pi/film.period_m,rtol=1e-12,atol=1e-6):
            raise ValueError('Cached mesh or wavevector sampling does not match requested benchmark')
        from spinfreq.model import Relaxation
        equilibrium=cached['m']
        torque=film.torque(equilibrium)
        relaxed=Relaxation(equilibrium,film.energy(equilibrium),torque,torque<=1e-5,0,'Cache equilibrium revalidated')
    else:
        relaxed=film.relax(lattice_seed(film),maxiter=6000)
    if not relaxed.converged: raise RuntimeError(f'Chain relaxation failed: {relaxed.torque_T:g} T')
    start=time.monotonic()
    rows=[];spectra=[];residuals=[]
    for point_index,reduced in enumerate(np.linspace(-1,1,kpoints)):
        k=reduced*np.pi/film.period_m
        if cached is None:
            spectrum=film.bloch_modes(relaxed.m,k,count=12,target_Hz=15e9)
            residual=float(np.max(film.last_eigen_residuals))
        else:
            spectrum=Spectrum(cached['eigenvalues'][point_index],cached['modes'][point_index])
            operator,basis=film.bloch_operator(relaxed.m,k)
            vectors=np.einsum('...ci,k...c->...ik',basis,spectrum.modes).reshape(operator.shape[0],-1)
            scale=film.material.gamma*(8*film.material.A/film.material.Ms*(1/film.dx**2+1/film.dy**2)+2*abs(film.material.K)/film.material.Ms+1)
            residual=max(np.linalg.norm(operator@v-value*v)/scale for v,value in zip(vectors.T,spectrum.eigenvalues))
            if residual>1e-8:
                raise RuntimeError(f'Cached eigenvectors do not satisfy current physics: {residual:g}')
        values=branch_values(spectrum)
        if values['breathing_GHz'] is None or values['upper_branch_GHz'] is None:
            raise RuntimeError('Requested spectrum does not contain required bands; increase count or targets')
        rows.append(dict(k_rad_per_nm=k/1e9,reduced_ka_over_pi=float(reduced),**values))
        spectra.append(spectrum)
        residuals.append(float(residual))
        print(f'{n}×{n}, k a/π={reduced:+.3f}: {values}',flush=True)
    write_table(folder/f'bands_{n}.csv',list(rows[0]),[list(row.values()) for row in rows])
    np.savez_compressed(folder/f'bloch_{n}.npz',m=relaxed.m,k_rad_m=np.array([row['k_rad_per_nm']*1e9 for row in rows]),
                        eigenvalues=np.array([s.eigenvalues for s in spectra]),modes=np.array([s.modes for s in spectra]))
    report=dict(cells_per_axis=n,cell_nm=40/n,images_each_side=images,residual_torque_T=relaxed.torque_T,
                topology_open_y=film.topological_charge(relaxed.m),maximum_eigen_residual=max(residuals),seconds=time.monotonic()-start,raw_eigenpairs_reused=cached is not None,
                maximum_computed_growth_rate_per_s=max(row['maximum_growth_per_s'] for row in rows))
    return film,relaxed,spectra,rows,report


def unfolded_map(film,spectra,rows):
    """Intrinsic mode Fourier weights; does not model source/FFT intensity."""
    frequencies=np.linspace(0,55,551)
    qvalues=[];columns=[]
    x=(np.arange(film.nx)+.5)*film.dx
    for spectrum,row in zip(spectra,rows):
        k=row['k_rad_per_nm']*1e9
        positive=np.flatnonzero((spectrum.frequencies_Hz>1e6)&(spectrum.frequencies_Hz<65e9))
        for reciprocal in range(-4,5):
            q=k+2*np.pi*reciprocal/film.period_m
            if abs(q)>0.5e9+1: continue
            transform=np.einsum('kyxc,x->kyc',spectrum.modes[positive],np.exp(-1j*q*x))/np.sqrt(film.nx)
            weight=np.sum(abs(transform)**2,axis=(1,2))
            f=spectrum.frequencies_Hz[positive]/1e9
            width=.12 # visualization linewidth, not a damping or fitted parameter
            intensity=np.sum(weight[None,:]*width**2/((frequencies[:,None]-f[None,:])**2+width**2),axis=1)
            qvalues.append(q/1e9);columns.append(intensity)
    qvalues=np.array(qvalues);columns=np.array(columns).T
    unique=np.unique(np.round(qvalues,12))
    merged=np.stack([columns[:,np.isclose(qvalues,q,atol=1e-12,rtol=0)].mean(axis=1) for q in unique],axis=1)
    return unique,frequencies,merged


def fit_collective(rows):
    cosine=np.cos(np.pi*np.array([r['reduced_ka_over_pi'] for r in rows]))
    design=np.column_stack((np.ones_like(cosine),2*cosine))
    result={}
    for branch,squared in [('gyration',False),('breathing',True)]:
        values=np.array([r[branch+'_GHz'] for r in rows],dtype=float)
        fitted=np.linalg.lstsq(design,values**2 if squared else values,rcond=None)[0]
        estimate=design@fitted
        if squared: estimate=np.sqrt(np.maximum(estimate,0))
        result[branch]=dict(coefficients=fitted.tolist(),units='GHz²' if squared else 'GHz',
                            rms_frequency_residual_GHz=float(np.sqrt(np.mean((values-estimate)**2))))
    # Literal paper coefficients; keep their inconsistency with quoted ranges visible.
    result['literal_paper_fits']=dict(c1_GHz=1.15,c2_GHz=-.5,c3_GHz2=294.9,c4_GHz2=124,
         gyration_range_GHz=[.15,2.15],breathing_range_GHz=np.sqrt([294.9-248,294.9+248]).tolist(),
         note='Literal printed formulas/coefficients do not produce the quoted 0.1–4 and 13.4–20.4 GHz ranges; no correction assumed')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--meshes',type=int,nargs='+',default=[20,40])
    parser.add_argument('--reuse',action='store_true',help='Reuse raw eigenpairs only after checking equilibrium, k grid and current-operator residuals')
    parser.add_argument('--k-points',type=int,default=17)
    parser.add_argument('--images',type=int,default=32)
    parser.add_argument('--check-images',type=int,default=64)
    parser.add_argument('--output',type=Path,default=Path('validation/liu2024/fig2'))
    args=parser.parse_args()
    if args.k_points<3 or args.k_points%2==0 or min(args.meshes)<3 or max(args.meshes)>64:
        parser.error('Require odd k-points >= 3 and meshes between 3 and 64')
    if args.images<1 or args.check_images<=args.images: parser.error('Require check-images > images >= 1')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').unlink(missing_ok=True)
    fm,qfm,ffm=fm_reference(args.output)
    reports=[];all_rows=[]
    for n in sorted(set(args.meshes)):
        film,relaxed,spectra,rows,report=chain_scan(n,args.k_points,args.images,args.output,args.reuse)
        reports.append(report);all_rows.append(rows)
    center=rows[len(rows)//2]
    ranges={branch:[min(r[branch+'_GHz'] for r in rows),max(r[branch+'_GHz'] for r in rows)] for branch in ['gyration','breathing']}
    image_checks=[]
    refined=BlochChain(nx=film.nx,ny=film.ny,dx=film.dx,images=args.check_images,material=paper_material(),field_T=(0,0,0))
    refined_result=refined.relax(relaxed.m,maxiter=6000)
    if not refined_result.converged: raise RuntimeError('Image-convergence equilibrium failed')
    for reduced in [0,.5,1]:
        s=refined.bloch_modes(refined_result.m,reduced*np.pi/refined.period_m,count=12,target_Hz=15e9)
        refined_branches=branch_values(s)
        baseline=min(rows,key=lambda row:abs(row['reduced_ka_over_pi']-reduced))
        if not np.isclose(baseline['reduced_ka_over_pi'],reduced): continue
        differences={b:abs(refined_branches[b+'_GHz']-baseline[b+'_GHz']) for b in ['gyration','breathing','upper_branch']}
        image_checks.append(dict(reduced_ka_over_pi=reduced,absolute_frequency_changes_GHz=differences))
    image_error=max(v for entry in image_checks for v in entry['absolute_frequency_changes_GHz'].values())
    # Numerical finite-width FM control separates edge effects from bulk FMR formula.
    uniform=np.zeros(film.shape);uniform[...,2]=1
    fm_relaxed=film.relax(uniform,maxiter=6000)
    if not fm_relaxed.converged: raise RuntimeError('Finite-width FM relaxation failed')
    fm_spectrum=film.bloch_modes(fm_relaxed.m,0,count=8,target_Hz=40e9)
    finite_fmr=float(min(fm_spectrum.frequencies_Hz[fm_spectrum.frequencies_Hz>0])/1e9)
    fits=fit_collective(rows)
    q,f,intensity=unfolded_map(film,spectra,rows)
    write_table(args.output/'unfolded_intensity.csv',['frequency_GHz',*[f'k={value:.8g}_rad_per_nm' for value in q]],
                [[frequency,*line] for frequency,line in zip(f,intensity)])
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    qdense=np.linspace(-.5,.5,501)
    p=paper_material()
    quadratic=fm['FMR_GHz']+p.gamma/(2*np.pi)*2*p.A/p.Ms*(qdense*1e9)**2/1e9
    axes[0].plot(qdense,quadratic,'k-',label='Paper quadratic approximation')
    axes[0].plot(qfm,ffm,'o',ms=3,label='Numerical infinite-film dipole/exchange modes')
    axes[0].axhline(37.5,color='gray',ls='--',label='Paper FMR: 37.5 GHz')
    axes[0].plot(0,finite_fmr,'s',label='Finite-width Bloch strip, k=0')
    axes[0].set(title='Fig.2(b): ferromagnetic reference',xlabel='kx (rad/nm)',ylabel='Frequency (GHz)',xlim=(-.5,.5),ylim=(0,55))
    axes[0].legend(fontsize=7)
    im=axes[1].pcolormesh(q,f,np.log10(np.maximum(intensity/intensity.max(),1e-5)),shading='auto',cmap='magma',vmin=-4,vmax=0)
    axes[1].set(title='Fig.2(c): unfolded Bloch-mode weights',xlabel='kx (rad/nm)',ylabel='Frequency (GHz)',xlim=(-.5,.5),ylim=(0,55))
    fig.colorbar(im,ax=axes[1],label='log₁₀ normalized intrinsic weight')
    savefig(fig,args.output,'fig2_dispersion')
    fig,axes=plt.subplots(1,3,figsize=(12,3.8))
    for mesh_rows,report in zip(all_rows,reports):
        qmesh=np.array([r['reduced_ka_over_pi'] for r in mesh_rows])
        for ax,branch in zip(axes,['gyration','breathing','upper_branch']):
            ax.plot(qmesh,[r[branch+'_GHz'] for r in mesh_rows],'o-',ms=3,label=f"{report['cell_nm']:g} nm")
    axes[0].axhspan(.1,4,alpha=.12,color='gray',label='Paper reported range')
    axes[1].axhspan(13.4,20.4,alpha=.12,color='gray',label='Paper reported range')
    axes[2].axhline(34.5,color='gray',ls='--',label='Paper k=0 upper onset')
    for ax,title in zip(axes,['Gyration candidate','Breathing candidate','Lowest upper branch']):
        ax.set(title=title,xlabel='k a / π',ylabel='Frequency (GHz)');ax.legend(fontsize=7)
    savefig(fig,args.output,'fig2_band_comparison')
    upper_error=abs(center['upper_branch_GHz']/34.5-1)*100
    breathing_errors=abs(np.array(ranges['breathing'])/np.array([13.4,20.4])-1)*100
    checks=dict(paper_1nm_mesh_used=bool(np.isclose(film.dx,1e-9,rtol=1e-9,atol=1e-18)),
                no_instability_in_computed_modes=max(row['maximum_growth_per_s'] for row in rows)<=0,
                infinite_FM_FMR_within_1_percent=fm['FMR_difference_percent']<1,
                shifted_upper_onset_within_1_percent=upper_error<1,
                breathing_endpoints_within_5_percent=bool(np.max(breathing_errors)<5),
                gyration_endpoints_within_5_percent=bool(np.max(abs(np.array(ranges['gyration'])/np.array([.1,4])-1))<.05),
                periodic_image_change_below_0p01_GHz=image_error<.01)
    checks={key:bool(value) for key,value in checks.items()}
    summary=dict(paper=PAPER,model='Infinite x-periodic chain, 40 nm period, 40 nm open width, 1 nm thickness',
                 material=asdict(p),FM=fm,finite_width_FM_onset_GHz=finite_fmr,meshes=reports,
                 sampled_band_ranges_GHz=ranges,k0_upper_branch_GHz=center['upper_branch_GHz'],
                 k0_upper_difference_percent=upper_error,breathing_endpoint_errors_percent=breathing_errors.tolist(),
                 image_convergence_checks=image_checks,maximum_image_frequency_change_GHz=image_error,
                 collective_fits=fits,checks=checks,full_fig2_validation_passed=bool(all(checks.values())),
                 intensity_note='Intrinsic Bloch-mode weights, not a reproduction of finite-chain sinc-driven time/space FFT intensities',
                 limitations=['Finite chain length and exact boundary conditions unspecified in paper; infinite-chain approximation used',
                              'Band classification by frequency intervals, not a complete mode-character tracking algorithm',
                              'Near-zero nonoscillatory translation modes recorded as zero, not discarded',
                              'Targeted 12-mode spectrum is incomplete above sampled window; global magnonic gaps not certified',
                              'Published fit coefficients and reported band intervals are internally inconsistent',
                              'No nonlinear frequency comb or Fig.3 standing waves included in this benchmark'])
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
