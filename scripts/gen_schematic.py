# -*- coding: utf-8 -*-
"""Generate a metro-style schematic SVG of the Nanjing night bus network."""
import json, math, os, re
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data')
net = json.load(open(os.path.join(DATA, 'network.json'), encoding='utf-8'))
routes = net['routes']
stops = net['stops']

# ---------- palette ----------
def hsl(h, s, l):
    return f'hsl({h:.0f},{s:.0f}%,{l:.0f}%)'
Y_IDS = [r['id'] for r in routes if r['id'].startswith('Y')]
COLORS = {}
for i, rid in enumerate(sorted(Y_IDS, key=lambda s: int(s[1:]))):
    h = (i * 137.508 + 15) % 360
    s = 72 if i % 3 else 62
    l = 60 if i % 2 else 52
    COLORS[rid] = hsl(h, s, l)
COLORS['SS1'] = '#f8fafc'   # 守时1号线: white (night flagship)
COLORS['SS2'] = '#fbbf24'   # 守时2号线: amber

# ---------- projection ----------
LNG0, LAT0 = 118.78, 32.06
KX = math.cos(math.radians(32.1)) * 111.32
KY = 110.9
SCALE = 52.0  # px per km
ROT = math.radians(-18)   # rotate layout so suburban tails align to axes
CR = math.cos(ROT); SR = math.sin(ROT)
def proj(lng, lat):
    x = (lng - LNG0) * KX * SCALE
    y = -(lat - LAT0) * KY * SCALE
    return (x * CR - y * SR, x * SR + y * CR)

pos = {n: proj(s['lng'], s['lat']) for n, s in stops.items()}

# radial compression of suburban tails (schematic convention)
cx0 = sum(q[0] for q in pos.values()) / len(pos)
cy0 = sum(q[1] for q in pos.values()) / len(pos)
R0, COMP = 360.0, 0.55
def compress(pt):
    dx, dy = pt[0] - cx0, pt[1] - cy0
    r = math.hypot(dx, dy)
    if r <= R0: return pt
    f = (R0 + (r - R0) * COMP) / r
    return (cx0 + dx * f, cy0 + dy * f)
pos = {n: compress(q) for n, q in pos.items()}

# ---------- stop graph ----------
edges = {}          # frozenset({a,b}) -> set(route ids)
adj = defaultdict(set)
route_edges = defaultdict(list)   # rid -> list of edge keys in order (dir0)
terminals = set()
for r in routes:
    rid = r['id']
    for di, d in enumerate(r['directions']):
        ns = [s['name'] for s in d['stops']]
        terminals.add(ns[0]); terminals.add(ns[-1])
        for a, b in zip(ns, ns[1:]):
            if a == b: continue
            k = frozenset((a, b))
            edges.setdefault(k, set()).add(rid)
            adj[a].add(b); adj[b].add(a)
            if di == 0:
                route_edges[rid].append(k)

# ---------- octilinear schematic layout ----------
# Every segment is exactly horizontal, vertical or 45°. Station spacing is
# uniform (metro convention); geography only seeds the layout via a weak anchor.
L_MIN, L_MAX = 26.0, 140.0
OCT = [(1, 0), (math.sqrt(.5), math.sqrt(.5)), (0, 1), (-math.sqrt(.5), math.sqrt(.5)),
       (-1, 0), (-math.sqrt(.5), -math.sqrt(.5)), (0, -1), (math.sqrt(.5), -math.sqrt(.5))]
OCT_ANG = [math.atan2(d[1], d[0]) for d in OCT]

def oct_dev(bear, o):
    return math.degrees(abs((bear - OCT_ANG[o] + math.pi) % (2 * math.pi) - math.pi))

