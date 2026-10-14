"""Independent continuum magnetostatics and an analytical DMI helix benchmark."""
import json
from pathlib import Path
import numpy as np
from numpy.polynomial.legendre import leggauss
from spinfreq import ConfinedFilm,Film,Material,BlochChain
from spinfreq.model import MU0


def surface_demag(a,b,c,order=160):
    """Uniform rectangular prism Nzz from Coulomb surface integrals.

    Two Duffy triangles remove the same-face 1/r singularity. This does not
    call Newell functions or the simulator's demag kernel. Dimensions may use
    any common unit. Cyclic permutations yield Nxx and Nyy.
    """
    nodes,weights=leggauss(order)
    nodes=(nodes+1)/2;weights=weights/2
    r,s=np.meshgrid(nodes,nodes,indexing='ij')
    u=np.hypot(a,b*s);v=np.hypot(a*s,b)
    integrand=a*b*(a*(1-r)*b*(1-r*s)*(1/u-r/np.hypot(r*u,c))
                   +a*(1-r*s)*b*(1-r)*(1/v-r/np.hypot(r*v,c)))
    return float(2*np.sum(weights[:,None]*weights[None,:]*integrand)/(np.pi*a*b*c))


def prism_factors(dimensions,order=160):
    x,y,z=dimensions
    return np.array([surface_demag(y,z,x,order),surface_demag(x,z,y,order),surface_demag(x,y,z,order)])


def run_checks(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    records=[]
    cases=[('cube',[5,5,5],5,5,1,1,5),('paper_single_film',[40,40,1],40,40,1,1,1),
           ('standard_problem_4_geometry',[500,125,3],100,25,5,5,3)]
    for name,dimensions,nx,ny,dx,dy,thickness in cases:
        film=ConfinedFilm(nx=nx,ny=ny,dx=dx*1e-9,dy=dy*1e-9,thickness=thickness*1e-9)
        reference=prism_factors(dimensions,160)
        refined=prism_factors(dimensions,256)
        computed=[]
        for axis in range(3):
            m=np.zeros(film.shape);m[...,axis]=1
            computed.append(float(-film.demag_field(m)[...,axis].mean()/(MU0*film.material.Ms)))
        computed=np.array(computed)
        error=float(np.max(abs(computed-reference)))
        record=dict(name=name,dimensions_nm=dimensions,numerical_N=computed.tolist(),surface_integral_N=reference.tolist(),
                    max_absolute_error=error,quadrature_refinement_change=float(max(abs(refined-reference))),
                    trace=float(computed.sum()),passed=error<1e-6,
                    note='Uniform prism magnetostatics only; this does not validate Standard Problem 4 switching dynamics')
        records.append(record)
        print(record,flush=True)
    # Rohart/Thiaville continuum pitch: lambda=4*pi*A/|D|, no K/demag/field.
    material=Material(A=15e-12,D=3e-3,K=0,alpha=.05)
    pitch=4*np.pi*material.A/abs(material.D)
    film=Film(nx=32,ny=3,dx=pitch/32,material=material,demag=False,field_T=(0,0,0))
    q=-material.D/(2*material.A)
    x=(np.arange(film.nx)+.5)*film.dx
    m=np.zeros(film.shape);m[...,0]=np.sin(q*x)[None,:];m[...,2]=np.cos(q*x)[None,:]
    density=film.energy(m)/(film.nx*film.ny*film.dx*film.dy*film.thickness)
    reference_density=-material.D**2/(4*material.A)
    torque=film.torque(m)
    # Compare neighboring permitted winding numbers, not just the field residual.
    neighbor_energies=[]
    for winding in [0,-2]:
        qq=2*np.pi*winding/pitch
        trial=np.zeros(film.shape);trial[...,0]=np.sin(qq*x)[None,:];trial[...,2]=np.cos(qq*x)[None,:]
        neighbor_energies.append(film.energy(trial))
    helix=dict(pitch_nm=pitch/1e-9,q_rad_m=q,computed_energy_density_J_m3=density,
               analytical_energy_density_J_m3=reference_density,residual_torque_T=torque,
               energy_error_relative=float(abs(density/reference_density-1)),
               lower_than_neighbor_windings=bool(film.energy(m)<min(neighbor_energies)),
               passed=bool(abs(density/reference_density-1)<1e-10 and torque<1e-9 and film.energy(m)<min(neighbor_energies)))
    # Finite-difference pitch has tan(theta)=-D*h/(2A). Test the exact
    # discrete energy and bulk torque, excluding physical open-y edge torque.
    angle=-2*np.pi/32
    spacing=-2*material.A*np.tan(angle)/material.D
    discrete=BlochChain(nx=32,ny=5,dx=spacing,material=material,demag=False,
                        dmi_boundary='bond',field_T=(0,0,0),images=1)
    xx=(np.arange(32)+.5)*spacing
    state=np.zeros(discrete.shape);state[...,0]=np.sin(angle/spacing*xx);state[...,2]=np.cos(angle/spacing*xx)
    fd_density=discrete.energy(state)/(discrete.nx*discrete.ny*discrete.dx*discrete.dy*discrete.thickness)
    fd_reference=2*material.A/spacing**2*(1-np.cos(angle))+material.D/spacing*np.sin(angle)
    bulk_torque=float(np.linalg.norm(np.cross(state,discrete.effective_field(state))[1:-1],axis=-1).max())
    fd_helix=dict(discrete_pitch_nm=32*spacing/1e-9,cell_nm=spacing/1e-9,
        computed_energy_density_J_m3=fd_density,analytical_energy_density_J_m3=float(fd_reference),
        bulk_residual_torque_T=bulk_torque,energy_error_relative=float(abs(fd_density/fd_reference-1)),
        note='Open-y edge torque is physical and excluded; only bulk stationarity is tested',
        passed=bool(abs(fd_density/fd_reference-1)<1e-10 and bulk_torque<1e-9))
    summary=dict(prism_checks=records,DMI_helix=helix,finite_difference_DMI_helix=fd_helix,
        all_passed=all(r['passed'] for r in records) and helix['passed'] and fd_helix['passed'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    if not summary['all_passed']: raise RuntimeError('Independent standard check failed')
    return summary

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('validation/liu2024/conditions/standard_checks'))
    run_checks(parser.parse_args().output)
