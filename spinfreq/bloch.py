"""Bloch eigenmodes for infinite 1D arrays: periodic x, open y, one z layer."""
import numpy as np
from scipy.fft import fft2,ifft2
from scipy.sparse.linalg import LinearOperator,eigs
from scipy.linalg import lu_factor,lu_solve
from .confined import ConfinedFilm,_newell_f,_newell_g
from .model import MU0,Spectrum


def cell_tensor(x,y,dx,dy,dz):
    """Dimensionless Newell tensor with far-cell quadrature, including nxy."""
    tensor=np.zeros((4,*x.shape))
    far=np.hypot(x,y)>40*max(dx,dy,dz)
    near=~far
    xx0,yy0=x[near],y[near]
    for a,wa in [(-1,1),(0,-2),(1,1)]:
        for b,wb in [(-1,1),(0,-2),(1,1)]:
            for c,wc in [(-1,1),(0,-2),(1,1)]:
                xx,yy,zz=xx0+a*dx,yy0+b*dy,np.full_like(xx0,c*dz)
                w=-wa*wb*wc/(4*np.pi*dx*dy*dz)
                tensor[0,near]+=w*_newell_f(xx,yy,zz)
                tensor[1,near]+=w*_newell_f(yy,xx,zz)
                tensor[2,near]+=w*_newell_f(zz,yy,xx)
                tensor[3,near]+=w*_newell_g(xx,yy,zz)
    if np.any(far):
        xf,yf=x[far],y[far]
        for a,wa in [(-1,.25),(0,.5),(1,.25)]:
            for b,wb in [(-1,.25),(0,.5),(1,.25)]:
                for c,wc in [(-1,.25),(0,.5),(1,.25)]:
                    xx,yy,zz=xf+a*dx/np.sqrt(3),yf+b*dy/np.sqrt(3),c*dz/np.sqrt(3)
                    r2=xx*xx+yy*yy+zz*zz
                    w=wa*wb*wc*dx*dy*dz/(4*np.pi*r2**2.5)
                    tensor[0,far]+=w*(r2-3*xx*xx)
                    tensor[1,far]+=w*(r2-3*yy*yy)
                    tensor[2,far]+=w*(r2-3*zz*zz)
                    tensor[3,far]-=w*3*xx*yy
    return tensor


