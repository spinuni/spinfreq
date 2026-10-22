# SpinFreq on Windows

You can run CPU simulations using native Windows Python. The browser's default
preview mode is separate from these local numerical commands.

1. Install **64-bit Python 3.11–3.13** from [python.org](https://www.python.org/downloads/windows/).
2. Download/extract the repository ZIP into a writable folder.
3. Double-click **Install.cmd** in this folder. It creates the repository's
   `.venv`, installs SpinFreq plus optional browser dependencies, and runs a CPU
   self-check. Internet access is needed during installation.
4. Double-click **Run-Demo.cmd**. It runs a small simulation, prints the results
   directory, and opens `spectrum.png`. Repeated runs keep earlier results.

**Open-Web.cmd** starts the optional local interface; open the printed URL.
On Windows it starts in preview. Explicit `--mode compute` is experimental and
requires native worker qualification before becoming the default. Direct CLI
and Python calculations use the numerical package without that supervisor.

The helpers are source-install scripts, not a signed standalone `.exe` bundle.
They do not require WSL2, a GPU, administrator installation or changes to
PowerShell execution policy. Native Windows CI is configured; successful Linux
checks do not establish native Windows execution evidence.

Terminal equivalent, from the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[web]"
.\.venv\Scripts\spinfreq-doctor.exe --check
.\.venv\Scripts\spinfreq-demo.exe --open
```

Follow the [first-result tutorial](../docs/getting-started/README.md) to interpret
outputs, then the [examples](../examples/README.md). For an error, retain the
terminal message and doctor output. `Install.cmd --ci` and `Run-Demo.cmd --ci`
disable interactive pauses/browser opening for CI checks only.
