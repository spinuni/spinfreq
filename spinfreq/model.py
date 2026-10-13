"""SI micromagnetics, periodic xy boundaries, uniform magnetization through z."""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
from scipy.linalg import eig, solve

MU0 = 4e-7 * np.pi

@dataclass(frozen=True)
class Material:
    Ms: float = 580e3  # A/m
    A: float = 15e-12  # J/m
    D: float = 3e-3  # J/m², interfacial DMI
    K: float = 0.8e6  # J/m³, easy z axis
    alpha: float = 0.02
    gamma: float = 1.760859e11  # rad/(s T), positive magnitude

    def __post_init__(self):
        if not np.all(np.isfinite([self.Ms, self.A, self.D, self.K, self.alpha, self.gamma])):
            raise ValueError("Material parameters must be finite")
        if self.Ms <= 0 or self.A < 0 or self.alpha < 0 or self.gamma <= 0:
            raise ValueError("Require Ms, gamma > 0 and A, alpha >= 0")

@dataclass
class Relaxation:
    m: np.ndarray
    energy_J: float
    torque_T: float
    converged: bool
    iterations: int
    message: str

@dataclass
class Spectrum:
    eigenvalues: np.ndarray  # s^-1; exp(lambda t)
    modes: np.ndarray  # (number of modes, ny, nx, 3), complex

    @property
    def frequencies_Hz(self):
        return self.eigenvalues.imag / (2 * np.pi)

    @property
    def decay_rates_per_s(self):
        return -self.eigenvalues.real

