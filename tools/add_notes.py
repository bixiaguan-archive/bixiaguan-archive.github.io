#!/usr/bin/env python3
"""
add_notes.py — 向统一附注索引写入/更新附注与勘误。

索引文件：bixiaguan_transcripts/notes/annotations.json
  annotations[]: {id, keyword, label, explanation, source,
                  episodes: [{ep, subtitle, timecode, note?}]}
    · keyword 唯一（统一索引，不重复收录同一术语）
    · episodes 记录该术语在各期出现的位置
    · note（可选）＝该期的特别说明：只对本期语境有效，不并入通用 explanation
  errata[]: {id, keyword, label, original, correct, source, ep, subtitle, timecode}
    · 主播口述的事实性错误，不改写转录正文

输入 JSON 结构：
{
  "annotations": [{"keyword","label","explanation","source","ep","subtitle","timecode","note"?}],
  "updates":     [{"keyword","explanation"?,"label"?,"source"?}],
  "errata":      [{"keyword","label","original","correct","source","ep","subtitle","timecode"}]
}

用法：python3 tools/add_notes.py tools/notes/ep002.json [--dry-run]
"""
import argparse
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "bixiaguan_transcripts" / "notes" / "annotations.json"


def norm(s):
    return (s or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    data = json.loads(NOTES.read_text(encoding="utf-8"))
    ann = data.get("annotations", [])
    err = data.get("errata", [])
    by_kw = {norm(a.get("keyword")): a for a in ann}

    added = merged = updated = err_added = noted = 0

    for item in spec.get("annotations", []):
        kw = norm(item["keyword"])
        ep_entry = {
            "ep": int(item["ep"]),
            "subtitle": str(item.get("subtitle", "")),
            "timecode": item.get("timecode", ""),
        }
        if item.get("note"):
            ep_entry["note"] = item["note"]
        cur = by_kw.get(kw)
        if cur is None:
            new = {
                "id": kw,
                "keyword": kw,
                "label": item.get("label", kw),
                "explanation": norm(item.get("explanation", "")),
                "source": norm(item.get("source", "")),
                "episodes": [ep_entry],
            }
            ann.append(new)
            by_kw[kw] = new
            added += 1
            print(f"  + 新术语 {kw}（ep{ep_entry['ep']}）")
        else:
            exists = any(
                e.get("ep") == ep_entry["ep"] and str(e.get("subtitle", "")) == ep_entry["subtitle"]
                for e in cur["episodes"]
            )
            if exists:
                print(f"  = 已存在 {kw}（ep{ep_entry['ep']} {ep_entry['subtitle']}）")
            else:
                cur["episodes"].append(ep_entry)
                merged += 1
                print(f"  + 复用术语 {kw} → 追加 ep{ep_entry['ep']}")
            if item.get("explanation") and norm(item["explanation"]) != norm(cur.get("explanation")):
                # 只有显式写在 updates 里才改通用解释，避免误覆盖
                print(f"    （提示：{kw} 的 explanation 与索引不同，如需改写请用 updates）")

    for item in spec.get("ep_notes", []):
        kw = norm(item["keyword"])
        cur = by_kw.get(kw)
        if not cur:
            print(f"  ! ep_notes 找不到术语 {kw}")
            continue
        target = None
        for e in cur["episodes"]:
            if e.get("ep") == int(item["ep"]) and (
                not item.get("subtitle") or str(e.get("subtitle", "")) == str(item["subtitle"])
            ):
                target = e
                break
        if target is None:
            print(f"  ! ep_notes 找不到 {kw} 的 ep{item['ep']} 条目")
            continue
        target["note"] = norm(item.get("note"))
        noted += 1
        print(f"  ~ 为 {kw} 的 ep{item['ep']} 条目补充本期说明")

    for item in spec.get("updates", []):
        kw = norm(item["keyword"])
        cur = by_kw.get(kw)
        if not cur:
            print(f"  ! updates 找不到术语 {kw}")
            continue
        for f in ("label", "explanation", "source"):
            if item.get(f) is not None:
                cur[f] = norm(item[f])
        updated += 1
        print(f"  ~ 更新统一索引条目 {kw}")

    for item in spec.get("errata", []):
        kw = norm(item["keyword"])
        dup = any(
            e.get("ep") == int(item["ep"]) and str(e.get("subtitle", "")) == str(item.get("subtitle", ""))
            and e.get("keyword") == kw
            for e in err
        )
        if dup:
            print(f"  = 勘误已存在 {kw}（ep{item['ep']}）")
            continue
        err.append({
            "id": f"ep{int(item['ep']):03d}-{kw}",
            "keyword": kw,
            "label": item.get("label", kw),
            "original": norm(item.get("original", "")),
            "correct": norm(item.get("correct", "")),
            "source": norm(item.get("source", "")),
            "ep": int(item["ep"]),
            "subtitle": str(item.get("subtitle", "")),
            "timecode": item.get("timecode", ""),
        })
        err_added += 1
        print(f"  + 勘误 {kw}（ep{item['ep']}）")

    data["annotations"] = ann
    data["errata"] = err
    data["version"] = int(data.get("version", 0)) + 1
    data["generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")

    print(f"\n新术语 {added}，复用追加 {merged}，本期说明 {noted}，更新 {updated}，勘误 {err_added}")
    if not args.dry_run:
        NOTES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已写回 {NOTES.relative_to(ROOT)}（version {data['version']}）")


if __name__ == "__main__":
    main()
