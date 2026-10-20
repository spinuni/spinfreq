"""Actual OOMMF table format and the historical even-FFT frequency offset."""
import gzip
import importlib.util
from pathlib import Path

import numpy as np
import pytest


def benchmark():
    path=Path(__file__).resolve().parents[1]/'benchmarks/dmi_temporal.py'
    spec=importlib.util.spec_from_file_location('dmi_temporal',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('compressed',[False,True])
def test_OOMMF_table_braced_labels_and_continuation(tmp_path,compressed):
    text='''# ODT 1.0
# Table Start
# Columns: {Oxs_TimeDriver::Simulation time} \\
# Oxs_TimeDriver::q1_cos Oxs_TimeDriver::q1_sin
# Units: s {} {}
1e-12 4.9e-5 -2.9e-6
2e-12 4.8e-5 -5.8e-6
# Table End
'''
    path=tmp_path/('trace.odt.gz' if compressed else 'trace.odt')
    path.write_bytes(gzip.compress(text.encode()) if compressed else text.encode())
    data=benchmark().read_odt(path)
    np.testing.assert_allclose(data['Oxs_TimeDriver::Simulation time'],[1e-12,2e-12])
    np.testing.assert_allclose(data['Oxs_TimeDriver::q1_cos'],[4.9e-5,4.8e-5])


def test_incomplete_OOMMF_run_cannot_be_analyzed_as_complete(tmp_path):
    path=tmp_path/'unfinished.odt'
    path.write_text('# ODT 1.0\n# Table Start\n# Columns: time value\n0 1\n')
    with pytest.raises(ValueError,match='complete'):benchmark().read_odt(path)


def test_legacy_reversal_shifts_even_frequency_labels_by_one_bin(tmp_path):
    records=benchmark().fft_audit(tmp_path)
    even,odd=records
    np.testing.assert_allclose(even['legacy_error_GHz'],-even['bin_GHz'],atol=1e-10)
    np.testing.assert_allclose(odd['legacy_error_GHz'],0,atol=1e-10)
    for row in records:
        np.testing.assert_allclose(row['correct_peak_GHz'],row['true_frequency_GHz'],rtol=1e-12)
