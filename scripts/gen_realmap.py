# -*- coding: utf-8 -*-
"""Generate Leaflet real-map view of the Nanjing night bus network."""
import json, math, os
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), '..')
net = json.load(open(os.path.join(ROOT, 'data', 'network.json'), encoding='utf-8'))

def hsl(h, s, l):
    return f'hsl({h:.0f},{s:.0f}%,{l:.0f}%)'
COLORS = {}
ys = sorted([r['id'] for r in net['routes'] if r['id'].startswith('Y')], key=lambda s: int(s[1:]))
for i, rid in enumerate(ys):
    COLORS[rid] = hsl((i * 137.508 + 15) % 360, 72 if i % 3 else 62, 60 if i % 2 else 52)
COLORS['SS1'] = '#f8fafc'
COLORS['SS2'] = '#fbbf24'
subs = sorted(r['id'] for r in net['routes'] if not r['id'].startswith(('Y', 'SS')))
for i, rid in enumerate(subs):
    COLORS[rid] = hsl((i * 47 + 190) % 360, 70, 58)

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
        L = math.hypot(dx, dy)
        dmax, idx = -1, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            if L < 1e-12:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * (px - ax) - dx * (py - ay)) / L
            if d > dmax: dmax, idx = d, k
        if dmax > eps:
            keep[idx] = True
            stack.append((i, idx)); stack.append((idx, j))
    return [p for p, k in zip(pts, keep) if k]

coverage = defaultdict(lambda: defaultdict(list))
for r in net['routes']:
    for di, d in enumerate(r['directions']):
        for s in d['stops']:
            coverage[s['name']][r['id']].append(di)

routes_js = []
for r in net['routes']:
    dirs = []
    for d in r['directions']:
        paths = [rdp([[round(la, 6), round(lo, 6)] for lo, la in p], 4e-5) for p in d['paths']]
        dirs.append({'name': d['name'], 'from': d['from'], 'to': d['to'],
                     'start': d['start'], 'end': d['end'],
                     'stops': [s['name'] for s in d['stops']], 'paths': paths})
    routes_js.append({'id': r['id'], 'label': r['label'], 'color': COLORS[r['id']],
                      'oneway': r['oneway'], 'dirs': dirs})

stops_js = {}
for n, s in net['stops'].items():
    stops_js[n] = {'lat': round(s['lat'], 6), 'lng': round(s['lng'], 6),
                   'routes': {rid: dis for rid, dis in coverage[n].items()}}

payload = {'asof': net['asof'], 'routes': routes_js, 'stops': stops_js}
js = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
sched = json.load(open(os.path.join(ROOT, 'data', 'schedule.json'), encoding='utf-8'))
sched_js = json.dumps(sched, ensure_ascii=False, separators=(',', ':'))
# Metro adjacency substrate (station->lines) + day-type operating-hour envelope.
# Built from 南京地铁 official/本地宝 timetables; see README 停站时间模型.
metro = json.load(open(os.path.join(ROOT, 'data', 'metro.json'), encoding='utf-8'))
metro_stations_js = json.dumps(metro['stations'], ensure_ascii=False, separators=(',', ':'))
metro_hours_js = json.dumps(metro['hours'], ensure_ascii=False, separators=(',', ':'))

# ---- speedometer gauge (static SVG, needle driven by JS) ----
GEARS = [1/6, 1/3, 0.5, 1, 5, 15, 20, 30, 60, 120]
GLABS = ['10s', '20s', '30s', '1', '5', '15', '20', '30', '60', '120']
GCX, GCY, GR = 66, 70, 56
GA0, GA1 = 195.0, -15.0
GSPAN = GA0 - GA1
GLEN = GR * math.radians(GSPAN)
GDEF = 3  # default gear: 1 min/s

def gp(a, rr):
    return (GCX + rr * math.cos(math.radians(a)), GCY - rr * math.sin(math.radians(a)))

def gauge_svg():
    x0, y0 = gp(GA0, GR); x1, y1 = gp(GA1, GR)
    arc = f'M {x0:.1f} {y0:.1f} A {GR} {GR} 0 1 1 {x1:.1f} {y1:.1f}'
    f0 = GDEF / (len(GEARS) - 1)
    p = [f'<svg id="gsvg" viewBox="0 0 132 92" width="132" height="92" role="slider" tabindex="0" '
         f'aria-label="模拟速度" aria-valuemin="0" aria-valuemax="120" aria-valuenow="1">',
         '<defs><linearGradient id="ggrad" x1="0" y1="1" x2="1" y2="0">'
         '<stop offset="0" stop-color="#5b8def"/><stop offset=".5" stop-color="#fbbf24"/>'
         '<stop offset="1" stop-color="#f87171"/></linearGradient></defs>',
         f'<path d="{arc}" fill="none" stroke="#232c52" stroke-width="6" stroke-linecap="round"/>',
         f'<path id="gfill" d="{arc}" fill="none" stroke="url(#ggrad)" stroke-width="6" '
         f'stroke-linecap="round" stroke-dasharray="{GLEN*f0:.1f} {GLEN:.1f}"/>']
    for i, g in enumerate(GLABS):
        a = GA0 - GSPAN * i / (len(GEARS) - 1)
        tx0, ty0 = gp(a, GR - 4); tx1, ty1 = gp(a, GR - 11)
        lx, ly = gp(a, GR - 21)
        p.append(f'<line x1="{tx0:.1f}" y1="{ty0:.1f}" x2="{tx1:.1f}" y2="{ty1:.1f}" stroke="#4a5688" stroke-width="1.6"/>')
        p.append(f'<text class="glab" data-i="{i}" x="{lx:.1f}" y="{ly+2.6:.1f}" text-anchor="middle" '
                 f'font-size="7.5" fill="#8fa0c9">{g}</text>')
        if i < len(GEARS) - 1:
            am = a - GSPAN / (len(GEARS) - 1) / 2
            mx0, my0 = gp(am, GR - 4); mx1, my1 = gp(am, GR - 8)
            p.append(f'<line x1="{mx0:.1f}" y1="{my0:.1f}" x2="{mx1:.1f}" y2="{my1:.1f}" stroke="#333d6b" stroke-width="1"/>')
    a0 = GA0 - GSPAN * f0
    p.append(f'<g id="gneedle" transform="rotate({90-a0:.1f} {GCX} {GCY})">'
             f'<line x1="{GCX}" y1="{GCY}" x2="{GCX}" y2="{GCY-44}" stroke="#ffd97a" stroke-width="2.6" stroke-linecap="round"/>'
             f'<line x1="{GCX}" y1="{GCY}" x2="{GCX}" y2="{GCY+8}" stroke="#ffd97a" stroke-width="2.6" stroke-linecap="round" opacity=".45"/></g>')
    p.append(f'<circle cx="{GCX}" cy="{GCY}" r="4.6" fill="#0d1226" stroke="#ffd97a" stroke-width="2"/>')
    p.append('</svg>')
    return ''.join(p)

nroutes = len(net['routes'])
nstops = len(net['stops'])
has_sub = any(r['id'].startswith(('LS', 'GC')) for r in net['routes'])
sub_note = ('溧水区（溧水Y1/Y2/Y5路夜间）与高淳区（801/802路、803路高职园夜间专线）的夜间/晚间线路已一并纳入，'
            '其服务时段早于主城夜班（约18:00–23:00）。' if has_sub else '')
sub_note += '时段飞站：双龙街（0:00–5:00，Y21/Y27往江宁方向走高架通过不停车），全网共1处，模拟按各班车经过时刻自动判定。'

