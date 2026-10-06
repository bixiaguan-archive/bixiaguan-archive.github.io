#!/usr/bin/env python3
"""
apply_fixes.py — 应用人工核对过的 ASR 修正，并写入修正日志。

修正清单是一个 JSON 数组，每项：
{
  "ep": 2,
  "find": "错误写法",
  "replace": "正确写法",
  "subtitle": 123,                 # 可选：限定在该字幕块及其相邻块内查找
  "all": false,                    # true 时替换该期内所有出现
  "evidence": "依据：《中国文物图集》/Wikipedia 条目 …",
  "kind": "asr"                    # asr | punct | spacing | term
}

安全规则：
  * 找不到 find → 记为 MISS，不改文件；
  * 未给 subtitle 且出现多次 → 记为 AMBIGUOUS，不改文件（除非 all: true）；
  * 每次成功修正都追加到 bixiaguan_transcripts/notes/asr_fixlog.json。

用法：
    python3 tools/apply_fixes.py fixes_ep002.json [--dry-run]
"""
import argparse
import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS = ROOT / "bixiaguan_transcripts"
FIXLOG = TRANSCRIPTS / "notes" / "asr_fixlog.json"


def find_srt(ep):
    for p in sorted(TRANSCRIPTS.glob(f"ep{ep:03d}_*.srt")):
        return p
    raise SystemExit(f"找不到 ep{ep:03d}")


def parse(text):
    """返回 [(num, timecode, body, raw_index)]，非标准块 num=None。"""
    out = []
    for idx, chunk in enumerate(re.split(r"\n\n+", text.strip())):
        lines = chunk.strip().splitlines()
        if len(lines) >= 2 and "-->" in lines[1]:
            num = int(lines[0]) if lines[0].strip().isdigit() else None
            tc = lines[1]  # 保留完整时间码行（含 --> 与结束时间）
            out.append([num, tc, "\n".join(lines[2:]), idx])
        else:
            out.append([None, None, chunk, idx])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fixes", help="修正清单 JSON 文件")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fixes = json.loads(Path(args.fixes).read_text(encoding="utf-8"))
    if isinstance(fixes, dict):
        fixes = fixes.get("fixes", [])

    by_ep = {}
    for f in fixes:
        by_ep.setdefault(int(f["ep"]), []).append(f)

    log = []
    if FIXLOG.exists():
        log = json.loads(FIXLOG.read_text(encoding="utf-8"))
    applied = skipped = 0

    for ep, items in sorted(by_ep.items()):
        path = find_srt(ep)
        blocks = parse(path.read_text(encoding="utf-8"))
        changed = False
        for f in items:
            find, repl = f["find"], f["replace"]
            sub = f.get("subtitle")
            scope = [b for b in blocks if b[0] is not None and (sub is None or abs(b[0] - sub) <= 1)]
            hits = [b for b in scope if find in b[2]]
            if not hits:
                # 跨块切断的情况：拼相邻块再查
                joined = None
                for i in range(len(blocks) - 1):
                    a, b = blocks[i], blocks[i + 1]
                    if a[0] is None or b[0] is None:
                        continue
                    if sub is not None and not (sub - 1 <= a[0] <= sub + 1):
                        continue
                    junction = a[2] + b[2]
                    for m in re.finditer(re.escape(find), junction):
                        if m.start() < len(a[2]) < m.end():   # 确实跨越块边界
                            joined = (a, b, m.start(), m.end())
                            break
                    if joined:
                        break
                if joined:
                    a, b, s, e = joined
                    len_a = len(a[2])
                    k = len_a - s                     # find 落在前块尾部的字符数
                    a[2] = a[2][:s] + repl[:k]
                    b[2] = repl[k:] + b[2][e - len_a:]
                    changed = True
                    applied += 1
                    print(f"  ep{ep:03d} [{a[0]}|{b[0]}] {find!r} → {repl!r} (跨块)")
                    log.append({"ep": ep, "subtitle": a[0], "timecode": a[1].split("-->")[0].strip(), "find": find,
                                "replace": repl, "kind": f.get("kind", "asr"),
                                "evidence": f.get("evidence", ""),
                                "at": datetime.datetime.now().isoformat(timespec="seconds")})
                    continue
                print(f"  MISS ep{ep:03d} {find!r}（{f.get('note','')}）")
                skipped += 1
                continue
            total = sum(b[2].count(find) for b in hits)
            if total > 1 and not f.get("all") and sub is None:
                print(f"  AMBIGUOUS ep{ep:03d} {find!r} 出现 {total} 次，需给 subtitle 或 all:true")
                skipped += 1
                continue
            for b in hits:
                b[2] = b[2].replace(find, repl)
                changed = True
                applied += 1
                print(f"  ep{ep:03d} [{b[0]}] {b[1].split(chr(10))[0].split('-->')[0].strip()} {find!r} → {repl!r}")
                log.append({"ep": ep, "subtitle": b[0], "timecode": b[1].split("-->")[0].strip(), "find": find,
                            "replace": repl, "kind": f.get("kind", "asr"),
                            "evidence": f.get("evidence", ""),
                            "at": datetime.datetime.now().isoformat(timespec="seconds")})
        if changed and not args.dry_run:
            out = "\n\n".join(
                (f"{b[0]}\n{b[1]}\n{b[2]}" if b[0] is not None else b[2]) for b in blocks
            ) + "\n"
            path.write_text(out, encoding="utf-8")
            print(f"已写回 {path.name}")

    if not args.dry_run and applied:
        FIXLOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n合计：修正 {applied} 处，跳过 {skipped} 处{'（dry-run）' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
