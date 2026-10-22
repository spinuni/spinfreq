@echo off
setlocal
pushd "%~dp0.."
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if errorlevel 1 goto use_python
for %%V in (3.12 3.13 3.11) do (
  py -%%V -c "import sys; sys.exit(0 if sys.maxsize > 2**32 else 1)" >nul 2>nul
  if not errorlevel 1 (
    py -%%V -m venv .venv
    if errorlevel 1 goto failed
    goto install
  )
)
goto use_python
:use_python
python -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) and sys.maxsize > 2**32 else 1)"
if errorlevel 1 goto python_error
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) and sys.maxsize > 2**32 else 1)"
if errorlevel 1 goto python_error
echo Installing SpinFreq and its optional browser interface in this checkout's .venv...
".venv\Scripts\python.exe" -m pip install -e ".[web]"
if errorlevel 1 goto failed
".venv\Scripts\spinfreq-doctor.exe" --check
if errorlevel 1 goto failed
echo Ready. Double-click windows\Run-Demo.cmd to run your first CPU simulation.
if /I not "%~1"=="--ci" pause
popd
exit /b 0
:python_error
echo Install 64-bit Python 3.11, 3.12 or 3.13 from https://www.python.org/downloads/windows/
echo Enable the Python launcher or add Python to PATH, then run this installer again.
:failed
echo Setup did not finish. Read the error above or docs\getting-started\README.md.
if /I not "%~1"=="--ci" pause
popd
exit /b 1
