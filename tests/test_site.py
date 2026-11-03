"""起本地站点（即 GitHub Pages 部署的 bixiaguan_search/），用本机 Chrome 检查用户可见行为。

先运行 `python3 build_index.py` 生成数据。
"""
import functools
import http.server
import json
import re
import threading
from pathlib import Path
from urllib.parse import quote

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "bixiaguan_search"


MAP = "/ancient-buildings-map.html"
TERMS = "/terms.html"
ERRATA = "/errata.html"


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
def playwright():
    with sync_playwright() as p:
        yield p


# 每个测试单独起浏览器：本机 Chrome 连着跑约 30 秒后会自行断开
@pytest.fixture
def browser(playwright):
    b = playwright.chromium.launch(channel="chrome")
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


def test_search_box_focus_starts_downloading_the_index(page, base_url):
    page.goto(base_url + "/")
    expect(page.locator(".ep-item")).to_have_count(102)
    with page.expect_request(lambda r: r.url.endswith("/search_index.json"), timeout=5000):
        page.focus("#q")


def test_home_list_shows_errata_count_linking_to_errata_page(page, base_url):
    page.goto(base_url + "/")
    badge = page.locator(".ep-item", has_text="EP088").locator("a.ep-errata")
    expect(badge).to_have_text(re.compile(r"^勘误 \d+$"))
    badge.click()
    expect(page).to_have_url(re.compile(r"errata\.html#ep88$"))
    expect(page.locator("#ep88")).to_be_in_viewport()


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
    (TERMS, ".term"),
    (ERRATA, ".erratum"),
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


def test_term_index_groups_by_pinyin_and_links_into_transcript(page, base_url):
    page.goto(base_url + TERMS)
    assert page.locator(".term").count() > 3000
    page.locator(".letters a", has_text="L").click()
    expect(page.locator("#letter-L")).to_be_in_viewport()
    page.fill("#term-filter", "梁思成")
    term = page.locator(".term", has=page.locator(".kw", has_text=re.compile("^梁思成$")))
    expect(term.locator(".ep-count")).to_have_text(re.compile(r"^\d{2} 期$"))
    moment = term.locator("a.moment").first
    assert re.fullmatch(r"index\.html\?ep=\d+&t=\d+", moment.get_attribute("href"))
    moment.click()
    expect(page.locator(".transcript-seg.seek")).to_be_in_viewport()


def test_expanded_term_marks_each_episode_note(page, base_url):
    page.goto(base_url + TERMS)
    page.fill("#term-filter", "阿旃陀")
    term = page.locator(".term", has=page.locator(".kw", has_text=re.compile("^阿旃陀石窟$")))
    term.locator(".term-head").click()
    expect(term.locator(".detail")).to_contain_text("马哈拉施特拉")
    tag = term.locator(".detail .note b").first
    expect(tag).to_have_text("EP008")
    assert tag.evaluate("e => getComputedStyle(e).backgroundColor") != "rgba(0, 0, 0, 0)"


def test_term_index_sorts_by_episode_count_and_can_show_places_only(page, base_url):
    page.goto(base_url + TERMS + "?sort=count")
    counts = page.locator(".term .ep-count").evaluate_all("els => els.slice(0, 30).map(e => parseInt(e.textContent))")
    assert counts == sorted(counts, reverse=True) and counts[0] >= 20
    total = page.locator(".term").count()
    page.locator("#places-only").check()
    places = page.locator(".term:visible").count()
    assert 500 < places < total
    expect(page.locator(".term", has=page.locator(".kw", has_text=re.compile("^佛光寺$")))).to_be_visible()


def test_topic_notes_stay_on_episode_pages_but_not_in_term_index(page, base_url):
    annotations = json.loads((ROOT / "bixiaguan_transcripts/notes/annotations.json").read_text())["annotations"]
    topic = next(a for a in annotations if a.get("topic"))
    page.goto(base_url + TERMS)
    expect(page.locator(".term").first).to_be_visible()
    assert page.locator(".term .kw", has_text=re.compile("^" + re.escape(topic["keyword"]) + "$")).count() == 0
    ep = topic["episodes"][0]["ep"]
    assert topic["keyword"] in page.request.get(f"{base_url}/ep/{ep}.json").text()


def test_errata_page_groups_by_episode_and_filters(page, base_url):
    page.goto(base_url + ERRATA)
    assert page.locator(".erratum").count() > 350
    page.fill("#errata-filter", "崇庆寺")
    shown = page.locator(".erratum:visible")
    expect(shown).to_have_count(1)
    expect(page.locator(".ep-group:visible h2")).to_contain_text("EP088")
    link = shown.locator("a.moment")
    assert re.fullmatch(r"index\.html\?ep=88&t=\d+", link.get_attribute("href"))


def test_static_episode_page_reads_without_javascript(browser, base_url):
    ctx = browser.new_context(java_script_enabled=False)
    pg = ctx.new_page()
    pg.goto(base_url + "/episode/88.html")
    expect(pg.locator("h1")).to_contain_text("罗汉排行榜之长清灵岩寺")
    assert pg.locator(".seg").count() > 100
    expect(pg.locator(".errata li", has_text="崇庆寺")).to_be_visible()
    expect(pg.locator('a[href="../index.html?ep=88"]').first).to_be_visible()
    ctx.close()


def test_sitemap_lists_every_page_for_search_engines(page, base_url):
    sitemap = page.request.get(base_url + "/sitemap.xml").text()
    pages = re.findall(r"<loc>https://bixiaguan-archive\.github\.io/([^<]*)</loc>", sitemap)
    assert {f"episode/{n}.html" for n in range(1, 103)} <= set(pages)
    assert {"", "terms.html", "errata.html", "cast.html", "ancient-buildings-map.html"} <= set(pages)
    robots = page.request.get(base_url + "/robots.txt").text()
    assert "Sitemap: https://bixiaguan-archive.github.io/sitemap.xml" in robots


@pytest.mark.parametrize("path", ["/", "/cast.html", MAP, ERRATA])
def test_every_page_nav_reaches_term_index(page, base_url, path):
    page.goto(base_url + path)
    page.locator("nav a", has_text="索引").click()
    expect(page.locator(".term").first).to_be_visible()
