import json
import sys

import pytest

from spinfreq.onboarding import cpu_self_check, demo_main, doctor_main


def test_doctor_reports_and_executes_real_cpu_check(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["spinfreq-doctor", "--check"])
    doctor_main()
    output = capsys.readouterr().out
    assert "CPU analytical self-check: passed" in output
    assert cpu_self_check() < 1e-10


def test_demo_preserves_previous_results_and_explains_outputs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["spinfreq-demo"])
    demo_main()
    first = (tmp_path/"results/first-simulation/results.zip").read_bytes()
    demo_main()
    assert (tmp_path/"results/first-simulation/results.zip").read_bytes() == first
    assert json.loads((tmp_path/"results/first-simulation-2/summary.json").read_text())["status"] == "succeeded"
    text = capsys.readouterr().out
    assert "1/4 Finding" in text and "Open spectrum.png" in text


def test_demo_browser_is_opt_in_and_occupied_output_refused(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("spinfreq.onboarding.webbrowser.open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(sys, "argv", ["spinfreq-demo", "--output", str(tmp_path/"run"), "--open"])
    demo_main()
    assert opened == [(tmp_path/"run/spectrum.png").as_uri()]
    with pytest.raises(SystemExit) as error:
        demo_main()
    assert error.value.code == 1
