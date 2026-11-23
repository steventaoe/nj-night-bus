# -*- coding: utf-8 -*-
"""Calibrate the segment speed model against Baidu route-planning durations.

For spans of each night line (full run + expressway/bridge spans + a mid
urban span), query map.baidu.com qt=bt and extract the bus segment that
boards/alights exactly at our stops: it carries distance (m) and time (s).
Fit  t = Lreg/vr + Lfast/vf + nturns*turn_pen + nstops*dwell  by least
squares, then write data/speed_model.json used by build_schedule.py.
"""
import json, math, os, sys, time, urllib.parse
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import build_schedule as bs
import fetch_baidu as fb

DATA = bs.DATA

def wgs2gcj(lng, lat):
    dlat, dlng = fb._tlat(lng - 105, lat - 35), fb._tlng(lng - 105, lat - 35)
    rl = lat / 180 * math.pi
    m = 1 - fb.EE * math.sin(rl) ** 2
    sm = math.sqrt(m)
    dlat = (dlat * 180) / ((fb.A * (1 - fb.EE)) / (m * sm) * math.pi)
    dlng = (dlng * 180) / (fb.A / sm * math.cos(rl) * math.pi)
    return lng + dlng, lat + dlat

def gcj2bd(lng, lat):
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * fb.X_PI)
    t = math.atan2(lat, lng) + 0.000003 * math.cos(lng * fb.X_PI)
    return z * math.cos(t) + 0.0065, z * math.sin(t) + 0.006

def ll2mc(lng, lat):
    x, y = lng * 111320 * math.cos(lat / 180 * math.pi), lat * 110540
    for _ in range(30):
        gl, gt = fb.mc2ll(x, y)
        ex, ey = gl - lng, gt - lat
        if abs(ex) < 1e-9 and abs(ey) < 1e-9: break
        h = 1.0
        gx1, gy1 = fb.mc2ll(x + h, y); gx2, gy2 = fb.mc2ll(x, y + h)
        a, b = (gx1 - gl) / h, (gx2 - gl) / h
        c, d = (gy1 - gt) / h, (gy2 - gt) / h
        det = a * d - b * c
        x -= (d * ex - b * ey) / det; y -= (-c * ex + a * ey) / det
    return x, y

def mc_of(nm):
    s = bs.net['stops'][nm]
    gl, gt = wgs2gcj(s['lng'], s['lat'])
    bl, bt = gcj2bd(gl, gt)
    return ll2mc(bl, bt)

def query_span(n1, n2):
    a, b = mc_of(n1), mc_of(n2)
    sn = f'1$$$${a[0]:.0f},{a[1]:.0f}$${n1}$$0$$$$'
    en = f'1$$$${b[0]:.0f},{b[1]:.0f}$${n2}$$0$$$$'
    p = (fb.COMMON + '&qt=bt&c=315&sn=' + urllib.parse.quote(sn) +
         '&en=' + urllib.parse.quote(en) + '&sy=0&version=5&rn=10&ie=utf-8')
    return fb.get(p)

def _variants(r):
    lines, stops = r.get('lines', []), r.get('stops', [])
    if lines and isinstance(lines[0], list):
        yield from zip(lines, stops)
    else:
        yield lines, stops

def match_segment(resp, n1, n2, span_km):
    best = None
    for r in (resp or {}).get('content', []) or []:
        if not isinstance(r, dict): continue
        for lines, stops in _variants(r):
            if len(stops) < 2 or not all(isinstance(s, dict) for s in (stops[0], stops[-1])):
                continue
            gon, goff = stops[0].get('getOn'), stops[-1].get('getOff')
            on = gon.get('name', '') if isinstance(gon, dict) else ''
            off = goff.get('name', '') if isinstance(goff, dict) else ''
            if on != n1 or off != n2: continue
            segs = [l for l in lines if isinstance(l, dict) and l.get('time') and l.get('distance')]
            if len(segs) != 1: continue  # only direct single-bus rides
            ln = segs[0]
            err = abs(ln['distance'] - span_km * 1000)
            if err > max(800.0, 0.12 * span_km * 1000): continue  # different path
            if best is None or err < best[0]:
                best = (err, {'time': ln['time'], 'dist': ln['distance'],
                              'nstops': ln.get('station_num', 0), 'line': ln.get('name', '')})
    return best[1] if best else None

