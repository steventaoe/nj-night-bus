"""Generate planner.html — a passenger-perspective transfer/route planner.

Reuses the *exact* realistic-mode engine from gen_realmap.py (same DATA/SCHED,
same deterministic per-departure time warp), so a planned arrival time equals
what the city-wide simulation shows. The planner shell hides the macro UI and
adds: stop/time inputs, a transfer search (direct + 1-transfer enumeration +
earliest-arrival Dijkstra), policy controls (transfer-station preference, walk /
wait / total thresholds, "赌一把" tight transfers, day type), and a full journey
playback that highlights only the ridden lines.
"""
import os

ROOT = os.path.join(os.path.dirname(__file__), '..')

# Importing runs gen_realmap (regenerates realmap.html identically) and exposes
# the fully-substituted page string as G.html plus the shared data payload.
import gen_realmap as G

base = G.html
assert base.count('<body>') == 1 and base.count('</head>') == 1 and base.count('</body>') == 1

CSS = '''
<style id="plannerstyle">
 body.planner #simbar,body.planner #speedpanel,body.planner #board,body.planner #side,
 body.planner #sidebackdrop,body.planner #sidetoggle,body.planner #flash,body.planner #achpage,
 body.planner #toast,body.planner #godpanel,body.planner .helpbtn,body.planner .leaflet-control-layers{display:none!important}
 body.planner .leaflet-marker-pane .busicon{display:none!important}
 body.planner #map{inset:0}
 #pl{position:fixed;top:0;left:0;bottom:0;width:380px;max-width:92vw;z-index:1300;display:flex;flex-direction:column;
     background:#0b1024f2;border-right:1px solid #2a2347;backdrop-filter:blur(6px);color:#c7d0ee;font-size:13px}
 #plhead{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid #2a2347;background:#0e1430}
 #plhead .t{font-weight:700;font-size:15px;color:#e6ddff;flex:1}
 #plhead button{background:none;border:1px solid #3a2c66;color:#a99be0;border-radius:7px;padding:3px 9px;cursor:pointer;font-size:12px}
 #plbody{overflow:auto;padding:12px 14px;flex:1}
 .plsec{margin-bottom:14px}
 .pllabel{font-size:11px;color:#8b96c4;letter-spacing:.04em;margin-bottom:6px;text-transform:none}
 .plrow{display:flex;gap:8px;align-items:center;margin-bottom:8px}
 .plrow>label{width:74px;flex:none;color:#9aa4cf;font-size:12px}
 .plrow input[type=text],.plrow select,.plrow input[type=number]{flex:1;background:#141a38;border:1px solid #2c3563;color:#e8ecff;
     border-radius:7px;padding:6px 8px;font-size:13px;min-width:0}
 .plrow input[type=range]{flex:1}
 .plrow b{color:#d6ccff;font-variant-numeric:tabular-nums;min-width:34px;text-align:right}
 .plchips{display:flex;gap:6px;flex-wrap:wrap}
 .plchips button{flex:1;min-width:64px;background:#161b3a;border:1px solid #2c3563;color:#c3cbee;border-radius:7px;padding:6px 4px;cursor:pointer;font-size:12px}
 .plchips button.on{background:#3a2c66;border-color:#a855f7;color:#fff}
 .plgo{width:100%;background:linear-gradient(135deg,#7c3aed,#a855f7);border:none;color:#fff;border-radius:9px;padding:10px;cursor:pointer;font-size:14px;font-weight:600}
 .plgo:hover{filter:brightness(1.1)}
 .plchk{display:flex;align-items:center;gap:6px;font-size:12px;color:#9aa4cf;cursor:pointer}
 .plnote{font-size:11px;color:#6f7aa8;line-height:1.5;margin-top:6px}
 .plerr{background:#2a1626;border:1px solid #7c3a5a;color:#f5b8cd;border-radius:8px;padding:8px 10px;font-size:12px;margin-bottom:10px}
 .plpick{flex:none;width:34px;height:32px;background:#161b3a;border:1px solid #2c3563;color:#c3cbee;border-radius:7px;cursor:pointer;font-size:15px;line-height:1;padding:0}
 .plpick:hover{background:#243055;color:#ffd97a}
 .plpick.armed{background:#3a2c66;border-color:#a855f7;color:#fff;box-shadow:0 0 0 1px #a855f755}
 #plhint{font-size:11px;color:#8b96c4;margin:0 0 8px;line-height:1.4}
 #plhint:empty{display:none}
 #plhint b{color:#9fe8c8}
 #plac{position:fixed;z-index:1400;display:none;max-height:244px;overflow:auto;background:#11173a;border:1px solid #3a2c66;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.55);padding:4px}
 #plac .acit{padding:6px 9px;border-radius:6px;cursor:pointer;font-size:13px;color:#dfe4ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 #plac .acit:hover,#plac .acit.act{background:#3a2c66;color:#fff}
 #plac .acit .hl{color:#ffd97a}
 #plac .acnone{padding:8px 9px;color:#7f8db8;font-size:12px}
 #plac .acsub{padding:5px 9px 3px;color:#6f7aa8;font-size:10px;border-top:1px solid #2a2347;margin-top:3px}
 .itcard{background:#11173a;border:1px solid #2a2347;border-radius:10px;padding:10px;margin-bottom:9px;cursor:pointer;transition:border-color .12s}
 .itcard:hover{border-color:#5b4b96}
 .itcard.sel{border-color:#a855f7;background:#171d44;box-shadow:0 0 0 1px #a855f755}
 .ittop{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
 .ittime{font-size:17px;font-weight:700;color:#fff}
 .itarr{font-size:12px;color:#9fe8c8}
 .itmeta{font-size:11px;color:#8b96c4;margin-left:auto;text-align:right}
 .itlegs{display:flex;flex-direction:column;gap:3px}
 .itlg{display:flex;align-items:center;gap:7px;font-size:12px;line-height:1.4}
 .itlg .dot{width:9px;height:9px;border-radius:50%;flex:none}
 .itlg .bar{width:3px;align-self:stretch;border-radius:2px;flex:none;margin:1px 0 1px 3px}
 .itlg .tx{flex:1;min-width:0}
 .itlg .mut{color:#7f8db8}
 .tag{display:inline-block;font-size:10px;padding:1px 6px;border-radius:20px;margin-left:5px;vertical-align:middle}
 .tag.risk{background:#3a1d1d;color:#f6a5a5;border:1px solid #7c3a3a}
 .tag.last{background:#3a2d1d;color:#f6d6a5;border:1px solid #7c5a3a}
 .tag.wait{background:#1d2a3a;color:#a5c8f6;border:1px solid #3a5a7c}
 .tag.walk{background:#1d3a2a;color:#a5f6c8;border:1px solid #3a7c5a}
 .tag.crowd{background:#3a1d33;color:#f6a5e0;border:1px solid #7c3a6a}
 .tag.rec{background:#243a1d;color:#cdf6a5;border:1px solid #4f7c3a}
 #plplay{border-top:1px solid #2a2347;background:#0e1430;padding:9px 12px;display:none}
 #plplay.on{display:block}
 .plprow{display:flex;align-items:center;gap:8px}
 .plprow button{background:#1c1740;border:1px solid #4c3a75;color:#e3d6ff;border-radius:7px;padding:5px 11px;cursor:pointer;font-size:13px}
 #plscrub{flex:1}
 #plstatus{font-size:12px;color:#d6ccff;margin-top:7px;line-height:1.5;min-height:34px}
 #plstatus .big{font-size:13px;color:#fff;font-weight:600}
 #plstatus .sub{color:#8b96c4}
 .plcrowd{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
 @media(max-width:760px){#pl{width:100%;max-width:100%;top:auto;height:56vh;border-right:none;border-top:1px solid #2a2347}}
</style>
'''

