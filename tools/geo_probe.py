#!/usr/bin/env python3
"""Geocode a small batch of place names via Nominatim (rate-limited, cached)."""
import json, os, sys, time, urllib.parse, urllib.request

CACHE = os.path.join(os.path.dirname(__file__), 'geo_cache.json')
UA = {'User-Agent': 'bixiaguan-heritage-map/0.1 (research; contact: local)'}


def load():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    return {}


def save(c):
    json.dump(c, open(CACHE, 'w'), ensure_ascii=False, indent=1)


def q(name, extra=''):
    url = 'https://nominatim.openstreetmap.org/search?format=json&limit=3&accept-language=zh&countrycodes=cn,jp&dedupe=1&q=' + urllib.parse.quote(name + ' ' + extra)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except Exception as e:
        return [{'error': str(e)}]


def main():
    cache = load()
    todo = sys.argv[1:]
    for name in todo:
        if name in cache:
            print('CACHED', name, cache[name])
            continue
        res = q(name)
        if res and 'error' not in res[0]:
            best = res[0]
            cache[name] = {'lat': float(best['lat']), 'lon': float(best['lon']), 'name': best.get('display_name', '')[:90]}
            print('OK    ', name, cache[name]['lat'], cache[name]['lon'], cache[name]['name'][:70])
        else:
            cache[name] = None
            print('NONE  ', name, res[:1])
        save(cache)
        time.sleep(1.2)


if __name__ == '__main__':
    main()
