#!/usr/bin/env python3
"""fix_anchors.py — 修正勘误/附注的锚点与同期重复。

背景：网页端是按「在全文里搜 keyword」来挂锚点的（index.html），
所以 keyword 与该期正文写法不一致时，锚点会丢失或贴到错误位置。本脚本：

1. 为每条附注实例计算 `anchor`（该期正文里真实存在的字串）并写回；
2. 按 anchor 在正文中的真实位置校正 subtitle / timecode；
3. 勘误用 `original` 里能在正文对上的片段作 anchor；
4. 同一期同一 keyword 有多条实例时只保留首次出现（若有 note 则并到首条）。

用法：
    python3 tools/fix_anchors.py --report          # 只统计
    python3 tools/fix_anchors.py --write           # 写回 annotations.json
"""
import argparse
import difflib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "bixiaguan_transcripts"
NOTES = T / "notes" / "annotations.json"
REPORT = ROOT / "tools" / "anchor-report.txt"

SKIP = "《》·・‧\u00b7\u30fb \t\r\n\u3000"
GENERIC_SUFFIX = ("博物馆", "美术馆", "大学", "学院", "祠", "寺", "宫", "塔", "式", "柱式",
                  "城墙", "石刻", "收藏", "遗址", "石窟", "造像", "壁画", "图", "像")


def is_skip(ch):
    return ch in SKIP


def norm(s):
    return "".join(c for c in s if not is_skip(c))


def load_blocks(ep):
    p = sorted(T.glob(f"ep{ep:03d}_*.srt"))[0]
    out = []
    for ch in re.split(r"\n\n+", p.read_text(encoding="utf-8").strip()):
        ls = ch.strip().splitlines()
        if len(ls) >= 3 and "-->" in ls[1]:
            out.append([int(ls[0]), ls[1].split("-->")[0].strip(), "".join(ls[2:])])
    return out


class Ep:
    def __init__(self, ep):
        self.ep = ep
        self.blocks = load_blocks(ep)
        self.raw = "".join(b[2] for b in self.blocks)
        self.norm = norm(self.raw)
        self.to_raw = []
        self.norm_start = []
        pos = 0
        self.block_of_raw = []
        for i, b in enumerate(self.blocks):
            self.block_of_raw.extend([i] * len(b[2]))
        for ri, ch in enumerate(self.raw):
            if not is_skip(ch):
                self.to_raw.append(ri)
        self.index = {b[0]: i for i, b in enumerate(self.blocks)}

    def occurrences(self, needle):
        """返回 [(raw_start, raw_end, block_idx)]"""
        n = norm(needle)
        if not n:
            return []
        out = []
        start = 0
        while True:
            p = self.norm.find(n, start)
            if p < 0:
                break
            rs = self.to_raw[p]
            re_ = self.to_raw[p + len(n) - 1] + 1
            out.append((rs, re_, self.block_of_raw[rs]))
            start = p + 1
        return out

    def hint_block(self, subtitle):
        m = re.match(r"\s*(\d+)", str(subtitle or ""))
        if not m:
            return 0
        return self.index.get(int(m.group(1)), 0)


BARE = {"博物馆", "美术馆", "大学", "学院", "建筑", "展厅", "艺术", "文化", "遗址",
        "石窟", "图书馆", "公园", "城墙", "石刻", "造像", "壁画", "遗址群", "古城"}

WINDOW = 14
FUNC = "的了的在是把被而就也都还很不太这那其之等，。、（）「」"


def ok_fragment(s):
    """碎片不能只是虚词，否则锚到「的欣赏」这类无意义片段上。"""
    t = s.strip(FUNC)
    return len(t) >= 3


def trim_anchor(s, limit=40):
    if len(s) <= limit:
        return s
    cut = max(s.rfind("，", 0, limit), s.rfind("。", 0, limit), s.rfind("、", 0, limit))
    return s[: cut + 1] if cut >= 8 else s[:limit]


