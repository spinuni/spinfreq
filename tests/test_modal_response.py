import numpy as np
from scipy.integrate import solve_ivp

from spinfreq import Film, ConfinedFilm, Material, ModalResponse
from spinfreq.model import MU0


def macrospin():
    p=Material(Ms=580e3,A=0,D=0,K=.6e6,alpha=.03,gamma=1.7595e11)
    film=ConfinedFilm(nx=1,ny=1,dx=4e-9,dy=8e-9,thickness=1e-9,material=p,field_T=(0,0,.1))
    m=np.array([[[0.,0.,1.]]]);n=film.demag_self_tensor
    b=.1+2*p.K/p.Ms-MU0*p.Ms*n[2]
    hx=b+MU0*p.Ms*n[0];hy=b+MU0*p.Ms*n[1]
    matrix=p.gamma/(1+p.alpha**2)*np.array([[-p.alpha*hx,-hy],[hx,-p.alpha*hy]])
    return film,m,matrix


def test_prepared_response_matches_analytic_gilbert_susceptibility():
    film,m,matrix=macrospin();prepared=ModalResponse(film,m)
    frequencies=np.array([20.,35.,45.])*1e9
    drive=np.array([1e-6,2e-7j,0])
    p=film.material
    force=p.gamma/(1+p.alpha**2)*np.array([p.alpha*drive[0]+drive[1],-drive[0]+p.alpha*drive[1]])
    expected=np.array([np.linalg.solve(2j*np.pi*f*np.eye(2)-matrix,force) for f in frequencies])
    fields=prepared.response(frequencies,drive)
    np.testing.assert_allclose(fields[:,0,0,:2],expected,rtol=1e-12,atol=1e-15)
    assert max(prepared.last_response_residuals)<1e-12


def test_raised_cosine_multitone_transient_against_independent_time_integration():
    film,m,matrix=macrospin();prepared=ModalResponse(film,m);p=film.material
    frequencies=np.array([19.,35.])*1e9
    drives=np.array([[1e-6,0,0],[0,5e-7j,0]])
    times=np.linspace(0,2e-9,401);ramp=3e-10
    def rhs(t,u):
        envelope=.5*(1-np.cos(np.pi*t/ramp)) if t<ramp else 1.
        b=envelope*np.real((drives*np.exp(2j*np.pi*frequencies*t)[:,None]).sum(axis=0))
        force=p.gamma/(1+p.alpha**2)*np.array([p.alpha*b[0]+b[1],-b[0]+p.alpha*b[1]])
        return matrix@u+force
    independent=solve_ivp(rhs,(0,times[-1]),np.zeros(2),t_eval=times,rtol=1e-10,atol=1e-15)
    assert independent.success
    actual=prepared.ramped_mean_response(times,frequencies,drives,ramp,batch_samples=37)
    np.testing.assert_allclose(actual[:,:2],independent.y.T,rtol=2e-7,atol=2e-14)
    np.testing.assert_allclose(actual[:,2],0,atol=1e-30)


def test_antiphase_spatial_drive_can_have_zero_mean_response():
    film=Film(nx=2,ny=2,dx=2e-9,material=Material(D=0),field_T=(0,0,.1))
    m=np.zeros(film.shape);m[...,2]=1
    model=ModalResponse(film,m)
    drive=np.zeros(film.shape);drive[:,0,0]=1e-6;drive[:,1,0]=-1e-6
    mean=model.ramped_mean_response(np.linspace(0,1e-9,101),[20e9],[drive],2e-10)
    # Translational symmetry separates the alternating drive from the k=0 mean.
    np.testing.assert_allclose(mean,0,atol=1e-18)
