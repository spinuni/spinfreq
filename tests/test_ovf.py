import numpy as np
from spinfreq.ovf import read_ovf,write_ovf


def test_ovf2_text_roundtrip(tmp_path):
    field=np.random.default_rng(7).normal(size=(3,4,3))
    path=tmp_path/'field.ovf'
    write_ovf(path,field,1e-9,2e-9,1e-9)
    result,metadata=read_ovf(path)
    np.testing.assert_array_equal(result,field)
    assert float(metadata['ystepsize'])==2e-9


def test_ovf2_binary_read(tmp_path):
    field=np.arange(18,dtype=np.float32).reshape(2,3,3)
    path=tmp_path/'binary.ovf'
    header=b'# OOMMF OVF 2.0\n# xnodes: 3\n# ynodes: 2\n# znodes: 1\n# valuedim: 3\n# Begin: Data Binary 4\n'
    path.write_bytes(header+np.array([1234567],dtype='<f4').tobytes()+field.astype('<f4').tobytes()+b'\n# End: Data Binary 4\n')
    result,_=read_ovf(path)
    np.testing.assert_array_equal(result,field)


def test_ovf2_binary8_timestamp(tmp_path):
    field=np.arange(18,dtype=np.float64).reshape(2,3,3)
    path=tmp_path/'binary8.ovf'
    header=b'# OOMMF OVF 2.0\n# xnodes: 3\n# ynodes: 2\n# znodes: 1\n# valuedim: 3\n# Desc: Total simulation time: 5e-12 s\n# Begin: Data Binary 8\n'
    path.write_bytes(header+np.array([123456789012345],dtype='<f8').tobytes()+field.astype('<f8').tobytes())
    result,metadata=read_ovf(path)
    np.testing.assert_array_equal(result,field)
    assert metadata['time_s']==5e-12