def span_features(g, cls, i1, i2):
    k1, k2 = g['stop_km'][i1], g['stop_km'][i2]
    L = {'reg': 0.0, 'art': 0.0, 'fast': 0.0}
    for j, c in enumerate(cls):
        a, b = g['cum'][j], g['cum'][j + 1]
        ov = max(0.0, min(b, k2) - max(a, k1))
        if ov > 0: L[c] += ov
    nturn = 0
    for j in range(1, len(g['path']) - 1):
        if k1 + 1e-6 < g['cum'][j] < k2 - 1e-6:
            d = abs((bs.heading(g['path'][j], g['path'][j + 1]) -
                     bs.heading(g['path'][j - 1], g['path'][j]) + 540) % 360 - 180)
            if d > 45: nturn += 1
    return L['reg'], L['art'], L['fast'], nturn, i2 - i1 - 1

def main():
    obs = []
    cache_path = os.path.join(DATA, 'calib_obs.json')
    done = set()
    if os.path.exists(cache_path):
        obs = json.load(open(cache_path, encoding='utf-8'))
        done = {(o['rid'], o['di'], o['n1'], o['n2']) for o in obs}
    nq = nfail = 0
    for r in bs.net['routes']:
        for di, d in enumerate(r['directions']):
            g = bs.geometry(d)
            cls = bs.classify(g)
            ns = [s['name'] for s in d['stops']]
            n = len(ns)
            spans = [(0, n - 1)]
            gaps = [i for i in range(n - 1)
                    if math.hypot((d['stops'][i + 1]['lat'] - d['stops'][i]['lat']) * bs.KY,
                                  (d['stops'][i + 1]['lng'] - d['stops'][i]['lng']) * bs.KX) > 2.5]
            if gaps:
                i = gaps[0]
                spans.append((i, i + 1))
            else:
                spans.append((n // 3, 2 * n // 3))
            for i1, i2 in spans:
                if i2 - i1 < 2: continue
                key = (r['id'], di, ns[i1], ns[i2])
                if key in done: continue
                Lreg, Lart, Lfast, nturn, nmid = span_features(g, cls, i1, i2)
                span_km = g['stop_km'][i2] - g['stop_km'][i1]
                resp = query_span(ns[i1], ns[i2])
                nq += 1
                time.sleep(0.3)
                m = match_segment(resp, ns[i1], ns[i2], span_km)
                if not m:
                    nfail += 1
                    print('MISS', r['id'], di, ns[i1], '->', ns[i2], flush=True)
                    continue
                obs.append({'rid': r['id'], 'di': di, 'n1': ns[i1], 'n2': ns[i2],
                            'Lreg': round(Lreg, 3), 'Lart': round(Lart, 3),
                            'Lfast': round(Lfast, 3),
                            'nturn': nturn, 'nmid': nmid, 'span_km': round(span_km, 3),
                            **m})
                done.add(key)
                json.dump(obs, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                print(f"OK {r['id']}|{di} {ns[i1]}->{ns[i2]} {m['dist']}m {m['time']}s "
                      f"({m['line'][:22]}) reg={Lreg:.1f} art={Lart:.1f} fast={Lfast:.1f}", flush=True)
    print(f'queries={nq} misses={nfail} observations={len(obs)}', flush=True)
    if len(obs) < 10:
        raise SystemExit('too few observations to fit')
    fit(obs)

def fit(obs):
    # Recompute span features under the current classification, then fit
    # urban observations (no fast/art sections):
    #   t_sec = 60/v_reg*Lreg + turn_pen*60*nturn + dwell*60*nmid
    # Baidu's planner uses a uniform ~20 km/h regardless of road class, so
    # only urban spans calibrate v_reg; v_fast is the 70 km/h limit derated
    # for night running, and v_art comes from the published SS1 run time.
    rows = []
    for o in obs:
        r = next(x for x in bs.net['routes'] if x['id'] == o['rid'])
        d = r['directions'][o['di']]
        g = bs.geometry(d)
        cls = bs.classify(g)
        ns = [s['name'] for s in d['stops']]
        i1, i2 = ns.index(o['n1']), ns.index(o['n2'])
        span_km = g['stop_km'][i2] - g['stop_km'][i1]
        if abs(o['dist'] - span_km * 1000) > max(800.0, 0.12 * span_km * 1000):
            continue  # Baidu segment followed a different route's path
        Lreg, Lart, Lfast, nturn, nmid = span_features(g, cls, i1, i2)
        rows.append((o, Lreg, Lart, Lfast, nturn, nmid))
    urban = [(o, lr, nt, nm) for o, lr, la, lf, nt, nm in rows if la < 0.3 and lf < 0.3]
    A = np.array([[lr, nt, nm] for _, lr, nt, nm in urban])
    t = np.array([o['time'] for o, *_ in urban], dtype=float)
    tp = bs.MODEL['turn_pen']
    x, *_ = np.linalg.lstsq(A[:, [0, 2]], t - tp * 60 * A[:, 1], rcond=None)
    vr, dwell = 3600 / x[0], x[1] / 60
    print(f'urban fit on {len(urban)} spans: v_reg={vr:.2f} km/h dwell={dwell:.3f} min (turn_pen fixed {tp})')
    vr = min(40.0, max(15.0, vr)); dwell = min(0.6, max(0.2, dwell))

    # v_art from published SS1 泰冯路->方州广场东: 38 stops, 70 min
    # (南京晨报 2025-06-20, http://njcb.xhby.net/pc/con/202506/20/content_1458708.html)
    r = next(x for x in bs.net['routes'] if x['id'] == 'SS1')
    d = r['directions'][1]
    g = bs.geometry(d)
    cls = bs.classify(g)
    Lreg, Lart, Lfast, nturn, nmid = span_features(g, cls, 0, len(d['stops']) - 1)
    t_art = 70 - dwell * nmid - tp * nturn - Lreg / vr * 60 - Lfast / bs.MODEL['v_fast'] * 60
    v_art = Lart / t_art * 60
    print(f'SS1 published 70 min: reg={Lreg:.1f} art={Lart:.1f} fast={Lfast:.1f} km '
          f'-> v_art={v_art:.2f} km/h')
    v_art = min(40.0, max(20.0, v_art))

    model = {'v_reg': round(vr, 2), 'v_art': round(v_art, 2),
             'v_fast': bs.MODEL['v_fast'], 'turn_pen': tp, 'dwell': round(dwell, 3)}
    pred = np.array([lr / model['v_reg'] * 3600 + la / model['v_art'] * 3600 +
                     lf / model['v_fast'] * 3600 + nt * tp * 60 + nm * model['dwell'] * 60
                     for _, lr, la, lf, nt, nm in rows])
    tall = np.array([o['time'] for o, *_ in rows])
    err = pred - tall
    print(f'model {model}')
    print(f'all-span MAE={np.abs(err).mean():.0f}s (Baidu ignores road class; '
          f'fast/art spans expected to differ)')
    uerr = np.array([lr / model['v_reg'] * 3600 + nt * tp * 60 + nm * model['dwell'] * 60
                     for _, lr, nt, nm in urban]) - t
    print(f'urban MAE={np.abs(uerr).mean():.0f}s max={np.abs(uerr).max():.0f}s')
    for (o, lr, la, lf, nt, nm), e in sorted(zip(rows, err), key=lambda z: -abs(z[1]))[:6]:
        print(f"  {o['rid']}|{o['di']} {o['n1'][:8]}->{o['n2'][:8]}: obs={o['time']}s "
              f"pred={o['time']+e:.0f}s reg={lr:.1f} art={la:.1f} fast={lf:.1f}")
    json.dump(model, open(os.path.join(DATA, 'speed_model.json'), 'w', encoding='utf-8'), indent=1)
    print('speed_model.json written')

if __name__ == '__main__':
    main()