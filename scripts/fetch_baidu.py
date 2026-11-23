# -*- coding: utf-8 -*-
"""Fetch Nanjing night bus lines from Baidu Map web API (qt=con/inf/bsl)."""
import json, math, re, time, urllib.request, urllib.parse, os, sys

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(DATA, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0',
      'Referer': 'https://map.baidu.com/'}
BASE = 'https://map.baidu.com/?'
COMMON = 'newmap=1&reqflag=pcmap&biz=1&from=webmap&da_par=direct&pcevaname=pc4.1'

def get(params, tries=3):
    url = BASE + params
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                txt = r.read().decode('utf-8', 'replace')
            if txt.strip():
                return json.loads(txt)
        except Exception as e:
            print('  retry', i, e, flush=True)
        time.sleep(1 + i)
    return None

def search(wd, rn=20, pn=0):
    p = f'{COMMON}&qt=con&c=315&wd={urllib.parse.quote(wd)}&nn=0&db=0&sug=0&addr=0&on_gel=1&src=7&gr=3&l=12&rn={rn}&pn={pn}'
    return get(p)

def inf(uid):
    return get(f'{COMMON}&qt=inf&uid={uid}&c=315&l=12')

def bsl(uid, auth):
    p = f'{COMMON}&qt=bsl&uid={uid}&c=315&auth={urllib.parse.quote(auth)}&device_ratio=1&l=12'
    return get(p)

def is_busline(it):
    return isinstance(it, dict) and any(c[0] == 903 for c in it.get('cla', []) if isinstance(c, list))

