// Headless verification of realmap.html inline script (DOM/Leaflet auto-mocks).
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync('D:/nj_night_bus/data/_check_realmap.js', 'utf8');

function makeEl(id) {
  const cls = new Set();
  const el = {
    id, checked: true, value: '', textContent: '', innerHTML: '', className: '',
    style: {}, dataset: {}, attrs: {}, min: 0, max: 0, step: 0, children: [], hidden: false,
    classList: {
      toggle(c, f) { const on = f === undefined ? !cls.has(c) : f; on ? cls.add(c) : cls.delete(c); return on; },
      add(c) { cls.add(c); }, remove(c) { cls.delete(c); }, contains(c) { return cls.has(c); },
    },
    listeners: {},
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    appendChild(c) { this.children.push(c); return c; },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k]; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 132, height: 92 }; },
    setPointerCapture() {}, releasePointerCapture() {},
    closest() { return null; }, contains() { return false; },
    querySelector(sel) {
      if (sel === 'input' && this.innerHTML.includes('<input')) {
        if (!this._input) {
          this._input = makeEl(this.id + '>input');
          const m = this.innerHTML.match(/data-r="([^"]+)"/);
          if (m) this._input.dataset.r = m[1];
        }
        return this._input;
      }
      return this._q || (this._q = makeEl(this.id + '>' + sel));
    },
    querySelectorAll() { return []; },
    onclick: null, onchange: null, oninput: null, onkeydown: null,
  };
  return el;
}
const byId = {}, created = [];
const presetBtns = ['concert', 'sports', 'qingao', 'festival', 'lantern', 'laomendong'].map(p => { const e = makeEl('preset>' + p); e.dataset.preset = p; return e; });
const documentMock = {
  body: makeEl('body'),
  addEventListener() {},
  getElementById(id) { return byId[id] || (byId[id] = makeEl(id)); },
  createElement(tag) { const el = makeEl('<' + tag + '#' + created.length + '>'); created.push(el); return el; },
  querySelector(sel) { return byId['q>' + sel] || (byId['q>' + sel] = makeEl('q>' + sel)); },
  querySelectorAll(sel) {
    if (sel === '.chip input') return created.filter(e => e.className === 'chip').map(d => d.querySelector('input'));
    if (sel === '.gpresets button') return presetBtns;
    return [];
  },
};
const lsStore = {};
const localStorageMock = { getItem(k) { return k in lsStore ? lsStore[k] : null; }, setItem(k, v) { lsStore[k] = String(v); }, removeItem(k) { delete lsStore[k]; } };
function autoMock(name) {
  const store = {};
  const f = function () { return proxy; };
  const proxy = new Proxy(f, {
    get(t, k) {
      if (k === Symbol.toPrimitive) return () => name;
      if (k === 'then') return undefined;
      if (!(k in store)) store[k] = autoMock(name + '.' + String(k));
      return store[k];
    },
    apply() { return proxy; },
    set(t, k, v) { store[k] = v; return true; },
  });
  return proxy;
}
let tsNow = 1000, rafCb = null;
const ctx = vm.createContext({
  document: documentMock,
  window: { _l: {}, addEventListener(t, f) { (this._l[t] = this._l[t] || []).push(f); }, innerWidth: 1400, innerHeight: 900 },
  L: autoMock('L'),
  performance: { now: () => tsNow },
  requestAnimationFrame: cb => { rafCb = cb; },
  setTimeout: () => 0,
  clearTimeout: () => {},
  localStorage: localStorageMock,
  console,
});
vm.runInContext(src + '\n;globalThis.__test={SIM,SCHED,DATA,posAt,renderSim,doJump,fmtT,fmtSpeed,fmtWait,nextArrivals,chipState,pool,playBtn,scrub,loop,ORDER,' +
  'setSpeed,gaugePick,GEARS,gneedle,gfill,speedval,setSpeedPanel,busState,renderBoard,bbody,openFlash,updateFlash,closeFlash,' +
  'get livePopup(){return livePopup}, set livePopup(v){livePopup=v}, get flash(){return flash}, get gearIdx(){return gearIdx}, depPlan, FSP,' +
  'placeFlashBus, flashGeom, openHelp, closeHelp, helpSearch, stopScale, paintStops, STOP_R, STOP_W,' +
  'get REAL(){return REAL}, setReal, planFor, buildReal, posReal, REAL_CFG, dirLights, peakW, hashStr, mulberry32,' +
  'isNarrow, playLabel, speedLabel, modeLabel, fsLabel, fsActive, refreshBarLabels, applyNarrowBoard,' +
  'routeW, isHub, todW, ROUTE_W, nodeType, nodeMul, nodeGate, NODE_GATE_PTS,' +
  'metroAdj, metroW, dayMul, dayClass, DAY_MUL, DAY_CLASS, METRO_STATIONS, METRO_HOURS, setFlowModel, flowLoad,' +
  'setDayType, dayLabel, daybtn, modebtn, get DAYTYPE(){return DAYTYPE}, set DAYTYPE(v){DAYTYPE=v},' +
  'capacity, crowdTier, crowdColor, demandLoad, alightProb, paxPlan, occAt, PAX_BOARD, CAP_DEFAULT, CAP_OVERRIDE,' +
  'eventBoard, curveAt, stopIdx, extraPassTimes, setODModel, odFlow, godSig,' +
  'get EVENTS(){return EVENTS}, get EXTRA_DEPS(){return EXTRA_DEPS}, get EVENT_VER(){return EVENT_VER},' +
  'ACH, unlock, get achGot(){return achGot}, openAch, closeAch, renderAch, showToast, achTick,' +
  'get GOD(){return GOD}, setGod, godbtn, PRESETS, createEvent, addExtra, makeExtraV, autoDispatch, renderEvents,' +
  'toWgs, distM, parseClock, clockInput, focusGodRoute, fillGodRoutes, fillGodDirs, fillGodStops, groute, gdir, gstop};',
  ctx, { timeout: 30000 });
const T = ctx.__test || (ctx.globalThis && ctx.globalThis.__test);
let pass = 0, fail = 0;
const ok = (cond, msg) => { if (cond) { pass++; } else { fail++; console.log('FAIL:', msg); } };
// Capture the as-loaded defaults before any later section mutates SIM.speed / gearIdx.
const __initSpeed = T.SIM.speed, __initGear = T.gearIdx;

// 1. sidebar chips
const nRoutes = T.DATA.routes.length;
const chips = created.filter(e => e.className === 'chip');
ok(chips.length === nRoutes && nRoutes === 43, '43 chips, got ' + chips.length);
let sameEnds = 0;
for (const c of chips) {
  const m = c.innerHTML.match(/<span class="ends">([^<]+)<\/span>/);
  if (!m) { sameEnds++; continue; }
  const parts = m[1].split(' ⇌ ');
  if (parts.length === 2 && parts[0] === parts[1]) sameEnds++;
}
ok(sameEnds === 0, 'no chip shows identical endpoints');

// 2. schedule integrity (incl. new km fields)
const dirs = Object.keys(T.SCHED.dirs);
ok(dirs.length === 86, '86 dirs, got ' + dirs.length);
let badMono = 0, badStopT = 0, badKm = 0;
for (const k of dirs) {
  const v = T.SCHED.dirs[k];
  for (let i = 1; i < v.frames.length; i++) {
    if (v.frames[i][0] < v.frames[i - 1][0]) badMono++;
    if (v.frames[i].length !== 5) badKm++;
  }
  if (!v.stopKm || v.stopKm.length !== v.stopT.length) badKm++;
  const rid = k.split('|')[0], di = +k.split('|')[1];
  const r = T.DATA.routes.find(x => x.id === rid);
  if (v.stopT.length !== r.dirs[di].stops.length) badStopT++;
  for (let i = 1; i < v.stopT.length; i++) if (v.stopT[i] - v.stopT[i - 1] < 0.3) badStopT++;
}
ok(badMono === 0, 'frames monotonic, violations ' + badMono);
ok(badStopT === 0, 'stopT lengths/gaps valid, violations ' + badStopT);
ok(badKm === 0, 'frames carry km + stopKm present, violations ' + badKm);
ok(T.SCHED.model && T.SCHED.model.v_reg <= 40 && T.SCHED.model.v_fast <= 70, 'model within limits');
// posAt km matches stopKm at stop arrivals
let kmErr = 0;
for (const k of ['Y1|0', 'LSY2|0', 'GC803|0']) {
  const v = T.SCHED.dirs[k];
  for (let i = 0; i < v.stopT.length; i++)
    if (Math.abs(T.posAt(v, v.stopT[i] + 0.01)[3] - v.stopKm[i]) > 0.02) kmErr++;
}
ok(kmErr === 0, 'posAt km aligns with stopKm, violations ' + kmErr);

