// ============================================================================
// /interface/{channelId} — full draggable widget interface served by EBS.
//
// ISOLATED PAGE. Does NOT share code with:
//   - overlay/                     (local OBS overlay; ws://127.0.0.1:8765/ws)
//   - twitch_extension/frontend/   (real Twitch extension; PubSub + JWT WSS)
//
// All visual / behavior changes here MUST stay inside this file.
// ============================================================================

export const INTERFACE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ASCIIMUD — Live Interface</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-user-select:none;user-select:none}
html,body{width:100%;height:100%;overflow:hidden;background:#06070a;
  font-family:'Consolas','Menlo',monospace;color:#cabd9a}
#stage{position:fixed;inset:0}

/* ---------- map background layer ---------- */
#mapWrap{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:#0a0805}
#mapImg{max-width:100%;max-height:100%;opacity:.85;filter:saturate(.8) brightness(.95);transition:opacity .4s}
#mapDot{position:absolute;width:18px;height:18px;border-radius:50%;
  background:#ff3838;border:2px solid #fff;box-shadow:0 0 14px #ff3838aa,0 0 30px #ff383844;
  transform:translate(-50%,-50%);pointer-events:none;
  transition:left .8s ease,top .8s ease,background .2s,box-shadow .2s;z-index:5}
#mapDot.combat{background:#ff1010;box-shadow:0 0 18px #ff1010cc,0 0 40px #ff101055}
#mapDot.dead{background:#444;border-color:#888;box-shadow:none}
#mapArrow{position:absolute;width:0;height:0;border-left:7px solid transparent;
  border-right:7px solid transparent;border-bottom:14px solid #fff;
  transform:translate(-50%,-100%) rotate(0deg);transform-origin:50% 100%;
  pointer-events:none;z-index:6;transition:transform .4s ease,left .8s ease,top .8s ease;
  filter:drop-shadow(0 0 4px #000)}
#vignette{position:absolute;inset:0;pointer-events:none;z-index:6;
  box-shadow:inset 0 0 0 0 transparent;transition:box-shadow .25s}
body[data-combat="1"] #vignette{box-shadow:inset 0 0 80px 8px #ff1010aa}

/* ---------- stale-data overlay ---------- */
#stale{position:fixed;inset:0;display:none;align-items:center;justify-content:center;
  z-index:50;background:rgba(0,0,0,.55);font-size:1.4rem;color:#ffae3a;pointer-events:none}
body.stale #stale{display:flex}
body.stale #stage{filter:saturate(.4) brightness(.55)}

/* ---------- toolbar ---------- */
#toolbar{position:fixed;top:8px;left:50%;transform:translateX(-50%);z-index:30;
  background:rgba(8,10,16,.85);border:1px solid #2a2a3a;border-radius:6px;
  padding:6px 10px;display:flex;gap:8px;align-items:center;font-size:.72rem;color:#9d8e6b}
#toolbar button{background:#161823;border:1px solid #2a2a3a;color:#cabd9a;
  padding:4px 9px;border-radius:3px;cursor:pointer;font:inherit}
#toolbar button:hover{background:#222637;color:#fff}
#toolbar button.active{background:#3a2a18;border-color:#7a5a18;color:#ffd07a}
#toolbar #connState{padding:0 4px;color:#88ff88}
#toolbar #connState.bad{color:#ff5555}

/* ---------- widgets ---------- */
.widget{position:absolute;background:rgba(10,11,16,.92);border:1px solid #2c2c3c;
  border-radius:5px;color:#d6c89e;font-size:.78rem;min-width:140px;min-height:60px;
  z-index:10;display:flex;flex-direction:column;backdrop-filter:blur(2px);
  box-shadow:0 4px 18px rgba(0,0,0,.5)}
