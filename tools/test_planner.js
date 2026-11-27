// Headless verification of planner.html — runs BOTH inline scripts (engine + planner)
// in one shared vm context, then exercises the DOM-free __planner.planOD search.
// The crux: a planned ride's board/alight times must equal the engine's own
// arrival matrix (deps[k] + plan.st[i]), i.e. the planner never invents timings.
const fs = require('fs'), vm = require('vm');

const html = fs.readFileSync('D:/nj_night_bus/planner.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('FAIL:', m); } };
ok(scripts.length === 2, 'planner.html has 2 script blocks, got ' + scripts.length);
const src = scripts.join('\n;\n');

function makeEl(id) {
  const cls = new Set();
  return {
    id, checked: false, value: '', textContent: '', innerHTML: '', className: '', style: {},
    dataset: {}, attrs: {}, children: [], hidden: false,
    classList: { toggle(c, f) { const on = f === undefined ? !cls.has(c) : f; on ? cls.add(c) : cls.delete(c); return on; }, add(c) { cls.add(c); }, remove(c) { cls.delete(c); }, contains(c) { return cls.has(c); } },
    listeners: {}, addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    appendChild(c) { this.children.push(c); return c; },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 132, height: 92 }; },
    setPointerCapture() {}, releasePointerCapture() {}, closest() { return null; }, contains() { return false; },
    querySelector() { return makeEl(id + '>q'); }, querySelectorAll() { return []; },
    onclick: null, onchange: null, oninput: null, onkeydown: null,
  };
}
const byId = {};
const documentMock = {
  body: makeEl('body'), addEventListener() {},
  getElementById(id) { return byId[id] || (byId[id] = makeEl(id)); },
  createElement(t) { return makeEl('<' + t + '>'); },
  querySelector(s) { return byId['q>' + s] || (byId['q>' + s] = makeEl('q>' + s)); },
  querySelectorAll() { return []; },
};
const lsStore = {};
function autoMock(name) {
  const store = {}; const f = function () { return proxy; };
  const proxy = new Proxy(f, {
    get(t, k) { if (k === Symbol.toPrimitive) return () => name; if (k === 'then') return undefined; if (!(k in store)) store[k] = autoMock(name + '.' + String(k)); return store[k]; },
    apply() { return proxy; }, set(t, k, v) { store[k] = v; return true; },
  });
  return proxy;
}
let tsNow = 1000;
const ctx = vm.createContext({
  document: documentMock,
  window: { _l: {}, addEventListener(t, f) { (this._l[t] = this._l[t] || []).push(f); }, innerWidth: 1400, innerHeight: 900, devicePixelRatio: 1 },
  L: autoMock('L'), performance: { now: () => tsNow }, requestAnimationFrame: () => 0,
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0,
  localStorage: { getItem(k) { return k in lsStore ? lsStore[k] : null; }, setItem(k, v) { lsStore[k] = String(v); }, removeItem(k) { delete lsStore[k]; } },
  indexedDB: undefined, URL: { createObjectURL: () => 'blob:x', revokeObjectURL() {} },
  fetch: () => Promise.reject(new Error('no net')), navigator: { userAgent: 'node' }, console,
});
vm.runInContext(src + '\n;globalThis.__eng={DATA,SCHED,REAL,planFor,posAt,paxPlan,distM,fmtT};', ctx, { timeout: 60000 });
const P = ctx.__planner;
ok(!!P, '__planner hook exported');
if (!P) { console.log(`\n${pass} passed, ${fail} failed`); process.exit(1); }
const DATA = P.DATA, SCHED = P.SCHED;

// 1. realistic mode active
ok(P.REAL === true, 'planner forces REAL=true on load, got ' + P.REAL);
P.setReal(true); P.clearArrCache();

// 2. arrival matrix matches the engine (deps[k] + plan.st[i], null when skipped)
const someKey = Object.keys(SCHED.dirs)[0];
const [srid, sdi] = [someKey.split('|')[0], +someKey.split('|')[1]];
const M = P.arrMat(srid, sdi);
const v = SCHED.dirs[someKey];
ok(Array.isArray(M) && M.length === v.deps.length, 'arrMat rows == deps count');
let amBad = 0, amSkip = 0, amMono = 0;
for (let k = 0; k < M.length; k++) {
  const pl = P.planFor(v, someKey, k);
  if (M[k].length !== pl.st.length) amBad++;
  let prevA = -1;
  for (let i = 0; i < pl.st.length; i++) {
    const expect = pl.sk && pl.sk[i] ? null : v.deps[k] + pl.st[i];
    if (M[k][i] === null) { amSkip++; if (expect !== null) amBad++; }
    else if (Math.abs(M[k][i] - expect) > 1e-6) amBad++;
    else { if (M[k][i] < prevA - 1e-6) amMono++; prevA = M[k][i]; }
  }
}
ok(amBad === 0, 'arrMat cells == deps[k]+st[i] (bad=' + amBad + ')');
ok(amMono === 0, 'arrMat times monotonic per departure (bad=' + amMono + ')');