def candidate_strings(kw):
    """按可信度从高到低给出候选锚点字串：(text, rank)。

    rank 0 = 词本身；1 = 词的部件/去后缀核心；2 = 词的首尾片段（短而准，如「素和氏」→「素和」）；
    3 = 一般子串。原则：宁可短而准，也不要划住一大片无关内容。
    """
    if not kw:
        return
    yield kw, 0
    parts = [p for p in re.split(r"[·・‧\u00b7]", kw) if len(p) >= 2]
    if len(parts) > 1:
        for p in sorted(parts, key=len, reverse=True):
            yield p, 1
    core = kw
    for suf in GENERIC_SUFFIX:
        if core.endswith(suf) and len(core) - len(suf) >= 2:
            yield core[: -len(suf)], 1
            break
    # 首/尾片段：由长到短，最短 2 字（短词如「素和氏」「金冠」很需要这一档）
    if len(kw) >= 3:
        for size in range(min(len(kw) - 1, 8), 1, -1):
            if kw[:size].rstrip("的") in STOP or kw[-size:].rstrip("的") in STOP:
                continue
            if kw[:size][0] in EDGE_BAD or kw[:size][-1] in EDGE_BAD:
                continue
            if kw[-size:][0] in EDGE_BAD or kw[-size:][-1] in EDGE_BAD:
                continue
            yield kw[:size], 2
            yield kw[-size:], 2
    if len(kw) >= 5:
        for size in range(len(kw) - 1, 2, -1):
            for i in range(len(kw) - size + 1):
                sub = kw[i:i + size]
                if sub[0] in EDGE_BAD or sub[-1] in EDGE_BAD:
                    continue
                if set(sub) & set("个这那一的了是就都也还很不太在把被其之等和与及对从为以于并且但"):
                    continue
                yield sub, 3


BARE = {"博物馆", "美术馆", "大学", "学院", "建筑", "展厅", "艺术", "文化", "遗址",
        "石窟", "图书馆", "公园", "城墙", "石刻", "造像", "壁画", "遗址群", "古城"}

WINDOW = 14
FUNC = "的了的在是把被而就也都还很不太这那其之等，。、（）「」"
# 勘误锚点优先划在这些「可疑词」周围（数字、绝对化表述、否定）
HOT = re.compile(r"[0-9０-９]|最|唯一|第一|全都|全部|完全|从来|一直|一定|不是|没有|并非|都")


def ok_fragment(s):
    """碎片不能只是虚词，否则锚到「的欣赏」这类无意义片段上。"""
    t = s.strip(FUNC)
    return len(t) >= 2


def trim_anchor(s, limit=40):
    if len(s) <= limit:
        return s
    cut = max(s.rfind("，", 0, limit), s.rfind("。", 0, limit), s.rfind("、", 0, limit))
    return s[: cut + 1] if cut >= 8 else s[:limit]


def short_span(text, token_re, maxlen=14):
    """在 text 里围绕 token_re 命中的位置取一个短窗口（≤ maxlen）。"""
    m = token_re.search(text)
    if not m:
        return None
    half = maxlen // 2
    lo = max(0, m.start() - half)
    hi = min(len(text), lo + maxlen)
    lo = max(0, hi - maxlen)
    seg = text[lo:hi]
    for sep in ("，", "。", "、", "；", "："):
        i = seg.find(sep)
        if 0 <= i < len(seg) - 2:
            seg = seg[i + 1:]
    return seg.strip("，。、；： ") or None


