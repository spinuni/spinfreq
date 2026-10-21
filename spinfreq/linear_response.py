"""Reusable dense modal response and exact linear turn-on transients.

The operator is a snapshot of the supplied model/equilibrium. Rebuild it after
changing material, geometry or bias. This is small-signal frequency-domain
reconstruction, not nonlinear LLG integration.
"""
import numpy as np
from scipy.linalg import eig, lu_factor, lu_solve


def _exponential_interval(values,omega,times,start,stop):
    """Integral exp(lambda*(t-s))*exp(i*omega*s) ds over [start,stop]."""
    duration=stop-start
    difference=values[:,None]-1j*omega
    z=difference*duration[None,:]
    ratio=np.ones_like(z)
    np.divide(np.expm1(z),z,out=ratio,where=z!=0)
    return np.exp(values[:,None]*(times-stop)[None,:]+1j*omega*stop[None,:])*duration[None,:]*ratio


class ModalResponse:
    """Prepare a full dense eigenbasis once for repeated frequency sweeps.

    Drives use tesla and B(t)=Re[drive*exp(+i*2*pi*f*t)]. An inverse right-mode
    basis is used for damped, nonnormal operators. The usual dense cell limits
    apply; a prepared subset of modes is not supported.
    """
    def __init__(self,film,equilibrium,equilibrium_tolerance_T=1e-6):
        self.m=film.check(equilibrium).copy()
        self.matrix,self.basis=film.linearize(self.m,equilibrium_tolerance_T)
        self.material=film.material
        self.values,self.vectors=eig(self.matrix)
        self._mode_norms=np.linalg.norm(self.vectors,axis=0)
        self._factor=lu_factor(self.vectors)
        count=self.m.shape[0]*self.m.shape[1]
        observation=self.basis.reshape(count,3,2).transpose(1,0,2).reshape(3,2*count)/count
        self._mean_modes=observation@self.vectors

    def _force(self,drive_T):
        drive=np.broadcast_to(np.asarray(drive_T,dtype=complex),self.m.shape)
        if not np.all(np.isfinite(drive)):raise ValueError('Drive must be finite')
        p=self.material;c=np.cross(self.m,drive)
        force=-p.gamma/(1+p.alpha**2)*(c+p.alpha*np.cross(self.m,c))
        return np.einsum('...ci,...c->...i',self.basis,force).ravel()

    def _weights(self,force):
        weights=lu_solve(self._factor,force)
        residual=np.linalg.norm(self.vectors@weights-force)/max(np.linalg.norm(force),1e-300)
        if not np.isfinite(residual) or residual>1e-7:raise RuntimeError('Full eigenbasis failed force-reconstruction residual')
        self.last_basis_residual=float(residual)
        return weights

    def response(self,frequencies_Hz,drive_T=(1e-4,0,0),residual_tolerance=1e-7):
        """Return complex vector fields; verify each shifted-system residual."""
        frequencies=np.atleast_1d(np.asarray(frequencies_Hz,dtype=float))
        if frequencies.ndim!=1 or not np.all(np.isfinite(frequencies)) or np.any(frequencies<0):
            raise ValueError('Frequencies must be finite and nonnegative')
        if not np.isfinite(residual_tolerance) or residual_tolerance<=0:raise ValueError('Require a positive residual tolerance')
        force=self._force(drive_T);weights=self._weights(force);fields=[];residuals=[]
        for f in frequencies:
            denominator=2j*np.pi*f-self.values
            if np.any(denominator==0):raise RuntimeError('Undamped pole makes harmonic response singular')
            coordinates=self.vectors@(weights/denominator)
            residual=np.linalg.norm(2j*np.pi*f*coordinates-self.matrix@coordinates-force)/max(np.linalg.norm(force),1e-300)
            if not np.isfinite(residual) or residual>residual_tolerance:raise RuntimeError(f'Modal response residual failed at {f:g} Hz: {residual:g}')
            fields.append(np.einsum('...ci,...i->...c',self.basis,coordinates.reshape(*self.m.shape[:2],2)))
            residuals.append(float(residual))
        self.last_response_residuals=np.array(residuals)
        return np.array(fields)

    def ramped_mean_response(self,times_s,frequencies_Hz,drives_T,ramp_s,batch_samples=64):
        """Mean delta m from zero perturbation with a raised-cosine turn-on.

        The field is r(t)*sum Re[drive_j*exp(i*2*pi*f_j*t)], where
        r(t)=(1-cos(pi*t/ramp_s))/2 until ramp_s, then 1. Exact modal convolution
        includes startup transients. Samples are batched to bound temporary RAM.
        This does not assume a steady state has been reached.
        """
        times=np.asarray(times_s,dtype=float);frequencies=np.asarray(frequencies_Hz,dtype=float)
        drives=np.asarray(drives_T,dtype=complex)
        if times.ndim!=1 or not len(times) or not np.all(np.isfinite(times)) or np.any(times<0) or np.any(np.diff(times)<=0):
            raise ValueError('Require increasing finite nonnegative times')
        if frequencies.ndim!=1 or not len(frequencies) or not np.all(np.isfinite(frequencies)) or np.any(frequencies<0):
            raise ValueError('Require finite nonnegative tone frequencies')
        if len(drives)!=len(frequencies):raise ValueError('One drive is required per frequency')
        if not np.isfinite(ramp_s) or ramp_s<=0 or not isinstance(batch_samples,int) or batch_samples<1:
            raise ValueError('Require positive ramp duration and integer batch size')
        output=np.zeros((len(times),3),dtype=complex);full_state_bound=np.zeros(len(times));ramp_frequency=np.pi/ramp_s
        for frequency,drive in zip(frequencies,drives):
            omega=2*np.pi*frequency
            for sign,phasor in [(1,drive),(-1,drive.conj())]:
                weights=self._weights(self._force(phasor))
                observed=self._mean_modes*weights
                for first in range(0,len(times),batch_samples):
                    t=times[first:first+batch_samples];end=np.minimum(t,ramp_s);zero=np.zeros_like(t)
                    integral=np.zeros((len(self.values),len(t)),dtype=complex)
                    for coefficient,nu in [(.5,sign*omega),(-.25,sign*omega+ramp_frequency),(-.25,sign*omega-ramp_frequency)]:
                        integral+=coefficient*_exponential_interval(self.values,nu,t,zero,end)
                    integral+=_exponential_interval(self.values,sign*omega,t,end,t)
                    output[first:first+len(t)]+=.5*(observed@integral).T
                    full_state_bound[first:first+len(t)]+=.5*((self._mode_norms*abs(weights))@abs(integral))
        # Spatial averaging can cancel the entire physical signal. Scale the
        # roundoff guard with full-state contributions, not that vanishing mean.
        if not np.all(np.isfinite(output)) or not np.all(np.isfinite(full_state_bound)):
            raise RuntimeError('Linear transient exceeded finite numerical range')
        if np.max(abs(output.imag))>1e-8*max(np.max(full_state_bound),np.max(abs(output.real)),1e-30):
            raise RuntimeError('Modal transient failed real-signal consistency')
        return output.real
