"""Single-process web supervisor with a bounded serial subprocess queue."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid

from ..config import validate_web_config
from ..jobs import write_json
from ..runtime import backend


class QueueFull(RuntimeError):
    pass


class JobManager:
    def __init__(self, directory, *, timeout_s=120, max_pending=4, max_retained=16):
        self.runtime = backend()
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lease = self.runtime.acquire(self.directory/".lock")
        self.timeout_s = timeout_s
        self.max_pending = max_pending
        self.max_retained = max_retained
        self._lock = threading.RLock()
        self._records = {}
        self._active = None
        self._stopped = threading.Event()
        try:
            for path in self.directory.glob("*/status.json"):
                record = json.loads(path.read_text())
                if record["status"] in ("queued", "running"):
                    record.update(status="interrupted", error="Server stopped before job completion", finished=time.time())
                    write_json(path, record)
                self._records[record["id"]] = record
        except BaseException:
            self._lease.close()
            raise
        self._thread = threading.Thread(target=self._supervise, name="spinfreq-supervisor", daemon=True)
        self._thread.start()

    def _save(self, record):
        write_json(self.directory/record["id"]/"status.json", record)

    def submit(self, config):
        validate_web_config(config)
        with self._lock:
            pending = sum(r["status"] in ("queued", "running") for r in self._records.values())
            if pending >= self.max_pending or len(self._records) >= self.max_retained:
                raise QueueFull("Job capacity reached; wait or delete completed jobs")
            identifier = uuid.uuid4().hex
            directory = self.directory/identifier
            directory.mkdir(mode=0o700)
            write_json(directory/"request.json", config.to_dict())
            record = {"id": identifier, "status": "queued", "created": time.time(), "runtime": self.runtime.name}
            self._save(record)
            self._records[identifier] = record
            return dict(record)

    def get(self, identifier):
        with self._lock:
            if identifier not in self._records:
                raise KeyError(identifier)
            record = dict(self._records[identifier])
            progress = self.directory/identifier/"progress.json"
            if progress.exists():
                record["stage"] = json.loads(progress.read_text())["stage"]
            return record

    def list(self):
        with self._lock:
            return [self.get(key) for key in reversed(self._records)]

    def cancel(self, identifier):
        with self._lock:
            record = self._records[identifier]
            if record["status"] in ("queued", "running"):
                if self._active and self._active[0] == identifier:
                    self._terminate(self._active[1])
                    self._active[3].close()
                    self._active = None
                record.update(status="cancelled", finished=time.time())
                self._save(record)
            return self.get(identifier)

    def delete(self, identifier):
        import shutil
        with self._lock:
            if self._records[identifier]["status"] in ("queued", "running"):
                raise ValueError("Cancel a pending job before deletion")
            shutil.rmtree(self.directory/identifier)
            del self._records[identifier]

    def _terminate(self, process):
        self.runtime.terminate(process)

    def _tick(self):
        with self._lock:
            if self._active:
                identifier, process, started, log = self._active
                directory = self.directory/identifier
                record = self._records[identifier]
                sizes = []
                for path in directory.rglob('*'):
                    try:
                        if path.is_file():
                            sizes.append(path.stat().st_size)
                    except FileNotFoundError:
                        # Plot/font caches can atomically rename temporary files.
                        continue
                if record["status"] == "running" and (time.monotonic()-started > self.timeout_s
                        or sum(sizes) > 96*1024**2 or max(sizes, default=0) > 32*1024**2):
                    self._terminate(process)
                    record.update(status="failed", error="Wall-time, file or disk limit exceeded (32 MiB/file, 96 MiB/job)", finished=time.time())
                    self._save(record)
                if process.poll() is None:
                    return
                self.runtime.release(process)
                log.close()
                if record["status"] == "running":
                    path = directory/"results"/"summary.json"
                    summary = json.loads(path.read_text()) if path.exists() else {}
                    success = process.returncode == 0 and summary.get("status") == "succeeded"
                    record.update(status="succeeded" if success else "failed", finished=time.time(),
                                  returncode=process.returncode)
                    if not success:
                        record["error"] = summary.get("error", "Worker terminated; resource or numerical failure")
                    self._save(record)
                self._active = None
            for identifier, record in self._records.items():
                if record["status"] != "queued":
                    continue
                directory = self.directory/identifier
                environment = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                                   MPLBACKEND="Agg", MPLCONFIGDIR=str(directory/"mpl-cache"),
                                   SPINFREQ_WORKER_RUNTIME=self.runtime.name)
                log = (directory/"worker.log").open("wb")
                try:
                    process = self.runtime.start([sys.executable, "-m", "spinfreq.worker", str(directory),
                                                  "--parent", str(os.getpid()), "--timeout", str(self.timeout_s)],
                                                 log, environment)
                except (OSError, RuntimeError) as error:
                    log.close()
                    record.update(status="failed", error=f"Worker could not start: {error}", finished=time.time())
                    self._save(record)
                    continue
                # Own the process before any fallible status publication, so a
                # disk/journal error cannot leave an untracked native worker.
                self._active = (identifier, process, time.monotonic(), log)
                record.update(status="running", started=time.time())
                self._save(record)
                break

    def _supervise(self):
        while not self._stopped.wait(.1):
            try:
                self._tick()
            except Exception as error:
                with self._lock:
                    if self._active:
                        identifier, process, _, log = self._active
                        self._terminate(process); log.close(); self._active = None
                        self._records[identifier].update(status="failed", error=f"Supervisor failure: {error}", finished=time.time())
                        self._save(self._records[identifier])

    def close(self):
        self._stopped.set()
        self._thread.join()
        with self._lock:
            for identifier in list(self._records):
                self.cancel(identifier)
            if self._active:
                self._terminate(self._active[1]); self._active[3].close(); self._active = None
            self._lease.close()