HTML = '''
<div id="pl">
 <div id="plhead"><span class="t">🧭 换乘规划 · 乘客视角</span><a href="realmap.html" title="返回全城模拟" style="color:#a99be0;text-decoration:none;font-size:12px;border:1px solid #3a2c66;border-radius:7px;padding:3px 9px">🗺 全城模拟</a><button id="plreset" title="清除高亮与结果">重置</button></div>
 <div id="plbody">
  <div class="plsec">
   <div class="pllabel">行程</div>
   <div class="plrow"><label>出发站</label><input id="plfrom" type="text" placeholder="输入站名搜索…" autocomplete="off"><button class="plpick" id="pickfrom" type="button" title="在地图上取点作为出发地（吸附到最近站点）">📍</button></div>
   <div class="plrow"><label>目的站</label><input id="plto" type="text" placeholder="输入站名搜索…" autocomplete="off"><button class="plpick" id="pickto" type="button" title="在地图上取点作为目的地（吸附到最近站点）">📍</button></div>
   <div id="plhint"></div>
   <div class="plrow"><label>出发时刻</label><input id="pltime" type="text" value="23:00" placeholder="23:00"><span style="color:#6f7aa8;font-size:11px">00–11 时视为次日</span></div>
   <div class="plrow"><label>客流日型</label><div class="plchips" id="plday" style="flex:1">
     <button data-dt="weekday" class="on">工作日</button><button data-dt="weekend">周末</button><button data-dt="holiday">节假日</button></div></div>
  </div>
  <div class="plsec">
   <div class="pllabel">换乘偏好与阈值</div>
   <div class="plrow"><label>换乘站优先</label><div class="plchips" id="plpref" style="flex:1">
     <button data-pf="fast" class="on">最快到达</button><button data-pf="hub">大站枢纽</button><button data-pf="first">共线首站</button></div></div>
   <div class="plrow"><label>最长步行</label><input id="plwalk" type="range" min="3" max="20" step="1" value="15"><b id="plwalkv">15</b><span style="color:#6f7aa8;font-size:11px">分</span></div>
   <div class="plrow"><label>最长候车</label><input id="plwait" type="range" min="5" max="60" step="5" value="30"><b id="plwaitv">30</b><span style="color:#6f7aa8;font-size:11px">分</span></div>
   <div class="plrow"><label>最长全程</label><input id="pltotal" type="range" min="30" max="240" step="10" value="150"><b id="pltotalv">150</b><span style="color:#6f7aa8;font-size:11px">分</span></div>
   <label class="plchk"><input id="plgamble" type="checkbox"> 允许「赌一把」紧换乘（后车可能趁前车等灯追上，有错过风险）</label>
   <div class="plrow" id="plgamblerow" style="display:none;margin-top:6px"><label>赌窗口</label><input id="plgamblemin" type="range" min="1" max="6" step="1" value="3"><b id="plgambleminv">3</b><span style="color:#6f7aa8;font-size:11px">分</span></div>
   <label class="plchk" style="margin-top:6px"><input id="plorwalk" type="checkbox" checked> 允许出发/到达端步行接驳（扩大可达范围）</label>
  </div>
  <button class="plgo" id="plgo">🔍 规划路线</button>
  <div class="plnote">基于<b>现实模式</b>（含发车延误、红灯、堵车、停站波动的确定性随机）计算到站时刻，与全城模拟一致。步行以直线距离 ÷ 4.5 km/h 估算（静态地图不含路网导航）。</div>
  <div id="plmsg"></div>
  <div class="plsec" style="margin-top:12px"><div class="pllabel" id="plreslabel">方案</div><div id="plres"></div></div>
 </div>
 <div id="plplay">
  <div class="plprow"><button id="plpp">⏸ 暂停</button><input id="plscrub" type="range" min="0" max="1000" value="0"><select id="plspeed" style="background:#141a38;border:1px solid #2c3563;color:#e8ecff;border-radius:7px;padding:4px">
    <option value="2">2分/秒</option><option value="5">5分/秒</option><option value="10" selected>10分/秒</option><option value="30">30分/秒</option></select></div>
  <div id="plstatus"></div>
 </div>
</div>
'''

