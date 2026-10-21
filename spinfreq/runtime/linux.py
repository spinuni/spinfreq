"""Linux worker process groups, storage lease and hard resource controls."""
import ctypes
import os
import signal
import subprocess


class LinuxRuntime:
    name = 'linux-rlimit'

    def acquire(self, path):
        import fcntl
        lease = path.open('a+b')
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lease.close()
            raise RuntimeError('Data directory already has a supervisor; use one server process') from None
        return lease

    def start(self, command, log, environment):
        return subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                env=environment, start_new_session=True)

    def terminate(self, process):
        # Kill the group even when the direct worker already exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

    def release(self, process):
        self.terminate(process)


def configure_worker(parent, timeout):
    import resource
    if ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0:
        raise RuntimeError('Could not configure parent-death signal')
    if os.getppid() != parent:
        raise SystemExit('Worker owner no longer exists')
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32*1024**2, 32*1024**2))
    signal.alarm(timeout)