# Direction runs: DP per route direction minimizes turns + deviation from the
# current layout, so consecutive stations share one direction (straight runs).
SWITCH = 35.0
def assign_dirs(cur):
    votes = defaultdict(list)
    for r in routes:
        for d in r['directions']:
            ns = [s['name'] for s in d['stops']]
            seq = [(a, b) for a, b in zip(ns, ns[1:]) if a != b]
            if not seq: continue
            bears = [math.atan2(cur[b][1] - cur[a][1], cur[b][0] - cur[a][0]) for a, b in seq]
            dp = [oct_dev(bears[0], o) for o in range(8)]
            back = []
            for i in range(1, len(seq)):
                nd = [0.0] * 8; bk = [0] * 8
                for o in range(8):
                    best = min(range(8), key=lambda q: dp[q] + (0 if q == o else SWITCH))
                    nd[o] = dp[best] + (0 if best == o else SWITCH) + oct_dev(bears[i], o)
                    bk[o] = best
                dp = nd; back.append(bk)
            o = min(range(8), key=lambda q: dp[q])
            assign = [o]
            for bk in reversed(back):
                o = bk[o]; assign.append(o)
            assign.reverse()
            for (a, b), o in zip(seq, assign):
                votes[frozenset((a, b))].append(o if a < b else (o + 4) % 8)
    return votes

EDGE_L = {}
for k in edges:
    a, b = sorted(k)
    geo = math.hypot(pos[b][0] - pos[a][0], pos[b][1] - pos[a][1])
    EDGE_L[k] = L_MIN if geo <= 60 else min(L_MIN + (geo - 60) * 0.25, L_MAX)

ANCHOR = 0.02
# exact least-squares octilinear layout: x and y separate into two SPD systems
import numpy as np
names = list(pos)
idx = {n: i for i, n in enumerate(names)}
N = len(names)
M = np.zeros((N, N))
for k in edges:
    a, b = sorted(k)
    ia, ib = idx[a], idx[b]
    M[ia, ia] += 1; M[ib, ib] += 1; M[ia, ib] -= 1; M[ib, ia] -= 1
M[np.diag_indices(N)] += ANCHOR

def solve(votes):
    el = []
    rx = np.zeros(N); ry = np.zeros(N)
    for k in edges:
        a, b = sorted(k)
        v = votes.get(k)
        o = max(set(v), key=v.count) if v else 0
        d = OCT[o]; L = EDGE_L[k]
        el.append([a, b, L, d])
        ia, ib = idx[a], idx[b]
        rx[ia] -= L * d[0]; rx[ib] += L * d[0]
        ry[ia] -= L * d[1]; ry[ib] += L * d[1]
    for n, i in idx.items():
        rx[i] += ANCHOR * pos[n][0]; ry[i] += ANCHOR * pos[n][1]
    px = np.linalg.solve(M, rx); py = np.linalg.solve(M, ry)
    return el, {n: (float(px[i]), float(py[i])) for n, i in idx.items()}

# self-consistency: directions adapt to the solved layout, layout to directions
cur = pos
for it in range(5):
    elist, p = solve(assign_dirs(cur))
    cur = p

# reweighted solve: confident edges become exactly octilinear; cycle closure
# error is pushed onto the few turning edges, which receive a bend instead
def solve_w(el, ws):
    Mw = np.zeros((N, N))
    rx = np.zeros(N); ry = np.zeros(N)
    for (a, b, L, d), w in zip(el, ws):
        ia, ib = idx[a], idx[b]
        Mw[ia, ia] += w; Mw[ib, ib] += w; Mw[ia, ib] -= w; Mw[ib, ia] -= w
        rx[ia] -= w * L * d[0]; rx[ib] += w * L * d[0]
        ry[ia] -= w * L * d[1]; ry[ib] += w * L * d[1]
    Mw[np.diag_indices(N)] += ANCHOR
    for n, i in idx.items():
        rx[i] += ANCHOR * pos[n][0]; ry[i] += ANCHOR * pos[n][1]
    px = np.linalg.solve(Mw, rx); py = np.linalg.solve(Mw, ry)
    return {n: (float(px[i]), float(py[i])) for n, i in idx.items()}

