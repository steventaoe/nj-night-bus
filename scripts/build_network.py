# -*- coding: utf-8 -*-
"""Build final night-bus network dataset from crawled Baidu data."""
import json, os, re, statistics
from collections import defaultdict

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
lines = json.load(open(os.path.join(DATA, 'lines_wgs84.json'), encoding='utf-8'))
_sub = os.path.join(DATA, 'suburban_lines.json')
if os.path.exists(_sub):
    lines += json.load(open(_sub, encoding='utf-8'))

def norm_stop(name):
    return re.sub(r'\(\d+站台\)$', '', name).strip()

def route_key(ln):
    raw = ln.get('raw_name') or ln['name']
    nm = ln['name']
    m = re.match(r'(Y\d+)路', raw)
    if m and not nm.startswith(('溧水', '高淳')): return m.group(1)
    m = re.match(r'溧水(Y\d+)路', nm)
    if m: return 'LS' + m.group(1)
    m = re.match(r'高淳(80\d)路', nm)
    if m: return 'GC' + m.group(1)
    if '守时' in raw:
        return 'SS2' if '2号线' in raw or '2号线' in ln['name'] else 'SS1'
    return None  # 502 / 502高峰巴士 / 高淳定时公交 (daytime services)

def parse_endpoints(name):
    if name.endswith((')', '）')):
        depth = 0
        for i in range(len(name) - 1, -1, -1):
            c = name[i]
            if c in '）)':
                depth += 1
            elif c in '（(':
                depth -= 1
                if depth == 0:
                    m = re.match(r'(.+?)-(.+)', name[i + 1:-1])
                    if m:
                        return norm_stop(m.group(1)), norm_stop(m.group(2))
                    break
    return None, None

routes = {}
issues = []
for ln in lines:
    k = route_key(ln)
    if k is None:
        continue
    r = routes.setdefault(k, {'id': k, 'directions': []})
    frm, to = parse_endpoints(ln['name'])
    stops = []
    for s in ln['stations']:
        if s['lng'] is None:
            issues.append(f"no coord: {ln['name']} / {s['name']}")
            continue
        stops.append({'name': norm_stop(s['name']), 'raw': s['name'],
                      'lng': s['lng'], 'lat': s['lat']})
    # drop consecutive duplicates
    ded = []
    for s in stops:
        if ded and ded[-1]['name'] == s['name']:
            continue
        ded.append(s)
    r['directions'].append({
        'uid': ln['uid'], 'name': ln['name'], 'from': frm, 'to': to,
        'start': ln.get('start'), 'end': ln.get('end'),
        'company': ln.get('company'), 'price': ln.get('price'),
        'stops': ded, 'paths': ln.get('paths', []),
    })

# disambiguate suburban stop names that collide with urban stops (e.g. 岔路口)
urban_names = {s['name'] for k, r in routes.items() if not k.startswith(('LS', 'GC'))
               for d in r['directions'] for s in d['stops']}
for k, r in routes.items():
    if not k.startswith(('LS', 'GC')): continue
    suf = '（溧水）' if k.startswith('LS') else '（高淳）'
    for d in r['directions']:
        for s in d['stops']:
            if s['name'] in urban_names:
                s['name'] += suf

# sort directions: outbound first (heuristic: keep crawled order), loop lines keep 内圈/外圈
def route_sort_key(k):
    if k.startswith('LS'): return (2, int(k[3:]))
    if k.startswith('GC'): return (3, int(k[2:]))
    if k.startswith('Y'): return (0, int(k[1:]))
    return (1, k)

out_routes = []
for k in sorted(routes, key=route_sort_key):
    r = routes[k]
    dirs = r['directions']
    if len(dirs) == 2:
        a = {s['name'] for s in dirs[0]['stops']}
        b = {s['name'] for s in dirs[1]['stops']}
        dirs[0]['oneway_stops'] = sorted(a - b)
        dirs[1]['oneway_stops'] = sorted(b - a)
        r['oneway'] = sorted(a ^ b)
    else:
        for d in dirs:
            d['oneway_stops'] = []
        r['oneway'] = []
    r['label'] = ('守时公交1号线' if k == 'SS1' else
                  '守时公交2号线' if k == 'SS2' else
                  '溧水' + k[2:] + '路' if k.startswith('LS') else
                  '高淳' + k[2:] + '路' if k.startswith('GC') else k + '路')
    out_routes.append(r)

# merged stop index
stops = {}
for r in out_routes:
    for d in r['directions']:
        for s in d['stops']:
            e = stops.setdefault(s['name'], {'name': s['name'], 'lngs': [], 'lats': [], 'routes': {}})
            e['lngs'].append(s['lng']); e['lats'].append(s['lat'])
            e['routes'].setdefault(r['id'], []).append(d['name'])
for name, e in stops.items():
    e['lng'] = statistics.mean(e['lngs']); e['lat'] = statistics.mean(e['lats'])
    e['n_routes'] = len(e['routes'])
    e['routes'] = {k: v for k, v in e['routes'].items()}
    del e['lngs']; del e['lats']

network = {
    'city': '南京', 'asof': '2026-11-20',
    'source': '百度地图网页版公交数据（2026-07更新）+ 南京公交集团公告核对',
    'note': 'Y6/Y9/Y14/Y15/Y18/Y19/Y20已撤销；502路白天常规线不计入，夜间服务由守时公交1号线承担；'
            '溧水Y1/Y2/Y5路夜间、高淳801/802/803路为郊区夜间/晚间线路（高淳定时公交为白天线，不计入）',
    'routes': out_routes, 'stops': stops,
}
json.dump(network, open(os.path.join(DATA, 'network.json'), 'w', encoding='utf-8'), ensure_ascii=False)

print('routes:', len(out_routes))
print('directions:', sum(len(r['directions']) for r in out_routes))
print('unique stops:', len(stops))
print('interchange stops (>=2 routes):', sum(1 for e in stops.values() if e['n_routes'] >= 2))
ow = [(r['id'], len(r['oneway'])) for r in out_routes if r['oneway']]
print('routes with oneway stops:', ow)
print('issues:', issues[:10], '...' if len(issues) > 10 else '')
coll = [n for n, e in stops.items()
        if any(k.startswith(('LS', 'GC')) for k in e['routes'])
        and any(not k.startswith(('LS', 'GC')) for k in e['routes'])]
print('suburban/urban shared stop names:', coll)
for r in out_routes:
    d0 = r['directions'][0]
    print(r['id'], '|', ' / '.join(f"{d['from']}→{d['to']} {d['start']}-{d['end']} ({len(d['stops'])}站)" for d in r['directions']))