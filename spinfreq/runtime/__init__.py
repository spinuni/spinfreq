"""Platform-specific controls for trusted local computation workers."""
import sys


def backend():
    if sys.platform.startswith('linux'):
        from .linux import LinuxRuntime
        return LinuxRuntime()
    if sys.platform == 'win32':
        from .windows import WindowsRuntime
        return WindowsRuntime()
    raise RuntimeError('Protected workers require Linux or Windows; use landing mode')