for _ in range(3):
    ws = []
    for a, b, L, d in elist:
        dx, dy = p[b][0] - p[a][0], p[b][1] - p[a][1]
        Ll = math.hypot(dx, dy) or 1
        ws.append(64.0 if (dx * d[0] + dy * d[1]) / Ll > 0.995 else 1.0)
    p = solve_w(elist, ws)

# exact octilinearity: insert one bend where relaxation left a residual angle
GEOM = {}
n_bent = 0
for a, b, L, d in elist:
    ax, ay = p[a]; bx, by = p[b]
    dx, dy = bx - ax, by - ay
    Ll = math.hypot(dx, dy)
    k = frozenset((a, b))
    if Ll < 1e-6:
        GEOM[k] = [(ax, ay), (bx, by)]
        continue
    if (dx * d[0] + dy * d[1]) / Ll > 0.9995:
        GEOM[k] = [(ax, ay), (bx, by)]
        continue
    n_bent += 1
    if abs(dx) >= abs(dy):
        t = abs(dx) - abs(dy)
        bend = (ax + math.copysign(t, dx), ay) if t >= 0 else (bx - math.copysign(-t, dx), by)
    else:
        t = abs(dy) - abs(dx)
        bend = (ax, ay + math.copysign(t, dy)) if t >= 0 else (bx, by - math.copysign(-t, dy))
    GEOM[k] = [(ax, ay), bend, (bx, by)]

def offset_pts(pts, off):
    # offset an octilinear path perpendicularly (clamped miter at bend)
    if off == 0: return pts
    if len(pts) == 2:
        (x0, y0), (x1, y1) = pts
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        return [(x0 + nx * off, y0 + ny * off), (x1 + nx * off, y1 + ny * off)]
    (x0, y0), (x1, y1), (x2, y2) = pts
    def seg_norm(ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1
        return (-dy / L, dx / L)
    n1 = seg_norm(x0, y0, x1, y1)
    n2 = seg_norm(x1, y1, x2, y2)
    a = (x0 + n1[0] * off, y0 + n1[1] * off)
    c = (x2 + n2[0] * off, y2 + n2[1] * off)
    mx, my = n1[0] + n2[0], n1[1] + n2[1]
    L2 = max(mx * mx + my * my, 0.6)   # clamp near-reversal miters
    b = (x1 + mx * 2 * off / L2, y1 + my * 2 * off / L2)
    return [a, b, c]

GAP = 4.4
STROKE = 3.0
edge_route_off = {}   # (edge, rid) -> offset
for k, rset in edges.items():
    rs = sorted(rset, key=lambda s: (0, int(s[1:])) if s.startswith('Y') else (1, s))
    for i, rid in enumerate(rs):
        edge_route_off[(k, rid)] = (i - (len(rs) - 1) / 2) * GAP

# ---------- svg assembly ----------
xs = [q[0] for q in p.values()]; ys = [q[1] for q in p.values()]
MINX, MAXX = min(xs) - 90, max(xs) + 90
MINY, MAXY = min(ys) - 90, max(ys) + 90
W, H = MAXX - MINX, MAXY - MINY
def X(x): return x - MINX
def Y(y): return y - MINY

svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" font-family="\'Microsoft YaHei\',\'PingFang SC\',sans-serif">')
svg.append(f'<rect width="{W:.0f}" height="{H:.0f}" fill="#0d1226"/>')

# stylized Yangtze: horizontal band (schematic convention)
river = [(118.55, 31.93), (118.62, 31.99), (118.68, 32.035), (118.73, 32.07),
         (118.76, 32.095), (118.80, 32.125), (118.845, 32.165), (118.89, 32.205), (118.94, 32.245)]
ry0 = sum(compress(proj(a, b))[1] for a, b in river) / len(river)
svg.append(f'<line x1="0" y1="{Y(ry0):.1f}" x2="{W:.0f}" y2="{Y(ry0):.1f}" stroke="#1c3557" stroke-width="26" opacity="0.9"/>')
svg.append(f'<text x="{W-150:.0f}" y="{Y(ry0)+5:.1f}" fill="#3e6ea5" font-size="15" letter-spacing="6">长 江</text>')

