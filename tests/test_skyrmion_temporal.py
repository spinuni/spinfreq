"""Independent pole extraction, complex residues and native reference integrity."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def benchmark(monkeypatch):
    path=Path(__file__).resolve().parents[1]/'benchmarks/skyrmion_temporal.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec=importlib.util.spec_from_file_location('skyrmion_temporal',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_independent_fit_recovers_three_damped_poles(monkeypatch):
    module=benchmark(monkeypatch)
    frequencies=np.array([1.83,16.3,38.]);rates=np.array([.15,.8,1.8])
    times=np.arange(1,2001)*2e-12
    waves=np.exp((-rates+2j*np.pi*frequencies)[None,:]*times[:,None]/1e-9)
    signals=np.column_stack([(waves[:,0]+.6*waves[:,2]).real,
        (waves[:,0]-.6*waves[:,2]).imag,.8*waves[:,1].imag])
    fit=module.fit_poles(times,signals,.2)
    np.testing.assert_allclose(fit['frequencies_GHz'],frequencies,rtol=1e-8)
    np.testing.assert_allclose(fit['decay_rates_per_ns'],rates,rtol=1e-7)
    assert fit['residual_RMS_over_channel_std']<1e-8


def test_complex_spatial_residues_keep_temporal_phase(monkeypatch):
    module=benchmark(monkeypatch);rng=np.random.default_rng(81)
    residues=rng.normal(size=(3,2,2,3))+1j*rng.normal(size=(3,2,2,3))
    fit=dict(frequencies_GHz=[1.83,16.3,38.],decay_rates_per_ns=[.15,.8,1.8])
    times=np.arange(1,401)*1e-11
    waves=np.exp((-np.array(fit['decay_rates_per_ns'])+2j*np.pi*np.array(fit['frequencies_GHz']))[None,:]*times[:,None]/1e-9)
    fields=2*np.real(np.einsum('tj,jyxc->tyxc',waves,residues))
    extracted,residual=module.extract_mode_fields(times,fields,fit)
    np.testing.assert_allclose(extracted,residues,atol=1e-12)
    assert residual<1e-12


def test_archive_restore_checks_integrity_before_writing(tmp_path,monkeypatch):
    module=benchmark(monkeypatch);native=tmp_path/'native';native.mkdir()
    (native/'ringdown.mif').write_text('# Actual solver input\n')
    (native/'snapshot.omf').write_bytes(b'Native reference bytes')
    reference=tmp_path/'reference';hashes,digest=module.archive_reference(native,reference)
    (reference/'summary.json').write_text(json.dumps(dict(raw_reference_sha256=hashes,reference_archive_sha256=digest)))
    restored=tmp_path/'restored';module.restore_reference(reference,restored)
    assert (restored/'snapshot.omf').read_bytes()==b'Native reference bytes'
    archive=reference/'oommf_reference.tar.gz';content=bytearray(archive.read_bytes());content[-10]^=1;archive.write_bytes(content)
    with pytest.raises(ValueError,match='hash mismatch'):module.restore_reference(reference,tmp_path/'corrupted')
    assert not (tmp_path/'corrupted').exists()


def test_mesh_qualification_cannot_accept_only_coarse_dynamics(tmp_path,monkeypatch):
    module=benchmark(monkeypatch)
    root=tmp_path/'cases';(root/'field_0mT').mkdir(parents=True)
    config=dict(nx=20,ny=20,dx_m=2e-9,dy_m=2e-9,thickness_m=1e-9,field_T=[0,0,0],
        dmi_boundary='bond',material=dict(Ms=580e3,A=15e-12,D=.003,K=.6e6,alpha=.01,gamma=1.7595e11))
    (root/'field_0mT/summary.json').write_text(json.dumps(dict(configuration=config)))
    mesh=tmp_path/'mesh.json';mesh.write_text(json.dumps(dict(results=[
        dict(field_T=0,cells=40,frequencies_GHz=[1.9,17.1,38.4]),
        dict(field_T=0,cells=50,frequencies_GHz=[1.902,17.2,38.5])])))
    with pytest.raises(ValueError,match='finest qualified pair'):
        module.qualify_suite(root,mesh,tmp_path/'output')