STOP = {"宁波", "泉州", "中国", "日本", "韩国", "美国", "王朝", "时期", "时代", "文化", "艺术",
        "历史", "建筑", "博物馆", "展览", "研究", "问题", "地方", "地区", "城市", "人物",
        "作品", "一个", "这个", "什么", "情况", "内容", "部分", "著名", "重要", "主要", "特别",
        "非常", "当时", "后来", "影响", "关系", "特点", "传统", "发展", "开始", "出现", "认为",
        "表示", "方法", "方式", "过程", "结果", "原因", "条件", "基础", "中心", "代表", "意义",
        "价值", "作用", "国家", "民族", "宗教", "佛教", "道教", "绘画", "造像", "寺院", "佛像",
        "收藏", "文物", "发现", "记载", "文献", "资料", "学者", "先生", "老师", "主播", "本期",
        "节目", "我们", "他们", "以及", "包括", "通过", "由于", "因为", "所以", "但是", "而且",
        "前面", "后面", "里面", "外面", "上面", "下面", "中间", "以后", "以前", "之后", "之前",
        "这样", "那样", "怎么", "就是", "可以", "没有", "那个", "你们", "自己", "大家", "时候",
        "东西", "样子", "感觉", "印象", "名字", "大概", "关于", "对于", "其中", "同时", "这些", "那些",
        "比较", "影响", "文化", "日本", "时代", "方面", "基础", "背景", "条件", "阶段", "情况", "变化"}
EDGE_BAD = set("的了也而就之等和与及是在把被这那其对从为以于并且但")
FUNC_CHARS = set("的了在是把被而就也都还很不太这那其之等和与及以为上下面里中前后时候个一二三四五六七八九十")


def content_terms(extras):
    """从标签/解释/本期说明里抽出「这条附注真正在讲的那个词」。"""
    out = []
    for src in extras or []:
        for chunk in re.split(r"[的与和、：:（）()「」《》，。；？!！]", src or ""):
            chunk = chunk.strip()
            if 2 <= len(chunk) <= 12:
                out.append(chunk)
    seen, res = set(), []
    for t in sorted(out, key=len, reverse=True):
        if t in seen or t in STOP:
            continue
        if not any(ch not in FUNC_CHARS for ch in t):
            continue
        seen.add(t)
        res.append(t)
    return res


def choose(ep, kw, hint, extras=None):
    """返回 (anchor_text, block_idx, confidence)。优先就近、优先短而准。

    顺序：词本身 → 部件/去后缀 → 首尾片段 → 内容词（标签/本期说明里真正在讲的词）
    → 任意子串 → 就近模糊 → 整条字幕兜底。
    """
    best = None
    texts = list(candidate_strings(kw))
    # 内容词作为 rank 3（比任意子串更贴近这条附注真正在讲的东西）
    # 内容词/任意子串两档噪音较大，不再启用：改由下面的最长公共片段兜底

    for text, rank in texts:
        if rank > 0 and not ok_fragment(text):
            continue
        occ = ep.occurrences(text)
        if not occ:
            continue
        near = [o for o in occ if abs(o[2] - hint) <= WINDOW]
        pool = near if near else occ
        after = [o for o in pool if o[2] >= hint] or pool
        pick = after[0]
        key = (rank, 0 if near else 1, abs(pick[2] - hint), -len(text))
        if best is None or key < best[0]:
            best = (key, text, pick)
        if best[0][0] == 0 and best[0][1] == 0:
            break
    if best is None:
        blk = ep.blocks[hint] if ep.blocks else None
        if blk is None:
            return None, None, "none"
        return trim_anchor(blk[2], 18), hint, "block"
    (rank, far, dist, _), text, pick = best
    anchor = ep.raw[pick[0]:pick[1]]
    if rank > 0 and norm(anchor) in BARE:
        blk = ep.blocks[hint] if ep.blocks else None
        if blk is not None:
            return trim_anchor(blk[2], 18), hint, "block"
    conf = "high" if rank == 0 else ("mid" if far == 0 else "low")
    return anchor, pick[2], conf


QUOTED = re.compile(r"[「『\"“]([^」』\"”]{2,20})[」』\"”]|\*\*([^*]{2,20})\*\*|《([^》]{2,20})》")
# 勘误锚点优先划在这些「可疑词」周围（数字、绝对化表述）
HOT = re.compile(r"[0-9０-９]|最|唯一|第一|从来|一直|全都|完全")


