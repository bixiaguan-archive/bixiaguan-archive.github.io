#!/usr/bin/env python3
"""scan_one.py — 为单期生成 ASR 可疑候选报告，输出到 tools/candidates/epNNN.md

用法：python3 tools/scan_one.py 78 [79 ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asr_scan  # noqa: E402

OUT = Path(__file__).resolve().parent / "candidates"


def one(ep, min_freq=4, max_rare=2, ns=(3, 4, 5), top=200):
    corpus = asr_scan.load_corpus(ep)
    candidates, counts, positions, corpus = asr_scan.scan(corpus, ns, min_freq, max_rare)
    candidates.sort(key=lambda c: (-len(c["rare"]), -c["alt_count"], c["rare_count"]))
    term_hits = asr_scan.known_term_candidates(corpus, counts, max_rare=max_rare)
    term_hits.sort(key=lambda c: (-c["alt_count"], c["rare_count"]))
    term_pairs = {(h["rare"], h["alt"]) for h in term_hits}
    candidates = [c for c in candidates if (c["rare"], c["alt"]) not in term_pairs]

    lines = [f"# ep{ep:03d} ASR 可疑候选（自动生成，需人工核对）", ""]
    lines.append(f"参数 min_freq={min_freq} max_rare={max_rare} n={ns}")
    lines.append("")
    lines.append("## 一、附注术语的近似变体（最高优先级）")
    lines.append("")
    for h in term_hits[:top]:
        lines.append(f"- `{h['rare']}`（{h['rare_count']} 次）→ 疑似 `{h['alt']}`（{h['alt_count']} 次）")
        for c in asr_scan.context(corpus, h["rare"], limit=3):
            lines.append(f"    - {c}")
    lines.append("")
    lines.append("## 二、罕见 n-gram 与高频 n-gram 一字之差")
    lines.append("")
    for c in candidates[:top]:
        lines.append(f"- `{c['rare']}`（{c['rare_count']}）→ `{c['alt']}`（{c['alt_count']}）")
        for ctx in asr_scan.context(corpus, c["rare"], limit=3):
            lines.append(f"    - {ctx}")
    OUT.mkdir(exist_ok=True)
    p = OUT / f"ep{ep:03d}.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ep{ep:03d}: 术语变体 {len(term_hits)}；n-gram {len(candidates)} → {p}")


if __name__ == "__main__":
    eps = [int(x) for x in sys.argv[1:]] or list(range(78, 103))
    for e in eps:
        one(e)
