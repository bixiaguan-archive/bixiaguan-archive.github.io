#!/usr/bin/env python3
"""apply_anchorreview.py — 应用「逐条人工判定锚点」工作流的产出。

读取 tools/anchorreview/epNNN.out.json，校验 anchor 是该期正文里原样存在的字串后写回
annotations.json（附注与勘误），并按 anchor 实际位置校正 subtitle / timecode。

用法：python3 tools/apply_anchorreview.py [--write]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix_anchors as fa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "bixiaguan_transcripts" / "notes" / "annotations.json"
WR = ROOT / "tools" / "anchorreview"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    d = json.loads(NOTES.read_text(encoding="utf-8"))
    ann = {}
    for a in d["annotations"]:
        for e in a["episodes"]:
            ann[(a["keyword"], e["ep"], str(e.get("subtitle")))] = e
    err = {}
    for e in d["errata"]:
        err[(e["keyword"], e["ep"], str(e.get("subtitle")))] = e

    st = {"files": 0, "items": 0, "changed": 0, "same": 0, "bad_anchor": 0,
          "not_found": 0, "missing": 0}
    problems = []
    E = {}

    def ep(n):
        if n not in E:
            E[n] = fa.Ep(n)
        return E[n]

    seen = set()
    for f in sorted(WR.glob("ep*.out.json")):
        epn = int(re.search(r"ep(\d+)", f.name).group(1))
        st["files"] += 1
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"{f.name}: JSON 解析失败 {exc}")
            continue
        for it in items:
            st["items"] += 1
            i = it.get("id") or ""
            parts = i.split("|")
            if len(parts) < 3:
                problems.append(f"{f.name}: id 格式异常 {i!r}")
                continue
            kind, kw, sub = parts[0], parts[1], parts[2]
            key = (kw, epn, sub)
            seen.add(key)
            ent = ann.get(key) if kind == "ann" else err.get(key)
            if ent is None:
                st["not_found"] += 1
                problems.append(f"{f.name}: 找不到条目 {i!r}")
                continue
            anchor = (it.get("anchor") or "").strip()
            FILLER = ("就谈到", "比如说", "呃", "嗯", "啊", "那么", "然后", "这个这个")
            occ = ep(epn).occurrences(anchor)
            bad = (not anchor or not occ or len(anchor) > 20
                   or anchor[0] in "的了是在把被而就也都还很不太这那其之等和与及，。、？！"
                   or anchor[-1] in "的了是在把被而就也都还很不太这那其之等和与及，。、？！"
                   or anchor.startswith(FILLER) or anchor.endswith(FILLER))
            if bad:
                st["bad_anchor"] += 1
                problems.append(f"{f.name}: anchor 不合规/含衍字 {i!r} → {anchor[:24]!r}")
                continue
            cur = ent.get("anchor") or ""
            if fa.norm(anchor) == fa.norm(cur):
                st["same"] += 1
            else:
                st["changed"] += 1
            ent["anchor"] = anchor
            rs, re_, blk = occ[0]          # 取该期第一次出现的位置
            ent["subtitle"] = str(ep(epn).blocks[blk][0])
            ent["timecode"] = ep(epn).blocks[blk][1]

    # 工作单里没被产出的条目
    for f in sorted(WR.glob("ep[0-9][0-9][0-9].json")):
        epn = int(re.search(r"ep(\d+)", f.name).group(1))
        for it in json.loads(f.read_text(encoding="utf-8")):
            parts = it["id"].split("|")
            if (parts[1], epn, parts[2]) not in seen:
                st["missing"] += 1

    print(json.dumps(st, ensure_ascii=False, indent=1))
    if problems:
        print(f"问题 {len(problems)} 条：")
        for p in problems[:15]:
            print("  ", p)
    if args.write:
        NOTES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写回 annotations.json")


if __name__ == "__main__":
    main()
