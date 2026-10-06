#!/usr/bin/env python3
"""apply_metacleanup.py — 应用元叙述清理工作流的产出。"""
import argparse, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "bixiaguan_transcripts" / "notes" / "annotations.json"
WR = ROOT / "tools" / "metacleanup"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    d = json.loads(NOTES.read_text(encoding="utf-8"))
    st = {"files": 0, "items": 0, "ex": 0, "note": 0, "del": 0, "not_found": 0}
    problems = []
    drop_ann, drop_err = set(), set()
    for f in sorted(WR.glob("ep*.out.json")):
        ep = int(re.search(r"ep(\d+)", f.name).group(1)); st["files"] += 1
        try: items = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e: problems.append(f"{f.name}: {e}"); continue
        for it in items:
            st["items"] += 1
            parts = (it.get("id") or "").split("|")
            if len(parts) < 3: problems.append(f"{f.name}: id 异常"); continue
            kind, kw, sub = parts[0], parts[1], parts[2]
            found = False
            for ann in d["annotations"]:
                if ann["keyword"] != kw: continue
                for e in ann["episodes"]:
                    if e["ep"] == ep and str(e.get("subtitle")) == sub:
                        found = True
                        if it.get("delete"): drop_ann.add((kw, ep, sub)); st["del"] += 1; break
                        ne = it.get("new_explanation"); nn = it.get("new_note")
                        if ne is not None and ne.strip() and ne.strip() != (ann.get("explanation") or "").strip():
                            ann["explanation"] = ne.strip(); st["ex"] += 1
                        if nn is not None and nn.strip() and nn.strip() != (e.get("note") or "").strip():
                            e["note"] = nn.strip(); st["note"] += 1
                break
            if found: continue
            for e in d["errata"]:
                if e["keyword"] == kw and e["ep"] == ep and str(e.get("subtitle")) == sub:
                    found = True
                    if it.get("delete"): drop_err.add((kw, ep, sub)); st["del"] += 1; break
                    ne = it.get("new_explanation")
                    if ne is not None and ne.strip() and ne.strip() != (e.get("correct") or "").strip():
                        e["correct"] = ne.strip(); st["ex"] += 1
            if not found: st["not_found"] += 1
    if drop_ann or drop_err:
        d["annotations"] = [ann for ann in d["annotations"]
                            if not any((ann["keyword"], e["ep"], str(e.get("subtitle"))) in drop_ann for e in ann["episodes"])]
        d["errata"] = [e for e in d["errata"] if (e["keyword"], e["ep"], str(e.get("subtitle"))) not in drop_err]
    print(json.dumps(st, ensure_ascii=False, indent=1))
    for p in problems[:10]: print("  ", p)
    if a.write:
        NOTES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写回 annotations.json")

if __name__ == "__main__":
    main()
