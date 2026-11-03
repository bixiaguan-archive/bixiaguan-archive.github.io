#!/opt/homebrew/bin/python3.12
"""
解析所有 SRT 文件，生成：
- search_index.json：全部期的 {ep, title, ytId, segments}，供全文检索
- ep/<期号>.json：单期 segments + 该期勘误与附注，供全文浏览
- map.json：访古地图的地点与路线，合并注释里的简介、期数与时间点
- terms.json + terms/<首字母>.json / errata.json / counts.json：词条索引、勘误总表、首页每期勘误数
- episode/<期号>.html、sitemap.xml、robots.txt：供搜索引擎收录的单期静态页与站点地图
"""
import html, json, re, shutil
from pathlib import Path

from pypinyin import lazy_pinyin

TRANSCRIPTS_DIR = Path(__file__).parent / "bixiaguan_transcripts"
SITE_DIR = Path(__file__).parent / "bixiaguan_search"
OUTPUT = SITE_DIR / "search_index.json"
EP_DIR = SITE_DIR / "ep"

# ── Notes 读取（从结构化的 JSON 文件）─────────
NOTES_JSON = TRANSCRIPTS_DIR / "notes" / "annotations.json"
MAP_DIR = TRANSCRIPTS_DIR / "map"

def _time_to_sec(t):
    """hh:mm:ss(.fff|,fff|:ff) -> int seconds"""
    parts = t.replace(",", ":").split(":")
    h = int(parts[0])
    m = int(parts[1])
    s = int(parts[2])  # ignore frames/milliseconds if present
    return h*3600 + m*60 + s

_all_notes_pre = []
notes_data = json.loads(NOTES_JSON.read_text(encoding="utf-8"))
# 遍历 annotations（附注）
for a in notes_data.get("annotations", []):
    for ep_entry in a.get("episodes", []):
        _all_notes_pre.append({
            "type": "annotation",
            "ep": ep_entry["ep"],
            "subtitle": str(ep_entry.get("subtitle", "")),
            "time": ep_entry.get("timecode", "00:00:00"),
            "start": _time_to_sec(ep_entry.get("timecode", "00:00:00")),
            "label": a.get("label", ""),
            "keyword": a.get("keyword", ""),
            "explanation": a.get("explanation", ""),
            "source": a.get("source", ""),
            "note": ep_entry.get("note", ""),
            "anchor": ep_entry.get("anchor", ""),
        })
# 遍历 errata（勘误）
for e in notes_data.get("errata", []):
    _all_notes_pre.append({
        "type": "errata",
        "ep": e["ep"],
        "subtitle": str(e.get("subtitle", "")),
        "time": e.get("timecode", "00:00:00"),
        "start": _time_to_sec(e.get("timecode", "00:00:00")),
        "label": e.get("label", ""),
        "keyword": e.get("keyword", ""),
        "original": e.get("original", ""),
        "correct": e.get("correct", ""),
        "source": e.get("source", ""),
        "status": "fact-error",
        "anchor": e.get("anchor", ""),
    })

