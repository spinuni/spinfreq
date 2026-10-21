"""One bounded worker. Linux configures rlimits; Windows is gated into a job."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--parent", type=int, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    args = parser.parse_args()
    if sys.platform.startswith('linux'):
        from .runtime.linux import configure_worker
        configure_worker(args.parent, args.timeout)
    elif sys.platform == 'win32':
        if os.environ.get('SPINFREQ_WORKER_RUNTIME') != 'windows-job-object-experimental':
            raise RuntimeError('Windows workers must be launched through a protected supervisor')
    else:
        raise RuntimeError('Unsupported worker platform')
    from .config import JobConfig
    from .jobs import run_job, write_json
    directory = args.directory
    def progress(stage):
        write_json(directory/"progress.json", {"stage": stage})
    run_job(JobConfig.load(directory/"request.json"), directory/"results", progress)


if __name__ == "__main__":
    main()
