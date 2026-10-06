#!/usr/bin/env python3
"""
asr_scan.py — ASR 可疑片段扫描

思路：ASR 错误通常是「罕见写法 + 常见词的同音/近形变体」。
对语料做 n-gram 统计，找出「罕见 n-gram」与「高频 n-gram」只差一个字的情况，
按可疑度排序输出，供人工核对后写入 fix_epNNN.py。

用法：
    python3 tools/asr_scan.py                 # 全语料，输出报告到 tools/asr_candidates.md
    python3 tools/asr_scan.py --ep 12         # 只看某一期
    python3 tools/asr_scan.py --min-freq 8 --max-rare 2 --n 3,4,5
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS = ROOT / "bixiaguan_transcripts"
NOTES_JSON = TRANSCRIPTS / "notes" / "annotations.json"
REPORT = Path(__file__).resolve().parent / "asr_candidates.md"

HAN = re.compile(r"[一-鿿]")
HAN_SEQ = re.compile(r"[一-鿿]+")


def load_corpus(only_ep=None):
    """返回 {ep: text}，text 为去掉序号与时间码后的连续文本。"""
    corpus = {}
    for p in sorted(TRANSCRIPTS.glob("ep*.srt")):
        m = re.match(r"ep(\d+)_", p.name)
        if not m:
            continue
        ep = int(m.group(1))
        if only_ep and ep != only_ep:
            continue
        text = p.read_text(encoding="utf-8")
        text = re.sub(r"\n?\d+\n\d\d:\d\d:\d\d,\d\d\d --> \d\d:\d\d:\d\d,\d\d\d\n", " ", text)
        corpus[ep] = re.sub(r"\s+", "", text)
    return corpus


def gram_positions(text, n):
    for i in range(len(text) - n + 1):
        g = text[i:i + n]
        if HAN_SEQ.fullmatch(g):
            yield i, g


def scan(corpus, ns=(3, 4, 5), min_freq=6, max_rare=2):
    counts = Counter()
    for ep, text in corpus.items():
        for n in ns:
            for _, g in gram_positions(text, n):
                counts[g] += 1
    # 高频 gram 的通配模式索引
    pattern_index = defaultdict(list)
    for g, c in counts.items():
        if c >= min_freq:
            for j in range(len(g)):
                pattern_index[g[:j] + "." + g[j + 1:]].append(g)

    candidates = []
    seen = set()
    candidate_rare = set()
    for g, c in counts.items():
        if c > max_rare:
            continue
        for j in range(len(g)):
            pat = g[:j] + "." + g[j + 1:]
            for alt in pattern_index.get(pat, ()):
                if alt == g:
                    continue
                key = (g, alt)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({
                    "rare": g, "rare_count": c,
                    "alt": alt, "alt_count": counts[alt],
                    "diff_pos": j,
                })
                candidate_rare.add(g)

    # 只为真正可疑的罕见 gram 记录位置（省内存与时间）
    positions = defaultdict(list)
    for g in candidate_rare:
        rx = re.compile(re.escape(g))
        for ep, text in corpus.items():
            for m in rx.finditer(text):
                positions[g].append((ep, m.start()))
    for c in candidates:
        c["eps"] = sorted({ep for ep, _ in positions[c["rare"]]})
    return candidates, counts, positions, corpus


def context(corpus, gram, width=18, limit=3):
    out = []
    for ep, text in corpus.items():
        for m in re.finditer(re.escape(gram), text):
            s = max(0, m.start() - width)
            out.append(f"ep{ep:03d} …{text[s:m.end() + width]}…")
            if len(out) >= limit:
                return out
    return out


def known_term_candidates(corpus, counts, max_rare=2, min_term_freq=3):
    """附注索引里的术语，如果在语料中出现「差一个字」的罕见变体，优先报警。

    收紧条件以减少噪音：术语本身在语料中出现 min_term_freq 次以上；
    变体出现次数 <= max_rare；且变体所在期次里术语也出现过（同集内混用）。
    """
    if not NOTES_JSON.exists():
        return []
    data = json.loads(NOTES_JSON.read_text(encoding="utf-8"))
    terms = set()
    for a in data.get("annotations", []):
        for t in (a.get("keyword", ""), a.get("label", "")):
            t = "".join(HAN.findall(t))
            if 3 <= len(t) <= 8:
                terms.add(t)

    ep_text = corpus
    hits = {}
    for term in terms:
        if counts.get(term, 0) < min_term_freq:
            continue
        term_eps = {ep for ep, t in ep_text.items() if term in t}
        for j in range(len(term)):
            rx = re.compile(term[:j] + "." + term[j + 1:])
            for ep, text in ep_text.items():
                for m in rx.finditer(text):
                    g = m.group(0)
                    if g == term or counts.get(g, 0) > max_rare:
                        continue
                    if ep not in term_eps:
                        continue
                    key = (g, term)
                    if key in hits:
                        hits[key]["eps"].append(ep)
                    else:
                        hits[key] = {
                            "rare": g, "rare_count": counts.get(g, 0),
                            "alt": term, "alt_count": counts.get(term, 0),
                            "eps": [ep],
                        }
    return list(hits.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", type=int)
    ap.add_argument("--min-freq", type=int, default=6)
    ap.add_argument("--max-rare", type=int, default=2)
    ap.add_argument("--n", default="3,4,5")
    ap.add_argument("--top", type=int, default=400)
    args = ap.parse_args()
    ns = tuple(int(x) for x in args.n.split(","))

    corpus = load_corpus(args.ep)
    candidates, counts, positions, corpus = scan(corpus, ns, args.min_freq, args.max_rare)
    # 可疑度：罕见词越短、高频替代词越常见，越可疑
    candidates.sort(key=lambda c: (-len(c["rare"]), -c["alt_count"], c["rare_count"]))

    term_hits = known_term_candidates(corpus, counts, max_rare=args.max_rare)
    term_hits.sort(key=lambda c: (-c["alt_count"], c["rare_count"]))
    term_pairs = {(h["rare"], h["alt"]) for h in term_hits}
    candidates = [c for c in candidates if (c["rare"], c["alt"]) not in term_pairs]

    lines = ["# ASR 可疑候选（自动生成，需人工核对）", ""]
    lines.append(f"语料：{len(corpus)} 期；参数 min_freq={args.min_freq} max_rare={args.max_rare} n={ns}")
    lines.append("")
    lines.append("## 一、附注术语的近似变体（最高优先级）")
    lines.append("")
    for h in term_hits[:args.top]:
        lines.append(f"- `{h['rare']}`（{h['rare_count']} 次）→ 疑似 `{h['alt']}`（{h['alt_count']} 次）｜期次 {h['eps']}")
        for c in context(corpus, h["rare"], limit=2):
            lines.append(f"    - {c}")
    lines.append("")
    lines.append("## 二、罕见 n-gram 与高频 n-gram 一字之差")
    lines.append("")
    for c in candidates[:args.top]:
        lines.append(f"- `{c['rare']}`（{c['rare_count']}）→ `{c['alt']}`（{c['alt_count']}）｜期次 {c['eps']}")
        for ctx in context(corpus, c["rare"], limit=2):
            lines.append(f"    - {ctx}")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"术语近似变体 {len(term_hits)} 条；n-gram 候选 {len(candidates)} 条")
    print(f"报告：{REPORT}")


if __name__ == "__main__":
    main()
