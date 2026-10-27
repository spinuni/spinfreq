@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\spinfreq-web.exe" goto missing
echo Open http://127.0.0.1:8000 after the server starts.
echo This is configuration preview. Use Run-Demo.cmd for a local CPU simulation.
echo Press Ctrl+C to stop the server.
".venv\Scripts\spinfreq-web.exe" --mode landing
if errorlevel 1 goto failed
popd
exit /b 0
:missing
echo Run Install.cmd in this candidate folder first.
:failed
pause
popd
exit /b 1
