@echo off
setlocal
pushd "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
for %%V in (3.12 3.13 3.11) do (
  py -%%V -c "import sys; sys.exit(0 if sys.maxsize > 2**32 else 1)" >nul 2>nul
  if not errorlevel 1 (
    py -%%V install.py
    if errorlevel 1 goto failed
    goto success
  )
)
:use_python
python install.py
if errorlevel 1 goto failed
:success
echo Ready. Double-click Run-Demo.cmd to calculate or Open-Web.cmd for preview.
if /I not "%~1"=="--ci" pause
popd
exit /b 0
:failed
echo Setup did not finish. Read the error above and INSTALL.md.
echo Use 64-bit Python 3.11, 3.12 or 3.13 from https://www.python.org/downloads/windows/
if /I not "%~1"=="--ci" pause
popd
exit /b 1
