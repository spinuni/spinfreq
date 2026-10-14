import importlib.util
from pathlib import Path
import sys
import numpy as np
from spinfreq import Material


def module(name):
    directory=Path(__file__).resolve().parents[1]/'benchmarks'
    spec=importlib.util.spec_from_file_location(name,directory/f'{name}.py')
    loaded=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(directory))
    try: spec.loader.exec_module(loaded)
    finally: sys.path.pop(0)
    return loaded


def test_independent_prism_integral():
    checks=module('standard_checks')
    np.testing.assert_allclose(checks.prism_factors([1,1,1],64),1/3,atol=1e-12)
    factors=checks.prism_factors([40,40,1],128)
    np.testing.assert_allclose(factors,[.03519867118536,.03519867118536,.9296026576293],atol=1e-11)
    assert abs(sum(factors)-1)<1e-11


def test_pinned_spin_projection_and_macrospin_modes():
    conditions=module('liu2024_conditions')
    p=Material(A=0,D=0,K=0,alpha=0)
    film=conditions.PinnedChain(nx=3,ny=5,dx=1e-9,pinned_nm=2,demag=False,
                                material=p,field_T=(0,0,1))
    m=np.zeros(film.shape);m[...,2]=1
    m[film.free]=[.1,0,np.sqrt(.99)]
    r=film.relax(m)
    assert r.converged
    np.testing.assert_array_equal(r.m[~film.free],np.broadcast_to([0,0,1],r.m[~film.free].shape))
    matrix,_=film.bloch_operator(r.m,0,assemble=True)
    assert matrix.shape==(6,6)
    spectrum=film.bloch_modes(r.m,0,count=2,target_Hz=.9*p.gamma/(2*np.pi))
    np.testing.assert_allclose(abs(spectrum.eigenvalues.imag),p.gamma,rtol=1e-9)
    np.testing.assert_array_equal(spectrum.modes[:,~film.free],0)


def test_pinned_projected_gradient():
    conditions=module('liu2024_conditions')
    film=conditions.PinnedChain(nx=5,ny=5,dx=1e-9,pinned_nm=1,demag=False,field_T=(0,0,.1))
    m=conditions.seed(film);m[~film.free]=(0,0,1)
    v=np.random.default_rng(7).normal(size=film.shape);v[~film.free]=0
    eps=1e-5
    finite=(film.energy(m+eps*v)-film.energy(m-eps*v))/(2*eps)
    analytical=-film.material.Ms*np.sum(film.effective_field(m)*v)*film.dx*film.dy*film.thickness
    np.testing.assert_allclose(finite,analytical,rtol=1e-8,atol=1e-30)


def test_residual_refinement_keeps_pinned_spins():
    conditions=module('liu2024_conditions')
    from spinfreq import refine_equilibrium
    p=Material(A=0,D=0,K=0)
    film=conditions.PinnedChain(nx=3,ny=5,dx=1e-9,pinned_nm=2,demag=False,
                                material=p,field_T=(0,0,1))
    m=np.zeros(film.shape);m[...,2]=1;m[film.free]=[.01,0,np.sqrt(1-.01**2)]
    result=refine_equilibrium(film,m,tolerance_T=1e-9)
    assert result.converged and result.torque_T<1e-9
    np.testing.assert_array_equal(result.m[~film.free],np.broadcast_to([0,0,1],result.m[~film.free].shape))
    np.testing.assert_allclose(np.linalg.norm(result.m,axis=-1),1,atol=1e-14)