# edges
svg.append('<g id="edges">')
for k, rset in edges.items():
    pts = GEOM[k]
    rs = sorted(rset, key=lambda s: (0, int(s[1:])) if s.startswith('Y') else (1, s))
    for rid in rs:
        off = edge_route_off[(k, rid)]
        op = offset_pts(pts, off)
        d = ' '.join(f'{X(x):.1f},{Y(y):.1f}' for x, y in op)
        dash = ' stroke-dasharray="7 4"' if rid in ('SS1', 'SS2') else ''
        svg.append(f'<polyline class="edge r-{rid}" points="{d}" fill="none" stroke="{COLORS[rid]}" stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round"{dash}/>')
svg.append('</g>')

# stop markers
def local_dir(n, rid):
    vx = vy = 0.0
    for m in adj[n]:
        k = frozenset((n, m))
        if rid in edges.get(k, ()):
            pts = GEOM[k]
            q = pts[1] if pts[0] == p[n] else pts[-2]
            dx, dy = q[0] - p[n][0], q[1] - p[n][1]
            L = math.hypot(dx, dy) or 1
            vx += dx / L; vy += dy / L
    L = math.hypot(vx, vy)
    return (vx / L, vy / L) if L > 1e-6 else (1.0, 0.0)

def stop_offset(n, rid):
    offs = [edge_route_off[(frozenset((n, m)), rid)] for m in adj[n]
            if (frozenset((n, m)), rid) in edge_route_off]
    return sum(offs) / len(offs) if offs else 0.0

oneway_by_route = {r['id']: set(r['oneway']) for r in routes}
stop_routes = defaultdict(set)
for r in routes:
    for d in r['directions']:
        for s in d['stops']:
            stop_routes[s['name']].add(r['id'])

svg.append('<g id="stops">')
marker_info = {}   # name -> (cx, cy, is_interchange)
for n, s in stops.items():
    x, y = p[n]
    rids = sorted(stop_routes[n], key=lambda t: (0, int(t[1:])) if t.startswith('Y') else (1, t))
    inter = len(rids) >= 2
    ow_any = any(n in oneway_by_route[rid] for rid in rids)
    title = n + '｜' + '、'.join(rid + ('路' if rid.startswith('Y') else '') for rid in rids)
    if ow_any:
        owr = [rid for rid in rids if n in oneway_by_route[rid]]
        title += '｜单向站(仅部分方向/线路停靠: ' + '、'.join(owr) + ')'
    svg.append(f'<g class="stop{" interchange" if inter else ""}"><title>{title}</title>')
    if inter:
        rad = 5.0 + max(0, (len(rids) - 2)) * 1.1
        svg.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{rad:.1f}" fill="#f5f7ff" stroke="#0d1226" stroke-width="2"/>')
        marker_info[n] = (x, y, True, rad)
    else:
        rid = rids[0]
        dx, dy = local_dir(n, rid)
        off = stop_offset(n, rid)
        cx, cy = x - dy * off, y + dx * off
        ow = n in oneway_by_route[rid]
        col = COLORS[rid]
        if ow:
            r = 3.6
            d = f'M {X(cx):.1f} {Y(cy)-r:.1f} L {X(cx)+r:.1f} {Y(cy):.1f} L {X(cx):.1f} {Y(cy)+r:.1f} L {X(cx)-r:.1f} {Y(cy):.1f} Z'
            svg.append(f'<path class="mk r-{rid}" d="{d}" fill="#0d1226" stroke="{col}" stroke-width="1.8"/>')
        else:
            svg.append(f'<circle class="mk r-{rid}" cx="{X(cx):.1f}" cy="{Y(cy):.1f}" r="3.1" fill="#0d1226" stroke="{col}" stroke-width="1.8"/>')
        marker_info[n] = (cx, cy, False, 3.6)
    svg.append('</g>')
