#!/usr/bin/env python3
"""progress.py — 汇总每期校对进度：ASR 修正数、附注实例数、勘误数。

输出 markdown 表格到 stdout（可重定向到 tools/PROGRESS.md）。
"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXLOG = ROOT / "bixiaguan_transcripts" / "notes" / "asr_fixlog.json"
NOTES = ROOT / "bixiaguan_transcripts" / "notes" / "annotations.json"
EPISODES = ROOT / "bixiaguan_search" / "episodes.json"


def main():
    fixes = collections.Counter()
    if FIXLOG.exists():
        for f in json.loads(FIXLOG.read_text(encoding="utf-8")):
            fixes[f["ep"]] += 1

    data = json.loads(NOTES.read_text(encoding="utf-8"))
    ann = collections.Counter()
    for a in data.get("annotations", []):
        for e in a.get("episodes", []):
            ann[e["ep"]] += 1
    err = collections.Counter()
    for e in data.get("errata", []):
        err[e["ep"]] += 1

    eps = {e["ep"]: e for e in json.loads(EPISODES.read_text(encoding="utf-8"))}

    print("| 期 | 标题 | ASR 修正 | 附注 | 勘误 |")
    print("|---:|---|---:|---:|---:|")
    for ep in sorted(eps):
        title = eps[ep]["title"].replace(f"《壁下观》Episode {ep} ", "").strip()
        print(f"| {ep} | {title} | {fixes.get(ep,0)} | {ann.get(ep,0)} | {err.get(ep,0)} |")
    print()
    print(f"合计：ASR 修正 {sum(fixes.values())} 处（覆盖 {len(fixes)} 期）；"
          f"附注实例 {sum(ann.values())}（术语 {len(data.get('annotations', []))} 条）；"
          f"勘误 {sum(err.values())} 条")


if __name__ == "__main__":
    main()
