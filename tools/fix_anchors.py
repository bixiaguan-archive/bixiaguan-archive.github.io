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


WINDOW = 14
FUNC = "的了的与和及之其等被把而就都也还很不太这个一上下里中时对从为以，。、（）「」"


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
    """按可信度从高到低给出候选锚点字串：(text, rank)。"""
    if not kw:
        return
    yield kw, 0
    parts = [p for p in re.split(r"[·・‧\u00b7]", kw) if len(p) >= 2]
    if len(parts) > 1:
        for p in sorted(parts, key=len, reverse=True):
            yield p, 1
    core = kw
    for suf in GENERIC_SUFFIX:
        if core.endswith(suf) and len(core) - len(suf) >= 3:
            yield core[: -len(suf)], 1
            break
    if len(kw) >= 5:
        for size in range(len(kw) - 1, 2, -1):
            for i in range(len(kw) - size + 1):
                yield kw[i:i + size], 2


def choose(ep, kw, hint):
    """返回 (anchor_text, block_idx, confidence)。优先就近匹配。"""
    best = None
    for text, rank in candidate_strings(kw):
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
        # 兜底：锚定该时间码所在的整条字幕
        blk = ep.blocks[hint] if ep.blocks else None
        if blk is None:
            return None, None, "none"
        return blk[2], hint, "block"
    (rank, far, dist, _), text, pick = best
    anchor = ep.raw[pick[0]:pick[1]]
    conf = "high" if rank == 0 else ("mid" if far == 0 else "low")
    return anchor, pick[2], conf


def errata_anchor(ep, original, hint, label=""):
    parts = [p.strip() for p in re.split(r"[……]+|\.\.\.", original or "") if p.strip()]
    parts.sort(key=len, reverse=True)
    for p in parts:
        p2 = p.strip("「」“”\"'，。、？！：；")
        if len(p2) < 4:
            continue
        occ = ep.occurrences(p2)
        if occ:
            after = [o for o in occ if o[2] >= hint]
            pick = after[0] if after else occ[0]
            return trim_anchor(ep.raw[pick[0]:pick[1]]), pick[2], "high"
    return choose(ep, label or original, hint)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    d = json.loads(NOTES.read_text(encoding="utf-8"))
    EPS = {}
    def ep_of(n):
        if n not in EPS:
            EPS[n] = Ep(n)
        return EPS[n]

    stat = {"ann_total": 0, "ann_anchor_high": 0, "ann_anchor_mid": 0, "ann_anchor_low": 0,
            "ann_anchor_fuzzy": 0, "ann_anchor_block": 0, "ann_unresolved": 0, "ann_dedup": 0, "ann_tc_moved": 0,
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
            anchor, blk, conf = choose(ep, kw, hint)
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
        anchor, blk, conf = errata_anchor(ep, e.get("original", ""), hint, e.get("label", ""))
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
