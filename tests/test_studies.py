from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from spinfreq import JobConfig, StudyConfig, load_initial_state, run_job, run_study
from spinfreq.config import presets
from spinfreq.jobs import NumericalFailure
from spinfreq.model import MU0
from spinfreq.ovf import write_ovf


def macrospin():
    return replace(presets()["periodic-fmr"], nx=1, ny=1, points=5)


def test_continued_field_sweep_matches_analytic_poles_and_verified_resume(tmp_path, monkeypatch):
    spec = StudyConfig(macrospin(), {"field_T.2": [.05, .1, .2, .1]}, continuation=True)
    result = run_study(spec, tmp_path/"study")
    assert result["status"] == "succeeded"
    for index, field in enumerate(spec.axes["field_T.2"]):
        directory = tmp_path/"study"/"cases"/f"{index:04d}"/"attempt-0000"
        summary = json.loads((directory/"summary.json").read_text())
        assert summary["initialization"]["kind"] == ("uniform" if index == 0 else "provided-state")
        assert summary["initialization"]["initial_sha256"] == hashlib.sha256((directory/"initial.npy").read_bytes()).hexdigest()
        p = spec.base.material
        expected = p.gamma/(1+p.alpha**2)*(field+2*p.K/p.Ms-MU0*p.Ms)/(2*np.pi)
        assert result["cases"][index]["attempts"][0]["observables"]["lowest_frequency_Hz"] == pytest.approx(expected, rel=1e-12)
        if index:
            prior = directory.parents[1]/f"{index-1:04d}"/"attempt-0000"/"equilibrium.npy"
            assert (directory/"initial.npy").read_bytes() == prior.read_bytes()
            assert "preset" not in summary
    assert (tmp_path/"study"/"spectra.pdf").stat().st_size > 0
    def no_recalculation(*args, **kwargs):
        raise AssertionError("Verified completed cases must not run again")
    monkeypatch.setattr("spinfreq.studies.run_job", no_recalculation)
    resumed = run_study(spec, tmp_path/"study", resume=True)
    assert resumed == result
    assert not (tmp_path/"study"/".study.lock").exists()
    with pytest.raises(ValueError, match="configuration or numerical implementation changed"):
        run_study(StudyConfig(macrospin(), {"field_T.2": [.2]}), tmp_path/"study", resume=True)
    artifact = tmp_path/"study/cases/0000/attempt-0000/equilibrium.npy"
    artifact.write_bytes(b"modified")
    with pytest.raises(ValueError, match="integrity failed"):
        run_study(spec, tmp_path/"study", resume=True)


def test_independent_multiaxis_cases_continue_after_physical_rejection(tmp_path):
    # Negative bias makes the +z seed stationary but dynamically unstable.
    spec = StudyConfig(macrospin(), {"material.alpha": [.02, .04], "field_T.2": [-5., .1]})
    result = run_study(spec, tmp_path/"study")
    assert [r["status"] for r in result["cases"]] == ["failed", "failed", "succeeded", "succeeded"]
    assert result["status"] == "failed"
    assert not (tmp_path/"study/cases/0000/attempt-0000/results.zip").exists()
    rows = np.genfromtxt(tmp_path/"study/poles.csv", delimiter=",", names=True)
    assert list(rows["case"]) == [2., 3.]


def test_continuation_failure_stops_path_and_resume_keeps_failed_attempt(tmp_path, monkeypatch):
    spec = StudyConfig(macrospin(), {"field_T.2": [.1, .2, .3]}, continuation=True)
    original = run_job
    def failure(config, output, **kwargs):
        if config.field_T[2] == .2:
            raise NumericalFailure("injected failure")
        return original(config, output, **kwargs)
    monkeypatch.setattr("spinfreq.studies.run_job", failure)
    result = run_study(spec, tmp_path/"study")
    assert [r["status"] for r in result["cases"]] == ["succeeded", "failed", "pending"]
    monkeypatch.setattr("spinfreq.studies.run_job", original)
    resumed = run_study(spec, tmp_path/"study", resume=True)
    assert resumed["status"] == "succeeded"
    attempts = resumed["cases"][1]["attempts"]
    assert len(attempts) == 2 and attempts[0]["status"] == "failed"
    assert attempts[1]["initial_from_case"] == 0
    assert (tmp_path/"study/cases/0001/attempt-0001/initial.npy").read_bytes() == (tmp_path/"study/cases/0000/attempt-0000/equilibrium.npy").read_bytes()
    monkeypatch.setattr("spinfreq.studies._implementation", lambda: {"changed": True})
    with pytest.raises(ValueError, match="numerical implementation changed"):
        run_study(spec, tmp_path/"study", resume=True)


