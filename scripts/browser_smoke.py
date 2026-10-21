"""Real Chromium UI -> worker -> image/export smoke test; launch server first."""
import argparse
import json
from pathlib import Path
import zipfile
import shutil
import re
import time
from urllib.request import urlopen
from urllib.error import URLError

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', type=Path, default=Path('results/browser-smoke'))
    parser.add_argument('--browser', default=shutil.which('chromium'), help='Optional installed Chromium executable')
    parser.add_argument('--landing', action='store_true', help='Check preview/configuration export without a worker')
    parser.add_argument('--session', help='Require this qualification server session before submitting a job')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic()+15
    while True:
        try:
            with urlopen(args.url+'/api/presets', timeout=1):
                break
        except URLError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.1)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.browser)
        page = browser.new_page(viewport={'width':1280, 'height':1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.url)
        support = page.request.get(args.url+'/api/capabilities').json()
        if args.session:
            assert support.get('qualification_session') == args.session, 'Wrong qualification server session'
        expect(page.locator('.hero-logo')).to_have_js_property('complete', True)
        assert page.locator('.hero-logo').element_handle().get_property('naturalWidth').json_value() > 0
        expect(page.locator('#launch')).not_to_have_text('Explore the workbench')
        page.screenshot(path=str(args.output/'landing.png'), full_page=True)
        # The installed handbook must render without external scripts and remain
        # usable on a phone before entering the numerical workbench.
        for name in ('manual', 'theory', 'api', 'downloads', 'validation', 'about'):
            page.goto(args.url+'/'+name+'.html')
            expect(page.locator('article h1')).to_be_visible()
            page.set_viewport_size({'width':390, 'height':844})
            assert page.locator('html').evaluate('(el) => el.scrollWidth') <= 390, name
            if name == 'manual':
                page.screenshot(path=str(args.output/'manual-mobile.png'), full_page=True)
            page.set_viewport_size({'width':1280, 'height':1000})
        page.goto(args.url+'/downloads.html')
        with page.expect_download() as event:
            page.locator('article a[href="downloads/prism-fmr.json"]').click()
        event.value.save_as(args.output/'preset-download.json')
        assert json.loads((args.output/'preset-download.json').read_text())['model'] == 'confined'
        page.goto(args.url)
        expect(page.locator('#launch')).not_to_have_text('Explore the workbench')
        page.click('#launch')
        page.locator('#preset option[value="prism-fmr"]').wait_for(state='attached')
        page.select_option('#preset', 'prism-fmr')
        page.fill('#points', '21')
        if args.landing:
            expect(page.locator('#run')).to_be_disabled()
            expect(page.locator('#preview-notice')).to_be_visible()
            with page.expect_download() as event:
                page.click('#export-config')
            event.value.save_as(args.output/'configuration.json')
            config = json.loads((args.output/'configuration.json').read_text())
            assert config['nx'] == 1 and config['points'] == 21
            assert page.request.get(args.url+'/api/jobs').json() == []
            assert not errors, errors
            page.screenshot(path=str(args.output/'desktop.png'), full_page=True)
            page.set_viewport_size({'width':390, 'height':844})
            assert page.locator('html').element_handle().get_property('scrollWidth').json_value() <= 390
            page.screenshot(path=str(args.output/'mobile.png'), full_page=True)
            report = {'browser':'Chromium', 'browser_version':browser.version,
                      'mode':'landing', 'configuration_export_passed':True,
                      'simulation_disabled':True, 'javascript_errors':errors,
                      'mobile_horizontal_overflow':False}
            (args.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
            browser.close()
            return
        page.click('#run')
        expect(page.locator('#status')).to_have_text(re.compile(r'^succeeded'), timeout=120000)
        for name in ('spectrum', 'equilibrium', 'mode'):
            expect(page.locator('#'+name)).to_have_js_property('complete', True)
            assert page.locator('#'+name).element_handle().get_property('naturalWidth').json_value() > 0
        with page.expect_download() as event:
            page.click('#zip')
        event.value.save_as(args.output/'results.zip')
        with zipfile.ZipFile(args.output/'results.zip') as archive:
            config = json.loads(archive.read('configuration.json'))
            summary = json.loads(archive.read('summary.json'))
        assert config['nx'] == 1 and config['points'] == 21
        assert summary['status'] == 'succeeded' and summary['stability'] == 'stable'
        if args.session:
            assert summary.get('qualification_session') == args.session
        server_platform = page.request.get(args.url+'/api/capabilities').json()['platform']
        expected_runtime = 'windows-job-object-experimental' if server_platform == 'win32' else 'linux-rlimit'
        assert summary['worker_runtime'] == expected_runtime
        assert not errors, errors
        page.screenshot(path=str(args.output/'desktop.png'), full_page=True)
        page.set_viewport_size({'width':390, 'height':844})
        assert page.locator('html').element_handle().get_property('scrollWidth').json_value() <= 390
        page.screenshot(path=str(args.output/'mobile.png'), full_page=True)
        report = {'browser':'Chromium', 'ui_worker_download_passed':True, 'images_loaded':3,
                  'javascript_errors':errors, 'mobile_horizontal_overflow':False,
                  'configuration_sha256':summary['configuration_sha256'],
                  'server_platform':server_platform,
                  'worker_runtime':summary.get('worker_runtime', 'unrecorded')}
        report['qualification_session'] = support.get('qualification_session')
        (args.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
        browser.close()


if __name__ == '__main__':
    main()
