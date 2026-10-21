# Native Windows computation: experimental opt-in

The web can attempt simulations on **64-bit native Windows** with:

```powershell
.\.venv\Scripts\spinfreq-web.exe --mode compute
```

Automatic startup still selects preview on Windows. The implementation is
experimental until the native CI suite passes and its results are reviewed.
This workspace runs Linux; no native Windows execution is claimed here.
Linux/WSL2 remains the locally qualified compute path. macOS retains preview.

## Execution contract

The same `JobConfig`, numerical solver, residual/stability checks and artifacts
are used on both systems. Platform runtime code lives under `spinfreq/runtime/`.
No new Python dependency is required for Windows: ctypes calls the OS APIs.

| Control | Linux | Experimental Windows |
| --- | --- | --- |
| Exclusive data-directory owner | `flock` | Nonblocking `msvcrt` byte-range lease |
| Startup | Worker applies rlimits and parent-death signal | Interpreter waits at stdin gate until server assigns a configured Job Object |
| Memory | 2 GiB virtual address space | 2 GiB committed memory per process and aggregate job |
| CPU | 60 s user+kernel CPU per process, 61 s hard | 60 s aggregate Job Object user CPU |
| Wall time | Worker alarm plus 120 s supervisor bound | 120 s supervisor bound |
| Per-file / aggregate disk | 32 MiB hard file rlimit plus polling / 96 MiB polling | 32 MiB file / 96 MiB total, both polled every 0.1 s |
| Cancellation | Kill process group | Terminate complete Job Object |
| Owner death | Linux parent-death signal | Non-inheritable Job Object handle closes; kill-on-close terminates the job |
| Completion | Clean remaining process group | Close Job Object to remove descendants |

Committed memory, virtual address space and physical RSS are different quantities.
Windows CPU enforcement counts user time, not kernel time. Disk monitoring is
periodic and permits a transient overshoot; it is not a Windows filesystem quota.
The bounded configuration and fixed artifact set are additional size controls.
The backend is for trusted local research calculations, not hostile code isolation.

Windows numerical imports occur only after successful job assignment. If native
API setup/assignment fails, the gated process is killed; no unbounded fallback
exists. A Job Object handle is owned only by the server and is not inherited by
workers. Windows versions/hosts that prohibit nested job assignment fail closed.
Atomic JSON writes retry brief Windows sharing violations within a bounded time.

## Native qualification procedure

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[test,web,web-test]'
.\.venv\Scripts\python.exe -m pytest -q tests/test_runtime.py tests/test_web.py tests/test_portable_web.py
.\.venv\Scripts\spinfreq-web.exe --mode compute --port 8000
# Another terminal, after installing a Chromium browser:
.\.venv\Scripts\python.exe scripts/browser_smoke.py --url http://127.0.0.1:8000
```

The platform CI matrix runs real Job Object tests on `windows-latest`, including
memory-allocation refusal, CPU termination, failed-assignment gating, descendant
cancellation and normal completion, exclusive ownership, timeout, disk limits, server crash/restart and
real numerical jobs. These native-only tests are explicitly skipped on Linux.
Native Chromium CI also submits through the UI and inspects downloaded results,
recording the server platform and worker runtime. Observe those native results
before changing Windows auto mode or claiming parity.
The [evidence ledger](../../validation/release_candidate/windows/README.md) keeps
implementation and qualification separate.

## Installed-wheel evidence bundle

Use the [platform evidence collector](../releases/PLATFORM_EVIDENCE.md) for a
single-command native run and a standalone verifier. The platform CI now tests
the exact installed wheel and uploads `platform-qualification-win32`, including
JUnit cases, checksummed artifacts, source revision and server-session binding.
The checker rejects skipped native tests and Linux bundles presented as Windows.
