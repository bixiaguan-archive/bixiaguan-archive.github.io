"""按 GitHub Pages 部署结构起本地站点，用本机 Chrome 检查用户可见行为。

先运行 `python3 build_index.py` 生成数据。
"""
import functools
import http.server
import threading
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "bixiaguan_search"


class DeployLayoutHandler(http.server.SimpleHTTPRequestHandler):
    """与 deploy.yml 一致：站点根是 bixiaguan_search/，访古地图复制到根下。"""

    def translate_path(self, path):
        if path.split("?")[0] == "/ancient-buildings-map.html":
            return str(ROOT / "ancient-buildings-map.html")
        return super().translate_path(path)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def base_url():
    handler = functools.partial(DeployLayoutHandler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1100, "height": 900})
    pg = ctx.new_page()
    yield pg
    ctx.close()


def json_bytes_loaded(page):
    return page.evaluate(
        "performance.getEntriesByType('resource')"
        ".filter(e => e.name.endsWith('.json'))"
        ".reduce((s, e) => s + e.decodedBodySize, 0)"
    )


def test_home_shows_episode_list_without_downloading_transcripts(page, base_url):
    page.goto(base_url + "/")
    expect(page.locator(".ep-item")).to_have_count(102)
    assert json_bytes_loaded(page) < 1_000_000


def test_episode_page_shows_transcript_with_notes(page, base_url):
    page.goto(base_url + "/?ep=87")
    expect(page.locator(".transcript-header h2")).to_contain_text("EP087")
    assert page.locator(".transcript-seg").count() > 100
    page.locator(".note-badge").first.click()
    expect(page.locator("#note-popup")).to_be_visible()
    expect(page.locator("#note-popup-content .note-item").first).to_be_visible()


def test_full_text_search_highlights_hits(page, base_url):
    page.goto(base_url + "/")
    page.fill("#q", "照夜白")
    page.press("#q", "Enter")
    expect(page.locator(".hit-text mark").first).to_have_text("照夜白")
    expect(page.locator("#status")).to_contain_text("找到")


def test_back_button_returns_from_transcript_to_list(page, base_url):
    page.goto(base_url + "/")
    page.locator(".browse-link").first.click()
    expect(page.locator(".transcript-view")).to_be_visible()
    page.go_back()
    expect(page.locator(".ep-item")).to_have_count(102)
    assert "ep=" not in page.url


@pytest.mark.parametrize("path, ready", [
    ("/?ep=87", ".transcript-seg"),
    ("/ancient-buildings-map.html", "#list tbody tr"),
])
def test_phone_width_has_no_horizontal_scroll(browser, base_url, path, ready):
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    pg = ctx.new_page()
    pg.goto(base_url + path)
    expect(pg.locator(ready).first).to_be_attached()
    assert pg.evaluate("document.documentElement.scrollWidth") <= 375
    ctx.close()


def test_map_episode_link_opens_that_episode(page, base_url):
    page.goto(base_url + "/ancient-buildings-map.html")
    row = page.locator("#list tbody tr").filter(has_text="#").first
    row.click()
    link = page.locator(".leaflet-popup a", has_text="期").first
    expect(link).to_be_visible()
    with page.context.expect_page() as new_page_info:
        link.click()
    episode = new_page_info.value
    expect(episode.locator(".transcript-view")).to_be_visible()


def test_map_links_back_to_home(page, base_url):
    page.goto(base_url + "/ancient-buildings-map.html")
    page.locator("nav a", has_text="首页").click()
    expect(page.locator(".ep-item")).to_have_count(102)