JS = r'''
(function(){
 try{
  // ---- run the planner on the realistic engine ----
  try{ if(typeof setReal==='function') setReal(true); }catch(e){}
  SIM.playing=false;

  var WALK_MPM=75;            // 4.5 km/h straight-line
  var BOARD_BUF=0.5;          // minutes needed to board / same-stop transfer
  var arrCache=new Map(), walkNb=null, planLayer=null, baseDimmed=false;
  var RESULTS=[], SEL=-1, JT=null, pLast=0;

  function defOpt(o){ o=o||{}; return {maxWalkMin:(o.maxWalkMin!=null?o.maxWalkMin:15),maxTransferWait:(o.maxTransferWait!=null?o.maxTransferWait:30),maxTotal:(o.maxTotal!=null?o.maxTotal:150),gamble:!!o.gamble,gambleMin:(o.gambleMin!=null?o.gambleMin:3),orWalk:(o.orWalk!==false),pref:(o.pref||'fast')}; }
  function planOD(O,D,T0,opt){ opt=opt||defOpt(); var c=directOptions(O,D,T0,opt).concat(transferOptions(O,D,T0,opt)); var dj=dijkstra(O,D,T0,opt); if(dj)c.push(dj); return dedupSort(c,opt); }
  globalThis.__planner={defOpt:defOpt,planOD:planOD,directOptions:directOptions,transferOptions:transferOptions,dijkstra:dijkstra,dedupSort:dedupSort,mkItin:mkItin,arrMat:arrMat,buildWalk:buildWalk,walkList:walkList,clearArrCache:clearArrCache,stC:stC,dirStops:dirStops,WALK_MPM:WALK_MPM,BOARD_BUF:BOARD_BUF,
    DATA:DATA,SCHED:SCHED,posAt:posAt,planFor:planFor,paxPlan:paxPlan,pt:pt,distM:distM,fmtT:fmtT,parseClock:parseClock,setReal:setReal,setDayType:setDayType,capacity:capacity,nodeType:nodeType,crowdTier:crowdTier,crowdColor:crowdColor,
    get REAL(){return REAL},get DAYTYPE(){return DAYTYPE},get SIM(){return SIM}};

  function stC(nm){ var s=DATA.stops[nm]; return s?[s.lat,s.lng]:null; }
  function dirStops(rid,di){ var v=SCHED.dirs[rid+'|'+di]; var r=DATA.routes.find(function(x){return x.id===rid;}); return (v&&v.names)||(r?r.dirs[di].stops:[]); }
  function routeOf(rid){ return DATA.routes.find(function(x){return x.id===rid;}); }
  function arrMat(rid,di){
    var key=rid+'|'+di, M=arrCache.get(key); if(M!==undefined) return M;
    var v=SCHED.dirs[key]; if(!v){ arrCache.set(key,null); return null; }
    M=[];
    for(var k=0;k<v.deps.length;k++){
      var pl=planFor(v,key,k), st=pl?pl.st:v.stopT, sk=pl?pl.sk:null, row=new Array(st.length);
      for(var i=0;i<st.length;i++) row[i]=(sk&&sk[i])?null:v.deps[k]+st[i];
      M.push(row);
    }
    arrCache.set(key,M); return M;
  }
  function clearArrCache(){ arrCache.clear(); }
  function buildWalk(){
    if(walkNb) return walkNb;
    var names=Object.keys(DATA.stops), co=names.map(function(nm){return DATA.stops[nm];});
    var RMAX=1600, dLat=RMAX/111000, dLng=RMAX/(111000*Math.cos(32*Math.PI/180));
    walkNb=new Map();
    for(var a=0;a<names.length;a++){ var ca=co[a], list=[];
      for(var b=0;b<names.length;b++){ if(a===b)continue; var cb=co[b];
        if(Math.abs(ca.lat-cb.lat)>dLat||Math.abs(ca.lng-cb.lng)>dLng)continue;
        var d=distM([ca.lat,ca.lng],[cb.lat,cb.lng]); if(d<=RMAX) list.push([names[b],d/WALK_MPM,d]);
      }
      list.sort(function(x,y){return x[1]-y[1];}); walkNb.set(names[a],list);
    }
    return walkNb;
  }
  function walkList(nm,maxMin){ var L=(buildWalk().get(nm))||[]; var out=[]; for(var i=0;i<L.length&&L[i][1]<=maxMin;i++)out.push(L[i]); return out; }

  // ---------- itinerary metrics ----------
  function crowdInfo(ratio){
    if(typeof crowdTier==='function'){ try{ return {label:crowdTier(ratio),color:(typeof crowdColor==='function'?crowdColor(ratio):'#888')}; }catch(e){} }
    var lab=ratio<0.3?'舒适':ratio<0.7?'一般':'拥挤'; return {label:lab,color:ratio<0.3?'#4ade80':ratio<0.7?'#fbbf24':'#f87171'};
  }
  function mkItin(legs,T0,tag){
    var end=T0,walkM=0,walkT=0,waits=[],rides=0,maxRatio=0,flags=[],prev=T0;
    for(var li=0;li<legs.length;li++){ var lg=legs[li];
      if(lg.type==='walk'){ walkM+=lg.dm; walkT+=lg.wm; prev=lg.arr; end=lg.arr; }
      else{ rides++; var w=lg.board-prev; lg.wait=w; waits.push(w);
        if(w<-1e-6&&flags.indexOf('gamble')<0)flags.push('gamble');
        if(w>20&&flags.indexOf('longwait')<0)flags.push('longwait');
        var key=lg.rid+'|'+lg.di,v=SCHED.dirs[key],pl=planFor(v,key,lg.k),mx=0,cap=90;
        try{ var px=paxPlan(v,key,lg.k,pl); cap=px.cap; for(var i=lg.fromIdx;i<=lg.toIdx;i++)if(px.occ[i]>mx)mx=px.occ[i]; }catch(e){}
        lg.occ=mx; lg.cap=cap; lg.ratio=cap>0?mx/cap:0; if(lg.ratio>maxRatio)maxRatio=lg.ratio;
        if(lg.k===v.deps.length-1&&flags.indexOf('lastbus')<0)flags.push('lastbus');
        prev=lg.alight; end=lg.alight;
      }
    }
    var transfers=Math.max(0,rides-1);
    if(maxRatio>=0.7&&flags.indexOf('crowd')<0)flags.push('crowd');
    if(walkT>0&&flags.indexOf('walk')<0)flags.push('walk');
    // transfer-station metadata (first alight stop) for policy sorting
    var tStop=null,tIdx=999,tHub=0;
    for(var j=0;j<legs.length;j++){ if(legs[j].type==='ride'){ tStop=legs[j].to; tIdx=legs[j].toIdx;
      var s=DATA.stops[tStop]; tHub=s?Object.keys(s.routes).length:1; if(typeof nodeType==='function'&&nodeType(tStop))tHub+=3; break; } }
    return {legs:legs,start:T0,end:end,total:end-T0,rides:rides,transfers:transfers,walkM:walkM,walkT:walkT,
      waits:waits,maxRatio:maxRatio,fare:2*rides,flags:flags,tStop:tStop,tIdx:tIdx,tHub:tHub,tag:tag||null,
      sig:legs.map(function(l){return l.type==='ride'?(l.rid+'|'+l.di+'|'+l.k+'|'+l.fromIdx+'|'+l.toIdx):('w'+l.from+'>'+l.to);}).join(';')};
  }

  // ---------- searches ----------
  function directOptions(O,D,T0,opt){
    var res=[],so=DATA.stops[O],sd=DATA.stops[D]; if(!so||!sd)return res;
    Object.keys(so.routes).forEach(function(rid){ if(!(rid in sd.routes))return;
      so.routes[rid].forEach(function(di){ if(sd.routes[rid].indexOf(di)<0)return;
        var stops=dirStops(rid,di),i=stops.indexOf(O),j=stops.indexOf(D); if(i<0||j<0||j<=i)return;
        var M=arrMat(rid,di); if(!M)return; var cnt=0;
        for(var k=0;k<M.length&&cnt<2;k++){ if(M[k][i]==null||M[k][j]==null)continue; if(M[k][i]<T0+BOARD_BUF)continue;
          res.push(mkItin([{type:'ride',rid:rid,di:di,k:k,fromIdx:i,toIdx:j,from:O,to:D,board:M[k][i],alight:M[k][j]}],T0,'direct')); cnt++; }
      });
    });
    return res;
  }
  function transferOptions(O,D,T0,opt){
    var res=[],so=DATA.stops[O]; if(!so)return res; var maxEnd=T0+opt.maxTotal, nbCap=24;
    var origins=[[O,0]];
    if(opt.orWalk){ var wl=walkList(O,opt.maxWalkMin); for(var q=0;q<wl.length&&q<nbCap;q++)origins.push([wl[q][0],wl[q][1]]); }
    for(var oi=0;oi<origins.length;oi++){
      var Os=origins[oi][0],wTo=origins[oi][1],Tat= T0+wTo, sto=DATA.stops[Os]; if(!sto)continue;
      var preWalk = wTo>0?[{type:'walk',from:O,to:Os,dep:T0,arr:Tat,wm:wTo,dm:wTo*WALK_MPM}]:[];
      Object.keys(sto.routes).forEach(function(ridA){ sto.routes[ridA].forEach(function(diA){
        var stopsA=dirStops(ridA,diA),iA=stopsA.indexOf(Os); if(iA<0)return; var MA=arrMat(ridA,diA); if(!MA)return;
        var kA=-1; for(var k=0;k<MA.length;k++){ if(MA[k][iA]!=null&&MA[k][iA]>=Tat+BOARD_BUF){kA=k;break;} } if(kA<0)return;
        for(var xA=iA+1;xA<stopsA.length;xA++){ if(MA[kA][xA]==null)continue; var X=stopsA[xA],tX=MA[kA][xA]; if(tX>maxEnd)break;
          var legA={type:'ride',rid:ridA,di:diA,k:kA,fromIdx:iA,toIdx:xA,from:Os,to:X,board:MA[kA][iA],alight:tX};
          var secs=[[X,0]]; var wl2=walkList(X,opt.maxWalkMin);
          for(var w2=0;w2<wl2.length&&w2<nbCap;w2++) secs.push([wl2[w2][0],wl2[w2][1]]);
          for(var si=0;si<secs.length;si++){
            var Ys=secs[si][0],wXY=secs[si][1],stY=DATA.stops[Ys]; if(!stY)continue;
            var tAtY=tX+wXY, need=wXY>0?tAtY:tAtY+BOARD_BUF;
            var midWalk = wXY>0?[{type:'walk',from:X,to:Ys,dep:tX,arr:tAtY,wm:wXY,dm:wXY*WALK_MPM}]:[];
            Object.keys(stY.routes).forEach(function(ridB){ stY.routes[ridB].forEach(function(diB){
              var stopsB=dirStops(ridB,diB),yB=stopsB.indexOf(Ys); if(yB<0)return;
              var dIdx=stopsB.indexOf(D); var endWalk=null, dB=-1;
              if(dIdx>yB){ dB=dIdx; }
              else if(opt.orWalk){ for(var zi=yB+1;zi<stopsB.length;zi++){ var Z=stopsB[zi],wd=distM(stC(Z),stC(D))/WALK_MPM; if(wd<=opt.maxWalkMin){ dB=zi; endWalk=[Z,wd]; break; } } }
              if(dB<0)return; var MB=arrMat(ridB,diB); if(!MB)return;
              var kB=-1,gamble=false;
              for(var kk=0;kk<MB.length;kk++){ if(MB[kk][yB]==null||MB[kk][dB]==null)continue;
                if(MB[kk][yB]>=need){kB=kk;break;}
                if(opt.gamble&&MB[kk][yB]>=need-opt.gambleMin){kB=kk;gamble=true;break;} }
              if(kB<0)return; var waitB=MB[kB][yB]-(tX+wXY);
              if(waitB>opt.maxTransferWait)return; var alightB=MB[kB][dB]; if(alightB>maxEnd)return;
              var legs=preWalk.concat([legA]).concat(midWalk).concat([{type:'ride',rid:ridB,di:diB,k:kB,fromIdx:yB,toIdx:dB,from:Ys,to:stopsB[dB],board:MB[kB][yB],alight:alightB}]);
              if(endWalk){ var Z2=endWalk[0],wm2=endWalk[1]; legs.push({type:'walk',from:Z2,to:D,dep:alightB,arr:alightB+wm2,wm:wm2,dm:wm2*WALK_MPM}); }
              var it=mkItin(legs,T0,gamble?'gamble':'transfer'); res.push(it);
            }); });
          }
        }
      }); });
    }
    return res;
  }
  function dijkstra(O,D,T0,opt){
    var best=new Map(),settled=new Set(),pq=[[T0,O]],maxEnd=T0+opt.maxTotal;
    best.set(O,{t:T0,leg:null});
    var guard=0;
    while(pq.length&&guard++<200000){
      pq.sort(function(a,b){return a[0]-b[0];}); var top=pq.shift(),ts=top[0],s=top[1];
      if(settled.has(s))continue; settled.add(s); if(s===D)break; if(ts>maxEnd)continue;
      var bs=best.get(s), cameWalk=bs&&bs.leg&&bs.leg.type==='walk';
      if(!cameWalk){ var wl=walkList(s,opt.maxWalkMin);
        for(var a=0;a<wl.length;a++){ var nb=wl[a][0],wm=wl[a][1]; if(settled.has(nb))continue; var cand=ts+wm;
          if(cand<=maxEnd&&(!best.has(nb)||cand<best.get(nb).t-1e-9)){ best.set(nb,{t:cand,leg:{type:'walk',from:s,to:nb,dep:ts,arr:cand,wm:wm,dm:wm*WALK_MPM}}); pq.push([cand,nb]); } } }
      var stn=DATA.stops[s]; if(!stn)continue;
      Object.keys(stn.routes).forEach(function(rid){ stn.routes[rid].forEach(function(di){
        var stops=dirStops(rid,di),i=stops.indexOf(s); if(i<0)return; var M=arrMat(rid,di); if(!M)return;
        var k=-1; for(var kk=0;kk<M.length;kk++){ if(M[kk][i]!=null&&M[kk][i]>=ts+BOARD_BUF){k=kk;break;} }
        if(k<0)return;
        if(s!==O&&(M[k][i]-ts)>opt.maxTransferWait)return; // transfer wait over threshold
        for(var j=i+1;j<stops.length;j++){ if(M[k][j]==null)continue; var nb2=stops[j]; if(settled.has(nb2))continue; var c2=M[k][j]; if(c2>maxEnd)continue;
          if(!best.has(nb2)||c2<best.get(nb2).t-1e-9){ best.set(nb2,{t:c2,leg:{type:'ride',rid:rid,di:di,k:k,fromIdx:i,toIdx:j,from:s,to:nb2,board:M[k][i],alight:c2}}); pq.push([c2,nb2]); } }
      }); });
    }
    if(!best.has(D))return null;
    var legs=[],cur=D,guard2=0;
    while(cur&&cur!==O&&guard2++<50){ var b=best.get(cur); if(!b||!b.leg)break; legs.unshift(b.leg); cur=b.leg.from; }
    if(cur!==O)return null;
    return mkItin(legs,T0,'dijkstra');
  }

  function dedupSort(list,opt){
    var seen={},out=[];
    for(var i=0;i<list.length;i++){ var it=list[i]; if(!it||it.total<=0)continue; if(it.total>opt.maxTotal+1)continue; if(seen[it.sig])continue; seen[it.sig]=1; out.push(it); }
    function key(it){
      if(opt.pref==='hub') return it.end-(it.tHub>=5?10:it.tHub>=3?5:0);
      if(opt.pref==='first') return it.tIdx*60+it.end;
      return it.end;
    }
    out.sort(function(a,b){ var d=key(a)-key(b); if(d)return d; if(a.transfers!==b.transfers)return a.transfers-b.transfers; return a.walkM-b.walkM; });
    return out;
  }

  function plan(){
    var O=(document.getElementById('plfrom').value||'').trim(), D=(document.getElementById('plto').value||'').trim();
    var T0=parseClock(document.getElementById('pltime').value);
    var msg=document.getElementById('plmsg'), res=document.getElementById('plres');
    msg.innerHTML=''; res.innerHTML=''; RESULTS=[]; SEL=-1; stopPlayback(); clearHighlight();
    if(!DATA.stops[O]||!DATA.stops[D]){ msg.innerHTML='<div class="plerr">请从下拉建议中选择有效的出发站与目的站。</div>'; return; }
    if(O===D){ msg.innerHTML='<div class="plerr">出发站与目的站相同。</div>'; return; }
    if(T0==null){ msg.innerHTML='<div class="plerr">请输入有效出发时刻（HH:MM）。</div>'; return; }
    var opt={maxWalkMin:+document.getElementById('plwalk').value,maxTransferWait:+document.getElementById('plwait').value,
      maxTotal:+document.getElementById('pltotal').value,gamble:document.getElementById('plgamble').checked,
      gambleMin:+document.getElementById('plgamblemin').value,orWalk:document.getElementById('plorwalk').checked,pref:PREF};
    document.getElementById('plgo').textContent='⏳ 规划中…';
    setTimeout(function(){
      var cands=[];
      try{ cands=planOD(O,D,T0,opt); }
      catch(e){ document.getElementById('plgo').textContent='🔍 规划路线'; msg.innerHTML='<div class="plerr">规划出错：'+String(e).slice(0,120)+'</div>'; return; }
      RESULTS=cands.slice(0,10);
      document.getElementById('plgo').textContent='🔍 规划路线';
      if(!RESULTS.length){
        var why='未找到可行方案。可能原因：① 该 OD 夜间无直接共线，且 15 分钟步行内无可接续的第二条线；② 到站时另一线<b>末班已收车</b>；③ 换乘候车或全程超过所设阈值。可尝试放宽「最长步行/候车/全程」、勾选「赌一把」或「步行接驳」，或改用邻近大站。';
        msg.innerHTML='<div class="plerr">'+why+'</div>'; return;
      }
      renderResults();
      selectItin(0);
    },20);
  }

  // ---------- rendering ----------
  function fmtDur(m){ m=Math.max(0,Math.round(m)); var h=Math.floor(m/60),mm=m%60; return h>0?(h+'小时'+(mm?mm+'分':'')):(mm+'分'); }
  function destName(rid,di){ var r=routeOf(rid); if(rid==='Y33')return di===0?'内圈':'外圈'; return '往'+r.dirs[di].to; }
  function legLineHTML(lg){
    var r=routeOf(lg.rid);
    if(lg.type==='ride'){
      var ci=crowdInfo(lg.ratio||0);
      return '<div class="itlg"><span class="dot" style="background:'+r.color+'"></span><span class="tx">'+
        '<b style="color:'+r.color+'">'+r.label+'</b> '+destName(lg.rid,lg.di)+
        ' <span class="mut">'+lg.from+' → '+lg.to+'（'+(lg.toIdx-lg.fromIdx)+'站）</span>'+
        '<span class="tag crowd"><span class="plcrowd" style="background:'+ci.color+'"></span>'+Math.round((lg.ratio||0)*100)+'% '+ci.label+'</span></span></div>';
    }
    return '<div class="itlg"><span class="dot" style="background:#6f7aa8"></span><span class="tx mut">🚶 步行 '+Math.round(lg.dm)+' m（约'+Math.max(1,Math.round(lg.wm))+'分）'+lg.from+'→'+lg.to+'</span></div>';
  }
  function flagTags(it){
    var h='';
    if(it.tag==='direct')h+='<span class="tag rec">直达</span>';
    if(it.flags.indexOf('gamble')>=0)h+='<span class="tag risk">赌一把·紧换乘</span>';
    if(it.flags.indexOf('lastbus')>=0)h+='<span class="tag last">末班车</span>';
    if(it.flags.indexOf('longwait')>=0)h+='<span class="tag wait">候车较长</span>';
    return h;
  }
  function renderResults(){
    var box=document.getElementById('plres'); document.getElementById('plreslabel').textContent='方案（'+RESULTS.length+'）';
    box.innerHTML=RESULTS.map(function(it,idx){
      var waitTxt=it.waits.length?it.waits.map(function(w){return w<0?'紧'+Math.abs(Math.round(w))+'分':('候'+Math.round(w)+'分');}).join(' · '):'';
      var legsHTML=it.legs.map(legLineHTML).join('');
      return '<div class="itcard" data-i="'+idx+'"><div class="ittop"><span class="ittime">'+fmtDur(it.total)+'</span>'+
        '<span class="itarr">'+fmtT(it.end)+' 到</span>'+
        '<span class="itmeta">'+it.transfers+'次换乘<br>¥'+it.fare+(it.walkM>0?' · 步'+Math.round(it.walkM)+'m':'')+'</span></div>'+
        '<div class="itlegs">'+legsHTML+'</div>'+
        '<div style="margin-top:6px;font-size:11px;color:#8b96c4">'+(waitTxt?'换乘 '+waitTxt:'')+(it.tStop&&it.transfers>0?(' · 换乘站 '+it.tStop+'（'+it.tHub+'线）'):'')+flagTags(it)+'</div></div>';
    }).join('');
    box.querySelectorAll('.itcard').forEach(function(c){ c.onclick=function(){ selectItin(+c.dataset.i); }; });
  }

  // ---------- map highlight & playback ----------
  function ensureLayer(){ if(!planLayer){ map.createPane('planPane'); map.getPane('planPane').style.zIndex=650; planLayer=L.layerGroup([],{pane:'planPane'}); planLayer.addTo(map); } return planLayer; }
  function dimBase(on){
    Object.keys(routeLayers).forEach(function(rid){ var g=routeLayers[rid]; if(!g)return; g.eachLayer(function(fg){ if(fg.eachLayer)fg.eachLayer(function(l){ if(l.setStyle)l.setStyle({opacity:on?0.07:0.85}); }); else if(fg.setStyle)fg.setStyle({opacity:on?0.07:0.85}); }); });
    baseDimmed=on;
  }
  function legCoords(rid,di,fromIdx,toIdx){
    var v=SCHED.dirs[rid+'|'+di]; if(!v)return [];
    var k0=v.stopKm[fromIdx],k1=v.stopKm[toIdx],pts=[];
    for(var i=0;i<v.frames.length;i++){ var fr=v.frames[i]; if(fr[4]>=k0-1e-6&&fr[4]<=k1+1e-6)pts.push(pt(fr[1],fr[2])); }
    if(pts.length<2){ var a=stC(dirStops(rid,di)[fromIdx]),b=stC(dirStops(rid,di)[toIdx]); if(a&&b)pts=[pt(a[0],a[1]),pt(b[0],b[1])]; }
    return pts;
  }
  function clearHighlight(){ if(planLayer)planLayer.clearLayers(); if(baseDimmed)dimBase(false); }
  function highlight(it){
    var L2=ensureLayer(); L2.clearLayers(); dimBase(true);
    it.legs.forEach(function(lg){
      if(lg.type==='ride'){ var r=routeOf(lg.rid),co=legCoords(lg.rid,lg.di,lg.fromIdx,lg.toIdx);
        if(co.length)L2.addLayer(L.polyline(co,{pane:'planPane',color:r.color,weight:7,opacity:0.95,lineJoin:'round'}));
      }else{ var a=stC(lg.from),b=stC(lg.to); if(a&&b)L2.addLayer(L.polyline([pt(a[0],a[1]),pt(b[0],b[1])],{pane:'planPane',color:'#9aa4cf',weight:4,opacity:0.8,dashArray:'6 7'})); }
    });
    // markers: origin / dest / transfers
    function pin(nm,color,txt){ var c=stC(nm); if(!c)return; var m=L.marker(pt(c[0],c[1]),{pane:'planPane',icon:L.divIcon({className:'jpin',iconSize:[18,18],iconAnchor:[9,9],html:'<div style="width:16px;height:16px;border-radius:50%;background:'+color+';border:2px solid #0b1020;box-shadow:0 0 0 2px '+color+'66"></div>'}),zIndexOffset:800}); m.bindTooltip(txt,{direction:'top',offset:[0,-10]}); L2.addLayer(m); }
    var O=it.legs.length?it.legs[0].from:null, Dl=it.legs[it.legs.length-1];
    if(O)pin(O,'#22c55e','出发 '+O);
    if(Dl)pin(Dl.to,'#ef4444','到达 '+Dl.to);
    it.legs.forEach(function(lg,i){ if(lg.type==='ride'&&i<it.legs.length-1){ var nx=it.legs[i+1]; if(nx&&nx.type==='ride')pin(lg.to,'#f59e0b','换乘 '+lg.to); } });
    var b=[]; it.legs.forEach(function(lg){ if(lg.type==='ride'){ var co=legCoords(lg.rid,lg.di,lg.fromIdx,lg.toIdx); co.forEach(function(p){b.push(p);}); } });
    if(b.length>1)map.fitBounds(L.latLngBounds(b),{padding:[60,60],maxZoom:15});
  }
  var jmark=null;
  function ensureMarker(){ var L2=ensureLayer(); if(!jmark||!L2.hasLayer(jmark)){ if(!jmark)jmark=L.marker([32.06,118.79],{pane:'planPane',zIndexOffset:900,icon:L.divIcon({className:'jmark',iconSize:[26,26],iconAnchor:[13,13],html:'<div style="font-size:22px;line-height:26px;text-align:center;filter:drop-shadow(0 2px 3px #000)">🧍</div>'})}); L2.addLayer(jmark); } return jmark; }
  function buildPhases(it){
    var ph=[],prev=it.start,cur=it.legs.length?it.legs[0].from:null;
    it.legs.forEach(function(lg){
      if(lg.type==='walk'){ if(lg.dep>prev+0.05)ph.push({type:'wait',t0:prev,t1:lg.dep,at:cur}); ph.push({type:'walk',t0:lg.dep,t1:lg.arr,from:lg.from,to:lg.to}); prev=lg.arr; cur=lg.to; }
      else{ if(lg.board>prev+0.05)ph.push({type:'wait',t0:prev,t1:lg.board,at:cur,rid:lg.rid,di:lg.di}); ph.push({type:'ride',t0:lg.board,t1:lg.alight,leg:lg}); prev=lg.alight; cur=lg.to; }
    });
    ph.push({type:'done',t0:prev,t1:prev+0.001,at:cur});
    return ph;
  }
  function phaseAt(ph,T){ for(var i=0;i<ph.length;i++){ if(T<ph[i].t1-1e-9)return ph[i]; } return ph[ph.length-1]; }
  function renderJourney(){
    if(!JT)return; var it=JT.itin,ph=JT.phases,T=JT.t,p=phaseAt(ph,T),m=ensureMarker(),st=document.getElementById('plstatus');
    var html='',el0=st0=null;
    if(p.type==='wait'){ var c=stC(p.at); if(c)m.setLatLng(pt(c[0],c[1])); var r=p.rid?routeOf(p.rid):null;
      html='<span class="big">🚏 在 '+p.at+' 候车</span> · 还有 '+Math.max(0,Math.round(p.t1-T))+' 分'+(r?('，乘 <b style="color:'+r.color+'">'+r.label+'</b> '+destName(p.rid,p.di)):'')+'<br><span class="sub">'+fmtT(T)+' · 全程 '+fmtDur(T-it.start)+' / '+fmtDur(it.total)+'</span>';
      m.setIcon(L.divIcon({className:'jmark',iconSize:[26,26],iconAnchor:[13,13],html:'<div style="font-size:22px;line-height:26px;text-align:center;filter:drop-shadow(0 2px 3px #000)">🧍</div>'}));
    } else if(p.type==='walk'){ var a=stC(p.from),b=stC(p.to),u=p.t1>p.t0?Math.max(0,Math.min(1,(T-p.t0)/(p.t1-p.t0))):1;
      if(a&&b)m.setLatLng(pt(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u));
      html='<span class="big">🚶 步行前往 '+p.to+'</span><br><span class="sub">'+fmtT(T)+' · 约 '+Math.round(u*100)+'% · 全程 '+fmtDur(T-it.start)+' / '+fmtDur(it.total)+'</span>';
      m.setIcon(L.divIcon({className:'jmark',iconSize:[26,26],iconAnchor:[13,13],html:'<div style="font-size:22px;line-height:26px;text-align:center;filter:drop-shadow(0 2px 3px #000)">🚶</div>'}));
    } else if(p.type==='ride'){ var lg=p.leg,key=lg.rid+'|'+lg.di,v=SCHED.dirs[key],pl=planFor(v,key,lg.k),el=T-v.deps[lg.k],q=posAt(v,el,pl);
      if(q)m.setLatLng(pt(q[0],q[1])); var rr=routeOf(lg.rid),stops=dirStops(lg.rid,lg.di),st2=pl?pl.st:v.stopT,ni=-1;
      for(var i=lg.fromIdx;i<=lg.toIdx;i++){ if(st2[i]>el+1e-9){ni=i;break;} }
      var nxt=ni>=0?stops[ni]:(lg.to+'（即将到达）'); var occ=0,cap=lg.cap; try{occ=paxPlan(v,key,lg.k,pl).occ[Math.max(lg.fromIdx,Math.min(lg.toIdx,(ni<0?lg.toIdx:ni)))]||0;}catch(e){}
      var ci=crowdInfo(cap?occ/cap:0);
      html='<span class="big"><span style="color:'+rr.color+'">🚌 '+rr.label+'</span> '+destName(lg.rid,lg.di)+'</span> · 下一站 '+nxt+'<br><span class="sub">'+fmtT(T)+' · 车载 <span class="plcrowd" style="background:'+ci.color+'"></span>'+occ+'/'+cap+'（'+ci.label+'）· 全程 '+fmtDur(T-it.start)+' / '+fmtDur(it.total)+'</span>';
      m.setIcon(L.divIcon({className:'jmark',iconSize:[26,26],iconAnchor:[13,13],html:'<div style="font-size:20px;line-height:26px;text-align:center;filter:drop-shadow(0 2px 3px #000)">🚌</div>'}));
    } else { var c2=stC(p.at); if(c2)m.setLatLng(pt(c2[0],c2[1]));
      html='<span class="big">🏁 已到达 '+p.at+'</span><br><span class="sub">'+fmtT(it.end)+' · 全程 '+fmtDur(it.total)+' · ¥'+it.fare+'</span>';
      m.setIcon(L.divIcon({className:'jmark',iconSize:[26,26],iconAnchor:[13,13],html:'<div style="font-size:22px;line-height:26px;text-align:center;filter:drop-shadow(0 2px 3px #000)">🏁</div>'}));
    }
    st.innerHTML=html;
    var span=it.end-it.start,fr=span>0?(T-it.start)/span:0; document.getElementById('plscrub').value=Math.round(fr*1000);
  }
  function pLoop(now){ if(!JT)return; var dt=Math.min(0.2,(now-pLast)/1000); pLast=now;
    if(JT.playing){ JT.t+=dt*JT.speed; if(JT.t>=JT.itin.end){ JT.t=JT.itin.end; JT.playing=false; document.getElementById('plpp').textContent='↻ 重播'; } }
    renderJourney(); requestAnimationFrame(pLoop);
  }
  function stopPlayback(){ if(JT){JT=null;} document.getElementById('plplay').classList.remove('on'); }
  function selectItin(i){
    if(i<0||i>=RESULTS.length)return; SEL=i; var it=RESULTS[i];
    document.querySelectorAll('#plres .itcard').forEach(function(c){ c.classList.toggle('sel',+c.dataset.i===i); });
    highlight(it);
    JT={itin:it,phases:buildPhases(it),t:it.start,playing:true,speed:+document.getElementById('plspeed').value};
    document.getElementById('plpp').textContent='⏸ 暂停';
    document.getElementById('plplay').classList.add('on'); renderJourney(); pLast=performance.now(); requestAnimationFrame(pLoop);
  }

  // ---------- controls ----------
  var PREF='fast';
  var STOP_NAMES=Object.keys(DATA.stops).sort();
  document.querySelectorAll('#plday button').forEach(function(b){ b.onclick=function(){ document.querySelectorAll('#plday button').forEach(function(x){x.classList.remove('on');}); b.classList.add('on'); if(typeof setDayType==='function')setDayType(b.dataset.dt); clearArrCache(); if(RESULTS.length)plan(); }; });
  document.querySelectorAll('#plpref button').forEach(function(b){ b.onclick=function(){ document.querySelectorAll('#plpref button').forEach(function(x){x.classList.remove('on');}); b.classList.add('on'); PREF=b.dataset.pf; if(RESULTS.length){ RESULTS=dedupSort(RESULTS.slice(),{pref:PREF}); renderResults(); selectItin(0);} }; });
  function bindRange(id,vid){ var e=document.getElementById(id),v=document.getElementById(vid); e.oninput=function(){ v.textContent=e.value; }; }
  bindRange('plwalk','plwalkv'); bindRange('plwait','plwaitv'); bindRange('pltotal','pltotalv'); bindRange('plgamblemin','plgambleminv');
  document.getElementById('plgamble').onchange=function(e){ document.getElementById('plgamblerow').style.display=e.target.checked?'flex':'none'; };
  document.getElementById('plgo').onclick=plan;
  document.getElementById('plreset').onclick=function(){ document.getElementById('plres').innerHTML=''; document.getElementById('plmsg').innerHTML=''; RESULTS=[];SEL=-1; stopPlayback(); clearHighlight(); if(jmark){try{map.removeLayer(jmark);}catch(e){} jmark=null;} if(pickMark){try{map.removeLayer(pickMark);}catch(e){} pickMark=null;} if(typeof disarmPick==='function')disarmPick(); };
  document.getElementById('plpp').onclick=function(){ if(!JT)return; if(JT.t>=JT.itin.end){ JT.t=JT.start; JT.playing=true; document.getElementById('plpp').textContent='⏸ 暂停'; } else { JT.playing=!JT.playing; document.getElementById('plpp').textContent=JT.playing?'⏸ 暂停':'▶ 播放'; } };
  document.getElementById('plspeed').onchange=function(e){ if(JT)JT.speed=+e.target.value; };
  document.getElementById('plscrub').oninput=function(e){ if(!JT)return; var it=JT.itin; JT.t=it.start+(it.end-it.start)*(+e.target.value/1000); JT.playing=false; document.getElementById('plpp').textContent='▶ 播放'; renderJourney(); };

  // ---------- station autocomplete (replaces the laggy native <datalist>) ----------
  var acBox=document.createElement('div'); acBox.id='plac'; document.body.appendChild(acBox);
  var acInput=null, acItems=[], acIdx=-1;
  function acMatch(q){
    q=(q||'').trim();
    if(!q) return STOP_NAMES.slice(0,40);
    var pre=[],sub=[];
    for(var i=0;i<STOP_NAMES.length;i++){ var nm=STOP_NAMES[i];
      if(nm.indexOf(q)===0) pre.push(nm); else if(nm.indexOf(q)>0) sub.push(nm);
    }
    return pre.concat(sub).slice(0,40);
  }
  function acRender(){
    var q=(acInput&&acInput.value||'').trim();
    acItems=acMatch(q); acIdx=-1;
    if(!acItems.length){ acBox.innerHTML='<div class="acnone">无匹配站点</div>'; return; }
    var h='';
    for(var i=0;i<acItems.length;i++){ var nm=acItems[i];
      var esc=nm.replace(/&/g,'&amp;').replace(/</g,'&lt;'); var hi=esc;
      if(q){ var p=nm.indexOf(q); if(p>=0) hi=esc.slice(0,p)+'<span class="hl">'+esc.slice(p,p+q.length)+'</span>'+esc.slice(p+q.length); }
      h+='<div class="acit" data-nm="'+esc+'">'+hi+'</div>';
    }
    h+='<div class="acsub">'+(acItems.length>=40?'仅列前 40 条，继续输入可缩小范围 · ':'')+'↑↓ 选择 · 回车确认</div>';
    acBox.innerHTML=h;
    var els=acBox.querySelectorAll('.acit');
    for(var j=0;j<els.length;j++){ (function(el){ el.onmousedown=function(e){ if(e&&e.preventDefault)e.preventDefault(); acChoose(el.getAttribute('data-nm')); }; })(els[j]); }
  }
  function acPosition(){ if(!acInput)return; var r=acInput.getBoundingClientRect(); acBox.style.left=r.left+'px'; acBox.style.top=(r.bottom+3)+'px'; acBox.style.width=r.width+'px'; }
  function acOpen(inp){ acInput=inp; acRender(); acPosition(); acBox.style.display='block'; }
  function acClose(){ acBox.style.display='none'; acInput=null; acIdx=-1; }
  function acChoose(nm){ if(!acInput||!nm)return; acInput.value=nm; acClose(); }
  function acMove(d){ var els=acBox.querySelectorAll('.acit'); if(!els.length)return; acIdx=(acIdx+d+els.length)%els.length; for(var i=0;i<els.length;i++) els[i].classList.toggle('act',i===acIdx); try{els[acIdx].scrollIntoView({block:'nearest'});}catch(e){} }
  function bindAC(inp){
    if(!inp)return;
    inp.addEventListener('focus',function(){ acOpen(inp); });
    inp.addEventListener('click',function(){ if(acBox.style.display!=='block')acOpen(inp); });
    inp.addEventListener('input',function(e){ if(e&&e.isComposing)return; acOpen(inp); });
    inp.addEventListener('compositionend',function(){ acOpen(inp); });
    inp.addEventListener('keydown',function(e){
      if(acBox.style.display!=='block'||acInput!==inp)return;
      var k=e.key;
      if(k==='ArrowDown'){ if(e.preventDefault)e.preventDefault(); acMove(1); }
      else if(k==='ArrowUp'){ if(e.preventDefault)e.preventDefault(); acMove(-1); }
      else if(k==='Enter'){ if(acIdx>=0){ if(e.preventDefault)e.preventDefault(); acChoose(acItems[acIdx]); } else if(acItems.length===1){ if(e.preventDefault)e.preventDefault(); acChoose(acItems[0]); } }
      else if(k==='Escape'){ acClose(); }
    });
    inp.addEventListener('blur',function(){ setTimeout(function(){ if(acInput===inp)acClose(); },120); });
  }
  bindAC(document.getElementById('plfrom'));
  bindAC(document.getElementById('plto'));
  var plbodyEl=document.getElementById('plbody'); if(plbodyEl)plbodyEl.addEventListener('scroll',function(){ if(acBox.style.display==='block')acPosition(); });

  // ---------- map point-picking for origin / destination ----------
  var pickTarget=null, pickMark=null;
  var plhint=document.getElementById('plhint');
  var pickBtn={from:document.getElementById('pickfrom'),to:document.getElementById('pickto')};
  var pickInp={from:document.getElementById('plfrom'),to:document.getElementById('plto')};
  function setHint(h){ if(plhint)plhint.innerHTML=h||''; }
  function disarmPick(){ pickTarget=null; if(pickBtn.from)pickBtn.from.classList.remove('armed'); if(pickBtn.to)pickBtn.to.classList.remove('armed'); try{map.getContainer().style.cursor='';}catch(e){} setHint(''); }
  function armPick(w){ if(pickTarget===w){ disarmPick(); return; } pickTarget=w; if(pickBtn.from)pickBtn.from.classList.toggle('armed',w==='from'); if(pickBtn.to)pickBtn.to.classList.toggle('armed',w==='to'); try{map.getContainer().style.cursor='crosshair';}catch(e){} setHint('📍 在地图上点击选择<b>'+(w==='from'?'出发':'目的')+'</b>位置…（Esc 取消）'); }
  function nearestStop(lat,lng){ var best=null,bd=1e18; for(var i=0;i<STOP_NAMES.length;i++){ var nm=STOP_NAMES[i],c=stC(nm); if(!c)continue; var d=distM([lat,lng],c); if(d<bd){bd=d;best=nm;} } return best?{name:best,d:bd}:null; }
  map.on('click',function(e){
    if(!pickTarget)return;
    var w=(typeof toWgs==='function')?toWgs(e.latlng.lat,e.latlng.lng):[e.latlng.lat,e.latlng.lng];
    var ns=nearestStop(w[0],w[1]); if(!ns)return;
    var which=pickTarget;
    if(pickInp[which])pickInp[which].value=ns.name;
    try{ if(pickMark){map.removeLayer(pickMark);} var gp=pt(w[0],w[1]); pickMark=L.marker(gp,{pane:'planPane',zIndexOffset:800,icon:L.divIcon({className:'pickmark',iconSize:[24,24],iconAnchor:[12,12],html:'<div style="font-size:20px;line-height:24px;text-align:center;filter:drop-shadow(0 2px 3px #000)">📍</div>'})}); ensureLayer().addLayer(pickMark); }catch(err){}
    disarmPick();
    setHint('📍 已取点 → 吸附最近站点 <b>'+ns.name+'</b>（'+(which==='from'?'出发':'目的')+'，直线约 '+Math.round(ns.d)+' 米）');
  });
  if(pickBtn.from)pickBtn.from.onclick=function(){ armPick('from'); };
  if(pickBtn.to)pickBtn.to.onclick=function(){ armPick('to'); };
  document.addEventListener('keydown',function(e){ if(e&&e.key==='Escape'&&pickTarget)disarmPick(); });

  // sensible defaults in the pickers
  document.getElementById('plfrom').value='新街口南';
  document.getElementById('plto').value='建康路·夫子庙';
 }catch(err){ var m=document.getElementById('plmsg'); if(m)m.innerHTML='<div class="plerr">规划器初始化失败：'+String(err).slice(0,200)+'</div>'; }
})();
'''

out = (base
       .replace('<body>', '<body class="planner">')
       .replace('</head>', CSS + '</head>')
       .replace('</body>', HTML + '<script>' + JS + '</script></body>'))

path = os.path.join(ROOT, 'planner.html')
open(path, 'w', encoding='utf-8').write(out)
print('planner.html written,', len(out) // 1024, 'KB')
