"""Render the canonical handbook; optionally export a backend-free website.

Generated pages are committed and shipped in the wheel, so users do not need
Markdown at runtime. Run --check in CI to detect stale documentation.
"""
import argparse
from html import escape
import json
from pathlib import Path
import shutil
import sys
import tomllib
import re
from urllib.parse import urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "spinfreq/web/static"
PAGES = {
    "start": "Start here",
    "manual": "Manual", "theory": "Theory", "api": "API",
    "downloads": "Downloads", "validation": "Validation", "about": "About",
}


def source_for(name):
    return ROOT/"docs/getting-started/README.md" if name == "start" else ROOT/"docs/handbook"/f"{name}.md"


def render(name, source):
    md = markdown.Markdown(extensions=["toc", "tables", "fenced_code"],
                           extension_configs={"toc": {"toc_depth": "2-3"}})
    content = md.convert(source)
    def documentation_link(match):
        target = urlsplit(match.group(1))
        if target.scheme or target.netloc or not target.path.endswith(".md"):
            return match.group(0)
        path = (source_for(name).parent/target.path).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("Documentation link escapes the repository")
        pages = {source_for(key).resolve(): key+".html" for key in PAGES}
        href = pages.get(path, "https://github.com/spinuni/spinfreq/blob/main/"+path.relative_to(ROOT).as_posix())
        return 'href="'+href+('#'+target.fragment if target.fragment else '')+'"'
    content = re.sub(r'href="([^"]+)"', documentation_link, content)
    links = "".join(f'<a href="{key}.html"' +
                    (' aria-current="page"' if key == name else '') +
                    f'>{label}</a>' for key, label in PAGES.items())
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="SpinFreq {escape(PAGES[name])}: thin-film frequency-domain micromagnetics.">
<title>{PAGES[name]} · SpinFreq</title><link rel="stylesheet" href="static/style.css"></head>
<body><a class="skip-link" href="#content">Skip to content</a><main class="handbook">
<nav class="topbar" aria-label="Main"><a class="brand" href="index.html">SpinFreq</a><div>{links}<a href="workbench">Simulator ↗</a></div></nav>
<p class="eyebrow">HANDBOOK · {escape(version)} · RESEARCH CANDIDATE</p>
<div class="book-layout"><aside class="book-toc" aria-label="On this page"><strong>On this page</strong>{md.toc}</aside>
<article id="content">{content}</article></div>
<footer>SpinFreq · MIT licensed · <a href="https://github.com/spinuni/spinfreq">Source and issues</a> · Documentation ships with the application.</footer>
</main></body></html>
'''


def build(check=False, export=None):
    stale = []
    for name in PAGES:
        source = source_for(name)
        page = STATIC / f"{name}.html"
        rendered = render(name, source.read_text(encoding="utf-8"))
        if check:
            if not page.exists() or page.read_text(encoding="utf-8") != rendered:
                stale.append(str(page.relative_to(ROOT)))
        else:
            page.write_text(rendered, encoding="utf-8", newline="\n")
    if stale:
        raise SystemExit("Stale handbook: run python scripts/build_site.py\n" + "\n".join(stale))
    if export:
        destination = Path(export).resolve()
        # Avoid overwriting sources or an existing output with unrelated files.
        if destination == ROOT or ROOT.is_relative_to(destination) or destination.is_relative_to(STATIC):
            raise SystemExit("Choose a separate, empty export directory")
        if destination.exists() and any(destination.iterdir()):
            raise SystemExit("Export directory must be empty")
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "static").mkdir()
        for name in ("style.css", "spinfreq-logo.png"):
            shutil.copyfile(STATIC / name, destination / "static" / name)
        for name in ["landing", *PAGES]:
            page = (STATIC / f"{name}.html").read_text(encoding="utf-8")
            page = page.replace('href="/"', 'href="index.html"').replace('href="/index.html"', 'href="index.html"')
            page = page.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
            page = page.replace('href="/workbench"', 'href="http://127.0.0.1:8000/workbench"')
            page = page.replace('href="workbench"', 'href="http://127.0.0.1:8000/workbench"')
            page = page.replace('<script defer src="static/landing.js"></script>', '')
            page = page.replace('Explore the workbench</a>', 'Open local workbench</a>')
            page = page.replace('Checking local execution capabilities…', 'Static documentation · launch spinfreq-web locally to compute.')
            page = page.replace('The workbench reports whether this server supports simulation workers.',
                                'This is the documentation website. Install SpinFreq on your computer to run simulations, then use the local workbench link.')
            (destination / ("index.html" if name == "landing" else f"{name}.html")).write_text(page, encoding="utf-8")
        # Import only when exporting; regular rendering does not need the package.
        sys.path.insert(0, str(ROOT))
        from spinfreq.config import presets
        (destination / "downloads").mkdir()
        for name, config in presets().items():
            (destination / "downloads" / f"{name}.json").write_text(json.dumps(config.to_dict(), indent=2)+"\n", encoding="utf-8")
        (destination / ".nojekyll").touch()
        print(f"Static site exported to {destination}; no simulation backend included.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    build(args.check, args.export)