// 3. walk-neighbour index: sorted, bounded by radius, straight-line/4.5kmh
const wn = P.buildWalk();
ok(wn && typeof wn.get === 'function' && wn.size === Object.keys(DATA.stops).length, 'walk index covers all stops (' + (wn && wn.size) + ')');
const dense = Object.keys(DATA.stops).find(nm => (wn.get(nm) || []).length > 0);
const wl = P.walkList(dense, 15);
let wlSorted = true, wlBound = true;
for (let i = 1; i < wl.length; i++) if (wl[i][1] < wl[i - 1][1] - 1e-9) wlSorted = false;
for (const e of wl) { if (e[1] > 15 + 1e-6) wlBound = false; if (Math.abs(e[2] - e[1] * P.WALK_MPM) > 1e-3) wlBound = false; }
ok(wlSorted, 'walkList sorted by minutes ascending');
ok(wlBound, 'walkList within maxWalkMin and dm==wm*WALK_MPM');

// helpers to validate any itinerary's internal consistency vs the engine
function legsToString(it) { return it.legs.map(l => l.type === 'ride' ? (l.rid + '|' + l.di + ' ' + l.from + '>' + l.to) : ('walk ' + l.from + '>' + l.to)).join(' , '); }
function validate(it, O, D, T0, opt) {
  let bad = [];
  if (!(it.total > 0)) bad.push('total<=0');
  if (Math.abs(it.total - (it.end - it.start)) > 1e-6) bad.push('total!=end-start');
  if (Math.abs(it.start - T0) > 1e-6) bad.push('start!=T0');
  if (it.fare !== 2 * it.rides) bad.push('fare!=2*rides');
  if (it.transfers !== Math.max(0, it.rides - 1)) bad.push('transfers!=rides-1');
  if (it.legs[0].from !== O) bad.push('first leg not from O');
  if (it.legs[it.legs.length - 1].to !== D) bad.push('last leg not to D');
  let prevArr = T0, rides = 0, walkM = 0, walkT = 0, prevType = null;
  const allow = opt.gamble ? opt.gambleMin : 0;
  for (const lg of it.legs) {
    if (lg.type === 'walk' && prevType === 'walk') bad.push('consecutive walk legs (chain)');
    prevType = lg.type;
    if (lg.type === 'walk') {
      const a = P.stC(lg.from), b = P.stC(lg.to);
      if (Math.abs(lg.dm - P.distM(a, b)) > 1.0) bad.push('walk dm!=dist');
      if (Math.abs(lg.wm - lg.dm / P.WALK_MPM) > 1e-6) bad.push('walk wm!=dm/mpm');
      if (lg.dep < prevArr - 1e-6) bad.push('walk dep<prevArr (teleport)');
      if (Math.abs(lg.arr - (lg.dep + lg.wm)) > 1e-6) bad.push('walk arr!=dep+wm');
      if (lg.wm > opt.maxWalkMin + 1e-6) bad.push('walk exceeds maxWalkMin');
      walkM += lg.dm; walkT += lg.wm; prevArr = lg.arr;
    } else {
      rides++;
      const stops = P.dirStops(lg.rid, lg.di), MM = P.arrMat(lg.rid, lg.di);
      if (!MM) { bad.push('no arrMat'); continue; }
      if (stops[lg.fromIdx] !== lg.from || stops[lg.toIdx] !== lg.to) bad.push('ride idx/name mismatch');
      if (lg.toIdx <= lg.fromIdx) bad.push('ride not downstream');
      if (Math.abs(MM[lg.k][lg.fromIdx] - lg.board) > 1e-6) bad.push('board!=arrMat');
      if (Math.abs(MM[lg.k][lg.toIdx] - lg.alight) > 1e-6) bad.push('alight!=arrMat');
      if (lg.board < prevArr - allow - 1e-6) bad.push('board before arrival (teleport)');
      if (lg.alight <= lg.board) bad.push('alight<=board');
      if (!(lg.ratio >= 0 && lg.ratio < 1.6) || !(lg.cap > 0) || !(lg.occ >= 0)) bad.push('crowd out of range');
      prevArr = lg.alight;
    }
  }
  if (rides !== it.rides) bad.push('rides count');
  if (Math.abs(walkM - it.walkM) > 1e-3 || Math.abs(walkT - it.walkT) > 1e-6) bad.push('walk totals');
  return bad;
}

