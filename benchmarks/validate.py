"""Reproducible analytical benchmarks and skyrmion convergence; all quantities SI."""
import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from spinfreq import Film, Material, skyrmion_lattice
from spinfreq.model import MU0


def uniform(film, axis=2):
    m = np.zeros(film.shape)
    m[..., axis] = 1
    return m


def savefig(fig, folder, name):
    fig.tight_layout()
    for suffix in ('png', 'pdf'):
        fig.savefig(folder/f'{name}.{suffix}', dpi=180)
    plt.close(fig)


def table(folder, name, header, rows):
    with (folder/f'{name}.csv').open('w', newline='') as file:
        writer = csv.writer(file, lineterminator='\n')
        writer.writerow(header)
        writer.writerows(rows)


def analytical(folder):
    p = Material(A=15e-12, D=0, K=0, alpha=0)
    fields = np.linspace(0.1, 1.0, 13)
    inplane, perpendicular = [], []
    for b in fields:
        film = Film(nx=3, ny=3, material=p, field_T=(b,0,0))
        values = film.modes(uniform(film,0)).frequencies_Hz
        inplane.append(min(values[values>0]))
        # Perpendicular saturation requires B > mu0 Ms.
        film = Film(nx=3, ny=3, material=p, field_T=(0,0,b+MU0*p.Ms))
        values = film.modes(uniform(film)).frequencies_Hz
        perpendicular.append(min(values[values>0]))
    inplane_ref = p.gamma/(2*np.pi)*np.sqrt(fields*(fields+MU0*p.Ms))
    perpendicular_ref = p.gamma/(2*np.pi)*fields
    fig, axes = plt.subplots(1,2,figsize=(9,3.5))
    for ax, computed, reference, label in zip(axes,[inplane,perpendicular],[inplane_ref,perpendicular_ref],['In-plane Kittel','Perpendicular Kittel']):
        ax.plot(fields,reference/1e9,label='Analytical')
        ax.plot(fields,np.array(computed)/1e9,'o',mfc='none',label='LLG eigenvalues')
        ax.set(xlabel='B (T)' if ax is axes[0] else 'B − μ₀Ms (T)',ylabel='Frequency (GHz)',title=label)
        ax.legend()
    savefig(fig,folder,'kittel')
    table(folder,'kittel',['field_or_effective_field_T','inplane_numerical_Hz','inplane_analytical_Hz','perpendicular_numerical_Hz','perpendicular_analytical_Hz'],zip(fields,inplane,inplane_ref,perpendicular,perpendicular_ref))
    # Fundamental thickness mode for perpendicular saturation, diagonal xy kernel.
    film = Film(nx=9,ny=3,dx=10e-9,dy=10e-9,thickness=5e-9,material=p,field_T=(0,0,1.2))
    b = 1.2-MU0*p.Ms
    exchange = 2*p.A/p.Ms*film.k2
    reference = p.gamma/(2*np.pi)*np.sqrt((b+exchange)*(b+exchange+MU0*p.Ms*(1-film.nzz)))
    actual = film.modes(uniform(film)).frequencies_Hz
    actual = np.sort(actual[actual>0])
    expected = np.sort(reference.ravel())
    k = np.sqrt(film.k2).ravel()
    order = np.argsort(k)
    fig,ax = plt.subplots(figsize=(6,4))
    ax.plot(k[order]/1e9,reference.ravel()[order]/1e9,'o',label='Thickness-averaged dipole/exchange formula')
    # Compare multisets: degeneracies preclude individual eigenvector labels.
    ax.plot(k[order]/1e9,actual[np.argsort(np.argsort(reference.ravel()))][order]/1e9,'x',label='LLG eigenvalues (sorted matching)')
    ax.set(xlabel='|k| (nm⁻¹)',ylabel='Frequency (GHz)',title='Perpendicular-film spin waves')
    ax.legend(fontsize=8)
    savefig(fig,folder,'dispersion')
    table(folder,'dispersion',['sorted_numerical_Hz','sorted_analytical_Hz'],zip(actual,expected))
    # Independent Gilbert susceptibility with exp(+i omega t), without demag.
    p_response = Material(D=0,K=0,alpha=0.03)
    film = Film(nx=3,ny=3,material=p_response,field_T=(0,0,0.3),demag=False)
    f0 = p_response.gamma*0.3/(2*np.pi)
    frequencies = np.linspace(0.75*f0,1.25*f0,201)
    drive = 1e-5
    response = film.response(uniform(film),frequencies,(drive,0,0))
    chi = response[...,0].mean(axis=(1,2))/drive
    omega = 2*np.pi*frequencies
    c = p_response.gamma*0.3+1j*p_response.alpha*omega
    chi_ref = p_response.gamma*c/(c*c-omega*omega)
    fig,axes = plt.subplots(1,2,figsize=(9,3.5))
    for ax,component,label in [(axes[0],np.real,'Re χxx (T⁻¹)'),(axes[1],lambda x:-x.imag,'−Im χxx (T⁻¹)')]:
        ax.plot(frequencies/1e9,component(chi_ref),label='Analytical Gilbert susceptibility')
        ax.plot(frequencies[::8]/1e9,component(chi)[::8],'o',mfc='none',label='Frequency solver')
        ax.set(xlabel='Frequency (GHz)',ylabel=label)
        ax.legend(fontsize=8)
    savefig(fig,folder,'susceptibility')
    table(folder,'susceptibility',['frequency_Hz','numeric_real_per_T','numeric_imag_per_T','analytical_real_per_T','analytical_imag_per_T'],zip(frequencies,chi.real,chi.imag,chi_ref.real,chi_ref.imag))
    errors = dict(kittel_inplane_relative=float(np.max(abs(np.array(inplane)/inplane_ref-1))),
                  kittel_perpendicular_relative=float(np.max(abs(np.array(perpendicular)/perpendicular_ref-1))),
                  dipole_exchange_relative=float(np.max(abs(actual/expected-1))),
                  susceptibility_relative=float(np.max(abs(chi-chi_ref)/abs(chi_ref))))
    if max(errors.values()) > 1e-8:
        raise RuntimeError(f'Analytical benchmark failed: {errors}')
    return errors


