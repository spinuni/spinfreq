import numpy as np
from scipy.linalg import eigvals
from spinfreq import BlochChain,Material
from spinfreq.bloch import cell_tensor


def test_bloch_exchange_fourier_dispersion():
    p=Material(D=0,K=0,alpha=0)
    film=BlochChain(nx=5,ny=3,dx=4e-9,material=p,field_T=(0,0,1),demag=False)
    m=np.zeros(film.shape);m[...,2]=1
    k=.27*np.pi/film.period_m
    matrix,basis=film.bloch_operator(m,k,assemble=True)
    computed=np.sort(eigvals(matrix).imag[eigvals(matrix).imag>0])
    kx=k+2*np.pi*np.arange(film.nx)/film.period_m
    ky=np.pi*np.arange(film.ny)/(film.ny*film.dy)
    exchange=2*p.A/p.Ms*(4*np.sin(kx[None,:]*film.dx/2)**2/film.dx**2+4*np.sin(ky[:,None]*film.dy/2)**2/film.dy**2)
    predicted=np.sort((p.gamma*(1+exchange)).ravel())
    np.testing.assert_allclose(computed,predicted,rtol=1e-10)


def test_bloch_field_is_hermitian_and_k_conjugate():
    film=BlochChain(nx=5,ny=4,images=4)
    rng=np.random.default_rng(8)
    a=rng.normal(size=film.shape)+1j*rng.normal(size=film.shape)
    b=rng.normal(size=film.shape)+1j*rng.normal(size=film.shape)
    k=.4*np.pi/film.period_m
    np.testing.assert_allclose(np.vdot(a,film.internal_field_bloch(b,k)),np.vdot(film.internal_field_bloch(a,k),b),rtol=1e-10)
    np.testing.assert_allclose(film.internal_field_bloch(a,k).conj(),film.internal_field_bloch(a.conj(),-k),rtol=1e-12)


def test_periodic_equilibrium_field_gradient():
    film=BlochChain(nx=5,ny=4,images=4)
    rng=np.random.default_rng(2)
    m,v=rng.normal(size=film.shape),rng.normal(size=film.shape)
    epsilon=1e-5
    numerical=(film.energy(m+epsilon*v)-film.energy(m-epsilon*v))/(2*epsilon)
    expected=-film.material.Ms*np.sum(film.effective_field(m)*v)*film.dx*film.dy*film.thickness
    np.testing.assert_allclose(numerical,expected,rtol=1e-8,atol=1e-30)


def test_targeted_modes_match_dense_eigenvalues():
    film=BlochChain(nx=5,ny=3,material=Material(D=0),demag=False,field_T=(0,0,1))
    m=np.zeros(film.shape);m[...,2]=1
    k=.3*np.pi/film.period_m
    matrix,_=film.bloch_operator(m,k,assemble=True)
    dense=eigvals(matrix)
    spec=film.bloch_modes(m,k,count=6,target_Hz=80e9)
    for value in spec.eigenvalues:
        assert np.min(abs(dense-value))/abs(value)<1e-8
    assert max(film.last_eigen_residuals)<1e-8