html = '''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0d1226">
<title>南京夜间公交 · 真实地图</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
 html,body{margin:0;height:100%;overflow:hidden;background:#0d1226;color:#e8ecf8;font-family:'Microsoft YaHei','PingFang SC',sans-serif}
 @supports(height:100dvh){html,body{height:100dvh}}
 #map{position:absolute;top:0;bottom:0;left:0;right:390px}
 aside{position:absolute;top:0;bottom:0;right:0;width:390px;overflow:auto;background:#0d1226;border-left:1px solid #1c2547;padding:14px 16px;box-sizing:border-box}
 #sidebackdrop{position:fixed;inset:0;background:rgba(4,6,14,.55);z-index:1250}
 #sidebackdrop[hidden]{display:none}
 #sideclose{display:none;position:absolute;top:10px;right:12px;background:#1c2547;color:#c6d2f2;border:1px solid #2c3a6e;border-radius:6px;padding:4px 11px;cursor:pointer;font-size:14px;line-height:1;z-index:3}
 aside::-webkit-scrollbar{width:9px}
 aside::-webkit-scrollbar-track{background:#0d1226}
 aside::-webkit-scrollbar-thumb{background:#2c3a6e;border-radius:5px}
 aside::-webkit-scrollbar-thumb:hover{background:#3d4f8f}
 h1{font-size:19px;margin:0 0 4px;letter-spacing:1px}
 .sub{color:#8fa0c9;font-size:12px;line-height:1.7;margin-bottom:10px}
 .ctl{font-size:12.5px;color:#aab8e0;margin:6px 0}
 .ctl label{margin-right:14px;cursor:pointer;display:inline-block}
 .btns button{background:#1c2547;color:#c6d2f2;border:1px solid #2c3a6e;border-radius:6px;padding:3px 10px;margin:0 6px 8px 0;cursor:pointer;font-size:12px}
 .btns button:hover{background:#2c3a6e}
 .chip{display:grid;grid-template-columns:16px 14px 84px 1fr;gap:2px 7px;padding:6px 6px;border-radius:8px;align-items:center;font-size:12px;cursor:pointer}
 .chip:hover{background:#141c3d}
 .chip input{cursor:pointer}
 .sw{width:14px;height:14px;border-radius:4px;grid-row:span 2}
 .rt{font-weight:bold;font-size:12.5px}
 .ends{color:#c6d2f2}
 .tm{grid-column:3/5;color:#7f8db8;font-size:11px}
 .ow{grid-column:3/5;color:#f0a35e;font-size:11px}
 .leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#141c3d;color:#e8ecf8}
 .leaflet-popup-content{font-size:12.5px;line-height:1.7}
 .leaflet-container{background:#0d1226}
 .ptitle{font-weight:bold;font-size:14px;margin-bottom:4px}
 .prow b{color:#fff}
 .pwait{display:block;color:#7f8db8;font-size:11px;margin:-2px 0 3px 0}
 .pwait b{color:#ffd97a;font-weight:normal}
 .pskip{color:#c98ab8;font-size:11px}
 .skiptag{color:#ff7ab8;font-size:11px;border:1px solid #5b2a4a;border-radius:4px;padding:0 4px;margin-left:4px}
 .owtag{color:#fbbf24}
 a{color:#7fb3ff}
 #map.darktiles .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.92) contrast(.92) saturate(.55)}
 #simbar{position:absolute;left:0;right:390px;bottom:0;z-index:1000;display:flex;align-items:center;gap:9px;padding:8px 12px;background:rgba(10,14,32,.93);border-top:1px solid #2c3a6e;font-size:12.5px}
 #simbar button{background:#1c2547;color:#c6d2f2;border:1px solid #2c3a6e;border-radius:6px;padding:4px 12px;cursor:pointer;font-size:12.5px;white-space:nowrap}
 #simbar button:hover{background:#2c3a6e}
 #play{min-width:74px;color:#ffd97a}
 #speedbtn{color:#ffd97a;font-family:Consolas,'Courier New',monospace}
 #speedbtn.on{background:#3d3212;border-color:#8a6d3b}
 #modebtn{color:#9fd0ff;font-family:Consolas,'Courier New',monospace}
 #modebtn.real{background:#12303d;border-color:#3b7d8a;color:#7fe3ff}
 #daybtn{color:#c9b6ff;font-family:Consolas,'Courier New',monospace}
 #daybtn.on{background:#2a2347;border-color:#6b5b95;color:#e3d6ff}
 #daybtn:disabled{opacity:.38;cursor:default}
 #fsbtn{color:#c6d2f2}
 #fsbtn.on{background:#12303d;border-color:#3b7d8a;color:#7fe3ff}
 #sidetoggle{display:none}
 /* ---- floating speed dial panel ---- */
 #speedpanel{position:absolute;left:12px;bottom:62px;z-index:1200;background:rgba(13,18,38,.97);border:1px solid #2c3a6e;border-radius:12px;padding:12px 16px 10px;box-shadow:0 12px 40px rgba(0,0,0,.55),0 0 24px rgba(91,141,239,.12)}
 #speedpanel[hidden]{display:none}
 #speedpanel .sphead{display:flex;align-items:center;gap:10px;margin-bottom:2px}
 #speedpanel .sptitle{font-size:12px;color:#8fa0c9;letter-spacing:1px}
 #speedval{color:#ffd97a;font-size:15px;font-weight:bold;font-family:Consolas,'Courier New',monospace;margin-left:auto;text-shadow:0 0 10px rgba(255,217,122,.4)}
 #gsvg{width:150px;height:105px;cursor:grab;touch-action:none;outline:none;display:block;margin:0 auto}
 #gsvg:active{cursor:grabbing}
 #gsvg:focus-visible{filter:drop-shadow(0 0 4px #5b8def)}
 #speedpanel .sphint{font-size:10.5px;color:#7f8db8;text-align:center;line-height:1.6;margin-top:2px}
 #clock{font-family:Consolas,'Courier New',monospace;font-size:17px;font-weight:bold;color:#ffd97a;min-width:92px;text-align:center}
 #scrub{flex:1;accent-color:#fbbf24;cursor:pointer;min-width:80px}
 #tinput{width:62px;background:#141c3d;border:1px solid #2c3a6e;color:#e8ecf8;border-radius:5px;padding:4px 6px;font-size:12.5px}
 #bcount{color:#8fa0c9;white-space:nowrap;min-width:74px;text-align:right}
 .busicon{background:transparent;border:none}
 .buslab{position:absolute;left:19px;top:3px;font-size:10px;line-height:14px;padding:0 3px;border-radius:3px;background:rgba(13,18,38,.88);color:#e8ecf8;border:1px solid #888;white-space:nowrap}
 /* ---- railway-style departure board (docked, draggable, resizable) ---- */
 #board{position:fixed;top:12px;right:402px;width:440px;height:min(60vh,540px);z-index:1100;
  background:#04060e;border:1px solid #3a2f14;border-radius:12px;display:flex;flex-direction:column;overflow:hidden;
  box-shadow:0 20px 70px rgba(0,0,0,.7),0 0 0 1px rgba(255,180,84,.12),0 0 60px rgba(255,180,84,.07);
  font-family:Consolas,'Courier New',monospace}
 #board::after{content:'';position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(255,255,255,.022) 0 1px,transparent 1px 3px)}
 #board.mini{height:auto!important}
 #board.mini .bstats,#board.mini .bfilter,#board.mini .bwrap,#board.mini .bfoot,#board.mini .bgrip{display:none}
 .bhead{display:flex;align-items:center;gap:10px;padding:10px 14px;background:linear-gradient(180deg,#1a1408,#0c0a04);border-bottom:1px solid #3a2f14;cursor:grab;user-select:none;touch-action:none}
 .bhead:active{cursor:grabbing}
 .btitle{color:#ffb454;font-size:14px;font-weight:bold;letter-spacing:2px;text-shadow:0 0 12px rgba(255,180,84,.5)}
 .btitle span{display:block;font-size:8px;color:#8a6d3b;letter-spacing:2.5px;font-weight:normal}
 .bclock{margin-left:auto;color:#ffd97a;font-size:21px;font-weight:bold;text-shadow:0 0 14px rgba(255,217,122,.6)}
 .bhead button{background:#171208;color:#c9a25e;border:1px solid #3a2f14;border-radius:6px;padding:3px 9px;cursor:pointer;font-size:12px;font-family:inherit}
 .bhead button:hover{background:#241c0c;color:#ffd97a}
 .bstats{padding:5px 14px;color:#c9a25e;font-size:11.5px;border-bottom:1px solid #241c0c}
 .bstats b{color:#ffd97a;font-size:12.5px}
 .bfilter{display:flex;gap:10px;padding:7px 14px;align-items:center}
 #bq{flex:1;min-width:60px;background:#0c0a04;border:1px solid #3a2f14;color:#ffd97a;border-radius:6px;padding:4px 9px;font-family:inherit;font-size:12px}
 #bq::placeholder{color:#6b5527}
 .bfilter label{color:#8a6d3b;font-size:11px;white-space:nowrap;cursor:pointer}
 .bwrap{overflow:auto;padding:0 8px 8px;flex:1}
 .bwrap::-webkit-scrollbar{width:9px}
 .bwrap::-webkit-scrollbar-track{background:#0c0a04}
 .bwrap::-webkit-scrollbar-thumb{background:#3a2f14;border-radius:5px}
 .bwrap::-webkit-scrollbar-thumb:hover{background:#5a4a1e}
 #board table{width:100%;border-collapse:collapse;font-size:12px}
 #board th{position:sticky;top:0;background:#0c0a04;color:#8a6d3b;text-align:left;padding:6px 7px;border-bottom:1px solid #3a2f14;font-size:10.5px;letter-spacing:1px;z-index:1}
 #board td{height:26px;padding:0 7px;border-bottom:1px solid #171208;color:#e8c98a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 #board td.bseg{min-width:110px;max-width:180px}
 #board td.bdir{max-width:150px}
 #board tbody tr:hover td{background:#171208;cursor:pointer}
 .bled{font-weight:bold;text-shadow:0 0 8px currentColor}
 .bseg{color:#ffd97a}
 .bstat{padding:1px 6px;border-radius:4px;font-size:10.5px}
 .brun{color:#7dd87d;border:1px solid #2c4a2c}
 .bstop{color:#ffb454;border:1px solid #4a3a14}
 .bskip{color:#ff7ab8;border:1px solid #5b2a4a}
 .bempty{text-align:center;color:#8a6d3b;padding:26px}
 .bfoot{padding:6px 14px;color:#6b5527;font-size:10px;border-top:1px solid #241c0c}
 .bgrip{position:absolute;right:0;bottom:0;width:20px;height:20px;cursor:nwse-resize;touch-action:none;z-index:2}
 .bgrip::before{content:'';position:absolute;right:4px;bottom:4px;width:9px;height:9px;border-right:2px solid #8a6d3b;border-bottom:2px solid #8a6d3b}
 /* ---- metro flash line-map (top banner on bus click) ---- */
 #flash{position:fixed;top:10px;left:50%;transform:translateX(-50%);width:min(940px,94vw);z-index:1500;
  background:linear-gradient(180deg,#0b1126,#070b1a);border:1px solid #5b8def;border-radius:14px;overflow:hidden;
  box-shadow:0 14px 50px rgba(0,0,0,.6)}
 #flash[hidden]{display:none}
 .fhead{display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid #1c2547;flex-wrap:wrap}
 .fline{font-weight:bold;font-size:14px;color:#0b1020;padding:2px 12px;border-radius:6px;letter-spacing:1px}
 .fdir{color:#c6d2f2;font-size:12.5px}
 .fdep{color:#7f8db8;font-size:11.5px}
 .fclock{margin-left:auto;font-family:Consolas,'Courier New',monospace;font-size:22px;font-weight:bold;color:#ffd97a;text-shadow:0 0 14px rgba(255,217,122,.55)}
 .ffollow{color:#8fa0c9;font-size:11px;cursor:pointer;white-space:nowrap}
 #fclose{background:#141c3d;color:#c6d2f2;border:1px solid #2c3a6e;border-radius:6px;padding:3px 10px;cursor:pointer;font-size:12px}
 #fclose:hover{background:#2c3a6e}
 .finfo{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:8px 16px;font-size:11.5px;color:#7f8db8;border-bottom:1px solid #1c2547}
 .finfo b{display:block;color:#e8ecf8;font-size:13px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 #fstat b{color:#7dd87d}
 #fcrowd b{font-size:12px}
 .fcbar{height:6px;border-radius:3px;background:#1c2547;overflow:hidden;margin-top:4px}
 .fcbar i{display:block;height:100%;width:0;border-radius:3px;background:#34d399;transition:width .2s,background .2s}
 .fcio{display:block;font-size:10px;color:#7f8db8;margin-top:3px;white-space:nowrap}
 #godbtn{color:#f0abfc}
 #godbtn.on{background:#3b1d47;border-color:#a855f7;color:#f5d0fe}
 #godbtn:disabled{opacity:.38;cursor:default}
 #godpanel{position:fixed;left:14px;bottom:74px;width:300px;max-height:70vh;overflow:auto;z-index:1200;background:#0e1430f2;border:1px solid #a855f7;border-radius:12px;box-shadow:0 14px 50px rgba(0,0,0,.6);backdrop-filter:blur(6px);font-size:12px;color:#c7d0ee}
 .ghead{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;border-bottom:1px solid #2a2347;position:sticky;top:0;background:#0e1430}
 .gtitle{font-weight:700;color:#f5d0fe}
 .ghead button{background:none;border:none;color:#8b96c4;cursor:pointer;font-size:14px}
 .gbody{padding:8px 12px 12px}
 .gsec{margin-bottom:12px}
 .glabel{font-weight:600;color:#e3d6ff;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center}
 .gpresets{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
 .gpresets button{flex:1;min-width:80px;background:#1c1740;border:1px solid #4c3a75;color:#e3d6ff;border-radius:7px;padding:6px 4px;cursor:pointer;font-size:11px}
 .gpresets button:hover{background:#2a2347}
 .gdepquick{display:flex;gap:5px}
 .gdepquick button{background:#1c1740;border:1px solid #4c3a75;color:#e3d6ff;border-radius:6px;padding:3px 9px;cursor:pointer;font-size:11px}
 .gdepquick button:hover{background:#2a2347}
 .grow{display:flex;align-items:center;gap:8px;margin:5px 0}
 .grow label{flex:0 0 78px;color:#8b96c4}
 .grow input[type=range]{flex:1}
 .grow input[type=text],.grow select{flex:1;background:#0b1020;border:1px solid #2a2347;color:#e8ecf8;border-radius:6px;padding:4px 6px;font-size:12px}
 .grow b{color:#f5d0fe;min-width:38px;text-align:right}
 .gplace{width:100%;background:#3b1d47;border:1px solid #a855f7;color:#f5d0fe;border-radius:8px;padding:8px;cursor:pointer;font-size:12px;margin-top:4px}
 .gplace.armed{background:#a855f7;color:#1a0b2e;font-weight:700}
 .ghint{font-size:10.5px;color:#7f8db8;margin-top:6px;line-height:1.5}
 .gmini{background:none;border:1px solid #4c3a75;color:#c9b6ff;border-radius:5px;padding:1px 7px;cursor:pointer;font-size:10px}
 .gevents{display:flex;flex-direction:column;gap:5px}
 .gempty{color:#5a648c;font-size:11px}
 .gev{display:flex;justify-content:space-between;align-items:center;background:#161b3a;border:1px solid #2a2347;border-radius:7px;padding:5px 8px}
 .gev button{background:none;border:none;color:#f87171;cursor:pointer}
 #toast{position:fixed;left:50%;bottom:96px;transform:translateX(-50%);z-index:1500;background:#1c1740f5;border:1px solid #a855f7;color:#f5d0fe;padding:10px 18px;border-radius:10px;box-shadow:0 10px 40px rgba(0,0,0,.5);font-size:13px;max-width:80vw;text-align:center}
 #achpage{position:fixed;inset:0;z-index:1400;background:rgba(4,7,18,.72);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px)}
 #achpage[hidden]{display:none}
 .acard{width:min(680px,92vw);max-height:84vh;overflow:auto;background:#0e1430;border:1px solid #a855f7;border-radius:14px;box-shadow:0 20px 70px rgba(0,0,0,.7)}
 .ahead{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #2a2347;position:sticky;top:0;background:#0e1430}
 .atitle{font-weight:700;font-size:16px;color:#f5d0fe}
 #achcount{color:#8b96c4;font-size:12px;flex:1}
 .ahead button{background:none;border:none;color:#8b96c4;cursor:pointer;font-size:14px}
 .abody{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;padding:14px 16px}
 .ach{border:1px solid #2a2347;border-radius:10px;padding:10px 12px;background:#12183a;opacity:.55}
 .ach.got{opacity:1;border-color:#a855f7;background:#1c1740}
 .ach .ai{font-size:22px}
 .ach .an{font-weight:700;color:#e8ecf8;margin:3px 0;font-size:13px}
 .ach.got .an{color:#f5d0fe}
 .ach .ad{font-size:11px;color:#8b96c4;line-height:1.45}
 .ach .at{font-size:10px;color:#34d399;margin-top:4px}
 .afoot{padding:10px 16px;border-top:1px solid #2a2347;color:#5a648c;font-size:11px}
 @media(max-width:760px){#godpanel{left:8px;right:8px;width:auto;bottom:120px;max-height:55vh}}
 .fstrip{overflow-x:auto;overflow-y:hidden;height:118px;position:relative}
 .fstrip::-webkit-scrollbar{height:9px}
 .fstrip::-webkit-scrollbar-track{background:#070b1a}
 .fstrip::-webkit-scrollbar-thumb{background:#2c3a6e;border-radius:5px}
 .fstrip::-webkit-scrollbar-thumb:hover{background:#3d4f8f}
 .finner{position:relative;height:100%}
 .ftrack{position:absolute;left:0;right:0;top:57px;height:4px;background:#232c52;border-radius:2px}
 .flit{position:absolute;left:0;top:57px;height:4px;border-radius:2px;box-shadow:0 0 10px currentColor}
 .fseg{position:absolute;top:55px;height:8px;border-radius:4px;animation:fblink 1s ease-in-out infinite;box-shadow:0 0 14px currentColor}
 .fdot{position:absolute;top:54px;width:10px;height:10px;border-radius:50%;background:#0b1126;border:2px solid #3a4470;box-sizing:border-box}
 .fdot.done{border-color:currentColor}
 .fdot.cur{animation:fpulse 1s ease-in-out infinite}
 .fdot.next{animation:fblink 1s ease-in-out infinite;border-color:#ffd97a}
 .fdot.skip{border-style:dashed;border-color:#ff7ab8}
 .fdot.skip.done{border-color:#ff7ab8;background:#0b1126!important}
 .ftag{font-style:normal;color:#ff7ab8;border:1px solid #5b2a4a;border-radius:3px;padding:0 2px;font-size:9px}
 .flab{position:absolute;width:74px;text-align:center;font-size:10px;color:#8fa0c9;line-height:1.3}
 .flab.above{top:12px}
 .flab.below{top:76px}
 .flab.end{color:#e8ecf8;font-weight:bold}
 .fbus{position:absolute;top:47px;width:24px;height:24px;margin-left:-12px}
 .fbuscore{position:absolute;inset:6px;border-radius:50%;box-shadow:0 0 12px currentColor,0 0 4px #fff inset}
 .fbusring{position:absolute;inset:0;border-radius:50%;border:2px solid currentColor;animation:fring 1.4s ease-out infinite}
 @keyframes fblink{0%,100%{opacity:1}50%{opacity:.2}}
 @keyframes fpulse{0%,100%{transform:scale(1)}50%{transform:scale(1.5)}}
 @keyframes fring{0%{transform:scale(.6);opacity:1}100%{transform:scale(1.7);opacity:0}}
 /* ---- searchable help modal (summoned by top-left button) ---- */
 .helpbtn{background:#1c2547;color:#c6d2f2;border:1px solid #2c3a6e;border-radius:6px;padding:5px 11px;cursor:pointer;font-size:12.5px;font-family:inherit;box-shadow:0 1px 5px rgba(0,0,0,.4)}
 .helpbtn:hover{background:#2c3a6e;color:#ffd97a}
 #help{position:fixed;inset:0;z-index:2000;background:rgba(4,6,14,.74);display:flex;align-items:center;justify-content:center;padding:24px}
 #help[hidden]{display:none}
 .hcard{width:min(760px,100%);max-height:86vh;display:flex;flex-direction:column;background:#0d1226;border:1px solid #2c3a6e;border-radius:14px;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.7),0 0 40px rgba(91,141,239,.12)}
 .hhead{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #1c2547;flex-wrap:wrap}
 .htitle{font-size:15px;font-weight:bold;color:#e8ecf8;letter-spacing:1px;white-space:nowrap}
 #helpq{flex:1;min-width:160px;background:#0c0a04;border:1px solid #3a2f14;color:#ffd97a;border-radius:6px;padding:6px 11px;font-family:inherit;font-size:12.5px}
 #helpq::placeholder{color:#6b5527}
 #helpcount{color:#8a6d3b;font-size:11px;white-space:nowrap}
 #helpclose{background:#141c3d;color:#c6d2f2;border:1px solid #2c3a6e;border-radius:6px;padding:5px 11px;cursor:pointer;font-size:12px}
 #helpclose:hover{background:#2c3a6e}
 .hbody{overflow:auto;padding:6px 18px 14px;flex:1}
 .hbody::-webkit-scrollbar{width:9px}
 .hbody::-webkit-scrollbar-track{background:#0d1226}
 .hbody::-webkit-scrollbar-thumb{background:#2c3a6e;border-radius:5px}
 .hsec{padding:11px 0;border-bottom:1px solid #161d3a}
 .hsec[hidden]{display:none}
 .hsec h3{margin:0 0 5px;font-size:13.5px;color:#ffd97a;letter-spacing:.5px}
 .hsec p{margin:0 0 6px;font-size:12.5px;color:#aab8e0;line-height:1.85}
 .hsec p:last-child{margin-bottom:0}
 .hsec b{color:#e8ecf8}
 .hbody mark{background:#ffd97a;color:#0b1020;border-radius:2px;padding:0 1px}
 .hempty{padding:26px;text-align:center;color:#8a6d3b;font-size:12.5px}
 .hempty[hidden]{display:none}
 @media (max-width:1100px){
  aside{width:330px} #map{right:330px} #simbar{right:330px}
  #board{right:342px;width:380px}
 }
 @media (max-width:760px){
  #map{right:0}
  #simbar{right:0;flex-wrap:wrap;gap:6px;padding:6px 8px;padding-bottom:calc(6px + env(safe-area-inset-bottom))}
  #simbar button{padding:6px 10px;font-size:12px;min-height:34px}
  #scrub{flex:1 1 100%;order:50;min-width:0;height:28px}
  #clock{font-size:15px;min-width:auto}
  aside{width:min(340px,88vw);transform:translateX(105%);transition:transform .25s;z-index:1300;box-shadow:-8px 0 30px rgba(0,0,0,.5);padding-top:16px;-webkit-overflow-scrolling:touch}
  body.showside aside{transform:none}
  #sidetoggle{display:inline-block}
  #sideclose{display:block}
  #bcount{min-width:0;font-size:11px}
  #board{right:8px;top:8px;width:min(400px,calc(100vw - 16px));height:min(46vh,400px)}
  #board.mini{width:auto;max-width:calc(100vw - 16px)}
  .bdir{display:none}
  .bclock{font-size:17px}
  .leaflet-control-scale{display:none}
  .finfo{grid-template-columns:repeat(2,1fr)}
  #speedpanel{left:8px;bottom:112px}
  .helpbtn{padding:7px 11px}
 }
 @media (max-width:600px){
  #tinput,#jump{display:none}
  #simbar{gap:5px}
  #simbar button{padding:6px 8px;font-size:11.5px;min-height:36px}
  #play{min-width:46px}
  #speedpanel{bottom:120px;left:6px}
  #flash{width:98vw;top:6px}
  .fhead{padding:8px 10px;gap:8px}
  .fclock{font-size:18px}
  #help{padding:8px}
  .hcard{max-height:92vh;border-radius:10px}
  .hhead{gap:6px;padding:10px 12px}
  .hbody{padding:4px 12px 12px}
 }
</style></head><body>
<div id="map"></div>
<div id="simbar">
 <button id="sidetoggle">☰ 线路</button>
 <button id="play">▶ 播放</button>
 <button id="speedbtn" title="呼出速度调节盘">⏱ 1分/秒 ▴</button>
 <button id="modebtn" title="当前：理论模式（图定时刻表）">🌙 理论模式</button>
 <button id="daybtn" title="现实模式客流日型（仅影响现实模式停站需求）" disabled>🗓 工作日</button>
 <button id="godbtn" title="金手指模式：注入活动客流、加车调度（基于现实模式）" disabled>🪄 金手指</button>
 <button id="fsbtn" title="全屏显示">⛶ 全屏</button>
 <span id="clock">--:--</span>
 <input id="scrub" type="range" title="拖动进度条">
 <input id="tinput" type="text" placeholder="23:30" title="输入时刻，00:00–11:59 视为次日">
 <button id="jump">跳转</button>
 <span id="bcount">运行 0 辆</span>
</div>
<div id="speedpanel" hidden>
 <div class="sphead"><span class="sptitle">模拟速度调节盘</span><span id="speedval">1分/秒</span></div>
 __GAUGE__
 <div class="sphint">拖动指针 / 点击刻度换挡 · ←→ 键微调<br>低速档 10s/20s/30s 为「秒/秒」，其余为「分/秒」</div>
</div>
<div id="board">
 <div class="bhead" id="bhead">
  <div class="btitle">南京夜间公交 · 运行大屏<span>NANJING NIGHT BUS · LIVE</span></div>
  <div class="bclock" id="bclock">--:--</div>
  <button id="bmin" title="最小化 / 还原">—</button>
 </div>
 <div class="bstats">正在运行 <b id="brun">0</b> 辆 · 已发出 <b id="bdep">0</b> 班 · 待发车 <b id="bwait">0</b> 班</div>
 <div class="bfilter">
  <input id="bq" type="text" placeholder="筛选：线路 / 站点 / 方向…">
  <label><input type="checkbox" id="bonly" checked> 仅地图已选线路</label>
 </div>
 <div class="bwrap">
  <table>
   <thead><tr><th>线路</th><th class="bdir">方向</th><th>发车</th><th>当前区间</th><th>下一站</th><th>预计到达</th><th>状态</th></tr></thead>
   <tbody id="bbody"></tbody>
  </table>
 </div>
 <div class="bfoot">按线路编号排序（主城→溧水→高淳）· 点击行定位车辆并打开闪灯图 · 拖动标题栏移动 / 右下角缩放</div>
 <div class="bgrip" id="bgrip" title="拖动调整大小"></div>
</div>
<div id="flash" hidden>
 <div class="fhead">
  <span class="fline" id="fline">—</span>
  <span class="fdir" id="fdir">—</span>
  <span class="fdep" id="fdep">—</span>
  <span class="fclock" id="fclock">--:--</span>
  <label class="ffollow"><input type="checkbox" id="ffollow" checked> 跟随车辆</label>
  <button id="fclose">✕ 关闭</button>
 </div>
 <div class="finfo">
  <div>当前站 / 区间<b id="fcur">—</b></div>
  <div>下一站<b id="fnext">—</b></div>
  <div>预计到达<b id="feta">—</b></div>
  <div id="fstat">状态<b id="fstatv">—</b></div>
  <div id="fcrowd">拥挤度<b id="fcrowdv">—</b><div class="fcbar"><i id="fcfill"></i></div><span class="fcio" id="fcio"></span></div>
 </div>
 <div class="fstrip" id="fstrip"><div class="finner" id="finner"></div></div>
</div>
<div id="godpanel" hidden>
 <div class="ghead"><span class="gtitle">🪄 金手指调度台</span><button id="godclose">✕</button></div>
 <div class="gbody">
  <div class="gsec">
   <div class="glabel">注入活动客流（散场接驳）</div>
   <div class="gpresets">
    <button data-preset="concert">🎤 奥体演唱会</button>
    <button data-preset="sports">🏟 体育赛事</button>
    <button data-preset="qingao">🎤 青奥演唱会</button>
    <button data-preset="festival">🎵 咪豆音乐节</button>
    <button data-preset="lantern">🏮 秦淮灯会</button>
    <button data-preset="laomendong">🏮 老门东灯会</button>
   </div>
   <div class="grow"><label>人数 <b id="gcrowdv">3000</b></label><input id="gcrowd" type="range" min="200" max="20000" step="100" value="3000"></div>
   <div class="grow"><label>散场时刻</label><input id="gtime" type="text" value="22:30" placeholder="22:30"></div>
   <div class="grow"><label>持续(分)</label><input id="gdur" type="range" min="20" max="120" step="5" value="60"><b id="gdurv">60</b></div>
   <div class="grow"><label>扩散半径(m)</label><input id="gradius" type="range" min="300" max="2500" step="100" value="1200"><b id="gradiusv">1200</b></div>
   <button id="gplace" class="gplace">📍 点击地图放置活动</button>
   <div class="ghint" id="ghint">选预设或调参后点「放置」，再点地图任意位置；客流自最近站点向周边数站扩散，并按线路分担（含换乘外溢）。</div>
  </div>
  <div class="gsec">
   <div class="glabel">活动列表 <button id="gclear" class="gmini">清空</button></div>
   <div id="gevents" class="gevents"><span class="gempty">暂无活动</span></div>
  </div>
  <div class="gsec">
   <div class="glabel">加车调度</div>
   <div class="grow"><label>线路</label><select id="groute"></select></div>
   <div class="grow"><label>方向</label><select id="gdir"></select></div>
   <div class="grow"><label>加车站点</label><select id="gstop"></select></div>
   <div class="grow"><label>发车时刻</label><input id="gdeptime" type="text" value="22:45" placeholder="22:45"></div>
   <div class="grow"><label>快捷发车</label><span class="gdepquick"><button data-off="0">现在</button><button data-off="10">+10分</button><button data-off="20">+20分</button></span></div>
   <button id="gadd" class="gplace">🚌 从该站加开一班车</button>
   <div class="ghint">金手指模式从拥挤站直接加车；活动散场致拥挤时自动加车纾解，并把本栏跳到受影响线路、发车时刻默认设为当前模拟时间（不晚于现在）。「现在/+10分/+20分」按当前时间配置即时或延时发车。现实模式自动调度则从始发站加车并飞站至拥挤站。</div>
  </div>
 </div>
</div>
<div id="toast" hidden></div>
<div id="achpage" hidden>
 <div class="acard">
  <div class="ahead"><span class="atitle">🏆 成就</span><span id="achcount"></span><button id="achclose">✕ 关闭</button></div>
  <div class="abody" id="achbody"></div>
  <div class="afoot">成就自动保存在本浏览器 · 入口隐蔽，线索见「📖 说明 → 隐藏成就彩蛋」</div>
 </div>
</div>
<div id="sidebackdrop" hidden></div>
<aside id="side">
 <button id="sideclose" title="关闭线路栏">✕</button>
 <h1>南京夜间公交 · 真实地图</h1>
 <div class="sub">__NROUTES__条线路 · __NSTOPS__站 · 截至2026-11-20<br>
 走向与站点来自百度地图（2026-07更新）。高德底图使用GCJ02坐标（JS实时转换），OSM底图使用WGS84。</div>
 <div class="ctl">
  <label><input type="checkbox" id="bothdir" checked> 显示对向走向</label>
  <label><input type="checkbox" id="owmark" checked> 单向站标记</label>
  <label><input type="checkbox" id="stopmark" checked> 站点</label>
  <label><input type="checkbox" id="darkfilter" checked> 底图压暗</label>
 </div>
 <div class="btns"><button id="all">全选</button><button id="none">全不选</button><button id="ss">仅守时公交</button><button id="fit">全图范围</button></div>
 <div id="chips"></div>
</aside>
<div id="help" hidden>
 <div class="hcard">
  <div class="hhead">
   <span class="htitle">📖 使用说明</span>
   <input id="helpq" type="text" placeholder="搜索说明内容（如：速度 / 飞站 / 大屏 / 始发站）…">
   <span id="helpcount"></span>
   <button id="helpclose">✕ 关闭</button>
  </div>
  <div class="hbody" id="helpbody">
   <div class="hsec">
    <h3>读图基础</h3>
    <p>全图站点圆点大小统一，并随地图放大一并增大；白色圆点 = 普通站点（多线换乘站带深色边），<span style="color:#fbbf24">琥珀色圆点</span> = 单向站（仅某一方向停靠，弹窗注明方向）；虚线 = 地铁末班守时公交。</p>
    <p>点击站点弹出详情，查看各线路在此的停靠方向与下一班到站；点击侧栏线路名可缩放到该线走向。左上角图层控件可切换高德（GCJ02，国内快）/ OSM德国 / OSM标准（WGS84）底图。放大地图时站点圆点会随之增大，便于看清。</p>
   </div>
   <div class="hsec">
    <h3>线路筛选与显示</h3>
    <p>侧栏顶部按钮：<b>全选</b> / <b>全不选</b> / <b>仅守时公交</b> / <b>全图范围</b>（缩放到全网）。每条线路前的复选框控制是否绘制，点击线路色块或名称缩放到该线。</p>
    <p>显示开关：<b>显示对向走向</b>（同时画出反方向）、<b>单向站标记</b>（单向站圆点填琥珀色）、<b>站点</b>（圆点）、<b>底图压暗</b>（夜间滤镜，突出线路）。</p>
   </div>
   <div class="hsec">
    <h3>运行模拟播放</h3>
    <p>底部播放条从首班 <b>__SIMSTART__</b> 模拟至收车后 <b>__SIMEND__</b>（理论末班约 07:23 到达；现实模式叠加延误后最晚约 08:07 收车，窗口留有余量防止播放停住）。点击 <b>▶ 播放 / ⏸ 暂停</b> 开始或停止；到达窗口末端自动暂停。</p>
    <p>拖动<b>进度条</b>任意定位；在时刻框输入时间后点 <b>跳转</b> 或按回车精确跳转，<b>00:00–11:59 视为次日</b>。右侧「运行 N 辆」实时显示在途车辆数。</p>
   </div>
   <div class="hsec">
    <h3>速度调节盘</h3>
    <p>点击 <b>⏱ 速度按钮</b> 呼出指针式调节盘：拖动指针或点击刻度换挡，呼出后按 <b>← →</b>（或 ↑ ↓）微调。再次点击速度按钮或按 Esc 收起。</p>
    <p>档位：低速 <b>10 / 20 / 30 秒每秒</b>（真实节奏），以及 <b>1 / 5 / 15 / 20 / 30 / 60 / 120 分每秒</b>（快进）。默认 1 分/秒。</p>
   </div>
   <div class="hsec">
    <h3>站点弹窗</h3>
    <p>站点弹窗<b>随模拟实时刷新</b>，按线路给出下一班到站时刻、<b>等待时间</b>（即将到站 / X 分钟）与<b>距本站里程</b>；该方向的<b>始发站</b>直接标注「始发站」，待发车车辆标注「距起点 X km（待发车）」。</p>
    <p>弹窗打开时拖动地图不会被强制拉回；已收车方向显示「已收车」，时段飞站方向显示「飞站通过不停靠」。</p>
   </div>
   <div class="hsec">
    <h3>运行大屏</h3>
    <p>常驻右上角的火车站大屏式列表，按线路编号排序（主城 → 溧水 → 高淳），列出全部在途车辆的发车时刻、当前区间、下一站、预计到达与状态。<b>每行行高固定</b>，车辆增减时表格不会上下抖动。</p>
    <p>拖动<b>标题栏</b>移动位置，拖动<b>右下角</b>缩放，点 <b>—</b> 最小化 / 还原。筛选框支持按线路 / 站点 / 方向过滤；「仅地图已选线路」联动侧栏勾选。<b>点击任意行</b>定位该车辆并打开闪灯图。</p>
   </div>
   <div class="hsec">
    <h3>闪灯图（车辆运行图）</h3>
    <p><b>点击地图上的小车或大屏行</b>，在页面顶端打开地铁闪灯图式运行图：站点圆点依次点亮，当前站与下一站闪烁，显示当前区间、下一站、预计到达与状态。</p>
    <p>勾选 <b>跟随车辆</b> 后画面平滑跟随车标移动（车标与进度同步，无晃动）；到终点后车标停在末站圆点上不再前冲。点 <b>✕ 关闭</b> 或按 Esc 关闭。</p>
   </div>
   <div class="hsec">
    <h3>时段飞站规则</h3>
    <p><b>双龙街</b>站 <b>00:00–05:00</b> 飞站通过不停靠（走高架），仅影响 Y21 / Y27 的<b>出城方向</b>，进城方向正常停靠。飞站班次省略该站停站时间，后续站点到站时刻相应提前。</p>
    <p>站点弹窗、运行大屏（飞站状态）与闪灯图（虚线圆点 + 「飞」标签）均会标注飞站。</p>
   </div>
   <div class="hsec">
    <h3>数据与旅速模型</h3>
    <p>发车时刻采用百度地图公布的<b>固定发车时刻表</b>（守时2号线按 10 分钟间隔；溧水 Y1/Y2、高淳 801/802 仅公布首末班时段，按约 30 分钟间隔估算）。每班均为<b>场站独立发出</b>——夜间公交到终点即收车，不原地折返。</p>
    <p>各站到站时刻按<b>分段限速旅速模型估算</b>：常规道路限速 40km/h，折减红绿灯/转弯后旅速约 <b>__VR__ km/h</b>（百度百余段行程时间校准）；江北大道地面辅路约 <b>__VA__ km/h</b>（守时1号线公布全程 70 分钟校准）；高速/过江通道等无站区段限速 70km/h，按 <b>__VF__ km/h</b> 计；每站停 <b>__DWELL__</b> 分钟、急弯每次加 <b>__TP__</b> 分钟。</p>
   </div>
   <div class="hsec">
    <h3>理论模式 / 现实模式</h3>
    <p>底部 <b>🌙 理论模式</b> 按钮可一键切换两种模拟。<b>理论模式</b>严格按图定时刻表与旅速模型运行，结果可复现，用于对照；<b>现实模式</b>为每班车叠加<b>确定性随机扰动</b>（按班次固定随机种子，拖动进度条往返结果完全一致）。</p>
    <p>现实模式包含五类效应：① 在推断的信号灯路口随机遇到<b>绿灯/闪黄通过</b>或<b>红灯等待</b>；② <b>停站时长随机</b>——夜间客流稀少时多数站仅"稍减速完成开关门"即走，景区/饭店/换乘大站停留更久（并按<b>客流日型</b>与<b>地铁接驳</b>微调，详见下节）；③ <b>发车随机延误</b> 0–3 分钟（绝不早发）；④ 跨凌晨/晚高峰（约 06:00 后、17–19 时）的班次随机遭遇<b>堵车降速</b>；⑤ 每次停站/等灯后的<b>起步加减速</b>使速度不均匀。</p>
    <p>信号灯位置由线路几何<b>推断</b>（城市段每约 0.55 km 或明显转弯处设一处，高速/过江等无站区段不设灯），并非逐一实地调研；如需精确可接入真实信号数据。现实模式下大屏/弹窗/闪灯图显示的时刻均为该车次的实际（含延误）时刻。</p>
   </div>
   <div class="hsec">
    <h3>客流日型与地铁接驳</h3>
    <p>现实模式下底部 <b>🗓 工作日 / 周末 / 节假日</b> 按钮可切换客流日型（理论模式下禁用）。日型影响两方面：① <b>线路客流</b>——夫子庙/新街口/奥体等夜生活·景区线（Y1/Y2/Y7）周末、节假日（灯会/国庆）客流显著放大，工作日偏空；铁路·地铁接驳线（Y3/Y8/Y13/Y16/Y23/Y34/SS1/SS2）平日稀疏，春运/五一返程高峰放大（注：春节假期本身反而近空）；其余普通线节假日略降。② <b>地铁运营时刻</b>——工作日城区末班约 23:30、周五周六延时约 00:15、节假日约 00:45（南京南可达 01:00），首班约 05:45。</p>
    <p>对<b>地铁沿线/可近距离换乘的站点</b>（按站名匹配南京地铁 263 站，约 250 个公交站命中），停站需求随时段微调：<b>地铁运营中</b>二者争抢客流，公交停站偏短（×0.7）；<b>末班地铁刚结束</b>后约 90 分钟内，末班地铁客流涌入接驳换乘，停站显著加长（峰值约 1.8×，随时间衰减）；深夜地铁停运且接驳潮退去后回归常态。日型越晚收班，接驳高峰越后移。S 线（宁天/宁溧/宁高/机场等）收班更早，接驳潮相应提前。</p>
    <p>站名匹配为<b>近似</b>（与信号灯几何推断同理），并非逐一实地测距；如需精确可接入真实站点坐标/OD 客流。模型预留了客流模拟接口 <code>setFlowModel(fn)</code>：注入 <code>fn(站名, 线路, 到站时刻, 日型)→负载</code> 即可用实测客流覆盖参数化需求。</p>
   </div>
   <div class="hsec">
    <h3>客流模拟与拥挤度</h3>
    <p>现实模式下，闪灯图新增<b>拥挤度</b>栏：按车型额定载客量计算实时车载人数与占比，分三档——<span style="color:#34d399">≤30% 舒适</span> / <span style="color:#fbbf24">30–70% 一般</span> / <span style="color:#f87171">70–100% 拥挤</span>，并显示当前站<b>上/下车人数</b>。理论模式仅显示额定载客提示。</p>
    <p>额定载客量按车型估算：主城干线 10.5–12m 纯电动公交约 <b>90 人</b>（25–46 座+站立），溧水/高淳郊区线约 <b>70 人</b>，守时1号线双节车约 <b>150 人</b>（逐线精确配车未公开，故为车型级估计）。逐站上下车人数与<b>停站时长同源</b>：开关门即走的短停对应 0–1 人，普通停站数人，枢纽/夜生活大站长停对应多人，并与实测 POV 节奏一致。车载人数逐站累计（上车−下车），到终点清空。</p>
    <p>预留<b>客流流线（OD）接口</b> <code>setODModel(fn)</code>：注入 <code>fn(线路,方向,班次,上车站i,下车站j)→人数</code> 即可用真实 OD 替换概率下车模型（本轮不计算，留待后续严肃研究）。另有 <code>setFlowModel(fn)</code> 覆盖逐站需求负载。</p>
   </div>
   <div class="hsec">
    <h3>金手指模式（活动客流与加车调度）</h3>
    <p>切到现实模式后，底部 <b>🪄 金手指</b> 按钮可用，打开调度台。可模拟<b>演唱会/体育赛事/音乐节/灯会</b>等深夜散场、地铁已停运、夜班公交接驳的场景：选预设（奥体演唱会/体育赛事/青奥演唱会/咪豆音乐节/秦淮灯会·白鹭洲/老门东灯会）一键注入，或调参（人数/散场时刻/持续/扩散半径）后点「放置」再<b>点击地图任意位置</b>自由注入。</p>
    <p>注入的客流以<b>最近站点为中心向周边数站扩散</b>（距离衰减权重），并按各站途经线路分担——因此<b>换乘客流会外溢到其他线路</b>，影响整个线网。客流按散场曲线（前 15 分钟爬坡、随后衰减）守恒地分配到窗口内经过的各班车上。</p>
    <p><b>加车调度</b>：金手指模式可在线路/方向/站点下拉框选择<b>拥挤站直接加开一班车</b>，发车时刻默认设为当前模拟时间（不晚于现在），「现在/+10分/+20分」快捷按钮可配置即时或延时发车；活动散场致某站车载≥75% 时<b>自动从拥挤站加车纾解</b>，并把下方加车栏<b>自动跳到受影响线路</b>。现实模式<b>自动调度</b>则在某班车拥挤度≥90% 时，从<b>始发站加车并飞站</b>直达拥挤站。加车会分担注入客流、缓解拥挤——可在闪灯图对比加车前后占比。活动列表可单独移除或清空。</p>
   </div>
   <div class="hsec">
    <h3>换乘规划（乘客视角）</h3>
    <p>本页是<b>宏观俯瞰</b>全城；另有一张独立页面 <a href="planner.html" target="_blank" rel="noopener" style="color:#ffd97a">🧭 换乘规划（planner.html）→</a>，回到<b>一名乘客</b>的视角：给定出发站、目的站与出发时刻，给出具体换乘方案并<b>回放完整运转</b>。它复用本页的<b>现实模式</b>引擎（同一套时刻表与逐班次随机扰动），故规划出的到站时刻与本页模拟<b>完全一致</b>。</p>
    <p>规划页可调：最长步行（按直线距离 ÷ 4.5 km/h 估算，默认 15 分）、最长换乘候车（默认 30 分）、最长全程（默认 150 分）、换乘站偏好（<b>最快到达 / 大站枢纽 / 共线首站</b>），以及「<b>赌一把</b>」紧换乘（赌后车趁前车等灯追上，有错过风险）。方案含每段<b>拥挤度</b>、票价（¥2/程）、步行距离与<b>末班车</b>提示；某方向末班已收车时该换乘自动判为不可行。选中后<b>仅高亮所乘线路</b>（其余淡出），乘客标记按 步行→候车→乘车→到达 实时移动，进度条可逐帧拖动。</p>
   </div>
   <div class="hsec">
    <h3>隐藏成就彩蛋</h3>
    <p>本站藏有一个仿 Steam 的<b>成就页</b>，记录你的探索（首次打开、切现实模式、节假日人潮、金手指上手、奥体演唱会、挤爆啦、加车调度、深夜守望、时光飞逝、跑完全程）。成就自动保存在本浏览器。</p>
    <p>开启方式被刻意<b>藏了起来</b>，这里不再明说。线索有二：其一，入口就在侧栏<b>最上方那行标题</b>上，对它<b>多点几下</b>、手快些；其二，键盘党可留意 <b>Ctrl + Shift</b> 再搭一个字母的三键组合。找到时会有提示弹出。</p>
   </div>
   <div class="hsec">
    <h3>守时公交与线路备注</h3>
    <p>守时1号线：泰冯路地铁站西 23:10 发车接驳 S8 末班（21:40 方州广场东回送）；守时2号线：月苑南路 23:20–00:20 / 迈皋桥东 23:40–00:40 接驳 1 号线末班。</p>
    <p>Y6/Y9/Y14/Y15/Y18/Y19/Y20 已撤销；Y4/Y17/Y21 存在区间车（对向起讫站不同）；Y30/Y41 末班早于午夜。__SUBNOTE__</p>
   </div>
   <div class="hsec">
    <h3>快捷键</h3>
    <p><b>Esc</b>：依次关闭说明弹窗 / 闪灯图 / 速度盘。<b>← →</b>（速度盘打开时）：微调模拟速度。<b>回车</b>（时刻框内）：跳转至输入时刻。</p>
   </div>
   <div class="hsec">
    <h3>移动端 / 竖屏使用</h3>
    <p>窄屏（≤760px）自动切换移动布局：线路侧栏收起，点底部 <b>☰</b> 按钮调出，点<b>遮罩</b>、右上角 <b>✕</b> 或在栏内<b>向右滑动</b>收起；运行大屏默认最小化为标题条（点 <b>□</b> 展开），不再遮挡地图。控制条按钮精简为图标，进度条独占一行便于拖动。</p>
    <p>点 <b>⛶ 全屏</b> 进入沉浸式全屏（安卓 Chrome 等支持；iOS Safari 不支持网页元素全屏，此时按钮自动隐藏，可"添加到主屏幕"后以全屏运行）。切换横竖屏或进出全屏时地图自动重算尺寸；手机初始视野聚焦主城（zoom 12），点侧栏「全图范围」可看全网。</p>
   </div>
  </div>
  <div class="hempty" id="helpempty" hidden>没有匹配的说明，换个关键词试试。</div>
 </div>
</div>
<script>
const DATA = __PAYLOAD__;
const SCHED = __SCHED__;
// WGS84 -> GCJ02 (for Amap basemap)
const GCJ = (() => {
  const A = 6378245.0, EE = 0.00669342162296594323;
  const tlat = (x, y) => {
    let r = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*Math.sqrt(Math.abs(x));
    r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
    r += (20*Math.sin(y*Math.PI) + 40*Math.sin(y/3*Math.PI)) * 2/3;
    r += (160*Math.sin(y/12*Math.PI) + 320*Math.sin(y*Math.PI/30)) * 2/3;
    return r;
  };
  const tlng = (x, y) => {
    let r = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*Math.sqrt(Math.abs(x));
    r += (20*Math.sin(6*x*Math.PI) + 20*Math.sin(2*x*Math.PI)) * 2/3;
    r += (20*Math.sin(x*Math.PI) + 40*Math.sin(x/3*Math.PI)) * 2/3;
    r += (150*Math.sin(x/12*Math.PI) + 300*Math.sin(x/30*Math.PI)) * 2/3;
    return r;
  };
  return (lat, lng) => {
    let dlat = tlat(lng - 105, lat - 35), dlng = tlng(lng - 105, lat - 35);
    const rl = lat / 180 * Math.PI;
    let m = 1 - EE * Math.sin(rl) ** 2;
    const sm = Math.sqrt(m);
    dlat = (dlat * 180) / ((A * (1 - EE)) / (m * sm) * Math.PI);
    dlng = (dlng * 180) / (A / sm * Math.cos(rl) * Math.PI);
    return [lat + dlat, lng + dlng];
  };
})();

// ---------- cached basemap tiles ----------
// First visit fetches tiles normally and stores each blob in IndexedDB; later visits
// serve tiles from the local cache so the basemap paints instantly even on a weak network.
let tileDBP=null;
function tileDB(){
  if(tileDBP) return tileDBP;
  tileDBP=new Promise(res=>{
    try{
      if(typeof indexedDB==='undefined'){ res(null); return; }
      const rq=indexedDB.open('njbus_tiles_v1',1);
      rq.onupgradeneeded=()=>{ try{ rq.result.createObjectStore('t'); }catch(e){} };
      rq.onsuccess=()=>res(rq.result);
      rq.onerror=()=>res(null);
      rq.onblocked=()=>res(null);
    }catch(e){ res(null); }
  });
  return tileDBP;
}
function tileGet(url){ return tileDB().then(db=>new Promise(res=>{
  if(!db){ res(null); return; }
  try{ const rq=db.transaction('t','readonly').objectStore('t').get(url); rq.onsuccess=()=>res(rq.result||null); rq.onerror=()=>res(null); }catch(e){ res(null); }
})); }
function tilePut(url,blob){ tileDB().then(db=>{ if(!db)return; try{ db.transaction('t','readwrite').objectStore('t').put(blob,url); }catch(e){} }); }
const CachedTiles=L.TileLayer.extend({
  createTile(coords,done){
    const tile=document.createElement('img');
    tile.alt='';
    L.DomEvent.on(tile,'load',()=>{ const s=tile.src; done(null,tile); if(s&&s.indexOf('blob:')===0)setTimeout(()=>URL.revokeObjectURL(s),0); });
    L.DomEvent.on(tile,'error',()=>done(new Error('tile error'),tile));
    const url=this.getTileUrl(coords);
    tileGet(url).then(hit=>{
      if(hit){ tile.src=URL.createObjectURL(hit); return; }
      fetch(url,{mode:'cors'}).then(r=>{ if(!r.ok)throw new Error('http '+r.status); return r.blob(); })
        .then(b=>{ tilePut(url,b); tile.src=URL.createObjectURL(b); })
        .catch(()=>{ tile.crossOrigin=''; tile.src=url; });
    });
    return tile;
  }
});
function cachedTiles(url,opts){ return new CachedTiles(url,opts); }
const map = L.map('map', {preferCanvas: true, zoomSnap: 0.5}).setView([32.06, 118.79], 11);
const amap = cachedTiles('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
  {attribution: '&copy; 高德地图 AutoNavi', subdomains: '1234', maxZoom: 18, coordMode: 'gcj'});
const osmde = cachedTiles('https://tile.openstreetmap.de/{z}/{x}/{y}.png',
  {attribution: '&copy; OpenStreetMap', maxZoom: 19, coordMode: 'wgs'});
const osm = cachedTiles('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  {attribution: '&copy; OpenStreetMap', maxZoom: 19, coordMode: 'wgs'});
amap.addTo(map);
L.control.layers({'高德（国内快）': amap, 'OSM德国': osmde, 'OSM标准': osm}, null, {position: 'topleft'}).addTo(map);
L.control.scale({imperial: false, position: 'topright'}).addTo(map);
const helpBtn = L.DomUtil.create('button', 'helpbtn');
helpBtn.type = 'button'; helpBtn.textContent = '📖 说明'; helpBtn.title = '查看使用说明（可搜索）';
L.DomEvent.disableClickPropagation(helpBtn);
helpBtn.onclick = openHelp;
map.addControl(new (L.Control.extend({onAdd() { return helpBtn; }}))({position: 'topleft'}));

let MODE = 'gcj';
const pt = (lat, lng) => MODE === 'gcj' ? GCJ(lat, lng) : [lat, lng];
const routeLayers = {}, dirLayers = {};
let stopLayer = L.layerGroup();
// Stops live in a higher pane than routes so re-adding lines (全不选→全选)
// can never paint over the stop dots — canvas draw order alone is add-order dependent.
map.createPane('routesPane'); map.getPane('routesPane').style.zIndex = 400;
map.createPane('stopsPane'); map.getPane('stopsPane').style.zIndex = 450;
const renderer = L.canvas({pane: 'routesPane', padding: 0.4});
const stopRenderer = L.canvas({pane: 'stopsPane', padding: 0.4});
const chipState = {};
const ORDER = {}; DATA.routes.forEach((r, i) => ORDER[r.id] = i);

// ---------- operation simulator ----------
const SIM = {t: SCHED.start, playing: false, speed: 1};
let dirty = true, dragging = false;
const pool = new Map();
const fmtT = m => {
  const h = Math.floor(m / 60) % 24, mm = Math.floor(m % 60);
  return String(h).padStart(2, '0') + ':' + String(mm).padStart(2, '0') + (m >= 1440 ? '⁺¹' : '');
};
const fmtSpeed = v => v < 1 ? Math.round(v * 60) + '秒/秒' : v + '分/秒';
function fmtWait(min) {
  if (min <= 0.5) return '即将到站';
  return Math.max(1, Math.round(min)) + '分钟';
}
// per-departure skip plan: a stop marked "X时至Y时不停靠" is passed without
// dwelling when this departure's pass-through time falls in the window.
const planCache = new Map();
function depPlan(v, key, k) {
  if (!v.skip || !v.skip.length) return null;
  const ck = key + '|' + k;
  let p = planCache.get(ck);
  if (p) return p;
  const dw = SCHED.model.dwell, n = v.stopT.length;
  const st = new Array(n), sk = new Array(n).fill(false);
  let shift = 0;
  for (let i = 0; i < n; i++) {
    st[i] = v.stopT[i] - shift;
    for (const w of v.skip) if (w.i === i) {
      const pass = v.deps[k] + st[i];
      if (pass >= w.from && pass < w.to) { sk[i] = true; shift += dw; }
    }
  }
  p = {st, sk, run: v.run - shift};
  planCache.set(ck, p);
  return p;
}
function posAt(v, el, plan) {
  if (plan && plan.real) return posReal(v, plan, el);
  if (plan) {
    const dw = SCHED.model.dwell;
    let add = 0;
    for (let i = 0; i < plan.st.length; i++) if (plan.sk[i] && plan.st[i] <= el) add += dw;
    el += add;
  }
  const f = v.frames;
  let lo = 0, hi = f.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (f[mid][0] < el) lo = mid + 1; else hi = mid; }
  const i = Math.max(0, lo - 1), a = f[i], b = f[Math.min(i + 1, f.length - 1)];
  const span = b[0] - a[0], u = span > 1e-9 ? Math.max(0, Math.min(1, (el - a[0]) / span)) : 0;
  const da = ((b[3] - a[3] + 540) % 360) - 180;
  return [a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, a[3] + da * u, a[4] + (b[4] - a[4]) * u];
}
// ---------- realistic mode: deterministic per-departure time warp ----------
// Theoretical mode plays the published timetable exactly. Realistic mode layers
// five stochastic effects on top, seeded per departure so scrubbing back and
// forth always shows the same bus in the same place:
//   ① signals    inferred junctions: green / flashing-yellow pass, or red wait
//   ② dwell      per-stop demand = route ridership × time-of-night × node type.
//                Low demand → quick "door-cycle only" stop (Nanjing Y-lines are
//                all-stops, so an empty stop still opens doors ~12-25 s); high
//                demand → long stop. Railway/coach hubs dwell longest; ordinary
//                2-3-route transfer stops get NO bonus, because night Y↔Y transfer
//                demand is ~zero at 30-60 min headways (nobody waits half an hour).
//   ③ depDelay   0..few minutes late departure (never early)
//   ④ congestion peak-hour speed loss for departures crossing ~06:00 / 17-19h
//   ⑤ accel      extra time + eased start after each stop / red light
// The warp RT = [[realMin, theoreticalTau], ...] maps elapsed real minutes (from
// the scheduled departure) to the theoretical timeline that posAt interpolates.
const REAL_CFG = {
  depMax: 3.0,
  quickMin: 0.20, quickMax: 0.42, busyMul: [1.7, 3.4], normMul: [0.55, 1.4],
  lightSpacing: 0.55, turnLightDeg: 18, pRed: 0.34, redMin: 0.3, redMax: 1.6,
  pYellow: 0.12, yellowWait: 0.12, accel: 0.06, accelLong: 0.05,
  congMax: 0.75, fastGapKm: 2.5,
  // dwell demand model (2026-11 recalibration; evidence in README 停站时间模型)
  pQuickBase: 0.42, pQuickSlope: 0.45, pBusyBase: 0.12, pBusyExp: 1.3, busyCap: 0.72,
  hubMul: 1.9, hubBusyMul: 1.35, majorMul: 1.35, majorRoutes: 4, nightMul: 1.55, hospMul: 1.3,
  originMul: 1.2, endMul: 0.8, loadMin: 0.15, loadMax: 3.0,
  // metro interaction at metro-adjacent stops: competition while metro runs,
  // feeder surge right after the last train (see metroW / METRO_HOURS).
  metroComp: 0.70, metroFeederPeak: 1.80,
  todPts: [[0,1.40],[60,1.35],[90,1.10],[150,0.60],[240,0.45],[300,0.90],[360,1.20],[460,1.00],[720,1.00],[1080,1.00],[1260,1.10],[1380,1.30],[1440,1.40]]
};
// ---- metro adjacency + day-type operating hours (data/metro.json) ----
// METRO_STATIONS: base station name -> comma-joined line codes (urban then S).
// METRO_HOURS[dayType]: first = morning resumption (05:45⁺¹), close = last train
// passing central stations (absolute night-service minutes), feeder = surge-window
// length (min), sOffset = S-lines close earlier than the urban envelope.
const METRO_STATIONS = __METRO_STATIONS__;
const METRO_HOURS = __METRO_HOURS__;
// Day-type ridership classes. tourist = 夫子庙/新街口/奥体 nightlife & scenic lines
// (weekend/holiday spikes); feeder = railway/metro接驳 & residential lines (ordinary
// sparse, 春运/五一返程 peaks, but empty during 春节假期本身); local = everything else.
const DAY_CLASS = {
  tourist: ['Y1','Y2','Y7'],
  feeder: ['Y3','Y8','Y13','Y16','Y23','Y34','SS1','SS2']
};
const DAY_CLS = {}; for (const c in DAY_CLASS) for (const r of DAY_CLASS[c]) DAY_CLS[r] = c;
function dayClass(rid){ return DAY_CLS[rid] || 'local'; }
// Multiplier on the ordinary-weekday baseline routeW. Weekday is the corrected
// ordinary period; weekend/holiday boost tourist & feeder demand (evidence in README).
const DAY_MUL = {
  weekday: {tourist:1.00, feeder:1.00, local:1.00},
  weekend: {tourist:1.25, feeder:1.05, local:0.97},
  holiday: {tourist:1.70, feeder:1.35, local:0.90}
};
let DAYTYPE = 'weekday';
function dayMul(rid, dt){ const m = DAY_MUL[dt] || DAY_MUL.weekday; return m[dayClass(rid)]; }
// Per-route ridership weight (1.0 = baseline), representing the ORDINARY weekday.
// Tiers distilled from hard counts (Y16 peak ~28-30 pax at the 21-22h / 05-06h
// commuter edges, ordinary Sept-2020 week), journalist ride-alongs, timetable
// frequency as a demand proxy (Y26/Y28/Y38/Y39 only 3-4 runs a night), and the
// 2024-25 线网整合 that culled the emptiest lines. Routes with no evidence: 1.0.
// Holiday-provenance correction (2026-11): Y13 "年前趟趟爆满" was a 春运 peak and
// SS1 "95% 上座率" was 国庆中秋双节 only — both reduced toward ordinary levels
// (Y13 2.0->1.3, SS1 1.5->1.1); Y1 "拥挤到01:30" was stale 2006 evidence (1.6->1.3);
// Y16 deep-night is lighter than its commuter-edge peak (2.0->1.7). Holiday/weekend
// peaks are now restored by the day-type multiplier (DAY_MUL), not baked in here.
const ROUTE_W = {
  Y16: 1.7, Y13: 1.3, SS2: 1.7,
  Y1: 1.3, Y8: 1.6, Y3: 1.6, SS1: 1.1, Y34: 1.5,
  Y23: 1.3, Y21: 1.3, Y37: 1.3, Y28: 1.3, Y32: 1.3, Y30: 1.2, Y36: 1.2, Y27: 1.15,
  Y4: 0.55, Y7: 0.55, Y11: 0.55, Y22: 0.55, Y29: 0.5, Y31: 0.5, Y33: 0.5, Y35: 0.5,
  Y38: 0.45, Y39: 0.45, Y40: 0.45, Y41: 0.45,
  LSY1: 0.6, LSY2: 0.6, LSY5: 0.6, GC801: 0.6, GC802: 0.55, GC803: 0.5
};
function routeW(rid) { const w = ROUTE_W[rid]; return w == null ? 1.0 : w; }
// Node classification for dwell demand, each gated by whether it actually discharges
// passengers at that hour (evidence in README 停站时间模型):
//   rail    南京站·南广场 —— 普速 K/T/Z 到发，但深夜(约 00:30-05:00)极少车次停靠、
//           客流大幅回落，故按时段开闸；龙蟠路·南京站东/西 距站约 500m、无车站
//           客流，不计入枢纽（仅作普通站）
//   hsr     南京南站 —— 高铁 00:00-06:00 天窗；客流集中在末班地铁/末班车 wave
//           (~22:00-00:30)，深夜近静，05:30 后随首班车回升
//   coach   客运站/长途汽车站 —— 长途客运凌晨 2-5 时停运，故该窗口近静
//   hospital 医院 —— 24h 急诊/陪护，幅度不大且基本平稳，交接班略升
//   nightlife 新街口/夫子庙/大行宫(1912)/老门东/奥体 —— 22:00-01:00 高峰，01:00 后清场
// 南京西站 2012-03-24 起停办客运（今为客车整备所），不再算枢纽。
function nodeType(nm) {
  if (!nm) return null;
  if (/南京南站/.test(nm)) return 'hsr';
  if (/南京站·南广场/.test(nm)) return 'rail';
  if (/客运站|长途汽车站|长途车站|长途东站/.test(nm)) return 'coach';
  if (/医院/.test(nm)) return 'hospital';
  if (/新街口|夫子庙|大行宫|老门东|奥体|湖南路|狮子桥|上海路|1912/.test(nm)) return 'nightlife';
  return null;
}
// Transport hubs (railway + coach) — helper for tests and the busy-branch logic.
function isHub(nm) { const t = nodeType(nm); return t === 'rail' || t === 'hsr' || t === 'coach'; }
function nodeMul(t) {
  if (t === 'rail' || t === 'hsr' || t === 'coach') return REAL_CFG.hubMul;
  if (t === 'nightlife') return REAL_CFG.nightMul;
  if (t === 'hospital') return REAL_CFG.hospMul;
  return 1;
}
// Hour gates: multiplier in [0,1] on the node bonus, by minute-of-day (wrapping).
const NODE_GATE_PTS = {
  rail:     [[0,0.55],[30,0.45],[150,0.30],[240,0.30],[330,0.55],[420,1.00],[1080,1.00],[1320,1.00],[1380,0.90],[1440,0.55]],
  hsr:      [[0,1.00],[30,1.00],[90,0.50],[330,0.22],[360,0.50],[1320,0.90],[1380,1.00],[1440,1.00]],
  coach:    [[0,0.90],[120,0.90],[150,0.18],[300,0.18],[330,0.70],[1320,0.90],[1440,0.90]],
  nightlife:[[0,0.90],[60,0.80],[120,0.30],[300,0.15],[1080,0.20],[1260,0.60],[1350,1.00],[1440,0.90]],
  hospital: [[0,0.90],[360,0.90],[420,1.00],[480,1.00],[1320,0.95],[1380,1.00],[1440,0.90]]
};
function nodeGate(t, m) {
  const P = NODE_GATE_PTS[t]; if (!P) return 1;
  const x = ((m % 1440) + 1440) % 1440;
  if (x <= P[0][0]) return P[0][1];
  for (let i = 1; i < P.length; i++) if (x <= P[i][0]) {
    const a = P[i - 1], b = P[i], u = (x - a[0]) / ((b[0] - a[0]) || 1);
    return a[1] + (b[1] - a[1]) * u;
  }
  return P[P.length - 1][1];
}
// Time-of-night demand multiplier. Ridership does NOT decay monotonically through
// the night: it surges right after the metro stops (~00:00-01:30), collapses to a
// trough ~02:30-04:00, then climbs again into the 05:00-06:00 early-shift /
// train-arrival peak (Y16 is famously full at 05:00).
function todW(m) {
  const t = ((m % 1440) + 1440) % 1440, P = REAL_CFG.todPts;
  if (t <= P[0][0]) return P[0][1];
  for (let i = 1; i < P.length; i++) if (t <= P[i][0]) {
    const a = P[i - 1], b = P[i], u = (t - a[0]) / ((b[0] - a[0]) || 1);
    return a[1] + (b[1] - a[1]) * u;
  }
  return P[P.length - 1][1];
}
let REAL = false;
const realCache = new Map(), lightCache = new Map(), fastCache = new Map();
// ---- metro adjacency (name-matched against METRO_STATIONS, approximate like the
// signal inference) ----
const metroAdjCache = new Map();
const METRO_EXCL = ['龙蟠路·南京站','鼓楼河西','江北国际医院','溧水中专','宁杭高铁溧水','岔路口（溧水）','泮池园'];
function metroAdj(nm){
  if(!nm) return null;
  if(metroAdjCache.has(nm)) return metroAdjCache.get(nm);
  let res=null;
  if(!METRO_EXCL.some(e=>nm.indexOf(e)>=0)){
    let base=null;
    const sm=nm.match(/^S\\d+(.+?)站/);
    if(nm.indexOf('地铁站')>=0){
      const b=nm.split('地铁站')[0];
      if(METRO_STATIONS[b]) base=b;
      else { let bl=0; for(const s in METRO_STATIONS) if(b.length>=s.length && b.slice(-s.length)===s && s.length>bl){ base=s; bl=s.length; } }
    } else if(sm && METRO_STATIONS[sm[1]]) base=sm[1];
    if(!base){
      let bp=1e9,bl=0;
      for(const s in METRO_STATIONS){
        let p=nm.indexOf(s);
        while(p>=0){
          if(p===0||nm[p-1]==='·'){
            const after=nm[p+s.length]||'';
            if(!(s.length===2&&'路街大桥河'.indexOf(after)>=0)){
              if(p<bp||(p===bp&&s.length>bl)){ base=s; bp=p; bl=s.length; }
              break;
            }
          }
          p=nm.indexOf(s,p+1);
        }
      }
    }
    if(base) res={st:base, lines:METRO_STATIONS[base]};
  }
  metroAdjCache.set(nm,res);
  return res;
}
// Metro demand modifier at metro-adjacent stops. While the metro runs it competes
// for passengers (load × metroComp < 1); right after the FIRST serving line closes,
// the last-metro crowd feeds the night bus (surge up to metroFeederPeak, decaying over
// the feeder window); deep night returns to 1. Day-type shifts the close time later
// (weekend/holiday 延时), so the feeder wave moves with it. S-lines close earlier.
function metroW(nm, clk, dt){
  const adj=metroAdj(nm); if(!adj) return 1;
  const H=METRO_HOURS[dt]||METRO_HOURS.weekday;
  let close=Infinity;
  for(const l of adj.lines.split(',')){ const c=H.close+(l[0]==='S'?H.sOffset:0); if(c<close) close=c; }
  if(clk<=close||clk>=H.first) return REAL_CFG.metroComp;
  const since=clk-close;
  if(since>0&&since<=H.feeder) return 1+(REAL_CFG.metroFeederPeak-1)*(1-since/H.feeder);
  return 1;
}
// ---- reserved passenger-flow interface ----
// A future flow model (measured OD / boardings per stop-time-daytype) can be injected
// via setFlowModel(fn): fn(nm, rid, clk, dayType) -> load number, or null to fall back
// to the parametric demand below. This is the hook for real 客流模拟; METRO_STATIONS /
// metroAdj provide the metro-adjacency substrate it would build on.
let FLOW_MODEL=null;
function setFlowModel(fn){ FLOW_MODEL=(typeof fn==='function')?fn:null; realCache.clear(); dirty=true; }
function flowLoad(nm,rid,clk,dt){ try{ return FLOW_MODEL?FLOW_MODEL(nm,rid,clk,dt):null; }catch(e){ return null; } }
// ---- passenger flow (realistic + god mode) ----
// Rated capacity by vehicle class. Nanjing trunk night lines run 10.5-12m battery
// buses rated ~90-104 pax (25-46 seated + standing); suburban 溧水/高淳 use smaller
// ~70-pax buses; SS1 守时公交 uses 双节 (articulated) ~150-pax cars. Per-route exact
// assignment is not public, so these are class estimates (evidence in README).
const CAP_DEFAULT = 90;
const CAP_OVERRIDE = { SS1:150, SS2:90, LSY1:70, LSY2:70, LSY5:70, GC801:70, GC802:70, GC803:70 };
function capacity(rid){ const c=CAP_OVERRIDE[rid]; return c==null?CAP_DEFAULT:c; }
// crowding tiers: <=30% 舒适, 30-70% 一般, 70-100% 拥挤
function crowdTier(r){ return r<=0.30?'舒适':r<=0.70?'一般':'拥挤'; }
function crowdColor(r){ return r<=0.30?'#34d399':r<=0.70?'#fbbf24':'#f87171'; }
// demand load shared with buildReal (same formula; kept separate so the dwell rng
// stream is untouched). i/n give origin/terminal modifiers.
function demandLoad(rid,nm,clk,i,n){
  const nt=nodeType(nm);
  const nRoutes=nm&&DATA.stops[nm]?Object.keys(DATA.stops[nm].routes).length:1;
  const major=!nt&&nRoutes>=REAL_CFG.majorRoutes;
  let load=routeW(rid)*dayMul(rid,DAYTYPE)*todW(clk)*metroW(nm,clk,DAYTYPE);
  if(nt) load*=nodeMul(nt)*nodeGate(nt,clk); else if(major) load*=REAL_CFG.majorMul;
  if(i===0) load*=REAL_CFG.originMul; else if(i===n-1) load*=REAL_CFG.endMul;
  const fl=flowLoad(nm,rid,clk,DAYTYPE); if(fl!=null) load=fl;
  return Math.max(REAL_CFG.loadMin,Math.min(REAL_CFG.loadMax,load));
}
// alighting probability: a fraction of onboard passengers get off here. Hubs and
// nightlife discharge more; later stops discharge more (people reach destinations).
function alightProb(nm,i,n){
  const nt=nodeType(nm); let p=0.18;
  if(nt==='rail'||nt==='hsr'||nt==='coach') p=0.40;
  else if(nt==='nightlife') p=0.34;
  else if(nt==='hospital') p=0.26;
  p*=0.7+0.6*(i/Math.max(1,n-1));
  return Math.min(0.7,p);
}
// ---- god-mode event demand field (filled by the 金手指 layer; empty in plain modes) ----
let EVENTS=[], EVENT_VER=0, EXTRA_DEPS=[];
function godSig(){ return EVENT_VER+':'+EXTRA_DEPS.length; }
// dispersal curve: ramp up over first 15 min, plateau, then decay to 0 at dur.
function curveAt(dt,dur){ return dt<0||dt>dur?0:(dt<15?dt/15:Math.max(0,1-(dt-15)/Math.max(1,dur-15))); }
function stopIdx(rid,di,nm){ const r=DATA.routes.find(x=>x.id===rid); return r?r.dirs[di].stops.indexOf(nm):-1; }
// pass-times of EXTRA_DEPS on (rid,nm) inside an event window. Adding 加车 puts more
// departures in the denominator below, so the injected crowd splits and crowding eases.
function extraPassTimes(rid,nm,ev){
  const out=[];
  for(const e of EXTRA_DEPS){
    if(e.rid!==rid) continue;
    const idx=stopIdx(rid,e.di,nm); if(idx<0||idx<e.fromIdx) continue;
    const v=SCHED.dirs[rid+'|'+e.di]; if(!v) continue;
    const pass=e.dep+(v.stopT[idx]-v.stopT[e.fromIdx]);
    if(pass>=ev.tStart&&pass<=ev.tStart+ev.dur) out.push(pass);
  }
  return out;
}
// Extra boardings injected at a stop by active events (concert/sports dispersal).
// Crowd spreads spatially (stopW, sum=1) and across EVERY route serving the stop
// (routeShare[nm], sum=1 per stop → transfer spillover to other lines), then is
// conserved across the departures passing during the window (scheduled + extra),
// weighted by the dispersal curve. Deterministic given EVENTS/EXTRA_DEPS.
function eventBoard(nm,clk,rid){
  if(!EVENTS.length) return 0;
  let s=0;
  for(const ev of EVENTS){
    const sw=ev.stopW[nm]; if(sw==null) continue;
    const rm=ev.routeShare[nm]; const rs=rm?rm[rid]:0; if(!rs) continue;
    const c=curveAt(clk-ev.tStart,ev.dur); if(c<=0) continue;
    const sched=(ev.sched[nm]&&ev.sched[nm][rid])||[];
    const extra=extraPassTimes(rid,nm,ev);
    let wsum=0;
    for(const p of sched) wsum+=curveAt(p-ev.tStart,ev.dur);
    for(const p of extra) wsum+=curveAt(p-ev.tStart,ev.dur);
    if(wsum<=1e-9) continue;
    s+=ev.crowd*sw*rs*c/wsum;
  }
  return s;
}
// ---- reserved OD (origin-destination) interface ----
// A future serious OD study can inject setODModel(fn): fn(rid,di,k,i,j)->pax travelling
// from stop i to stop j on this departure. When present it would replace the
// probabilistic alightings below with true destination-aware alightings. Not computed now.
let OD_MODEL=null;
function setODModel(fn){ OD_MODEL=(typeof fn==='function')?fn:null; paxCache.clear(); }
function odFlow(rid,di,k,i,j){ try{ return OD_MODEL?OD_MODEL(rid,di,k,i,j):null; }catch(e){ return null; } }
// Per-departure boardings/alightings/onboard, deterministic (separate rng stream so the
// dwell sequence is unchanged). Pax counts are tied to the dwell tier so 上下车客流量与
// 停站时间相匹配: short door-cycle → 0-1 pax, normal → a few, busy hub → many.
const PAX_BOARD = 0.6;
const paxCache = new Map();
function paxPlan(v,key,k,plan){
  const ck=key+'|'+k+'|'+DAYTYPE+'|'+godSig();
  let p=paxCache.get(ck); if(p) return p;
  const rid=key.split('|')[0], di=+key.split('|')[1];
  const r=DATA.routes.find(x=>x.id===rid); const names=v.names||(r?r.dirs[di].stops:[]);
  const n=v.stopT.length, cap=capacity(rid);
  const rng=mulberry32(hashStr(key+'#'+k+'#pax'));
  const dwr=plan&&plan.dwr?plan.dwr:null, sk=plan?plan.sk:null, dw=SCHED.model.dwell;
  const B=new Array(n).fill(0), A=new Array(n).fill(0), occ=new Array(n).fill(0);
  let onboard=0;
  for(let i=0;i<n;i++){
    if(sk&&sk[i]){ occ[i]=onboard; continue; }
    const nm=names[i], clk=v.deps[k]+v.stopT[i];
    const load=demandLoad(rid,nm,clk,i,n);
    const d=dwr?(dwr[i]!=null?dwr[i]:dw):dw;
    const tier=d<=REAL_CFG.quickMax+1e-9?0:d>=dw*REAL_CFG.busyMul[0]?2:1;
    const tierMul=[0.5,1.0,1.9][tier];
    let board=Math.round(load*PAX_BOARD*tierMul*(0.7+rng()*0.7));
    board+=Math.round(eventBoard(nm,clk,rid));
    if(i===n-1) board=0;
    let alight;
    if(i===n-1) alight=onboard;
    else if(i===0) alight=0;
    else alight=Math.round(onboard*alightProb(nm,i,n)*(0.8+rng()*0.4));
    alight=Math.min(onboard,alight);
    const afterAlight=onboard-alight;
    board=Math.min(board,cap-afterAlight);
    onboard=afterAlight+board;
    B[i]=board; A[i]=alight; occ[i]=onboard;
  }
  p={B,A,occ,cap}; paxCache.set(ck,p); return p;
}
// occupancy of a departure at elapsed real minutes el (interpolated between stops).
function occAt(v,plan,pax,el){
  if(!pax) return 0;
  const st=plan?plan.st:v.stopT, n=st.length;
  let i=0; while(i<n-1&&st[i+1]<=el) i++;
  return pax.occ[i];
}
function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function peakW(m) {
  const tod = ((m % 1440) + 1440) % 1440;
  const tri = (x, a, b, c) => x <= a || x >= c ? 0 : (x < b ? (x - a) / (b - a) : (c - x) / (c - b));
  return Math.max(tri(tod, 300, 420, 540), tri(tod, 1000, 1110, 1220));
}
function fastSpans(v) {
  let s = fastCache.get(v); if (s) return s;
  s = []; const k = v.stopKm;
  for (let i = 0; i < k.length - 1; i++) if (k[i + 1] - k[i] > REAL_CFG.fastGapKm) s.push([k[i], k[i + 1]]);
  fastCache.set(v, s); return s;
}
function inFast(v, kmx) { const s = fastSpans(v); for (let i = 0; i < s.length; i++) if (kmx >= s[i][0] - 1e-6 && kmx <= s[i][1] + 1e-6) return true; return false; }
// Signal positions (theoretical minutes) inferred from geometry: a junction
// proxy every ~lightSpacing km of urban running, plus notable turns. Limited-
// access spans (long non-stop gaps) carry no signals. Cached per direction.
function dirLights(v) {
  let L = lightCache.get(v); if (L) return L;
  L = []; const f = v.frames; let since = 0;
  for (let i = 1; i < f.length; i++) {
    const dkm = f[i][4] - f[i - 1][4];
    if (dkm <= 1e-9) continue;
    if (inFast(v, f[i][4])) { since = 0; continue; }
    const dh = Math.abs(((f[i][3] - f[i - 1][3] + 540) % 360) - 180);
    since += dkm;
    if (since >= REAL_CFG.lightSpacing || dh > REAL_CFG.turnLightDeg) { L.push(f[i][0]); since = 0; }
  }
  lightCache.set(v, L); return L;
}
function accelFor(d) { return REAL_CFG.accel + (d > 1.0 ? REAL_CFG.accelLong : 0); }
function travelReal(a, b, depBase, sev) { return (b - a) * (1 + sev * REAL_CFG.congMax * peakW(depBase + (a + b) / 2)); }
function buildReal(v, key, k) {
  const rng = mulberry32(hashStr(key + '#' + k));
  const n = v.stopT.length, dw = SCHED.model.dwell, f = v.frames, depBase = v.deps[k];
  const r = DATA.routes.find(x => x.id === key.split('|')[0]);
  const di = +key.split('|')[1];
  const names = v.names || (r ? r.dirs[di].stops : []);
  const sk = new Array(n).fill(false);
  if (v.skip) for (const w of v.skip) for (let i = 0; i < n; i++) if (w.i === i) {
    const pass = depBase + v.stopT[i]; if (pass >= w.from && pass < w.to) sk[i] = true;
  }
  const dwr = new Array(n);
  const rid = key.split('|')[0];
  const wDay = routeW(rid) * dayMul(rid, DAYTYPE);
  for (let i = 0; i < n; i++) {
    if (sk[i]) { dwr[i] = 0; continue; }
    const nm = names[i];
    const nRoutes = nm && DATA.stops[nm] ? Object.keys(DATA.stops[nm].routes).length : 1;
    const nt = nodeType(nm), major = !nt && nRoutes >= REAL_CFG.majorRoutes;
    const clk = depBase + v.stopT[i];
    let load = wDay * todW(clk) * metroW(nm, clk, DAYTYPE);
    if (nt) load *= nodeMul(nt) * nodeGate(nt, clk); else if (major) load *= REAL_CFG.majorMul;
    if (i === 0) load *= REAL_CFG.originMul; else if (i === n - 1) load *= REAL_CFG.endMul;
    const fl = flowLoad(nm, rid, clk, DAYTYPE); if (fl != null) load = fl;
    load = Math.max(REAL_CFG.loadMin, Math.min(REAL_CFG.loadMax, load));
    const pBusy = Math.min(REAL_CFG.busyCap, REAL_CFG.pBusyBase * Math.pow(load, REAL_CFG.pBusyExp));
    const pQuick = Math.max(0.05, Math.min(0.92, REAL_CFG.pQuickBase + REAL_CFG.pQuickSlope * (1 - load)));
    const busyNode = nt === 'rail' || nt === 'hsr' || nt === 'coach' || nt === 'nightlife';
    const u = rng();
    if (u < pQuick) dwr[i] = REAL_CFG.quickMin + rng() * (REAL_CFG.quickMax - REAL_CFG.quickMin);
    else if (u < pQuick + pBusy) dwr[i] = dw * (REAL_CFG.busyMul[0] + rng() * (REAL_CFG.busyMul[1] - REAL_CFG.busyMul[0])) * (busyNode ? REAL_CFG.hubBusyMul : 1);
    else dwr[i] = dw * (REAL_CFG.normMul[0] + rng() * (REAL_CFG.normMul[1] - REAL_CFG.normMul[0]));
  }
  const depDelay = +(rng() * rng() * REAL_CFG.depMax).toFixed(2);
  const sev = rng();
  const reds = [];
  for (const tau of dirLights(v)) {
    const u = rng();
    if (u < REAL_CFG.pRed) reds.push({tau, wait: REAL_CFG.redMin + rng() * (REAL_CFG.redMax - REAL_CFG.redMin)});
    else if (u < REAL_CFG.pRed + REAL_CFG.pYellow) reds.push({tau, wait: REAL_CFG.yellowWait});
  }
  reds.sort((a, b) => a.tau - b.tau);
  const dstop = new Array(f.length - 1).fill(-1);
  for (let i = 0; i < f.length - 1; i++) {
    if (Math.abs(f[i][1] - f[i + 1][1]) < 1e-9 && Math.abs(f[i][2] - f[i + 1][2]) < 1e-9) {
      let s = -1, best = 1e9;
      for (let j = 0; j < n; j++) { const d = Math.abs(v.stopKm[j] - f[i][4]); if (d < best) { best = d; s = j; } }
      dstop[i] = best < 0.02 ? s : -2;
    }
  }
  const RT = [[0, f[0][0]]];
  const push = (real, tau) => {
    const last = RT[RT.length - 1];
    if (real <= last[0] + 1e-9) { if (tau > last[1]) last[1] = tau; return; }
    RT.push([real, tau]);
  };
  let real = depDelay, ri = 0, pendAccel = 0;
  push(real, f[0][0]);
  for (let i = 0; i < f.length - 1; i++) {
    const ta = f[i][0], tb = f[i + 1][0];
    while (ri < reds.length && reds[ri].tau <= ta + 1e-9) {
      const w = reds[ri].wait; real += w; push(real, ta); pendAccel += accelFor(w); ri++;
    }
    if (dstop[i] >= 0) {
      const s = dstop[i], dReal = dwr[s] !== undefined ? dwr[s] : dw;
      real += dReal; push(real, tb); pendAccel += accelFor(dReal);
    } else if (dstop[i] === -2) {
      real += travelReal(ta, tb, depBase, sev); push(real, tb);
    } else {
      let cur = ta;
      while (ri < reds.length && reds[ri].tau < tb - 1e-9) {
        const tr = reds[ri].tau;
        real += travelReal(cur, tr, depBase, sev); push(real, tr);
        const w = reds[ri].wait; real += w; push(real, tr); pendAccel += accelFor(w);
        cur = tr; ri++;
      }
      if (pendAccel > 0 && tb > cur + 1e-9) {
        const tm = cur + (tb - cur) * 0.5;
        real += travelReal(cur, tm, depBase, sev) * 1.5 + pendAccel; push(real, tm);
        real += travelReal(tm, tb, depBase, sev) * 0.85; push(real, tb);
        pendAccel = 0;
      } else {
        real += travelReal(cur, tb, depBase, sev); push(real, tb);
      }
    }
  }
  while (ri < reds.length) { real += reds[ri].wait; push(real, f[f.length - 1][0]); ri++; }
  const tauToReal = tau => {
    let lo = 0, hi = RT.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (RT[mid][1] < tau - 1e-9) lo = mid + 1; else hi = mid; }
    const j = Math.max(1, lo), a = RT[j - 1], b = RT[j];
    const span = b[1] - a[1];
    const u = span > 1e-9 ? Math.max(0, Math.min(1, (tau - a[1]) / span)) : 1;
    return a[0] + (b[0] - a[0]) * u;
  };
  const st = new Array(n);
  for (let i = 0; i < n; i++) st[i] = +tauToReal(v.stopT[i]).toFixed(3);
  const run = +RT[RT.length - 1][0].toFixed(3);
  let nRed = 0; for (const x of reds) if (x.wait > REAL_CFG.yellowWait + 1e-9) nRed++;
  return {st, sk, run, dwr, real: true, rt: RT, depDelay, sev, diag: {nRed, nLight: dirLights(v).length}};
}
function posReal(v, plan, el) {
  const RT = plan.rt;
  if (el <= RT[0][0]) return posAt(v, RT[0][1]);
  const last = RT[RT.length - 1];
  if (el >= last[0]) return posAt(v, last[1]);
  let lo = 0, hi = RT.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (RT[mid][0] < el) lo = mid + 1; else hi = mid; }
  const j = Math.max(1, lo), a = RT[j - 1], b = RT[j];
  const span = b[0] - a[0];
  const u = span > 1e-9 ? (el - a[0]) / span : 0;
  return posAt(v, a[1] + (b[1] - a[1]) * u);
}
function planFor(v, key, k) {
  if (!REAL) return depPlan(v, key, k);
  const ck = key + '|' + k + '|' + DAYTYPE;
  let p = realCache.get(ck);
  if (!p) { p = buildReal(v, key, k); realCache.set(ck, p); }
  return p;
}
function busIcon(color, rid) {
  const svg = '<svg width="20" height="28" viewBox="-10 -14 20 28">' +
    '<rect x="-5" y="-12" width="10" height="24" rx="2.6" fill="' + color + '" stroke="#0b1020" stroke-width="1.2"/>' +
    '<rect x="-3.6" y="-10.6" width="7.2" height="3.6" rx="1.2" fill="#0b1020" opacity="0.8"/>' +
    '<rect x="-3.6" y="8.2" width="7.2" height="2.6" rx="1" fill="#0b1020" opacity="0.6"/>' +
    '<rect x="-4.4" y="-5.4" width="1.5" height="3" fill="#0b1020" opacity="0.55"/>' +
    '<rect x="2.9" y="-5.4" width="1.5" height="3" fill="#0b1020" opacity="0.55"/>' +
    '<rect x="-4.4" y="-1.2" width="1.5" height="3" fill="#0b1020" opacity="0.55"/>' +
    '<rect x="2.9" y="-1.2" width="1.5" height="3" fill="#0b1020" opacity="0.55"/>' +
    '<rect x="-4.4" y="3" width="1.5" height="3" fill="#0b1020" opacity="0.55"/>' +
    '<rect x="2.9" y="3" width="1.5" height="3" fill="#0b1020" opacity="0.55"/>' +
    '<rect x="-1.1" y="-4.6" width="2.2" height="9" rx="1" fill="#ffffff" opacity="0.35"/>' +
    '<circle cx="-3.2" cy="-12" r="1.1" fill="#ffe9a8"/><circle cx="3.2" cy="-12" r="1.1" fill="#ffe9a8"/></svg>';
  return L.divIcon({className: 'busicon', iconSize: [20, 28], iconAnchor: [10, 14],
    html: '<div class="busrot">' + svg + '</div><span class="buslab" style="border-color:' + color + '">' + rid + '</span>'});
}
function nextArrivals(nm, st) {
  let h = '<div class="prow" style="margin-top:6px;border-top:1px solid #2c3a6e;padding-top:4px"><b>模拟下一班到站</b>（当前 ' + fmtT(SIM.t) + '，估算）</div>';
  const skInfo = (SCHED.skipStops || []).find(x => x.name === nm);
  if (skInfo) h += '<div class="prow pskip">⚠ ' + skInfo.window + ' 飞站通过不停靠（走高架）</div>';
  for (const rid of Object.keys(st.routes)) {
    const r = DATA.routes.find(x => x.id === rid);
    for (const di of st.routes[rid]) {
      const key = rid + '|' + di;
      const v = SCHED.dirs[key];
      if (!v) continue;
      const idx = r.dirs[di].stops.indexOf(nm);
      if (idx < 0) continue;
      const dest = rid === 'Y33' ? (di === 0 ? '内圈' : '外圈') : '往' + r.dirs[di].to;
      let arrK = -1, arrAt = 0, passInfo = null;
      for (let k = 0; k < v.deps.length; k++) {
        const dep = v.deps[k];
        const plan = planFor(v, key, k);
        const at = plan ? plan.st[idx] : v.stopT[idx];
        if (dep + at < SIM.t) continue;
        if (plan && plan.sk[idx]) { if (!passInfo) passInfo = {dep, at}; continue; }
        arrK = k; arrAt = at; break;
      }
      if (passInfo) h += '<div class="prow pskip"><span style="color:' + r.color + '">' + r.label + '</span> ' + dest +
        ' → ' + fmtT(passInfo.dep + passInfo.at) + ' 飞站通过不停靠</div>';
      if (arrK < 0) {
        if (!passInfo) h += '<div class="prow"><span style="color:' + r.color + '">' + r.label + '</span> ' + dest +
          ' → <span style="color:#7f8db8">已收车</span></div>';
        continue;
      }
      const dep = v.deps[arrK], plan = planFor(v, key, arrK);
      const wait = dep + arrAt - SIM.t;
      let distTxt;
      if (idx === 0) distTxt = '始发站';
      else if (dep > SIM.t) distTxt = '距起点 <b>' + v.stopKm[idx].toFixed(1) + '</b> km（待发车）';
      else distTxt = '距本站 <b>' + Math.max(0, v.stopKm[idx] - posAt(v, SIM.t - dep, plan)[3]).toFixed(1) + '</b> km';
      h += '<div class="prow"><span style="color:' + r.color + '">' + r.label + '</span> ' + dest + ' → ' + fmtT(dep + arrAt) +
        '<span class="pwait">等待 <b>' + fmtWait(wait) + '</b> · ' + distTxt + '</span></div>';
    }
  }
  return h;
}
const isNarrow = () => { try { if (window.matchMedia) return window.matchMedia('(max-width:760px)').matches; } catch (e) {} return (window.innerWidth || 1280) <= 760; };
function playLabel(){ return SIM.playing ? (isNarrow() ? '⏸' : '⏸ 暂停') : (isNarrow() ? '▶' : '▶ 播放'); }
function speedLabel(open){ return (isNarrow() ? '⏱' : '⏱ ' + fmtSpeed(SIM.speed)) + (open ? ' ▾' : ' ▴'); }
function modeLabel(){ return REAL ? (isNarrow() ? '🌆' : '🌆 现实模式') : (isNarrow() ? '🌙' : '🌙 理论模式'); }
const DAYTYPES = ['weekday','weekend','holiday'];
const DAYLAB = {weekday:'工作日',weekend:'周末',holiday:'节假日'};
function dayLabel(){ return isNarrow() ? '🗓' : '🗓 ' + DAYLAB[DAYTYPE]; }
function fsLabel(){ return fsActive() ? (isNarrow() ? '🗗' : '🗗 退出全屏') : (isNarrow() ? '⛶' : '⛶ 全屏'); }
const fsbtn = document.getElementById('fsbtn');
function refreshBarLabels(){
  playBtn.textContent = playLabel();
  speedbtn.textContent = speedLabel(!speedpanel.hidden);
  modebtn.textContent = modeLabel();
  const db = document.getElementById('daybtn'); if (db) db.textContent = dayLabel();
  if (fsbtn) fsbtn.textContent = fsLabel();
  const st = document.getElementById('sidetoggle'); if (st) st.textContent = isNarrow() ? '☰' : '☰ 线路';
  const gb = document.getElementById('godbtn'); if (gb) gb.textContent = isNarrow() ? '🪄' : '🪄 金手指';
}
const playBtn = document.getElementById('play');
const scrub = document.getElementById('scrub');
scrub.min = SCHED.start; scrub.max = SCHED.end; scrub.step = 0.25; scrub.value = SIM.t;
playBtn.onclick = () => {
  if (!SIM.playing && SIM.t >= SCHED.end - 0.01) SIM.t = SCHED.start;
  SIM.playing = !SIM.playing;
  playBtn.textContent = playLabel();
  dirty = true;
};
scrub.addEventListener('pointerdown', () => { dragging = true; });
window.addEventListener('pointerup', () => { dragging = false; });
scrub.oninput = () => { SIM.t = +scrub.value; dirty = true; };
const doJump = () => {
  const m = document.getElementById('tinput').value.trim().match(/^(\\d{1,2}):(\\d{2})/);
  if (!m) return;
  let v = (+m[1]) * 60 + (+m[2]);
  if (+m[1] < 12) v += 1440;
  if (v < SCHED.start) v += 1440;
  SIM.t = Math.max(SCHED.start, Math.min(SCHED.end, v));
  dirty = true;
};
document.getElementById('jump').onclick = doJump;
document.getElementById('tinput').onkeydown = e => { if (e.key === 'Enter') doJump(); };

// ---------- speedometer dial (summoned by button) ----------
const GEARS = [1/6, 1/3, 0.5, 1, 5, 15, 20, 30, 60, 120];
const GLEN = __GLEN__;
const gsvg = document.getElementById('gsvg');
const gneedle = document.getElementById('gneedle');
const gfill = document.getElementById('gfill');
const speedval = document.getElementById('speedval');
const speedbtn = document.getElementById('speedbtn');
const speedpanel = document.getElementById('speedpanel');
let gearIdx = 3, gdrag = false;
function setSpeed(i) {
  gearIdx = Math.max(0, Math.min(GEARS.length - 1, i));
  SIM.speed = GEARS[gearIdx];
  if (SIM.speed >= 120) unlock('speedster');
  const frac = gearIdx / (GEARS.length - 1);
  const a = 195 - 210 * frac;
  gneedle.setAttribute('transform', 'rotate(' + (90 - a).toFixed(1) + ' 66 70)');
  gfill.setAttribute('stroke-dasharray', (GLEN * frac).toFixed(1) + ' ' + GLEN.toFixed(1));
  speedval.textContent = fmtSpeed(SIM.speed);
  speedbtn.textContent = speedLabel(!speedpanel.hidden);
  gsvg.setAttribute('aria-valuenow', String(SIM.speed));
  document.querySelectorAll('.glab').forEach(t => {
    const on = +t.dataset.i === gearIdx;
    t.setAttribute('fill', on ? '#ffd97a' : '#8fa0c9');
    t.setAttribute('font-weight', on ? 'bold' : 'normal');
  });
  dirty = true;
}
function gaugePick(e) {
  const rect = gsvg.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const x = (e.clientX - rect.left) * 132 / rect.width;
  const y = (e.clientY - rect.top) * 92 / rect.height;
  let a = Math.atan2(70 - y, x - 66) * 180 / Math.PI;
  if (a < -15) a = a < -90 ? 195 : -15;
  a = Math.max(-15, Math.min(195, a));
  setSpeed(Math.round((195 - a) / 210 * (GEARS.length - 1)));
}
gsvg.addEventListener('pointerdown', e => { gdrag = true; gsvg.setPointerCapture(e.pointerId); gaugePick(e); e.preventDefault(); });
gsvg.addEventListener('pointermove', e => { if (gdrag) gaugePick(e); });
gsvg.addEventListener('pointerup', () => { gdrag = false; });
// ← → speed nudge lives at window level (keydown handler below) so it works
// whenever the dial is open — the old gsvg-level listener never fired because
// opening the panel leaves focus on the speed button, not the SVG.
const setSpeedPanel = open => {
  speedpanel.hidden = !open;
  speedbtn.classList.toggle('on', open);
  speedbtn.textContent = speedLabel(open);
};
speedbtn.onclick = () => setSpeedPanel(speedpanel.hidden);
const modebtn = document.getElementById('modebtn');
function setReal(on) {
  REAL = !!on;
  modebtn.textContent = modeLabel();
  modebtn.classList.toggle('real', REAL);
  modebtn.title = REAL ? '当前：现实模式（随机延误 / 红绿灯 / 堵车 / 停站波动）' : '当前：理论模式（图定时刻表）';
  const db = document.getElementById('daybtn');
  if (db) { db.disabled = !REAL; db.textContent = dayLabel(); db.classList.toggle('on', REAL && DAYTYPE !== 'weekday'); }
  const gb = document.getElementById('godbtn');
  if (gb) { gb.disabled = !REAL; if (!REAL && GOD) setGod(false); }
  if (REAL) unlock('realist');
  dirty = true;
  renderSim(); renderBoard();
  if (flash) updateFlash();
  if (livePopup) livePopup.p.setContent(livePopup.i.html + nextArrivals(livePopup.i.nm, livePopup.i.st));
}
modebtn.onclick = () => setReal(!REAL);
const daybtn = document.getElementById('daybtn');
function setDayType(dt) {
  DAYTYPE = dt; realCache.clear();
  daybtn.textContent = dayLabel();
  daybtn.classList.toggle('on', dt !== 'weekday');
  daybtn.title = '现实模式客流日型：' + DAYLAB[dt] + '（仅影响现实模式停站需求；地铁延时与客流随日型变化）';
  if (dt === 'holiday') unlock('holiday');
  dirty = true; renderSim(); renderBoard();
  if (flash) updateFlash();
  if (livePopup) livePopup.p.setContent(livePopup.i.html + nextArrivals(livePopup.i.nm, livePopup.i.st));
}
daybtn.onclick = () => { if (!REAL) return; setDayType(DAYTYPES[(DAYTYPES.indexOf(DAYTYPE) + 1) % DAYTYPES.length]); };
function fsActive(){ return !!(document.fullscreenElement || document.webkitFullscreenElement); }
function syncFs(){ if (fsbtn) { fsbtn.textContent = fsLabel(); fsbtn.classList.toggle('on', fsActive()); } }
function toggleFs(){
  const el = document.documentElement || document.body;
  if (!fsActive()) { const r = el.requestFullscreen || el.webkitRequestFullscreen; if (r) { try { const p = r.call(el); if (p && p.catch) p.catch(() => {}); } catch (e) {} } }
  else { const x = document.exitFullscreen || document.webkitExitFullscreen; if (x) { try { x.call(document); } catch (e) {} } }
}
if (fsbtn) {
  fsbtn.onclick = toggleFs;
  if (!(document.fullscreenEnabled || document.webkitFullscreenEnabled)) fsbtn.style.display = 'none';
  syncFs();
}
['fullscreenchange', 'webkitfullscreenchange'].forEach(ev => document.addEventListener(ev, () => { syncFs(); setTimeout(() => map.invalidateSize(), 80); }));
document.addEventListener('pointerdown', e => {
  if (!speedpanel.hidden && !speedpanel.contains(e.target) && e.target !== speedbtn) setSpeedPanel(false);
});
setSpeed(3);

// ---------- live stop popup ----------
let livePopup = null, lastPop = 0;
// autoPan is off on all popups: Leaflet would otherwise re-pan on every
// moveend (and content update), yanking the map back while the user drags.
// Fit the popup into view once, at open time only.
function fitPopup(p) {
  const c = p && p._container; if (!c || !c.getBoundingClientRect) return;
  const mr = map.getContainer().getBoundingClientRect();
  const pr = c.getBoundingClientRect();
  let dx = 0, dy = 0;
  if (pr.left < mr.left + 4) dx = pr.left - mr.left - 4;
  else if (pr.right > mr.right - 4) dx = pr.right - mr.right + 4;
  if (pr.top < mr.top + 4) dy = pr.top - mr.top - 4;
  else if (pr.bottom > mr.bottom - 4) dy = pr.bottom - mr.bottom + 4;
  if (dx || dy) map.panBy([dx, dy], {animate: false});
}
map.on('popupopen', e => {
  const s = e.popup && e.popup._source;
  livePopup = s && s._stopInfo ? {p: e.popup, i: s._stopInfo} : null;
  if (livePopup) { livePopup.p.setContent(livePopup.i.html + nextArrivals(livePopup.i.nm, livePopup.i.st)); lastPop = performance.now(); }
  fitPopup(e.popup);
});
map.on('popupclose', () => { livePopup = null; });

// ---------- railway-style departure board (docked top-right) ----------
const board = document.getElementById('board');
const bbody = document.getElementById('bbody');
let lastBoard = 0;
const BKEY = 'njbus_board_v1';
const bstore = {
  get() { try { return JSON.parse(localStorage.getItem(BKEY)); } catch (e) { return null; } },
  set(v) { try { localStorage.setItem(BKEY, JSON.stringify(v)); } catch (e) {} }
};
function busState(v, stops, el, dep, plan) {
  const st = plan ? plan.st : v.stopT, n = st.length, dw0 = SCHED.model.dwell;
  const dwr = plan && plan.dwr ? plan.dwr : null;
  const sk = plan ? plan.sk : null, run = plan ? plan.run : v.run;
  let i = 0;
  while (i < n - 1 && st[i + 1] <= el) i++;
  if (i >= n - 1 || el >= run) return {status: '终到', seg: stops[n - 1], next: '—', eta: '—', cls: 'bstop'};
  let j = i + 1;
  while (j < n - 1 && sk && sk[j]) j++;
  const dwi = dwr ? (dwr[i] !== undefined ? dwr[i] : dw0) : dw0;
  if (sk && sk[i]) {
    if (el < st[i] + dw0) return {status: '飞站', seg: stops[i] + '（通过不停车）', next: stops[j], eta: fmtT(dep + st[j]), cls: 'bskip'};
    return {status: '行驶', seg: stops[i] + ' → ' + stops[j], next: stops[j], eta: fmtT(dep + st[j]), cls: 'brun'};
  }
  if (el < st[i] + dwi) return {status: '停靠', seg: stops[i], next: stops[j], eta: fmtT(dep + st[j]), cls: 'bstop'};
  return {status: '行驶', seg: stops[i] + ' → ' + stops[j], next: stops[j], eta: fmtT(dep + st[j]), cls: 'brun'};
}
function renderBoard() {
  const t = SIM.t;
  document.getElementById('bclock').textContent = fmtT(t);
  const q = (document.getElementById('bq').value || '').trim();
  const only = document.getElementById('bonly').checked;
  const rows = [];
  let nrun = 0, ndep = 0, nwait = 0;
  for (const r of DATA.routes) {
    r.dirs.forEach((d, di) => {
      const v = SCHED.dirs[r.id + '|' + di];
      if (!v) return;
      for (let k = 0; k < v.deps.length; k++) {
        const dep = v.deps[k];
        if (dep > t) { nwait++; continue; }
        ndep++;
        const plan = planFor(v, r.id + '|' + di, k);
        if (dep + (plan ? plan.run : v.run) < t) continue;
        nrun++;
        if (only && chipState[r.id] === false) continue;
        const bs = busState(v, d.stops, t - dep, dep, plan);
        const dir = r.id === 'Y33' ? (di === 0 ? '内圈' : '外圈') : d.from + '→' + d.to;
        if (q && !(r.label + dir + bs.seg + bs.next).includes(q)) continue;
        rows.push({r, di, k, dep, bs, dir, depShow: dep + (plan && plan.real ? plan.depDelay : 0)});
      }
    });
  }
  document.getElementById('brun').textContent = nrun;
  document.getElementById('bdep').textContent = ndep;
  document.getElementById('bwait').textContent = nwait;
  rows.sort((a, b) => ORDER[a.r.id] - ORDER[b.r.id] || a.di - b.di || a.dep - b.dep);
  let h = '';
  for (const x of rows) {
    h += '<tr data-key="' + x.r.id + '|' + x.di + '|' + x.k + '">' +
      '<td><span class="bled" style="color:' + x.r.color + '">' + x.r.label + '</span></td>' +
      '<td class="bdir">' + x.dir + '</td>' +
      '<td>' + fmtT(x.depShow) + '</td>' +
      '<td class="bseg">' + x.bs.seg + '</td>' +
      '<td>' + x.bs.next + '</td>' +
      '<td>' + x.bs.eta + '</td>' +
      '<td><span class="bstat ' + x.bs.cls + '">' + x.bs.status + '</span></td></tr>';
  }
  bbody.innerHTML = h || '<tr><td colspan="7" class="bempty">当前无运行车辆</td></tr>';
}
document.getElementById('bq').oninput = renderBoard;
document.getElementById('bonly').onchange = renderBoard;
bbody.addEventListener('click', e => {
  const tr = e.target.closest ? e.target.closest('tr') : null;
  if (!tr || !tr.dataset.key) return;
  locateBus(tr.dataset.key);
  openFlash(tr.dataset.key);
});
function locateBus(key) {
  const parts = key.split('|');
  const v = SCHED.dirs[parts[0] + '|' + parts[1]];
  if (!v) return;
  const q = posAt(v, SIM.t - v.deps[+parts[2]], planFor(v, parts[0] + '|' + parts[1], +parts[2]));
  map.setView(pt(q[0], q[1]), 14);
}
// drag + resize + minimize, persisted
(() => {
  const head = document.getElementById('bhead');
  const grip = document.getElementById('bgrip');
  const minBtn = document.getElementById('bmin');
  const clampBox = () => {
    const mini = board.classList.contains('mini');
    let w = board.offsetWidth || 440, h = board.offsetHeight || 300;
    if (w > window.innerWidth - 8) { board.style.width = Math.max(240, window.innerWidth - 8) + 'px'; w = board.offsetWidth; }
    if (!mini && h > window.innerHeight - 8) { board.style.height = Math.max(120, window.innerHeight - 8) + 'px'; h = board.offsetHeight; }
    let l = parseFloat(board.style.left), t = parseFloat(board.style.top);
    if (isNaN(l) || isNaN(t)) return;
    l = Math.max(0, Math.min(window.innerWidth - w, l));
    t = Math.max(0, Math.min(window.innerHeight - Math.min(h, window.innerHeight - 8), t));
    board.style.left = l + 'px'; board.style.top = t + 'px';
  };
  const save = () => bstore.set({l: board.style.left, t: board.style.top,
    w: board.style.width, h: board.style.height, mini: board.classList.contains('mini')});
  const saved = bstore.get();
  if (saved) {
    if (saved.w) board.style.width = saved.w;
    if (saved.h) board.style.height = saved.h;
    if (saved.l) { board.style.left = saved.l; board.style.top = saved.t; board.style.right = 'auto'; }
    if (saved.mini) board.classList.add('mini');
    clampBox();
  }
  let mode = null, sx = 0, sy = 0, ol = 0, ot = 0, ow = 0, oh = 0;
  const down = (e, m) => {
    if (e.target.closest && e.target.closest('button,input')) return;
    mode = m; sx = e.clientX; sy = e.clientY;
    const rect = board.getBoundingClientRect();
    ol = rect.left; ot = rect.top; ow = rect.width; oh = rect.height;
    board.style.left = ol + 'px'; board.style.top = ot + 'px'; board.style.right = 'auto';
    e.preventDefault();
  };
  head.addEventListener('pointerdown', e => down(e, 'move'));
  grip.addEventListener('pointerdown', e => down(e, 'size'));
  window.addEventListener('pointermove', e => {
    if (!mode) return;
    if (mode === 'move') {
      board.style.left = Math.max(0, Math.min(window.innerWidth - board.offsetWidth, ol + e.clientX - sx)) + 'px';
      board.style.top = Math.max(0, Math.min(window.innerHeight - Math.min(board.offsetHeight, window.innerHeight - 8), ot + e.clientY - sy)) + 'px';
    } else {
      board.style.width = Math.max(240, Math.min(window.innerWidth - 8 - ol, ow + e.clientX - sx)) + 'px';
      if (!board.classList.contains('mini'))
        board.style.height = Math.max(120, Math.min(window.innerHeight - 8 - ot, oh + e.clientY - sy)) + 'px';
    }
  });
  window.addEventListener('pointerup', () => { if (mode) { mode = null; clampBox(); save(); } });
  minBtn.onclick = () => {
    board.classList.toggle('mini');
    minBtn.textContent = board.classList.contains('mini') ? '□' : '—';
    save();
  };
  if (board.classList.contains('mini')) minBtn.textContent = '□';
  window.addEventListener('resize', clampBox);
})();
const sidebackdrop = document.getElementById('sidebackdrop');
const sideEl = document.getElementById('side');
function sideOpen(){ return document.body.classList.contains('showside'); }
function setSide(open){
  document.body.classList.toggle('showside', open);
  if (sidebackdrop) sidebackdrop.hidden = !open;
  setTimeout(() => map.invalidateSize(), 280);
}
document.getElementById('sidetoggle').onclick = () => setSide(!sideOpen());
const sideclose = document.getElementById('sideclose');
if (sideclose) sideclose.onclick = () => setSide(false);
if (sidebackdrop) sidebackdrop.onclick = () => setSide(false);
if (sideEl) {
  let sx = null, sy = null;
  sideEl.addEventListener('touchstart', e => { const t = e.changedTouches[0]; sx = t.clientX; sy = t.clientY; }, {passive: true});
  sideEl.addEventListener('touchend', e => { if (sx === null) return; const t = e.changedTouches[0]; const dx = t.clientX - sx, dy = t.clientY - sy; sx = null; if (isNarrow() && dx > 70 && Math.abs(dy) < 60) setSide(false); }, {passive: true});
}
function applyNarrowBoard(){
  const b = document.getElementById('board');
  if (b && isNarrow() && !b.classList.contains('mini')) { b.classList.add('mini'); const mb = document.getElementById('bmin'); if (mb) mb.textContent = '□'; }
}
function onResize(){ refreshBarLabels(); applyNarrowBoard(); map.invalidateSize(); }
window.addEventListener('resize', onResize);
window.addEventListener('orientationchange', () => setTimeout(onResize, 150));
applyNarrowBoard();
refreshBarLabels();

// ---------- metro flash line-map (top banner) ----------
const FSP = 78;
let flash = null, lastFlash = 0;
function openFlash(key) {
  let rid, di, k, r, d, v, plan, extra = false;
  const ex = EXTRA_DEPS.find(e => e.key === key);
  if (ex) {
    rid = ex.rid; di = ex.di; k = 0; extra = true;
    r = DATA.routes.find(x => x.id === rid); v = ex.v; plan = planFor(v, ex.key, 0);
    d = {stops: v.names, from: r.dirs[di].stops[ex.fromIdx], to: r.dirs[di].to};
  } else {
    const parts = key.split('|');
    rid = parts[0]; di = +parts[1]; k = +parts[2];
    r = DATA.routes.find(x => x.id === rid);
    v = SCHED.dirs[rid + '|' + di];
    if (!r || !v) return;
    d = r.dirs[di];
    plan = planFor(v, rid + '|' + di, k);
  }
  flash = {key, rid, di, k, r, d, v, plan, extra};
  const n = d.stops.length;
  const inner = document.getElementById('finner');
  inner.style.width = ((n - 1) * FSP + 60) + 'px';
  let h = '<div class="ftrack"></div><div class="flit" id="flit"></div><div class="fseg" id="fseg"></div>';
  d.stops.forEach((s, i) => {
    const x = 30 + i * FSP;
    const skipped = plan && plan.sk[i];
    h += '<div class="fdot' + (skipped ? ' skip' : '') + '" id="fd' + i + '" style="left:' + (x - 5) + 'px;color:' + r.color + '"></div>' +
      '<div class="flab ' + (i % 2 ? 'below' : 'above') + (i === 0 || i === n - 1 ? ' end' : '') +
      '" style="left:' + (x - 37) + 'px">' + s + (skipped ? ' <i class="ftag">飞</i>' : '') + '</div>';
  });
  h += '<div class="fbus" id="fbus" style="color:' + r.color + '"><div class="fbuscore"></div><div class="fbusring"></div></div>';
  inner.innerHTML = h;
  const el = document.getElementById('flash');
  el.hidden = false;
  el.style.borderColor = r.color;
  el.style.boxShadow = '0 14px 50px rgba(0,0,0,.6),0 0 34px ' + r.color + '55';
  const fl = document.getElementById('fline');
  fl.textContent = r.label; fl.style.background = r.color;
  document.getElementById('fdir').textContent = rid === 'Y33' ? (di === 0 ? '内圈运行' : '外圈运行') : d.from + ' → ' + d.to;
  document.getElementById('fdep').textContent = '本次发车 ' + fmtT(v.deps[k] + (plan && plan.real ? plan.depDelay : 0)) + (extra ? '（加车）' : '');
  updateFlash();
}
function flashGeom() {
  const v = flash.v, plan = flash.plan;
  const dep = v.deps[flash.k];
  const st = plan ? plan.st : v.stopT, sk = plan ? plan.sk : null;
  const run = plan ? plan.run : v.run, dw0 = SCHED.model.dwell, n = st.length;
  const dwr = plan && plan.dwr ? plan.dwr : null;
  const el = Math.max(0, Math.min(run, SIM.t - dep));
  let i = 0;
  while (i < n - 1 && st[i + 1] <= el) i++;
  const skipped = !!(sk && sk[i]);
  const dwi = dwr ? (dwr[i] !== undefined ? dwr[i] : dw0) : dw0;
  const dwelling = i < n - 1 && !skipped && el < st[i] + dwi;
  const passing = i < n - 1 && skipped && el < st[i] + dw0;
  // frac 0 at the terminal: i is already the last index, adding 1 would
  // push the bus a full stop-spacing past the end of the track.
  const frac = i < n - 1 ? Math.max(0, Math.min(1, (el - st[i]) / (st[i + 1] - st[i]))) : 0;
  const pos = 30 + (i + (dwelling ? 0 : frac)) * FSP;
  return {dep, st, sk, run, dw: dw0, n, el, i, skipped, dwelling, passing, pos, arrived: el >= run};
}
// Bus marker, lit track and follow-scroll all derive from the same instantaneous
// position and move together every frame, so they never drift apart. The old
// CSS left-transition lagging behind an instant scrollLeft made the marker wobble.
function placeFlashBus() {
  if (!flash) return;
  const pos = flashGeom().pos;
  const bus = document.getElementById('fbus');
  if (bus) bus.style.left = pos + 'px';
  const lit = document.getElementById('flit');
  if (lit) lit.style.width = pos + 'px';
  if (document.getElementById('ffollow').checked) {
    const strip = document.getElementById('fstrip');
    const cw = strip.clientWidth || 600;
    const max = Math.max(0, (strip.scrollWidth || 0) - cw);
    strip.scrollLeft = Math.max(0, Math.min(max, pos - cw / 2));
  }
}
function updateFlash() {
  if (!flash) return;
  const d = flash.d, r = flash.r;
  const g = flashGeom();
  const dep = g.dep, st = g.st, sk = g.sk, run = g.run, n = g.n, el = g.el, i = g.i;
  const dwelling = g.dwelling, passing = g.passing, arrived = g.arrived;
  let j = i + 1;
  while (j < n - 1 && sk && sk[j]) j++;
  document.getElementById('fclock').textContent = fmtT(SIM.t);
  document.getElementById('fcur').textContent = i >= n - 1 ? d.stops[n - 1]
    : dwelling ? d.stops[i] : passing ? d.stops[i] + '（飞站通过）' : d.stops[i] + ' → ' + d.stops[i + 1];
  document.getElementById('fnext').textContent = i < n - 1 ? d.stops[j] : '—';
  document.getElementById('feta').textContent = i < n - 1 ? fmtT(dep + st[j]) : '已到达';
  document.getElementById('fstatv').textContent = SIM.t < dep ? '待发车' : arrived ? '终到收车'
    : dwelling ? '停靠上下客' : passing ? '飞站通过不停车' : '区间运行';
  // crowding gauge (realistic / god mode only; theoretical shows rated capacity hint)
  const pax = flash.plan && flash.plan.real ? paxPlan(flash.v, flash.key, flash.k, flash.plan) : null;
  const cv = document.getElementById('fcrowdv'), cf = document.getElementById('fcfill'), cio = document.getElementById('fcio');
  if (pax) {
    const occ = pax.occ[i], ratio = occ / pax.cap, col = crowdColor(ratio);
    cv.textContent = occ + '/' + pax.cap + ' · ' + crowdTier(ratio) + ' ' + Math.round(ratio * 100) + '%';
    cv.style.color = col;
    cf.style.width = Math.min(100, ratio * 100) + '%'; cf.style.background = col;
    cio.textContent = (dwelling || arrived) ? '本站 上' + pax.B[i] + ' / 下' + pax.A[i] : '上' + pax.B[i] + ' / 下' + pax.A[i];
    if (ratio >= 1) unlock('full');
  } else {
    cv.textContent = '理论模式 · 额定' + capacity(flash.rid) + '人'; cv.style.color = '#7f8db8';
    cf.style.width = '0%'; cio.textContent = '切现实模式看客流';
  }
  const lit = document.getElementById('flit');
  lit.style.background = r.color; lit.style.color = r.color;
  const seg = document.getElementById('fseg');
  if (i < n - 1 && !dwelling && el < run) {
    seg.style.display = 'block'; seg.style.left = (30 + i * FSP) + 'px';
    seg.style.width = FSP + 'px'; seg.style.background = r.color; seg.style.color = r.color;
  } else seg.style.display = 'none';
  for (let jj = 0; jj < n; jj++) {
    const dot = document.getElementById('fd' + jj);
    const isSk = !!(sk && sk[jj]);
    dot.className = 'fdot' + (isSk ? ' skip' : '') + (jj < i ? ' done' : jj === i ? (dwelling || arrived ? ' done cur' : ' cur') : jj === i + 1 ? ' next' : '');
    dot.style.background = jj <= i && !isSk ? r.color : '#0b1126';
  }
  placeFlashBus();
}
const closeFlash = () => { flash = null; document.getElementById('flash').hidden = true; };
document.getElementById('fclose').onclick = closeFlash;
// ---------- searchable help modal ----------
const helpEl = document.getElementById('help');
const helpq = document.getElementById('helpq');
const helpSecs = Array.prototype.slice.call(document.querySelectorAll('#helpbody .hsec'));
helpSecs.forEach(s => { s.dataset.orig = s.innerHTML; });
function helpHighlight(sec, q) {
  if (!document.createTreeWalker || typeof NodeFilter === 'undefined') return;
  const walker = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT, null);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const text = node.nodeValue, lower = text.toLowerCase();
    let idx = lower.indexOf(q);
    if (idx < 0) continue;
    const frag = document.createDocumentFragment();
    let last = 0;
    while (idx >= 0) {
      frag.appendChild(document.createTextNode(text.slice(last, idx)));
      const mark = document.createElement('mark');
      mark.textContent = text.slice(idx, idx + q.length);
      frag.appendChild(mark);
      last = idx + q.length;
      idx = lower.indexOf(q, last);
    }
    frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }
}
function helpSearch() {
  const q = (helpq.value || '').trim().toLowerCase();
  let shown = 0;
  for (const s of helpSecs) {
    s.innerHTML = s.dataset.orig;
    const match = !q || s.textContent.toLowerCase().includes(q);
    s.hidden = !match;
    if (match) { shown++; if (q) helpHighlight(s, q); }
  }
  document.getElementById('helpcount').textContent = q ? shown + ' / ' + helpSecs.length + ' 节' : '';
  document.getElementById('helpempty').hidden = shown !== 0;
}
function openHelp() { helpEl.hidden = false; helpSearch(); if (helpq.focus) helpq.focus(); }
function closeHelp() { helpEl.hidden = true; }
document.getElementById('helpclose').onclick = closeHelp;
helpq.oninput = helpSearch;
helpEl.addEventListener('click', e => { if (e.target === helpEl) closeHelp(); });
window.addEventListener('keydown', e => {
  const tag = (e.target && e.target.tagName) || '';
  if (e.ctrlKey && e.shiftKey && (e.key === 'A' || e.key === 'a')) { openAch(); e.preventDefault(); return; }
  if (e.key === 'Escape') {
    if (!helpEl.hidden) { closeHelp(); return; }
    const ap = document.getElementById('achpage'); if (ap && !ap.hidden) { closeAch(); return; }
    const gp = document.getElementById('godpanel'); if (gp && !gp.hidden) { setGod(false); return; }
    if (flash) closeFlash();
    if (!speedpanel.hidden) setSpeedPanel(false);
    return;
  }
  // ← → / ↑ ↓ nudge the simulation speed while the dial is open, unless the
  // user is typing in a field (so the time box / scrubber keep native arrows).
  if (!speedpanel.hidden && tag !== 'INPUT' && tag !== 'TEXTAREA') {
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { setSpeed(gearIdx + 1); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { setSpeed(gearIdx - 1); e.preventDefault(); }
  }
});

function renderSim() {
  const t = SIM.t;
  document.getElementById('clock').textContent = fmtT(t);
  if (!dragging) scrub.value = t;
  const active = new Set();
  for (const r of DATA.routes) {
    if (chipState[r.id] === false) continue;
    r.dirs.forEach((d, di) => {
      const v = SCHED.dirs[r.id + '|' + di];
      if (!v) return;
      for (let k = 0; k < v.deps.length; k++) {
        const dep = v.deps[k];
        if (dep > t) break;
        const plan = planFor(v, r.id + '|' + di, k);
        if (dep + (plan ? plan.run : v.run) < t) continue;
        const key = r.id + '|' + di + '|' + k;
        active.add(key);
        const q = posAt(v, t - dep, plan);
        let e = pool.get(key);
        if (!e) {
          const mk = L.marker(pt(q[0], q[1]), {icon: busIcon(r.color, r.id), zIndexOffset: 600});
          mk.bindTooltip(r.label + ' · ' + fmtT(dep + (plan && plan.real ? plan.depDelay : 0)) + '发车（点击查看闪灯图）', {direction: 'top', offset: [0, -12]});
          mk.on('click', () => openFlash(key));
          mk.addTo(map);
          e = {mk}; pool.set(key, e);
        } else e.mk.setLatLng(pt(q[0], q[1]));
        const el = e.mk.getElement();
        if (el) el.querySelector('.busrot').style.transform = 'rotate(' + q[2].toFixed(1) + 'deg)';
      }
    });
  }
  for (const e of EXTRA_DEPS) {
    if (e.dep > t) continue;
    const plan = planFor(e.v, e.key, 0);
    if (e.dep + (plan ? plan.run : e.v.run) < t) continue;
    active.add(e.key);
    const q = posAt(e.v, t - e.dep, plan);
    const r = DATA.routes.find(x => x.id === e.rid);
    let en = pool.get(e.key);
    if (!en) {
      const mk = L.marker(pt(q[0], q[1]), {icon: busIcon(r.color, e.rid), zIndexOffset: 650});
      mk.bindTooltip(r.label + ' · 加车 ' + fmtT(e.dep) + '发车（点击查看闪灯图）', {direction: 'top', offset: [0, -12]});
      mk.on('click', () => openFlash(e.key));
      mk.addTo(map);
      en = {mk}; pool.set(e.key, en);
    } else en.mk.setLatLng(pt(q[0], q[1]));
    const el = en.mk.getElement();
    if (el) el.querySelector('.busrot').style.transform = 'rotate(' + q[2].toFixed(1) + 'deg)';
  }
  if (REAL && t - lastAuto > 2) { lastAuto = t; autoDispatch(t, active); }
  for (const [key, e] of pool) if (!active.has(key)) { map.removeLayer(e.mk); pool.delete(key); }
  document.getElementById('bcount').textContent = '运行 ' + active.size + ' 辆';
  const now = performance.now();
  if (livePopup && now - lastPop > 250) {
    livePopup.p.setContent(livePopup.i.html + nextArrivals(livePopup.i.nm, livePopup.i.st));
    lastPop = now;
  }
  if (now - lastBoard > 400) { renderBoard(); lastBoard = now; }
  if (flash && now - lastFlash > 200) { updateFlash(); lastFlash = now; }
  dirty = false;
}
let lastTs = performance.now();
function loop(now) {
  const dt = Math.min(0.1, (now - lastTs) / 1000);
  lastTs = now;
  if (SIM.playing) {
    SIM.t += dt * SIM.speed;
    if (SIM.t >= SCHED.end) { SIM.t = SCHED.end; SIM.playing = false; playBtn.textContent = playLabel(); }
    dirty = true;
  }
  if (dirty) renderSim();
  achTick(SIM.t);
  if (flash) placeFlashBus();
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

function dirDesc(st, rid, nm) {
  const r = DATA.routes.find(x => x.id === rid);
  const dis = st.routes[rid];
  if (dis.length === 2 && !r.oneway.includes(nm)) return '双向停靠';
  return '<span class="owtag">单向</span> 仅 ' +
    dis.map(i => r.id === 'Y33' ? (i === 0 ? '内圈' : '外圈') : '往' + r.dirs[i].to).join(' / ') + ' 方向';
}

// Uniform stop-dot sizing: one base radius for every stop (interchange or not),
// scaled by zoom so dots grow together as you zoom in.
const STOP_R = 3, STOP_W = 1.5;
function stopScale(z) { return Math.max(0.8, Math.min(4, Math.pow(1.2, z - 11))); }
// One-way stops are flagged by an amber fill inside the dot — no overlay glyph.
function paintStops() {
  const ow = document.getElementById('owmark').checked;
  stopLayer.eachLayer(m => {
    const amber = ow && m._ow;
    m.setStyle({fillColor: amber ? '#fbbf24' : '#f5f7ff', color: amber ? '#0d1226' : m._col});
  });
}
function build() {
  Object.values(routeLayers).forEach(g => map.removeLayer(g));
  map.removeLayer(stopLayer);
  stopLayer = L.layerGroup();
  for (const [nm, st] of Object.entries(DATA.stops)) {
    const rids = Object.keys(st.routes);
    const inter = rids.length >= 2;
    const owAny = rids.some(rid => DATA.routes.find(x => x.id === rid).oneway.includes(nm));
    const col = inter ? '#0d1226' : DATA.routes.find(x => x.id === rids[0]).color;
    const owAmber = owAny && document.getElementById('owmark').checked;
    const m = L.circleMarker(pt(st.lat, st.lng), {renderer: stopRenderer, radius: STOP_R * stopScale(map.getZoom()),
      fillColor: owAmber ? '#fbbf24' : '#f5f7ff', fillOpacity: 1, color: owAmber ? '#0d1226' : col, weight: STOP_W});
    m._inter = inter; m._ow = owAny; m._col = col;
    let html = '<div class="ptitle">' + nm + (owAny ? ' <span class="owtag">◆单向站</span>' : '') +
      ((SCHED.skipStops || []).some(x => x.name === nm) ? ' <span class="skiptag">时段飞站</span>' : '') + '</div>';
    for (const rid of rids) {
      const r = DATA.routes.find(x => x.id === rid);
      html += '<div class="prow"><b style="color:' + r.color + '">' + r.label + '</b> ' + dirDesc(st, rid, nm) + '</div>';
    }
    m._stopInfo = {nm, st, html};
    m.bindPopup(() => html + nextArrivals(nm, st), {autoPan: false});
    m.bindTooltip(nm, {direction: 'top', offset: [0, -4]});
    stopLayer.addLayer(m);
  }
  for (const r of DATA.routes) {
    const g = L.layerGroup();
    routeLayers[r.id] = g; dirLayers[r.id] = [];
    r.dirs.forEach((d, di) => {
      const lg = L.featureGroup();
      for (const p of d.paths) {
        lg.addLayer(L.polyline(p.map(q => pt(q[0], q[1])), {renderer, color: r.color, weight: 3, opacity: 0.85,
          dashArray: r.id.startsWith('SS') ? '7 5' : null}));
      }
      lg.bindPopup('<div class="ptitle" style="color:' + r.color + '">' + r.label + '</div>' + d.name +
        '<br>服务时间 ' + d.start + '–' + d.end + '<br>' + d.stops.length + ' 站', {autoPan: false});
      dirLayers[r.id].push(lg);
    });
    if (chipState[r.id] !== false) {
      g.addTo(map);
      dirLayers[r.id].forEach((lg, di) => { if (di === 0 || bothdir()) lg.addTo(g); });
    }
  }
  if (document.getElementById('stopmark').checked) stopLayer.addTo(map);
}
const bothdir = () => document.getElementById('bothdir').checked;

const chips = document.getElementById('chips');
for (const r of DATA.routes) {
  chipState[r.id] = true;
  const d0 = r.dirs[0];
  const ends = r.id === 'Y33' ? '鼎泰家园西门 环线' : d0.from + ' ⇌ ' + d0.to;
  const times = [...new Set(r.dirs.map(d => d.start === d.end ? d.start + '发车' : d.start + '–' + d.end))].join(' / ');
  const div = document.createElement('div');
  div.className = 'chip';
  div.innerHTML = '<input type="checkbox" checked data-r="' + r.id + '"><span class="sw" style="background:' + r.color + '"></span>' +
    '<span class="rt">' + r.label + '</span><span class="ends">' + ends + '</span>' +
    '<span class="tm">' + times + '</span>' +
    (r.oneway.length ? '<span class="ow">含' + r.oneway.length + '个单向站</span>' : '');
  const cb = div.querySelector('input');
  cb.onchange = () => {
    chipState[r.id] = cb.checked;
    const g = routeLayers[r.id];
    if (cb.checked) {
      g.addTo(map);
      dirLayers[r.id].forEach((lg, di) => { if (di === 0 || bothdir()) lg.addTo(g); });
    } else map.removeLayer(g);
    dirty = true;
  };
  div.onclick = e => {
    if (e.target.tagName === 'INPUT') return;
    const b = L.latLngBounds([]);
    r.dirs[0].stops.forEach(n => b.extend(pt(DATA.stops[n].lat, DATA.stops[n].lng)));
    map.fitBounds(b, {padding: [40, 40]});
  };
  chips.appendChild(div);
}
document.getElementById('bothdir').onchange = () => {
  for (const rid of Object.keys(routeLayers)) {
    const g = routeLayers[rid];
    dirLayers[rid].forEach((lg, di) => {
      if (di === 0) return;
      if (bothdir() && map.hasLayer(g)) lg.addTo(g); else g.removeLayer(lg);
    });
  }
};
document.getElementById('owmark').onchange = paintStops;
document.getElementById('stopmark').onchange = e => e.target.checked ? stopLayer.addTo(map) : map.removeLayer(stopLayer);
map.on('zoomend', () => {
  const r = STOP_R * stopScale(map.getZoom());
  stopLayer.eachLayer(m => { if (m.setRadius) m.setRadius(r); });
});
const darkfilter = document.getElementById('darkfilter');
const applyFilter = () => document.getElementById('map').classList.toggle('darktiles', darkfilter.checked && MODE === 'gcj');
darkfilter.onchange = applyFilter;
const setAll = v => { document.querySelectorAll('.chip input').forEach(i => { i.checked = v; i.onchange(); }); };
document.getElementById('all').onclick = () => setAll(true);
document.getElementById('none').onclick = () => setAll(false);
document.getElementById('ss').onclick = () => { document.querySelectorAll('.chip input').forEach(i => { i.checked = i.dataset.r.startsWith('SS'); i.onchange(); }); };
const allBounds = () => L.latLngBounds(Object.values(DATA.stops).map(s => pt(s.lat, s.lng)));
function homeView(){ if (isNarrow()) map.setView([32.06, 118.79], 12); else map.fitBounds(allBounds(), {padding: [30, 30]}); }
document.getElementById('fit').onclick = () => map.fitBounds(allBounds(), {padding: [30, 30]});
map.on('baselayerchange', e => {
  MODE = e.layer.options.coordMode;
  for (const [k, e2] of pool) map.removeLayer(e2.mk);
  pool.clear();
  dirty = true;
  build();
  applyFilter();
  homeView();
});
// ---------- hidden achievements (Steam-style easter egg) ----------
const ACH = [
  {id:'welcome', icon:'🌙', name:'欢迎来到南京夜班巴士模拟', desc:'首次打开页面'},
  {id:'realist', icon:'🌆', name:'脚踏实地', desc:'首次切换到现实模式'},
  {id:'holiday', icon:'🏮', name:'灯会人潮', desc:'切换到节假日客流日型'},
  {id:'godmode', icon:'🪄', name:'金手指上手', desc:'首次开启金手指调度台'},
  {id:'concert', icon:'🎤', name:'比歌声更快', desc:'在金手指模式下于奥体中心模拟演唱会散场'},
  {id:'full', icon:'🚇', name:'挤爆啦！', desc:'模拟拥挤程度达到 100%'},
  {id:'dispatcher', icon:'🚌', name:'调度有方', desc:'首次加开一班车'},
  {id:'nightowl', icon:'🦉', name:'深夜守望', desc:'模拟时间进入凌晨 02:00–04:00'},
  {id:'speedster', icon:'⚡', name:'时光飞逝', desc:'使用 120 分/秒快进'},
  {id:'marathon', icon:'🏁', name:'跑完全程', desc:'播放到收车窗口末端'}
];
const ACH_KEY='njbus_ach_v1';
let achGot={};
try{ const s=localStorage.getItem(ACH_KEY); if(s) achGot=JSON.parse(s)||{}; }catch(e){ achGot={}; }
function achSave(){ try{ localStorage.setItem(ACH_KEY, JSON.stringify(achGot)); }catch(e){} }
let toastTimer=null;
function showToast(msg){ const t=document.getElementById('toast'); if(!t)return; t.textContent=msg; t.hidden=false; if(toastTimer)clearTimeout(toastTimer); toastTimer=setTimeout(()=>{t.hidden=true;},2800); }
function unlock(id){
  if(achGot[id]) return;
  const a=ACH.find(x=>x.id===id); if(!a) return;
  achGot[id]=Date.now(); achSave();
  showToast('🏆 成就解锁：'+a.name);
  const ap=document.getElementById('achpage'); if(ap&&!ap.hidden) renderAch();
}
function renderAch(){
  const body=document.getElementById('achbody'); if(!body)return;
  let got=0;
  body.innerHTML=ACH.map(a=>{ const g=!!achGot[a.id]; if(g)got++;
    return '<div class="ach'+(g?' got':'')+'"><div class="ai">'+(g?a.icon:'🔒')+'</div><div class="an">'+a.name+'</div><div class="ad">'+a.desc+'</div>'+(g?'<div class="at">已解锁</div>':'')+'</div>';
  }).join('');
  const c=document.getElementById('achcount'); if(c)c.textContent=got+' / '+ACH.length+' 已解锁';
}
function openAch(){ renderAch(); const ap=document.getElementById('achpage'); if(ap)ap.hidden=false; }
function closeAch(){ const ap=document.getElementById('achpage'); if(ap)ap.hidden=true; }
document.getElementById('achclose').onclick=closeAch;
document.getElementById('achpage').addEventListener('click',e=>{ if(e.target.id==='achpage')closeAch(); });
function achTick(t){ if(t>=1560&&t<=1680)unlock('nightowl'); if(t>=SCHED.end-0.01)unlock('marathon'); }
// hidden entry: click the sidebar title 5× quickly, or Ctrl+Shift+A (hinted in 说明)
(function(){ const h=document.querySelector('#side h1'); if(!h)return; let n=0,last=0;
  h.addEventListener('click',()=>{ const now=Date.now(); if(now-last>1500)n=0; last=now; n++; if(n>=5){n=0;openAch();} });
  h.style.cursor='pointer';
})();

// ---------- god mode (金手指): event injection + extra dispatch ----------
let GOD=false, EVENT_SEQ=0, EXTRA_SEQ=0, armed=false, lastAuto=-1e9;
const autoDone=new Set();
const PRESETS={
  concert:{stop:'奥体中心西门',crowd:3000,time:'23:50',dur:70,radius:1500,label:'奥体演唱会'},
  sports:{stop:'奥体新城',crowd:5000,time:'00:10',dur:50,radius:1200,label:'体育赛事'},
  qingao:{stop:'邺城路·青奥村东',crowd:4000,time:'23:30',dur:60,radius:1400,label:'青奥演唱会'},
  festival:{stop:'天生桥大道东',crowd:8000,time:'22:00',dur:90,radius:1800,label:'咪豆音乐节'},
  lantern:{stop:'建康路·夫子庙',lat:32.0193,lng:118.7868,crowd:9000,time:'21:30',dur:90,radius:1800,label:'秦淮灯会·白鹭洲'},
  laomendong:{stop:'中华门城堡',crowd:6000,time:'21:00',dur:80,radius:1500,label:'老门东灯会'}
};
function toWgs(lat,lng){ if(MODE!=='gcj')return [lat,lng]; let a=lat,b=lng; for(let i=0;i<3;i++){const g=GCJ(a,b); a+=lat-g[0]; b+=lng-g[1];} return [a,b]; }
function distM(p,q){ const R=6371000,dLa=(q[0]-p[0])*Math.PI/180,dLo=(q[1]-p[1])*Math.PI/180,la=p[0]*Math.PI/180,lb=q[0]*Math.PI/180;
  const h=Math.sin(dLa/2)*Math.sin(dLa/2)+Math.cos(la)*Math.cos(lb)*Math.sin(dLo/2)*Math.sin(dLo/2); return 2*R*Math.asin(Math.min(1,Math.sqrt(h))); }
function parseClock(s){ const m=(s||'').trim().match(/^(\\d{1,2}):(\\d{2})/); if(!m)return null; let v=(+m[1])*60+(+m[2]); if(+m[1]<12)v+=1440; return v; }
function clockInput(m){ const h=Math.floor(m/60)%24, mm=Math.floor(m%60); return String(h).padStart(2,'0')+':'+String(mm).padStart(2,'0'); }
// Jump the manual 加车 form to the route/direction/stop just relieved, with departure
// defaulting to the current sim time (so the extra takes effect no later than now).
function focusGodRoute(rid,di,stopIdx,t){
  if(!groute)return;
  groute.value=rid; fillGodDirs();
  gdir.value=String(di); fillGodStops();
  gstop.value=String(stopIdx);
  const el=document.getElementById('gdeptime'); if(el)el.value=clockInput(t);
}
function setCursor(c){ try{ const mc=map.getContainer(); if(mc&&mc.style)mc.style.cursor=c; }catch(e){} }
const godbtn=document.getElementById('godbtn');
const godpanel=document.getElementById('godpanel');
function setGod(on){
  GOD=!!on&&REAL;
  godpanel.hidden=!GOD;
  godbtn.classList.toggle('on',GOD);
  if(GOD){ unlock('godmode'); fillGodRoutes(); renderEvents(); const el=document.getElementById('gdeptime'); if(el)el.value=clockInput(SIM.t); }
  else { armed=false; setCursor(''); }
  dirty=true;
}
godbtn.onclick=()=>{ if(godbtn.disabled)return; setGod(!GOD); };
document.getElementById('godclose').onclick=()=>setGod(false);
const gcrowd=document.getElementById('gcrowd'),gcrowdv=document.getElementById('gcrowdv');
const gdur=document.getElementById('gdur'),gdurv=document.getElementById('gdurv');
const gradius=document.getElementById('gradius'),gradiusv=document.getElementById('gradiusv');
gcrowd.oninput=()=>gcrowdv.textContent=gcrowd.value;
gdur.oninput=()=>gdurv.textContent=gdur.value;
gradius.oninput=()=>gradiusv.textContent=gradius.value;
function readParams(){ return {crowd:+gcrowd.value, tStart:parseClock(document.getElementById('gtime').value)||1350, dur:+gdur.value, radius:+gradius.value}; }
document.querySelectorAll('.gpresets button').forEach(b=>{
  b.onclick=()=>{ const p=PRESETS[b.dataset.preset]; if(!p)return;
    gcrowd.value=p.crowd; gcrowdv.textContent=p.crowd;
    document.getElementById('gtime').value=p.time;
    gdur.value=p.dur; gdurv.textContent=p.dur;
    gradius.value=p.radius; gradiusv.textContent=p.radius;
    const s=DATA.stops[p.stop]; const c=(p.lat!=null&&p.lng!=null)?[p.lat,p.lng]:(s?[s.lat,s.lng]:toWgs(32.06,118.79));
    createEvent(c[0],c[1],readParams(),b.dataset.preset);
  };
});
const gplace=document.getElementById('gplace'),ghint=document.getElementById('ghint');
gplace.onclick=()=>{ armed=!armed; gplace.classList.toggle('armed',armed);
  gplace.textContent=armed?'📍 点击地图放置…（再点取消）':'📍 点击地图放置活动';
  setCursor(armed?'crosshair':'');
  ghint.textContent=armed?'在地图上点击活动位置（场馆/散场点），客流自最近站点向周边扩散。':'选预设或调参后点「放置」，再点地图任意位置；客流自最近站点向周边数站扩散，并按线路分担（含换乘外溢）。';
};
map.on('click',e=>{ if(!armed||!GOD)return; const w=toWgs(e.latlng.lat,e.latlng.lng);
  createEvent(w[0],w[1],readParams(),null);
  armed=false; gplace.classList.remove('armed'); gplace.textContent='📍 点击地图放置活动'; setCursor('');
});
// Inject a crowd at (lat,lng): spread spatially to nearby stops (stopW, sum=1) and
// across every route serving each stop (routeShare, sum=1 per stop → transfer spillover).
// sched[nm][rid] caches the scheduled pass-times in the window so eventBoard can conserve
// the crowd across departures. Deterministic given the schedule + params.
function createEvent(lat,lng,p,preset){
  const ds=Object.keys(DATA.stops).map(nm=>[nm,distM([lat,lng],[DATA.stops[nm].lat,DATA.stops[nm].lng])]);
  ds.sort((a,b)=>a[1]-b[1]);
  let use=ds.filter(d=>d[1]<=p.radius); if(!use.length)use=[ds[0]];
  const stopW={}; let tot=0;
  for(const [nm,d] of use){ const w=Math.pow(Math.max(0.05,1-d/p.radius),2); stopW[nm]=w; tot+=w; }
  for(const nm in stopW) stopW[nm]/=tot;
  const routeShare={},sched={};
  for(const nm in stopW){
    const rids=Object.keys(DATA.stops[nm].routes);
    routeShare[nm]={}; sched[nm]={};
    let rt=0; const rw={};
    for(const rid of rids){ const arr=[];
      for(const di of DATA.stops[nm].routes[rid]){ const v=SCHED.dirs[rid+'|'+di]; if(!v)continue; const idx=stopIdx(rid,di,nm); if(idx<0)continue;
        for(let k=0;k<v.deps.length;k++){ const pass=v.deps[k]+v.stopT[idx]; if(pass>=p.tStart&&pass<=p.tStart+p.dur)arr.push(pass); } }
      sched[nm][rid]=arr; const w=capacity(rid)*(1+arr.length); rw[rid]=w; rt+=w;
    }
    for(const rid in rw) routeShare[nm][rid]=rt>0?rw[rid]/rt:0;
  }
  const ev={id:++EVENT_SEQ,crowd:p.crowd,tStart:p.tStart,dur:p.dur,radius:p.radius,lat,lng,stopW,routeShare,sched,
    preset:preset||null,label:(preset?PRESETS[preset].label:'自定义活动')+' · '+ds[0][0]};
  EVENTS.push(ev); EVENT_VER++; paxCache.clear();
  renderEvents(); dirty=true; renderSim(); renderBoard(); if(flash)updateFlash();
  if(preset==='concert')unlock('concert');
  showToast('🪄 已注入 '+p.crowd+' 人客流于 '+ds[0][0]+' 周边');
  return ev;
}
function renderEvents(){
  const box=document.getElementById('gevents'); if(!box)return;
  if(!EVENTS.length){ box.innerHTML='<span class="gempty">暂无活动</span>'; return; }
  box.innerHTML=EVENTS.map(ev=>'<div class="gev"><span>'+ev.label+' · '+ev.crowd+'人 · '+fmtT(ev.tStart)+'</span><button data-ev="'+ev.id+'" title="移除">✕</button></div>').join('');
  box.querySelectorAll('button[data-ev]').forEach(b=>b.onclick=()=>{ const id=+b.dataset.ev; EVENTS=EVENTS.filter(e=>e.id!==id); EVENT_VER++; paxCache.clear(); renderEvents(); dirty=true; renderSim(); renderBoard(); if(flash)updateFlash(); });
}
document.getElementById('gclear').onclick=()=>{ EVENTS=[]; EVENT_VER++; paxCache.clear(); autoDone.clear(); renderEvents(); dirty=true; renderSim(); renderBoard(); if(flash)updateFlash(); };
const groute=document.getElementById('groute'),gdir=document.getElementById('gdir'),gstop=document.getElementById('gstop');
function fillGodRoutes(){
  groute.innerHTML=DATA.routes.map(r=>'<option value="'+r.id+'">'+r.label+'</option>').join('');
  fillGodDirs();
}
function fillGodDirs(){
  const r=DATA.routes.find(x=>x.id===groute.value)||DATA.routes[0];
  gdir.innerHTML=r.dirs.map((d,di)=>'<option value="'+di+'">'+(r.id==='Y33'?(di===0?'内圈':'外圈'):d.from+'→'+d.to)+'</option>').join('');
  fillGodStops();
}
function fillGodStops(){
  const r=DATA.routes.find(x=>x.id===groute.value)||DATA.routes[0]; const di=+gdir.value||0;
  gstop.innerHTML=r.dirs[di].stops.map((s,i)=>'<option value="'+i+'">'+s+'</option>').join('');
}
groute.onchange=fillGodDirs; gdir.onchange=fillGodStops;
document.getElementById('gadd').onclick=()=>{
  if(!GOD)return;
  const rid=groute.value,di=+gdir.value,fromIdx=+gstop.value;
  const dep=parseClock(document.getElementById('gdeptime').value); if(dep==null){showToast('请输入有效发车时刻');return;}
  addExtra(rid,di,dep,fromIdx,null);
  showToast('🚌 已从 '+DATA.routes.find(x=>x.id===rid).dirs[di].stops[fromIdx]+' 加开一班车');
};
document.querySelectorAll('.gdepquick button').forEach(b=>{
  b.onclick=()=>{ const el=document.getElementById('gdeptime'); if(el)el.value=clockInput(SIM.t+(+b.dataset.off||0)); };
});
// Synthetic direction sliced to start at fromIdx. God mode starts at the crowded stop;
// realistic auto-dispatch starts at the origin and expresses (飞站) up to the crowded stop.
function makeExtraV(rid,di,fromIdx){
  const base=SCHED.dirs[rid+'|'+di];
  const off=base.stopT[fromIdx],km0=base.stopKm[fromIdx];
  const f=[];
  for(const fr of base.frames) if(fr[0]>=off-1e-9) f.push([+(fr[0]-off).toFixed(4),fr[1],fr[2],fr[3],+(fr[4]-km0).toFixed(4)]);
  if(!f.length){ const g=base.frames[base.frames.length-1]; f.push([0,g[1],g[2],g[3],0]); }
  if(f[0][0]>1e-6) f.unshift([0,f[0][1],f[0][2],f[0][3],0]);
  const names=DATA.routes.find(x=>x.id===rid).dirs[di].stops.slice(fromIdx);
  return {frames:f,stopT:base.stopT.slice(fromIdx).map(s=>+(s-off).toFixed(4)),stopKm:base.stopKm.slice(fromIdx).map(s=>+(s-km0).toFixed(4)),deps:[0],run:+(base.run-off).toFixed(4),skip:[],names};
}
function addExtra(rid,di,dep,fromIdx,expressTo){
  if(EXTRA_DEPS.length>=24){ showToast('加车数量已达上限'); return null; }
  const v=makeExtraV(rid,di,fromIdx);
  if(expressTo!=null&&expressTo>fromIdx){ for(let i=fromIdx;i<expressTo;i++) v.skip.push({i:i-fromIdx,from:-1e9,to:1e9}); }
  const id=++EXTRA_SEQ, key=rid+'|'+di+'|x'+id;
  v.deps=[dep];
  const e={id,rid,di,dep,fromIdx,key,v,expressTo:expressTo==null?null:expressTo};
  EXTRA_DEPS.push(e); paxCache.clear();
  unlock('dispatcher');
  dirty=true; renderSim(); renderBoard(); if(flash)updateFlash();
  return e;
}
// Realistic auto-dispatch: a scheduled bus >=90% full triggers an express extra from the
// origin that skips up to the crowded stop. Only fires under heavy crowding (injected
// events), never in plain sparse night service. One extra per source departure.
function autoDispatch(t,active){
  if(EXTRA_DEPS.length>=24)return;
  const thr=GOD?0.75:0.90;
  for(const key of active){
    if(key.indexOf('|x')>=0||autoDone.has(key))continue;
    const parts=key.split('|'),rid=parts[0],di=+parts[1],k=+parts[2];
    const v=SCHED.dirs[rid+'|'+di]; if(!v)continue;
    const plan=planFor(v,rid+'|'+di,k); if(!plan||!plan.real)continue;
    const el=t-v.deps[k]; if(el<0)continue;
    const pax=paxPlan(v,rid+'|'+di,k,plan);
    const occ=occAt(v,plan,pax,el);
    if(occ/pax.cap>=thr){
      const st=plan.st; let i=0; while(i<st.length-1&&st[i+1]<=el)i++;
      if(i>0){
        if(GOD){ addExtra(rid,di,+t.toFixed(2),i,null); focusGodRoute(rid,di,i,t); }
        else { addExtra(rid,di,+(t+1).toFixed(2),0,i); }
        autoDone.add(key);
      }
    }
  }
}
unlock('welcome');

build();
applyFilter();
homeView();
renderBoard();
</script>
</body></html>'''
def fmt_min(m):
    m = int(round(m))
    pre = '次日' if m >= 1440 else ''
    return f'{pre}{m // 60 % 24:02d}:{m % 60:02d}'
