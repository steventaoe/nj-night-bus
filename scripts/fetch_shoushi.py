# -*- coding: utf-8 -*-
"""Fetch the two 地铁末班守时公交 lines and merge into lines_wgs84.json."""
import json, os, time, urllib.parse
from fetch_baidu import search, inf, bsl, parse_pt, parse_line_geo, DATA

def stop_blinfo(wd):
    d = search(wd, rn=10)
    for it in d.get('content', []):
        if isinstance(it, dict) and '公交车站' in it.get('std_tag', '') and it.get('name') == wd:
            di = inf(it['uid'])
            time.sleep(0.3)
            return di['content'].get('blinfo', [])
    return []

bl = stop_blinfo('月苑南路')
ss_uids = {}
for b in bl:
    if '守时' in b.get('addr', ''):
        print(b['addr'], '|', b['name'], '|', b['uid'])
        ss_uids[b['uid']] = b

# line 1 uids found at 葛塘地铁站
ss_uids['549c2376e4d8d2b01e5800af'] = {'addr': '地铁末班守时公交', 'name': '方州广场东-泰冯路地铁站西'}
ss_uids['26111956427aefd597ec8421'] = {'addr': '地铁末班守时公交', 'name': '泰冯路地铁站西-方州广场东'}

auth = None
new_lines = []
for uid, meta in ss_uids.items():
    d = inf(uid); time.sleep(0.3)
    if d and d.get('anti_auth'): auth = d['anti_auth']
    b = bsl(uid, auth or ''); time.sleep(0.3)
    if not b or not b.get('content'):
        print('FAIL', uid, meta); continue
    if b.get('anti_auth'): auth = b['anti_auth']
    ln = b['content'][0]
    print('OK', ln['name'], '| stations:', len(ln.get('stations', [])),
          '| time:', ln.get('startTime'), ln.get('endTime'),
          '| timetable:', str(ln.get('timetable'))[:200],
          '| timetable_ext:', ln.get('timetable_ext'))
    stations = []
    for s in ln.get('stations', []):
        pt = parse_pt(s.get('geo'))
        stations.append({'name': s['name'], 'uid': s.get('uid'),
                         'lng': pt[0] if pt else None, 'lat': pt[1] if pt else None})
    new_lines.append({
        'uid': uid, 'name': ln['name'], 'raw_name': ln.get('raw_name') or meta['addr'],
        'start': ln.get('startTime'), 'end': ln.get('endTime'),
        'company': ln.get('company'), 'price': ln.get('ticketPrice'),
        'pair_uid': (ln.get('pair_line') or {}).get('uid'),
        'pair_name': (ln.get('pair_line') or {}).get('name'),
        'stations': stations, 'paths': parse_line_geo(ln.get('geo')),
        'timetable': ln.get('timetable'), 'timetable_ext': ln.get('timetable_ext'),
    })
    json.dump(ln, open(os.path.join(DATA, f'ss_{uid}.json'), 'w', encoding='utf-8'), ensure_ascii=False)

lines = json.load(open(os.path.join(DATA, 'lines_wgs84.json'), encoding='utf-8'))
have = {l['uid'] for l in lines}
for l in new_lines:
    if l['uid'] not in have:
        lines.append(l)
json.dump(lines, open(os.path.join(DATA, 'lines_wgs84.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('merged, total directions:', len(lines))