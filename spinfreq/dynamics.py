"""Nonlinear LLG, excitation protocols, and cell-resolved FFT spectra."""
from dataclasses import dataclass
import numpy as np
from scipy.integrate import solve_ivp


@dataclass
class Trajectory:
    times_s: np.ndarray
    mean_m: np.ndarray
    max_norm_error: float
    evaluations: int


def sinc_drive(amplitude_T=5e-3,cutoff_Hz=50e9,center_s=1e-9,axis=0,mask=1.0):
    if not np.isfinite(cutoff_Hz) or cutoff_Hz<=0 or axis not in (0,1,2):
        raise ValueError('Require positive cutoff and axis 0, 1 or 2')
    vector=np.eye(3)[axis]*amplitude_T
    mask=np.asarray(mask)
    return lambda t: np.sinc(2*cutoff_Hz*(t-center_s))*mask[...,None]*vector


def harmonic_drive(amplitude_T=5e-3,frequency_Hz=13.4e9,axis=0,mask=1.0):
    if not np.isfinite(frequency_Hz) or frequency_Hz<=0 or axis not in (0,1,2):
        raise ValueError('Require positive frequency and axis 0, 1 or 2')
    vector=np.eye(3)[axis]*amplitude_T
    mask=np.asarray(mask)
    return lambda t: np.sin(2*np.pi*frequency_Hz*t)*mask[...,None]*vector


def left_strip(film,width_m=40e-9):
    if not np.isfinite(width_m) or not 0<width_m<=film.nx*film.dx:
        raise ValueError('Strip width must fit in the film')
    return np.broadcast_to((np.arange(film.nx)+0.5)*film.dx<width_m,(film.ny,film.nx)).astype(float)


def integrate(film,initial,times_s,drive=None,rtol=1e-7,atol=1e-9,max_step_s=np.inf,
              recorder=None,chunk_samples=128):
    """Adaptive nonlinear LLG with bounded-memory sample chunks.

    recorder(indices, fields) receives unit-norm samples and can write a memmap.
    No projection is applied inside the differential equation. Norm errors are
    measured before normalization; gross integration drift is rejected.
    """
    m=film.check(initial)
    times=np.asarray(times_s,dtype=float)
    if times.ndim!=1 or len(times)<2 or times[0]!=0 or not np.all(np.isfinite(times)) or np.any(np.diff(times)<=0):
        raise ValueError('Require increasing finite sample times starting at zero')
    if chunk_samples<1 or max_step_s<=0:
        raise ValueError('Require positive chunk size and maximum step')
    p=film.material
    def rhs(t,x):
        spins=x.reshape(film.shape)
        b=film.effective_field(spins)
        if drive is not None:
            b=b+np.broadcast_to(drive(t),film.shape)
        c=np.cross(spins,b)
        return (-p.gamma/(1+p.alpha**2)*(c+p.alpha*np.cross(spins,c))).ravel()
    mean=np.empty((len(times),3))
    mean[0]=m.mean(axis=(0,1))
    if recorder is not None:
        recorder(np.array([0]),m[None])
    start=0.0
    x=m.ravel().copy()
    max_error=0.0
    evaluations=0
    # Start safely relative to the largest exchange eigenvalue rather than
    # letting the ODE heuristic try a macroscopic step on a near-equilibrium film.
    stiffness_T = (8*p.A/p.Ms*(1/film.dx**2+1/film.dy**2)
                   + 2*abs(p.K)/p.Ms + 4*abs(p.D)/p.Ms*(1/film.dx+1/film.dy)
                   + np.linalg.norm(film.field_T) + 4*np.pi*1e-7*p.Ms)
    first_step = min(np.min(np.diff(times))/10,.1/(p.gamma*max(stiffness_T,1e-12)))
    for index in range(1,len(times),chunk_samples):
        stop=min(index+chunk_samples,len(times))
        result=solve_ivp(rhs,(start,times[stop-1]),x,method='DOP853',t_eval=times[index:stop],
                         rtol=rtol,atol=atol,max_step=max_step_s,
                         first_step=min(first_step,times[stop-1]-start,max_step_s))
        if not result.success or result.y.shape[1]!=stop-index:
            raise RuntimeError(f'Nonlinear integration failed: {result.message}')
        fields=result.y.T.reshape(-1,*film.shape)
        norms=np.linalg.norm(fields,axis=-1,keepdims=True)
        error=float(np.max(abs(norms-1)))
        max_error=max(max_error,error)
        if error>max(1e-4,100*rtol):
            raise RuntimeError(f'Spin norm drift {error:g}; reduce integration tolerances/step')
        fields=fields/norms
        mean[index:stop]=fields.mean(axis=(1,2))
        if recorder is not None:
            recorder(np.arange(index,stop),fields)
        # Keep the original unprojected trajectory between chunks.
        x=result.y[:,-1].copy()
        start=times[stop-1]
        evaluations+=result.nfev
    return Trajectory(times,mean,max_error,evaluations)


