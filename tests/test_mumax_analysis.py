import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from spinfreq.ovf import write_ovf


def test_analyze_mumax_snapshots_with_actual_timestamps(tmp_path):
    source=tmp_path/'reference.out'
    source.mkdir()
    for index in range(20):
        m=np.zeros((3,3,3))
        m[...,2]=.01*np.sin(2*np.pi*10e9*index*5e-12)
        path=source/f'm{index:06d}.ovf'
        write_ovf(path,m,1e-9,1e-9,1e-9)
        text=path.read_text().replace('# End: Header',f'# Desc: Total simulation time: {index*5e-12:.17g} s\n# End: Header')
        path.write_text(text)
    root=Path(__file__).resolve().parents[1]
    output=tmp_path/'analysis'
    subprocess.run([sys.executable,str(root/'benchmarks'/'analyze_mumax.py'),str(source),'--output',str(output)],
                   cwd=root,env={**os.environ,'MPLCONFIGDIR':str(tmp_path/'mpl')},check=True,capture_output=True)
    spectrum=np.loadtxt(output/'spectrum.csv',delimiter=',',skiprows=1)
    peak=spectrum[np.argmax(spectrum[:,1])]
    np.testing.assert_allclose(peak[:2],[10e9,.01],rtol=1e-6)
