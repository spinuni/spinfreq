"""Cell-centred excitation envelopes and normalized complex observation probes.

Coordinates are in metres from the lower-left film corner. Phasors use
exp(+i omega t); a plane-wave envelope is exp(+i(k.r + phase)). Profiles are
sampled, never silently rescaled to unit peak or wrapped at periodic edges.
"""
from dataclasses import dataclass
import math
import re

import numpy as np


@dataclass(frozen=True)
class SpatialProfile:
    kind: str = "uniform"
    center_m: tuple | None = None
    size_m: tuple | None = None
    sigma_m: tuple | None = None
    k_rad_m: tuple | None = None
    phase_rad: float = 0.

    def __post_init__(self):
        required = {"uniform": set(), "rectangle": {"center_m", "size_m"},
                    "gaussian": {"center_m", "sigma_m"}, "plane_wave": {"k_rad_m"}}
        if not isinstance(self.kind, str) or self.kind not in required:
            raise ValueError("Profile kind must be uniform, rectangle, gaussian or plane_wave")
        supplied = {name for name in ("center_m", "size_m", "sigma_m", "k_rad_m")
                    if getattr(self, name) is not None}
        if supplied != required[self.kind]:
            raise ValueError(f"{self.kind} requires exactly {sorted(required[self.kind])}")
        for name in supplied:
            value = getattr(self, name)
            if not isinstance(value, (tuple, list)) or len(value) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in value
            ):
                raise ValueError(f"{name} requires two finite real components")
            if name in ("size_m", "sigma_m") and min(value) <= 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, tuple(value))
        if type(self.phase_rad) not in (int, float) or not math.isfinite(self.phase_rad):
            raise ValueError("phase_rad must be a finite real number")

    def to_dict(self):
        data = {"kind": self.kind}
        for name in ("center_m", "size_m", "sigma_m", "k_rad_m"):
            if getattr(self, name) is not None:
                data[name] = list(getattr(self, name))
        if self.phase_rad:
            data["phase_rad"] = self.phase_rad
        return data

    @classmethod
    def from_dict(cls, data):
        allowed = {"kind", "center_m", "size_m", "sigma_m", "k_rad_m", "phase_rad"}
        if not isinstance(data, dict) or set(data)-allowed:
            raise ValueError("Unknown or malformed spatial profile")
        return cls(**data)

    def evaluate(self, nx, ny, dx_m, dy_m):
        if (type(nx) is not int or type(ny) is not int or min(nx, ny) < 1
                or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (dx_m, dy_m))):
            raise ValueError("Require positive cell counts and finite positive spacings")
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            x, y = np.meshgrid((np.arange(nx)+.5)*dx_m, (np.arange(ny)+.5)*dy_m)
            phase = np.full((ny, nx), self.phase_rad, dtype=float)
            envelope = np.ones((ny, nx))
            if self.kind == "rectangle":
                cx, cy = self.center_m
                sx, sy = self.size_m
                envelope = ((x >= cx-sx/2) & (x < cx+sx/2)
                            & (y >= cy-sy/2) & (y < cy+sy/2)).astype(float)
            elif self.kind == "gaussian":
                cx, cy = self.center_m
                sx, sy = self.sigma_m
                envelope = np.exp(-.5*((x-cx)/sx)**2-.5*((y-cy)/sy)**2)
            elif self.kind == "plane_wave":
                phase += self.k_rad_m[0]*x+self.k_rad_m[1]*y
            sampled = envelope*np.exp(1j*phase)
        if not np.all(np.isfinite(sampled)) or not np.any(np.abs(sampled) > 0):
            raise ValueError("Profile is nonfinite or has no resolved cells; refine or move it")
        return sampled


@dataclass(frozen=True)
class Probe:
    name: str
    profile: SpatialProfile = SpatialProfile()

    def __post_init__(self):
        if not isinstance(self.name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", self.name):
            raise ValueError("Probe name must start with a letter and contain at most 48 letters/digits/_/-")
        if not isinstance(self.profile, SpatialProfile):
            raise ValueError("Probe profile must be a SpatialProfile")

    def to_dict(self):
        return {"name": self.name, "profile": self.profile.to_dict()}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data)-{"name", "profile"} or "name" not in data:
            raise ValueError("Unknown or malformed probe")
        return cls(data["name"], SpatialProfile.from_dict(data.get("profile", {})))


def excitation_field(config):
    """Return the actual complex drive b in tesla, shape (ny,nx,3)."""
    profile = config.drive_profile or SpatialProfile()
    weights = profile.evaluate(config.nx, config.ny, config.dx_m, config.dy_m)
    vector = np.asarray(config.drive_T)+1j*np.asarray(config.drive_imag_T)
    return weights[..., None]*vector


def observe(response, weights):
    """Return sum(conj(w)*delta_m)/sum(abs(w)) for every probe and frequency.

    A uniform probe is the spatial mean; a complex plane-wave probe extracts
    the corresponding Fourier component. No drive or volume normalization is
    applied. The result is dimensionless magnetization, not susceptibility.
    """
    response = np.asarray(response)
    weights = np.asarray(weights)
    if (response.ndim != 4 or response.shape[-1] != 3 or weights.ndim != 3
            or response.shape[1:3] != weights.shape[1:] or not len(weights)
            or not np.all(np.isfinite(response)) or not np.all(np.isfinite(weights))):
        raise ValueError("Require finite response (nf,ny,nx,3) and weights (nprobe,ny,nx)")
    peak = np.abs(weights).max(axis=(1, 2))
    if not np.all(np.isfinite(peak)) or not np.all(peak > 0):
        raise ValueError("Observation probes must have nonzero weight")
    # Normalize before multiplying by a small response, including Gaussian tails.
    # Real divisions avoid complex-reciprocal overflow for subnormal weights.
    scaled = weights.real/peak[:, None, None]+1j*(weights.imag/peak[:, None, None])
    norm = np.abs(scaled).sum(axis=(1, 2))
    return np.einsum("pyx,fyxc->fpc", scaled.conj(), response)/norm[None, :, None]
