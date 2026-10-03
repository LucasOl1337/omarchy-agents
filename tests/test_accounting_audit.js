const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const root = path.join(__dirname, '..');
const main = fs.readFileSync(path.join(root,'Main.qml'),'utf8');
const panel = fs.readFileSync(path.join(root,'Panel.qml'),'utf8');
function contextFrom(source, names, values={}) {
  const context=vm.createContext(values);
  for (const name of names) {
    const match=source.match(new RegExp('  function '+name+'\\([^]*?\\n  }'));
    assert.ok(match,name); vm.runInContext(match[0],context);
  }
  return context;
}
test('freshness uses explicit update date even when old files contain padded current-day zeros',()=>{
  const c=contextFrom(main,['todayFieldsAreCurrent','dateString']);
  const yesterday=new Date(); yesterday.setDate(yesterday.getDate()-1);
  c.record={updatedAt:yesterday.toISOString(),todayTotalTokens:999,recentDays:[{date:c.dateString(new Date()),messageCount:0}]};
  assert.equal(vm.runInContext('todayFieldsAreCurrent(record)',c),false);
});
test('token-only records remain discoverable even without invented prompts or sessions',()=>{
  const c=contextFrom(main,['providerHasData','numberValue']);
  assert.equal(c.providerHasData({todayTotalTokens:100}),true);
});
test('account replicas select a whole latest record and sync retains daily model history',()=>{
  const c=contextFrom(main,['aggregateSnapshots','recentDateStrings','dateString','safeDeviceId','numberValue','combineNumber','combineObjectNumbers','emptyTokenBucket','currentTodayStats','todayFieldsAreCurrent']);
  const today=c.dateString(new Date());
  const a={scope:'account',updatedAt:new Date(Date.now()-1000).toISOString(),todayTotalTokens:100,todayTokensByModel:{opus:100},modelUsage:{opus:{inputTokens:100}},history:[{date:today,messageCount:100,tokensByModel:{opus:100}}]};
  const b={...a,updatedAt:new Date().toISOString(),todayTotalTokens:80,todayTokensByModel:{sonnet:80},modelUsage:{sonnet:{inputTokens:80}},history:[{date:today,messageCount:80,tokensByModel:{sonnet:80}}]};
  const result=c.aggregateSnapshots([{deviceId:'a',providers:{'9router':a}},{deviceId:'b',providers:{'9router':b}}]);
  const p=result.providers['9router'];
  assert.equal(p.todayTotalTokens,80);
  assert.equal(JSON.stringify(p.todayTokensByModel),JSON.stringify({sonnet:80}));
  assert.equal(p.history[0].messageCount,80);
  assert.deepEqual(Object.keys(p.modelUsage),['sonnet']);
  assert.equal(p.modelUsage.sonnet.inputTokens,80);
});
test('model display cap preserves the sum with an explicit Other row',()=>{
  const c=contextFrom(panel,['modelRowsFromUsage'],{usage:{friendlyModelName:id=>id}});
  const models=Object.fromEntries(Array.from({length:25},(_,i)=>['m'+i,{inputTokens:i+1}]));
  const rows=c.modelRowsFromUsage(models,8);
  assert.equal(rows.length,8);
  assert.equal(rows.reduce((n,row)=>n+row.total,0),325);
  assert.equal(rows.at(-1).id,'__other');
});
test('calendar summaries conserve Day/Hour/daily rows/models for generated source snapshots',()=>{
  const c=vm.createContext({}); vm.runInContext(fs.readFileSync(path.join(root,'UsageMath.js'),'utf8'),c);
  let seed=11; const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed%10000};
  for(let i=0;i<1000;i++) {
    const local=rand(),remote=rand(),models=rand();
    for (const period of ['day','week','month','total']) {
      const ledger={period, hours:[{start:100}],byProvider:{claude:{tokens:local,models:{opus:local},hours:[{start:100,tokens:local}],days:[{date:'2026-10-03',messageCount:local}]}}};
      const sources=[{id:'claude',name:'Claude',current:true,tokens:local,models:{opus:local}},{id:'9router',name:'9Router',current:true,tokens:remote,models:{opus:models},days:[{date:'2026-10-03',messageCount:remote}]}];
      const result=c.assemble(ledger,sources,id=>id,{period,today:'2026-10-03',start:'2026-09-01'});
      assert.equal(result.tokens,local+remote);
      assert.equal(Object.values(result.models).reduce((a,b)=>a+b,0),result.tokens);
      assert.equal(result.days.reduce((a,b)=>a+b.messageCount,0),result.tokens);
      if(period==='day') assert.equal(result.hours.reduce((a,b)=>a+b.tokens,0)+result.unassigned.reduce((a,b)=>a+b.tokens,0),result.tokens);
    }
  }
});
test('future daily detail does not hide the undated remainder or erase unknown model labels',()=>{
  const c=vm.createContext({}); vm.runInContext(fs.readFileSync(path.join(root,'UsageMath.js'),'utf8'),c);
  const result=c.assemble({},[{id:'9router',name:'Gateway',canonical:true,current:true,tokens:100,models:{},days:[{date:'2026-10-04',messageCount:50}]}],()=> 'wrong',{period:'week',today:'2026-10-03'});
  assert.equal(result.models['Sem modelo · Gateway'],100);
  assert.equal(result.days.reduce((n,row)=>n+row.messageCount,0),100);
});
test('Radar runs the actual QML ranking and rejects unknown quota percentages',()=>{
  const names=['windowIsLong','windowSpanMs','windowTitle','limitWindow','limitWindows','formatDuration','radarProviderAllowed','radarWindowAllowed','radarHarness','radarTier','radarWindowKind','radarPool','radarWhy','radarBand','radarScore','radarBalanceNote','currencyPrefix','formatMoney','accountLabel','buildRadarQuotaRows'];
  const c=contextFrom(panel,names);
  assert.equal(c.limitWindows({limits:[{percent:null},{percent:''},{percent:Infinity}]}).length,0);
  const records=[['claude',0.9],['codex',0.2],['grok',1.0],['9router',0.0]].map(([id,n])=>({providerId:id,chipName:id,limits:[{title:'Weekly',percent:n},{title:'Session',percent:0.0}]}));
  const rows=c.buildRadarQuotaRows(Date.now(),records);
  assert.equal(JSON.stringify(rows.map(r=>r.providerId)),JSON.stringify(['codex','claude','grok']));
  assert.equal(rows[2].badge,'esgotado');
});
