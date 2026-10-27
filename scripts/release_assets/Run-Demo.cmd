@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\spinfreq-demo.exe" goto missing
if /I "%~1"=="--ci" goto ci
".venv\Scripts\spinfreq-demo.exe" --open
goto finished
:ci
".venv\Scripts\spinfreq-demo.exe"
:finished
if errorlevel 1 goto failed
if /I not "%~1"=="--ci" pause
popd
exit /b 0
:missing
echo Run Install.cmd in this candidate folder first.
:failed
if /I not "%~1"=="--ci" pause
popd
exit /b 1
