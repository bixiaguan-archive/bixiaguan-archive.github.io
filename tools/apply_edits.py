#!/usr/bin/env python3
"""apply_edits.py — 应用附注编辑工作流的产出。

读取 tools/rewrite/epNNN.out.json，按 (keyword, ep) 回写 explanation / note。

用法：python3 tools/apply_edits.py [--write]
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "bixiaguan_transcripts" / "notes" / "annotations.json"
WR = ROOT / "tools" / "rewrite"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    d = json.loads(NOTES.read_text(encoding="utf-8"))
    by = {}
    for a in d["annotations"]:
        by[a["keyword"]] = a

    st = {"files": 0, "items": 0, "ex": 0, "note": 0, "missing_kw": 0, "missing_ep": 0}
    problems = []
    for f in sorted(WR.glob("ep*.out.json")):
        st["files"] += 1
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"{f.name}: JSON 解析失败 {exc}")
            continue
        if not isinstance(items, list):
            problems.append(f"{f.name}: 不是数组")
            continue
        for it in items:
            st["items"] += 1
            kw = it.get("keyword")
            ep = it.get("ep")
            a = by.get(kw)
            if a is None:
                st["missing_kw"] += 1
                problems.append(f"{f.name}: 找不到 keyword {kw!r}")
                continue
            ent = next((e for e in a["episodes"] if e["ep"] == ep), None)
            if ent is None:
                st["missing_ep"] += 1
                problems.append(f"{f.name}: {kw!r} 无 ep{ep} 实例")
                continue
            ne = it.get("new_explanation")
            if ne is not None and ne.strip() and ne.strip() != (a.get("explanation") or "").strip():
                a["explanation"] = ne.strip()
                st["ex"] += 1
            nn = it.get("new_note")
            if nn is not None and nn.strip() and nn.strip() != (ent.get("note") or "").strip():
                ent["note"] = nn.strip()
                st["note"] += 1

    print(json.dumps(st, ensure_ascii=False, indent=1))
    # 残留检查
    left_ex = sum(1 for a in d["annotations"] if re.search(r"本期|本集|这期", a.get("explanation") or ""))
    left_nt = sum(1 for a in d["annotations"] for e in a["episodes"]
                  if "本期说" in (e.get("note") or "") or "本集说" in (e.get("note") or ""))
    print(f"写回后 explanation 仍含「本期」: {left_ex}；note 仍含「本期说」: {left_nt}")
    if problems:
        print("问题：")
        for p in problems[:20]:
            print("  ", p)
    if args.write:
        NOTES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写回 annotations.json")


if __name__ == "__main__":
    main()
