# Install and launch

Python 3.11–3.13 is supported by the package configuration. Clone the repository
and open a terminal in its root before running these commands.

## Windows · PowerShell

No Linux subsystem is required to launch the landing/configuration preview:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[web]'
.\.venv\Scripts\spinfreq-web.exe
```

Open **http://127.0.0.1:8000**. Explore the project, open the workbench, select an
example, edit parameters and export its validated SI JSON. By default, simulation buttons
are disabled on native Windows. No Linux worker or job directory is initialized.
The native-Windows import/HTTP regression is configured in CI; this workspace
runs Linux, so a local Windows execution is not claimed.

To run the protected web simulation queue on a Windows computer, install WSL2
with a Linux distribution and follow the Linux instructions inside that
Linux environment. The calculations then use that computer's resources through
WSL2. Alternatively, 64-bit native Windows has an experimental opt-in:

```powershell
.\.venv\Scripts\spinfreq-web.exe --mode compute
```

This uses Windows Job Objects for memory/CPU limits and process-tree cleanup.
It is not enabled automatically: native lifecycle/resource CI must pass before
Windows becomes a qualified compute platform. See the
[Windows backend and qualification guide](../development/WINDOWS.md).

## Linux / WSL2 · shell

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[web]'
.venv/bin/spinfreq-web
```

Open the same URL. Linux enables the local simulation queue automatically. Choose
an example and run; inspect numerical status and download plots, fields and data.

## macOS · shell

Use the Linux installation commands to launch the portable landing/configuration
preview. The protected Linux worker is not enabled natively. macOS execution has
not been verified in this workspace.

## Choose a mode

```bash
spinfreq-web --mode auto      # Linux computes; Windows/macOS preview
spinfreq-web --mode landing   # Preview only on every platform
spinfreq-web --mode compute   # Linux or experimental native Windows
```

After exporting `spinfreq-config.json`, use it on a Linux compute installation:

```bash
spinfreq --config spinfreq-config.json --output results/my-film
```

Use a fresh output directory. For complete limits, job lifecycle and
troubleshooting, continue to the [web guide](../guides/WEB.md). For direct Python
calls, see the [user guide](../guides/USAGE.md).
