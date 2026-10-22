from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest

from spinfreq import StudyConfig, match_modes, run_study, track_study
from spinfreq.config import presets


def test_matching_is_phase_scale_and_frequency_rank_independent():
    previous = np.eye(3, dtype=complex)
    current = previous[[2, 0, 1]]*np.array([1e-150*np.exp(.7j), 7j, -3.])[:, None]
    result = match_modes(previous, current)
    np.testing.assert_array_equal(result.current_indices, [1, 2, 0])
    np.testing.assert_allclose(result.overlaps, 1)
    assert not result.ambiguous.any()
    reduced = match_modes(previous, current[:2])
    assert len(reduced.overlaps) == 2


def test_degenerate_rotations_are_ambiguous_and_bad_vectors_are_rejected():
    rotation = np.array([[1, 1], [1, -1]])/np.sqrt(2)
    result = match_modes(np.eye(2), rotation)
    np.testing.assert_allclose(result.overlaps, .5)
    assert result.ambiguous.all()
    for bad in (np.zeros((2, 2)), np.array([[np.nan, 0], [0, 1]])):
        with pytest.raises(ValueError):
            match_modes(np.eye(2), bad)
    with pytest.raises(ValueError, match="shapes"):
        match_modes(np.eye(2), np.eye(3))


def synthetic_study(path, frequencies, rotated=None):
    """Synthetic pole files exercise analysis only; they are not physics evidence."""
    base = replace(presets()["periodic-fmr"], nx=2, ny=1, points=3)
    spec = StudyConfig(base, {"field_T.2": [.1+.01*i for i in range(len(frequencies))]})
    ledger = run_study(spec, path)
    basis = np.zeros((2, 1, 2, 3), dtype=complex)
    basis[0, 0, 0, 0] = basis[1, 0, 0, 1] = 1
    for i, f in enumerate(frequencies):
        directory = path/ledger["cases"][i]["attempts"][-1]["directory"]
        modes = basis.copy() if rotated is None else rotated[i]@basis.reshape(2, -1)
        modes = modes.reshape(basis.shape)
        np.savez_compressed(directory/"modes.npz", eigenvalues=-1e7+2j*np.pi*np.array(f)*1e9, modes=modes)
        ledger["cases"][i]["attempts"][-1]["sha256"]["modes.npz"] = hashlib.sha256((directory/"modes.npz").read_bytes()).hexdigest()
    (path/"study.json").write_text(json.dumps(ledger))
    return ledger


def load_rows(path):
    import csv
    with path.open() as stream:
        return list(csv.DictReader(stream))


def test_mode_character_tracks_through_frequency_reordering(tmp_path):
    path = tmp_path/"study"
    identity = np.eye(2)
    synthetic_study(path, [[8, 12], [9, 11], [8, 12]],
                    rotated=[identity, identity[::-1]*1j, identity[::-1]*(-3)])
    result = track_study(path, tmp_path/"tracking", max_modes=2)
    assert result["provisional_lineage_rows"] == 0
    rows = load_rows(tmp_path/"tracking/branches.csv")
    branch_zero = [row for row in rows if row["branch"] == "0"]
    np.testing.assert_allclose([float(row["frequency_Hz"])/1e9 for row in branch_zero], [8, 11, 12], rtol=1e-14)
    assert (tmp_path/"tracking/branches.pdf").stat().st_size > 0
    assert not (path/".study.lock").exists()
    with pytest.raises(FileExistsError):
        track_study(path, tmp_path/"tracking")


def test_degeneracy_flags_persist_after_modes_separate(tmp_path):
    identity = np.eye(2)
    rotated = np.array([[1, 1], [1, -1]])/np.sqrt(2)
    path = tmp_path/"study"
    synthetic_study(path, [[8, 12], [10, 10], [9, 11], [8, 12]],
                    rotated=[identity, rotated, identity, identity])
    result = track_study(path, tmp_path/"tracking", max_modes=2)
    assert result["provisional_lineage_rows"] == 6
    rows = load_rows(tmp_path/"tracking/branches.csv")
    last = [row for row in rows if row["case"] == "3"]
    assert all(row["local_ambiguous"] == "False" and row["lineage_ambiguous"] == "True" for row in last)


def test_failed_case_breaks_lineage_and_tampered_results_are_refused(tmp_path):
    path = tmp_path/"study"
    ledger = synthetic_study(path, [[8, 12]]*3)
    ledger["cases"][1]["status"] = "failed"
    (path/"study.json").write_text(json.dumps(ledger))
    result = track_study(path, tmp_path/"tracking", max_modes=2)
    assert result["skipped_cases"] == [{"case": 1, "status": "failed"}]
    rows = load_rows(tmp_path/"tracking/branches.csv")
    assert {row["branch"] for row in rows if row["case"] == "0"}.isdisjoint(
        {row["branch"] for row in rows if row["case"] == "2"})
    (path/"cases/0000/attempt-0000/modes.npz").write_bytes(b"modified")
    with pytest.raises(ValueError, match="integrity"):
        track_study(path, tmp_path/"bad")
    assert not (tmp_path/"bad").exists() and not (path/".study.lock").exists()
    (path/".study.lock").touch()
    with pytest.raises(RuntimeError, match="locked"):
        track_study(path, tmp_path/"locked")
    assert (path/".study.lock").exists()