# YouTube ID 映射
YOUTUBE_IDS = {
    1:"a1cjeKAHNAc",2:"lOyDBOMwKJE",3:"Ghi60u-r5XA",4:"0j1I4NcU-V0",
    5:"j4Dn0NKE3TI",6:"I8MIKJKHWqE",7:"YSN0G0CtFTg",8:"9OIuV1gD2No",
    9:"QYihTxjz5H0",10:"WRy8gEdZKMw",11:"jhYXV5jMtVQ",12:"rSiHOLYBFus",
    13:"upM4vvDv-ho",14:"UQEWCZ4fOB8",15:"b19ywAH41vM",16:"xZKdhmqvv9A",
    17:"1Fm84oGVZuc",18:"YEnSTIUpduY",19:"0OabCg0gIJI",20:"O78rVjK8KeQ",
    21:"dgpZFWXz9PU",22:"n0aLiiEqwvM",23:"rvo0jyNL3Dw",24:"kO7pqbOPeO4",
    25:"JgOkcKVbhUY",26:"aLO3VD_PDW0",27:"5lf04P8QB3M",28:"T1UakFlpIEg",
    29:"mFg8qqokqA8",30:"8kNI2_6O46E",31:"rr8iCi9idJM",32:"f9k0ysPosyc",
    33:"O_S1E_t5udU",34:"FLQ35qaQV5I",35:"48toC2ZLj6I",36:"XiEwReNL1lw",
    37:"Me6RTgsGSh0",38:"Wg_g7HzG0A4",39:"dqYOmbJNBZs",40:"GU1KxRCuEq8",
    41:"ZHZrLpDCb48",42:"W32Fty_XMWI",43:"gE4VIrIDrfU",44:"iY3rrmsSE9k",
    45:"7Vqrh-DQ360",46:"zXUcCTe9Ri8",47:"E0FwWan-v30",48:"RZAOb2Owvvg",
    49:"CjdIh9_Rkjc",50:"O9xZcMl-Yso",51:"ddS0zBHEdEM",52:"q42oqgahd9o",
    53:"tNLAS_xjViU",54:"u2V9X_l_28M",55:"xubjQ7YQFME",56:"_2XyJ6Mil00",
    57:"_pDYsz8AkxE",58:"hBMlpC38lVM",59:"9qtD0p6mu5U",60:"DWEHzTBVJsU",
    61:"tqCVtg_Z4Wg",62:"9z8dTsdl1g4",63:"ulq0uENqx6w",64:"cOaimK_L6TU",
    65:"p0qMuI1UFNg",66:"qts4r8aIshM",67:"YcH4fM8Rts8",68:"K1gLC-ZfoqI",
    69:"Kg60nPu2GyU",70:"n0ivvTL3A5c",71:"35xkxb4VrvE",72:"cK497gR97K4",
    73:"lqjevDBu4cg",74:"ymRg4GvaAO4",75:"FRnNX46Oixw",76:"oSJnyWW7mSM",
    77:"K9clR0cXjao",78:"0wWsiw_VwrY",79:"0U7wm-qSqvI",80:"DLNBV6W0rbQ",
    81:"Rw8RCEav_w8",82:"SH-aP5GUQy0",83:"vnQUpfaHu54",84:"G-xyPOtDCq8",
    85:"EL5MplyleV8",86:"f0i3TMYnUdo",87:"MSC1oZR-2cs",88:"7BbWQLtczIE",
    89:"n8OtIeDGkyo",90:"T0KiJznYWzw",91:"5MiP-Z3V-rM",92:"aQtIpn3EDlc",
    93:"ypeypExKefw",94:"YAU1ne0hYg8",95:"lKoMSHw0aIk",96:"gIT85HsBLxw",
    97:"XmZM-jPnuKk",98:"urgrUGeTaZc",99:"S8vnb4nJPqs",100:"-7DDF3Ctyk8",
    101:"ecz__qjit6Q",102:"lg77UlI4ohg",
}

def srt_time_to_seconds(t):
    """00:01:23,456 -> 83.456"""
    h, m, s = t.split(":")
    s, ms = s.split(",")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

def parse_srt(path):
    """解析 SRT，返回 [{start, end, text}, ...]，每条约合并4个字幕块。

    合并逻辑：达到约50字或句末标点时断开，配对符号（《》""（）「」）未闭合时推迟断开。
    跨段 keyword 由前端处理。
    """
    MAX_BUF = 300
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r'\n\n+', text.strip())
    raw = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        time_match = re.match(r'(\S+)\s*-->\s*(\S+)', lines[1])
        if not time_match:
            continue
        start = srt_time_to_seconds(time_match.group(1))
        end   = srt_time_to_seconds(time_match.group(2))
        txt   = "".join(lines[2:])
        raw.append({"start": start, "end": end, "text": txt})

    PAIR_OPEN = set('《“（「『')
    PAIR_CLOSE = set('》”）」』')

    def has_unclosed_pair(t):
        depth = 0
        for ch in t:
            if ch in PAIR_OPEN: depth += 1
            elif ch in PAIR_CLOSE: depth = max(0, depth - 1)
        return depth > 0

    merged = []
    buf_text, buf_start, buf_end = "", None, None
    for r in raw:
        if buf_start is None:
            buf_start = r["start"]
        buf_text += r["text"]
        buf_end = r["end"]
        if len(buf_text) >= 50 or r["text"].endswith(("。", "？", "！", "…")):
            if has_unclosed_pair(buf_text) and len(buf_text) < MAX_BUF:
                continue
            merged.append({"start": buf_start, "end": buf_end, "text": buf_text})
            buf_text, buf_start, buf_end = "", None, None
    if buf_text:
        merged.append({"start": buf_start, "end": buf_end, "text": buf_text})

    # 标点前移：segment 不应以句读/闭括号开头，移到上一段末尾
    LEADING_PUNCT = set('，。、；：？！…》）」』】〉"’')
    for i in range(1, len(merged)):
        cur = merged[i]
        prev = merged[i - 1]
        strip_len = 0
        for ch in cur["text"]:
            if ch in LEADING_PUNCT:
                strip_len += 1
            else:
                break
        if strip_len > 0:
            prev["text"] += cur["text"][:strip_len]
            cur["text"] = cur["text"][strip_len:]

    return merged

