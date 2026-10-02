"""可选浏览器验收：pip install playwright；使用本机 Chrome，无需下载浏览器。"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs'
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8765/')
    page.wait_for_function("document.querySelector('#status').textContent.includes('已就绪')")
    page.locator('#run-top').click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('已完成')")
    assert page.locator('#return').inner_text() == '+0.21%'
    assert page.locator('#trade-rows tr').count() == 21
    page.locator('#fast').fill('40')
    assert page.locator('#export').is_disabled()
    assert page.locator('#outdated').is_visible()
    page.locator('#run-top').click()
    assert '短均线周期必须小于' in page.locator('#status-top').inner_text()
    page.locator('#fast').fill('10')
    page.locator('#dataset').select_option('custom')
    assert page.locator('#upload').is_visible()
    page.locator('#upload').set_input_files(str(ROOT / 'data/aapl.csv'))
    page.wait_for_function("document.querySelector('#status').textContent.includes('文件已读取')")
    page.locator('#run-top').click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('已完成')")
    assert page.locator('#return').inner_text() == '+0.21%'
    assert not page.locator('#outdated').is_visible()
    assert '506' in page.locator('#data-info').inner_text()
    assert '待校验' not in page.locator('#data-info').inner_text()
    with page.expect_download() as download:
        page.locator('#export').click()
    download.value.save_as(str(OUT / 'verified-report.json'))
    report = json.loads((OUT / 'verified-report.json').read_text(encoding='utf-8'))
    assert len(report['data_sha256']) == 64
    assert len(report['curve']) == 506
    with page.expect_download() as download:
        page.locator('#export-trades').click()
    download.value.save_as(str(OUT / 'verified-trades.csv'))
    assert len((OUT / 'verified-trades.csv').read_text(encoding='utf-8-sig').splitlines()) == 22
    page.screenshot(path=str(OUT / 'desktop.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(OUT / 'mobile.png'), full_page=True)
    assert not errors, errors
    print('PASS: real sample, parameter errors, stale state, CSV upload, JSON/CSV exports, mobile overflow, JS errors')
    browser.close()
