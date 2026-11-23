# -*- coding: utf-8 -*-
"""Build the night-bus operation simulation schedule.

Departures: authoritative fixed timetables from Baidu (per direction).
Each departure is an independent run from the origin depot: buses do not
turn around in place, so run time is not coupled to headway.
Per-stop arrivals: segment-classified speed model (regular roads 40 km/h
limit, expressway / river-crossing corridors 70 km/h limit, derated for
signals and turns), calibrated against Baidu route-planning segment
durations (data/calib_obs.json, see calibrate_speed.py).
Output: data/schedule.json  {start, end, dirs: {"RID|di": {deps, run, frames}}}
frames = [minuteOffset, lat, lng, headingDeg, alongPathKm] keyframes along the path.
Time-window skip stops (name marker "X时至Y时不停靠") are exported per direction
as skip=[{i, from, to}]; the runtime removes their dwell for affected departures.
"""
import json, math, os, glob, re

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data')
net = json.load(open(os.path.join(DATA, 'network.json'), encoding='utf-8'))
raw = json.load(open(os.path.join(DATA, 'baidu_details.json'), encoding='utf-8'))
for f in glob.glob(os.path.join(DATA, 'ss_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    for v in (d if isinstance(d, list) else [d]):
        if isinstance(v, dict) and 'uid' in v:
            raw[v['uid']] = v
_sub = os.path.join(DATA, 'suburban_details.json')
if os.path.exists(_sub):
    raw.update(json.load(open(_sub, encoding='utf-8')))

KX = math.cos(math.radians(32.1)) * 111.32
KY = 110.9

# speed model: effective km/h per road class + per-turn penalty (min).
# reg: urban streets (40 limit, signals/turns) — calibrated to Baidu's
#      published segment durations (~20 km/h + 0.35 min dwell).
# art: 江北大道地面辅路 (40 limit, few signals) — calibrated to the
#      published SS1 run time of 70 min (南京晨报 2025-06-20).
# fast: limited-access expressway / river crossings (70 limit, no stops
#      for >2.5 km) — 60 km/h effective; Baidu's planner ignores road
#      class so this class cannot be calibrated from its durations.
MODEL = {'v_reg': 20.0, 'v_art': 29.0, 'v_fast': 60.0, 'turn_pen': 0.1, 'dwell': 0.35}
_mp = os.path.join(DATA, 'speed_model.json')
if os.path.exists(_mp):
    MODEL.update(json.load(open(_mp, encoding='utf-8')))
DWELL = MODEL['dwell']

def km(a, b):
    return math.hypot((a[1] - b[1]) * KX, (a[0] - b[0]) * KY)

def rdp(pts, eps):
    if len(pts) < 3: return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1: continue
        ax, ay = pts[i]; bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        dmax, imax = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            if L2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
                d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d > dmax: dmax, imax = d, k
        if dmax > eps:
            keep[imax] = True
            stack.append((i, imax)); stack.append((imax, j))
    return [p for p, k in zip(pts, keep) if k]

def hhmm(s):
    h, m = s.split(':')
    return int(h) * 60 + int(m)

# time-window skip stops: Baidu encodes them in the stop name itself,
# e.g. 双龙街(0时至5时不停靠) — buses pass via the elevated road at night.
SKIP_RE = re.compile(r'(\d{1,2})时至(\d{1,2})时不停靠')

def skip_window(name):
    m = SKIP_RE.search(name)
    if not m:
        return None
    a, b = int(m.group(1)) * 60, int(m.group(2)) * 60
    if a < 720: a += 1440   # night-service absolute minutes (15:00 = 900)
    if b < 720: b += 1440
    if b <= a: b += 1440
    return a, b

def parse_deps(tt, rid):
    tt = tt.strip()
    if '-' in tt and len(tt.split()) <= 2 and ':' in tt.split('-')[0]:
        a, b = (hhmm(x) for x in tt.replace(' ', '').split('-'))
        if b < a: b += 1440
        step = 10 if rid == 'SS2' else 30
        return list(range(a, b + 1, step))
    out = []
    for t in tt.split():
        v = hhmm(t)
        if out and v < out[-1]: v += 1440
        out.append(v)
    return out

def geometry(d):
    """Simplified path + cumulative km + stop projections for a direction."""
    path = rdp([(p[1], p[0]) for p in d['paths'][0]], 1e-4)  # paths are [lng,lat]
    cum = [0.0]
    for a, b in zip(path, path[1:]):
        cum.append(cum[-1] + km(a, b))
    stop_km, stop_pos, vi = [], [], 0
    for s in d['stops']:
        best, bj, bt = 1e18, vi, 0.0
        for j in range(vi, len(path) - 1):
            ax, ay = path[j]; bx, by = path[j + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((s['lat'] - ax) * dx + (s['lng'] - ay) * dy) / L2))
            px, py = ax + t * dx, ay + t * dy
            dd = (px - s['lat']) ** 2 + ((py - s['lng']) * KX / KY) ** 2
            if dd < best: best, bj, bt = dd, j, t
        vi = bj
        seglen = cum[bj + 1] - cum[bj]
        stop_km.append(cum[bj] + bt * seglen)
        stop_pos.append((path[bj][0] + bt * (path[bj + 1][0] - path[bj][0]),
                         path[bj][1] + bt * (path[bj + 1][1] - path[bj][1])))
    for i in range(1, len(stop_km)):
        if stop_km[i] < stop_km[i - 1]:
            stop_km[i] = stop_km[i - 1] + 1e-6
    return {'path': path, 'cum': cum, 'stop_km': stop_km, 'stop_pos': stop_pos}

# ---- 江北大道地面辅路 corridor (arterial class), from SS1's own geometry ----
ART_SPEC = ('SS1', 0, '宁六路·丽景路', '方州广场东')
ART_BUFFER = 0.45  # km either side of corridor centreline

_r = next(x for x in net['routes'] if x['id'] == ART_SPEC[0])
_d = _r['directions'][ART_SPEC[1]]
_g = geometry(_d)
_names = [s['name'] for s in _d['stops']]
_i1, _i2 = _names.index(ART_SPEC[2]), _names.index(ART_SPEC[3])
_k1, _k2 = sorted((_g['stop_km'][_i1], _g['stop_km'][_i2]))
ART_CORRIDOR = [_g['stop_pos'][_i1 if _g['stop_km'][_i1] == _k1 else _i2]]
for _j, _c in enumerate(_g['cum']):
    if _k1 < _c < _k2:
        ART_CORRIDOR.append(_g['path'][_j])
ART_CORRIDOR.append(_g['stop_pos'][_i2 if _g['stop_km'][_i2] == _k2 else _i1])

def _pt_seg_km(p, a, b):
    dx, dy = (b[0] - a[0]) * KY, (b[1] - a[1]) * KX
    px, py = (p[0] - a[0]) * KY, (p[1] - a[1]) * KX
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px * dx + py * dy) / L2))
    return math.hypot(px - t * dx, py - t * dy)

