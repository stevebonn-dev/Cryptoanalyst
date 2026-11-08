// Server-side loop: runs the dashboard's own algorithm (taken from index.html) on a schedule,
// scores past signals, re-tunes thresholds, writes data/state.json + data/latest.json, sends push alerts.
const fs = require('fs'), vm = require('vm'), path = require('path');

async function run(opts = {}) {
  const root = opts.root || path.join(__dirname, '..');
  const env = opts.env || process.env;
  const baseFetch = opts.fetch || fetch;
  const seen = new Set();
  const doFetch = async (u, o) => {            // logs each failing host once so the Actions log shows why a run failed
    let host = '', pth = '';
    try { const x = new URL(String(u)); host = x.host; pth = x.pathname; } catch (e) {}
    try {
      const res = await baseFetch(u, o);
      if (!res.ok) { const k = host + ' ' + res.status; if (!seen.has(k)) { seen.add(k); console.log('HTTP ' + res.status + ' from ' + host + pth); } }
      return res;
    } catch (e) {
      const k = host + ' err'; if (!seen.has(k)) { seen.add(k); console.log('FETCH ERROR ' + host + ': ' + e.message); }
      throw e;
    }
  };
  let cfg = {};
  try { cfg = JSON.parse(fs.readFileSync(path.join(root, 'config.json'), 'utf8')); }
  catch (e) { console.log('config.json missing or unreadable (' + e.message + '); using the default asset list'); }
  let state = {};
  try { state = JSON.parse(fs.readFileSync(path.join(root, 'data/state.json'), 'utf8')); } catch (e) {}

  const store = {};
  if (state.cid1) store.cid1 = JSON.stringify(state.cid1);
  if (state.cid_al) store.cid_al = JSON.stringify(state.cid_al);
  store.cid_cfg = JSON.stringify({ list: cfg.assets || undefined, fib: cfg.fib || 'auto', gk: env.GLASSNODE_KEY || undefined, pos: cfg.positions || undefined, pfInit: cfg.pfInit || undefined });

  if (!fs.existsSync(path.join(root, 'index.html'))) throw new Error('index.html not found in the repo root (' + root + '); the loop reads the algorithm from it');
  // connectivity check: shows in the Actions log which Binance hosts this runner can reach
  for (const h of ['https://api.binance.com/api/v3/ping', 'https://data-api.binance.vision/api/v3/ping', 'https://api.binance.us/api/v3/ping', 'https://fapi.binance.com/fapi/v1/ping']) {
    try { const p = await baseFetch(h); console.log('PING ' + new URL(h).host + ' -> HTTP ' + p.status); }
    catch (e) { console.log('PING ' + new URL(h).host + ' -> ' + e.message); }
  }
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const js = html.split('<script>')[1].split('</script>')[0]
    .replace(/\nboot\(\);[^\n]*\n?/, '\n')
    // extra spot fallback for runners in regions where Binance's global hosts are blocked (Binance.US prices can differ slightly)
    .replace("'https://data-api.binance.vision']", "'https://data-api.binance.vision','https://api.binance.us']");

  const el = () => new Proxy({}, { get: (t, k) => k === 'style' ? {} : k === 'querySelector' ? () => el() : () => {}, set: () => true });
  const sandbox = {
    console, fetch: doFetch, setTimeout, clearTimeout, setInterval, URL,
    document: { getElementById: () => el(), addEventListener() {}, createElement: () => el() },
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } },
    navigator: {}, Notification: undefined, addEventListener() {}, devicePixelRatio: 1
  };
  sandbox.window = sandbox;
  const ctx = vm.createContext(sandbox);
  vm.runInContext(js, ctx);
  if (!vm.runInContext("typeof posTrack==='function'&&typeof posAct==='function'", ctx))
    console.log('WARNING: index.html in this repo is older than server/run.js (position tracking is missing). Upload the latest index.html to get position calls on the server.');

  const driver = `(async()=>{
    A=(CFG.list||DEF).map(mk);const now=Date.now(),out={},errs=[],notes=[];notify=m=>{notes.push(m)};
    for(const a of A){try{
      RAW[a.s]=await fetchAsset(a);if(typeof patLoad==='function'){try{await patLoad(a)}catch(e){}}if(typeof sfpLoad==='function'){try{await sfpLoad(a)}catch(e){}}if(typeof volLoad==='function'){try{await volLoad(a)}catch(e){}}if(typeof chainLoad==='function'){try{await chainLoad(a)}catch(e){}}
      const x=analyze(a,RAW[a.s],'1d',ST_.bias[a.s]||0);
      feedback(a,x,now);ltTrack(a,x,now);alertCheck(a,x);
      await gRun(a,now,x);
      const y=analyze(a,RAW[a.s],'1d',ST_.bias[a.s]||0);AN[a.s]=y;if(typeof posTrack==='function')posTrack(a,y,now);if(typeof advLog==='function'){try{advLog(a,y,now)}catch(e){}}const pv=typeof posAct==='function'?posAct(a,y):null;
      const g=GX[a.s],b=BT[a.s]&&BT[a.s].res,sl=q=>({g:q.g,th:q.th,s:q.s,cf:q.cf}),bs=q=>({score:q.OOS.score,rating:rate(q.OOS),oos:q.OOS,fs:q.fs,v:q.v,fib:q.fib});
      out[a.s]={p:y.p,chg:y.chg,s:y.s,cf:y.cf,pUp:y.pUp,derivs:y.topr!=null,
        G:g?{ST:sl(g.ST),MT:sl(g.MT)}:null,bt:b?{days:b.days,ST:bs(b.ST),MT:bs(b.MT)}:null,
        live:{ST:liveQ(a.s,'ST'),MT:liveQ(a.s,'MT'),LT:ltQ(a.s)},pos:pv?{act:pv.act,pnl:pv.pnl}:null,sup:y.sup.slice(0,3),res:y.res.slice(0,3)};
      for(const r of ((ST_.g&&ST_.g.sig)||[]))if(r.s===a.s&&r.t===now)notes.push(a.s+' G-'+r.hz+' '+(r.dir>0?'BUY':'SELL')+' @ '+f(r.p)+(r.cf>0?' (derivatives confirm)':r.cf<0?' (derivatives conflict)':''));
    }catch(e){errs.push(a.s+': '+e.message)}}
    if(typeof ctxLoad==='function'){try{await ctxLoad()}catch(e){}}
    if(typeof pfUpdate==='function'){try{pfUpdate(now)}catch(e){errs.push('portfolio: '+e.message)}}
    const snap={t:now,a:{}},L=v=>v&&v.length?v[v.length-1]:null;
    for(const a of A){const R=RAW[a.s];if(!R)continue;const fr=L(R.fr),oi=L(R.oi),tl=L(R.tl),gl=L(R.gl),tk=L(R.tk);let imb=null;try{const d=R.d,mid=(+d.bids[0][0]+ +d.asks[0][0])/2,bN=sum(d.bids.filter(b=>+b[0]>=mid*.99).map(b=>+b[0]*+b[1])),aN=sum(d.asks.filter(b=>+b[0]<=mid*1.01).map(b=>+b[0]*+b[1]));imb=(bN-aN)/(bN+aN||1)}catch(e){}
      snap.a[a.s]={p:+R.t.lastPrice,fr:fr?+fr.fundingRate:null,oi:oi?+oi.sumOpenInterestValue:null,tl:tl?+tl.longShortRatio:null,gl:gl?+gl.longShortRatio:null,tk:tk?+tk.buySellRatio:null,pm:R.pm&&+R.pm.indexPrice?(+R.pm.markPrice/+R.pm.indexPrice-1)*100:null,imb}}
    return{out,errs,notes,snap}})()`;
  const res = await vm.runInContext(driver, ctx);
  if (!Object.keys(res.out).length) throw new Error('No asset could be loaded: ' + res.errs.join('; '));

  const now = new Date().toISOString();
  fs.mkdirSync(path.join(root, 'data'), { recursive: true });
  fs.writeFileSync(path.join(root, 'data/latest.json'), JSON.stringify({ updated: now, assets: res.out, errors: res.errs }));
  fs.writeFileSync(path.join(root, 'data/state.json'), JSON.stringify({
    updated: now, runs: (state.runs || 0) + 1,
    cid1: JSON.parse(store.cid1 || '{"rec":[],"bias":{}}'), cid_al: store.cid_al ? JSON.parse(store.cid_al) : null
  }));

  if (res.snap) {   // hourly log of derivatives and depth readings, so order-flow signals can be backtested later
    const day = new Date(res.snap.t).toISOString().slice(0, 10), dir = path.join(root, 'data/hist');
    fs.mkdirSync(dir, { recursive: true });
    const fp = path.join(dir, day + '.json');
    let arr = []; try { arr = JSON.parse(fs.readFileSync(fp, 'utf8')); } catch (e) {}
    arr.push(res.snap); fs.writeFileSync(fp, JSON.stringify(arr));
    let ix = { days: [] }; try { ix = JSON.parse(fs.readFileSync(path.join(dir, 'index.json'), 'utf8')); } catch (e) {}
    ix.days = [...new Set([...ix.days, day])].sort();
    while (ix.days.length > 150) { const d = ix.days.shift(); try { fs.unlinkSync(path.join(dir, d + '.json')); } catch (e) {} }
    fs.writeFileSync(path.join(dir, 'index.json'), JSON.stringify(ix));
  }
  const topic = env.NTFY_TOPIC;
  if (topic && res.notes.length) {
    for (const n of [...new Set(res.notes)]) {
      try { await doFetch('https://ntfy.sh/' + encodeURIComponent(topic), { method: 'POST', body: n, headers: { Title: 'Crypto G dashboard' } }); } catch (e) {}
    }
  }
  res.errs.forEach(e => console.log('ASSET ERROR ' + e));
  console.log(`OK: ${Object.keys(res.out).length} assets, ${res.errs.length} errors, ${res.notes.length} alerts`);
  return res;
}

module.exports = { run };
if (require.main === module) run().catch(e => { console.error(e); process.exit(1); });