def _terms(label, correct, original):
    """从标签/正确说明里抽出「被质疑的那个词」的候选。"""
    out = []
    for src in (label or "", correct or "", original or ""):
        for m in QUOTED.finditer(src):
            t = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            if 2 <= len(t) <= 20:
                out.append(t)
    # 标签形如「打虎亭汉墓的位置」「沙畹著作中文译名」→ 取「的」前的名词短语
    lab = (label or "").strip()
    for sep in ("的", "是", "（", "(", "：", ":"):
        i = lab.find(sep)
        if 4 <= i <= 14:
            out.append(lab[:i])
            break
    out = [t for t in out if t]
    # 出现在 original 里的（主播真说过的）优先，其次按长度
    out.sort(key=lambda t: (0 if (original and t in original) else 1, -len(t)))
    return out


def _fuzzy_span(ep, term, hint, minratio=0.6, minlen=4):
    """词项在正文里没有原样出现时，就近找相似窗（如「北华考古图谱」↔正文「华北考古图谱」）。"""
    lo = max(0, hint - WINDOW)
    hi = min(len(ep.blocks), hint + WINDOW + 1)
    if lo >= hi:
        return None
    base = sum(len(b[2]) for b in ep.blocks[:lo])
    text = ep.raw[base:base + sum(len(b[2]) for b in ep.blocks[lo:hi])]
    nt = norm(term)
    if len(nt) < minlen:
        return None
    best = None
    for size in range(max(minlen, len(nt) - 2), len(nt) + 3):
        for i in range(0, max(1, len(text) - size + 1)):
            w = text[i:i + size]
            nw = norm(w)
            if len(nw) < minlen:
                continue
            r = difflib.SequenceMatcher(None, nt, nw).ratio()
            if r >= minratio and (best is None or r > best[0]):
                best = (r, base + i, base + i + size)
    if best is None:
        return None
    # 向两侧扩到汉字词边界（如命中的是「考古图谱」，扩成正文实际的「华北考古图谱」）
    rs, re_ = best[1], best[2]
    CJK = re.compile(r"[\u4e00-\u9fff]")
    for _ in range(4):
        if rs - 1 >= 0 and CJK.match(ep.raw[rs - 1]):
            rs -= 1
        else:
            break
    for _ in range(4):
        if re_ < len(ep.raw) and CJK.match(ep.raw[re_]):
            re_ += 1
        else:
            break
    return (best[0], rs, re_)