def near_art(p):
    for a, b in zip(ART_CORRIDOR, ART_CORRIDOR[1:]):
        if _pt_seg_km(p, a, b) <= ART_BUFFER:
            return True
    return False

def heading(a, b):
    return math.degrees(math.atan2((b[1] - a[1]) * KX / KY, b[0] - a[0]))

def turn_count(path, j1, j2):
    """Sharp turns (>45 deg) at interior vertices of path[j1:j2+1]."""
    n = 0
    for j in range(max(1, j1), min(j2, len(path) - 1)):
        d = abs((heading(path[j], path[j + 1]) - heading(path[j - 1], path[j]) + 540) % 360 - 180)
        if d > 45: n += 1
    return n

def classify(g):
    """Per path-segment class. 'fast': inside a >2.5 km straight-line stop
    gap (limited-access expressway / river-crossing sections, or suburban
    arterial non-stop runs). 'art': near the 江北大道 surface corridor.
    'reg': everything else."""
    cls = []
    si = 0
    skm = g['stop_km']
    for j in range(len(g['path']) - 1):
        while si + 1 < len(skm) and skm[si + 1] <= g['cum'][j] + 1e-9:
            si += 1
        fast = False
        if si + 1 < len(skm):
            a, b = g['stop_pos'][si], g['stop_pos'][si + 1]
            if math.hypot((b[1] - a[1]) * KX, (b[0] - a[0]) * KY) > 2.5:
                fast = True
        if fast:
            cls.append('fast')
            continue
        mid = ((g['path'][j][0] + g['path'][j + 1][0]) / 2,
               (g['path'][j][1] + g['path'][j + 1][1]) / 2)
        cls.append('art' if near_art(mid) else 'reg')
    return cls

def run_time_profile(g, cls):
    """Cumulative running minutes at each path vertex (turn penalties incl.)."""
    ct = [0.0]
    for j, c in enumerate(cls):
        v = MODEL['v_fast'] if c == 'fast' else MODEL['v_art'] if c == 'art' else MODEL['v_reg']
        dt = (g['cum'][j + 1] - g['cum'][j]) / v * 60
        if j > 0:
            d = abs((heading(g['path'][j], g['path'][j + 1]) -
                     heading(g['path'][j - 1], g['path'][j]) + 540) % 360 - 180)
            if d > 45: dt += MODEL['turn_pen']
        ct.append(ct[-1] + dt)
    return ct

def runT(g, ct, x):
    """Running minutes at along-path km x (linear interp on vertices)."""
    cum = g['cum']
    if x <= 0: return 0.0
    if x >= cum[-1]: return ct[-1]
    j = 0
    while j < len(cum) - 2 and cum[j + 1] < x:
        j += 1
    f = (x - cum[j]) / (cum[j + 1] - cum[j]) if cum[j + 1] > cum[j] else 0.0
    return ct[j] + f * (ct[j + 1] - ct[j])

