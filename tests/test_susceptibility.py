from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest
from scipy.linalg import lu_factor

from spinfreq import Film, ModalResponse, SpatialProfile, susceptibility, analyze_job, run_job
from spinfreq.config import presets
from spinfreq.model import MU0
from spinfreq.profiles import observe


def prepared_film(nx=1, ny=1):
    config = replace(presets()['periodic-fmr'], nx=nx, ny=ny, points=17)
    film = Film(nx=nx, ny=ny, dx=config.dx_m, dy=config.dy_m,
                thickness=config.thickness_m, material=config.material, field_T=config.field_T)
    m = np.zeros(film.shape); m[..., 2] = 1
    return config, film, ModalResponse(film, m)


def analytic_tensor(config, frequencies):
    p = config.material
    h = config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms
    rate = p.gamma/(1+p.alpha**2)
    matrix = rate*h*np.array([[-p.alpha, -1], [1, -p.alpha]])
    force = rate*np.array([[p.alpha, 1], [-1, p.alpha]])
    result = np.zeros((len(frequencies), 3, 3), complex)
    for index, f in enumerate(frequencies):
        result[index, :2, :2] = np.linalg.solve(2j*np.pi*f*np.eye(2)-matrix, force)
    return result


def test_full_gilbert_tensor_and_residue_reconstruction():
    config, film, prepared = prepared_film()
    f = np.linspace(0, 60e9, 61)
    data = susceptibility(prepared, f)
    np.testing.assert_allclose(data['tensor_per_T'][:, 0], analytic_tensor(config, f), rtol=2e-13, atol=2e-13)
    reconstructed = np.einsum('fn,npij->fpij', 1/(2j*np.pi*f[:, None]-data['eigenvalues_per_s']),
                               data['residues_per_T_s'])
    np.testing.assert_allclose(reconstructed, data['tensor_per_T'], rtol=2e-13, atol=2e-13)
    np.testing.assert_array_equal(data['tensor_per_T'][:, :, 2, :], 0)
    np.testing.assert_array_equal(data['tensor_per_T'][:, :, :, 2], 0)
    assert np.max(data['response_residuals']) < 1e-12


def test_complex_source_probe_polarization_and_mode_gauge():
    _, film, prepared = prepared_film(4, 2)
    f = np.array([2e9, 10e9, 33e9])
    source = SpatialProfile('plane_wave', k_rad_m=(2*np.pi/(film.nx*film.dx), 0)).evaluate(film.nx, film.ny, film.dx, film.dy)
    probes = np.array([np.ones(source.shape), source, source*np.exp(.7j)])
    data = susceptibility(prepared, f, source, probes)
    drive = np.array([1e-6+2e-7j, -3e-7j, 2e-7])
    direct = observe(prepared.response(f, source[..., None]*drive), probes)
    np.testing.assert_allclose(np.einsum('fpij,j->fpi', data['tensor_per_T'], drive), direct, atol=1e-16, rtol=1e-12)
    assert np.linalg.norm(data['tensor_per_T'][:, 0]) < 1e-12*np.linalg.norm(data['tensor_per_T'][:, 1])
    np.testing.assert_allclose(data['tensor_per_T'][:, 2], data['tensor_per_T'][:, 1]*np.exp(-.7j), atol=1e-11)
    factors = np.linspace(.2, 4, len(prepared.values))*np.exp(1j*np.arange(len(prepared.values)))
    prepared.vectors *= factors
    prepared._factor = lu_factor(prepared.vectors)
    scaled = susceptibility(prepared, f, source, probes)
    np.testing.assert_allclose(scaled['residues_per_T_s'], data['residues_per_T_s'], atol=.01, rtol=1e-11)
    np.testing.assert_allclose(scaled['tensor_per_T'], data['tensor_per_T'], atol=1e-11, rtol=1e-11)


def test_degenerate_group_residue_is_basis_invariant():
    _, _, prepared = prepared_film(2, 2)
    # A zero operator is exactly degenerate and diagonalizable. At f>0 the
    # resolvent remains defined; no stability claim is made by the low-level API.
    prepared.matrix[:] = 0
    prepared.values[:] = 0
    prepared.vectors = np.eye(len(prepared.values), dtype=complex)
    prepared._factor = lu_factor(prepared.vectors)
    data = susceptibility(prepared, [1e9])
    rng = np.random.default_rng(42)
    rotation, _ = np.linalg.qr(rng.normal(size=prepared.matrix.shape))
    prepared.vectors = rotation.astype(complex)
    prepared._factor = lu_factor(prepared.vectors)
    rotated = susceptibility(prepared, [1e9])
    np.testing.assert_allclose(rotated['residues_per_T_s'].sum(axis=0), data['residues_per_T_s'].sum(axis=0), rtol=1e-13, atol=.001)
    np.testing.assert_allclose(rotated['tensor_per_T'], data['tensor_per_T'], rtol=1e-13, atol=1e-13)


@pytest.mark.parametrize('source,probes', [(np.zeros((1, 1)), None), (np.ones((2, 1)), None),
                                           (None, np.zeros((1, 1, 1))), (None, np.ones((1, 2, 1)))])
def test_invalid_profiles(source, probes):
    _, _, prepared = prepared_film()
    with pytest.raises(ValueError):
        susceptibility(prepared, [1e9], source, probes)


@pytest.mark.parametrize('frequencies', [[], [-1], [np.nan], [[1e9]]])
def test_invalid_frequencies(frequencies):
    _, _, prepared = prepared_film()
    with pytest.raises(ValueError, match='frequency vector'):
        susceptibility(prepared, frequencies)


def test_verified_job_export_and_tampering(tmp_path):
    config = replace(presets()['prism-fmr'], points=5)
    job, output = tmp_path/'job', tmp_path/'tensor'
    run_job(config, job)
    original = (job/'manifest.json').read_bytes()
    report = analyze_job(job, output)
    assert report['status'] == 'succeeded'
    assert report['reconstruction_error_full_field_scaled'] < 1e-12
    assert (job/'manifest.json').read_bytes() == original
    manifest = json.loads((output/'manifest.json').read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256((output/name).read_bytes()).hexdigest() == digest
    with np.load(output/'susceptibility.npz', allow_pickle=False) as data:
        assert data['tensor_per_T'].shape == (5, 1, 3, 3)
    with pytest.raises(FileExistsError):
        analyze_job(job, output)
    (job/'equilibrium.npy').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='integrity'):
        analyze_job(job, tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_tensor_export_allows_symmetry_cancelled_probe(tmp_path):
    from spinfreq import Probe
    config = replace(presets()['periodic-fmr'], nx=4, ny=2, points=5,
                     drive_profile=SpatialProfile('plane_wave', k_rad_m=(2*np.pi/(4*4e-9), 0)),
                     probes=(Probe('mean'),))
    run_job(config, tmp_path/'job')
    summary = analyze_job(tmp_path/'job', tmp_path/'tensor')
    assert summary['grouped_tensor_reconstruction_scaled_error'] < 1e-12


def test_changed_numerical_source_rejected(tmp_path):
    job = tmp_path/'job'
    run_job(replace(presets()['prism-fmr'], points=3), job)
    path = job/'summary.json'
    summary = json.loads(path.read_text())
    summary['solver_source_sha256']['model.py'] = '0'*64
    path.write_text(json.dumps(summary))
    manifest = json.loads((job/'manifest.json').read_text())
    manifest['summary.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (job/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='sources changed'):
        analyze_job(job, tmp_path/'bad')