def errata_anchor(ep, original, hint, label="", correct=""):
    """勘误锚点：优先划在「被质疑的那个词」上，而不是整句原文。"""
    for t in _terms(label, correct, original):
        occ = ep.occurrences(t)
        if not occ:
            fz = _fuzzy_span(ep, t, hint)
            if fz:
                return ep.raw[fz[1]:fz[2]], ep.block_of_raw[fz[1]], "fuzzy"
            continue
        near = [o for o in occ if abs(o[2] - hint) <= WINDOW]
        pool = near or occ
        after = [o for o in pool if o[2] >= hint] or pool
        return ep.raw[after[0][0]:after[0][1]], after[0][2], "quote"

    parts = [p.strip() for p in re.split(r"[……]+|\.\.\.", original or "") if p.strip()]
    parts.sort(key=len, reverse=True)
    for p in parts:
        p2 = p.strip("「」“”\"'，。、？！：；")
        if len(p2) < 4:
            continue
        occ = ep.occurrences(p2)
        if not occ:
            continue
        after = [o for o in occ if o[2] >= hint] or occ
        rs, re_, blk = after[0]
        text = ep.raw[rs:re_]
        span = short_span(text, HOT, 12) if len(text) > 16 else trim_anchor(text, 16)
        return span or trim_anchor(text, 16), blk, "high"

    return choose(ep, label or original, hint)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--force", action="store_true", help="重新推导全部锚点（默认沿用已能定位的）")
    args = ap.parse_args()

    d = json.loads(NOTES.read_text(encoding="utf-8"))
    EPS = {}
    def ep_of(n):
        if n not in EPS:
            EPS[n] = Ep(n)
        return EPS[n]

    stat = {"ann_total": 0, "ann_anchor_high": 0, "ann_anchor_mid": 0, "ann_anchor_low": 0,
            "ann_anchor_fuzzy": 0, "ann_anchor_block": 0, "ann_anchor_content": 0, "ann_anchor_quote": 0, "ann_unresolved": 0, "ann_dedup": 0, "ann_tc_moved": 0, "ann_kept": 0,
            "err_total": 0, "err_high": 0, "err_mid": 0, "err_block": 0, "err_unresolved": 0, "err_tc_moved": 0}
    review = []

    for a in d["annotations"]:
        kw = a.get("keyword") or a.get("label") or ""
        eps = a.get("episodes", [])

        # ── 同期去重：保留首次出现 ──
        def sub_num(e):
            m = re.match(r"\s*(\d+)", str(e.get("subtitle") or ""))
            return int(m.group(1)) if m else 10 ** 9
        eps_sorted = sorted(eps, key=lambda e: (e["ep"], sub_num(e)))
        keep = []
        for e in eps_sorted:
            prev = next((k for k in keep if k["ep"] == e["ep"]), None)
            if prev is not None:
                stat["ann_dedup"] += 1
                if not prev.get("note") and e.get("note"):
                    prev["note"] = e["note"]
                continue
            keep.append(e)
        a["episodes"] = keep

        for e in keep:
            stat["ann_total"] += 1
            ep = ep_of(e["ep"])
            hint = ep.hint_block(e.get("subtitle"))
            old_sub = e.get("subtitle")
            prev_a = e.get("anchor")
            if not args.force and prev_a and ep.occurrences(prev_a):
                stat["ann_kept"] = stat.get("ann_kept", 0) + 1
                continue
            anchor, blk, conf = choose(ep, kw, hint, [a.get("label"), e.get("note")])
            if anchor is None:
                stat["ann_unresolved"] += 1
                review.append(("ANN", e["ep"], kw, old_sub, "未解析"))
                continue
            stat["ann_anchor_" + conf] += 1
            e["anchor"] = anchor
            if blk is not None:
                new_num, new_tc = ep.blocks[blk][0], ep.blocks[blk][1]
                if str(old_sub) != str(new_num):
                    stat["ann_tc_moved"] += 1
                e["subtitle"] = str(new_num)
                e["timecode"] = new_tc
            if conf in ("low", "fuzzy", "block"):
                review.append(("ANN", e["ep"], kw, old_sub, f"{conf}:{anchor[:30]}"))

    for e in d.get("errata", []):
        stat["err_total"] += 1
        ep = ep_of(e["ep"])
        hint = ep.hint_block(e.get("subtitle"))
        old_sub = e.get("subtitle")
        anchor, blk, conf = errata_anchor(ep, e.get("original", ""), hint, e.get("label", ""), e.get("correct", ""))
        if anchor is None:
            stat["err_unresolved"] += 1
            review.append(("ERR", e["ep"], e.get("keyword"), old_sub, "未解析"))
            continue
        stat["err_" + conf] = stat.get("err_" + conf, 0) + 1
        e["anchor"] = anchor
        if blk is not None:
            new_num, new_tc = ep.blocks[blk][0], ep.blocks[blk][1]
            if str(old_sub) != str(new_num):
                stat["err_tc_moved"] += 1
            e["subtitle"] = str(new_num)
            e["timecode"] = new_tc
        if conf != "high":
            review.append(("ERR", e["ep"], e.get("keyword"), old_sub, f"{conf}:{anchor[:30]}"))

    print(json.dumps(stat, ensure_ascii=False, indent=1))
    lines = [f"{t}\tep{ep}\t{kw}\tsub={sub}\t{note}" for t, ep, kw, sub, note in review]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"需人工过目 {len(review)} 条 → {REPORT.relative_to(ROOT)}")

    if args.write:
        NOTES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已写回 {NOTES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