.widget.dragging{z-index:25;border-color:#d4a955}
.widget .head{cursor:move;background:#1a1c28;border-bottom:1px solid #2c2c3c;
  padding:3px 8px;font-size:.65rem;letter-spacing:.18em;color:#7d6f4d;
  display:flex;justify-content:space-between;align-items:center;border-radius:5px 5px 0 0}
.widget .head .title{flex:1;text-transform:uppercase}
.widget .head .x{cursor:pointer;color:#5a4e38;padding:0 4px}
.widget .head .x:hover{color:#ff5555}
.widget .body{flex:1;padding:8px 10px;overflow:hidden}
body.locked .widget .head{cursor:default}
body.locked .widget .head .x{display:none}
body.locked .widget{box-shadow:none}
.widget .resize{position:absolute;right:0;bottom:0;width:14px;height:14px;cursor:se-resize;
  background:linear-gradient(135deg,transparent 50%,#3a3a4a 50%,#3a3a4a 70%,transparent 70%);
  border-radius:0 0 5px 0}
body.locked .widget .resize{display:none}

.row{display:flex;justify-content:space-between;align-items:center;margin:2px 0;gap:6px}
.row .lbl{color:#7d6f4d;font-size:.66rem;letter-spacing:.1em;text-transform:uppercase}
.row .val{color:#e6d8ac;font-variant-numeric:tabular-nums}
.bar{position:relative;height:8px;background:#1a1c28;border:1px solid #2c2c3c;border-radius:2px;
  overflow:hidden;margin:3px 0 5px}
.bar > .fill{position:absolute;inset:0;width:0%;background:#5fbf5f;
  transition:width .35s ease,background .25s}
.bar > .fill[data-tier="mid"]{background:#d4a93a}
.bar > .fill[data-tier="low"]{background:#d44a3a;animation:lowpulse 1s ease-in-out infinite}
@keyframes lowpulse{50%{opacity:.55}}
.bar.mp > .fill{background:#3a78d4}
.bar.tgt > .fill[data-faction="hostile"]{background:#d44a3a}
.bar.tgt > .fill[data-faction="friendly"]{background:#5fbf5f}
.bar.cast > .fill{background:#b87adf;transition:width .12s linear}
.bar.xp > .fill{background:#aa66ff}
.flash-hp{animation:hpflash .6s ease}
@keyframes hpflash{0%{box-shadow:0 0 0 0 #ff3838}50%{box-shadow:0 0 0 6px #ff383800}100%{box-shadow:0 0 0 0 transparent}}

#w-sev .body{display:flex;align-items:center;justify-content:center;font-size:1.4rem;font-weight:bold;
  letter-spacing:.18em;height:100%}
#w-sev[data-sev="0"] .body{color:#5fbf5f}
#w-sev[data-sev="1"] .body{color:#a8c93a}
#w-sev[data-sev="2"] .body{color:#d4a93a}
#w-sev[data-sev="3"] .body{color:#e07520;text-shadow:0 0 8px #e07520aa}
#w-sev[data-sev="4"] .body{color:#ff2020;text-shadow:0 0 12px #ff2020;animation:lowpulse .8s ease-in-out infinite}

#w-id .name{font-size:1rem;color:#ffd87a;letter-spacing:.05em}
#w-id .sub{font-size:.7rem;color:#7d6f4d;margin-top:1px}
#w-id .xpwrap{margin-top:6px}

#w-state .pills{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
.pill{padding:1px 6px;border-radius:8px;background:#1a1c28;color:#7d6f4d;
  font-size:.6rem;letter-spacing:.08em;border:1px solid #2c2c3c}
.pill.on{background:#3a2a18;color:#ffd07a;border-color:#7a5a18}

#w-coords .compass{display:inline-block;width:28px;height:28px;border:1px solid #2c2c3c;
  border-radius:50%;position:relative;background:#1a1c28;flex:0 0 auto}

#w-zone .body{font-size:1rem;color:#d4a955;letter-spacing:.04em}
#w-quest .body{color:#7d6f4d;font-style:italic;font-size:.72rem}

#w-conn .body{display:flex;align-items:center;gap:6px}
#w-conn .led{width:10px;height:10px;border-radius:50%;background:#5fbf5f;box-shadow:0 0 8px #5fbf5f}
body.stale #w-conn .led{background:#ff3838;box-shadow:0 0 8px #ff3838}

#w-buffs .icons,#w-debuffs .icons,#w-action .icons{display:flex;flex-wrap:wrap;gap:4px}
.icn{width:30px;height:30px;background:#1a1c28;border:1px solid #2c2c3c;border-radius:3px;
  font-size:.55rem;color:#7d6f4d;display:flex;align-items:center;justify-content:center;
  font-variant-numeric:tabular-nums}
.icn.cd{background:#3a1818;color:#ff8888}
.icn.empty{opacity:.3}

@media (max-width:780px){
  .widget{min-width:110px;font-size:.7rem}
  #toolbar{font-size:.62rem;padding:4px 6px}
}
</style>
</head>
<body data-combat="0">

<div id="stage">
  <div id="mapWrap">
    <img id="mapImg" alt="" onerror="this.style.display='none'">
    <div id="mapDot" style="left:50%;top:50%"></div>
    <div id="mapArrow" style="left:50%;top:50%"></div>
  </div>
  <div id="vignette"></div>
</div>

<div id="toolbar">
  <span id="connState">&bull; LIVE</span>
  <button id="btnLock">Lock layout</button>
  <button id="btnReset">Reset</button>
  <button id="btnDock">Hidden ▾</button>
</div>

<div id="stale">📡 Connection lost — waiting for data&hellip;</div>

<div class="widget" id="w-zone"   data-w="zone"     data-default="left:24px;top:60px;width:220px;height:62px"><div class="head"><span class="title">Zone</span><span class="x">×</span></div><div class="body">—</div><div class="resize"></div></div>

<div class="widget" id="w-id"     data-w="identity" data-default="left:24px;top:130px;width:220px;height:108px"><div class="head"><span class="title">Identity</span><span class="x">×</span></div><div class="body">
  <div class="name" id="idName">—</div>
  <div class="sub" id="idSub">—</div>
  <div class="xpwrap"><div class="row"><span class="lbl">XP</span><span class="val" id="idXp">— %</span></div><div class="bar xp"><div class="fill" id="idXpFill"></div></div></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-vitals" data-w="vitals"   data-default="left:24px;top:248px;width:240px;height:140px"><div class="head"><span class="title">Vitals</span><span class="x">×</span></div><div class="body">
  <div class="row"><span class="lbl">HP</span><span class="val" id="hpVal">— / —</span></div>
  <div class="bar"><div class="fill" id="hpFill"></div></div>
  <div class="row"><span class="lbl" id="mpLbl">Mana</span><span class="val" id="mpVal">— / —</span></div>
  <div class="bar mp"><div class="fill" id="mpFill"></div></div>
  <div class="row"><span class="lbl">Combo</span><span class="val" id="comboVal">0</span></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-cast"   data-w="cast"     data-default="left:24px;top:398px;width:240px;height:74px"><div class="head"><span class="title">Casting</span><span class="x">×</span></div><div class="body">
  <div class="row"><span class="lbl">Spell</span><span class="val" id="castName">—</span></div>
  <div class="bar cast"><div class="fill" id="castFill"></div></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-target" data-w="target"   data-default="right:24px;top:60px;width:240px;height:128px"><div class="head"><span class="title">Target</span><span class="x">×</span></div><div class="body">
  <div class="row"><span class="lbl" id="tgtLabel">No target</span><span class="val" id="tgtMeta">—</span></div>
  <div class="bar tgt"><div class="fill" id="tgtFill"></div></div>
  <div class="row"><span class="lbl">Cast</span><span class="val" id="tgtCastName">—</span></div>
  <div class="bar cast"><div class="fill" id="tgtCastFill"></div></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-sev"    data-w="sev"      data-default="right:24px;top:198px;width:140px;height:80px" data-sev="0"><div class="head"><span class="title">Severity</span><span class="x">×</span></div><div class="body">SEV 0</div><div class="resize"></div></div>

<div class="widget" id="w-state"  data-w="state"    data-default="right:24px;top:288px;width:240px;height:90px"><div class="head"><span class="title">State</span><span class="x">×</span></div><div class="body">
  <div class="pills" id="statePills"></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-bag"    data-w="bag"      data-default="right:24px;top:388px;width:140px;height:74px"><div class="head"><span class="title">Bag</span><span class="x">×</span></div><div class="body">
  <div class="row"><span class="lbl">Free</span><span class="val" id="bagFree">—</span></div>
  <div class="row"><span class="lbl">Status</span><span class="val" id="bagStatus">—</span></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-wallet" data-w="wallet"   data-default="right:174px;top:388px;width:160px;height:74px"><div class="head"><span class="title">Wallet</span><span class="x">×</span></div><div class="body">
  <div class="row"><span class="val" id="walletGold" style="color:#ffd87a">0g</span></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-dura"   data-w="dura"     data-default="right:24px;top:472px;width:200px;height:60px"><div class="head"><span class="title">Durability</span><span class="x">×</span></div><div class="body">
  <div class="row"><span class="lbl">Gear</span><span class="val" id="duraVal">— %</span></div>
  <div class="bar"><div class="fill" id="duraFill"></div></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-coords" data-w="coords"   data-default="left:24px;top:482px;width:240px;height:74px"><div class="head"><span class="title">Position</span><span class="x">×</span></div><div class="body">
  <div class="row"><span class="lbl">Map</span><span class="val" id="coordsVal">—,—</span><span class="compass" id="compass" title="facing"></span></div>
</div><div class="resize"></div></div>

<div class="widget" id="w-conn"   data-w="conn"     data-default="left:50%;top:566px;width:160px;height:60px"><div class="head"><span class="title">Stream</span><span class="x">×</span></div><div class="body">
  <span class="led"></span><span id="connText">live</span>
  <span class="val" id="tickVal" style="margin-left:auto;color:#7d6f4d">tick —</span>
</div><div class="resize"></div></div>

<div class="widget" id="w-buffs"  data-w="buffs"    data-default="left:280px;top:248px;width:170px;height:74px"><div class="head"><span class="title">Buffs</span><span class="x">×</span></div><div class="body"><div class="icons" id="buffIcons"></div></div><div class="resize"></div></div>
<div class="widget" id="w-debuffs" data-w="debuffs"  data-default="left:280px;top:332px;width:170px;height:74px"><div class="head"><span class="title">Debuffs</span><span class="x">×</span></div><div class="body"><div class="icons" id="debuffIcons"></div></div><div class="resize"></div></div>
<div class="widget" id="w-action" data-w="action"   data-default="left:280px;top:416px;width:380px;height:74px"><div class="head"><span class="title">Action Bar</span><span class="x">×</span></div><div class="body"><div class="icons" id="actionIcons"></div></div><div class="resize"></div></div>

<div class="widget" id="w-quest"  data-w="quest"    data-default="left:280px;top:160px;width:280px;height:80px"><div class="head"><span class="title">Quest</span><span class="x">×</span></div><div class="body">
  No quest data &mdash; addon update pending (Phase&nbsp;B).
</div><div class="resize"></div></div>

<script>
'use strict';
const CHANNEL_ID = "__CHANNEL_ID__";
const ZONES = __ZONE_DATA__;
const STORE_KEY = "asciimud.interface.layout.v1";
const STALE_AFTER_MS = 8000;

let lastUpdate = 0, lastZoneHash = null, lastZoneId = null, lastHp = null;
let prevHpFlashAt = 0;

function loadLayout(){
  try{ return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; }
  catch(_){ return {}; }
}
function saveLayout(){
  const out = {};
  document.querySelectorAll('.widget').forEach(w=>{
    out[w.dataset.w] = {
      left: w.style.left || '', top: w.style.top || '', right: w.style.right || '',
      width: w.style.width || '', height: w.style.height || '',
      hidden: w.dataset.hidden === '1',
    };
  });
  out.__locked = document.body.classList.contains('locked');
  localStorage.setItem(STORE_KEY, JSON.stringify(out));
}
function applyDefaults(w){
  w.style.left=''; w.style.top=''; w.style.right=''; w.style.width=''; w.style.height='';
  (w.dataset.default||'').split(';').forEach(p=>{
    const i = p.indexOf(':');
    if(i<0) return;
    const k = p.slice(0,i).trim(), v = p.slice(i+1).trim();
    if(k && v) w.style[k] = v;
  });
}
function applyLayout(){
  const saved = loadLayout();
  document.querySelectorAll('.widget').forEach(w=>{
    applyDefaults(w);
    const s = saved[w.dataset.w];
    if(!s) return;
    if(s.left)   { w.style.left = s.left; w.style.right=''; }
    if(s.top)    w.style.top    = s.top;
    if(s.right)  { w.style.right = s.right; w.style.left=''; }
    if(s.width)  w.style.width  = s.width;
    if(s.height) w.style.height = s.height;
    if(s.hidden) hideWidget(w);
  });
  if(saved.__locked){
    document.body.classList.add('locked');
    document.getElementById('btnLock').classList.add('active');
    document.getElementById('btnLock').textContent='Unlock layout';
  }
  refreshDock();
}
function resetLayout(){
  localStorage.removeItem(STORE_KEY);
  document.body.classList.remove('locked');
  document.getElementById('btnLock').classList.remove('active');
  document.getElementById('btnLock').textContent='Lock layout';
  document.querySelectorAll('.widget').forEach(w=>{
    delete w.dataset.hidden; w.style.display='';
    applyDefaults(w);
  });
  refreshDock();
}

function makeDraggable(w){
  const head = w.querySelector('.head');
  const resize = w.querySelector('.resize');
  let mode=null, startX=0, startY=0, baseL=0, baseT=0, baseW=0, baseH=0;

  head.addEventListener('pointerdown',(e)=>{
    if(document.body.classList.contains('locked')) return;
    if(e.target.classList.contains('x')) return;
    mode='drag';
    const r = w.getBoundingClientRect();
    w.style.right=''; w.style.left=r.left+'px'; w.style.top=r.top+'px';
    startX=e.clientX; startY=e.clientY; baseL=r.left; baseT=r.top;
    w.classList.add('dragging'); head.setPointerCapture(e.pointerId);
  });
  head.addEventListener('pointermove',(e)=>{
    if(mode!=='drag') return;
    w.style.left=Math.max(0, baseL + e.clientX-startX)+'px';
    w.style.top =Math.max(0, baseT + e.clientY-startY)+'px';
  });
  head.addEventListener('pointerup',()=>{
    if(mode!=='drag') return;
    mode=null; w.classList.remove('dragging'); saveLayout();
  });

  resize.addEventListener('pointerdown',(e)=>{
    if(document.body.classList.contains('locked')) return;
    e.stopPropagation(); mode='resize';
    const r = w.getBoundingClientRect();
    startX=e.clientX; startY=e.clientY; baseW=r.width; baseH=r.height;
    resize.setPointerCapture(e.pointerId);
  });
  resize.addEventListener('pointermove',(e)=>{
    if(mode!=='resize') return;
    w.style.width =Math.max(110, baseW + e.clientX-startX)+'px';
    w.style.height=Math.max(50,  baseH + e.clientY-startY)+'px';
  });
  resize.addEventListener('pointerup',()=>{
    if(mode!=='resize') return;
    mode=null; saveLayout();
  });

  w.querySelector('.head .x').addEventListener('click',()=>{
    if(document.body.classList.contains('locked')) return;
    hideWidget(w); saveLayout(); refreshDock();
  });
}
function hideWidget(w){ w.style.display='none'; w.dataset.hidden='1'; }
function showWidget(w){ w.style.display=''; delete w.dataset.hidden; }

function refreshDock(){
  const hidden = Array.from(document.querySelectorAll('.widget')).filter(w=>w.dataset.hidden==='1');
  const btn = document.getElementById('btnDock');
  btn.textContent = hidden.length ? 'Hidden ('+hidden.length+') ▾' : 'Hidden ▾';
  btn.disabled = hidden.length === 0;
  btn.style.opacity = hidden.length === 0 ? .4 : 1;
}
document.getElementById('btnDock').addEventListener('click',()=>{
  const hidden = Array.from(document.querySelectorAll('.widget')).filter(w=>w.dataset.hidden==='1');
  if(!hidden.length) return;
  const names = hidden.map(w=>w.dataset.w).join(', ');
  const pick = prompt('Show which widget? ('+names+', or "all")');
  if(!pick) return;
  hidden.forEach(w=>{
    if(pick==='all' || w.dataset.w===pick.trim().toLowerCase()) showWidget(w);
  });
  saveLayout(); refreshDock();
});
document.getElementById('btnLock').addEventListener('click',()=>{
  const on = document.body.classList.toggle('locked');
  document.getElementById('btnLock').classList.toggle('active', on);
  document.getElementById('btnLock').textContent = on ? 'Unlock layout' : 'Lock layout';
  saveLayout();
});
document.getElementById('btnReset').addEventListener('click',()=>{
  if(confirm('Reset all widgets to default positions?')) resetLayout();
});

function tier(pct){ return pct>=60?'good':(pct>=30?'mid':'low'); }
function setBar(fill, pct, faction){
  fill.style.width = (pct||0)+'%';
  fill.dataset.tier = tier(pct||0);
  if(faction) fill.dataset.faction = faction;
}
function deriveSeverity(s){
  if(!s||!s.player) return 0;
  const hp = s.player.hpPct;
  if(hp == null) return 0;
  if(hp <= 15) return 4;
  if(hp <= 30) return 3;
  if(hp <= 50 && s.combat) return 2;
  if(s.combat) return 1;
  return 0;
}
function spellLink(id, label){
  if(!id) return '<span class="icn empty">—</span>';
  return '<a class="icn" target="_blank" rel="noopener" href="https://www.wowhead.com/classic/spell='+id+'" title="Spell '+id+'" style="text-decoration:none;color:#9ed4ff">'+(label||id)+'</a>';
}

function renderSnapshot(snap){
  if(!snap || snap.t !== 'snapshot') return;
  const s = snap.data || {};
  const p = s.player || {};
  const z = s.zone || {};
  const t = s.target;

  const zi = ZONES[z.hash] || {};
  const zoneName = zi.name || (z.hash ? 'Unknown (0x'+z.hash.toString(16).toUpperCase()+')' : '—');
  if(z.hash !== lastZoneHash){
    lastZoneHash = z.hash;
    if(zi.zoneId && zi.zoneId !== lastZoneId){
      lastZoneId = zi.zoneId;
      const img = document.getElementById('mapImg');
      img.style.display=''; img.src='https://wow.zamimg.com/images/wow/maps/enus/zoom/'+zi.zoneId+'.jpg';
    } else if(!zi.zoneId){
      const img = document.getElementById('mapImg'); img.style.display='none'; img.removeAttribute('src');
      lastZoneId = null;
    }
  }
  const dot = document.getElementById('mapDot');
  const arrow = document.getElementById('mapArrow');
  if(z.mapX != null){ dot.style.left = (z.mapX/255*100).toFixed(2)+'%'; arrow.style.left = dot.style.left; }
  if(z.mapY != null){ dot.style.top  = (z.mapY/255*100).toFixed(2)+'%'; arrow.style.top  = dot.style.top; }
  dot.classList.toggle('combat', !!s.combat);
  dot.classList.toggle('dead', p.hp === 0);
  if(z.facing != null){
    arrow.style.transform = 'translate(-50%,-100%) rotate('+(z.facing/255*360)+'deg)';
  }

  document.querySelector('#w-zone .body').textContent = zoneName;

  document.getElementById('idName').textContent = (p.race||'?')+' '+(p.class||'?');
  document.getElementById('idSub').textContent  = 'Level '+(p.level||'?')+'  '+(p.faction||'') + (p.gender? '  '+p.gender : '');
  document.getElementById('idXp').textContent   = (p.xpPct||0)+' %' + (p.restedXp ? '  ★' : '');
  setBar(document.getElementById('idXpFill'), p.xpPct||0);

  document.getElementById('hpVal').textContent = (p.hp||0)+' / '+(p.hpMax||0);
  setBar(document.getElementById('hpFill'), p.hpPct||0);
  if(lastHp != null && p.hpPct != null && (lastHp - p.hpPct) >= 10 && (Date.now()-prevHpFlashAt > 600)){
    const bar = document.getElementById('hpFill').parentElement;
    bar.classList.remove('flash-hp'); void bar.offsetWidth; bar.classList.add('flash-hp');
    prevHpFlashAt = Date.now();
  }
  lastHp = p.hpPct;
  document.getElementById('mpLbl').textContent = (p.powerType||'Mana');
  document.getElementById('mpVal').textContent = (p.mp||0)+' / '+(p.mpMax||0);
  setBar(document.getElementById('mpFill'), p.mpPct||0);
  document.getElementById('comboVal').textContent = p.comboPoints||0;

  const cn = document.getElementById('castName');
  const cf = document.getElementById('castFill');
  if(p.cast && p.cast.spellId){
    cn.innerHTML = '<a target="_blank" rel="noopener" style="color:#b87adf" href="https://www.wowhead.com/classic/spell='+p.cast.spellId+'">#'+p.cast.spellId+'</a>';
    cf.style.width = (p.cast.progress||0)+'%';
  } else { cn.textContent = '—'; cf.style.width = '0%'; }

  const tlbl = document.getElementById('tgtLabel');
  const tmeta = document.getElementById('tgtMeta');
  const tfill = document.getElementById('tgtFill');
  const tcn = document.getElementById('tgtCastName');
  const tcf = document.getElementById('tgtCastFill');
  if(t && t.exists){
    tlbl.textContent = (t.hostile?'HOSTILE':'FRIENDLY') + (t.classification && t.classification !== 'normal'? ' '+String(t.classification).toUpperCase():'');
    tmeta.textContent = 'L'+(t.level||'?')+'  '+(t.hpPct||0)+'%';
    setBar(tfill, t.hpPct||0, t.hostile?'hostile':'friendly');
    if(t.cast && t.cast.spellId){
      tcn.innerHTML = '<a target="_blank" rel="noopener" style="color:#b87adf" href="https://www.wowhead.com/classic/spell='+t.cast.spellId+'">#'+t.cast.spellId+'</a>';
      tcf.style.width=(t.cast.progress||0)+'%';
    } else{ tcn.textContent='—'; tcf.style.width='0%'; }
  } else {
    tlbl.textContent='No target'; tmeta.textContent='—';
    setBar(tfill, 0); tcn.textContent='—'; tcf.style.width='0%';
  }

  const sev = deriveSeverity(s);
  const sevW = document.getElementById('w-sev');
  sevW.dataset.sev = sev;
  sevW.querySelector('.body').textContent = 'SEV '+sev;
  document.body.dataset.combat = s.combat ? '1' : '0';

  const pills = [
    ['combat', s.combat], ['resting', p.resting], ['mounted', p.mounted],
    ['pvp', p.pvp], ['grouped', p.grouped], ['pet', p.hasPet],
  ];
  document.getElementById('statePills').innerHTML =
    pills.map(([n,on])=>'<span class="pill '+(on?'on':'')+'">'+n+'</span>').join('');

  document.getElementById('bagFree').textContent = (p.bagFree!=null) ? p.bagFree : '—';
  document.getElementById('bagStatus').textContent = p.bagFull ? 'FULL' : 'ok';
  document.getElementById('walletGold').textContent = (p.gold||0)+'g';
  document.getElementById('duraVal').textContent = (p.durabilityPct||0)+' %';
  setBar(document.getElementById('duraFill'), p.durabilityPct||0);

  document.getElementById('coordsVal').textContent = (z.mapX!=null?z.mapX:'—')+', '+(z.mapY!=null?z.mapY:'—');
  if(z.facing!=null){
    const c = document.getElementById('compass');
    c.innerHTML = '<span style="position:absolute;left:50%;top:50%;width:2px;height:12px;background:#ffd07a;transform-origin:50% 100%;transform:translate(-50%,-100%) rotate('+(z.facing/255*360)+'deg);display:block"></span>';
  }

  document.getElementById('tickVal').textContent = 'tick '+(s.tick!=null?s.tick:'—');
  document.getElementById('connText').textContent = 'live';

  const buffs = (s.buffs||[]).slice(0,8);
  document.getElementById('buffIcons').innerHTML =
    (buffs.length ? buffs : []).map(id=>spellLink(id,'#'+id)).join('') ||
    '<span class="icn empty">—</span>';
  const debuffs = (s.debuffs||[]).slice(0,8);
  document.getElementById('debuffIcons').innerHTML =
    (debuffs.length ? debuffs : []).map(id=>spellLink(id,'#'+id)).join('') ||
    '<span class="icn empty">—</span>';
  const ac = s.actionCooldowns || [];
  document.getElementById('actionIcons').innerHTML = ac.map((cd,i)=>{
    const cls = cd > 0 ? 'icn cd' : 'icn';
    return '<span class="'+cls+'" title="slot '+(i+1)+'">'+(cd>0?cd:(i+1))+'</span>';
  }).join('') || '<span class="icn empty">—</span>';
}

async function poll(){
  try{
    const r = await fetch('/state/'+CHANNEL_ID, {cache:'no-store'});
    if(r.status === 200){
      const snap = await r.json();
      renderSnapshot(snap);
      lastUpdate = Date.now();
      document.body.classList.remove('stale');
      document.getElementById('connState').textContent = '● LIVE';
      document.getElementById('connState').classList.remove('bad');
    } else if(r.status === 204){
      document.getElementById('connState').textContent = '○ NO DATA';
      document.getElementById('connState').classList.add('bad');
    }
  } catch(e){
    document.getElementById('connState').textContent = '⚠ OFFLINE';
    document.getElementById('connState').classList.add('bad');
  }
}
function staleCheck(){
  if(lastUpdate && Date.now() - lastUpdate > STALE_AFTER_MS){
    document.body.classList.add('stale');
  }
}

document.querySelectorAll('.widget').forEach(makeDraggable);
applyLayout();
poll();
setInterval(poll, 2000);
setInterval(staleCheck, 1000);
</script>
</body>
</html>`;