// 3. active bus counts (skip-aware run times)
const countAt = t => {
  let n = 0;
  for (const [key, v] of Object.entries(T.SCHED.dirs))
    for (let k = 0; k < v.deps.length; k++) {
      const p = T.depPlan(v, key, k);
      if (v.deps[k] <= t && v.deps[k] + (p ? p.run : v.run) >= t) n++;
    }
  return n;
};
for (const t of [T.SCHED.start, 1200, 1340, 1470, 1560, T.SCHED.end]) {
  T.SIM.t = t; T.renderSim();
  ok(T.pool.size === countAt(t), `active@${t}: pool=${T.pool.size} expected=${countAt(t)}`);
}

// 4. posAt dwell plateaus + terminal
let badPos = 0;
for (const k of ['Y1|0', 'Y32|0', 'SS1|0', 'Y33|0', 'LSY2|0', 'GC803|0']) {
  const v = T.SCHED.dirs[k];
  for (let i = 0; i < v.stopT.length; i++) {
    const a = T.posAt(v, v.stopT[i] + 0.05), b = T.posAt(v, v.stopT[i] + 0.25);
    if (Math.abs(a[0] - b[0]) > 1e-6 || Math.abs(a[1] - b[1]) > 1e-6) badPos++;
  }
  const end = T.posAt(v, v.run), lf = v.frames[v.frames.length - 1];
  if (Math.abs(end[0] - lf[1]) > 1e-6 || Math.abs(end[1] - lf[2]) > 1e-6) badPos++;
}
ok(badPos === 0, 'posAt dwell plateaus + terminal position');

// 5. jumps
byId['tinput'].value = '00:30'; T.doJump(); ok(T.SIM.t === 1470, 'jump 00:30 -> 1470');
byId['tinput'].value = '22:20'; T.doJump(); ok(T.SIM.t === 1340, 'jump 22:20 -> 1340');
byId['tinput'].value = '09:00'; T.doJump(); ok(T.SIM.t === T.SCHED.end, 'jump clamps to end');
byId['tinput'].value = '15:00'; T.doJump(); ok(T.SIM.t === T.SCHED.start, 'jump clamps to start');

// 6. play advance + auto-pause
T.SIM.t = 1400; T.SIM.speed = 30; T.playBtn.onclick();
tsNow += 1000; rafCb(tsNow);
ok(Math.abs(T.SIM.t - 1403) < 0.01, 'play advances speed*dt');
T.SIM.t = T.SCHED.end - 0.001; tsNow += 1000; rafCb(tsNow);
ok(T.SIM.playing === false && T.SIM.t === T.SCHED.end, 'auto-pause at end');

// 7. nextArrivals: live time + wait + distance
const nm = '南京站·南广场东', st = T.DATA.stops[nm];
T.SIM.t = 1470;
const h = T.nextArrivals(nm, st);
ok(h.includes('模拟下一班到站') && h.includes('00:30⁺¹'), 'nextArrivals shows current sim time');
ok(h.includes('等待') && /km/.test(h), 'nextArrivals shows wait time and distance');
ok(T.fmtWait(0.5) === '即将到站' && T.fmtWait(0.2) === '即将到站', 'fmtWait ≤30s -> 即将到站');
ok(T.fmtWait(1) === '1分钟' && T.fmtWait(1.2) === '1分钟', 'fmtWait 1min tier');
ok(T.fmtWait(4.5) === '5分钟' && T.fmtWait(7.4) === '7分钟', 'fmtWait rounds to minutes: ' + T.fmtWait(4.5));

// 8. speed dial: gears, panel summon, needle picking
ok(T.GEARS.length === 10 && T.GEARS[0] === 1/6 && T.GEARS[1] === 1/3 && T.GEARS[2] === 0.5,
  'gears include 10/20/30 sec-per-sec');
