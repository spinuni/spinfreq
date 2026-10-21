from dataclasses import replace
import hashlib
import json
import zipfile

import numpy as np
import pytest

from spinfreq import JobConfig, run_job
from spinfreq.config import presets, validate_web_config
from spinfreq.jobs import NumericalFailure
from spinfreq.model import MU0


@pytest.mark.parametrize("updates", [dict(nx=True), dict(points=1), dict(nx=4097), dict(dx_m=float('nan')),
                                    dict(field_T=[0, 0]), dict(drive_T=[False, 0, 0]), dict(schema_version=2),
                                    dict(material={"alpha": 0}), dict(typo=1), dict(material={"Mss": 1})])
def test_invalid_configurations_are_rejected(updates):
    data = presets()["prism-fmr"].to_dict(); data.update(updates)
    with pytest.raises(ValueError):
        JobConfig.from_dict(data)


def test_configuration_roundtrip_and_duplicate_keys(tmp_path):
    for config in presets().values():
        assert JobConfig.from_dict(json.loads(json.dumps(config.to_dict()))) == config
        validate_web_config(config)
    path = tmp_path/'duplicate.json'; path.write_text('{"nx":1,"nx":2}')
    with pytest.raises(ValueError, match="Duplicate"):
        JobConfig.load(path)


def test_job_analytic_periodic_fmr_and_download_manifest(tmp_path):
    config = replace(presets()['periodic-fmr'], nx=1, ny=1, points=5)
    result = run_job(config, tmp_path/'run')
    p = config.material
    expected = p.gamma/(1+p.alpha**2)*(config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms)/(2*np.pi)
    modes = np.load(tmp_path/'run/modes.npz')
    np.testing.assert_allclose(max(modes['eigenvalues'].imag)/(2*np.pi), expected, rtol=1e-12)
    assert result['stability'] == 'stable' and result['max_response_residual'] < 1e-7
    assert result['mode_count'] == 2
    manifest = json.loads((tmp_path/'run/manifest.json').read_text())
    with zipfile.ZipFile(tmp_path/'run/results.zip') as archive:
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        assert 'manifest.json' in archive.namelist()
    with pytest.raises(FileExistsError):
        run_job(config, tmp_path/'run')


def test_large_response_fails_without_exporting_spectra(tmp_path):
    config = replace(presets()['prism-fmr'], drive_T=(1., 0., 0.))
    with pytest.raises(NumericalFailure, match='reduce the drive'):
        run_job(config, tmp_path/'run')
    assert json.loads((tmp_path/'run/summary.json').read_text())['status'] == 'failed'
    assert not (tmp_path/'run/modes.npz').exists()
    assert not (tmp_path/'run/response.npz').exists()
    assert not (tmp_path/'run/results.zip').exists()


def test_failed_equilibrium_does_not_reach_spectral_solver(tmp_path, monkeypatch):
    from spinfreq import Relaxation
    from spinfreq.model import Film
    monkeypatch.setattr(Film, 'relax', lambda self, initial, **kw: Relaxation(initial, 0., 1., False, 1, 'failed'))
    monkeypatch.setattr('spinfreq.jobs.refine_equilibrium', lambda film, m, **kw: Relaxation(m, 0., 1., False, 1, 'failed'))
    with pytest.raises(NumericalFailure, match='Static torque'):
        run_job(JobConfig(), tmp_path/'run')
    assert not (tmp_path/'run/modes.npz').exists()


def test_web_capacity_is_distinct_from_core_dense_limit():
    config = replace(JobConfig(), nx=21, ny=21)
    with pytest.raises(ValueError, match='Web limit'):
        validate_web_config(config)


def test_checked_in_examples_match_api_presets():
    from pathlib import Path
    directory = Path(__file__).resolve().parents[1]/'examples'
    for name, config in presets().items():
        assert JobConfig.load(directory/(name+'.json')) == config


@pytest.mark.parametrize('state', ['unstable', 'uncertain'])
def test_unstable_and_neutral_macrospins_withhold_spectra(tmp_path, state):
    config = replace(presets()['periodic-fmr'], nx=1, ny=1, points=5)
    p = config.material
    bias = -5. if state == 'unstable' else MU0*p.Ms-2*p.K/p.Ms
    config = replace(config, field_T=(0., 0., bias))
    with pytest.raises(NumericalFailure, match='stability'):
        run_job(config, tmp_path/'run')
    summary = json.loads((tmp_path/'run/summary.json').read_text())
    assert summary['stability'] == state
    assert not (tmp_path/'run/modes.npz').exists()
