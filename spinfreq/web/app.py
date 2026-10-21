"""Local, single-user web service around the shared physics runner."""
import argparse
from contextlib import asynccontextmanager
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..config import JobConfig, presets
from ..jobs import ARTIFACTS
from .queue import JobManager, QueueFull
from .platforms import capabilities


def create_app(directory="results/web", *, mode="auto", **manager_options):
    support = capabilities(mode)
    @asynccontextmanager
    async def lifespan(app):
        app.state.jobs = JobManager(directory, **manager_options) if support["simulation_enabled"] else None
        try:
            yield
        finally:
            if app.state.jobs is not None:
                app.state.jobs.close()

    app = FastAPI(title="SpinFreq local research workbench", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin requests are not accepted"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'"
        return response

    def manager():
        if app.state.jobs is None:
            raise HTTPException(503, support["message"])
        return app.state.jobs

    def record(identifier):
        try:
            return manager().get(identifier)
        except KeyError:
            raise HTTPException(404, "Unknown job") from None

    @app.get("/")
    def index():
        return FileResponse(Path(__file__).with_name("static")/"landing.html")

    @app.get("/workbench")
    def workbench():
        return FileResponse(Path(__file__).with_name("static")/"index.html")

    @app.get("/static/{name}")
    def static(name: str):
        if name not in ("app.js", "landing.js", "style.css", "spinfreq-logo.png"):
            raise HTTPException(404)
        return FileResponse(Path(__file__).with_name("static")/name)

    @app.get("/api/presets")
    def get_presets():
        return {name: config.to_dict() for name, config in presets().items()}

    @app.get("/api/capabilities")
    def get_capabilities():
        return support

    @app.get("/api/jobs")
    def get_jobs():
        return manager().list() if support["simulation_enabled"] else []

    async def read_config(request):
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "Send application/json")
        # Bound streamed input as well as Content-Length; avoid unbounded reads.
        body = bytearray()
        async for chunk in request.stream():
            if len(body)+len(chunk) > 16384:
                raise HTTPException(413, "Configuration exceeds 16 KiB")
            body.extend(chunk)
        try:
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError(f"Duplicate key: {key}")
                    result[key] = value
                return result
            return JobConfig.from_dict(json.loads(body, object_pairs_hook=unique))
        except (ValueError, TypeError, RecursionError) as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/config/validate")
    async def validate_config(request: Request):
        config = await read_config(request)
        return config.to_dict()

    @app.post("/api/jobs", status_code=202)
    async def submit(request: Request):
        jobs = manager()
        config = await read_config(request)
        try:
            return jobs.submit(config)
        except QueueFull as error:
            raise HTTPException(429, str(error)) from None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.get("/api/jobs/{identifier}")
    def get_job(identifier: str):
        return record(identifier)

    @app.post("/api/jobs/{identifier}/cancel")
    def cancel(identifier: str):
        record(identifier)
        return manager().cancel(identifier)

    @app.delete("/api/jobs/{identifier}", status_code=204)
    def delete(identifier: str):
        record(identifier)
        try:
            manager().delete(identifier)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @app.get("/api/jobs/{identifier}/artifacts/{name}")
    def download(identifier: str, name: str):
        job = record(identifier)
        if name not in ARTIFACTS or (job["status"] != "succeeded" and name not in ("configuration.json", "summary.json")):
            raise HTTPException(404, "Artifact unavailable")
        path = manager().directory/identifier/"results"/name
        if not path.is_file():
            raise HTTPException(404, "Artifact unavailable")
        return FileResponse(path, filename=name)

    return app


def main():
    parser = argparse.ArgumentParser(description="SpinFreq web: Linux computation or portable configuration preview")
    parser.add_argument("--data-dir", type=Path, default=Path("results/web"))
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mode", choices=("auto", "landing", "compute"), default="auto",
                        help="auto enables workers on Linux and preview on Windows/macOS")
    args = parser.parse_args()
    import uvicorn
    try:
        app = create_app(args.data_dir, mode=args.mode)
    except ValueError as error:
        parser.error(str(error))
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1)


if __name__ == '__main__':
    main()
