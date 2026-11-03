#!/usr/bin/env python3
"""audit2.py — 附注/勘误锚点的全库定位体检（按全文归一化匹配）。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "bixiaguan_transcripts"
SKIP = "《》·・‧\u00b7\u30fb \t\r\n\u3000"


def norm(s):
    return "".join(c for c in s if c not in SKIP)


def sec(tc):
    m = re.match(r"(\d\d):(\d\d):(\d\d)", tc or "")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else -1


def load():
    eps = {}
    for p in sorted(T.glob("ep*.srt")):
        ep = int(re.match(r"ep(\d+)_", p.name).group(1))
        text = p.read_text(encoding="utf-8")
        segs = []
        for chunk in re.split(r"\n\n+", text.strip()):
            lines = chunk.strip().splitlines()
            if len(lines) >= 2 and "-->" in lines[1]:
                segs.append((int(lines[0]), sec(lines[1]), "\n".join(lines[2:])))
        eps[ep] = segs
    return eps


def main():
    eps = load()
    full = {}
    offs = {}
    for ep, segs in eps.items():
        normed = []
        starts = []
        pos = 0
        for num, s, body in segs:
            starts.append((pos, num, s))
            b = norm(body)
            normed.append(b)
            pos += len(b)
        full[ep] = "".join(normed)
        offs[ep] = starts

    def seg_at(ep, p):
        best = None
        for start, num, s in offs[ep]:
            if start <= p:
                best = (num, s)
            else:
                break
        return best

    data = json.loads((T / "notes" / "annotations.json").read_text(encoding="utf-8"))
    missing = []
    far = []
    for typ in ("annotations", "errata"):
        for item in data[typ]:
            key = item.get("keyword", "")
            refs = item.get("episodes", []) if typ == "annotations" else [item]
            for e in refs:
                ep = e.get("ep")
                needle = norm(e.get("anchor") or key)
                text = full.get(ep, "")
                hint = sec(e.get("timecode", ""))
                p = text.find(needle)
                if p < 0:
                    missing.append((typ, ep, e.get("subtitle"), key, e.get("anchor")))
                    continue
                num, s = seg_at(ep, p)
                if hint >= 0 and abs(s - hint) > 120:
                    far.append((typ, ep, e.get("subtitle"), key, e.get("anchor"), hint, s, num))

    print(f"锚点在全文中找不到：{len(missing)}（附注+勘误）")
    for m in missing[:400]:
        print("  MISS", m)
    print(f"\n锚点定位与时间码相差 >120s：{len(far)}")
    for m in far[:200]:
        print("  FAR", m)


if __name__ == "__main__":
    main()