def stable_equilibrium(film):
    # Exact reflection symmetry can keep a minimizer on a grid-pinning saddle.
    candidates = []
    for offset in (0.0, 0.5):
        seed = skyrmion_lattice(film)
        if offset:
            phase = np.exp(-1j*offset*(film.kx*film.dx+film.ky*film.dy))
            seed = np.fft.ifft2(np.fft.fft2(seed,axes=(0,1))*phase[...,None],axes=(0,1)).real
            seed /= np.linalg.norm(seed,axis=-1,keepdims=True)
        result = film.relax(seed,maxiter=4000)
        if result.converged:
            spectrum = film.modes(result.m)
            candidates.append((result,spectrum,offset))
    stable = [entry for entry in candidates if entry[1].eigenvalues.real.max() <= 0]
    if not stable:
        raise RuntimeError('No dynamically stable relaxed candidate; cannot report equilibrium absorption')
    result,spectrum,offset = min(stable,key=lambda entry:entry[0].energy_J)
    diagnostics = [dict(offset_cells=o,energy_J=r.energy_J,max_growth_per_s=float(s.eigenvalues.real.max())) for r,s,o in candidates]
    return result,spectrum,offset,diagnostics


def skyrmions(folder, sizes):
    rows = []
    pinning = {}
    for n in sizes:
        film = Film(nx=n,ny=n,dx=48e-9/n,thickness=1e-9)
        result,spectrum,offset,diagnostics = stable_equilibrium(film)
        pinning[str(n)] = dict(selected_offset_cells=offset,candidates=diagnostics)
        frequencies = spectrum.frequencies_Hz
        positive = np.flatnonzero(frequencies>1e6)
        first = positive[:3]
        rows.append([n,48/n,film.topological_charge(result.m),result.torque_T,result.energy_J,*list(frequencies[first]/1e9),float(spectrum.eigenvalues.real.max())])
        np.savez_compressed(folder/f'skyrmion_{n}.npz',m=result.m,eigenvalues=spectrum.eigenvalues,modes=spectrum.modes)
        print(f'mesh {n}: Q={rows[-1][2]:.6f}, f(GHz)={rows[-1][5:8]}',flush=True)
    table(folder,'mesh_convergence',['cells_per_axis','cell_nm','charge','torque_T','energy_J','f1_GHz','f2_GHz','f3_GHz','max_growth_per_s'],rows)
    data = np.array(rows)
    fig,axes = plt.subplots(1,2,figsize=(9,3.5))
    for j in range(3):
        axes[0].plot(data[:,1],data[:,5+j],'o-',label=f'Positive-frequency rank {j+1}')
    axes[0].set(xlabel='Cell size (nm), fixed 48 × 48 nm cell',ylabel='Frequency (GHz)')
    axes[0].legend(fontsize=8)
    axes[1].plot(data[:,1],data[:,2],'o-',label='Spectral charge')
    axes[1].axhline(-1,color='k',ls='--',label='Resolved skyrmion: Q = −1')
    axes[1].set(xlabel='Cell size (nm)',ylabel='Topological charge')
    axes[1].legend(fontsize=8)
    savefig(fig,folder,'mesh_convergence')
    # A separate moderate grid keeps driven sweep affordable and explicit.
    n = 16
    film = Film(nx=n,ny=n,dx=48e-9/n)
    result,spectrum,offset,diagnostics = stable_equilibrium(film)
    frequencies = np.linspace(0.1e9,100e9,241)
    fig,ax = plt.subplots(figsize=(7,4))
    for name,drive in [('in_plane_x',(1e-5,0,0)),('out_of_plane_z',(0,0,1e-5))]:
        response = film.response(result.m,frequencies,drive)
        power = film.absorbed_power(frequencies,response,drive)
        table(folder,f'absorption_{name}',['frequency_Hz','power_W'],zip(frequencies,power))
        np.savez_compressed(folder/f'response_{name}.npz',frequencies_Hz=frequencies,delta_m=response,drive_T=drive)
        ax.plot(frequencies/1e9,power,label=name.replace('_',' '))
    for f in spectrum.frequencies_Hz:
        if 0 < f < frequencies[-1]:
            ax.axvline(f/1e9,color='gray',alpha=0.3,lw=0.7)
    ax.set(xlabel='Frequency (GHz)',ylabel='Absorbed power (W)',title='Skyrmion response; vertical lines: eigenfrequencies')
    ax.legend()
    savefig(fig,folder,'skyrmion_absorption')
    fig,axes = plt.subplots(1,4,figsize=(12,3))
    extent = [0,48,0,48]
    im=axes[0].imshow(result.m[...,2],origin='lower',extent=extent,cmap='RdBu_r',vmin=-1,vmax=1)
    axes[0].set_title('Equilibrium mz')
    fig.colorbar(im,ax=axes[0],shrink=0.7)
    indices = np.flatnonzero(spectrum.frequencies_Hz>1e6)[:3]
    for ax,index in zip(axes[1:],indices):
        mode = spectrum.modes[index]
        # Choose global phase so the largest complex component is positive real.
        phase = np.angle(mode.ravel()[np.argmax(abs(mode))])
        mode = mode*np.exp(-1j*phase)
        im=ax.imshow(mode[...,2].real,origin='lower',extent=extent,cmap='RdBu_r')
        ax.set_title(f'Re δmz: {spectrum.frequencies_Hz[index]/1e9:.2f} GHz')
        fig.colorbar(im,ax=ax,shrink=0.7)
    for ax in axes:
        ax.set(xlabel='x (nm)',ylabel='y (nm)')
    savefig(fig,folder,'skyrmion_modes')
    return dict(geometry=dict(period_x_m=48e-9,period_y_m=48e-9,thickness_m=1e-9),material=asdict(film.material),field_T=film.field_T.tolist(),meshes=sizes,driven_grid=n,pinning_diagnostics=pinning,
                last_step_relative_frequency_change=(abs(data[-1,5:8]-data[-2,5:8])/abs(data[-1,5:8])).tolist() if len(rows)>1 else None)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('validation'))
    parser.add_argument('--meshes',type=int,nargs='+',default=[12,16,20,24])
    parser.add_argument('--analytical-only',action='store_true')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').unlink(missing_ok=True)
    summary={'analytical_relative_errors':analytical(args.output)}
    if not args.analytical_only:
        summary['skyrmion']=skyrmions(args.output,args.meshes)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