svg.append('</g>')

# ---------- labels ----------
def text_w(t, fs):
    return sum(fs if ord(c) > 0x2e7f else fs * 0.56 for c in t)

placed = []
def collide(rx, ry, rw, rh):
    for (ax, ay, aw, ah) in placed:
        if rx < ax + aw and ax < rx + rw and ry < ay + rh and ay < ry + rh:
            return True
    return False

def place_label(n, t, fs, bold, cls):
    x, y, inter, rad = marker_info[n]
    dx, dy = local_dir(n, sorted(stop_routes[n], key=lambda z: (0, int(z[1:])) if z.startswith('Y') else (1, z))[0])
    horiz = abs(dx) >= abs(dy)
    w = text_w(t, fs) + 4; h = fs + 3
    gap = rad + 4
    cands = []
    if horiz:
        cands = [(x, y - gap, 'middle', -h, 0), (x, y + gap, 'middle', 0, 0),
                 (x + gap, y, 'start', -h / 2, 0), (x - gap, y, 'end', -h / 2, 0)]
    else:
        cands = [(x + gap, y, 'start', -h / 2, 0), (x - gap, y, 'end', -h / 2, 0),
                 (x, y - gap, 'middle', -h, 0), (x, y + gap, 'middle', 0, 0)]
    cands += [(x + gap, y - gap, 'start', -h, 0), (x - gap, y - gap, 'end', -h, 0),
              (x + gap, y + gap, 'start', 0, 0), (x - gap, y + gap, 'end', 0, 0)]
    for extra in (10, 20, 32):
        g = gap + extra
        cands += [(x, y - g, 'middle', -h, extra), (x, y + g, 'middle', 0, extra),
                  (x + g, y, 'start', -h / 2, extra), (x - g, y, 'end', -h / 2, extra),
                  (x + g, y - g, 'start', -h, extra), (x - g, y - g, 'end', -h, extra),
                  (x + g, y + g, 'start', 0, extra), (x - g, y + g, 'end', 0, extra)]
    for cx, cy, anchor, oy, extra in cands:
        rx = cx - w / 2 if anchor == 'middle' else (cx if anchor == 'start' else cx - w)
        ry = cy + oy
        if not collide(rx, ry, w, h):
            placed.append((rx, ry, w, h))
            fw = ' font-weight="bold"' if bold else ''
            leader = ''
            if extra:
                ly = cy + oy + h / 2
                leader = (f'<line x1="{X(x):.1f}" y1="{Y(y):.1f}" x2="{X(cx):.1f}" y2="{Y(ly):.1f}" '
                          f'stroke="#5a6a9a" stroke-width="0.7"/>')
            return (f'<g class="lbl {cls}">{leader}<text x="{X(cx):.1f}" y="{Y(cy + oy + fs - 1):.1f}" '
                    f'text-anchor="{anchor}" font-size="{fs}"{fw} fill="#e8ecf8" '
                    f'stroke="#0d1226" stroke-width="3" paint-order="stroke">{t}</text></g>')
    if cls == 'major':
        cx, cy, anchor, oy, _ = cands[0]
        placed.append((cx - w / 2, cy + oy, w, h))
        return (f'<g class="lbl {cls}"><text x="{X(cx):.1f}" y="{Y(cy + oy + fs - 1):.1f}" '
                f'text-anchor="{anchor}" font-size="{fs}" font-weight="bold" fill="#e8ecf8" '
                f'stroke="#0d1226" stroke-width="3" paint-order="stroke">{t}</text></g>')
    return None

svg.append('<g id="labels">')
n_minor = n_skip = n_skip_major = 0
label_items = []
for n in stops:
    inter = marker_info[n][2]
    term = n in terminals
    if term:
        label_items.append((0, n, 11.5, True, 'major'))
    elif inter:
        label_items.append((1, n, 10, False, 'major'))
    else:
        label_items.append((2, n, 9, False, 'minor'))