def cell_spectrum(times_s,magnetization,component=2,discard_s=0,window='hann',batch_cells=256):
    """Average per-cell FFT magnitude and power, not FFT of spatial average.

    component=None accepts scalar cell traces (time,ny,nx) for bounded storage.
    The one-sided amplitude normalization gives a sinusoid's amplitude away
    from DC/Nyquist; power is amplitude squared, not spectral density.
    """
    times=np.asarray(times_s,dtype=float)
    if times.ndim!=1 or len(times)<3 or not np.all(np.isfinite(times)) or np.any(np.diff(times)<=0):
        raise ValueError('Require at least three increasing finite sample times')
    dt=times[1]-times[0]
    if not np.allclose(np.diff(times),dt,rtol=1e-8,atol=dt*1e-8):
        raise ValueError('FFT requires uniform samples')
    if component not in (None,0,1,2) or batch_cells<1:
        raise ValueError('Invalid component or cell batch size')
    values=np.asarray(magnetization)
    if values.ndim<2 or values.shape[0]!=len(times) or (component is not None and values.shape[-1]!=3):
        raise ValueError('Magnetization must have matching time axis and final vector axis')
    keep=times>=discard_s
    if np.sum(keep)<3:
        raise ValueError('Not enough samples after transient discard')
    values=values[np.flatnonzero(keep)[0]:]
    values=values.reshape(len(values),-1) if component is None else values.reshape(len(values),-1,3)
    n=len(values)
    if window=='hann': weights=np.hanning(n)
    elif window=='rectangular': weights=np.ones(n)
    else: raise ValueError('Window must be hann or rectangular')
    frequencies=np.fft.rfftfreq(n,dt)
    amplitude=np.zeros(len(frequencies))
    power=np.zeros(len(frequencies))
    cells=values.shape[1]
    for first in range(0,cells,batch_cells):
        selection=values[:,first:first+batch_cells] if component is None else values[:,first:first+batch_cells,component]
        block=np.asarray(selection,dtype=float)
        block=block-block.mean(axis=0)
        fft=np.fft.rfft(block*weights[:,None],axis=0)*2/weights.sum()
        fft[0]*=0.5
        if n%2==0: fft[-1]*=0.5
        amplitude+=np.sum(abs(fft),axis=1)/cells
        power+=np.sum(abs(fft)**2,axis=1)/cells
    return frequencies,amplitude,power


def space_time_spectrum(times_s,scalar_trace,dx_m,discard_s=0,time_window='hann',space_window='hann',batch_rows=1):
    """f–kx power of scalar (time,y,x) data, averaged over y after transforms.

    Spatial angular wavevectors are in rad/m. Temporal frequencies are Hz.
    Power is one-sided amplitude squared, not a spectral density. Opposite-phase
    transverse rows are retained. Rows are transformed in bounded batches.
    """
    times=np.asarray(times_s,dtype=float)
    trace=np.asarray(scalar_trace)
    if trace.ndim!=3 or trace.shape[0]!=len(times) or len(times)<3:
        raise ValueError('Require scalar trace of shape (time,y,x) and >=3 sample times')
    if not np.isfinite(dx_m) or dx_m<=0 or batch_rows<1:
        raise ValueError('Require positive cell width and row batch size')
    dt=times[1]-times[0]
    if dt<=0 or not np.all(np.isfinite(times)) or not np.allclose(np.diff(times),dt,rtol=1e-8,atol=dt*1e-8):
        raise ValueError('Space-time FFT requires uniformly increasing finite times')
    first=np.searchsorted(times,discard_s)
    trace=trace[first:]
    nt,ny,nx=trace.shape
    if nt<3 or nx<3: raise ValueError('Need at least three retained time and x samples')
    def window(name,size):
        if name=='hann': return np.hanning(size)
        if name=='rectangular': return np.ones(size)
        raise ValueError('Window must be hann or rectangular')
    wt,wx=window(time_window,nt),window(space_window,nx)
    frequencies=np.fft.rfftfreq(nt,dt)
    wavevectors=2*np.pi*np.fft.fftshift(np.fft.fftfreq(nx,dx_m))
    power=np.zeros((len(frequencies),nx))
    for index in range(0,ny,batch_rows):
        block=np.asarray(trace[:,index:index+batch_rows],dtype=float)
        if not np.all(np.isfinite(block)): raise ValueError('Nonfinite samples in trace')
        block=block-block.mean(axis=0)
        temporal=np.fft.rfft(block*wt[:,None,None],axis=0)*2/wt.sum()
        temporal[0]*=.5
        if nt%2==0: temporal[-1]*=.5
        transformed=np.fft.fftshift(np.fft.fft(temporal*wx[None,None,:],axis=-1),axes=-1)/wx.sum()
        power+=np.sum(abs(transformed)**2,axis=1)/ny
    return wavevectors,frequencies,power
