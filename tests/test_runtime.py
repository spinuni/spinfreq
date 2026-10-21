"""Runtime ABI checks plus real Windows resource/process-tree tests in CI."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from spinfreq.runtime.windows import BasicLimits, ExtendedLimits, BOOTSTRAP, is_process_running


def test_job_object_abi_uses_windows_integer_widths():
    # These structures have fixed Win32 DWORD widths even on LP64 Linux.
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(BasicLimits) == 64
        assert ctypes.sizeof(ExtendedLimits) == 144
        assert ExtendedLimits.job_memory.offset == 120


def test_startup_gate_requires_owner_token_and_preserves_standard_input():
    command = [sys.executable, '-c', BOOTSTRAP, '-c',
               "import os;os.fstat(0);print('PAYLOAD_EXECUTED')"]
    for token, allowed in [(b'', False), (b'1', True)]:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(token, timeout=10)
        assert (process.returncode == 0) is allowed, stderr
        assert (b'PAYLOAD_EXECUTED' in stdout) is allowed


windows = pytest.mark.skipif(sys.platform != 'win32', reason='Requires real Windows Job Objects')


@windows
def test_windows_memory_limit_rejects_large_allocation(tmp_path):
    from spinfreq.runtime.windows import WindowsRuntime
    runtime = WindowsRuntime(memory_bytes=128*1024**2)
    with (tmp_path/'worker.log').open('wb') as log:
        process = runtime.start([sys.executable, '-c', 'bytearray(512*1024**2)'], log, dict(os.environ))
        try:
            assert process.wait(timeout=15) != 0
        finally:
            runtime.terminate(process)
    assert b'MemoryError' in (tmp_path/'worker.log').read_bytes()


@windows
def test_windows_cpu_limit_terminates_busy_worker(tmp_path):
    from spinfreq.runtime.windows import WindowsRuntime
    runtime = WindowsRuntime(user_cpu_s=1)
    with (tmp_path/'worker.log').open('wb') as log:
        process = runtime.start([sys.executable, '-c', 'while True: pass'], log, dict(os.environ))
        try:
            assert process.wait(timeout=15) != 0
        finally:
            runtime.terminate(process)


@windows
@pytest.mark.parametrize('action', ['cancel', 'complete'])
def test_windows_cancellation_and_completion_remove_descendants(tmp_path, action):
    from spinfreq.runtime.windows import WindowsRuntime
    runtime = WindowsRuntime()
    pidfile = tmp_path/'child.json'
    code = '''import subprocess,sys,json,time
from pathlib import Path
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(50)'])
Path(sys.argv[1]).write_text(json.dumps({'pid':p.pid}))
if sys.argv[2]=='cancel': time.sleep(50)
'''
    with (tmp_path/'worker.log').open('wb') as log:
        process = runtime.start([sys.executable, '-c', code, str(pidfile), action], log, dict(os.environ))
        try:
            deadline = time.monotonic()+15
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(.03)
            assert pidfile.exists()
            child = json.loads(pidfile.read_text())['pid']
            assert is_process_running(child)
            if action == 'cancel':
                runtime.terminate(process)
            else:
                assert process.wait(timeout=5) == 0
                runtime.release(process)
            deadline = time.monotonic()+5
            while is_process_running(child) and time.monotonic() < deadline:
                time.sleep(.03)
            assert not is_process_running(child)
        finally:
            runtime.terminate(process)


@windows
def test_windows_failed_assignment_never_releases_gate(tmp_path, monkeypatch):
    from spinfreq.runtime.windows import WindowsRuntime
    runtime = WindowsRuntime()
    marker = tmp_path/'must-not-exist'
    # Force assignment failure after spawning a gated interpreter.
    monkeypatch.setattr(runtime.api, 'AssignProcessToJobObject', lambda *args: 0)
    with (tmp_path/'worker.log').open('wb') as log:
        with pytest.raises(OSError):
            runtime.start([sys.executable, '-c', 'from pathlib import Path;Path(__import__("sys").argv[1]).touch()', str(marker)],
                          log, dict(os.environ))
    assert not marker.exists()