mdl = sched.get('model', {'v_reg': 24, 'v_art': 33, 'v_fast': 60, 'turn_pen': 0.1, 'dwell': 0.6})
html = (html.replace('__PAYLOAD__', js).replace('__SCHED__', sched_js)
        .replace('__METRO_STATIONS__', metro_stations_js).replace('__METRO_HOURS__', metro_hours_js)
        .replace('__GAUGE__', gauge_svg()).replace('__GLEN__', f'{GLEN:.2f}')
        .replace('__NROUTES__', str(nroutes)).replace('__NSTOPS__', str(nstops))
        .replace('__SUBNOTE__', sub_note)
        .replace('__SIMSTART__', fmt_min(sched['start']))
        .replace('__SIMEND__', fmt_min(sched['end']))
        .replace('__VR__', f"{mdl['v_reg']:.0f}").replace('__VF__', f"{mdl['v_fast']:.0f}")
        .replace('__VA__', f"{mdl.get('v_art', 33):.0f}")
        .replace('__DWELL__', f"{mdl['dwell']:.2f}").replace('__TP__', f"{mdl['turn_pen']:.2f}"))
open(os.path.join(ROOT, 'realmap.html'), 'w', encoding='utf-8').write(html)
print('realmap.html written,', len(html) // 1024, 'KB')