ok(__initSpeed === 1 && __initGear === 3, 'default 1 min/s (speed ' + __initSpeed + ', gear ' + __initGear + ')');
ok(T.fmtSpeed(1/6) === '10秒/秒' && T.fmtSpeed(0.5) === '30秒/秒' && T.fmtSpeed(30) === '30分/秒', 'fmtSpeed labels');
byId['speedpanel'].hidden = true; // mirror the hidden attribute in HTML
byId['speedbtn'].onclick();
ok(byId['speedpanel'].hidden === false, 'speed button summons dial panel');
byId['speedbtn'].onclick();
ok(byId['speedpanel'].hidden === true, 'speed button toggles panel closed');
T.setSpeed(2); ok(T.SIM.speed === 0.5, 'setSpeed(2) -> 30秒/秒');
T.setSpeed(99); ok(T.SIM.speed === 120, 'clamp high');
T.setSpeed(-5); ok(T.SIM.speed === 1/6, 'clamp low');
ok(/rotate\(/.test(T.gneedle.attrs.transform || ''), 'needle transform set');
T.gaugePick({ clientX: 66, clientY: 14 }); ok(T.SIM.speed === 15, 'gauge top -> 15, got ' + T.SIM.speed);
T.gaugePick({ clientX: 120, clientY: 84 }); ok(T.SIM.speed === 120, 'gauge right -> 120');
T.gaugePick({ clientX: 12, clientY: 84 }); ok(T.SIM.speed === 1/6, 'gauge left -> 10秒/秒');
T.setSpeed(3);

// 8b. ← → speed nudge is window-level: works whenever the dial is open
const wkd = (ctx.window._l && ctx.window._l.keydown) || [];
ok(wkd.length >= 1, 'window keydown handler registered');
const fireKey = (k, tag) => wkd.forEach(fn => fn({ key: k, target: { tagName: tag || 'BODY' }, preventDefault() {} }));
T.setSpeed(3); T.setSpeedPanel(true);
fireKey('ArrowRight'); ok(T.gearIdx === 4 && T.SIM.speed === 5, 'ArrowRight nudges up while dial open -> gear ' + T.gearIdx);
fireKey('ArrowUp');    ok(T.gearIdx === 5, 'ArrowUp nudges up');
fireKey('ArrowLeft');  ok(T.gearIdx === 4, 'ArrowLeft nudges down');
fireKey('ArrowDown');  ok(T.gearIdx === 3 && T.SIM.speed === 1, 'ArrowDown nudges back to 1 min/s');
T.setSpeedPanel(false);
fireKey('ArrowRight'); ok(T.gearIdx === 3, 'arrows inert while dial closed');
T.setSpeedPanel(true);
fireKey('ArrowRight', 'INPUT'); ok(T.gearIdx === 3, 'arrows inert while focus is in an input');
T.setSpeedPanel(false);
T.setSpeed(3);

// 9. live stop popup refresh
const popCalls = [];
T.livePopup = { p: { setContent(x) { popCalls.push(x); } }, i: { nm, st, html: '<div>STATIC</div>' } };
T.SIM.t = 1470; tsNow += 1000; T.renderSim();
ok(popCalls.length === 1 && popCalls[0].includes('00:30⁺¹') && popCalls[0].includes('等待'), 'live popup refreshed with wait info');
T.SIM.t = 1500; tsNow += 1000; T.renderSim();
ok(popCalls.length === 2 && popCalls[1].includes('01:00⁺¹'), 'live popup tracks sim advance');
T.livePopup = null;

// 10. departure board: permanent, sorted by route number
T.SIM.t = 1470; tsNow += 1000; T.renderSim();
const keys = [...T.bbody.innerHTML.matchAll(/data-key="([^"]+)"/g)].map(m => m[1]);
ok(keys.length === countAt(1470), 'board rows = active buses: ' + keys.length);
let sorted = true;
for (let i = 1; i < keys.length; i++)
  if (T.ORDER[keys[i].split('|')[0]] < T.ORDER[keys[i - 1].split('|')[0]]) sorted = false;
ok(sorted, 'board sorted by route order (urban numeric -> SS -> 溧水 -> 高淳)');
ok(byId['brun'].textContent == countAt(1470), 'board run stat');
byId['bq'].value = '溧水'; T.renderBoard();
const lsKeys = [...T.bbody.innerHTML.matchAll(/data-key="(LS[^"]+)"/g)];
ok(T.SIM.t === 1470 ? lsKeys.length === 0 : lsKeys.length > 0, '溧水 filter (no 溧水 buses at 00:30)');
T.SIM.t = 1200; T.renderBoard();
const ls2 = [...T.bbody.innerHTML.matchAll(/data-key="(LS[^"]+)"/g)].length;
ok(ls2 > 0 && T.bbody.innerHTML.includes('溧水Y'), '溧水 rows carry 汉字 prefix at 20:00: ' + ls2);
byId['bq'].value = ''; T.SIM.t = 1470; T.renderBoard();
// minimize toggle
byId['bmin'].onclick();
ok(byId['board'].classList.contains('mini'), 'board minimizes');
byId['bmin'].onclick();
ok(!byId['board'].classList.contains('mini'), 'board restores');

// 11. busState segment logic
const v1 = T.SCHED.dirs['Y1|0'], s1 = T.DATA.routes.find(x => x.id === 'Y1').dirs[0].stops;
const dw = T.SCHED.model.dwell;
let bs = T.busState(v1, s1, v1.stopT[0] + dw / 2, 1300);
ok(bs.status === '停靠' && bs.seg === s1[0], 'busState dwelling at origin');
const mid = (v1.stopT[2] + dw + v1.stopT[3]) / 2;
bs = T.busState(v1, s1, mid, 1300);
ok(bs.status === '行驶' && bs.seg === s1[2] + ' → ' + s1[3], 'busState mid-segment');
bs = T.busState(v1, s1, v1.run, 1300);
ok(bs.status === '终到', 'busState terminal');

// 12. flash line-map
const dep1 = v1.deps.find(dp => dp <= 1470 && dp + v1.run >= 1470);
ok(dep1 !== undefined, 'found active Y1 departure at 00:30');
const fkey = 'Y1|0|' + v1.deps.indexOf(dep1);
T.SIM.t = 1470; T.openFlash(fkey);
ok(T.flash && T.flash.key === fkey && byId['flash'].hidden === false, 'flash opens on bus click');
ok(byId['fline'].textContent === 'Y1路', 'flash line badge');
ok(byId['fcur'].textContent.length > 0 && byId['fnext'].textContent.length > 0, 'flash current/next stop populated');
ok(byId['fclock'].textContent === '00:30⁺¹', 'flash clock');
const curBefore = byId['fcur'].textContent;
T.SIM.t = 1470 + (v1.stopT[5] - v1.stopT[0]); T.updateFlash();
ok(byId['fcur'].textContent !== curBefore || byId['fclock'].textContent !== '00:30⁺¹', 'flash advances with sim');
ok(byId['finner'].innerHTML.includes('fdot') && byId['finner'].innerHTML.includes('fbus'), 'flash strip has dots + bus');
// terminal: bus must rest exactly on the last dot, never overshoot past it
const nF = T.flash.d.stops.length, endX = 30 + (nF - 1) * T.FSP;
T.SIM.t = dep1 + v1.run - 0.01; T.updateFlash();
const leftBefore = parseFloat(byId['fbus'].style.left);
T.SIM.t = dep1 + v1.run; T.updateFlash();
const leftAt = parseFloat(byId['fbus'].style.left);
T.SIM.t = dep1 + v1.run + 60; T.updateFlash();
const leftAfter = parseFloat(byId['fbus'].style.left);
ok(Math.abs(leftAt - endX) < 0.01, 'flash bus rests on terminal dot at arrival');
ok(leftBefore <= leftAt + 0.01 && leftAfter === leftAt, 'flash bus never overshoots past terminal');
ok(byId['fstatv'].textContent === '终到收车' && byId['fd' + (nF - 1)].className.includes('done'), 'terminal status + done dot');
T.closeFlash();
ok(T.flash === null && byId['flash'].hidden === true, 'flash closes');

// 13. time-window skip stops (双龙街 0时至5时不停靠)
const sk27 = T.SCHED.dirs['Y27|1'], sk21 = T.SCHED.dirs['Y21|1'];
ok(sk27.skip && sk27.skip.length === 1 && sk27.skip[0].i === 7 && sk27.skip[0].from === 1440 && sk27.skip[0].to === 1740, 'Y27|1 skip rule 00:00–05:00');
ok(sk21.skip && sk21.skip.length === 1 && sk21.skip[0].i === 14, 'Y21|1 skip rule');
ok(T.SCHED.skipStops && T.SCHED.skipStops.length === 1 && T.SCHED.skipStops[0].dirs.length === 2, 'exactly one skip stop, two directions');
ok(!T.SCHED.dirs['Y27|0'].skip && !T.SCHED.dirs['Y21|0'].skip, 'opposite (进城) direction not skipped');
const i27 = sk27.skip[0].i, dw27 = T.SCHED.model.dwell;
let kSkip = -1, kStop = -1;
for (let k = 0; k < sk27.deps.length; k++) {
  const pass = sk27.deps[k] + sk27.stopT[i27];
  if (pass >= 1440 && pass < 1740 && kSkip < 0) kSkip = k;
  if (pass < 1440 && kStop < 0) kStop = k;
}
ok(kSkip >= 0 && kStop >= 0, 'found skipping and stopping departures');
const pSkip = T.depPlan(sk27, 'Y27|1', kSkip), pStop = T.depPlan(sk27, 'Y27|1', kStop);
ok(pSkip.sk[i27] === true && Math.abs(pSkip.run - (sk27.run - dw27)) < 1e-6, 'skip removes one dwell from run');
ok(pStop.sk[i27] === false && pStop.run === sk27.run, 'pre-midnight departure still stops');
ok(Math.abs(pSkip.st[i27] - sk27.stopT[i27]) < 1e-6 && Math.abs(pSkip.st[i27 + 1] - (sk27.stopT[i27 + 1] - dw27)) < 1e-6, 'downstream stop times shift earlier');
const pa = T.posAt(sk27, pSkip.st[i27] + 0.05, pSkip), pb = T.posAt(sk27, pSkip.st[i27] + 0.25, pSkip);
ok(Math.abs(pa[0] - pb[0]) > 1e-6 || Math.abs(pa[1] - pb[1]) > 1e-6, 'no dwell plateau at skipped stop');
ok(Math.abs(T.posAt(sk27, pSkip.st[i27] + 0.01, pSkip)[3] - sk27.stopKm[i27]) < 0.02, 'km aligns at skipped pass-through');
const s27 = T.DATA.routes.find(x => x.id === 'Y27').dirs[1].stops;
const bs27 = T.busState(sk27, s27, pSkip.st[i27] + dw27 / 2, sk27.deps[kSkip], pSkip);
ok(bs27.status === '飞站' && bs27.seg.includes('双龙街'), 'busState 飞站 at skipped stop');
T.SIM.t = sk27.deps[kSkip] + pSkip.st[i27] + 0.1; byId['bq'].value = ''; T.renderBoard();
ok(T.bbody.innerHTML.includes('飞站') && T.bbody.innerHTML.includes('bskip'), 'board shows 飞站 status');
const sknm = '双龙街(0时至5时不停靠)', skst = T.DATA.stops[sknm];
ok(!!skst, 'marked stop exists in DATA.stops');
T.SIM.t = 1470;
const hsk = T.nextArrivals(sknm, skst);
ok(hsk.includes('飞站') && hsk.includes('00:00–05:00'), 'popup shows skip window note');
ok(!/等待 <b>[^<]*秒/.test(hsk), 'popup waits have no seconds');
T.SIM.t = sk27.deps[kSkip] + pSkip.st[i27] + 0.1;
T.openFlash('Y27|1|' + kSkip);
ok(byId['fd' + i27].className.includes('skip'), 'flash dot marked skip');
ok(byId['fstatv'].textContent === '飞站通过不停车', 'flash status 飞站通过');
ok(byId['finner'].innerHTML.includes('ftag'), 'flash stop label carries 飞 tag');
T.closeFlash();

// 14. origin stop labelled 始发站 (not 距起点0.0km)
const rY1 = T.DATA.routes.find(x => x.id === 'Y1'), vY1 = T.SCHED.dirs['Y1|0'];
const onm = rY1.dirs[0].stops[0], ost = T.DATA.stops[onm];
T.SIM.t = vY1.deps[0] - 5;
const ho = T.nextArrivals(onm, ost);
ok(ho.includes('始发站'), 'origin stop shows 始发站');
ok(!ho.includes('距起点 <b>0.0</b>'), 'origin no longer shows 距起点0.0km');

// 15. flash bus marker / lit track / follow scroll stay in sync (no wobble)
const depA = v1.deps.find(dp => dp <= 1470 && dp + v1.run >= 1470);
T.SIM.t = 1470; T.openFlash('Y1|0|' + v1.deps.indexOf(depA));
ok(byId['fbus'].style.left === byId['flit'].style.width, 'bus left === lit width (synced)');
const l1 = parseFloat(byId['fbus'].style.left);
T.SIM.t = 1480; T.updateFlash();
const l2 = parseFloat(byId['fbus'].style.left);
ok(byId['fbus'].style.left === byId['flit'].style.width, 'still synced after advance');
ok(l2 > l1, 'bus advances with sim');
ok(parseFloat(byId['fstrip'].scrollLeft) >= 0, 'follow scroll clamped >= 0');
T.placeFlashBus();
ok(byId['fbus'].style.left === byId['flit'].style.width, 'placeFlashBus keeps sync');
T.closeFlash();

// 16. searchable help modal open/close
T.openHelp();
ok(byId['help'].hidden === false, 'help opens');
T.closeHelp();
ok(byId['help'].hidden === true, 'help closes');
ok(typeof T.helpSearch === 'function', 'helpSearch defined');

// 17. uniform stop dots + zoom scaling + amber one-way fill
ok(T.STOP_R === 3 && T.STOP_W === 1.5, 'uniform stop radius/weight constants');
ok(T.stopScale(11) === 1, 'stopScale(11) = 1 (overview)');
ok(T.stopScale(16) > T.stopScale(11), 'dots grow when zoomed in');
ok(T.stopScale(22) <= 4, 'stopScale capped at 4');
ok(T.stopScale(8) >= 0.8, 'stopScale floor 0.8');
ok(typeof T.paintStops === 'function', 'paintStops defined (amber one-way fill)');

// 18. realistic mode: seeded per-departure perturbations (delay/lights/congestion/dwell/accel)
const keyR = 'Y1|0', vR = T.SCHED.dirs[keyR];
ok(T.REAL === false, 'REAL defaults to false (theoretical)');
ok(T.planFor(vR, keyR, 0) === null, 'theoretical planFor === depPlan (null for no-skip dir)');
T.setReal(true);
ok(T.REAL === true, 'setReal(true) flips REAL');
const pR = T.planFor(vR, keyR, 0);
ok(pR && pR.real === true, 'realistic plan carries real=true');
ok(pR.depDelay >= 0 && pR.depDelay <= T.REAL_CFG.depMax, 'depDelay within [0,depMax] (never early)');
ok(pR.st.length === vR.stopT.length, 'realistic st length matches stop count');
let rMono = true; for (let i = 1; i < pR.st.length; i++) if (pR.st[i] < pR.st[i - 1] - 1e-9) rMono = false;
ok(rMono, 'realistic stop times monotonic');
ok(pR.run > 0 && isFinite(pR.run), 'realistic run finite & positive');
ok(Array.isArray(pR.rt) && pR.rt.length >= 2 && pR.rt[0][0] === 0, 'time-warp RT starts at real=0');
const pR2 = T.buildReal(vR, keyR, 0);
ok(JSON.stringify(pR.rt) === JSON.stringify(pR2.rt) && pR.depDelay === pR2.depDelay, 'buildReal deterministic per departure (scrub-stable)');
const pRk1 = T.buildReal(vR, keyR, 1);
ok(pRk1.depDelay !== pR.depDelay || JSON.stringify(pRk1.rt) !== JSON.stringify(pR.rt), 'distinct departures get distinct perturbations');
const o0 = T.posReal(vR, pR, 0), oEnd = T.posReal(vR, pR, pR.run + 5);
const thO = T.posAt(vR, 0), thE = T.posAt(vR, vR.run + 5);
ok(Math.abs(o0[0] - thO[0]) < 1e-6 && Math.abs(o0[1] - thO[1]) < 1e-6, 'posReal(0) sits at origin');
ok(Math.abs(oEnd[0] - thE[0]) < 1e-6 && Math.abs(oEnd[1] - thE[1]) < 1e-6, 'posReal(end) sits at terminal');
const oMid = T.posReal(vR, pR, pR.run * 0.5);
ok(isFinite(oMid[0]) && isFinite(oMid[1]) && Math.abs(oMid[0]) > 1 && Math.abs(oMid[1]) > 1, 'posReal mid-route finite coord');
ok(T.dirLights(vR).length > 0, 'dirLights infers signals along urban route');
ok(T.peakW(0) === 0 && T.peakW(420) === 1 && T.peakW(1110) === 1, 'peakW zero at midnight, peaks 07:00 & 18:30');
ok(T.peakW(420) >= T.peakW(360), 'peakW rises into morning peak');
ok(T.hashStr('a#0') === T.hashStr('a#0') && T.hashStr('a#0') !== T.hashStr('a#1'), 'hashStr stable & key-sensitive');
const gA = T.mulberry32(12345), gB = T.mulberry32(12345);
ok(gA() === gB(), 'mulberry32 reproducible from same seed');
const vS = T.SCHED.dirs['Y27|1'], iS = vS.skip[0].i;
let kS = -1; for (let k = 0; k < vS.deps.length; k++) { const pass = vS.deps[k] + vS.stopT[iS]; if (pass >= vS.skip[0].from && pass < vS.skip[0].to) { kS = k; break; } }
const pS = T.buildReal(vS, 'Y27|1', kS);
ok(kS >= 0 && pS.sk[iS] === true && pS.dwr[iS] === 0, 'realistic skipped stop gets zero dwell');
T.SIM.t = vR.deps[0] + 5; tsNow += 1000; T.renderSim(); T.renderBoard();
ok(T.bbody.innerHTML.length > 0, 'board & sim render without error in realistic mode');
T.openFlash(keyR + '|0'); T.updateFlash(); T.closeFlash();
ok(true, 'flash line-map renders in realistic mode');
T.setReal(false);
ok(T.REAL === false && T.planFor(vR, keyR, 0) === null, 'setReal(false) restores theoretical planFor');

// 19. mobile / portrait adaptation (drawer, fullscreen button, compact labels, auto-mini board)
ok(typeof T.isNarrow === 'function', 'isNarrow defined');
ctx.window.innerWidth = 1400;
ok(T.isNarrow() === false, 'desktop (1400px) is not narrow');
ok(/播放|暂停/.test(T.playLabel()), 'desktop play label carries text');
ok(T.modeLabel().length > 2 && T.speedLabel(false).indexOf('⏱ ') === 0, 'desktop mode/speed labels carry text');
ok(T.fsActive() === false, 'fsActive false (no fullscreen in sandbox)');
ok(typeof byId['fsbtn'].onclick === 'function', 'fullscreen button wired');
ctx.window.innerWidth = 500;
ok(T.isNarrow() === true, 'narrow at 500px');
ok(T.playLabel() === '▶' || T.playLabel() === '⏸', 'narrow play label icon-only');
ok(T.modeLabel() === '🌙' || T.modeLabel() === '🌆', 'narrow mode label icon-only');
ok(T.speedLabel(false) === '⏱ ▴' && T.speedLabel(true) === '⏱ ▾', 'narrow speed label icon-only');
T.refreshBarLabels();
ok(byId['sidetoggle'].textContent === '☰', 'refreshBarLabels compacts sidetoggle on narrow');
ok(byId['play'].textContent === '▶' || byId['play'].textContent === '⏸', 'refreshBarLabels compacts play button');
const sideT = byId['sidetoggle'];
sideT.onclick();
ok(documentMock.body.classList.contains('showside'), 'sidetoggle opens the drawer');
ok(byId['sidebackdrop'].hidden === false, 'backdrop visible while drawer open');
byId['sidebackdrop'].onclick();
ok(!documentMock.body.classList.contains('showside'), 'backdrop tap closes the drawer');
ok(byId['sidebackdrop'].hidden === true, 'backdrop hidden once closed');
ok(typeof byId['sideclose'].onclick === 'function', 'drawer close button wired');
T.applyNarrowBoard();
ok(byId['board'].classList.contains('mini'), 'departure board auto-minimised on narrow screen');
ctx.window.innerWidth = 1400;

// 20. dwell demand recalibration (per-route weight / typed nodes / hour gates / time-of-night / transfer decoupling)
ok(typeof T.routeW === 'function' && typeof T.isHub === 'function' && typeof T.todW === 'function' && typeof T.nodeType === 'function' && typeof T.nodeGate === 'function', 'dwell demand helpers defined');
ok(T.routeW('Y16') === 1.7 && T.routeW('Y13') === 1.3 && T.routeW('SS1') === 1.1, 'holiday-inflated weights corrected toward ordinary (Y16 1.7 / Y13 1.3 / SS1 1.1)');
ok(T.routeW('Y39') < 0.5 && T.routeW('Y38') < 0.5, 'near-empty routes weighted < 0.5');
ok(T.routeW('Y2') === 1.0 && T.routeW('__none__') === 1.0, 'routes without evidence default to 1.0');
ok(T.nodeType('南京站·南广场西') === 'rail' && T.nodeType('南京站·南广场东') === 'rail', '南京站·南广场 (station square) classified rail');
ok(T.nodeType('龙蟠路·南京站东') === null && T.nodeType('龙蟠路·南京站西') === null, '龙蟠路·南京站东/西 (~500m from station, no rail flow) NOT a hub');
ok(T.nodeType('南京南站') === 'hsr', '南京南站 (高铁) classified hsr');
ok(T.nodeType('汽车客运站') === 'coach' && T.nodeType('江宁长途汽车站') === 'coach' && T.nodeType('水阁路客运站') === 'coach', 'coach terminals classified coach');
ok(T.nodeType('南京西站') === null && T.nodeType('南京西站1站台') === null, '南京西站 (停办客运 since 2012-03-24) is NOT a hub');
ok(T.isHub('南京南站') && T.isHub('南京站·南广场西') && T.isHub('汽车客运站') && !T.isHub('南京西站') && !T.isHub('龙蟠路·南京站东') && !T.isHub('鼓楼医院'), 'isHub covers railway/coach transport hubs only');
ok(T.nodeType('鼓楼医院') === 'hospital' && T.nodeType('省人民医院') === 'hospital' && T.nodeType('南京市中医院') === 'hospital', '24h-emergency hospitals classified');
ok(T.nodeType('新街口东') === 'nightlife' && T.nodeType('太平南路·夫子庙') === 'nightlife' && T.nodeType('大行宫东') === 'nightlife', 'nightlife nodes classified');
ok(T.nodeType('南堡公园') === null && T.nodeType('') === null, 'ordinary stops have no node type');
ok(T.todW(30) > T.todW(200) && T.todW(200) < T.todW(330), 'demand surges post-metro, troughs ~03:20, rebounds by 05:30');
ok(T.todW(0) > 1.3 && T.todW(240) < 0.6, 'post-midnight surge exceeds deep-night trough');
ok(T.nodeGate('hsr', 23 * 60) > T.nodeGate('hsr', 4 * 60) * 1.5, '南京南站 gate collapses during the 00-06 高铁天窗 (' + T.nodeGate('hsr', 23 * 60).toFixed(2) + ' vs ' + T.nodeGate('hsr', 4 * 60).toFixed(2) + ')');
ok(T.nodeGate('coach', 1 * 60) > T.nodeGate('coach', 3 * 60 + 30) * 1.5, 'coach gate near-zero during the 02-05 停运 window (' + T.nodeGate('coach', 60).toFixed(2) + ' vs ' + T.nodeGate('coach', 210).toFixed(2) + ')');
ok(T.nodeGate('rail', 23 * 60) > T.nodeGate('rail', 3 * 60) * 1.5, '南京站·南广场 gate collapses in deep night (few stopping services after ~00:30) (' + T.nodeGate('rail', 23 * 60).toFixed(2) + ' vs ' + T.nodeGate('rail', 3 * 60).toFixed(2) + ')');
ok(T.nodeGate('nightlife', 23 * 60) > T.nodeGate('nightlife', 4 * 60) * 1.5, 'nightlife gate peaks late-evening and clears by deep night (' + T.nodeGate('nightlife', 23 * 60).toFixed(2) + ' vs ' + T.nodeGate('nightlife', 4 * 60).toFixed(2) + ')');
let agg = { hub: [0, 0], night: [0, 0], hosp: [0, 0], plain: [0, 0] };
let quickN = 0, totN = 0, sN = 0, sSum = 0, mN = 0, mSum = 0;
const perRoute = {};
for (const key of Object.keys(T.SCHED.dirs)) {
  const v = T.SCHED.dirs[key], rid = key.split('|')[0], di = +key.split('|')[1], wR = T.routeW(rid);
  const r = T.DATA.routes.find(x => x.id === rid), names = r ? r.dirs[di].stops : [];
  for (let k = 0; k < v.deps.length; k++) {
    const p = T.buildReal(v, key, k);
    for (let i = 0; i < p.dwr.length; i++) {
      if (p.sk && p.sk[i]) continue;
      const d = p.dwr[i], nm = names[i], nt = T.nodeType(nm);
      const nR = (nm && T.DATA.stops[nm]) ? Object.keys(T.DATA.stops[nm].routes).length : 1;
      totN++; if (d <= T.REAL_CFG.quickMax + 1e-9) quickN++;
      const bk = (nt === 'rail' || nt === 'hsr' || nt === 'coach') ? 'hub' : nt === 'nightlife' ? 'night' : nt === 'hospital' ? 'hosp' : 'plain';
      agg[bk][0] += d; agg[bk][1]++;
      const pr = perRoute[rid] || (perRoute[rid] = { s: 0, n: 0 }); pr.s += d; pr.n++;
      if (nt === null && i > 0 && i < p.dwr.length - 1) {
        const dn = d / wR;
        if (nR === 1) { sSum += dn; sN++; } else if (nR < T.REAL_CFG.majorRoutes) { mSum += dn; mN++; }
      }
    }
  }
}
const mean = b => b[0] / Math.max(1, b[1]);
const hubMean = mean(agg.hub), nightMean = mean(agg.night), hospMean = mean(agg.hosp), plainMean = mean(agg.plain);
const netMean = (agg.hub[0] + agg.night[0] + agg.hosp[0] + agg.plain[0]) / Math.max(1, totN);
ok(agg.hub[1] > 0 && hubMean > plainMean * 1.15, 'transport hubs dwell longer than ordinary stops (' + hubMean.toFixed(3) + ' vs ' + plainMean.toFixed(3) + ' min)');
ok(agg.night[1] > 0 && nightMean > plainMean, 'nightlife nodes dwell longer than ordinary stops (' + nightMean.toFixed(3) + ' vs ' + plainMean.toFixed(3) + ' min)');
ok(agg.hosp[1] > 0 && hospMean > plainMean, '24h-hospital nodes dwell longer than ordinary stops (' + hospMean.toFixed(3) + ' vs ' + plainMean.toFixed(3) + ' min)');
ok(netMean < T.SCHED.model.dwell, 'network mean dwell recalibrated below the 0.6-min nominal (' + netMean.toFixed(3) + ')');
ok(quickN / totN > 0.30, 'a healthy share of night stops are short door-cycles (' + (100 * quickN / totN).toFixed(0) + '%)');
const y16 = perRoute['Y16'], y39 = perRoute['Y39'];
ok(y16 && y39 && (y16.s / y16.n) > (y39.s / y39.n) * 1.3, 'busy Y16 dwells markedly longer than empty Y39');
const sMean = sSum / Math.max(1, sN), mMean = mSum / Math.max(1, mN);
ok(sN > 0 && mN > 0 && mMean < sMean * 1.25, 'ordinary 2-3-route transfer stops are NOT inflated vs single-route stops, weight-normalised (' + mMean.toFixed(3) + ' vs ' + sMean.toFixed(3) + ')');

// 21. simulation window covers realistic-mode finishes (no 收车 after SCHED.end)
let maxFinReal = -1, argFin = null;
for (const key of Object.keys(T.SCHED.dirs)) {
  const v = T.SCHED.dirs[key];
  for (let k = 0; k < v.deps.length; k++) {
    const fin = v.deps[k] + T.buildReal(v, key, k).run;
    if (fin > maxFinReal) { maxFinReal = fin; argFin = key + '|' + k; }
  }
}
ok(maxFinReal <= T.SCHED.end, 'realistic max finish ' + maxFinReal.toFixed(1) + ' (' + argFin + ') <= SCHED.end ' + T.SCHED.end);
ok(T.SCHED.end >= 1950, 'window end floor >= 08:30 (1950) for realistic headroom, got ' + T.SCHED.end);

// 22. metro adjacency (name-matched, boundary-aware, exclusions)
ok(typeof T.metroAdj === 'function' && typeof T.metroW === 'function', 'metro helpers defined');
ok(Object.keys(T.METRO_STATIONS).length > 200 && T.METRO_HOURS.weekday && T.METRO_HOURS.weekend && T.METRO_HOURS.holiday, 'metro station table + per-day-type hours loaded');
ok(T.metroAdj('新街口') && T.metroAdj('新街口').st === '新街口' && T.metroAdj('新街口').lines === '1,2', '新街口 matched to lines 1,2');
ok(T.metroAdj('迈皋桥') && T.metroAdj('迈皋桥').lines === '1', '迈皋桥 matched to line 1');
ok(T.metroAdj('南京南站') && T.metroAdj('南京南站').lines.indexOf('S1') >= 0, '南京南站 matched incl. airport S1');
ok(T.metroAdj('泰冯路地铁站') && T.metroAdj('泰冯路地铁站').st === '泰冯路', 'explicit 地铁站 suffix form matched');
ok(T.metroAdj('S8大厂站') && T.metroAdj('S8大厂站').st === '大厂', 'S-number 站 form matched');
ok(T.metroAdj('大厂·新庄') && T.metroAdj('大厂·新庄').st === '大厂', 'leftmost boundary match prefers 大厂 (S8) over 新庄');
ok(T.metroAdj('集庆门大街·南湖路') && T.metroAdj('集庆门大街·南湖路').st === '集庆门大街', '集庆门大街 matched to line 2');
ok(T.metroAdj('龙蟠路·南京站东') === null && T.metroAdj('龙蟠路·南京站西') === null, '龙蟠路·南京站 (~500m from platforms) excluded from metro adjacency');
ok(T.metroAdj('黑龙江路') === null && T.metroAdj('赛虹桥') === null && T.metroAdj('浦珠中路·万寿路') === null, 'road-suffix / mid-word false positives rejected (黑龙江路≠龙江, 赛虹桥≠虹桥, 万寿路≠万寿)');
ok(T.metroAdj('南堡公园') === null && T.metroAdj('') === null, 'ordinary non-metro stops return null');

// 23. metro demand modifier: competition while running / feeder surge after close / day-shift / S-line earlier
const MC = T.REAL_CFG.metroComp, MP = T.REAL_CFG.metroFeederPeak;
ok(T.metroW('迈皋桥', 20 * 60, 'weekday') === MC, 'metro-adjacent stop competes (×' + MC + ') while the metro runs (20:00)');
ok(T.metroW('迈皋桥', 1420, 'weekday') > 1.5, 'feeder surge right after weekday close (23:40, last-metro crowd boards the night bus)');
ok(T.metroW('迈皋桥', 1411, 'weekday') <= MP + 1e-9, 'feeder surge bounded by metroFeederPeak (' + MP + ')');
ok(T.metroW('迈皋桥', 1600, 'weekday') === 1, 'deep night (02:40) returns to baseline once the feeder wave decays');
ok(T.metroW('迈皋桥', 1800, 'weekday') === MC, 'early-morning competition resumes once the metro reopens (06:00 >= first)');
ok(T.metroW('南堡公园', 1420, 'weekday') === 1, 'non-adjacent stop unaffected by metro schedule');
ok(T.metroW('迈皋桥', 1430, 'weekday') > 1 && T.metroW('迈皋桥', 1430, 'weekend') === MC, 'weekend 延时 shifts close later: 23:50 is feeder on weekday but still competition on weekend');
ok(T.metroW('迈皋桥', 1470, 'weekend') > 1 && T.metroW('迈皋桥', 1470, 'holiday') === MC, 'holiday close later still: 00:30 feeder on weekend, competition on holiday');
ok(T.metroW('翠屏山', 1360, 'weekday') > 1 && T.metroW('迈皋桥', 1360, 'weekday') === MC, 'S-line closes earlier (sOffset): 22:40 feeder at S1 翠屏山 while line-1 迈皋桥 still running');

// 24. day-type ridership classes & multipliers
ok(T.dayClass('Y1') === 'tourist' && T.dayClass('Y16') === 'feeder' && T.dayClass('Y11') === 'local', 'routes classified tourist / feeder / local');
ok(T.dayMul('Y1', 'weekday') === 1.0 && T.dayMul('Y16', 'weekday') === 1.0 && T.dayMul('Y2', 'weekday') === 1.0, 'weekday is the corrected ordinary baseline (all ×1.0)');
ok(T.dayMul('Y1', 'weekend') === 1.25 && T.dayMul('Y1', 'holiday') === 1.70, 'tourist lines spike on weekend/holiday (Y1 ×1.25 / ×1.70)');
ok(T.dayMul('Y16', 'holiday') === 1.35 && T.dayMul('Y16', 'weekend') === 1.05, 'feeder lines rise modestly on weekend/holiday (Y16 ×1.05 / ×1.35)');
ok(T.dayMul('Y11', 'holiday') === 0.90 && T.dayMul('Y11', 'weekend') === 0.97, 'ordinary local lines dip slightly on weekend/holiday (Y11 ×0.97 / ×0.90)');
ok(T.DAYTYPE === 'weekday', 'default day-type is weekday');

// 25. day-type cache invalidation, per-day-type determinism, reserved flow hook
const y1key = Object.keys(T.SCHED.dirs).find(k => k.split('|')[0] === 'Y1');
const y1v = T.SCHED.dirs[y1key];
T.DAYTYPE = 'weekday'; T.setFlowModel(null);
const da = T.buildReal(y1v, y1key, 0), da2 = T.buildReal(y1v, y1key, 0);
ok(JSON.stringify(da.dwr) === JSON.stringify(da2.dwr), 'same day-type → identical dwell sequence (deterministic per departure)');
T.DAYTYPE = 'holiday';
const db = T.buildReal(y1v, y1key, 0);
ok(JSON.stringify(da.dwr) !== JSON.stringify(db.dwr), 'switching day-type changes tourist-line demand (weekday vs holiday dwell differs)');
T.DAYTYPE = 'weekday';
ok(JSON.stringify(T.buildReal(y1v, y1key, 0).dwr) === JSON.stringify(da.dwr), 'switching back to weekday reproduces the original sequence');
T.setFlowModel((nm, rid, clk, dt) => nm === '新街口' ? 2.5 : null);
ok(T.flowLoad('新街口', 'Y1', 0, 'weekday') === 2.5 && T.flowLoad('迈皋桥', 'Y1', 0, 'weekday') === null, 'reserved flow hook overrides load at matched stop-time, null elsewhere');
T.setFlowModel(() => 3.0);
const df = T.buildReal(y1v, y1key, 0);
ok(JSON.stringify(df.dwr) !== JSON.stringify(da.dwr), 'injected flow model changes the realised dwell sequence');
T.setFlowModel(null);
ok(T.flowLoad('新街口', 'Y1', 0, 'weekday') === null, 'clearing the flow model restores the parametric demand');
T.DAYTYPE = 'weekday';

// 26. day-type selector UI (disabled in theoretical, cycles in realistic)
T.setReal(false);
ok(byId['daybtn'] && byId['daybtn'].disabled === true, 'day-type button disabled in theoretical mode');
T.setReal(true);
ok(byId['daybtn'].disabled === false, 'day-type button enabled in realistic mode');
T.setDayType('weekday');
byId['daybtn'].onclick();
ok(T.DAYTYPE === 'weekend', 'day button cycles weekday → weekend');
byId['daybtn'].onclick();
ok(T.DAYTYPE === 'holiday', 'day button cycles weekend → holiday');
byId['daybtn'].onclick();
ok(T.DAYTYPE === 'weekday', 'day button cycles holiday → weekday');
T.setDayType('holiday');
ok(byId['daybtn'].classList.contains('on'), 'non-weekday day-type highlights the button');
T.setDayType('weekday'); T.setReal(false);

// 27. rated capacity & crowding tiers
ok(T.capacity('Y16') === 90 && T.capacity('Y1') === 90, 'trunk lines rated 90');
ok(T.capacity('SS1') === 150, 'SS1 articulated rated 150');
ok(T.capacity('LSY1') === 70 && T.capacity('GC801') === 70, 'suburban lines rated 70');
ok(T.crowdTier(0.2) === '舒适' && T.crowdTier(0.3) === '舒适', '<=30% 舒适');
ok(T.crowdTier(0.5) === '一般' && T.crowdTier(0.7) === '一般', '30-70% 一般');
ok(T.crowdTier(0.8) === '拥挤' && T.crowdTier(1.0) === '拥挤', '70-100% 拥挤');
ok(T.crowdColor(0.2) === '#34d399' && T.crowdColor(0.5) === '#fbbf24' && T.crowdColor(0.9) === '#f87171', 'crowding colors');

// 28. paxPlan: determinism, bounds, conservation, terminal empties
T.setReal(true); T.setDayType('weekday');
const pv = T.SCHED.dirs['Y16|0'];
const pplan = T.planFor(pv, 'Y16|0', 0);
const pax = T.paxPlan(pv, 'Y16|0', 0, pplan);
const pn = pv.stopT.length;
ok(pax.B.length === pn && pax.A.length === pn && pax.occ.length === pn, 'pax arrays match stop count');
ok(pax.occ.every(o => o >= 0 && o <= pax.cap), 'onboard within [0,cap]');
ok(pax.B.every(b => Number.isInteger(b) && b >= 0) && pax.A.every(a => Number.isInteger(a) && a >= 0), 'board/alight non-negative integers');
ok(pax.occ[pn - 1] === 0, 'terminal empties the bus');
let alightOk = true; for (let i = 1; i < pn; i++) if (pax.A[i] > pax.occ[i - 1]) alightOk = false;
ok(alightOk, 'alighting never exceeds prior onboard');
ok(T.paxPlan(pv, 'Y16|0', 0, pplan) === pax, 'paxPlan cached/deterministic');
// dwell-match: busy-tier stops board more on average than quick-tier stops
let qSum = 0, qN = 0, bSum = 0, bN = 0;
for (let i = 0; i < pn; i++) { const d = pplan.dwr[i]; if (pplan.sk[i]) continue;
  if (d <= T.REAL_CFG.quickMax + 1e-9) { qSum += pax.B[i]; qN++; } else if (d >= T.SCHED.model.dwell * T.REAL_CFG.busyMul[0]) { bSum += pax.B[i]; bN++; } }
ok(qN === 0 || bN === 0 || (bSum / bN) > (qSum / qN), 'busy stops board more than quick stops (dwell-match)');

// 29. reserved OD interface (hook present, not computed by default)
ok(T.odFlow('Y16', 0, 0, 0, 1) === null, 'OD null by default');
let odCalls = 0; T.setODModel((rid, di, k, i, j) => { odCalls++; return 5; });
ok(T.odFlow('Y16', 0, 0, 0, 1) === 5 && odCalls === 1, 'OD hook returns injected value');
T.setODModel(null); ok(T.odFlow('Y16', 0, 0, 0, 1) === null, 'OD hook resets to null');

// 30. god event: spatial spread, transfer spillover, window, 加车 relief
// Use a multi-route interchange hub so transfer spillover is exercised (奥体 itself
// is served only by Y7, so spillover is verified at a hub instead).
let hub = null;
for (const nm in T.DATA.stops) if (Object.keys(T.DATA.stops[nm].routes).length >= 3) { hub = nm; break; }
ok(!!hub, 'found an interchange hub for spillover test');
const hs = T.DATA.stops[hub];
const ev = T.createEvent(hs.lat, hs.lng, { crowd: 6000, tStart: 1350, dur: 120, radius: 2000 }, null);
ok(T.EVENTS.length === 1, 'event registered');
ok(Object.keys(ev.stopW).length >= 2, 'crowd spreads to multiple nearby stops');
let swSum = 0; for (const k in ev.stopW) swSum += ev.stopW[k];
ok(Math.abs(swSum - 1) < 1e-6, 'spatial weights normalized to 1');
ok(Object.keys(ev.routeShare[hub]).length >= 2, 'transfer spillover: hub crowd split across its routes');
let rsSum = 0; for (const r in ev.routeShare[hub]) rsSum += ev.routeShare[hub][r];
ok(Math.abs(rsSum - 1) < 1e-6, 'per-stop route shares normalized to 1');
// find an affected (stop,route) that actually has a scheduled departure in the window
let pair = null;
for (const nm in ev.sched) for (const rid in ev.sched[nm]) if (ev.sched[nm][rid].length) { pair = { nm, rid, pass: ev.sched[nm][rid][0] }; break; }
ok(!!pair, 'some affected stop-route has scheduled service in the window');
ok(T.eventBoard(pair.nm, pair.pass, pair.rid) > 0, 'event boardings positive at a served pass-time');
ok(T.eventBoard(pair.nm, 1350 + 121, pair.rid) === 0, 'event boardings zero after window');
ok(T.eventBoard('不存在站', pair.pass, pair.rid) === 0, 'unaffected stop gets no event load');
const di0 = T.DATA.stops[pair.nm].routes[pair.rid][0];
const idx0 = T.stopIdx(pair.rid, di0, pair.nm);
const before = T.eventBoard(pair.nm, pair.pass, pair.rid);
T.addExtra(pair.rid, di0, pair.pass, idx0, null);
const after = T.eventBoard(pair.nm, pair.pass, pair.rid);
ok(after < before, '加车 splits crowd → lower per-departure injected load');
byId['gclear'].onclick();
ok(T.EVENTS.length === 0, 'clear empties events');
T.EXTRA_DEPS.length = 0;

// 31. extra departures: synthetic direction, express skips, flash integration
const ex = T.addExtra('Y16', 0, 1360, 3, null);
const fullN = T.DATA.routes.find(x => x.id === 'Y16').dirs[0].stops.length;
ok(ex && ex.v.names.length === fullN - 3, 'god extra starts at crowded stop (sliced names)');
ok(ex.v.stopT[0] === 0, 'extra departure time rebased to 0 at start stop');
const exPlan = T.planFor(ex.v, ex.key, 0);
ok(exPlan && exPlan.real === true, 'extra departure uses realistic plan');
const exPax = T.paxPlan(ex.v, ex.key, 0, exPlan);
ok(exPax.occ.length === ex.v.stopT.length, 'extra pax matches sliced stops');
T.openFlash(ex.key);
ok(T.flash && T.flash.extra === true && T.flash.d.stops.length === ex.v.names.length, 'flash opens for extra departure');
T.closeFlash();
const ex2 = T.addExtra('Y16', 0, 1360, 0, 5);
ok(ex2.v.skip.length === 5, 'realistic auto extra expresses from origin');
const ex2Plan = T.planFor(ex2.v, ex2.key, 0);
ok(ex2Plan.sk.slice(0, 5).every(Boolean), 'express plan skips first 5 stops (飞站)');
T.EXTRA_DEPS.length = 0;

// 31b. end-to-end: a large event drives onboard to 100%; 加车 relieves actual onboard
T.setReal(true); T.setDayType('weekday'); T.SIM.t = 1300;
const hs2 = T.DATA.stops[hub];
T.createEvent(hs2.lat, hs2.lng, { crowd: 6000, tStart: 1350, dur: 120, radius: 2000 }, null);
function peakOnboard(rid) { const v = T.SCHED.dirs[rid + '|0']; let mx = 0;
  for (let k = 0; k < v.deps.length; k++) { const pl = T.planFor(v, rid + '|0', k); const px = T.paxPlan(v, rid + '|0', k, pl); for (const o of px.occ) if (o > mx) mx = o; } return mx; }
let evRid = null;
for (const rid in hs2.routes) { const v = T.SCHED.dirs[rid + '|0']; if (!v) continue; const idx = T.stopIdx(rid, 0, hub); if (idx < 0) continue;
  for (let k = 0; k < v.deps.length; k++) { const pass = v.deps[k] + v.stopT[idx]; if (pass >= 1350 && pass <= 1470) { evRid = rid; break; } } if (evRid) break; }
ok(!!evRid, 'a hub route has service in the event window');
const capR = T.capacity(evRid);
function peakLoc(rid) { const v = T.SCHED.dirs[rid + '|0']; let bm = 0, bk = 0, bi = 0;
  for (let k = 0; k < v.deps.length; k++) { const pl = T.planFor(v, rid + '|0', k); const px = T.paxPlan(v, rid + '|0', k, pl);
    px.occ.forEach((o, i) => { if (o > bm) { bm = o; bk = k; bi = i; } }); } return { bm, bk, bi }; }
const locBefore = peakLoc(evRid);
ok(locBefore.bm >= capR, 'large event drives onboard to 100% (挤爆啦 reachable), got ' + locBefore.bm + '/' + capR);
// add extras from the origin (serving every stop) to relieve the crowded stop
for (let a = 0; a < 6; a++) T.addExtra(evRid, 0, 1355 + a * 8, 0, null);
const vAfter = T.SCHED.dirs[evRid + '|0'];
const pxAfter = T.paxPlan(vAfter, evRid + '|0', locBefore.bk, T.planFor(vAfter, evRid + '|0', locBefore.bk));
ok(pxAfter.occ[locBefore.bi] < locBefore.bm, '加车 relieves the previously-crowded stop, ' + locBefore.bm + ' → ' + pxAfter.occ[locBefore.bi]);
byId['gclear'].onclick(); T.EXTRA_DEPS.length = 0;

// 32. achievements: unlock, idempotence, persistence, hidden page
ok(!!T.achGot.welcome, 'welcome unlocked on load');
ok(T.ACH.length >= 10, '>=10 achievements defined');
T.unlock('full'); ok(!!T.achGot.full, 'full (挤爆啦) unlocks');
const achN = Object.keys(T.achGot).length; T.unlock('full');
ok(Object.keys(T.achGot).length === achN, 'unlock is idempotent');
ok((localStorageMock.getItem('njbus_ach_v1') || '').includes('full'), 'achievements persisted to localStorage');
T.openAch(); ok(byId['achpage'].hidden === false, 'achievement page opens');
ok(byId['achbody'].innerHTML.includes('挤爆啦'), 'achievement page renders cards');
T.closeAch(); ok(byId['achpage'].hidden === true, 'achievement page closes');

// 33. god-mode gating & preset placement
T.setReal(false); ok(byId['godbtn'].disabled === true, 'godbtn disabled in theoretical mode');
T.setReal(true); ok(byId['godbtn'].disabled === false, 'godbtn enabled in realistic mode');
byId['godbtn'].onclick(); ok(T.GOD === true && byId['godpanel'].hidden === false, 'godbtn opens god panel');
ok(!!T.achGot.godmode, 'godmode achievement on first open');
presetBtns[0].onclick();
ok(!!T.achGot.concert, 'concert preset unlocks 比歌声更快');
ok(T.EVENTS.length >= 1, 'concert preset injects an event');
byId['gclear'].onclick(); T.EXTRA_DEPS.length = 0;
byId['godbtn'].onclick(); ok(T.GOD === false, 'godbtn toggles god off');
T.setReal(false); ok(T.GOD === false, 'leaving realistic mode forces god off');

// 34. calibration probe: peak onboard per route (plain weekday realistic, no events)
T.setReal(true); T.setDayType('weekday');
const probeRoutes = ['Y16', 'Y13', 'Y1', 'Y8', 'Y3', 'SS1', 'Y4', 'Y29', 'LSY1', 'GC801'];
const peaks = {};
for (const rid of probeRoutes) {
  const v = T.SCHED.dirs[rid + '|0']; if (!v) continue;
  let mx = 0;
  for (let k = 0; k < v.deps.length; k++) { const pl = T.planFor(v, rid + '|0', k); const px = T.paxPlan(v, rid + '|0', k, pl);
    for (const o of px.occ) if (o > mx) mx = o; }
  peaks[rid] = mx;
  console.log('PEAK', rid, mx, '/', T.capacity(rid), '=', Math.round(mx / T.capacity(rid) * 100) + '%');
}
ok(peaks.Y16 >= 8 && peaks.Y16 <= 22, 'Y16 peak onboard in plausible night trunk range (8-22), got ' + peaks.Y16);
ok(peaks.Y13 <= 18, 'Y13 peak onboard modest (<=18), got ' + peaks.Y13);
ok(peaks.Y4 <= 10 && peaks.Y29 <= 10, 'sparse lines peak low (<=10)');
ok(Object.values(peaks).every(p => p < 25), 'plain night service stays sparse (peak <25 onboard, ~<28%); only events fill buses');
T.setReal(false); T.setDayType('weekday');

// 35. enriched presets + god-mode auto-relief form focus + quick departure
ok(Object.keys(T.PRESETS).length >= 6, '>=6 event presets (concert/sports/qingao/festival/lantern/laomendong)');
ok(T.PRESETS.lantern && T.PRESETS.lantern.lat != null, '秦淮灯会 preset carries an explicit 白鹭洲 venue center');
ok(T.PRESETS.festival.label.indexOf('咪豆') >= 0, 'festival preset labelled 咪豆音乐节');
T.setReal(true); byId['godbtn'].onclick();
ok(T.clockInput(1450) === '00:10' && T.clockInput(1350) === '22:30', 'clockInput formats HH:MM without day suffix');
ok(byId['gdeptime'].value === T.clockInput(T.SIM.t), 'opening god panel defaults departure to current sim time (<= now)');
// quick +10 button configures a delayed departure relative to now
byId['gdeptime'].value = T.clockInput(T.SIM.t + 10);
ok(T.parseClock(byId['gdeptime'].value) >= T.SIM.t, '+10分 quick button yields a future (delayed) departure');
// focusGodRoute jumps the manual form to the affected route/direction/stop and sets dep<=now
const fr = T.DATA.routes[0].id;
T.focusGodRoute(fr, 0, 2, T.SIM.t);
ok(T.groute.value === fr && T.gstop.value === '2', 'focusGodRoute jumps manual form to affected route/stop');
ok(T.parseClock(byId['gdeptime'].value) <= T.SIM.t + 1, 'auto-relief departure is no later than current sim time');
byId['gclear'].onclick(); T.EXTRA_DEPS.length = 0; byId['godbtn'].onclick(); T.setReal(false);

// 36. in-page help documents the planner; achievement entry hinted (not spelled out)
const HTML = fs.readFileSync('D:/nj_night_bus/realmap.html', 'utf8');
ok(HTML.indexOf('planner.html') >= 0 && HTML.indexOf('换乘规划') >= 0, 'help documents & links the planner page');
ok(HTML.indexOf('连续点击侧栏标题') < 0 && HTML.indexOf('连续快速点击侧栏标题') < 0, 'achievement entry no longer explicitly stated in docs');
ok(HTML.indexOf('藏了起来') >= 0, 'achievement help gives a hint instead of the exact method');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);