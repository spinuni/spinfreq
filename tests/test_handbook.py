"""Installed handbook navigation, downloads and runnable API examples."""
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from spinfreq.config import JobConfig, presets
from spinfreq.web.app import create_app

PAGES = ("start", "manual", "theory", "api", "downloads", "validation", "about")


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.links, self.ids, self.python = [], set(), []
        self.code = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag in ("a", "link", "script", "img"):
            target = attrs.get("href", attrs.get("src"))
            if target:
                self.links.append(target)
        if tag == "code" and attrs.get("class") == "language-python":
            self.code = ""

    def handle_data(self, data):
        if self.code is not None:
            self.code += data

    def handle_endtag(self, tag):
        if tag == "code" and self.code is not None:
            self.python.append(self.code)
            self.code = None


def test_offline_handbook_links_and_downloads_without_workers(tmp_path):
    directory = tmp_path / "no-worker-storage"
    with TestClient(create_app(directory, mode="landing")) as client:
        documents = {f"/{name}.html": Document(client.get(f"/{name}.html").text) for name in PAGES}
        documents["/index.html"] = Document(client.get("/").text)
        for path, document in documents.items():
            for target in document.links:
                url = urlsplit(urljoin("http://testserver" + path, target))
                if url.netloc != "testserver":
                    continue
                response = client.get(url.path)
                assert response.status_code == 200, (path, target)
                if url.fragment:
                    assert unquote(url.fragment) in Document(response.text).ids, (path, target)
        for name, config in presets().items():
            response = client.get(f"/downloads/{name}.json")
            assert JobConfig.from_dict(response.json()) == config
            assert "attachment" in response.headers["content-disposition"]
        assert client.get("/downloads/missing.json").status_code == 404
        assert client.get("/unknown.html").status_code == 404
        assert client.get("/docs").url.path == "/api.html"
        assert "/api/jobs" in client.get("/openapi.json").json()["paths"]
        assert not client.get("/api/capabilities").json()["simulation_enabled"]
    assert not directory.exists()


def test_published_python_examples_run(tmp_path, monkeypatch):
    from spinfreq.web import app
    source = Path(app.__file__).with_name("static") / "api.html"
    examples = Document(source.read_text(encoding="utf-8")).python
    monkeypatch.chdir(tmp_path)
    (tmp_path / "prism-fmr.json").write_text(json.dumps(presets()["prism-fmr"].to_dict()))
    shared = {}
    exec(compile(examples[0], "handbook/shared-job", "exec"), shared)
    assert shared["summary"]["status"] == "succeeded"
    low_level = {}
    exec(compile(examples[1], "handbook/low-level", "exec"), low_level)
    assert low_level["delta_m"].shape == (21, 2, 2, 3)
    assert np.all(np.isfinite(low_level["power_W"]))
    assert np.all(low_level["power_W"] >= 0)