episodes = []
srt_files = sorted(TRANSCRIPTS_DIR.glob("ep*.srt"))
for srt_path in srt_files:
    m = re.match(r'ep(\d+)_(.+)\.srt', srt_path.name)
    if not m:
        continue
    ep_num = int(m.group(1))
    title  = m.group(2)
    yt_id  = YOUTUBE_IDS.get(ep_num, "")
    segments = parse_srt(srt_path)
    episodes.append({
        "ep": ep_num,
        "title": title,
        "ytId": yt_id,
        "segments": segments,
    })
    print(f"  ep{ep_num:03d} {title}  ({len(segments)} 段)")

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding="utf-8")

write_json(OUTPUT, [
    {"ep": e["ep"], "title": e["title"], "ytId": e["ytId"], "s": [[int(seg["start"]), seg["text"]] for seg in e["segments"]]}
    for e in episodes
])
size_mb = OUTPUT.stat().st_size / 1024 / 1024
print(f"\n✅ 索引已生成: {OUTPUT}  ({size_mb:.1f} MB, {len(episodes)} 期)")

# ── 单期文件 ep/<期号>.json：转录 + 该期注释 ─────────────────────────
notes_by_ep = {}
for n in _all_notes_pre:
    notes_by_ep.setdefault(n["ep"], []).append(n)
shutil.rmtree(EP_DIR, ignore_errors=True)
EP_DIR.mkdir()
for ep in episodes:
    write_json(EP_DIR / f"{ep['ep']}.json", {**ep, "notes": notes_by_ep.get(ep["ep"], [])})
errata_count = sum(1 for n in _all_notes_pre if n["type"] == "errata")
annot_count = sum(1 for n in _all_notes_pre if n["type"] == "annotation")
print(f"✅ 单期文件已生成: {EP_DIR}/  （勘误 {errata_count} 条，附注 {annot_count} 条）")

# ── 访古地图 map.json：人工维护的地点与路线 + 注释里的简介、期数与时间点 ──
annotations_by_keyword = {a["keyword"]: a for a in notes_data["annotations"]}
episode_titles = {ep["ep"]: ep["title"] for ep in episodes}
places = json.loads((MAP_DIR / "places.json").read_text(encoding="utf-8"))
routes = json.loads((MAP_DIR / "routes.json").read_text(encoding="utf-8"))
map_errors = []
map_places = []
for p in places:
    moments = {}
    for ref in p["annotations"]:
        keyword, eps = (ref, None) if isinstance(ref, str) else (ref["keyword"], set(ref["eps"]))
        if keyword not in annotations_by_keyword:
            map_errors.append(f"{p['name']}：注释词条不存在「{keyword}」")
            continue
        for e in annotations_by_keyword[keyword]["episodes"]:
            if e["ep"] not in episode_titles:
                map_errors.append(f"{p['name']}：注释「{keyword}」引用了不存在的第 {e['ep']} 期")
            if eps is None or e["ep"] in eps:
                moments.setdefault((e["ep"], _time_to_sec(e.get("timecode", "00:00:00"))), e.get("note", ""))
    if not moments:
        map_errors.append(f"{p['name']}：没有关联到任何一期")
        continue
    first = p["annotations"][0]
    primary = annotations_by_keyword[first if isinstance(first, str) else first["keyword"]]
    map_places.append({
        **{k: p[k] for k in ("name", "aliases", "loc", "era", "band", "type", "lost", "lat", "lng", "coordSource")},
        "desc": primary["explanation"],
        "source": primary["source"],
        "episodes": [{"ep": ep, "t": t, "note": note} for (ep, t), note in sorted(moments.items())],
    })
