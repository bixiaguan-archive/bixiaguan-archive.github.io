#!/usr/bin/env python3
"""fix_notes.py — 附注/勘误的写法治理（机械、保守）。

做的事：
1. 单期附注：把 explanation 里以「本期…」开头的句子移到该期的 note（期次专属信息出主体）；
   仅当主体仍剩下 ≥10 字的通用说明时才移动，否则保留原样并列入待改清单。
2. note 去掉「本期说/本期中/本期里/本期：」这类套话开头。
3. note 里与勘误重复的句子（「见本期勘误…」「已立勘误」等）删除。

用法：python3 tools/fix_notes.py [--write]
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "bixiaguan_transcripts" / "notes" / "annotations.json"
WORKLIST = ROOT / "tools" / "note-rewrite-worklist.txt"

SENT = re.compile(r"[^。！？]*[。！？]|[^。！？]+$")
LEAD = re.compile(r"^\s*(?:本期|本集|这期)\s*(?:说|中|里|的|：|:|，|,)?\s*")
ERRATA_REF = re.compile(
    r"[（(]?(?:详见|参见|见)?\s*(?:本期|同期|本集)?\s*勘误[^。！？]*[。！？]?"
    r"|[（(][^）)]*(?:已(?:作|立)|列为)\s*勘误[^）)]*[）)]"
    r"|[（(][^）)]*(?:误作|误说|应为|实为)[^）)]*(?:勘误)[^）)]*[）)]"
)


def sentences(text):
    return [s for s in SENT.findall(text or "") if s.strip()]


def clean_note(note):
    if not note:
        return note, False
    orig = note
    note = ERRATA_REF.sub("", note)
    note = LEAD.sub("", note.strip())
    note = re.sub(r"^[，。；、：,;:\s]+", "", note)
    note = re.sub(r"[，、；：]\s*(?=[。！？]|$)", "", note)
    note = re.sub(r"[，、；：]\s*$", "", note)
    note = re.sub(r"\s{2,}", " ", note).strip()
    if note and note[-1] not in "。！？…）】":
        note += "。"
    return note, note != orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    d = json.loads(NOTES.read_text(encoding="utf-8"))
    st = {"moved_sent": 0, "ann_split": 0, "lead_stripped": 0, "errata_ref_stripped": 0,
          "worklist": 0}
    work = []

    for a in d["annotations"]:
        ex = a.get("explanation") or ""
        eps = a.get("episodes") or []
        if len(eps) == 1 and "本期" in ex:
            sents = sentences(ex)
            moved = [s for s in sents if re.match(r"^\s*(?:本期|本集|这期)", s)]
            rest = "".join(s for s in sents if s not in moved)
            if moved and len(rest.strip()) >= 10:
                a["explanation"] = rest.strip()
                e = eps[0]
                add = "".join(moved)
                add, _ = clean_note(add)
                if add:
                    cur = (e.get("note") or "").strip()
                    e["note"] = (cur + "　" + add).strip() if cur else add
                    st["moved_sent"] += len(moved)
                    st["ann_split"] += 1
            elif moved:
                work.append(f"{a['keyword']}\tep{eps[0]['ep']}\t主体无法保留，需人工改写")

        for e in eps:
            nt = e.get("note")
            if not nt:
                continue
            new, changed = clean_note(nt)
            if re.search(r"勘误", nt) and "勘误" not in new:
                st["errata_ref_stripped"] += 1
            if changed:
                st["lead_stripped"] += 1
                e["note"] = new
            nt2 = e.get("note") or ""
            kw0 = (a.get("keyword") or "")[:1]
            if ("本期" in nt2 or len(nt2) > 120 or nt2.count("「") >= 3
                    or (kw0 and nt2.startswith(kw0) and len(nt2) > 20)):
                work.append(f"{a['keyword']}\tep{e['ep']}\t{nt2[:60]}")

    st["worklist"] = len(work)
    print(json.dumps(st, ensure_ascii=False, indent=1))
    WORKLIST.write_text("\n".join(work) + "\n", encoding="utf-8")
    print(f"待改写清单 {len(work)} 条 → {WORKLIST.relative_to(ROOT)}")
    if args.write:
        NOTES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写回 annotations.json")


if __name__ == "__main__":
    main()