def main():
    sched = {'model': MODEL, 'dirs': {}}
    all_deps, all_end = [], []
    skip_stops = {}
    for r in net['routes']:
        for di, d in enumerate(r['directions']):
            det = raw.get(d['uid'])
            if not det:
                raise SystemExit('no detail for ' + d['name'])
            deps = parse_deps((det.get('timetable') or '').strip() or f"{d['start']} {d['end']}", r['id'])
            if deps[0] < 720:  # service starting after midnight belongs to day+1
                deps = [v + 1440 for v in deps]
            g = geometry(d)
            cls = classify(g)
            ct = run_time_profile(g, cls)
            path, cum = g['path'], g['cum']
            stop_km, stop_pos = g['stop_km'], g['stop_pos']
            offs = [runT(g, ct, k) + i * DWELL for i, k in enumerate(stop_km)]
            run = offs[-1]
            # keyframes: dwell at each stop projection, move along path vertices
            # frame = [minuteOffset, lat, lng, headingDeg, alongPathKm]
            frames = [[0.0, stop_pos[0][0], stop_pos[0][1], round(heading(path[0], path[1]), 1), stop_km[0]],
                      [DWELL, stop_pos[0][0], stop_pos[0][1], round(heading(path[0], path[1]), 1), stop_km[0]]]
            si = 0
            for j in range(len(path) - 1):
                a, b = path[j], path[j + 1]
                ang = round(heading(a, b), 1)
                if j > 0:
                    t = ct[j] + (si + 1) * DWELL
                    frames.append([round(min(t, run), 2), a[0], a[1], ang, cum[j]])
                while si + 1 < len(stop_km) and stop_km[si + 1] <= cum[j + 1] + 1e-9:
                    si += 1
                    frames.append([round(offs[si], 2), stop_pos[si][0], stop_pos[si][1], ang, stop_km[si]])
                    frames.append([round(offs[si] + DWELL, 2), stop_pos[si][0], stop_pos[si][1], ang, stop_km[si]])
            frames.append([round(run, 2), stop_pos[-1][0], stop_pos[-1][1], frames[-1][3], stop_km[-1]])
            # monotonic time + dedupe
            clean = []
            for f in frames:
                if clean and f[0] <= clean[-1][0]:
                    f = [clean[-1][0] + 0.01, f[1], f[2], f[3], f[4]]
                if clean and f[1] == clean[-1][1] and f[2] == clean[-1][2] and f[0] - clean[-1][0] < 0.02:
                    continue
                clean.append(f)
            key = f"{r['id']}|{di}"
            entry = {'deps': deps, 'run': round(run, 2),
                     'stopT': [round(o, 2) for o in offs],
                     'stopKm': [round(k, 3) for k in stop_km], 'frames': clean}
            skip = []
            for i, s in enumerate(d['stops']):
                w = skip_window(s['name'])
                if w and 0 < i < len(d['stops']) - 1:
                    skip.append({'i': i, 'from': w[0], 'to': w[1]})
                    ent = skip_stops.setdefault(s['name'], {
                        'name': s['name'],
                        'window': f"{w[0]//60%24:02d}:{w[0]%60:02d}–{w[1]//60%24:02d}:{w[1]%60:02d}",
                        'dirs': []})
                    ent['dirs'].append(key)
            if skip:
                entry['skip'] = skip
            sched['dirs'][key] = entry
            all_deps += deps
            all_end += [deps[-1] + run]

    sched['start'] = min(all_deps)
    sched['end'] = round(max(all_end), 1)
    if skip_stops:
        sched['skipStops'] = list(skip_stops.values())
    peak = 0
    for t in range(sched['start'], int(sched['end']) + 1, 5):
        n = sum(1 for v in sched['dirs'].values() for dep in v['deps'] if dep <= t <= dep + v['run'])
        peak = max(peak, n)
    sched['peak'] = peak
    out = os.path.join(DATA, 'schedule.json')
    json.dump(sched, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    nf = sum(len(v['frames']) for v in sched['dirs'].values())
    nd = sum(len(v['deps']) for v in sched['dirs'].values())
    print(f"schedule.json: {os.path.getsize(out)/1024:.0f} KB, dirs={len(sched['dirs'])}, departures={nd}, frames={nf}")
    print(f"model: v_reg={MODEL['v_reg']:.1f} v_fast={MODEL['v_fast']:.1f} km/h, turn_pen={MODEL['turn_pen']:.2f} min, dwell={DWELL:.2f} min")
    print(f"sim window: {sched['start']//60:02d}:{sched['start']%60:02d} -> {int(sched['end'])//60%24:02d}:{int(sched['end'])%60:02d} (+1d), peak concurrent={peak}")
    for s in skip_stops.values():
        print(f"skip stop: {s['name']} window {s['window']} dirs {s['dirs']}")

if __name__ == '__main__':
    main()