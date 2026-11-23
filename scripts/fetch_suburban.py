# -*- coding: utf-8 -*-
"""Fetch full details (timetable, stops, geometry) for suburban night lines."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import fetch_baidu as fb

items = json.load(open(os.path.join(fb.DATA, 'suburban_search.json'), encoding='utf-8'))
want = re.compile(r'^(溧水Y\d+路夜间|高淳80[123]路|高淳定时公交)')
cand = {u: it for u, it in items.items() if want.match(it.get('name', ''))}
print('candidates:', [it['name'] for it in cand.values()], flush=True)

auth = None
details = {}
for uid, it in cand.items():
    d = fb.inf(uid); time.sleep(0.2)
    if d and d.get('anti_auth'): auth = d['anti_auth']
    b = fb.bsl(uid, auth or ''); time.sleep(0.25)
    if not b or not b.get('content'):
        d = fb.inf(uid); time.sleep(0.2)
        auth = (d or {}).get('anti_auth', auth)
        b = fb.bsl(uid, auth or ''); time.sleep(0.25)
    if not b or not b.get('content'):
        print('FAIL', it['name'], flush=True); continue
    if b.get('anti_auth'): auth = b['anti_auth']
    ln = b['content'][0]
    details[uid] = ln
    print(f"OK {ln['name']} | {ln.get('startTime')}-{ln.get('endTime')} | "
          f"tt={ln.get('timetable')!r} | stations={len(ln.get('stations', []))}", flush=True)
    pl = (ln.get('pair_line') or {}).get('uid')
    if pl and pl not in details and pl not in cand:
        pb = fb.bsl(pl, auth or ''); time.sleep(0.25)
        if pb and pb.get('content'):
            details[pl] = pb['content'][0]
            l2 = pb['content'][0]
            print(f"  pair OK {l2['name']} | {l2.get('startTime')}-{l2.get('endTime')} | "
                  f"tt={l2.get('timetable')!r}", flush=True)

json.dump(details, open(os.path.join(fb.DATA, 'suburban_details.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
lines = []
for uid, ln in details.items():
    stations = []
    for s in ln.get('stations', []):
        p = fb.parse_pt(s.get('geo'))
        stations.append({'name': s['name'], 'uid': s.get('uid'),
                         'lng': p[0] if p else None, 'lat': p[1] if p else None})
    lines.append({'uid': uid, 'name': ln['name'], 'raw_name': ln.get('raw_name'),
                  'start': ln.get('startTime'), 'end': ln.get('endTime'),
                  'company': ln.get('company'), 'price': ln.get('ticketPrice'),
                  'pair_uid': (ln.get('pair_line') or {}).get('uid'),
                  'stations': stations, 'paths': fb.parse_line_geo(ln.get('geo'))})
json.dump(lines, open(os.path.join(fb.DATA, 'suburban_lines.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('saved', len(lines), 'directions', flush=True)