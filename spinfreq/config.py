"""Versioned SI configuration shared by the package, CLI and web worker."""
from dataclasses import asdict, dataclass, field, fields
import json
import math
from pathlib import Path

from .model import Material
from .profiles import Probe, SpatialProfile


@dataclass(frozen=True)
class JobConfig:
    schema_version: int = 1
    model: str = "periodic"
    nx: int = 8
    ny: int = 8
    dx_m: float = 4e-9
    dy_m: float = 4e-9
    thickness_m: float = 1e-9
    material: Material = field(default_factory=Material)
    field_T: tuple = (0., 0., .1)
    dmi_boundary: str = "bond"
    seed: str = "uniform"
    seed_radius_m: float = 8e-9
    seed_wall_m: float = 3e-9
    fmin_Hz: float = 1e9
    fmax_Hz: float = 60e9
    points: int = 101
    drive_T: tuple = (1e-6, 0., 0.)
    torque_tolerance_T: float = 1e-8
    maxiter: int = 2000
    drive_imag_T: tuple = (0., 0., 0.)
    drive_profile: SpatialProfile | None = None
    probes: tuple = ()

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported schema_version; require integer 1")
        if self.model not in ("periodic", "confined") or self.dmi_boundary not in ("bond", "mumax"):
            raise ValueError("Require model periodic/confined and boundary bond/mumax")
        if self.model == "periodic" and self.dmi_boundary != "bond":
            raise ValueError("Periodic spectral model has no selectable DMI edge boundary")
        for name in ("nx", "ny", "points", "maxiter"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        cap = 1024 if self.model == "periodic" else 4096
        if self.nx*self.ny > cap or not 2 <= self.points <= 1001 or self.maxiter > 10000:
            raise ValueError("Dense cell, frequency-point or iteration limit exceeded")
        for name in ("dx_m", "dy_m", "thickness_m", "seed_radius_m", "seed_wall_m", "torque_tolerance_T"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("fmin_Hz", "fmax_Hz"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0 <= self.fmin_Hz < self.fmax_Hz or self.seed not in ("uniform", "skyrmion"):
            raise ValueError("Require 0 <= fmin < fmax and a supported seed")
        for name in ("field_T", "drive_T", "drive_imag_T"):
            value = getattr(self, name)
            if not isinstance(value, (list, tuple)) or len(value) != 3 or any(
                type(x) not in (int, float) or not math.isfinite(x) for x in value
            ):
                raise ValueError(f"{name} must contain three finite real SI components")
            object.__setattr__(self, name, tuple(value))
        if not isinstance(self.material, Material) or self.material.alpha <= 0:
            raise ValueError("Jobs require Material with strictly positive damping")
        if not any(self.drive_T) and not any(self.drive_imag_T):
            raise ValueError("Require a nonzero drive")
        if self.drive_profile is not None:
            if not isinstance(self.drive_profile, SpatialProfile):
                raise ValueError("drive_profile must be a SpatialProfile")
            self.drive_profile.evaluate(self.nx, self.ny, self.dx_m, self.dy_m)
        if not isinstance(self.probes, (tuple, list)) or len(self.probes) > 16 or any(
            not isinstance(probe, Probe) for probe in self.probes
        ):
            raise ValueError("Require at most 16 Probe objects")
        if len({probe.name for probe in self.probes}) != len(self.probes):
            raise ValueError("Probe names must be unique")
        for probe in self.probes:
            probe.profile.evaluate(self.nx, self.ny, self.dx_m, self.dy_m)
        object.__setattr__(self, "probes", tuple(self.probes))
        if self.seed == "skyrmion" and self.seed_radius_m >= .48*min(self.nx*self.dx_m, self.ny*self.dy_m):
            raise ValueError("Skyrmion seed radius must fit inside the film")

    def to_dict(self):
        data = asdict(self)
        # Preserve schema-1 preset JSON and hashes when optional features are unused.
        if any(self.drive_imag_T):
            data["drive_imag_T"] = list(self.drive_imag_T)
        else:
            data.pop("drive_imag_T")
        if self.drive_profile is None:
            data.pop("drive_profile")
        else:
            data["drive_profile"] = self.drive_profile.to_dict()
        if self.probes:
            data["probes"] = [probe.to_dict() for probe in self.probes]
        else:
            data.pop("probes")
        return data

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a JSON object")
        unknown = set(data)-{f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown configuration keys: {sorted(unknown)}")
        values = dict(data)
        if "drive_profile" in values:
            values["drive_profile"] = SpatialProfile.from_dict(values["drive_profile"])
        if "probes" in values:
            if not isinstance(values["probes"], list):
                raise ValueError("probes must be a JSON list")
            values["probes"] = tuple(Probe.from_dict(probe) for probe in values["probes"])
        if "material" in values:
            material = values["material"]
            if not isinstance(material, dict) or set(material)-{f.name for f in fields(Material)}:
                raise ValueError("Unknown or malformed material properties")
            if any(type(x) not in (int, float) for x in material.values()):
                raise ValueError("Material properties must be real numbers")
            values["material"] = Material(**material)
        return cls(**values)

    @classmethod
    def load(cls, path):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"Duplicate JSON key: {key}")
                result[key] = value
            return result
        return cls.from_dict(json.loads(Path(path).read_text(), object_pairs_hook=unique))


def presets():
    """Small reproducible examples; descriptions state the validation scope."""
    return {
        "periodic-fmr": JobConfig(material=Material(D=0)),
        "prism-fmr": JobConfig(model="confined", nx=1, ny=1, dx_m=4e-9, dy_m=8e-9,
                               material=Material(A=0, D=0, K=.6e6, alpha=.03, gamma=1.7595e11)),
        "confined-skyrmion": JobConfig(model="confined", nx=20, ny=20, dx_m=2e-9, dy_m=2e-9,
                                      material=Material(K=.6e6, alpha=.01, gamma=1.7595e11),
                                      field_T=(0., 0., 0.), seed="skyrmion", fmax_Hz=45e9),
    }


def validate_web_config(config):
    """Conservative computation bounds, not a continuum-accuracy envelope."""
    if config.nx*config.ny > 400 or config.points > 201 or config.maxiter > 3000:
        raise ValueError("Web limit: 400 cells, 201 frequencies, 3000 relaxation iterations")
    if not 1e-10 <= min(config.dx_m, config.dy_m, config.thickness_m) or max(
        config.nx*config.dx_m, config.ny*config.dy_m, config.thickness_m
    ) > 1e-5:
        raise ValueError("Web dimensions must be between 0.1 nm and 10 micrometres")
    p = config.material
    if not (1 <= p.Ms <= 1e7 and 0 <= p.A <= 1e-9 and abs(p.D) <= .1
            and abs(p.K) <= 1e8 and 1e9 <= p.gamma <= 1e13 and 1e-4 <= p.alpha <= 1):
        raise ValueError("Material exceeds web computation bounds")
    if max(map(abs, config.field_T)) > 20 or max(math.hypot(a, b) for a, b in zip(
        config.drive_T, config.drive_imag_T
    )) > 1e-4 or config.fmax_Hz > 1e13:
        raise ValueError("Field or frequency exceeds web computation bounds")
    if not 1e-10 <= config.torque_tolerance_T <= 1e-6:
        raise ValueError("Web torque tolerance must be 1e-10 to 1e-6 T")
