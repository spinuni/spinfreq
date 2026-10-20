"""Finite-difference, open-boundary single-layer films.

Exchange/DMI are derived from a nearest-neighbor bond energy. The natural
DMI boundary torque is retained. Demag uses cell-averaged Newell tensors.
"""
import numpy as np
from scipy.fft import rfft2, irfft2, next_fast_len
from .model import Film, MU0


def _asinh_ratio(numerator, denominator):
    ratio = np.divide(numerator, denominator, out=np.zeros_like(denominator), where=denominator != 0)
    return np.arcsinh(ratio)


def _newell_f(x,y,z):
    x,y,z = abs(x),abs(y),abs(z)
    r = np.sqrt(x*x+y*y+z*z)
    return ((2*x*x-y*y-z*z)*r/6 - x*y*z*np.arctan2(y*z,x*r)
            + y*(z*z-x*x)/2*_asinh_ratio(y,np.hypot(x,z))
            + z*(y*y-x*x)/2*_asinh_ratio(z,np.hypot(x,y)))


def _newell_g(x,y,z):
    sign = np.sign(x)*np.sign(y)
    x,y,z = abs(x),abs(y),abs(z)
    r = np.sqrt(x*x+y*y+z*z)
    return sign*(x*y*z*_asinh_ratio(z,np.hypot(x,y))
                 + y*(3*z*z-y*y)/6*_asinh_ratio(x,np.hypot(y,z))
                 + x*(3*z*z-x*x)/6*_asinh_ratio(y,np.hypot(x,z))
                 - z**3/6*np.arctan2(x*y,z*r)
                 - z*y*y/2*np.arctan2(x*z,y*r)
                 - z*x*x/2*np.arctan2(y*z,x*r)-x*y*r/3)


