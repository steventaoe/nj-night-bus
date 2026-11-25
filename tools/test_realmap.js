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
const documentMock = {
  body: makeEl('body'),
  addEventListener() {},
  getElementById(id) { return byId[id] || (byId[id] = makeEl(id)); },
  createElement(tag) { const el = makeEl('<' + tag + '#' + created.length + '>'); created.push(el); return el; },
  querySelectorAll(sel) {
    if (sel === '.chip input') return created.filter(e => e.className === 'chip').map(d => d.querySelector('input'));
    return [];
  },
};
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
  window: { addEventListener() {}, innerWidth: 1400, innerHeight: 900 },
  L: autoMock('L'),
  performance: { now: () => tsNow },
  requestAnimationFrame: cb => { rafCb = cb; },
  console,
});
vm.runInContext(src + '\n;globalThis.__test={SIM,SCHED,DATA,posAt,renderSim,doJump,fmtT,fmtSpeed,fmtWait,nextArrivals,chipState,pool,playBtn,scrub,loop,ORDER,' +
  'setSpeed,gaugePick,GEARS,gneedle,gfill,speedval,setSpeedPanel,busState,renderBoard,bbody,openFlash,updateFlash,closeFlash,' +
  'get livePopup(){return livePopup}, set livePopup(v){livePopup=v}, get flash(){return flash}, get gearIdx(){return gearIdx}, depPlan, FSP,' +
  'placeFlashBus, flashGeom, openHelp, closeHelp, helpSearch, stopScale, paintStops, STOP_R, STOP_W};',
  ctx, { timeout: 30000 });
const T = ctx.__test || (ctx.globalThis && ctx.globalThis.__test);
let pass = 0, fail = 0;
const ok = (cond, msg) => { if (cond) { pass++; } else { fail++; console.log('FAIL:', msg); } };

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
byId['tinput'].value = '07:50'; T.doJump(); ok(T.SIM.t === T.SCHED.end, 'jump clamps to end');
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
ok(T.SIM.speed === 30 && T.gearIdx === 7, 'default 30 min/s');
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
T.setSpeed(7);

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

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);