"""Check an exported website under a subpath, without an application backend."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
from threading import Thread

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--browser", default=shutil.which("chromium"))
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not (directory / "index.html").is_file():
        parser.error("Export the website first with scripts/build_site.py --export")

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=directory.parent))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/{directory.name}/"
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.browser)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: errors.append(response.url) if response.status >= 400 else None)
            for name in ("index", "start", "manual", "theory", "api", "downloads", "validation", "about"):
                page.goto(base + name + ".html")
                expect(page.locator("h1")).to_be_visible()
                assert page.locator("html").evaluate("(el) => el.scrollWidth") <= 390, name
                assert page.locator('a[href="http://127.0.0.1:8000/workbench"]').count() >= 1
                assert page.locator("script").count() == 0
            page.goto(base + "index.html")
            page.locator('.topbar a[href="manual.html"]').click()
            expect(page.locator("h1")).to_have_text("User manual")
            response = page.request.get(base + "downloads/prism-fmr.json")
            assert response.ok and response.json()["model"] == "confined"
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    print("Static website: eight pages, subpath navigation, mobile layout and preset JSON passed.")


if __name__ == "__main__":
    main()