class ConfinedFilm(Film):
    def __init__(self, *args, dmi_boundary='mumax', **kwargs):
        if dmi_boundary not in ('mumax', 'bond'):
            raise ValueError('dmi_boundary must be mumax or bond')
        self.dmi_boundary = dmi_boundary
        super().__init__(*args, **kwargs)
        self._demag_kernel = None
        self._fft_shape = (next_fast_len(2*self.ny-1),next_fast_len(2*self.nx-1))
        if self.demag:
            self._build_kernel()

    def _build_kernel(self):
        # Dimensionless coordinates reduce cancellation associated with SI powers.
        scale = max(self.dx,self.dy,self.thickness)
        dx,dy,dz = self.dx/scale,self.dy/scale,self.thickness/scale
        iy = np.arange(self._fft_shape[0])
        ix = np.arange(self._fft_shape[1])
        iy = np.where(iy < self.ny,iy,iy-self._fft_shape[0])
        ix = np.where(ix < self.nx,ix,ix-self._fft_shape[1])
        x,y = np.meshgrid(ix*dx,iy*dy)
        tensors = np.zeros((4,*x.shape))
        weights = [(-1,1),(0,-2),(1,1)]
        for a,wa in weights:
            for b,wb in weights:
                for c,wc in weights:
                    xx,yy,zz = x+a*dx,y+b*dy,np.full_like(x,c*dz)
                    w = -wa*wb*wc/(4*np.pi*dx*dy*dz)
                    tensors[0] += w*_newell_f(xx,yy,zz)
                    tensors[1] += w*_newell_f(yy,xx,zz)
                    tensors[2] += w*_newell_f(zz,yy,xx)
                    tensors[3] += w*_newell_g(xx,yy,zz)
        # Avoid catastrophic cancellation of Newell differences at long range.
        # Two-point Gauss quadrature in each source/target cell gives a 27-point
        # difference distribution; far-cell error is O((cell/r)^4).
        far = np.hypot(x,y) > 40*max(dx,dy,dz)
        if np.any(far):
            xf,yf = x[far],y[far]
            values = np.zeros((4,len(xf)))
            for a,wa in [(-1,.25),(0,.5),(1,.25)]:
                for b,wb in [(-1,.25),(0,.5),(1,.25)]:
                    for c,wc in [(-1,.25),(0,.5),(1,.25)]:
                        xx,yy,zz = xf+a*dx/np.sqrt(3),yf+b*dy/np.sqrt(3),c*dz/np.sqrt(3)
                        r2 = xx*xx+yy*yy+zz*zz
                        prefactor = wa*wb*wc*dx*dy*dz/(4*np.pi*r2**2.5)
                        values[0] += prefactor*(r2-3*xx*xx)
                        values[1] += prefactor*(r2-3*yy*yy)
                        values[2] += prefactor*(r2-3*zz*zz)
                        values[3] -= prefactor*3*xx*yy
            tensors[:,far] = values
        # nzx,nzy vanish by symmetry for one uniform cell layer.
        self._demag_kernel = rfft2(tensors, axes=(-2,-1))
        self.demag_self_tensor = tensors[:3,0,0].copy()

    def demag_field(self,m):
        h = rfft2(np.moveaxis(m,-1,0),s=self._fft_shape,axes=(-2,-1))
        kernel = self._demag_kernel
        out = np.empty_like(h)
        out[0] = kernel[0]*h[0]+kernel[3]*h[1]
        out[1] = kernel[3]*h[0]+kernel[1]*h[1]
        out[2] = kernel[2]*h[2]
        field = irfft2(out,s=self._fft_shape,axes=(-2,-1))[:,:self.ny,:self.nx]
        return -MU0*self.material.Ms*np.moveaxis(field,0,-1)

    def effective_field(self,m):
        p = self.material
        b = np.broadcast_to(self.field_T,self.shape).copy()
        for axis,spacing in [(1,self.dx),(0,self.dy)]:
            lo = [slice(None)]*3
            hi = lo.copy()
            lo[axis],hi[axis] = slice(None,-1),slice(1,None)
            lo,hi = tuple(lo),tuple(hi)
            difference = m[hi]-m[lo]
            b[lo] += 2*p.A/(p.Ms*spacing**2)*difference
            b[hi] -= 2*p.A/(p.Ms*spacing**2)*difference
            component = 0 if axis==1 else 1
            # E_DMI bond = D/h (m_lo,z m_hi,a - m_lo,a m_hi,z).
            b[lo][...,component] += p.D/(p.Ms*spacing)*m[hi][...,2]
            b[hi][...,component] -= p.D/(p.Ms*spacing)*m[lo][...,2]
            b[lo][...,2] -= p.D/(p.Ms*spacing)*m[hi][...,component]
            b[hi][...,2] += p.D/(p.Ms*spacing)*m[lo][...,component]
            if self.dmi_boundary == 'mumax' and p.D != 0:
                if p.A <= 0:
                    raise ValueError('MuMax DMI ghost boundary requires positive exchange')
                # Exact additional quadratic term from MuMax3 ghost extrapolation.
                correction = p.D**2/(2*p.A*p.Ms)
                for edge in (0,-1):
                    selector = [slice(None)]*3
                    selector[axis] = edge
                    selector = tuple(selector)
                    b[selector][...,component] += correction*m[selector][...,component]
                    b[selector][...,2] += correction*m[selector][...,2]
        b[...,2] += 2*p.K/p.Ms*m[...,2]
        if self.demag:
            b += self.demag_field(m)
        return b

    def derivative(self,m,axis):
        dimension,spacing = (1,self.dx) if axis=='x' else (0,self.dy)
        count=m.shape[dimension]
        if count==1:
            return np.zeros_like(m)
        return np.gradient(m,spacing,axis=dimension,edge_order=min(2,count-1))

    def linearize(self,m,equilibrium_tolerance_T=1e-4):
        # Full 40×40 reference fits comfortably in memory; inherited cap is periodic-only.
        return self.linear_operator(m,equilibrium_tolerance_T,assemble=True)

    def linear_operator(self,m,equilibrium_tolerance_T=1e-4,assemble=False):
        from scipy.sparse.linalg import LinearOperator
        m = self.check(m)
        if self.torque(m)>equilibrium_tolerance_T:
            raise ValueError('State is not an equilibrium; relax it before linearizing')
        basis = self.tangent_basis(m)
        b = self.effective_field(m)
        c = np.cross(m,b)
        p = self.material
        def matvec(coords):
            # Effective field FFT is real; evaluate real and imaginary parts separately.
            if np.iscomplexobj(coords):
                return matvec(coords.real)+1j*matvec(coords.imag)
            v = np.einsum('...ci,...i->...c',basis,np.asarray(coords).reshape(self.ny,self.nx,2))
            db = self.effective_field(v)-self.field_T
            dc = np.cross(v,b)+np.cross(m,db)
            df = -p.gamma/(1+p.alpha**2)*(dc+p.alpha*(np.cross(v,c)+np.cross(m,dc)))
            return np.einsum('...ci,...c->...i',basis,df).ravel()
        n = 2*self.nx*self.ny
        operator = LinearOperator((n,n),matvec=matvec,dtype=float)
        if not assemble:
            return operator,basis
        if n>8192:
            raise ValueError('Dense assembly limited to 4096 cells; use matrix-free response or dynamics')
        matrix = np.empty((n,n))
        unit = np.zeros(n)
        for j in range(n):
            unit[j] = 1
            matrix[:,j] = matvec(unit)
            unit[j] = 0
        return matrix,basis

    def response_iterative(self,m,frequencies_Hz,drive_T=(1e-4,0,0),rtol=1e-7,maxiter=200):
        """Matrix-free GMRES with true-residual checks; failure raises, never hides."""
        from scipy.sparse.linalg import LinearOperator,gmres
        operator,basis = self.linear_operator(m)
        frequencies = np.atleast_1d(np.asarray(frequencies_Hz,dtype=float))
        if frequencies.ndim!=1 or np.any(frequencies<0) or not np.all(np.isfinite(frequencies)):
            raise ValueError('Frequencies must be finite and nonnegative')
        drive = np.broadcast_to(np.asarray(drive_T,dtype=complex),self.shape)
        p = self.material
        c = np.cross(m,drive)
        force = -p.gamma/(1+p.alpha**2)*(c+p.alpha*np.cross(m,c))
        force = np.einsum('...ci,...c->...i',basis,force).ravel()/p.gamma
        fields = []
        previous = None
        for f in frequencies:
            system = LinearOperator(operator.shape,matvec=lambda x:2j*np.pi*f/p.gamma*x-operator@x/p.gamma,dtype=complex)
            solution,status = gmres(system,force,x0=previous,rtol=rtol,atol=0,restart=100,maxiter=maxiter)
            residual = np.linalg.norm(system@solution-force)/max(np.linalg.norm(force),1e-300)
            if status or residual>rtol*1.1:
                raise RuntimeError(f'GMRES failed at {f:g} Hz: status={status}, relative residual={residual:g}')
            previous = solution
            fields.append(np.einsum('...ci,...i->...c',basis,solution.reshape(self.ny,self.nx,2)))
        return np.asarray(fields)


def lattice_seed(film,columns=1,rows=1,period_m=40e-9,radius_m=8e-9,wall_m=3e-9):
    """Finite rectangular array seed; edge magnetization then relaxes naturally."""
    if columns<1 or rows<1 or radius_m<=0 or wall_m<=0:
        raise ValueError('Require positive lattice dimensions, radius and wall width')
    if not (np.isclose(film.nx*film.dx,columns*period_m) and np.isclose(film.ny*film.dy,rows*period_m)):
        raise ValueError('Film size must equal array count times lattice period')
    x = ((np.arange(film.nx)+0.5)*film.dx)%period_m-period_m/2
    y = ((np.arange(film.ny)+0.5)*film.dy)%period_m-period_m/2
    x,y = np.meshgrid(x,y)
    r = np.hypot(x,y)
    theta = 2*np.arctan(np.exp(np.clip((radius_m-r)/wall_m,-700,700)))
    theta = np.where(r==0,np.pi,theta)
    phi = np.arctan2(y,x)
    return np.stack((np.sin(theta)*np.cos(phi),np.sin(theta)*np.sin(phi),np.cos(theta)),axis=-1)
