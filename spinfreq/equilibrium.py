"""Residual-based Newton/Krylov refinement in normalized tangent coordinates."""
import numpy as np
from scipy.optimize import root
from spinfreq.model import Relaxation


def refine_equilibrium(film,m,tolerance_T=1e-8,maxiter=40):
    """Refine static torque; this does not guarantee dynamical stability."""
    if not np.isfinite(tolerance_T) or tolerance_T<=0 or maxiter<1:
        raise ValueError("Require positive finite torque tolerance and iterations")
    m=film.check(m).copy()
    free=getattr(film,'free',np.ones(m.shape[:2],dtype=bool))
    basis=film.tangent_basis(m)
    def unpack(u):
        result=m.copy()
        addition=np.einsum('...ci,...i->...c',basis[free],u.reshape(-1,2))
        raw=m[free]+addition
        result[free]=raw/np.linalg.norm(raw,axis=-1,keepdims=True)
        return result
    def residual(u):
        spins=unpack(u);b=film.effective_field(spins)
        tangent=b-(b*spins).sum(axis=-1,keepdims=True)*spins
        return np.einsum('...ci,...c->...i',basis[free],tangent[free]).ravel()
    result=root(residual,np.zeros(2*int(free.sum())),method='krylov',options={'fatol':tolerance_T/2,
        'maxiter':maxiter,'jac_options':{'method':'lgmres','inner_maxiter':100},'line_search':'armijo'})
    spins=unpack(result.x);torque=film.torque(spins)
    return Relaxation(spins,film.energy(spins),torque,torque<=tolerance_T,result.nit,str(result.message))
