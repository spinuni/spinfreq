import importlib.util
from pathlib import Path

import numpy as np


def test_multitone_demodulation_preserves_absolute_amplitude_and_phase(monkeypatch):
    path=Path(__file__).resolve().parents[1]/'benchmarks/driven_response.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec=importlib.util.spec_from_file_location('driven_response',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    frequencies=np.array([15.8,16.3,16.8,37.2,38.,38.8])*1e9
    rng=np.random.default_rng(13)
    phasors=(rng.normal(size=(6,3))+1j*rng.normal(size=(6,3)))*1e-4
    times=np.arange(1,4001)*2e-12
    trace=np.real(np.exp(2j*np.pi*times[:,None]*frequencies[None,:])@phasors)+[.01,-.02,.03]
    extracted,diagnostics=module.demodulate(times,trace,frequencies,4e-9)
    np.testing.assert_allclose(extracted,phasors,rtol=1e-11,atol=1e-15)
    assert diagnostics['design_condition_number']<2
