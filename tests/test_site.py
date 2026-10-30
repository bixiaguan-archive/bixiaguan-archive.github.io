"""起本地站点（即 GitHub Pages 部署的 bixiaguan_search/），用本机 Chrome 检查用户可见行为。

先运行 `python3 build_index.py` 生成数据。
"""
import functools
import http.server
import re
import threading
from pathlib import Path
from urllib.parse import quote

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "bixiaguan_search"


MAP = "/ancient-buildings-map.html"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def base_url():
    handler = functools.partial(QuietHandler, directory=str(SITE))
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


def test_time_link_scrolls_transcript_to_that_moment(page, base_url):
    page.goto(base_url + "/?ep=5&t=600")
    seg = page.locator(".transcript-seg.seek")
    expect(seg).to_be_in_viewport()
    minutes, seconds = map(int, seg.locator(".ts").inner_text().split(":"))
    assert 540 <= minutes * 60 + seconds <= 600


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
    (MAP, ".place-item"),
])
def test_phone_width_has_no_horizontal_scroll(browser, base_url, path, ready):
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    pg = ctx.new_page()
    pg.goto(base_url + path)
    expect(pg.locator(ready).first).to_be_attached()
    assert pg.evaluate("document.documentElement.scrollWidth") <= 375
    ctx.close()


def test_map_search_opens_place_with_links_into_transcript(page, base_url):
    page.goto(base_url + MAP)
    expect(page.locator(".place-item").first).to_be_visible()
    assert page.locator(".place-item").count() > 200
    page.fill("#map-search", "佛光寺")
    page.locator(".place-item", has_text="佛光寺").first.click()
    expect(page.locator("#detail h2")).to_have_text("佛光寺")
    expect(page.locator("#detail .facts a[href^='https://www.wikidata.org/wiki/Q']")).to_be_visible()
    moment = page.locator("#detail a.ep-moment").first
    assert re.fullmatch(r"index\.html\?ep=\d+&t=\d+", moment.get_attribute("href"))
    with page.context.expect_page() as new_page_info:
        moment.click()
    expect(new_page_info.value.locator(".transcript-seg.seek")).to_be_in_viewport()


def test_map_place_link_is_shareable_and_back_closes_it(page, base_url):
    page.goto(base_url + MAP)
    page.goto(base_url + MAP + "?place=" + quote("佛光寺"))
    expect(page.locator("#detail h2")).to_have_text("佛光寺")
    page.locator(".place-item").first.wait_for(state="attached")
    page.locator("#detail .back").click()
    expect(page.locator(".place-item").first).to_be_visible()
    page.locator(".place-item").nth(3).click()
    expect(page.locator("#detail")).to_be_visible()
    page.go_back()
    expect(page.locator("#detail")).to_be_hidden()


def test_map_era_filter_narrows_places(page, base_url):
    page.goto(base_url + MAP)
    expect(page.locator(".place-item").first).to_be_visible()
    total = page.locator(".place-item").count()
    page.locator('.band-chip[data-band="tang"]').click()
    bands = page.locator(".place-item").evaluate_all("els => els.map(e => e.dataset.band)")
    assert 0 < len(bands) < total
    assert set(bands) == {"tang"}


def test_map_route_draws_path_and_lists_stops(page, base_url):
    page.goto(base_url + MAP)
    page.locator('.tab[data-tab="routes"]').click()
    assert page.locator(".route-item").count() >= 20
    expect(page.locator(".route-group").first).to_have_text("山西")
    expect(page.locator(".route-group", has_text="海外")).to_be_visible()
    page.locator(".route-item").first.click()
    assert page.locator("#detail .stop").count() >= 3
    expect(page.locator(".leaflet-overlay-pane path").first).to_be_attached()


def test_map_routes_show_cover_posters(page, base_url):
    loaded = "img => img.complete && img.naturalWidth > 0"
    page.goto(base_url + MAP + "?route=1")
    cover = page.locator("#detail .route-cover")
    expect(cover).to_be_visible()
    expect(cover).to_have_attribute("alt", re.compile("^唐五代木构"))
    page.wait_for_function(f"({loaded})(document.querySelector('#detail .route-cover'))")
    page.locator("#detail .back").click()
    thumbs = page.locator("#route-list .route-item img")
    expect(thumbs).to_have_count(page.locator("#route-list .route-item").count())
    page.wait_for_function(f"({loaded})(document.querySelector('#route-list .route-item img'))")


def test_map_place_lists_routes_through_it(page, base_url):
    page.goto(base_url + MAP + "?place=" + quote("佛光寺"))
    route = page.locator("#detail .route-item", has_text="唐五代木构")
    expect(route).to_be_visible()
    route.click()
    expect(page.locator("#detail h2")).to_have_text(re.compile("^唐五代木构"))


def test_map_custom_route_orders_picked_places_nearest_first(page, base_url):
    page.goto(base_url + MAP)
    for name in ["晋祠", "故宫", "平遥古城", "隆兴寺"]:
        page.fill("#map-search", name)
        page.locator(".place-item").filter(has=page.locator(".nm", has_text=re.compile(f"^{name}$"))).click()
        page.locator("#detail .pick-toggle").click()
        page.locator("#detail .back").click()
    page.locator('.tab[data-tab="custom"]').click()
    order = ["故宫", "隆兴寺", "晋祠", "平遥古城"]
    names = page.locator("#view-custom .stop .nm").all_inner_texts()
    assert names in (order, order[::-1])
    expect(page.locator(".leaflet-overlay-pane path").first).to_be_attached()
    page.reload()
    assert page.locator("#view-custom .stop .nm").all_inner_texts() == names
    page.locator("#view-custom .unpick").first.click()
    expect(page.locator("#view-custom .stop")).to_have_count(3)


def test_map_links_back_to_home(page, base_url):
    page.goto(base_url + MAP)
    page.locator("nav a", has_text="首页").click()
    expect(page.locator(".ep-item")).to_have_count(102)