// 4. direct options on a known same-line pair
const r0 = DATA.routes[0];
const d0stops = r0.dirs[0].stops;
const O1 = d0stops[1], D1 = d0stops[Math.min(6, d0stops.length - 1)];
const T0 = P.parseClock('23:00');
const opt = P.defOpt();
const direct = P.directOptions(O1, D1, T0, opt);
ok(direct.length >= 1, 'directOptions finds a same-line trip ' + O1 + '>' + D1 + ' got ' + direct.length);
if (direct.length) {
  const it = direct[0];
  ok(it.rides === 1 && it.transfers === 0 && it.tag === 'direct', 'direct trip is 1 ride 0 transfers');
  const bad = validate(it, O1, D1, T0, opt);
  ok(bad.length === 0, 'direct trip consistent: ' + bad.join('; ') + ' [' + legsToString(it) + ']');
  ok(it.legs[0].board >= T0 + P.BOARD_BUF - 1e-6, 'direct board >= T0+buf');
}

// 5. full planOD across several OD pairs — invariants on every returned itinerary
const pairs = [];
for (let a = 0; a < DATA.routes.length && pairs.length < 8; a += 5) {
  const ra = DATA.routes[a], rb = DATA.routes[(a + 7) % DATA.routes.length];
  const O = ra.dirs[0].stops[1], D = rb.dirs[0].stops[Math.min(4, rb.dirs[0].stops.length - 1)];
  if (O && D && O !== D) pairs.push([O, D]);
}
let seenDirect = 0, seenTransfer = 0, seenWalkLeg = 0, seenLast = 0, totalIt = 0, allBad = [];
for (const [O, D] of pairs) {
  const list = P.planOD(O, D, T0, opt);
  // sorted by end ascending (pref 'fast')
  for (let i = 1; i < list.length; i++) if (list[i].end < list[i - 1].end - 1e-6) allBad.push('not sorted ' + O + '>' + D);
  // no duplicate signatures
  const sigs = new Set(); for (const it of list) { if (sigs.has(it.sig)) allBad.push('dup sig'); sigs.add(it.sig); }
  for (const it of list.slice(0, 6)) {
    totalIt++;
    const bad = validate(it, O, D, T0, opt);
    if (bad.length) allBad.push(O + '>' + D + ': ' + bad.join(','));
    if (it.transfers === 0) seenDirect++;
    if (it.transfers >= 1) seenTransfer++;
    if (it.legs.some(l => l.type === 'walk')) seenWalkLeg++;
    if (it.flags.includes('lastbus')) seenLast++;
  }
}
ok(allBad.length === 0, 'all planOD itineraries engine-consistent (' + totalIt + ' checked): ' + allBad.slice(0, 4).join(' | '));
ok(totalIt > 0, 'planOD produced itineraries, got ' + totalIt);
ok(seenDirect > 0, 'saw at least one direct itinerary (' + seenDirect + ')');
ok(seenTransfer > 0, 'saw at least one transfer itinerary (' + seenTransfer + ')');

// 6. threshold enforcement: tiny maxTotal yields nothing beyond it
const tight = P.defOpt({ maxTotal: 5 });
let over = 0;
for (const [O, D] of pairs) for (const it of P.planOD(O, D, T0, tight)) if (it.total > 5 + 1e-6) over++;
ok(over === 0, 'maxTotal respected (violations=' + over + ')');

// 7. walk legs honour maxWalkMin
let walkOver = 0;
for (const [O, D] of pairs) for (const it of P.planOD(O, D, T0, opt)) for (const l of it.legs) if (l.type === 'walk' && l.wm > opt.maxWalkMin + 1e-6) walkOver++;
ok(walkOver === 0, 'no walk leg exceeds maxWalkMin (violations=' + walkOver + ')');

// 8. transfer waits (waits[1..]) never exceed maxTransferWait; initial wait is capped only by maxTotal
let waitOver = 0, initOver = 0;
for (const [O, D] of pairs) for (const it of P.planOD(O, D, T0, opt)) {
  for (const w of it.waits.slice(1)) if (w > opt.maxTransferWait + 1e-6) waitOver++;
  if (it.waits.length && it.waits[0] > opt.maxTotal + 1e-6) initOver++;
}
ok(waitOver === 0, 'no transfer wait exceeds maxTransferWait (violations=' + waitOver + ')');
ok(initOver === 0, 'initial wait within maxTotal (violations=' + initOver + ')');

