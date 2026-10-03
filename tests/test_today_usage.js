const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, '../UsageMath.js'), 'utf8'), context);
const combine = (ledger, summaries) => JSON.parse(JSON.stringify(context.combine(ledger, summaries, id => id.replace(/^.* · /, '').replace(/\(high\)$/, ''))));
const summary = (id, tokens, models, current = true) => ({id, name: id, tokens, models, current});
const local = {
  hours: [{start: 100, current: false}, {start: 3700, current: true}],
  byProvider: {
    claude: {tokens: 300, calls: 2, models: {'opus': 300}, hours: [
      {start: 100, tokens: 100, calls: 1, models: {'opus': 100}, projects: {Dino: 100}},
      {start: 3700, tokens: 200, calls: 1, models: {'opus': 200}, projects: {DailyWork: 200}}
    ]}
  }
};
function assertConserved(result) {
  assert.equal(result.hours.reduce((sum, h) => sum + h.tokens, 0)
    + result.unassigned.reduce((sum, h) => sum + h.tokens, 0), result.tokens);
  assert.equal(Object.values(result.models).reduce((sum, n) => sum + n, 0), result.tokens);
}
test('All includes routed usage in both Hour and Day, exactly once', () => {
  const result = combine(local, [summary('claude', 290, {opus: 290}), summary('9router', 700, {'Sherlocker · opus(high)': 700})]);
  assert.equal(result.tokens, 1000);
  assert.equal(result.models.opus, 1000);
  assert.equal(result.unassigned[0].tokens, 700);
  assert.equal(result.hours[1].tokens, 200);
  assertConserved(result);
});
test('fresh local events replace stale daily counters instead of adding them', () => {
  const result = combine(local, [summary('claude', 290, {opus: 290})]);
  assert.equal(result.tokens, 300);
  assert.equal(result.unassigned.length, 0);
  assertConserved(result);
});
test('provider selection excludes other enabled and disabled sources', () => {
  const result = combine(local, [summary('9router', 700, {opus: 700})]);
  assert.equal(result.tokens, 700);
  assert.equal(result.hours[1].tokens, 0);
  assertConserved(result);
});
test('billing-only usage remains visible without invented hourly allocations', () => {
  const result = combine({hours: [], byProvider: {}}, [summary('cursor', 500, {'cursor-model': 500})]);
  assert.equal(result.tokens, 500);
  assert.equal(result.hours.length, 0);
  assert.equal(result.unassigned[0].label, 'cursor · sem horário');
  assertConserved(result);
});
test('yesterday API snapshots cannot be reported as today', () => {
  const result = combine(local, [summary('9router', 700, {opus: 700}, false)]);
  assert.equal(result.tokens, 0);
  assertConserved(result);
});
test('missing or inconsistent model detail is explicit and does not inflate totals', () => {
  for (const models of [{opus: 450}, {opus: 600}, {}]) {
    const result = combine({}, [summary('9router', 500, models)]);
    assert.equal(result.tokens, 500);
    assertConserved(result);
  }
});
test('sync keeps remote usage without counting local events twice', () => {
  const synced = summary('claude', 500, {opus: 500});
  synced.synced = true;
  const result = combine(local, [synced]);
  assert.equal(result.tokens, 500);
  assert.equal(result.hours.reduce((sum, h) => sum + h.tokens, 0), 300);
  assert.equal(result.unassigned[0].tokens, 200);
  assertConserved(result);
});
test('a panel left open past midnight drops yesterday hourly events', () => {
  const result = JSON.parse(JSON.stringify(context.combine(local, [summary('claude', 0, {}, false)], id => id, 90000)));
  assert.equal(result.tokens, 0);
  assert.equal(result.hours.length, 0);
  assertConserved(result);
});
