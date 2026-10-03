const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const panel = fs.readFileSync(path.join(__dirname, '../Panel.qml'), 'utf8');
function qmlFunction(name) {
  const match = panel.match(new RegExp('  function ' + name + '\\([^]*?\\n  }'));
  assert.ok(match, 'QML function exists: ' + name);
  return match[0];
}
function formatDateTime(date, format) {
  const hour = String(date.getUTCHours()).padStart(2, '0');
  const minute = String(date.getUTCMinutes()).padStart(2, '0');
  return format === 'HH' ? hour : hour + ':' + minute;
}
test('rendered Hour rows, folded hours, Day and models share the same totals', () => {
  const snapshot = {
    hours: Array.from({length: 17}, (_, hour) => ({start: hour * 3600, tokens: hour * 100, calls: hour, current: hour === 16, models: {opus: hour * 100}, projects: {Dino: hour * 100}})),
    unassigned: [{label: '9Router · sem horário', tokens: 50000, tooltip: 'remote'}],
    models: {opus: 63600}, tokens: 63600
  };
  const root = {todaySnapshot: snapshot, hourlyRowCap: 12, hourlyNewestFirst: false, todayDate: () => '2026-10-03'};
  const context = vm.createContext({root, hourlyRowCap: 12, todaySnapshot: snapshot, provider: {providerId: 'all'}, period: 'day',
    Qt: {formatDateTime}, usage: {formatTokenCount: String, friendlyModelName: id => id}});
  for (const name of ['mergeSplit', 'hourRange', 'hourSplitLines', 'hourSplits', 'hourTooltip', 'hourlyRows', 'emptyTokenBucket', 'addTokenValue', 'modelRowsFromUsage', 'todayModelRows', 'todayDate']) {
    if (name !== 'todayDate') vm.runInContext(qmlFunction(name), context);
  }
  context.todayDate = root.todayDate;
  const dayExpression = panel.match(/readonly property var periodRows: ([^]*?)(?=\n  readonly property)/)[1];
  const modelExpression = panel.match(/readonly property var models: ([^\n]+)/)[1];
  const day = vm.runInContext('(' + dayExpression.trim() + ')', context);
  const dayModels = vm.runInContext('(' + modelExpression + ')', context);
  assert.equal(day[0].messageCount, snapshot.tokens);
  for (const reversed of [false, true]) {
    root.hourlyNewestFirst = reversed;
    const hours = vm.runInContext('hourlyRows()', context);
    assert.equal(hours.reduce((sum, row) => sum + row.messageCount, 0), day[0].messageCount);
    assert.ok(hours.some(row => row.folded));
    assert.equal(hours.at(-1).label, '9Router · sem horário');
    context.period = 'hour';
    const hourModels = vm.runInContext('(' + modelExpression + ')', context);
    assert.equal(JSON.stringify(hourModels), JSON.stringify(dayModels));
  }
});