class BlochChain(ConfinedFilm):
    def __init__(self,*args,images=32,**kwargs):
        if int(images)!=images or images<1:
            raise ValueError('Require at least one periodic image on each side')
        demag=kwargs.pop('demag',True)
        super().__init__(*args,demag=False,**kwargs)
        self.demag=demag
        self.images=int(images)
        self.period_m=self.nx*self.dx
        # x convolution is circular; y retains zero padding. A doubled x
        # Toeplitz convolution of a truncated image sum is not exactly periodic.
        self._fft_shape=(self._fft_shape[0],self.nx)
        self._image_tensors=None
        self._kernel_cache={}
        if self.demag:
            scale=max(self.dx,self.dy,self.thickness)
            iy=np.arange(self._fft_shape[0])
            ix=np.arange(self._fft_shape[1])
            iy=np.where(iy<self.ny,iy,iy-self._fft_shape[0])
            ix=np.where(ix<=self.nx//2,ix,ix-self.nx)
            x,y=np.meshgrid(ix*self.dx/scale,iy*self.dy/scale)
            self._image_tensors=np.stack([cell_tensor(x-r*self.period_m/scale,y,self.dx/scale,self.dy/scale,self.thickness/scale)
                                         for r in range(-self.images,self.images+1)])

    def demag_bloch(self,m,k_rad_m):
        if not self.demag:
            return np.zeros_like(m)
        k=float(k_rad_m)
        if not np.isfinite(k): raise ValueError('Wavevector must be finite')
        if k not in self._kernel_cache:
            phases=np.exp(1j*k*self.period_m*np.arange(-self.images,self.images+1))
            tensor=np.einsum('r,rcyx->cyx',phases,self._image_tensors)
            displacement=np.arange(self.nx)
            displacement=np.where(displacement<=self.nx//2,displacement,displacement-self.nx)*self.dx
            # Transform the quasiperiodic field into a periodic envelope.
            tensor=tensor*np.exp(-1j*k*displacement)[None,None,:]
            # At the half-period sample, finite image truncation can violate
            # Hermiticity. Symmetrize displacement pairs without changing physics.
            inverse_y=(-np.arange(self._fft_shape[0]))%self._fft_shape[0]
            inverse_x=(-np.arange(self.nx))%self.nx
            tensor=.5*(tensor+tensor[:,inverse_y][:,:,inverse_x].conj())
            self._kernel_cache={k:fft2(tensor,axes=(-2,-1))}
        kernel=self._kernel_cache[k]
        envelope=np.exp(-1j*k*np.arange(self.nx)*self.dx)
        h=fft2(np.moveaxis(m,-1,0)*envelope[None,None,:],s=self._fft_shape,axes=(-2,-1))
        out=np.empty_like(h)
        out[0]=kernel[0]*h[0]+kernel[3]*h[1]
        out[1]=kernel[3]*h[0]+kernel[1]*h[1]
        out[2]=kernel[2]*h[2]
        result=ifft2(out,axes=(-2,-1))[:,:self.ny,:self.nx]
        field=-MU0*self.material.Ms*np.moveaxis(result,0,-1)*envelope.conj()[None,:,None]
        return field.real if k==0 and not np.iscomplexobj(m) else field

    def demag_field(self,m):
        return self.demag_bloch(m,0)

    def internal_field_bloch(self,m,k_rad_m=0):
        """Field linear in m; local-coordinate Bloch phase only at x-cell wrap."""
        p=self.material
        k=float(k_rad_m)
        phase=np.exp(1j*k*self.period_m)
        dtype=complex if (k!=0 or np.iscomplexobj(m)) else float
        m=np.asarray(m,dtype=dtype)
        plus=np.roll(m,-1,axis=1).copy()
        minus=np.roll(m,1,axis=1).copy()
        if dtype is complex:
            plus[:,-1]*=phase
            minus[:,0]*=phase.conjugate()
        b=2*p.A/(p.Ms*self.dx**2)*(plus+minus-2*m)
        b[...,0]+=p.D/(p.Ms*self.dx)*(plus[...,2]-minus[...,2])
        b[...,2]-=p.D/(p.Ms*self.dx)*(plus[...,0]-minus[...,0])
        difference=m[1:]-m[:-1]
        b[:-1]+=2*p.A/(p.Ms*self.dy**2)*difference
        b[1:]-=2*p.A/(p.Ms*self.dy**2)*difference
        b[:-1,...,1]+=p.D/(p.Ms*self.dy)*m[1:,...,2]
        b[1:,...,1]-=p.D/(p.Ms*self.dy)*m[:-1,...,2]
        b[:-1,...,2]-=p.D/(p.Ms*self.dy)*m[1:,...,1]
        b[1:,...,2]+=p.D/(p.Ms*self.dy)*m[:-1,...,1]
        if self.dmi_boundary=='mumax' and p.D!=0:
            if p.A<=0: raise ValueError('Natural DMI boundary requires positive exchange')
            correction=p.D**2/(2*p.A*p.Ms)
            for edge in (0,-1):
                b[edge,...,1]+=correction*m[edge,...,1]
                b[edge,...,2]+=correction*m[edge,...,2]
        b[...,2]+=2*p.K/p.Ms*m[...,2]
        if self.demag:
            b+=self.demag_bloch(m,k)
        return b

    def effective_field(self,m):
        return self.internal_field_bloch(m,0)+self.field_T

    def bloch_operator(self,m,k_rad_m,equilibrium_tolerance_T=1e-4,assemble=False):
        m=self.check(m)
        if self.torque(m)>equilibrium_tolerance_T:
            raise ValueError('Relax the equilibrium before calculating Bloch modes')
        basis=self.tangent_basis(m)
        b=self.effective_field(m)
        c=np.cross(m,b)
        p=self.material
        def matvec(coords):
            v=np.einsum('...ci,...i->...c',basis,np.asarray(coords).reshape(self.ny,self.nx,2))
            db=self.internal_field_bloch(v,k_rad_m)
            dc=np.cross(v,b)+np.cross(m,db)
            df=-p.gamma/(1+p.alpha**2)*(dc+p.alpha*(np.cross(v,c)+np.cross(m,dc)))
            return np.einsum('...ci,...c->...i',basis,df).ravel()
        n=2*self.nx*self.ny
        operator=LinearOperator((n,n),matvec=matvec,dtype=complex)
        if not assemble: return operator,basis
        if n>8192: raise ValueError('Dense Bloch assembly limited to 4096 cells')
        unit=np.zeros(n)
        matrix=np.empty((n,n),dtype=complex)
        for j in range(n):
            unit[j]=1
            matrix[:,j]=matvec(unit)
            unit[j]=0
        return matrix,basis

    def _mode_coordinates(self,vectors):
        """Embed tangent eigenvectors; subclasses may restrict frozen spins."""
        return vectors.reshape(self.ny,self.nx,2,-1)

    def bloch_modes(self,m,k_rad_m,count=12,target_Hz=15e9,tolerance=1e-9):
        """Shift-invert targeted eigenmodes; complete-field physics, truncated spectrum.

        Dense LU makes small unit cells practical without diagonalizing every mode.
        Count is the number of eigenvalues nearest the complex frequency shift,
        not the number of positive-frequency branches. Residuals are checked.
        """
        matrix,basis=self.bloch_operator(m,k_rad_m,assemble=True)
        n=len(matrix)
        if not 1<=count<n-1: raise ValueError('Require 1 <= count < tangent dimension - 1')
        shift=2j*np.pi*target_Hz
        factors=lu_factor(matrix-shift*np.eye(n))
        inverse=LinearOperator((n,n),matvec=lambda x:lu_solve(factors,x),dtype=complex)
        # Fixed deterministic starting vector for reproducible ARPACK iterations.
        initial=np.random.default_rng(17).normal(size=n)+1j*np.random.default_rng(18).normal(size=n)
        values,vectors=eigs(matrix,k=count,sigma=shift,OPinv=inverse,tol=tolerance,v0=initial)
        absolute_residuals=np.linalg.norm(matrix@vectors-vectors*values,axis=0)/np.linalg.norm(vectors,axis=0)
        residuals=absolute_residuals/(np.linalg.norm(matrix,ord=np.inf)+abs(values))
        if np.max(residuals)>max(1e-8,10*tolerance):
            raise RuntimeError(f'Bloch eigenvalue residual too large: {residuals.max():g}')
        order=np.argsort(values.imag)
        modes=np.einsum('...ci,...ik->k...c',basis,self._mode_coordinates(vectors))
        self.last_eigen_residuals=residuals[order]
        self.last_eigen_absolute_residuals=absolute_residuals[order]
        return Spectrum(values[order],modes[order])
