"""按站点顺序向 OSRM 请求驾车路线，把沿路轨迹写回 routes.json 的 path 字段。

改动路线站点后运行：python3 tools/route_paths.py
"""
import json, time, urllib.request
from pathlib import Path

MAP_DIR = Path(__file__).resolve().parent.parent / "bixiaguan_transcripts" / "map"
places = {p["name"]: p for p in json.loads((MAP_DIR / "places.json").read_text(encoding="utf-8"))}
routes_file = MAP_DIR / "routes.json"
routes = json.loads(routes_file.read_text(encoding="utf-8"))

for r in routes:
    coords = ";".join(f"{places[s]['lng']},{places[s]['lat']}" for s in r["stops"])
    url = f"https://router.project-osrm.org/route/v1/driving/{coords}?overview=simplified&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": "bixiaguan-archive-map/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        line = json.load(resp)["routes"][0]["geometry"]["coordinates"]
    r["path"] = [[round(lat, 4), round(lng, 4)] for lng, lat in line]
    print(f"{r['name']}：{len(r['stops'])} 站，轨迹 {len(r['path'])} 点")
    time.sleep(1)

routes_file.write_text(json.dumps(routes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
