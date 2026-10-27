"""Installed, offline experiment templates and portable guided project runners."""
import argparse
import hashlib
from importlib import resources
from importlib.metadata import version
import json
from pathlib import Path
import shlex
import sys

from .config import JobConfig
from .studies import StudyConfig


RECIPES = {
    'prism-fmr': {'source': 'prism-fmr.json', 'kind': 'job',
                  'description': 'First experiment: a single-cell magnetic prism.',
                  'scope': 'Analytical Gilbert response; no resolved spatial modes.'},
    'periodic-fmr': {'source': 'periodic-fmr.json', 'kind': 'job',
                     'description': 'A repeating thin film under a weak oscillating field.',
                     'scope': 'Periodic boundaries; the uniform resonance has an analytical reference.'},
    'confined-skyrmion': {'source': 'confined-skyrmion.json', 'kind': 'job',
                         'description': 'A confined skyrmion and its weak-field resonances.',
                         'scope': 'Coarse 2 nm matched OOMMF model; refine the mesh for continuum values.'},
    'localized-source': {'source': 'spectroscopy/localized-source.json', 'kind': 'job',
                        'description': 'Place a Gaussian source and measure local detectors.',
                        'scope': 'Linear periodic film; probe amplitudes differ from total absorbed power.'},
    'wavevector-probe': {'source': 'spectroscopy/wavevector-probe.json', 'kind': 'job',
                        'description': 'Select a wavevector with a complex polarized field.',
                        'scope': 'Periodic plane-wave source and Fourier probes; wavevector in rad/m.'},
    'fmr-field-sweep': {'source': 'studies/fmr-field-sweep.json', 'kind': 'study',
                       'description': 'Follow the uniform resonance as the static field changes.',
                       'scope': 'Six single-cell cases with equilibrium continuation.'},
    'fmr-damping-sweep': {'source': 'studies/fmr-damping-sweep.json', 'kind': 'study',
                         'description': 'Compare resonance linewidths for three damping values.',
                         'scope': 'Three independent single-cell cases; linear Gilbert damping.'},
    'skyrmion-field-path': {'source': 'studies/skyrmion-field-path.json', 'kind': 'study',
                            'description': 'Continue a confined skyrmion through three bias fields.',
                            'scope': 'Coarse 2 nm model; continuation does not establish global ground state or mesh convergence.'},
}


def _example(name):
    if name not in RECIPES:
        raise ValueError('Unknown example; use spinfreq-examples --list')
    data = json.loads(resources.files('spinfreq').joinpath('data', 'examples.json').read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('examples'), dict)
            or set(data['examples']) != set(RECIPES)):
        raise ValueError('Example gallery is incomplete; reinstall the package')
    config = data['examples'][name]
    model = (JobConfig if RECIPES[name]['kind'] == 'job' else StudyConfig).from_dict(config)
    return config, model


def list_examples():
    """List bundled templates with kind, scope, mesh and case count."""
    records = []
    for name, metadata in RECIPES.items():
        _, config = _example(name)
        base = config if metadata['kind'] == 'job' else config.base
        records.append({'name': name, **metadata, 'nx': base.nx, 'ny': base.ny,
                        'case_count': 1 if metadata['kind'] == 'job' else len(config.cases())})
    return records


def _command(arguments, windows=None):
    """Display commands, never execute a shell; PowerShell quoting is explicit."""
    windows = sys.platform == 'win32' if windows is None else windows
    if windows:
        return '& '+' '.join("'"+str(value).replace("'", "''")+"'" for value in arguments)
    return shlex.join([str(value) for value in arguments])


