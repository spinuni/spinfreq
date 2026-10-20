import numpy as np
import pytest
from spinfreq import Material
from spinfreq.confined import ConfinedFilm
from spinfreq.dynamics import integrate,sinc_drive,harmonic_drive,cell_spectrum,left_strip


def test_nonlinear_macrospin_against_exact_solution():
    p=Material(A=0,D=0,K=0,alpha=.1)
    film=ConfinedFilm(nx=3,ny=3,material=p,demag=False,field_T=(0,0,.2))
    theta=.8
    m=np.broadcast_to([np.sin(theta),0,np.cos(theta)],film.shape).copy()
    times=np.linspace(0,1e-9,201)
    result=integrate(film,m,times,chunk_samples=35,rtol=1e-9,atol=1e-11)
    w=p.gamma*.2/(1+p.alpha**2)
    z=np.tanh(np.arctanh(np.cos(theta))+p.alpha*w*times)
    xy=np.sqrt(1-z*z)
    exact=np.stack((xy*np.cos(w*times),xy*np.sin(w*times),z),axis=-1)
    np.testing.assert_allclose(result.mean_m,exact,atol=1e-8)
    assert result.max_norm_error<1e-8


def test_paper_sinc_convention_and_strip():
    np.testing.assert_allclose(sinc_drive()(1e-9),[.005,0,0])
    np.testing.assert_allclose(sinc_drive()(1e-9+1/(2*50e9)),0,atol=1e-16)
    np.testing.assert_allclose(harmonic_drive()(1/(4*13.4e9)),[.005,0,0])
    film=ConfinedFilm(nx=80,ny=4,dx=1e-9,demag=False)
    assert left_strip(film).sum()==160


def test_fft_cell_average_preserves_opposite_phase_modes():
    times=np.arange(1000)*5e-12
    signal=.01*np.sin(2*np.pi*2e9*times)
    m=np.zeros((len(times),2,3))
    m[:,0,2]=signal
    m[:,1,2]=-signal
    f,a,p=cell_spectrum(times,m,window='rectangular')
    index=np.argmax(a)
    np.testing.assert_allclose(f[index],2e9)
    np.testing.assert_allclose(a[index],.01,atol=1e-12)
    np.testing.assert_allclose(p[index],.0001,atol=1e-12)
    assert np.max(abs(m.mean(axis=1)))==0


def test_scalar_spectrum_matches_vector_and_transient_slicing():
    times=np.arange(1000)*5e-12
    m=np.zeros((len(times),2,3))
    m[:,:,2]=.01*np.sin(2*np.pi*2e9*times)[:,None]
    vector=cell_spectrum(times,m,discard_s=1e-9)
    scalar=cell_spectrum(times,m[...,2],component=None,discard_s=1e-9)
    for a,b in zip(vector,scalar): np.testing.assert_array_equal(a,b)


def test_space_time_fft_wavevector_units_and_opposite_rows():
    from spinfreq.dynamics import space_time_spectrum
    times=np.arange(1000)*5e-12
    x=np.arange(32)*1e-9
    k=2*np.pi*3/(32e-9)
    wave=.01*np.cos(2*np.pi*2e9*times[:,None]+k*x[None,:])
    trace=np.stack([wave,-wave],axis=1)
    q,f,power=space_time_spectrum(times,trace,1e-9,time_window='rectangular',space_window='rectangular')
    it,ix=np.unravel_index(np.argmax(power),power.shape)
    np.testing.assert_allclose([f[it],q[ix],power[it,ix]],[2e9,k,.0001],rtol=1e-10)


@pytest.mark.parametrize('samples',[1000,1001])
@pytest.mark.parametrize('temporal_sign',[-1,1])
def test_space_time_fft_exact_signed_bins_for_even_and_odd_samples(samples,temporal_sign):
    from spinfreq.dynamics import space_time_spectrum
    dt=1e-12;dx=2e-9;nx=32
    times=np.arange(samples)*dt;x=np.arange(nx)*dx
    frequency=17/(samples*dt);k=2*np.pi*3/(nx*dx)
    wave=.01*np.cos(temporal_sign*2*np.pi*frequency*times[:,None]+k*x[None,:])
    q,f,power=space_time_spectrum(times,wave[:,None,:],dx,time_window='rectangular',
                                 space_window='rectangular',temporal_sign=temporal_sign)
    it,ix=np.unravel_index(np.argmax(power),power.shape)
    np.testing.assert_allclose([f[it],q[ix],power[it,ix]],[frequency,k,.0001],rtol=1e-12)


def test_space_time_fft_rejects_unknown_temporal_sign():
    from spinfreq.dynamics import space_time_spectrum
    with pytest.raises(ValueError,match='temporal_sign'):
        space_time_spectrum(np.arange(5)*1e-12,np.zeros((5,1,3)),1e-9,temporal_sign=0)
