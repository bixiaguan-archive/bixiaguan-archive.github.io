#!/usr/bin/env python3
"""
srt_dump.py — 把某一期 SRT 按字幕号打印成便于人工校读的连续文本。

用法：
    python3 tools/srt_dump.py 2                 # ep002 全文（按字幕号分组）
    python3 tools/srt_dump.py 2 --from 1 --to 300
    python3 tools/srt_dump.py 2 --chars 6000    # 每次输出的字符预算（默认 6000）
    python3 tools/srt_dump.py 2 --grep 响堂山    # 只看含关键词的上下文

输出每段前标注字幕号区间与时间码，便于后续 apply_fixes.py 定位。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS = ROOT / "bixiaguan_transcripts"


def find_srt(ep):
    for p in sorted(TRANSCRIPTS.glob(f"ep{ep:03d}_*.srt")):
        return p
    raise SystemExit(f"找不到 ep{ep:03d}")


def blocks(ep):
    text = find_srt(ep).read_text(encoding="utf-8")
    out = []
    for chunk in re.split(r"\n\n+", text.strip()):
        lines = chunk.strip().splitlines()
        if len(lines) >= 2 and "-->" in lines[1]:
            num = int(lines[0]) if lines[0].strip().isdigit() else None
            tc = lines[1].split("-->")[0].strip()
            body = "".join(lines[2:])
            out.append((num, tc, body))
    return out


def group(bs, chars):
    """把字幕块合并成不超过 chars 的段落，返回 [(start,end,timecode,text)]。"""
    groups = []
    cur_s = cur_e = None
    cur_tc = ""
    buf = ""
    for num, tc, body in bs:
        if buf and len(buf) + len(body) > chars:
            groups.append((cur_s, cur_e, cur_tc, buf))
            buf, cur_s, cur_tc = "", None, ""
        if cur_s is None:
            cur_s, cur_tc = num, tc
        cur_e = num
        buf += body
    if buf:
        groups.append((cur_s, cur_e, cur_tc, buf))
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep", type=int)
    ap.add_argument("--from", dest="frm", type=int, default=1)
    ap.add_argument("--to", dest="to", type=int, default=10**9)
    ap.add_argument("--chars", type=int, default=6000)
    ap.add_argument("--grep", default=None)
    args = ap.parse_args()

    bs = [b for b in blocks(args.ep) if b[0] is None or (args.frm <= b[0] <= args.to)]
    if args.grep:
        rx = re.compile(args.grep)
        for num, tc, body in bs:
            if rx.search(body):
                lo = max(1, (num or 1) - 2)
                hi = (num or 1) + 2
                ctx = "".join(b for n, t, b in blocks(args.ep) if n and lo <= n <= hi)
                print(f"[{num}] {tc}  …{ctx}…\n")
        return

    for s, e, tc, txt in group(bs, args.chars):
        print(f"── [{s}-{e}] @{tc} ──")
        print(txt)
        print()


if __name__ == "__main__":
    main()
