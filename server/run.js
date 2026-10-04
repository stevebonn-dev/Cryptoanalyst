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
  store.cid_cfg = JSON.stringify({ list: cfg.assets || undefined, fib: cfg.fib || 'auto', gk: env.GLASSNODE_KEY || undefined, pos: cfg.positions || undefined });

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
      RAW[a.s]=await fetchAsset(a);
      const x=analyze(a,RAW[a.s],'1d',ST_.bias[a.s]||0);
      feedback(a,x,now);ltTrack(a,x,now);alertCheck(a,x);
      await gRun(a,now,x);
      const y=analyze(a,RAW[a.s],'1d',ST_.bias[a.s]||0);AN[a.s]=y;if(typeof posTrack==='function')posTrack(a,y,now);const pv=typeof posAct==='function'?posAct(a,y):null;
      const g=GX[a.s],b=BT[a.s]&&BT[a.s].res,sl=q=>({g:q.g,th:q.th,s:q.s,cf:q.cf}),bs=q=>({score:q.OOS.score,rating:rate(q.OOS),oos:q.OOS,fs:q.fs,v:q.v,fib:q.fib});
      out[a.s]={p:y.p,chg:y.chg,s:y.s,cf:y.cf,pUp:y.pUp,derivs:y.topr!=null,
        G:g?{ST:sl(g.ST),MT:sl(g.MT)}:null,bt:b?{days:b.days,ST:bs(b.ST),MT:bs(b.MT)}:null,
        live:{ST:liveQ(a.s,'ST'),MT:liveQ(a.s,'MT'),LT:ltQ(a.s)},pos:pv?{act:pv.act,pnl:pv.pnl}:null,sup:y.sup.slice(0,3),res:y.res.slice(0,3)};
      for(const r of ((ST_.g&&ST_.g.sig)||[]))if(r.s===a.s&&r.t===now)notes.push(a.s+' G-'+r.hz+' '+(r.dir>0?'BUY':'SELL')+' @ '+f(r.p)+(r.cf>0?' (derivatives confirm)':r.cf<0?' (derivatives conflict)':''));
    }catch(e){errs.push(a.s+': '+e.message)}}
    return{out,errs,notes}})()`;
  const res = await vm.runInContext(driver, ctx);
  if (!Object.keys(res.out).length) throw new Error('No asset could be loaded: ' + res.errs.join('; '));

  const now = new Date().toISOString();
  fs.mkdirSync(path.join(root, 'data'), { recursive: true });
  fs.writeFileSync(path.join(root, 'data/latest.json'), JSON.stringify({ updated: now, assets: res.out, errors: res.errs }));
  fs.writeFileSync(path.join(root, 'data/state.json'), JSON.stringify({
    updated: now, runs: (state.runs || 0) + 1,
    cid1: JSON.parse(store.cid1 || '{"rec":[],"bias":{}}'), cid_al: store.cid_al ? JSON.parse(store.cid_al) : null
  }));

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
