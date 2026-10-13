import importlib.util
from pathlib import Path
import numpy as np


def load_benchmark():
    path=Path(__file__).resolve().parents[1]/'benchmarks'/'liu2024.py'
    spec=importlib.util.spec_from_file_location('liu_benchmark',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paper_coarse_single_skyrmion_regression():
    benchmark=load_benchmark()
    film,result,spectrum,indices=benchmark.run_single(20)
    np.testing.assert_allclose(spectrum.frequencies_Hz[indices]/1e9,np.array([1.8433,16.4372,39.1174])*1.7595e11/1.760859e11,rtol=5e-4)
    assert result.converged
    # This coarse check is not the 1 nm paper validation.
    frequencies=np.array([1.8e9,17e9,39e9])
    modal=benchmark.modal_absorption(film,result.m,spectrum,frequencies)
    for axis in (0,2):
        drive=np.eye(3)[axis]*1e-6
        direct=film.response(result.m,frequencies,drive)
        np.testing.assert_allclose(modal[axis][0],direct.mean(axis=(1,2)),rtol=1e-6,atol=1e-13)
        np.testing.assert_allclose(modal[axis][1],film.absorbed_power(frequencies,direct,drive),rtol=1e-6,atol=1e-30)