def test_interrupted_case_is_retried_without_overwriting(tmp_path, monkeypatch):
    spec = StudyConfig(macrospin(), {"field_T.2": [.1]})
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr("spinfreq.studies.run_job", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_study(spec, tmp_path/"study")
    assert not (tmp_path/"study/.study.lock").exists()
    monkeypatch.setattr("spinfreq.studies.run_job", run_job)
    result = run_study(spec, tmp_path/"study", resume=True)
    assert [a["status"] for a in result["cases"][0]["attempts"]] == ["interrupted", "succeeded"]
    (tmp_path/"study/.study.lock").touch()
    with pytest.raises(RuntimeError, match="locked"):
        run_study(spec, tmp_path/"study", resume=True)


@pytest.mark.parametrize("axes, continuation", [
    ({"typo": [1]}, False), ({"schema_version": [1]}, False), ({"field_T.9": [1]}, False),
    ({"nx": [2.5]}, False), ({"material.alpha": [0]}, False), ({"field_T.2": [float("nan")]}, False),
    ({"nx": [1, 2]}, True), ({"field_T.2": [.1], "material.D": [0]}, True),
    ({"field_T.2": [True]}, False), ({"field_T.2": []}, False),
])
def test_invalid_studies_fail_before_running(axes, continuation):
    with pytest.raises(ValueError):
        StudyConfig(macrospin(), axes, continuation)


def test_study_configuration_roundtrip_duplicate_keys_and_case_limit(tmp_path):
    spec = StudyConfig(macrospin(), {"field_T.2": [.1, .2]})
    assert StudyConfig.from_dict(spec.to_dict()) == spec
    path = tmp_path/"duplicate.json"
    path.write_text('{"schema_version":1,"axes":{"nx":[1],"nx":[2]},"base":{}}')
    with pytest.raises(ValueError, match="Duplicate"):
        StudyConfig.load(path)
    with pytest.raises(ValueError, match="1024"):
        StudyConfig(macrospin(), {"field_T.2": list(range(1025))})


def test_state_import_geometry_units_and_restart(tmp_path):
    config = macrospin()
    m = np.array([[[0., 0., 1.]]])
    np.save(tmp_path/"state.npy", m)
    write_ovf(tmp_path/"state.ovf", m, config.dx_m, config.dy_m, config.thickness_m)
    for name in ("state.npy", "state.ovf"):
        np.testing.assert_array_equal(load_initial_state(tmp_path/name, config), m)
    with pytest.raises(ValueError, match="mesh"):
        load_initial_state(tmp_path/"state.ovf", replace(config, dx_m=2*config.dx_m))
    (tmp_path/"M.ovf").write_text((tmp_path/"state.ovf").read_text().replace("# valueunits: 1 1 1", "# valueunits: A/m A/m A/m"))
    with pytest.raises(ValueError, match="dimensionless"):
        load_initial_state(tmp_path/"M.ovf", config)
    np.save(tmp_path/"bad.npy", 580e3*m)
    with pytest.raises(ValueError, match="unit vectors"):
        load_initial_state(tmp_path/"bad.npy", config)
    with pytest.raises(ValueError, match="real"):
        run_job(config, tmp_path/"complex", initial_m=m.astype(complex))
    result = run_job(config, tmp_path/"restart", initial_m=load_initial_state(tmp_path/"state.ovf", config))
    assert result["initialization"]["kind"] == "provided-state"


def test_cli_restart_and_study_exit_status(tmp_path):
    config = macrospin()
    path = tmp_path/"config.json"
    path.write_text(json.dumps(config.to_dict()))
    np.save(tmp_path/"state.npy", np.array([[[0., 0., 1.]]]))
    subprocess.run([sys.executable, "-m", "spinfreq.cli", "--config", str(path),
                    "--initial-state", str(tmp_path/"state.npy"), "--output", str(tmp_path/"run")], check=True, capture_output=True)
    spec = StudyConfig(config, {"field_T.2": [-5.]})
    path.write_text(json.dumps(spec.to_dict()))
    dry = subprocess.run([sys.executable, "-m", "spinfreq.studies", "--config", str(path),
                          "--dry-run"], check=True, capture_output=True, text=True)
    assert json.loads(dry.stdout)["case_count"] == 1
    assert not (tmp_path/"study").exists()
    completed = subprocess.run([sys.executable, "-m", "spinfreq.studies", "--config", str(path),
                                "--output", str(tmp_path/"study")], capture_output=True, text=True)
    assert completed.returncode == 1 and "failed: 0/1" in completed.stdout
