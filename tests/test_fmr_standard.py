"""Numerical checks for the external-reference FMR benchmark utilities."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import expm


def benchmark():
    path=Path(__file__).resolve().parents[1]/'benchmarks'/'fmr_standard_problem.py'
    spec=importlib.util.spec_from_file_location('fmr_standard',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nonnormal_ringdown_against_matrix_exponential():
    # Elliptical precession: right eigenvectors are not orthogonal.
    # A conjugate transpose in place of the inverse gives a wrong trajectory.
    module=benchmark()
    matrix=np.array([[-.1,-4.],[1.,-.3]])
    times=np.linspace(.01,8,71)
    initial=np.array([.01,-.02])
    observation=np.eye(2)
    observed,_,_,_=module.linear_ringdown(matrix,initial,observation,times)
    expected=np.array([expm(matrix*t)@initial for t in times]).T
    np.testing.assert_allclose(observed,expected,rtol=1e-11,atol=1e-14)


def test_corrupted_external_reference_is_rejected(tmp_path):
    # Avoid silently comparing a changed upstream dataset with old claims.
    (tmp_path/'dynamic_txyz.txt').write_text('corrupted reference')
    with pytest.raises(ValueError,match='checksum'):
        benchmark().reference_files(tmp_path)