class Film:
    def __init__(self, nx=12, ny=12, dx=4e-9, dy=None, thickness=1e-9,
                 material=None, field_T=(0, 0, 0.1), demag=True):
        self.nx, self.ny = int(nx), int(ny)
        self.dx, self.dy, self.thickness = float(dx), float(dx if dy is None else dy), float(thickness)
        if min(self.nx, self.ny) < 3 or not np.all(np.isfinite([self.dx, self.dy, self.thickness])) or min(self.dx, self.dy, self.thickness) <= 0:
            raise ValueError("Require at least 3 cells per axis and positive finite dimensions")
        self.material = material or Material()
        self.field_T = np.asarray(field_T, dtype=float)
        if self.field_T.shape != (3,) or not np.all(np.isfinite(self.field_T)):
            raise ValueError("field_T must contain three finite components")
        self.demag = bool(demag)
        kx = 2 * np.pi * np.fft.fftfreq(self.nx, self.dx)
        ky = 2 * np.pi * np.fft.fftfreq(self.ny, self.dy)
        self.kx, self.ky = np.meshgrid(kx, ky)
        self.k2 = self.kx**2 + self.ky**2
        # Odd derivatives vanish at Nyquist to preserve real skew-adjointness.
        self.deriv_kx, self.deriv_ky = self.kx.copy(), self.ky.copy()
        if self.nx % 2 == 0:
            self.deriv_kx[:, self.nx // 2] = 0
        if self.ny % 2 == 0:
            self.deriv_ky[self.ny // 2, :] = 0
        q = np.sqrt(self.k2) * self.thickness
        f = np.ones_like(q)
        np.divide(-np.expm1(-q), q, out=f, where=q != 0)
        self.nzz = f
        self.nxx = np.divide((1-f)*self.kx**2, self.k2, out=np.zeros_like(q), where=self.k2 != 0)
        self.nyy = np.divide((1-f)*self.ky**2, self.k2, out=np.zeros_like(q), where=self.k2 != 0)
        self.nxy = np.divide((1-f)*self.kx*self.ky, self.k2, out=np.zeros_like(q), where=self.k2 != 0)
        # Mixed Nyquist coefficients cannot act on a real Fourier field.
        if self.nx % 2 == 0:
            self.nxy[:, self.nx // 2] = 0
        if self.ny % 2 == 0:
            self.nxy[self.ny // 2, :] = 0

    @property
    def shape(self):
        return (self.ny, self.nx, 3)

    def check(self, m, unit=True):
        m = np.asarray(m, dtype=float)
        if m.shape != self.shape or not np.all(np.isfinite(m)):
            raise ValueError(f"Expected finite magnetization of shape {self.shape}")
        if unit and not np.allclose(np.linalg.norm(m, axis=-1), 1, atol=1e-7):
            raise ValueError("Magnetization must have unit length")
        return m

    def derivative(self, m, axis):
        k = self.deriv_kx if axis == 'x' else self.deriv_ky
        return np.fft.ifft2(1j * k[..., None] * np.fft.fft2(m, axes=(0, 1)), axes=(0, 1)).real

    def demag_field(self, m):
        h = np.fft.fft2(m, axes=(0, 1))
        out = np.empty_like(h)
        out[..., 0] = self.nxx*h[..., 0] + self.nxy*h[..., 1]
        out[..., 1] = self.nxy*h[..., 0] + self.nyy*h[..., 1]
        out[..., 2] = self.nzz*h[..., 2]
        return -MU0*self.material.Ms*np.fft.ifft2(out, axes=(0, 1)).real

    def effective_field(self, m):
        """B_eff = -(1/Ms) δE/δm, in tesla; also accepts nonunit vectors."""
        p = self.material
        lap = np.fft.ifft2(-self.k2[..., None]*np.fft.fft2(m, axes=(0, 1)), axes=(0, 1)).real
        b = self.field_T + 2*p.A/p.Ms*lap
        b[..., 2] += 2*p.K/p.Ms*m[..., 2]
        x, y = self.derivative(m, 'x'), self.derivative(m, 'y')
        b[..., 0] += 2*p.D/p.Ms*x[..., 2]
        b[..., 1] += 2*p.D/p.Ms*y[..., 2]
        b[..., 2] -= 2*p.D/p.Ms*(x[..., 0]+y[..., 1])
        if self.demag:
            b += self.demag_field(m)
        return b

    def energy(self, m):
        """Total energy in joules, including the spectral exchange quadratic form."""
        m = self.check(m, unit=False)
        p = self.material
        internal = self.effective_field(m) - self.field_T
        density = -0.5*p.Ms*np.sum(m*internal, axis=-1)-p.Ms*np.sum(m*self.field_T, axis=-1)
        return float(np.sum(density)*self.dx*self.dy*self.thickness)

    def torque(self, m):
        return float(np.max(np.linalg.norm(np.cross(m, self.effective_field(m)), axis=-1)))

    def relax(self, initial, maxiter=2000, tolerance_T=1e-5):
        initial = self.check(initial)
        scale = max(self.material.Ms, abs(self.material.K), 1.0)
        volume = self.dx*self.dy*self.thickness
        def objective(x):
            raw = x.reshape(self.shape)
            norms = np.linalg.norm(raw, axis=-1, keepdims=True)
            if np.any(norms < 1e-12):
                raise ValueError("Zero spin encountered during relaxation")
            m = raw/norms
            b = self.effective_field(m)
            grad = -self.material.Ms*(b-np.sum(b*m, axis=-1, keepdims=True)*m)/norms/scale
            return self.energy(m)/volume/scale, grad.ravel()
        result = minimize(objective, initial.ravel(), jac=True, method='L-BFGS-B',
                          options={'maxiter':maxiter, 'gtol':tolerance_T*self.material.Ms/scale/10,
                                   'ftol':1e-15, 'maxls':50})
        m = result.x.reshape(self.shape)
        m = m/np.linalg.norm(m, axis=-1, keepdims=True)
        torque = self.torque(m)
        return Relaxation(m, self.energy(m), torque, torque <= tolerance_T,
                          result.nit, str(result.message))

    def llg(self, m):
        p = self.material
        c = np.cross(m, self.effective_field(m))
        return -p.gamma/(1+p.alpha**2)*(c+p.alpha*np.cross(m, c))

    def tangent_basis(self, m):
        m = self.check(m)
        ref = np.zeros_like(m)
        ref[..., 2] = 1
        ref[np.abs(m[..., 2]) > 0.9] = (1, 0, 0)
        e1 = np.cross(ref, m)
        e1 /= np.linalg.norm(e1, axis=-1, keepdims=True)
        return np.stack((e1, np.cross(m, e1)), axis=-1)

    def linearize(self, m, equilibrium_tolerance_T=1e-4):
        """Analytical LLG Jacobian in two local tangent coordinates per cell.

        Dense reference solver: memory O(N²), eigensolver O(N³).
        """
        m = self.check(m)
        if self.torque(m) > equilibrium_tolerance_T:
            raise ValueError("State is not an equilibrium; relax it before linearizing")
        n = self.nx*self.ny
        if n > 1024:
            raise ValueError("Dense reference solver limited to 1024 cells; use a smaller grid")
        basis = self.tangent_basis(m)
        b = self.effective_field(m)
        c = np.cross(m, b)
        p = self.material
        matrix = np.empty((2*n, 2*n))
        for column in range(2*n):
            v = np.zeros(self.shape)
            cell, component = divmod(column, 2)
            v.reshape(-1, 3)[cell] = basis.reshape(-1, 3, 2)[cell, :, component]
            db = self.effective_field(v)-self.field_T
            dc = np.cross(v, b)+np.cross(m, db)
            df = -p.gamma/(1+p.alpha**2)*(dc+p.alpha*(np.cross(v, c)+np.cross(m, dc)))
            matrix[:, column] = np.einsum('...ci,...c->...i', basis, df).ravel()
        return matrix, basis

    def modes(self, m, equilibrium_tolerance_T=1e-4):
        matrix, basis = self.linearize(m, equilibrium_tolerance_T)
        values, vectors = eig(matrix)
        order = np.argsort(values.imag)
        fields = np.einsum('...ci,...ik->k...c', basis, vectors.reshape(self.ny, self.nx, 2, -1))
        return Spectrum(values[order], fields[order])

    def response(self, m, frequencies_Hz, drive_T=(1e-4, 0, 0), equilibrium_tolerance_T=1e-4):
        """Complex δm for B(t)=Re[drive_T exp(i 2π f t)], shape (nf,ny,nx,3)."""
        matrix, basis = self.linearize(m, equilibrium_tolerance_T)
        frequencies = np.atleast_1d(np.asarray(frequencies_Hz, dtype=float))
        if frequencies.ndim != 1 or not np.all(np.isfinite(frequencies)) or np.any(frequencies < 0):
            raise ValueError("Frequencies must be finite and nonnegative")
        drive = np.broadcast_to(np.asarray(drive_T, dtype=complex), self.shape)
        if not np.all(np.isfinite(drive)):
            raise ValueError("Drive must be finite")
        p = self.material
        c = np.cross(m, drive)
        force = -p.gamma/(1+p.alpha**2)*(c+p.alpha*np.cross(m, c))
        force = np.einsum('...ci,...c->...i', basis, force).ravel()
        identity = np.eye(len(matrix))
        fields = []
        for f in frequencies:
            coords = solve(2j*np.pi*f*identity-matrix, force).reshape(self.ny, self.nx, 2)
            fields.append(np.einsum('...ci,...i->...c', basis, coords))
        return np.asarray(fields)

    def absorbed_power(self, frequencies_Hz, response, drive_T):
        """Cycle-averaged absorbed power (W), exp(+iωt) convention."""
        drive = np.broadcast_to(np.asarray(drive_T, dtype=complex), self.shape)
        overlap = np.sum(np.conj(drive)*response, axis=(1, 2, 3))
        return -0.5*self.material.Ms*self.dx*self.dy*self.thickness*2*np.pi*np.asarray(frequencies_Hz)*overlap.imag

    def topological_charge(self, m):
        """Spectral approximation; reliable only for spatially resolved textures."""
        m = self.check(m)
        return float(np.sum(m*np.cross(self.derivative(m, 'x'), self.derivative(m, 'y')))*self.dx*self.dy/(4*np.pi))


def skyrmion_lattice(film, radius=None, wall_width=None, polarity=-1, helicity=0.0):
    """One smooth Néel skyrmion per rectangular periodic cell (seed, not equilibrium)."""
    if polarity not in (-1, 1):
        raise ValueError("polarity must be ±1")
    lx, ly = film.nx*film.dx, film.ny*film.dy
    radius = min(lx, ly)*0.23 if radius is None else float(radius)
    wall_width = radius/3 if wall_width is None else float(wall_width)
    cutoff = min(lx, ly)*0.48
    if not 0 < radius < cutoff or wall_width <= 0:
        raise ValueError("Seed radius must fit inside the cell and wall width must be positive")
    x = (np.arange(film.nx)+0.5)*film.dx-lx/2
    y = (np.arange(film.ny)+0.5)*film.dy-ly/2
    x, y = np.meshgrid(x, y)
    r = np.hypot(x, y)
    theta = 2*np.arctan(np.exp(np.clip((radius-r)/wall_width, -700, 700)))
    # Compact smooth taper avoids a discontinuity at the periodic cell boundary.
    taper = np.clip((cutoff-r)/(cutoff-radius), 0, 1)
    theta *= taper*taper*(3-2*taper)
    phi = np.arctan2(y, x)+helicity
    m = np.stack((np.sin(theta)*np.cos(phi), np.sin(theta)*np.sin(phi), -polarity*np.cos(theta)), axis=-1)
    return m
