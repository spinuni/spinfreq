"""Installed gallery semantics and real generated-project execution."""
import hashlib
from importlib import resources
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from spinfreq.bundled_examples import RECIPES, _command, create_example, list_examples, main, run_example_main
from spinfreq.config import JobConfig
from spinfreq.qualification import package_fingerprint
from spinfreq.studies import StudyConfig


def test_all_bundled_recipes_validate_and_are_independent_copies(tmp_path):
    records = list_examples()
    assert len(records) == 8
    assert {record['kind'] for record in records} == {'job', 'study'}
    for record in records:
        path = tmp_path/record['name']
        manifest = create_example(record['name'], path)
        loader = JobConfig if record['kind'] == 'job' else StudyConfig
        config = loader.load(path/manifest['configuration_file'])
        assert manifest['case_count'] == (1 if record['kind'] == 'job' else len(config.cases()))
        for name, digest in manifest['starter_files_sha256'].items():
            assert hashlib.sha256((path/name).read_bytes()).hexdigest() == digest
    other = tmp_path/'second'
    create_example('prism-fmr', other)
    (tmp_path/'prism-fmr/configuration.json').write_text('{}')
    assert JobConfig.load(other/'configuration.json').nx == 1


def test_existing_folder_and_invalid_name_never_overwrite(tmp_path):
    sentinel = tmp_path/'keep.txt'; sentinel.write_text('keep')
    with pytest.raises(FileExistsError):
        create_example('prism-fmr', tmp_path)
    assert sentinel.read_text() == 'keep'
    with pytest.raises(ValueError, match='Unknown example'):
        create_example('../outside', tmp_path/'new')
    assert not (tmp_path/'new').exists()


def test_editable_moved_project_runs_from_unrelated_working_directory(tmp_path):
    original, moved, cwd = tmp_path/'original', tmp_path/'experiment with spaces', tmp_path/'elsewhere'
    create_example('prism-fmr', original)
    shutil.move(original, moved); cwd.mkdir()
    path = moved/'configuration.json'
    data = json.loads(path.read_text()); data['points'] = 7; data['field_T'][2] = .2
    path.write_text(json.dumps(data))
    command = [sys.executable, str(moved/'run.py')]
    checked = subprocess.run([*command, '--check'], cwd=cwd, capture_output=True, text=True, check=True)
    assert '1 case(s)' in checked.stdout
    assert not (moved/'results').exists()
    subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True)
    output = moved/'results/run'
    actual = JobConfig.load(output/'configuration.json')
    assert actual.points == 7 and actual.field_T[2] == .2
    saved = (output/'results.zip').read_bytes()
    rejected = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    assert rejected.returncode == 1
    assert (output/'results.zip').read_bytes() == saved
    subprocess.run([*command, '--output', 'results/second'], cwd=cwd, capture_output=True, text=True, check=True)
    assert (moved/'results/second/spectrum.png').is_file()
    assert not (cwd/'results').exists()


def test_generated_study_uses_study_loader_and_case_count(tmp_path, monkeypatch, capsys):
    create_example('fmr-field-sweep', tmp_path/'scan')
    path = tmp_path/'scan/study.json'
    spec = json.loads(path.read_text()); spec['axes']['field_T.2'] = [.1, .2]
    path.write_text(json.dumps(spec))
    monkeypatch.setattr(sys, 'argv', ['run.py', '--check'])
    run_example_main(tmp_path/'scan', kind='study')
    assert '2 case(s)' in capsys.readouterr().out
    assert not (tmp_path/'scan/results').exists()
    monkeypatch.setattr(sys, 'argv', ['run.py'])
    run_example_main(tmp_path/'scan', kind='study')
    ledger = json.loads((tmp_path/'scan/results/study/study.json').read_text())
    assert ledger['status'] == 'succeeded' and len(ledger['cases']) == 2
    assert (tmp_path/'scan/results/study/spectra.png').is_file()


def test_bad_edited_config_stops_before_creating_results(tmp_path, monkeypatch):
    create_example('prism-fmr', tmp_path/'case')
    path = tmp_path/'case/configuration.json'
    data = json.loads(path.read_text()); data['dx_m'] = -1
    path.write_text(json.dumps(data))
    monkeypatch.setattr(sys, 'argv', ['run.py'])
    with pytest.raises(SystemExit) as error:
        run_example_main(tmp_path/'case', kind='job')
    assert error.value.code == 1
    assert not (tmp_path/'case/results').exists()


def test_gallery_cli_lists_then_creates_without_calculating(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['spinfreq-examples', '--list'])
    main()
    output = capsys.readouterr().out
    assert all(name in output for name in RECIPES)
    monkeypatch.setattr(sys, 'argv', ['spinfreq-examples', '--name', 'prism-fmr', '--output', str(tmp_path/'example')])
    main()
    assert not (tmp_path/'example/results').exists()
    text = capsys.readouterr().out
    assert 'Check:' in text and 'No calculation performed' in text
    assert str(Path(sys.executable)) in text


def test_powershell_command_quotes_spaces_and_apostrophes():
    assert _command([r"C:\Users\O'Brien\Python\python.exe", 'D:/my experiment/run.py', '--check'], windows=True) == (
        "& 'C:\\Users\\O''Brien\\Python\\python.exe' 'D:/my experiment/run.py' '--check'")


def test_json_resources_are_covered_by_package_fingerprint(tmp_path):
    data = tmp_path/'data'; data.mkdir()
    resource = data/'examples.json'; resource.write_bytes(b'{"value": 1}\n')
    first = package_fingerprint(tmp_path)
    resource.write_bytes(b'{"value": 2}\r\n')
    second = package_fingerprint(tmp_path)
    assert second != first
    resource.write_bytes(b'{"value": 2}\n')
    assert package_fingerprint(tmp_path) == second


def test_generated_gallery_matches_canonical_source_when_available():
    source = Path(__file__).resolve().parents[1]/'examples'
    data = json.loads(resources.files('spinfreq').joinpath('data', 'examples.json').read_text())
    for name, metadata in RECIPES.items():
        assert data['examples'][name] == json.loads((source/metadata['source']).read_text())
