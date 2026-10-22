# Your first SpinFreq simulation

Start with one small CPU calculation, learn what its plots mean, then move to
films, skyrmions and research studies. No GPU, MuMax3 or Linux subsystem is
required for this local demo. The current source candidate uses **64-bit
Python 3.11, 3.12 or 3.13**; it is not yet a standalone application installer.

## 1. Get the source

[Download the source ZIP](https://github.com/spinuni/spinfreq/archive/refs/heads/main.zip)
and extract it into a writable folder such as Documents. Git users can run:

```bash
git clone https://github.com/spinuni/spinfreq.git
cd spinfreq
```

The ZIP/main branch is a moving development snapshot. Keep the source revision
with research results. Installation downloads Python dependencies from the
package index; subsequent demo calculations run locally.

## 2. Install on Windows

Install 64-bit Python 3.11–3.13 from [python.org](https://www.python.org/downloads/windows/).
Open the extracted repository's `windows` folder, double-click **Install.cmd**
and wait for the CPU self-check to pass. Then double-click **Run-Demo.cmd**.
The helper scripts create and use a `.venv` inside this checkout and leave
previous results intact. They do not change PowerShell execution policy.

If you prefer a PowerShell terminal, open it in the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[web]"
.\.venv\Scripts\spinfreq-doctor.exe --check
.\.venv\Scripts\spinfreq-demo.exe --open
```

These commands run a native Windows **CPU** simulation. They use the numerical
Python package directly. The optional protected browser queue has separate
platform controls, described below. See [Windows helpers](../../windows/README.md)
for troubleshooting and current qualification status.

## 2. Install on Linux or macOS

Open a terminal in the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/spinfreq-doctor --check
.venv/bin/spinfreq-demo --open
```

Omit `--open` on a remote/headless machine and open the saved image manually.
The self-check exercises the installed CPU eigensolver against analytical FMR.
Native Windows/macOS CI checks are configured; this Linux workspace does not
establish that they have passed on those hosts.

## Your first result

The demo finds the resting magnetization, calculates natural modes and sweeps
an oscillating field. It prints progress and a results path such as
`results/first-simulation`. Later demos use `first-simulation-2`, and so on.

| Open this file | What it tells you |
| --- | --- |
| `spectrum.png` | Absorbed power versus frequency; peaks indicate strong response to the chosen drive |
| `equilibrium.png` | Magnetization at rest; this one-cell example has no spatial texture |
| `mode.png` | A mode's amplitude pattern; a single cell is deliberately simple |
| `summary.json` | Numerical status, residuals, units and versions |
| `configuration.json` / `results.zip` | Reproducible input and complete portable result bundle |

A **mode** is a spatial pattern of magnetic motion. A **resonance** is a strong
response to a particular excitation. The excitation and detector determine
which modes are visible. **FMR** means ferromagnetic resonance. A **skyrmion**
is a nonuniform magnetic texture; its existence and stability must be checked.

The demo is a single-cell rectangular prism, useful for learning and analytical
checks. It does not represent a spatially resolved device. Frequency is plotted
in GHz; JSON uses SI units such as metres, hertz and tesla.

## 3. Try another example

In Windows PowerShell, from the repository root:

```powershell
.\.venv\Scripts\spinfreq.exe --preset periodic-fmr --output results/my-film
.\.venv\Scripts\spinfreq.exe --preset confined-skyrmion --output results/my-skyrmion
```

On Linux/macOS:

```bash
.venv/bin/spinfreq --preset periodic-fmr --output results/my-film
.venv/bin/spinfreq --preset confined-skyrmion --output results/my-skyrmion
```

Use a fresh output directory. For a skyrmion, inspect the equilibrium and
numerical status before interpreting peaks; the preset is a coarse 2 nm matched
reference problem and needs mesh refinement for continuum accuracy.

Choose a path: [example gallery](../../examples/README.md),
[local source/detector](../guides/SPECTROSCOPY.md),
[parameter studies](../guides/RESEARCH.md), or
[mode matching](../guides/MODE_TRACKING.md). The [manual](../handbook/manual.md)
and [theory](../handbook/theory.md) explain the full workflow and assumptions.

To compare x/y/z field polarizations after a simulation, follow the
[tensor tutorial](../guides/SUSCEPTIBILITY.md). It includes Windows commands
and explains which output image to open first.

## Optional browser interface

Install `.[web]` from the checkout, then run `spinfreq-web` and open
**http://127.0.0.1:8000**. On Windows, **Open-Web.cmd** starts it after installation.
Your browser displays the interface; calculations use the machine running Python.

| Platform | Local CPU commands | Protected browser queue |
| --- | --- | --- |
| Linux / WSL2 | Available | Enabled automatically |
| Windows | Native Python calculation path; verify with doctor/demo | Preview by default; experimental `--mode compute` |
| macOS | Python calculation path; verify with doctor/demo | Preview only |

A Windows preview does not mean all Windows computation is disabled. The demo
and command-line simulations are separate from the protected browser worker.
Native Windows worker qualification remains pending; it is not enabled by
default. Continue to the [web guide](../guides/WEB.md) when you need that interface.

## If something goes wrong

- **Python command is missing:** install the supported 64-bit Python and enable
  its launcher/PATH option. On Windows, try `py -3 --version`.
- **A dependency fails to install:** check Python version and internet access;
  keep the terminal error. Use a clean `.venv` with a supported Python.
- **The image does not open:** find `spectrum.png` in the printed results folder.
- **An output directory is occupied:** choose a new `--output` path. The demo
  allocates a new folder automatically.
- **A numerical calculation stops:** inspect `summary.json`; report the full
  configuration and `spinfreq-doctor --check` output with the error.

For research, retain data and versions, perform mesh/solver convergence and
compare an independent reference. A passing demo is a first installation check.