# ---- coordinate conversion BD09MC -> BD09LL -> GCJ02 -> WGS84 ----
MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.87, 1678043.12, 0]
MC2LL = [
 [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331, 200.9824383106796, -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
 [-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289, 96.32687599759846, -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
 [-3.030883460898826e-8, 0.000008983055099835726, 0.30071316287616, 59.74293618442277, 7.35796249210497, -25.38371002664745, 13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
 [-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591, 40.31678527705744, 0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
 [3.09191371068437e-9, 0.000008983055096904627, 0.00006377998203, 20.45646794248399, 0.58106424092035, -0.64991698352356, 0.05540595248354, 0.01392550200146, -0.00138495017259, 2409888.13],
 [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]

def mc2ll(x, y):
    x, y = abs(x), abs(y)
    c = None
    for i, band in enumerate(MCBAND):
        if y >= band:
            c = MC2LL[i]; break
    lng = c[0] + c[1] * x
    cc = y / c[9]
    lat = c[2] + c[3]*cc + c[4]*cc**2 + c[5]*cc**3 + c[6]*cc**4 + c[7]*cc**5 + c[8]*cc**6
    return lng, lat

X_PI = math.pi * 3000.0 / 180.0
def bd2gcj(bl, bt):
    x, y = bl - 0.0065, bt - 0.006
    z = math.sqrt(x*x + y*y) - 0.00002 * math.sin(y * X_PI)
    t = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(t), z * math.sin(t)

A = 6378245.0
EE = 0.00669342162296594323
def _tlat(x, y):
    r = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    r += (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi)) * 2/3
    r += (20*math.sin(y*math.pi) + 40*math.sin(y/3*math.pi)) * 2/3
    r += (160*math.sin(y/12*math.pi) + 320*math.sin(y*math.pi/30)) * 2/3
    return r
def _tlng(x, y):
    r = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    r += (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi)) * 2/3
    r += (20*math.sin(x*math.pi) + 40*math.sin(x/3*math.pi)) * 2/3
    r += (150*math.sin(x/12*math.pi) + 300*math.sin(x/30*math.pi)) * 2/3
    return r
def gcj2wgs(lng, lat):
    dlat, dlng = _tlat(lng-105, lat-35), _tlng(lng-105, lat-35)
    rl = lat/180*math.pi
    m = 1 - EE*math.sin(rl)**2
    sm = math.sqrt(m)
    dlat = (dlat*180)/((A*(1-EE))/(m*sm)*math.pi)
    dlng = (dlng*180)/(A/sm*math.cos(rl)*math.pi)
    return lng*2-(lng+dlng), lat*2-(lat+dlat)

def to_wgs(x, y):
    bl, bt = mc2ll(x, y)
    gl, gt = bd2gcj(bl, bt)
    return gcj2wgs(gl, gt)

def parse_pt(geo):
    # "1|x,y;x,y|x,y;" -> first pair
    m = re.search(r'([\d.]+),([\d.]+)', geo or '')
    if not m: return None
    return to_wgs(float(m.group(1)), float(m.group(2)))

def parse_line_geo(geo):
    # "2|bbox|poly;poly;..." polys are comma-separated x,y pairs
    parts = (geo or '').split('|')
    if len(parts) < 3: return []
    out = []
    for poly in parts[2].split(';'):
        nums = [float(v) for v in poly.split(',') if v]
        pts = [to_wgs(nums[i], nums[i+1]) for i in range(0, len(nums)-1, 2)]
        if len(pts) >= 2: out.append(pts)
    return out

def main():
    queries = [f'Y{n}路' for n in range(1, 46)] + ['502路', '守时公交2号线', '地铁末班守时公交']
    found = {}   # uid -> search item
    for q in queries:
        d = search(q)
        time.sleep(0.25)
        if not d:
            print('SEARCH FAIL', q, flush=True); continue
        items = [it for it in d.get('content', []) if is_busline(it)]
        keep = []
        for it in items:
            nm = it.get('name', '')
            if q.startswith('Y'):
                n = q[:-1]
                if not re.match(rf'^{n}路', nm): continue
                if nm.startswith(('溧水', '高淳')): continue
            elif q == '502路':
                if not nm.startswith('502路'): continue
            else:
                if '守时' not in nm: continue
            keep.append(it)
            found[it['uid']] = it
        print(q, '->', [it['name'] for it in keep], flush=True)

    print('total uids:', len(found), flush=True)
    json.dump(list(found.values()), open(os.path.join(DATA, 'search_items.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    auth = None
    details = {}
    for uid, it in found.items():
        d = inf(uid)
        time.sleep(0.2)
        if d and d.get('anti_auth'):
            auth = d['anti_auth']
        b = bsl(uid, auth or '')
        time.sleep(0.25)
        if not b or not b.get('content'):
            d = inf(uid); time.sleep(0.2)
            auth = (d or {}).get('anti_auth', auth)
            b = bsl(uid, auth or ''); time.sleep(0.25)
        if not b or not b.get('content'):
            print('DETAIL FAIL', it['name'], uid, flush=True); continue
        if b.get('anti_auth'): auth = b['anti_auth']
        line = b['content'][0]
        details[uid] = line
        # follow pair line if not already in found
        pl = line.get('pair_line') or {}
        puid = pl.get('uid')
        if puid and puid not in found and puid not in details:
            time.sleep(0.25)
            pb = bsl(puid, auth or '')
            if not pb or not pb.get('content'):
                pd = inf(puid); time.sleep(0.2)
                auth = (pd or {}).get('anti_auth', auth)
                pb = bsl(puid, auth or ''); time.sleep(0.25)
            if pb and pb.get('content'):
                if pb.get('anti_auth'): auth = pb['anti_auth']
                details[puid] = pb['content'][0]
                print('  pair:', pb['content'][0]['name'], flush=True)
            else:
                print('  PAIR FAIL', pl.get('name'), flush=True)
        print('OK', line['name'], 'stations:', len(line.get('stations', [])), flush=True)

    json.dump(details, open(os.path.join(DATA, 'baidu_details.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    # consolidated output
    lines = []
    for uid, ln in details.items():
        stations = []
        for s in ln.get('stations', []):
            pt = parse_pt(s.get('geo'))
            stations.append({'name': s['name'], 'uid': s.get('uid'),
                             'lng': pt[0] if pt else None, 'lat': pt[1] if pt else None})
        lines.append({
            'uid': uid, 'name': ln['name'], 'raw_name': ln.get('raw_name'),
            'start': ln.get('startTime'), 'end': ln.get('endTime'),
            'company': ln.get('company'), 'price': ln.get('ticketPrice'),
            'pair_uid': (ln.get('pair_line') or {}).get('uid'),
            'pair_name': (ln.get('pair_line') or {}).get('name'),
            'stations': stations,
            'paths': parse_line_geo(ln.get('geo')),
        })
    json.dump(lines, open(os.path.join(DATA, 'lines_wgs84.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('DONE', len(lines), 'directions', flush=True)

if __name__ == '__main__':
    main()