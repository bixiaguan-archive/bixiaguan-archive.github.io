#!/usr/bin/env python3
"""normalize_boilerplate.py — 规范片头/片尾固定用语里的网址与邮箱写法。

第一遍粗校时 ep001-077 已把「壁下观点com」「壁下观at幺六三点com」之类的
ASR 写法统一成 bixiaguan.com / 壁下观@163.com / 壁下观@ipn.li，ep078-102 未做。

ASR 断句经常把「壁下观」切成两块（如「member 点壁\\x00下观点 com」），
所以本脚本先把各字幕块正文用 \\x00 连接，在连接串上做正则替换；
命中跨块时把替换文本按原分割点在块间分配，再把 \\x00 拆回各块。
（分配后若某块正文变空，则该条规则跳过并报警，保证 SRT 结构不被破坏。）

用法：
    python3 tools/normalize_boilerplate.py --range 78-102 [--dry-run]
"""
import argparse
import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS = ROOT / "bixiaguan_transcripts"
FIXLOG = TRANSCRIPTS / "notes" / "asr_fixlog.json"
SEP = "\x00"

S = r"[\s\u3000\x00]*"          # 块分隔符 / 空白
DOT = r"[.。]"                   # 中英文句点


def sp(s):
    """允许每个字符之间出现空白或字幕块分隔符。"""
    return S.join(re.escape(c) for c in s)


XG = sp("壁下观")
BXG = sp("bixiaguan")
URLROOT = rf"(?:{XG}|{BXG}){S}(?:点)?{S}{DOT}?{S}{sp('com')}"

RULES = [
    # 支付宝账号：壁下观@163.com
    ("alipay",
     re.compile(rf"(?:{XG}|{BXG}){S}(?:at|AT|@){S}(?:点|{DOT})?{S}(?:{sp('幺六三')}|163){S}(?:点|{DOT})?{S}{sp('com')}",
                re.IGNORECASE),
     "壁下观@163.com"),
    # 邮箱：壁下观@ipn.li
    ("email",
     re.compile(rf"(?:{XG}|{BXG}){S}(?:at|AT|@){S}{DOT}?{S}{sp('ipn')}{S}(?:点|{DOT})?{S}{sp('li')}",
                re.IGNORECASE),
     "壁下观@ipn.li"),
    # 会员网址（网址在前）：bixiaguan.com/member
    ("member_url",
     re.compile(rf"{URLROOT}{S}(?:{sp('斜杠')}|/|／){S}{sp('member')}", re.IGNORECASE),
     "bixiaguan.com/member"),
    # 会员网址（member 在前）：bixiaguan.com/member
    ("member_first",
     re.compile(rf"{sp('member')}{S}{DOT}?{S}(?:点)?{S}(?:{XG}|{BXG}){S}(?:点)?{S}{DOT}?{S}{sp('com')}",
                re.IGNORECASE),
     "bixiaguan.com/member"),
    # 普通网址：bixiaguan.com
    ("url",
     re.compile(URLROOT, re.IGNORECASE),
     "bixiaguan.com"),
]

ASCII_ALNUM = re.compile(r"[0-9A-Za-z]")


def blocks(path):
    text = path.read_text(encoding="utf-8")
    out = []
    for chunk in re.split(r"\n\n+", text.strip()):
        lines = chunk.strip().splitlines()
        if len(lines) >= 2 and "-->" in lines[1]:
            num = int(lines[0]) if lines[0].strip().isdigit() else None
            out.append([num, lines[1], "".join(lines[2:])])
    return out


def split_replacement(repl, seg, seps):
    """把 repl 分配到 seg 的各子段（seps 为 SEP 下标）；默认按原字符比例分配，
    但避免把 ASCII 单词/数字从中间切开。"""
    if not seps:
        return [repl]
    n = len(seg) - len(seps)
    cuts = [sum(1 for ch in seg[:si] if ch != SEP) for si in seps]
    ks = [round(len(repl) * (c / n)) if n else 0 for c in cuts]
    bad = any(
        0 < k < len(repl) and ASCII_ALNUM.match(repl[k - 1]) and ASCII_ALNUM.match(repl[k])
        for k in ks
    )
    if bad:
        # 整段替换文本放进原本字符最多的那一块
        bounds = [0] + list(cuts) + [n]
        sizes = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
        idx = max(range(len(sizes)), key=lambda i: (sizes[i], -i))
        parts = [""] * (len(seps) + 1)
        parts[idx] = repl
        return parts
    parts, prev = [], 0
    for k in ks:
        parts.append(repl[prev:k])
        prev = k
    parts.append(repl[prev:])
    return parts


def normalize(ep, dry_run=False):
    p = sorted(TRANSCRIPTS.glob(f"ep{ep:03d}_*.srt"))[0]
    bs = blocks(p)
    log = []
    for kind, rx, repl in RULES:
        joined = SEP.join(b[2] for b in bs)
        starts, pos = [], 0
        for b in bs:
            starts.append(pos)
            pos += len(b[2]) + 1
        pieces, last, skipped = [], 0, 0
        for m in rx.finditer(joined):
            seg = m.group(0)
            # 纯跨块拼接（正文一字未改）不计入修正，也不写日志
            if seg.replace(SEP, "") == repl:
                continue
            seps = [i for i, ch in enumerate(seg) if ch == SEP]
            parts = split_replacement(repl, seg, seps)
            blk = max(i for i, s in enumerate(starts) if s <= m.start())
            trial = SEP.join(parts)
            # 试算：替换后不能产生空字幕块
            trial_pieces = (joined[:m.start()] + trial + joined[m.end():]).split(SEP)
            if any(t == "" for t in trial_pieces):
                skipped += 1
                continue
            num, tc = bs[blk][0], bs[blk][1].split("-->")[0].strip()
            log.append({"ep": ep, "subtitle": num, "timecode": tc,
                        "find": seg.replace(SEP, ""), "replace": repl,
                        "kind": "boilerplate",
                        "evidence": "片头/片尾固定用语；与 ep001-077 的统一写法一致。"})
            pieces.append(joined[last:m.start()])
            pieces.append(trial)
            last = m.end()
        pieces.append(joined[last:])
        joined2 = "".join(pieces)
        new_pieces = joined2.split(SEP)
        if len(new_pieces) != len(bs):
            raise SystemExit(f"ep{ep:03d} {kind}: 块数变化 {len(bs)} → {len(new_pieces)}")
        for b, t in zip(bs, new_pieces):
            b[2] = t
        if skipped:
            print(f"    （{kind}: 跳过 {skipped} 处以免产生空字幕块）")
    if log and not dry_run:
        out = "\n\n".join(f"{b[0]}\n{b[1]}\n{b[2]}" for b in bs) + "\n"
        p.write_text(out, encoding="utf-8")
    return p, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eps", nargs="*", type=int)
    ap.add_argument("--range", dest="rng")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    eps = list(args.eps)
    if args.rng:
        a, b = args.rng.split("-")
        eps += list(range(int(a), int(b) + 1))
    if not eps:
        eps = list(range(78, 103))

    all_log = []
    for ep in sorted(set(eps)):
        path, log = normalize(ep, args.dry_run)
        all_log += log
        print(f"ep{ep:03d}: {len(log)} 处 boilerplate 规范化  ({path.name})")
    if all_log and not args.dry_run:
        cur = json.loads(FIXLOG.read_text(encoding="utf-8")) if FIXLOG.exists() else []
        cur += all_log
        FIXLOG.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已追加 {len(all_log)} 条到 {FIXLOG.relative_to(ROOT)}")
    print(f"合计 {len(all_log)} 处{'（dry-run）' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