place_names = {p["name"] for p in map_places}
for r in routes:
    for stop in r["stops"]:
        if stop not in place_names:
            map_errors.append(f"路线「{r['name']}」的站点不在地点表里：{stop}")
    for cover in (SITE_DIR / "route-covers" / r["cover"], SITE_DIR / "route-covers" / "thumb" / r["cover"]):
        if not cover.is_file():
            map_errors.append(f"路线「{r['name']}」的封面文件缺失：{cover.relative_to(SITE_DIR)}")
if map_errors:
    raise SystemExit("❌ 访古地图数据有误：\n" + "\n".join(map_errors))
write_json(SITE_DIR / "map.json", {"places": map_places, "routes": routes, "titles": episode_titles})
print(f"✅ 访古地图已生成: {SITE_DIR / 'map.json'}  （{len(map_places)} 处地点，{len(routes)} 条路线）")

# ── 词条索引：terms.json 是列表（词条、首字母、是否地点、各期时间点），
#    terms/<首字母>.json 是展开时才加载的简介、出处与各期备注；被访古地图引用的词条标为地点
place_keywords = {ref if isinstance(ref, str) else ref["keyword"] for p in places for ref in p["annotations"]}

def pinyin_key(text):
    text = text.lstrip("《〈「『“\"'（(【[ ")
    return "".join(lazy_pinyin(text)).lower()

def label_core(label):
    return re.sub(r"[（(][^）)]*[）)]", "", re.sub(r"^本期[：:]", "", label)).strip()

by_keyword = {a["keyword"] for a in notes_data["annotations"]}
seen_labels, dup_errors = {}, []
for a in notes_data["annotations"]:
    core = label_core(a["label"])
    if not core:
        continue
    if core != a["keyword"] and core in by_keyword:
        dup_errors.append(f"「{a['keyword']}」的标签就是另一词条「{core}」")
    if core in seen_labels:
        dup_errors.append(f"「{a['keyword']}」与「{seen_labels[core]}」标签相同：{core}")
    seen_labels.setdefault(core, a["keyword"])
if dup_errors:
    raise SystemExit("❌ 词条重复，请合并：\n" + "\n".join(dup_errors))

terms, term_details = [], {}
for a in sorted(notes_data["annotations"], key=lambda a: pinyin_key(a["keyword"])):
    key = pinyin_key(a["keyword"])
    letter = key[0].upper() if key[:1].isascii() and key[:1].isalpha() else "#"
    moments = sorted({(e["ep"], _time_to_sec(e.get("timecode", "00:00:00"))): e.get("note", "") for e in a["episodes"]}.items())
    terms.append({"k": a["keyword"], "l": a["label"], "L": letter, "p": a["keyword"] in place_keywords,
                  "m": [[ep, sec] for (ep, sec), _ in moments]})
    term_details.setdefault(letter, {})[a["keyword"]] = [a["explanation"], a["source"], [note for _, note in moments]]
write_json(SITE_DIR / "terms.json", {"titles": episode_titles, "terms": terms})
TERMS_DIR = SITE_DIR / "terms"
shutil.rmtree(TERMS_DIR, ignore_errors=True)
TERMS_DIR.mkdir()
for letter, details in term_details.items():
    write_json(TERMS_DIR / f"{'_' if letter == '#' else letter}.json", details)
print(f"✅ 词条索引已生成: {SITE_DIR / 'terms.json'}  （{len(terms)} 条，其中地点 {sum(t['p'] for t in terms)} 条）")

# ── 勘误总表 errata.json 与首页每期勘误数 counts.json ──────────────────
errata = sorted(
    ({"ep": e["ep"], "t": _time_to_sec(e.get("timecode", "00:00:00")), "l": e["label"],
      "o": e.get("original", ""), "c": e.get("correct", ""), "s": e.get("source", "")}
     for e in notes_data["errata"]),
    key=lambda e: (e["ep"], e["t"]))
write_json(SITE_DIR / "errata.json", {"titles": episode_titles, "errata": errata})
counts = {}
for e in errata:
    counts[e["ep"]] = counts.get(e["ep"], 0) + 1
write_json(SITE_DIR / "counts.json", counts)
print(f"✅ 勘误总表已生成: {SITE_DIR / 'errata.json'}  （{len(errata)} 条）")

# ── 单期静态页 episode/<期号>.html + sitemap.xml + robots.txt ──────────────
SITE_URL = "https://bixiaguan-archive.github.io/"
STATIC_DIR = SITE_DIR / "episode"
meta = {m["ep"]: m for m in json.loads((SITE_DIR / "episodes.json").read_text(encoding="utf-8"))}
esc = html.escape

