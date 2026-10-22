@echo off
setlocal
pushd "%~dp0.."
if not exist ".venv\Scripts\spinfreq-web.exe" goto missing
echo Open http://127.0.0.1:8000 in your browser once the server says it is running.
echo Windows opens in configuration preview. Use Run-Demo.cmd for a local CPU simulation.
echo Press Ctrl+C to stop the server.
".venv\Scripts\spinfreq-web.exe"
if errorlevel 1 goto failed
popd
exit /b 0
:missing
echo Run windows\Install.cmd first.
:failed
echo The browser server did not start successfully; inspect the message above.
pause
popd
exit /b 1
