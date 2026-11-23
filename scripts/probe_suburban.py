# -*- coding: utf-8 -*-
"""Probe Baidu for 溧水/高淳 night bus lines (suburban districts)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import fetch_baidu as fb

queries = ['溧水Y1路', '溧水Y2路', '溧水Y3路', '溧水Y5路',
           '溧水101路', '溧水102路', '溧水103路', '溧水105路', '溧水106路',
           '高淳801路', '高淳802路', '溧水夜间公交', '高淳夜间公交', '高淳夜班']
out = {}
for q in queries:
    d = fb.search(q)
    time.sleep(0.3)
    items = [it for it in (d or {}).get('content', []) if fb.is_busline(it)]
    names = [(it.get('name', ''), it['uid']) for it in items]
    print(q, '->', [n for n, _ in names], flush=True)
    for it in items:
        out[it['uid']] = it
json.dump(out, open(os.path.join(fb.DATA, 'suburban_search.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('total unique busline uids:', len(out), flush=True)