// 9. gamble: negative waits only appear when gamble enabled, and are flagged
const noG = P.defOpt({ gamble: false });
let negNoG = 0;
for (const [O, D] of pairs) for (const it of P.planOD(O, D, T0, noG)) for (const w of it.waits) if (w < -1e-6) negNoG++;
ok(negNoG === 0, 'no negative (gamble) waits when gamble disabled, got ' + negNoG);
const gOpt = P.defOpt({ gamble: true, gambleMin: 4 });
let negFlagBad = 0, negSeen = 0;
for (const [O, D] of pairs) for (const it of P.planOD(O, D, T0, gOpt)) {
  const hasNeg = it.waits.some(w => w < -1e-6);
  if (hasNeg) { negSeen++; if (!it.flags.includes('gamble')) negFlagBad++; if (it.waits.some(w => w < -gOpt.gambleMin - 1e-6)) negFlagBad++; }
}
ok(negFlagBad === 0, 'negative waits flagged "gamble" and within gambleMin (bad=' + negFlagBad + ')');

// 10. dijkstra returns a valid O->D chain or null
let djOk = true, djFound = 0;
for (const [O, D] of pairs) {
  const it = P.dijkstra(O, D, T0, opt);
  if (it) { djFound++; const bad = validate(it, O, D, T0, opt); if (bad.length) djOk = false; }
}
ok(djOk, 'dijkstra itineraries consistent');

// 11. last-bus flag correctness via mkItin on a real final departure
const lk = Object.keys(SCHED.dirs).find(k => SCHED.dirs[k].deps.length >= 2);
const lv = SCHED.dirs[lk], lastK = lv.deps.length - 1;
const [lrid, ldi] = [lk.split('|')[0], +lk.split('|')[1]];
const ls = P.dirStops(lrid, ldi), LM = P.arrMat(lrid, ldi);
if (LM && LM[lastK][0] != null && LM[lastK][ls.length - 1] != null) {
  const synth = P.mkItin([{ type: 'ride', rid: lrid, di: ldi, k: lastK, fromIdx: 0, toIdx: ls.length - 1, from: ls[0], to: ls[ls.length - 1], board: LM[lastK][0], alight: LM[lastK][ls.length - 1] }], LM[lastK][0] - 1, 'x');
  ok(synth.flags.includes('lastbus'), 'final departure flagged lastbus');
} else ok(true, 'lastbus synth skipped (no clean final departure)');

// 12. dedupSort ordering by preference key
const prefFirst = P.defOpt({ pref: 'first' });
let firstOrdOk = true;
for (const [O, D] of pairs) {
  const list = P.planOD(O, D, T0, prefFirst);
  for (let i = 1; i < list.length; i++) {
    const ka = list[i - 1].tIdx * 60 + list[i - 1].end, kb = list[i].tIdx * 60 + list[i].end;
    if (kb < ka - 1e-6) firstOrdOk = false;
  }
}
ok(firstOrdOk, 'pref=first sorts by (tIdx*60+end) ascending');

// 13. day-type switch clears cache and stays consistent
P.setDayType('weekend'); P.clearArrCache();
let dtBad = 0;
for (const [O, D] of pairs.slice(0, 3)) for (const it of P.planOD(O, D, T0, opt).slice(0, 3)) { const bad = validate(it, O, D, T0, opt); if (bad.length) dtBad++; }
ok(dtBad === 0, 'weekend day-type itineraries still engine-consistent (bad=' + dtBad + ')');
ok(P.DAYTYPE === 'weekend', 'setDayType reflected, got ' + P.DAYTYPE);

// 14. UI: instant custom autocomplete replaces the laggy native datalist; map pick-point buttons
ok(html.indexOf('function acMatch') >= 0, 'custom autocomplete acMatch present (matches on 1st char)');
ok(html.indexOf("acBox.id='plac'") >= 0, 'autocomplete dropdown element #plac created');
ok(html.indexOf('list="plstops"') < 0 && html.indexOf('<datalist id=') < 0, 'native datalist removed from the station inputs');
ok(html.indexOf('compositionend') >= 0 && html.indexOf('isComposing') >= 0, 'autocomplete is IME-aware (compositionend + isComposing guard)');
ok(html.indexOf('id="pickfrom"') >= 0 && html.indexOf('id="pickto"') >= 0, 'map pick-point buttons for origin & destination');
ok(html.indexOf('function nearestStop') >= 0 && html.indexOf("map.on('click'") >= 0, 'pick snaps to nearest stop on map click');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
