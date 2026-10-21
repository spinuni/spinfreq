"""One bounded Linux worker process. Started only by the web job manager."""
import argparse
import ctypes
import os
from pathlib import Path
import resource
import signal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--parent", type=int, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    args = parser.parse_args()
    # Terminate a worker if its owning server dies, including a startup race.
    if ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0:
        raise RuntimeError("Could not configure parent-death signal")
    if os.getppid() != args.parent:
        raise SystemExit("Worker owner no longer exists")
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 61))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32*1024**2, 32*1024**2))
    signal.alarm(args.timeout)
    from .config import JobConfig
    from .jobs import run_job, write_json
    directory = args.directory
    def progress(stage):
        write_json(directory/"progress.json", {"stage": stage})
    run_job(JobConfig.load(directory/"request.json"), directory/"results", progress)


if __name__ == "__main__":
    main()