label_items.sort(key=lambda t: t[0])
for _, n, fs, bold, cls in label_items:
    out = place_label(n, n, fs, bold, cls)
    if out:
        svg.append(out)
        if cls == 'minor': n_minor += 1
    else:
        n_skip += 1
        if cls == 'major': n_skip_major += 1
svg.append('</g>')

# north arrow + scale note
svg.append(f'<g transform="translate({W-60:.0f},52) rotate({math.degrees(ROT):.0f})"><path d="M0,-22 L8,10 L0,3 L-8,10 Z" fill="#e8ecf8"/><text y="28" text-anchor="middle" fill="#e8ecf8" font-size="13">N</text></g>')
svg.append('</svg>')
svg_str = '\n'.join(svg)
open(os.path.join(ROOT, 'schematic.svg'), 'w', encoding='utf-8').write(svg_str)

# ---------- HTML wrapper ----------
def fmt_time(d):
    s, e = d.get('start') or '?', d.get('end') or '?'
    return f'{s}–{e}' if s != e else f'{s} 发车'

legend = []
for r in routes:
    rid = r['id']
    d0 = r['directions'][0]
    if rid == 'Y33':
        ends = '鼎泰家园西门 环线（内圈/外圈）'
    elif rid == 'SS1':
        ends = '泰冯路地铁站西 ⇌ 方州广场东'
    elif rid == 'SS2':
        ends = '迈皋桥东 ⇌ 月苑南路'
    else:
        ends = f"{d0['from']} ⇌ {d0['to']}"
    times = ' / '.join(dict.fromkeys(fmt_time(d) for d in r['directions']))
    ow = f'<span class="ow">含{len(r["oneway"])}个单向站</span>' if r['oneway'] else ''
    badge = '守时' if rid.startswith('SS') else ''
    legend.append(
        f'<div class="chip" data-route="{rid}"><span class="sw" style="background:{COLORS[rid]}'
        f'{";border:1px dashed #0d1226" if rid.startswith("SS") else ""}"></span>'
        f'<span class="rt">{r["label"]}{badge}</span><span class="ends">{ends}</span>'
        f'<span class="tm">{times}</span>{ow}</div>')

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>南京夜间公交运营示意图</title>
<style>
 body{{margin:0;background:#070b1a;color:#e8ecf8;font-family:'Microsoft YaHei','PingFang SC',sans-serif}}
 header{{padding:18px 26px 10px}}
 h1{{margin:0;font-size:24px;letter-spacing:2px}}
 .sub{{color:#8fa0c9;font-size:13px;margin-top:6px;line-height:1.7}}
 .wrap{{display:flex;gap:0;align-items:flex-start}}
 .mapbox{{flex:1;overflow:auto;height:calc(100vh - 118px);border-top:1px solid #1c2547}}
 .mapbox svg{{display:block;width:100%;height:auto;min-width:900px}}
 aside{{width:390px;max-height:calc(100vh - 118px);overflow:auto;padding:12px 16px;border-left:1px solid #1c2547;border-top:1px solid #1c2547;box-sizing:border-box}}
 .ctl{{margin:4px 0 12px;font-size:13px;color:#aab8e0}}
 .ctl label{{margin-right:16px;cursor:pointer}}
 .chip{{display:grid;grid-template-columns:14px 86px 1fr;gap:2px 8px;padding:7px 8px;border-radius:8px;cursor:pointer;align-items:center;font-size:12px}}
 .chip:hover{{background:#141c3d}}
 .sw{{width:14px;height:14px;border-radius:4px;grid-row:span 2}}
 .rt{{font-weight:bold;font-size:13px}}
 .ends{{color:#c6d2f2}}
 .tm{{grid-column:2/4;color:#7f8db8;font-size:11px}}
 .ow{{grid-column:2/4;color:#f0a35e;font-size:11px}}
 .note{{font-size:12px;color:#8fa0c9;line-height:1.8;margin-top:14px;border-top:1px solid #1c2547;padding-top:10px}}
 .lg{{display:inline-block;width:10px;height:10px;border-radius:50%;background:#f5f7ff;border:2px solid #0d1226;vertical-align:-1px}}
 .dm{{display:inline-block;width:9px;height:9px;background:#0d1226;border:1.8px solid #f0a35e;transform:rotate(45deg);vertical-align:-1px}}
 svg .minor{{display:none}}
 body.show-all svg .minor{{display:block}}
 svg.focus .edge,svg.focus .mk{{opacity:.10}}
 svg.focus .edge.hot,svg.focus .mk.hot{{opacity:1}}
</style></head><body>
<header>
 <h1>南京夜间公交运营示意图 <span style="font-size:13px;color:#8fa0c9;font-weight:normal">Nanjing Night Bus Network · 22:00 后</span></h1>
 <div class="sub">37条线路 · 74个方向 · 941个站点 · 214个换乘站 ｜ 数据截至 2026-11-20（百度地图2026-07数据，经南京公交集团公告核对）<br>
 抽象示意图：线条仅横平竖直与45°，站距均匀化，不还原实际走向与比例（精确走向见真实地图版）。换乘站以白色圆点表示，<span class="dm"></span> 菱形为单向站（仅一个方向停靠）。悬停站点可看详情，悬停右侧线路可高亮。</div>
</header>
<div class="wrap">
 <div class="mapbox" id="mapbox">{svg_str}</div>
 <aside>
  <div class="ctl"><label><input type="checkbox" id="all"> 显示全部站点名</label><label><input type="checkbox" id="river" checked> 长江</label></div>
  {''.join(legend)}
  <div class="note">
   <b>图例</b><br><span class="lg"></span> 换乘站（≥2条线路）&nbsp;&nbsp;○ 普通站（双向）&nbsp;&nbsp;<span class="dm"></span> 单向站<br>
   虚线 = 地铁末班守时公交：<b>守时1号线</b> 泰冯路地铁站西 23:10 发车（接驳S8号线末班），方州广场东 21:40 回送；<b>守时2号线</b> 月苑南路 23:20–00:20 / 迈皋桥东 23:40–00:40，10分钟一班（接驳1号线末班）。<br><br>
   Y6、Y9、Y14、Y15、Y18、Y19、Y20 已撤销（2024-11/2025-01优化），原走廊由 Y2/Y3/Y4/Y5/Y13/Y17/Y24 等覆盖。Y30、Y41 为傍晚/晚间线，末班早于午夜。Y4、Y17、Y21 部分班次区间运行（见各方向起讫站）。<br><br>
   数据来源：百度地图网页版公交接口；南京公交集团公告（tongzhi/6956、7264、7295、8566）；现代快报、搜狐新闻关于守时公交的报道。
  </div>
 </aside>
</div>
<script>
 const svg=document.querySelector('svg');
 document.getElementById('all').onchange=e=>document.body.classList.toggle('show-all',e.target.checked);
 document.getElementById('river').onchange=e=>{{svg.querySelector('line').style.display=e.target.checked?'':'none';svg.querySelector('text').style.display=e.target.checked?'':'none';}};
 document.querySelectorAll('.chip').forEach(ch=>{{
   const rid=ch.dataset.route;
   const els=svg.querySelectorAll('.r-'+rid);
   ch.onmouseenter=()=>{{svg.classList.add('focus');els.forEach(el=>el.classList.add('hot'));}};
   ch.onmouseleave=()=>{{svg.classList.remove('focus');els.forEach(el=>el.classList.remove('hot'));}};
 }});
</script>
</body></html>'''
open(os.path.join(ROOT, 'schematic.html'), 'w', encoding='utf-8').write(html)
print(f'SVG {W:.0f}x{H:.0f}, edges={len(edges)}, bent={n_bent}, minor labels shown={n_minor}, skipped={n_skip} (major skipped={n_skip_major})')