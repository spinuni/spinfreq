"""Windows Job Objects. No Win32 APIs are loaded when imported elsewhere.

Workers wait on a private stdin gate until assigned to a configured job. Only
the server owns the non-inheritable job handle: its closure/crash kills the job.
Memory limits bound committed memory, not Linux virtual address space.
"""
import ctypes as C
import subprocess
import sys


DWORD = C.c_uint32
SIZE_T = C.c_size_t
HANDLE = C.c_void_p


class BasicLimits(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64), ('flags', DWORD),
                ('min_working_set', SIZE_T), ('max_working_set', SIZE_T),
                ('active_process_limit', DWORD), ('affinity', SIZE_T),
                ('priority_class', DWORD), ('scheduling_class', DWORD)]


class IOCounters(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in
                ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class ExtendedLimits(C.Structure):
    _fields_ = [('basic', BasicLimits), ('io', IOCounters), ('process_memory', SIZE_T),
                ('job_memory', SIZE_T), ('peak_process_memory', SIZE_T), ('peak_job_memory', SIZE_T)]


def kernel32():
    if sys.platform != 'win32':
        raise RuntimeError('Windows Job Objects require native Windows')
    api = C.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([C.c_void_p, C.c_wchar_p], HANDLE),
        'SetInformationJobObject': ([HANDLE, C.c_int, C.c_void_p, DWORD], C.c_int),
        'AssignProcessToJobObject': ([HANDLE, HANDLE], C.c_int),
        'TerminateJobObject': ([HANDLE, C.c_uint], C.c_int),
        'CloseHandle': ([HANDLE], C.c_int),
        'OpenProcess': ([DWORD, C.c_int, DWORD], HANDLE),
        'WaitForSingleObject': ([HANDLE, DWORD], DWORD),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes = arguments
        function.restype = result
    return api


def checked(result):
    if not result:
        raise C.WinError(C.get_last_error())
    return result


def is_process_running(pid):
    api = kernel32()
    handle = api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        if C.get_last_error() == 87:  # no such PID
            return False
        raise C.WinError(C.get_last_error())
    try:
        result = api.WaitForSingleObject(handle, 0)
        if result == 0xffffffff:
            raise C.WinError(C.get_last_error())
        return result == 258  # WAIT_TIMEOUT
    finally:
        api.CloseHandle(handle)


class WindowsProcess:
    def __init__(self, process, job, api):
        self.process, self.job, self.api = process, job, api
        self.pid = process.pid

    @property
    def returncode(self):
        return self.process.returncode

    def poll(self):
        return self.process.poll()

    def wait(self, timeout=None):
        return self.process.wait(timeout=timeout)

    def close_job(self):
        if self.job:
            checked(self.api.CloseHandle(self.job))
            self.job = None


# Imports of the simulator (and numerical libraries) happen only after assignment.
BOOTSTRAP = '''import sys
if sys.stdin.buffer.read(1) != b'1': raise SystemExit('Worker owner closed the startup gate')
# Keep the read handle valid at EOF: Windows descendants duplicate GetStdHandle.
args=sys.argv[1:]
if args[0]=='-m':
 import runpy
 sys.argv=args[1:]
 runpy.run_module(args[1],run_name='__main__',alter_sys=True)
elif args[0]=='-c':
 sys.argv=['-c',*args[2:]]
 exec(compile(args[1],'<bounded-worker>','exec'),{'__name__':'__main__'})
else: raise SystemExit('Unsupported worker entry point')
'''


class WindowsRuntime:
    name = 'windows-job-object-experimental'

    def __init__(self, memory_bytes=2*1024**3, user_cpu_s=60):
        if C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('The Windows worker requires 64-bit Python')
        self.api = kernel32()
        self.memory_bytes = memory_bytes
        self.user_cpu_s = user_cpu_s

    def acquire(self, path):
        import msvcrt
        lease = path.open('a+b')
        try:
            if lease.seek(0, 2) == 0:
                lease.write(b'\0'); lease.flush()
            lease.seek(0)
            msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            lease.close()
            raise RuntimeError('Data directory already has a supervisor; use one server process') from None
        return lease

    def start(self, command, log, environment):
        if command[0] != sys.executable or command[1] not in ('-m', '-c'):
            raise ValueError('Only the current Python interpreter can start a bounded worker')
        api = self.api
        job = checked(api.CreateJobObjectW(None, None))
        process = None
        try:
            limits = ExtendedLimits()
            # JOB_TIME | PROCESS_MEMORY | JOB_MEMORY | KILL_ON_JOB_CLOSE
            limits.basic.flags = 0x4 | 0x100 | 0x200 | 0x2000
            limits.basic.job_time = int(self.user_cpu_s*10_000_000)
            limits.process_memory = limits.job_memory = self.memory_bytes
            checked(api.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
            process = subprocess.Popen([sys.executable, '-c', BOOTSTRAP, *command[1:]],
                                       stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                                       env=environment, creationflags=subprocess.CREATE_NO_WINDOW,
                                       close_fds=True)
            handle = checked(api.OpenProcess(0x0100 | 0x0001, False, process.pid))
            try:
                checked(api.AssignProcessToJobObject(job, handle))
            finally:
                api.CloseHandle(handle)
            process.stdin.write(b'1'); process.stdin.flush(); process.stdin.close()
            return WindowsProcess(process, job, api)
        except BaseException:
            try:
                if process is not None:
                    try:
                        if process.stdin and not process.stdin.closed:
                            process.stdin.close()
                    except OSError:
                        pass
                    process.kill(); process.wait()
            finally:
                api.CloseHandle(job)
            raise

    def terminate(self, process):
        if process.job:
            try:
                checked(self.api.TerminateJobObject(process.job, 1))
            finally:
                process.close_job()
        process.wait()

    def release(self, process):
        # Closing the job also kills any descendants that outlived their parent.
        process.close_job()
        process.wait()
