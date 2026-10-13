import importlib.util
from pathlib import Path


def test_analytical_validation_artifacts(tmp_path):
    path = Path(__file__).resolve().parents[1]/'benchmarks'/'validate.py'
    spec = importlib.util.spec_from_file_location('validation_benchmarks', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    errors = module.analytical(tmp_path)
    assert max(errors.values()) < 1e-8
    for name in ['kittel','dispersion','susceptibility']:
        assert (tmp_path/f'{name}.png').stat().st_size > 1000
        assert (tmp_path/f'{name}.pdf').stat().st_size > 1000
        assert len((tmp_path/f'{name}.csv').read_text().splitlines()) > 10


def test_stable_grid_position_selection():
    import numpy as np
    from spinfreq import Film
    path = Path(__file__).resolve().parents[1]/'benchmarks'/'validate.py'
    spec = importlib.util.spec_from_file_location('validation_stability', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    film = Film(nx=16, ny=16, dx=48e-9/16)
    result, spectrum, offset, diagnostics = module.stable_equilibrium(film)
    assert result.converged
    assert np.max(spectrum.eigenvalues.real) < 0
    assert len(diagnostics) == 2
    assert any(entry['max_growth_per_s'] > 0 for entry in diagnostics)
    assert abs(film.topological_charge(result.m)+1) < 0.01
