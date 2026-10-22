from dataclasses import replace
import hashlib
import json
import zipfile

import numpy as np
import pytest

from spinfreq import JobConfig, Probe, SpatialProfile, StudyConfig, run_job
from spinfreq.config import presets, validate_web_config
from spinfreq.profiles import excitation_field, observe


def analytic_response(config, frequencies, k=0.):
    """Independent physical-coordinate Gilbert system for a +z periodic film."""
    from spinfreq.model import MU0
    p = config.material
    h = config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms+2*p.A/p.Ms*k*k
    n = -np.expm1(-abs(k)*config.thickness_m)/(abs(k)*config.thickness_m) if k else 1.
    hx, hy = h+MU0*p.Ms*(1-n), h
    rate = p.gamma/(1+p.alpha**2)
    j = rate*np.array([[-p.alpha*hx, -hy], [hx, -p.alpha*hy]])
    b = np.asarray(config.drive_T)+1j*np.asarray(config.drive_imag_T)
    force = rate*np.array([p.alpha*b[0]+b[1], -b[0]+p.alpha*b[1]])
    return np.array([np.r_[np.linalg.solve(2j*np.pi*f*np.eye(2)-j, force), 0j] for f in frequencies])


def test_profile_coordinates_phase_and_observation_normalization():
    np.testing.assert_allclose(SpatialProfile(phase_rad=np.pi/2).evaluate(2, 1, 1., 1.), 1j, atol=1e-15)
    rectangle = SpatialProfile("rectangle", center_m=(2., 1.), size_m=(2., 2.))
    np.testing.assert_array_equal(rectangle.evaluate(4, 2, 1., 1.).real, [[0, 1, 1, 0], [0, 1, 1, 0]])
    gaussian = SpatialProfile("gaussian", center_m=(2., 1.), sigma_m=(1., 2.))
    expected = np.exp(-.5*np.array([1.5, .5, .5, 1.5])**2-.5*(.5/2)**2)
    np.testing.assert_allclose(gaussian.evaluate(4, 2, 1., 1.).real, np.tile(expected, (2, 1)))
    response = np.ones((2, 2, 4, 3))*np.array([1+2j, -3j, 0.5])
    weights = np.array([rectangle.evaluate(4, 2, 1., 1.), gaussian.evaluate(4, 2, 1., 1.)])
    observed = observe(response, weights)
    np.testing.assert_allclose(observed, np.broadcast_to([1+2j, -3j, .5], (2, 2, 3)))
    np.testing.assert_allclose(observe(response, 7*weights), observed)
    np.testing.assert_allclose(observe(response, 1e-300*weights), observed)


@pytest.mark.parametrize("data", [
    {"kind": "typo"}, {"kind": "rectangle"}, {"kind": "gaussian", "center_m": [0, 0], "sigma_m": [0, 1]},
    {"kind": "uniform", "k_rad_m": [1, 0]}, {"kind": "plane_wave", "k_rad_m": [float("nan"), 0]},
    {"kind": "uniform", "phase_rad": True}, {"kind": "uniform", "typo": 1},
])
def test_invalid_profile_definitions(data):
    with pytest.raises(ValueError):
        SpatialProfile.from_dict(data)


def test_unresolved_profiles_and_bad_probes_fail_before_output():
    with pytest.raises(ValueError, match="no resolved cells"):
        JobConfig(drive_profile=SpatialProfile("rectangle", center_m=(1., 1.), size_m=(1e-9, 1e-9)))
    with pytest.raises(ValueError, match="unique"):
        JobConfig(probes=(Probe("same"), Probe("same")))
    with pytest.raises(ValueError):
        Probe("=invalid")
    with pytest.raises(ValueError):
        JobConfig.from_dict({"probes": {"name": "x"}})
    with pytest.raises(ValueError):
        JobConfig.from_dict({"drive_profile": {"kind": "uniform", "path": "arbitrary.npy"}})
    with pytest.raises(ValueError):
        observe(np.ones((1, 2, 3, 3)), np.zeros((1, 2, 3)))


def test_legacy_configuration_hash_and_default_mean_are_preserved(tmp_path):
    from pathlib import Path
    for name, preset in presets().items():
        original = json.loads((Path(__file__).parents[1]/"examples"/f"{name}.json").read_text())
        assert preset.to_dict() == JobConfig.from_dict(original).to_dict()
        digest = lambda d: hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert digest(original) == digest(preset.to_dict())
    config = replace(presets()["periodic-fmr"], nx=2, ny=2, points=5)
    run_job(config, tmp_path/"default")
    with np.load(tmp_path/"default/observations.npz") as observation, np.load(tmp_path/"default/response.npz") as response:
        assert list(observation["probe_names"]) == ["mean"]
        np.testing.assert_allclose(observation["delta_m"][:, 0], response["delta_m"].mean(axis=(1, 2)), atol=1e-18)
    with zipfile.ZipFile(tmp_path/"default/results.zip") as archive:
        assert {"excitation.npy", "observations.csv", "observations.npz"} <= set(archive.namelist())


def test_complex_polarization_matches_independent_gilbert_susceptibility(tmp_path):
    config = replace(presets()["periodic-fmr"], nx=1, ny=1, points=11,
                     drive_T=(1e-6, .3e-6, 0), drive_imag_T=(.2e-6, -.8e-6, 0))
    run_job(config, tmp_path/"elliptical")
    with np.load(tmp_path/"elliptical/response.npz") as data:
        expected = analytic_response(config, data["frequencies_Hz"])
        np.testing.assert_allclose(data["delta_m"][:, 0, 0], expected, rtol=1e-12, atol=1e-18)
    np.testing.assert_allclose(np.load(tmp_path/"elliptical/excitation.npy")[0, 0],
                               np.array(config.drive_T)+1j*np.array(config.drive_imag_T))


def test_plane_wave_selection_and_fourier_probe_sign(tmp_path):
    config = replace(presets()["periodic-fmr"], nx=8, ny=1, points=9, dx_m=8e-9, fmax_Hz=150e9)
    k = 2*np.pi/(config.nx*config.dx_m)
    profile = SpatialProfile("plane_wave", k_rad_m=(k, 0))
    config = replace(config, drive_profile=profile,
                     probes=(Probe("matched", profile), Probe("mean"),
                             Probe("opposite", SpatialProfile("plane_wave", k_rad_m=(-k, 0)))))
    assert JobConfig.from_dict(json.loads(json.dumps(config.to_dict()))) == config
    run_job(config, tmp_path/"wave")
    with np.load(tmp_path/"wave/observations.npz") as data:
        expected = analytic_response(config, data["frequencies_Hz"], k)
        np.testing.assert_allclose(data["delta_m"][:, 0], expected, rtol=1e-11, atol=1e-18)
        assert np.linalg.norm(data["delta_m"][:, 1:])/np.linalg.norm(expected) < 1e-11


def test_web_phasor_bound_and_quadrature_study_axis():
    with pytest.raises(ValueError, match="Field or frequency"):
        validate_web_config(JobConfig(drive_T=(8e-5, 0, 0), drive_imag_T=(8e-5, 0, 0)))
    spec = StudyConfig(presets()["prism-fmr"], {"drive_imag_T.1": [-1e-6, 1e-6]})
    assert spec.cases()[0][1].drive_imag_T == (0., -1e-6, 0.)
    assert np.iscomplexobj(excitation_field(spec.cases()[0][1]))
