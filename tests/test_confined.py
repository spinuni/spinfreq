import numpy as np
import pytest
from spinfreq.confined import ConfinedFilm
from spinfreq import Material
from spinfreq.model import MU0


def test_newell_cube_self_trace_and_symmetry():
    film=ConfinedFilm(nx=5,ny=5,dx=1e-9,thickness=1e-9)
    np.testing.assert_allclose(film.demag_self_tensor,1/3,atol=1e-13)
    rng=np.random.default_rng(7)
    a,b=rng.normal(size=film.shape),rng.normal(size=film.shape)
    np.testing.assert_allclose(np.sum(a*film.demag_field(b)),np.sum(b*film.demag_field(a)),rtol=1e-12)
    assert np.sum(a*film.demag_field(a))<0


def test_open_boundary_field_gradient():
    film=ConfinedFilm(nx=5,ny=4,dx=1.5e-9,dy=2e-9,thickness=1e-9)
    rng=np.random.default_rng(5)
    m,v=rng.normal(size=film.shape),rng.normal(size=film.shape)
    eps=1e-5
    measured=(film.energy(m+eps*v)-film.energy(m-eps*v))/(2*eps)
    expected=-film.material.Ms*np.sum(film.effective_field(m)*v)*film.dx*film.dy*film.thickness
    np.testing.assert_allclose(measured,expected,rtol=1e-8,atol=1e-30)


def test_exchange_does_not_wrap_and_dmi_edge_torque():
    film=ConfinedFilm(nx=5,ny=5,demag=False,field_T=(0,0,0),material=Material(K=0,D=0))
    m=np.zeros(film.shape)
    m[:,0,0]=1
    assert np.all(film.effective_field(m)[:,-1]==0)
    p=Material(K=0)
    film=ConfinedFilm(nx=5,ny=5,demag=False,field_T=(0,0,0),material=p)
    m=np.zeros(film.shape)
    m[...,2]=1
    field=film.effective_field(m)
    np.testing.assert_allclose(field[:,0,0],p.D/(p.Ms*film.dx))
    np.testing.assert_allclose(field[:,-1,0],-p.D/(p.Ms*film.dx))
    np.testing.assert_allclose(field[1:-1,1:-1],0)


def test_matrix_free_matches_dense_response():
    film=ConfinedFilm(nx=3,ny=3,demag=False,material=Material(D=0),field_T=(0,0,1))
    m=np.zeros(film.shape)
    m[...,2]=1
    operator,_=film.linear_operator(m)
    dense,_=film.linearize(m)
    v=np.random.default_rng(6).normal(size=dense.shape[0])
    np.testing.assert_allclose(operator@v,dense@v,rtol=1e-12)
    np.testing.assert_allclose(film.response_iterative(m,[10e9]),film.response(m,[10e9]),rtol=1e-6,atol=1e-12)


@pytest.mark.parametrize('nx,ny',[(4,3),(5,1),(1,4),(1,1)])
def test_mumax_dmi_ghost_stencil_matches_boundary_correction(nx,ny):
    # Independently implement the four neighbor terms in cuda/dmi.cu.
    p=Material(K=0)
    film=ConfinedFilm(nx=nx,ny=ny,demag=False,material=p,field_T=(0,0,0))
    m=np.random.default_rng(11).normal(size=film.shape)
    expected=np.zeros_like(m)
    for y in range(film.ny):
        for x in range(film.nx):
            center=m[y,x]
            for axis,spacing,component in [(1,film.dx,0),(0,film.dy,1)]:
                for direction in (-1,1):
                    yy,xx=y+(direction if axis==0 else 0),x+(direction if axis==1 else 0)
                    if 0<=yy<film.ny and 0<=xx<film.nx:
                        neighbor=m[yy,xx]
                    else:
                        neighbor=center.copy()
                        neighbor[component]-=direction*spacing*p.D/(2*p.A)*center[2]
                        neighbor[2]+=direction*spacing*p.D/(2*p.A)*center[component]
                    expected[y,x]+=2*p.A/(p.Ms*spacing**2)*(neighbor-center)
                    expected[y,x,component]+=direction*p.D/(p.Ms*spacing)*neighbor[2]
                    expected[y,x,2]-=direction*p.D/(p.Ms*spacing)*neighbor[component]
    np.testing.assert_allclose(film.effective_field(m),expected,rtol=1e-12,atol=1e-12)


def test_thin_cell_demag_trace():
    film=ConfinedFilm(nx=3,ny=3,dx=2e-9,dy=3e-9,thickness=1e-9)
    np.testing.assert_allclose(film.demag_self_tensor.sum(),1,atol=1e-12)
    assert np.all(film.demag_self_tensor>0)


def test_far_demag_kernel_approaches_dipole():
    film=ConfinedFilm(nx=60,ny=3,dx=1e-9,thickness=1e-9)
    m=np.zeros(film.shape)
    m[1,0,2]=1
    field=film.demag_field(m)[1,50,2]
    expected=-MU0*film.material.Ms*(film.dx*film.dy*film.thickness)/(4*np.pi*(50*film.dx)**3)
    np.testing.assert_allclose(field,expected,rtol=1e-5)
