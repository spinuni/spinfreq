import numpy as np
import pytest
from spinfreq import Film, Material, skyrmion_lattice
from spinfreq.model import MU0

def uniform(film):
    m = np.zeros(film.shape)
    m[..., 2] = 1
    return m

def test_variational_field():
    film = Film(nx=5, ny=5)
    rng = np.random.default_rng(2)
    m = rng.normal(size=film.shape)
    v = rng.normal(size=film.shape)
    eps = 1e-5
    measured = (film.energy(m+eps*v)-film.energy(m-eps*v))/(2*eps)
    predicted = -film.material.Ms*np.sum(film.effective_field(m)*v)*film.dx*film.dy*film.thickness
    np.testing.assert_allclose(measured, predicted, rtol=1e-8, atol=1e-30)

def test_uniform_demag_and_kittel():
    film = Film(nx=3, ny=3, field_T=(0,0,1))
    m = uniform(film)
    np.testing.assert_allclose(film.demag_field(m)[..., 2], -MU0*film.material.Ms)
    b = 1+2*film.material.K/film.material.Ms-MU0*film.material.Ms
    spec = film.modes(m)
    expected = film.material.gamma*b/(1+film.material.alpha**2)
    positive = spec.eigenvalues[spec.eigenvalues.imag > 0]
    lowest = positive[np.argmin(positive.imag)]
    np.testing.assert_allclose(lowest.imag, expected, rtol=1e-10)
    np.testing.assert_allclose(lowest.real, -film.material.alpha*expected, rtol=1e-10)
    assert np.max(abs(np.sum(spec.modes*m, axis=-1))) < 1e-10

def test_exchange_dispersion():
    film = Film(nx=5, ny=3, demag=False, material=Material(D=0, K=0, alpha=0), field_T=(0,0,1))
    spec = film.modes(uniform(film))
    predicted = film.material.gamma*(1+2*film.material.A/film.material.Ms*film.k2.ravel())
    actual = spec.eigenvalues.imag[spec.eigenvalues.imag > 0]
    np.testing.assert_allclose(np.sort(actual), np.sort(predicted), rtol=1e-10)

def test_response_resonance_and_power():
    film = Film(nx=3, ny=3, field_T=(0,0,1))
    m = uniform(film)
    f0 = min(film.modes(m).frequencies_Hz[film.modes(m).frequencies_Hz > 0])
    frequencies = np.array([0.8, 1, 1.2])*f0
    response = film.response(m, frequencies)
    amplitude = np.sqrt(np.sum(abs(response)**2, axis=(1,2,3)))
    assert np.argmax(amplitude) == 1
    assert np.all(film.absorbed_power(frequencies, response, (1e-4,0,0)) > 0)
    doubled = film.response(m, frequencies, (2e-4,0,0))
    np.testing.assert_allclose(doubled, 2*response)

def test_analytic_jacobian():
    film = Film(nx=3, ny=3)
    m = uniform(film)
    matrix, basis = film.linearize(m)
    rng = np.random.default_rng(8)
    coords = rng.normal(size=(3,3,2))
    v = np.einsum('...ci,...i->...c', basis, coords)
    eps = 1e-6
    plus, minus = m+eps*v, m-eps*v
    plus /= np.linalg.norm(plus, axis=-1, keepdims=True)
    minus /= np.linalg.norm(minus, axis=-1, keepdims=True)
    numerical = np.einsum('...ci,...c->...i', basis, (film.llg(plus)-film.llg(minus))/(2*eps)).ravel()
    np.testing.assert_allclose(matrix@coords.ravel(), numerical, rtol=1e-8)

def test_relaxation_and_equilibrium_guard():
    film = Film(nx=3, ny=3, demag=False, material=Material(D=0), field_T=(0,0,1))
    m = uniform(film)
    m[...,0] = 0.2
    m /= np.linalg.norm(m, axis=-1, keepdims=True)
    with pytest.raises(ValueError, match='equilibrium'):
        film.modes(m)
    result = film.relax(m)
    assert result.converged
    assert result.energy_J < film.energy(m)
    assert np.min(result.m[...,2]) > 0.999

def test_resolved_seed_charge():
    film = Film(nx=65, ny=65, dx=2e-9)
    m = skyrmion_lattice(film)
    np.testing.assert_allclose(np.linalg.norm(m, axis=-1), 1)
    assert abs(film.topological_charge(m)+1) < 0.03


def test_skyrmion_relaxation_preserves_texture():
    film = Film(nx=12, ny=12)
    seed = skyrmion_lattice(film)
    result = film.relax(seed)
    assert result.converged
    assert result.energy_J < film.energy(seed)
    assert abs(film.topological_charge(result.m)+1) < 0.03

def test_noncollinear_jacobian():
    film = Film(nx=5, ny=5)
    m = skyrmion_lattice(film)
    # Permit an unequilibrated seed only to test the derivative itself.
    matrix, basis = film.linearize(m, equilibrium_tolerance_T=100)
    coords = np.random.default_rng(4).normal(size=(5,5,2))
    v = np.einsum('...ci,...i->...c', basis, coords)
    eps = 1e-6
    numerical = np.einsum('...ci,...c->...i', basis, (film.llg(m+eps*v)-film.llg(m-eps*v))/(2*eps)).ravel()
    np.testing.assert_allclose(matrix@coords.ravel(), numerical, rtol=1e-7, atol=100)
