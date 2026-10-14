import importlib.util
from pathlib import Path
import sys
import numpy as np


def benchmark():
    directory=Path(__file__).resolve().parents[1]/'benchmarks'
    spec=importlib.util.spec_from_file_location('fig2_benchmark',directory/'liu2024_fig2.py')
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(directory))
    try: spec.loader.exec_module(module)
    finally: sys.path.pop(0)
    return module


def test_fig2_fm_reference_and_fit_units(tmp_path):
    module=benchmark()
    report,q,f=module.fm_reference(tmp_path)
    assert report['max_relative_error']<1e-10
    np.testing.assert_allclose(report['FMR_GHz'],37.52764986,rtol=1e-9)
    rows=[]
    for reduced in np.linspace(-1,1,17):
        cosine=np.cos(np.pi*reduced)
        rows.append(dict(reduced_ka_over_pi=reduced,gyration_GHz=1.2-1.0*cosine,
                         breathing_GHz=np.sqrt(295+120*cosine)))
    fits=module.fit_collective(rows)
    np.testing.assert_allclose(fits['gyration']['coefficients'],[1.2,-.5],atol=1e-12)
    np.testing.assert_allclose(fits['breathing']['coefficients'],[295,60],atol=1e-12)
    assert fits['breathing']['rms_frequency_residual_GHz']<1e-12
    # Preserve the literal publication's inconsistent coefficients, never repair them silently.
    assert fits['literal_paper_fits']['breathing_range_GHz'][0]<7
    assert fits['literal_paper_fits']['breathing_range_GHz'][1]>23


def test_bloch_cache_rejects_invalid_mesh(tmp_path):
    import pytest
    module=benchmark()
    np.savez(tmp_path/'bloch_4.npz',m=np.zeros((3,3,3)),k_rad_m=np.zeros(3))
    with pytest.raises(ValueError,match='Cached mesh'):
        module.chain_scan(4,3,2,tmp_path,reuse=True)


def test_old_bloch_physics_cache_is_rejected(tmp_path):
    import pytest
    module=benchmark()
    m=np.zeros((4,4,3));m[...,2]=1
    k=np.linspace(-1,1,3)*np.pi/(40e-9)
    np.savez(tmp_path/'bloch_4.npz',m=m,k_rad_m=k)
    with pytest.raises(ValueError,match='predates periodic'):
        module.chain_scan(4,3,2,tmp_path,reuse=True)
