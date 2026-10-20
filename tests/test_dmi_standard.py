"""Single-cell axes and signed-wavevector DMI conventions."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import eigvals

from spinfreq import Film, ConfinedFilm, BlochChain, Material


@pytest.mark.parametrize('geometry',[Film,ConfinedFilm])
def test_single_cell_macrospin_frequency_and_decay(geometry):
    # A cubic confined cell has isotropic demag; a periodic film is checked
    # with demag disabled. Exchange contributes zero for one uniform spin.
    p=Material(K=0,D=0,alpha=.01)
    film=geometry(nx=1,ny=1,dx=1e-9,thickness=1e-9,material=p,
                  field_T=(0,0,.5),demag=(geometry is ConfinedFilm))
    m=np.array([[[0.,0.,1.]]])
    values=film.modes(m).eigenvalues
    expected=p.gamma*.5/(1+p.alpha**2)
    np.testing.assert_allclose(np.sort(values.imag),[-expected,expected],rtol=1e-12)
    np.testing.assert_allclose(values.real,-p.alpha*expected,rtol=1e-11)
    assert film.topological_charge(m)==0


@pytest.mark.parametrize('nx,ny',[(2,1),(1,2),(1,1)])
def test_short_axis_field_energy_gradient(nx,ny):
    film=ConfinedFilm(nx=nx,ny=ny,dx=1e-9,dy=2e-9,thickness=1e-9)
    rng=np.random.default_rng(93)
    m,v=rng.normal(size=film.shape),rng.normal(size=film.shape)
    eps=1e-5
    measured=(film.energy(m+eps*v)-film.energy(m-eps*v))/(2*eps)
    expected=-film.material.Ms*np.sum(film.effective_field(m)*v)*film.dx*film.dy*film.thickness
    np.testing.assert_allclose(measured,expected,rtol=1e-8,atol=1e-30)
    single='y' if ny==1 else 'x'
    assert np.all(film.derivative(m,single)==0)


def test_one_cell_bloch_phase_exchange_and_signed_DMI_dispersion():
    # exp(i k x + lambda t): DMI shifts lambda by +i gamma 2D sin(kh)/(Ms h).
    # Both conjugate branches at fixed k are needed; f>0 physical exp(-iwt)
    # corresponds to the negative-imaginary branch.
    p=Material(D=-3e-3,K=0,alpha=0)
    film=BlochChain(nx=1,ny=1,dx=2e-9,dy=2e-9,material=p,
                    field_T=(0,1,0),demag=False,images=1,dmi_boundary='bond')
    m=np.array([[[0.,1.,0.]]])
    for k in [-.08e9,.08e9]:
        matrix,_=film.bloch_operator(m,k,assemble=True)
        values=eigvals(matrix)
        h=1+4*p.A/(p.Ms*film.dx**2)*(1-np.cos(k*film.dx))
        shift=2*p.D/(p.Ms*film.dx)*np.sin(k*film.dx)
        np.testing.assert_allclose(np.sort(values.imag),p.gamma*np.array([shift-h,shift+h]),rtol=1e-12)
        np.testing.assert_allclose(values.real,0,atol=1e-4)


@pytest.mark.parametrize('count',[0,-1,3.5])
def test_invalid_cell_counts_do_not_change_geometry_silently(count):
    with pytest.raises(ValueError):ConfinedFilm(nx=count,ny=1)


def benchmark():
    path=Path(__file__).resolve().parents[1]/'benchmarks/dmi_standard_problem.py'
    spec=importlib.util.spec_from_file_location('dmi_standard',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_DMI_periodic_Jacobian_against_analytical_signed_dispersion(tmp_path):
    result=benchmark().analytic_nonreciprocity(tmp_path)
    assert result['passed']
    assert result['inferred_D_J_m2']<0
    assert result['max_subspace_residual']<1e-12


def test_DMI_reference_checksum_rejects_changed_data(tmp_path):
    module=benchmark();name=next(iter(module.HASHES))
    path=tmp_path/name;path.parent.mkdir(parents=True);path.write_text('changed data')
    with pytest.raises(ValueError,match='checksum'):module.references(tmp_path)