def create_example(name, output):
    """Create a new editable experiment folder; no calculation or overwrites."""
    data, config = _example(name)
    output = Path(output)
    metadata = RECIPES[name]
    kind = metadata['kind']
    filename = 'configuration.json' if kind == 'job' else 'study.json'
    count = 1 if kind == 'job' else len(config.cases())
    encoded = json.dumps(data, indent=2, allow_nan=False)+'\n'
    runner = f'''"""Run this experiment using the Python environment with SpinFreq installed."""
from pathlib import Path
from spinfreq.bundled_examples import run_example_main

if __name__ == '__main__':
    run_example_main(Path(__file__).resolve().parent, kind={kind!r})
'''
    image = 'spectrum.png' if kind == 'job' else 'spectra.png'
    folder = 'run' if kind == 'job' else 'study'
    readme = f'''# {name}

{metadata['description']}

## Before you run

Edit **{filename}** to change this experiment. Values are SI: metres, hertz,
tesla and material units described in the installed manual. This is a
**{kind}** with **{count}** case(s). {metadata['scope']}
All cases use one magnetization through the film thickness and linear weak-field
response. CPU calculations use your computer; a GPU or web server is not required.

## Run from your SpinFreq Python environment

The creation command prints an exact command for your installed Python. Use it,
or open a terminal in this experiment folder and run with that same environment:

```text
python run.py --check
python run.py
```

`--check` validates the edited configuration and reports the mesh and case count;
it does not run a simulation or create results. If Python cannot import SpinFreq,
replace `python` with the full path of the environment used for installation.
For Windows PowerShell, use `& 'C:\\path to\\.venv\\Scripts\\python.exe' run.py`.
For Linux/macOS, use `/path/to/.venv/bin/python run.py`.

The runner locates this folder independently of the terminal's current directory.
By default, results go into **results/{folder}/** next to this README.
Open **results/{folder}/{image}** first, then inspect numerical status and
residuals before interpreting peaks. Keep input files and result archives.

Existing results are preserved. For another run, choose a fresh directory:

```text
python run.py --output results/second-run
```

Relative output paths are resolved from this experiment folder. Study cases have
individual subfolders; aggregate `cases.csv`, `poles.csv` and `study.json` describe
successes and failures. A study file must be run with `spinfreq-study`, not
`spinfreq --config`. A single job can also be run with
`spinfreq --config configuration.json --output results/another-run`.

## Reproduce and extend

**experiment.json** records the original template, package version and hashes of
the generated starter files. Editing the configuration is expected: those hashes
identify the starting point, not a lock on your changes. Simulation results record
the configuration actually executed. Refine mesh/frequency sampling and compare
an independent reference before making a research claim.

After a single job, `spinfreq-susceptibility --job results/run --output results/tensor`
compares field polarizations. After a suitable one-axis fixed-mesh study,
`spinfreq-track --study results/study --output results/tracking` follows mode shapes.
See the installed handbook through `spinfreq-web --mode landing` at
http://127.0.0.1:8000/start.html. Browser preview does not require a computation worker.
'''
    contents = {filename: encoded, 'run.py': runner, 'README.md': readme}
    manifest = {'schema_version': 1, 'template': name, 'kind': kind,
                'package_version': version('spinfreq'), 'case_count': count,
                'configuration_file': filename, 'source_example': metadata['source'],
                'template_sha256': hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                'starter_files_sha256': {key: hashlib.sha256(text.encode('utf-8')).hexdigest() for key, text in contents.items()}}
    output.mkdir(parents=True, exist_ok=False)
    for filename, text in {**contents, 'experiment.json': json.dumps(manifest, indent=2)+'\n'}.items():
        # Write bytes so starter-file hashes are identical on Windows and Unix.
        with (output/filename).open('xb') as stream:
            stream.write(text.encode('utf-8'))
    return manifest


def run_example_main(directory, *, kind):
    """Entry used by generated run.py; validates edited input before execution."""
    from .jobs import run_job
    from .studies import run_study
    parser = argparse.ArgumentParser(description='Run or check this local CPU experiment')
    parser.add_argument('--check', action='store_true', help='Validate without calculating or creating results')
    parser.add_argument('--output', type=Path, help='New results directory; relative to the experiment folder')
    args = parser.parse_args()
    directory = Path(directory).resolve()
    if kind not in ('job', 'study'):
        parser.error('Unknown experiment kind')
    try:
        config = (JobConfig if kind == 'job' else StudyConfig).load(directory/('configuration.json' if kind == 'job' else 'study.json'))
        base = config if kind == 'job' else config.base
        count = 1 if kind == 'job' else len(config.cases())
        print(f'Validated {kind}: {base.nx} x {base.ny} cells, {count} case(s).', flush=True)
        if args.check:
            print('No calculation performed. Run without --check to calculate.')
            return
        output = args.output or Path('results')/('run' if kind == 'job' else 'study')
        if not output.is_absolute():
            output = directory/output
        print(f'Calculating on CPU. Results: {output}', flush=True)
        if kind == 'job':
            run_job(config, output, progress=lambda stage: print(stage, flush=True))
        else:
            result = run_study(config, output)
            if result['status'] != 'succeeded':
                raise RuntimeError('Study did not complete; inspect study.json and case summaries')
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        parser.exit(1, f'Experiment stopped: {error}\nUse a fresh output directory and keep failure diagnostics.\n')
    print(f"Done. Open {output/('spectrum.png' if kind == 'job' else 'spectra.png')}")


def main():
    parser = argparse.ArgumentParser(description='Create editable experiments from the installed offline example gallery')
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--list', action='store_true', help='List available experiments and their scope')
    choice.add_argument('--name', choices=list(RECIPES), help='Example to copy; no simulation runs yet')
    parser.add_argument('--output', type=Path, help='New experiment folder (must not exist)')
    args = parser.parse_args()
    if args.list:
        if args.output:
            parser.error('--output is used with --name')
        for record in list_examples():
            print(f"{record['name']} [{record['kind']}, {record['case_count']} case(s), {record['nx']} x {record['ny']} cells]")
            print(f"  {record['description']} {record['scope']}")
        return
    if args.output is None:
        parser.error('--output is required with --name')
    try:
        manifest = create_example(args.name, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Example not created: {error}\nChoose a new output folder.\n')
    runner = (args.output/'run.py').resolve()
    print(f"Created {manifest['kind']}: {args.output.resolve()}")
    print(f"Edit {manifest['configuration_file']}; {manifest['case_count']} case(s). No calculation performed.")
    print('Check: '+_command([sys.executable, runner, '--check']))
    print('Run:   '+_command([sys.executable, runner]))
