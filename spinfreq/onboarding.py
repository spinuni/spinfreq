"""Small, portable first-run commands; no browser/server dependency."""
import argparse
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
import math
from pathlib import Path
import platform
import struct
import sys
import webbrowser

import numpy as np

from .config import presets
from .jobs import run_job
from .model import Film, MU0


def cpu_self_check():
    """Exercise the installed eigensolver against perpendicular Gilbert FMR."""
    config = replace(presets()["periodic-fmr"], nx=1, ny=1)
    film = Film(nx=1, ny=1, dx=config.dx_m, thickness=config.thickness_m,
                material=config.material, field_T=config.field_T)
    m = np.array([[[0., 0., 1.]]])
    f = max(film.modes(m).frequencies_Hz)
    p = config.material
    expected = p.gamma/(1+p.alpha**2)*(config.field_T[2]+2*p.K/p.Ms-MU0*p.Ms)/(2*np.pi)
    error = float(abs(f/expected-1))
    if not math.isfinite(error) or error > 1e-10:
        raise RuntimeError(f"CPU frequency self-check failed: relative error {error:g}")
    return error


def doctor_main():
    parser = argparse.ArgumentParser(description="Check your local SpinFreq installation")
    parser.add_argument("--check", action="store_true", help="Also execute a small analytical CPU check")
    args = parser.parse_args()
    print(f"SpinFreq {version('spinfreq')}")
    print(f"Python {platform.python_version()} ({struct.calcsize('P')*8}-bit), {platform.system()} {platform.machine()}")
    for name in ("numpy", "scipy", "matplotlib"):
        try:
            print(f"{name}: {version(name)}")
        except PackageNotFoundError:
            parser.exit(1, f"Missing dependency: {name}. Reinstall from the installation guide.\n")
    web = find_spec("fastapi") is not None and find_spec("uvicorn") is not None
    print("Browser interface: " + ("installed" if web else "optional dependencies absent; the CPU commands still work"))
    if sys.platform == "win32":
        print("Windows: local CPU commands available; browser starts in preview.")
        print("Protected native browser computation requires experimental --mode compute; qualification is pending.")
    elif sys.platform.startswith("linux"):
        print("Linux: local CPU commands and protected browser computation available.")
    else:
        print("Local CPU commands available when dependencies work; protected browser computation is unavailable.")
    print("GPU backend: not implemented; calculations use CPU NumPy/SciPy.")
    if args.check:
        try:
            error = cpu_self_check()
        except (ValueError, RuntimeError, OSError) as error:
            parser.exit(1, f"Self-check failed: {error}\n")
        print(f"CPU analytical self-check: passed (relative error {error:.2g}).")
    print("Next: run spinfreq-demo for your first spectrum.")


def _new_demo_directory(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 10001):
        candidate = root/("first-simulation" if index == 1 else f"first-simulation-{index}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError("Too many demo directories; choose --output explicitly")


def demo_main():
    parser = argparse.ArgumentParser(description="Run a small local CPU simulation and explain the results")
    parser.add_argument("--output", type=Path, help="Empty output directory; default allocates a new results/first-simulation folder")
    parser.add_argument("--open", action="store_true", help="Open the spectrum with your default browser after success")
    args = parser.parse_args()
    print("Your first SpinFreq simulation: a one-cell magnetic prism.")
    print("This uses your computer's CPU. No GPU, web server or Linux subsystem is required.")
    stages = {"relaxation": "1/4 Finding the resting magnetization...",
              "eigenmodes": "2/4 Finding natural frequencies...",
              "frequency response": "3/4 Calculating response to a weak oscillating field...",
              "plots and exports": "4/4 Saving plots and reproducible data..."}
    try:
        output = args.output if args.output is not None else _new_demo_directory(Path.cwd()/"results")
        result = run_job(presets()["prism-fmr"], output,
                         progress=lambda stage: print(stages[stage], flush=True) if stage in stages else None)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f"Simulation stopped: {error}\nUse a new --output directory and inspect summary.json if available.\n")
    print(f"Done. Numerical status: {result['stability']}.")
    print(f"Results: {output.resolve()}")
    print("Open spectrum.png: the horizontal axis is frequency; peaks show strong absorption.")
    print("Open equilibrium.png: the magnetization at rest. This one-cell example has no spatial texture.")
    print("Keep configuration.json and results.zip to reproduce or share the calculation.")
    if args.open:
        try:
            opened = webbrowser.open((output/"spectrum.png").resolve().as_uri())
        except (webbrowser.Error, OSError):
            opened = False
        if not opened:
            print("The browser did not open automatically. Open spectrum.png from the results folder.")
    print("Next: run spinfreq-examples --list, then create an editable experiment with --name and --output.")
