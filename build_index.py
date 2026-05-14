#!/opt/homebrew/bin/python3.12
"""
解析所有 SRT 文件，生成搜索索引 search_index.json
每条记录包含：epNum, title, youtubeId, segments（含时间戳+文本）
"""
import json, re
from pathlib import Path

TRANSCRIPTS_DIR = Path(__file__).parent / "bixiaguan_transcripts"
OUTPUT = Path(__file__).parent / "bixiaguan_search" / "search_index.json"
OUTPUT.parent.mkdir(exist_ok=True)

# YouTube ID 映射
YOUTUBE_IDS = {
    1:"a1cjeKAHNAc",2:"lOyDBOMwKJE",3:"Ghi60u-r5XA",4:"0j1I4NcU-V0",
    5:"j4Dn0NKE3TI",6:"I8MIKJKHWqE",7:"YSN0G0CtFTg",8:"9OIuV1gD2No",
    9:"QYihTxjz5H0",10:"WRy8gEdZKMw",11:"jhYXV5jMtVQ",12:"rSiHOLYBFus",
    13:"upM4vvDv-ho",14:"UQEWCZ4fOB8",15:"b19ywAH41vM",16:"xZKdhmqvv9A",
    17:"1Fm84oGVZuc",18:"YEnSTIUpduY",19:"0OabCg0gIJI",20:"O78rVjK8KeQ",
    21:"dgpZFWXz9PU",22:"n0aLiiEqwvM",23:"rvo0jyNL3Dw",24:"kO7pqbOPeO4",
    25:"JgOkcKVbhUY",26:"aLO3VD_PDW0",27:"5lf04P8QB3M",28:"T1UakFlpIEg",
    29:"mFg8qqokqA8",30:"8kNI2_6O46E",31:"rr8iCi9idJM",32:"f9k0ysPosyc",
    33:"O_S1E_t5udU",34:"FLQ35qaQV5I",35:"48toC2ZLj6I",36:"XiEwReNL1lw",
    37:"Me6RTgsGSh0",38:"Wg_g7HzG0A4",39:"dqYOmbJNBZs",40:"GU1KxRCuEq8",
    41:"ZHZrLpDCb48",42:"W32Fty_XMWI",43:"gE4VIrIDrfU",44:"iY3rrmsSE9k",
    45:"7Vqrh-DQ360",46:"zXUcCTe9Ri8",47:"E0FwWan-v30",48:"RZAOb2Owvvg",
    49:"CjdIh9_Rkjc",50:"O9xZcMl-Yso",51:"ddS0zBHEdEM",52:"q42oqgahd9o",
    53:"tNLAS_xjViU",54:"u2V9X_l_28M",55:"xubjQ7YQFME",56:"_2XyJ6Mil00",
    57:"_pDYsz8AkxE",58:"hBMlpC38lVM",59:"9qtD0p6mu5U",60:"DWEHzTBVJsU",
    61:"tqCVtg_Z4Wg",62:"9z8dTsdl1g4",63:"ulq0uENqx6w",64:"cOaimK_L6TU",
    65:"p0qMuI1UFNg",66:"qts4r8aIshM",67:"YcH4fM8Rts8",68:"K1gLC-ZfoqI",
    69:"Kg60nPu2GyU",70:"n0ivvTL3A5c",71:"35xkxb4VrvE",72:"cK497gR97K4",
    73:"lqjevDBu4cg",74:"ymRg4GvaAO4",75:"FRnNX46Oixw",76:"oSJnyWW7mSM",
    77:"K9clR0cXjao",78:"0wWsiw_VwrY",79:"0U7wm-qSqvI",80:"DLNBV6W0rbQ",
    81:"Rw8RCEav_w8",82:"SH-aP5GUQy0",83:"vnQUpfaHu54",84:"G-xyPOtDCq8",
    85:"EL5MplyleV8",86:"f0i3TMYnUdo",87:"MSC1oZR-2cs",88:"7BbWQLtczIE",
    89:"n8OtIeDGkyo",90:"T0KiJznYWzw",91:"5MiP-Z3V-rM",92:"aQtIpn3EDlc",
    93:"ypeypExKefw",94:"YAU1ne0hYg8",95:"lKoMSHw0aIk",96:"gIT85HsBLxw",
    97:"XmZM-jPnuKk",98:"urgrUGeTaZc",99:"S8vnb4nJPqs",100:"-7DDF3Ctyk8",
    101:"ecz__qjit6Q",102:"lg77UlI4ohg",
}

def srt_time_to_seconds(t):
    """00:01:23,456 -> 83.456"""
    h, m, s = t.split(":")
    s, ms = s.split(",")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

def parse_srt(path):
    """解析 SRT，返回 [{start, end, text}, ...]，每条约合并4个字幕块"""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r'\n\n+', text.strip())
    raw = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        # lines[0] = 序号, lines[1] = 时间, lines[2+] = 文本
        time_match = re.match(r'(\S+)\s*-->\s*(\S+)', lines[1])
        if not time_match:
            continue
        start = srt_time_to_seconds(time_match.group(1))
        end   = srt_time_to_seconds(time_match.group(2))
        txt   = "".join(lines[2:])
        raw.append({"start": start, "end": end, "text": txt})

    # 合并成约 60 字左右的段落，便于展示
    merged = []
    buf_text, buf_start, buf_end = "", None, None
    for r in raw:
        if buf_start is None:
            buf_start = r["start"]
        buf_text += r["text"]
        buf_end = r["end"]
        if len(buf_text) >= 50 or r["text"].endswith(("。", "？", "！", "…")):
            merged.append({"start": buf_start, "end": buf_end, "text": buf_text})
            buf_text, buf_start, buf_end = "", None, None
    if buf_text:
        merged.append({"start": buf_start, "end": buf_end, "text": buf_text})
    return merged

episodes = []
srt_files = sorted(TRANSCRIPTS_DIR.glob("ep*.srt"))
for srt_path in srt_files:
    m = re.match(r'ep(\d+)_(.+)\.srt', srt_path.name)
    if not m:
        continue
    ep_num = int(m.group(1))
    title  = m.group(2)
    yt_id  = YOUTUBE_IDS.get(ep_num, "")
    segments = parse_srt(srt_path)
    episodes.append({
        "ep": ep_num,
        "title": title,
        "ytId": yt_id,
        "segments": segments,
    })
    print(f"  ep{ep_num:03d} {title}  ({len(segments)} 段)")

OUTPUT.write_text(json.dumps(episodes, ensure_ascii=False, separators=(',', ':')), encoding="utf-8")
size_mb = OUTPUT.stat().st_size / 1024 / 1024
print(f"\n✅ 索引已生成: {OUTPUT}  ({size_mb:.1f} MB, {len(episodes)} 期)")