def clock(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"

STATIC_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EP{n:03d} {title} · 壁下观</title>
<meta name="description" content="{summary}">
<style>
body {{ font-family: 'Noto Serif SC', 'Songti SC', 'SimSun', Georgia, serif; background: #faf8f5; color: #2c2c2c; margin: 0; line-height: 1.8; }}
nav {{ text-align: center; padding: 1rem; border-bottom: 1px solid #e8e2da; background: #fdfcfa; }}
nav a {{ color: #666; text-decoration: none; margin: 0 .8rem; font-size: .9rem; }}
nav a:hover {{ color: #c44; }}
main {{ max-width: 760px; margin: 0 auto; padding: 1.5rem 1rem 3rem; overflow-wrap: anywhere; }}
h1 {{ font-size: 1.5rem; font-weight: 600; }}
h2 {{ font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #e8e2da; }}
.meta, .pager {{ color: #888; font-size: .9rem; }}
.desc {{ white-space: pre-line; }}
a {{ color: #a33; }}
.seg a {{ color: #999; font-size: .8rem; margin-right: .5rem; text-decoration: none; font-family: monospace; }}
.errata li {{ margin-bottom: .6rem; }}
</style>
</head>
<body>
<nav><a href="../index.html">首页</a><a href="../terms.html">索引</a><a href="../errata.html">勘误</a><a href="../cast.html">登场人物</a><a href="../ancient-buildings-map.html">访古地图</a></nav>
<main>
<h1>EP{n:03d} {title}</h1>
<p class="meta">{date}{cast} · <a href="../index.html?ep={n}">交互式全文浏览</a> · <a href="https://www.youtube.com/watch?v={yt}">YouTube</a></p>
<p class="desc">{desc}</p>
{errata}<h2>全文</h2>
{segments}
<p class="pager">{pager}</p>
</main>
</body>
</html>
"""

shutil.rmtree(STATIC_DIR, ignore_errors=True)
STATIC_DIR.mkdir()
errata_by_ep = {}
for e in errata:
    errata_by_ep.setdefault(e["ep"], []).append(e)
ep_nums = [e["ep"] for e in episodes]
for i, ep in enumerate(episodes):
    n, m = ep["ep"], meta[ep["ep"]]
    desc = "\n".join(l for l in m["description"].split("\n") if "listennotes.com" not in l).strip()
    err = errata_by_ep.get(n, [])
    err_html = ("<section class=\"errata\"><h2>勘误</h2><ul>" + "".join(
        f"<li><a href=\"../index.html?ep={n}&amp;t={e['t']}\">{clock(e['t'])}</a> <b>{esc(e['l'])}</b>：{esc(e['c'])}</li>" for e in err)
        + "</ul></section>\n") if err else ""
    pager = []
    if i > 0:
        pager.append(f"<a href=\"{ep_nums[i - 1]}.html\">← 上一期</a>")
    if i + 1 < len(ep_nums):
        pager.append(f"<a href=\"{ep_nums[i + 1]}.html\">下一期 →</a>")
    (STATIC_DIR / f"{n}.html").write_text(STATIC_PAGE.format(
        n=n, title=esc(ep["title"]), yt=ep["ytId"], date=esc(m["date"]),
        summary=esc(re.sub(r"\s+", " ", desc)[:150]), desc=esc(desc),
        cast=(" · " + "、".join(esc(c["name"]) for c in m["cast"])) if m["cast"] else "",
        errata=err_html, pager=" · ".join(pager),
        segments="\n".join(f"<p class=\"seg\"><a href=\"../index.html?ep={n}&amp;t={int(s['start'])}\">{clock(s['start'])}</a>{esc(s['text'])}</p>" for s in ep["segments"]),
    ), encoding="utf-8")

pages = ["", "terms.html", "errata.html", "cast.html", "ancient-buildings-map.html"] + [f"episode/{n}.html" for n in ep_nums]
(SITE_DIR / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"<url><loc>{SITE_URL}{p}</loc></url>\n" for p in pages) + "</urlset>\n", encoding="utf-8")
(SITE_DIR / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
print(f"✅ 单期静态页已生成: {STATIC_DIR}/  （{len(episodes)} 页），sitemap.xml 共 {len(pages)} 个地址")
