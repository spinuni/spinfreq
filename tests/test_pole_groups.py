import numpy as np
import pytest

from spinfreq import group_poles, grouped_response


def test_diameter_limit_sign_and_decay_separation():
    # Close adjacent pairs must not form a long chain. Equal frequencies with
    # different decay rates must not be called the same complex pole.
    hz = np.array([-1+10j, -1+10.9j, -1+11.8j, -8+10j, -1-10j])
    result = group_poles(2*np.pi*hz, np.ones((5, 3)), atol_Hz=1., rtol=0)
    assert sorted(r['count'] for r in result['groups']) == [1, 1, 1, 2]
    assert result['mode_group'][0] == result['mode_group'][1]
    assert result['mode_group'][2] != result['mode_group'][0]
    assert result['mode_group'][3] != result['mode_group'][0]
    assert result['mode_group'][4] != result['mode_group'][0]
    assert max(r['complex_diameter_Hz'] for r in result['groups']) <= 1


def test_nearby_response_keeps_each_denominator_and_is_order_invariant():
    values = 2*np.pi*np.array([-.01+10j, -.01+10.1j, -2-10j])
    residue = np.array([[1+2j, -3j], [-1-2j, 2j], [.3j, 4.]])
    frequencies = np.array([10., 10.05, 10.1])
    result = group_poles(values, residue, atol_Hz=.2, rtol=0)
    assert any(g['kind'] == 'nearby_distinct' for g in result['groups'])
    computed = sum(response for _, response in grouped_response(frequencies, values, residue, result))
    exact = (1/(2j*np.pi*frequencies[:, None]-values))@residue
    np.testing.assert_allclose(computed, exact, atol=1e-14)
    order = [2, 0, 1]
    permuted = group_poles(values[order], residue[order], atol_Hz=.2, rtol=0)
    np.testing.assert_allclose(permuted['summed_residues'], result['summed_residues'])
    # Putting the cancelling summed residues over a mean pole loses the signal.
    group = next(r for r in result['groups'] if r['count'] == 2)
    mean_pole = values[group['members']].mean()
    approximate = result['summed_residues'][group['group']][None]/(2j*np.pi*frequencies[:, None]-mean_pole)
    exact_group = dict(grouped_response(frequencies, values, residue, result))[group['group']]
    assert np.linalg.norm(exact_group-approximate) > 1


def test_coincident_sum_invariant_under_basis_rotation():
    rng = np.random.default_rng(12)
    c = rng.normal(size=(3, 3))+1j*rng.normal(size=(3, 3))
    forcing = rng.normal(size=(3, 2))+1j*rng.normal(size=(3, 2))
    q, _ = np.linalg.qr(rng.normal(size=(3, 3))+1j*rng.normal(size=(3, 3)))
    values = np.full(3, -3+1e10j)
    residues = np.einsum('in,nj->nij', c, forcing)
    rotated = np.einsum('in,nj->nij', c@q, q.conj().T@forcing)
    first, second = group_poles(values, residues), group_poles(values, rotated)
    assert first['groups'][0]['kind'] == 'numerically_coincident'
    np.testing.assert_allclose(first['summed_residues'], second['summed_residues'], atol=2e-14)


@pytest.mark.parametrize('options', [{'atol_Hz': -1}, {'rtol': np.nan}, {'rtol': True}])
def test_bad_group_tolerances(options):
    with pytest.raises(ValueError):
        group_poles([1j], [1], **options)


def test_partition_and_singular_response_rejected():
    grouping = group_poles([0j, 0j], [1, 2])
    with pytest.raises(RuntimeError, match='Singular'):
        list(grouped_response([0], [0j, 0j], [1, 2], grouping))
    grouping['groups'][0]['members'] = [0, 0]
    with pytest.raises(ValueError, match='partition'):
        list(grouped_response([1], [0j, 0j], [1, 2], grouping))


def test_symmetric_film_groups_reconstruct_full_complex_tensor():
    from spinfreq import Film, Material, ModalResponse, susceptibility
    film = Film(nx=4, ny=4, dx=8e-9, thickness=1e-9,
                material=Material(D=0), field_T=(0, 0, .1))
    m = np.zeros(film.shape); m[..., 2] = 1
    prepared = ModalResponse(film, m)
    source = np.zeros(m.shape[:2]); source[0, 0] = 1
    frequencies = np.array([5e9, 20e9, 70e9])
    data = susceptibility(prepared, frequencies, source, source[None])
    grouping = group_poles(prepared.values, data['residues_per_T_s'])
    assert any(g['count'] > 1 for g in grouping['groups'])
    reconstructed = sum(response for _, response in grouped_response(frequencies, prepared.values, data['residues_per_T_s'], grouping))
    np.testing.assert_allclose(reconstructed, data['tensor_per_T'], rtol=1e-12, atol=1e-12)
