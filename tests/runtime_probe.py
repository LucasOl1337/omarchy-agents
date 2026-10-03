#!/usr/bin/env python3
"""Run real QML bindings in an agent bench, with deterministic offline data.

X11 benches cannot instantiate Wayland layer-shell attached properties.
Only KeyboardPanel's window adapter is replaced; tracker QML, collectors'
interface, FileView, processes, properties and delegates are the real code.
"""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).parents[1]


def run(bench, real_data=False):
    with tempfile.TemporaryDirectory(prefix='agents-runtime-') as temporary:
        root = Path(temporary)
        (root / 'Commons').symlink_to('/usr/share/omarchy/shell/Commons')
        shutil.copytree('/usr/share/omarchy/shell/Ui', root / 'Ui')
        (root / 'Ui/KeyboardPanel.qml').write_text('''import QtQuick
Item {
 property Item anchorItem
 property QtObject bar
 property var owner
 property bool open: false
 property Item focusTarget
 property int contentWidth: 560
 property int contentHeight: 850
 property bool popoutSwitching: false
 width: contentWidth; height: contentHeight; visible: open
 function fittedContentWidth(value) { return value }
 function fittedContentHeight(value, maximum) { return Math.min(value, maximum) }
}
''')
        plugin = root / 'Plugin'; plugin.mkdir()
        for p in [*ROOT.glob('*.qml'), *ROOT.glob('*.js')]: shutil.copy2(p, plugin / p.name)
        shutil.copytree(ROOT / 'assets', plugin / 'assets')
        (plugin / 'bin').mkdir()
        update = plugin / 'bin/update'; update.write_text('#!/bin/sh\nexit 0\n'); update.chmod(0o755)
        now = datetime.datetime.now().astimezone()
        day = now.date().isoformat(); midnight = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        hour = dict(start=midnight, tokens=300, calls=2, models={'claude-opus-5-5':300}, projects={})
        ledger = dict(updatedAt=now.timestamp(), hours=[dict(hour, current=False)], byProvider={'claude':dict(tokens=300,calls=2,models={'claude-opus-5-5':300},hours=[hour],days=[dict(date=day,messageCount=300)])})
        totals = {'week':600,'month':900,'total':1200}
        summary = {kind:dict(period=kind,updatedAt=now.timestamp(),byProvider={'claude':dict(tokens=n,calls=2,models={'claude-opus-5-5':n},days=[dict(date=day,messageCount=n)],hours=[])}) for kind,n in totals.items()}
        (plugin / 'bin/tracking.py').write_text('import sys,json\nledger='+repr(ledger)+'\nsummary='+repr(summary)+'\nprint(json.dumps(summary[sys.argv[sys.argv.index("--period")+1]] if "--summary" in sys.argv else ledger))\n')
        state=root/'state/omarchy/agents/usage'; state.mkdir(parents=True)
        for id,n,model in [('claude',300,'claude-opus-5-5'),('9router',700,'Sherlocker · cc/claude-opus-5-5(high)')]:
            record=dict(id=id,name=id,ready=True,updatedAt=now.isoformat(),todayTotalTokens=n,todayTokensByModel={model:n},
                        history=[dict(date=day,messageCount=n,tokensByModel={model:n})],recentDays=[dict(date=day,messageCount=n)],modelUsage={model:{'inputTokens':n}})
            if id=='9router':
                record['periodTotals']={'week':1000,'month':2000,'total':3000}
                record['periodTokensByModel']={'week':{model:1000},'month':{model:2000}}
                record['modelUsage']={model:{'inputTokens':3000}}
            (state/(id+'.json')).write_text(json.dumps(record))
        if real_data:
            usage = Path.home()/'.local/state/omarchy/agents/usage'
            for p in state.glob('*.json'): p.unlink()
            for p in usage.glob('*.json'): shutil.copy2(p, state/p.name)
            for name in ['tracking.py','usage_accounting.py']:
                shutil.copy2(ROOT/'bin'/name, plugin/'bin'/name)
        (root/'shell.qml').write_text('''import QtQuick
import Quickshell
ShellRoot {
 id: shell
 property var dashboard
 property var retained
 property var checks: []
 property int step: 0
 property var cases: [{provider:"all",period:"day"},{provider:"all",period:"hour"},{provider:"all",period:"week"},{provider:"all",period:"month"},{provider:"all",period:"total"},{provider:"claude",period:"day"},{provider:"claude",period:"hour"},{provider:"9router",period:"day"},{provider:"9router",period:"hour"}]
 Component.onCompleted: {
  retained=Qt.createComponent("file://PLUGIN/Panel.qml")
  dashboard=retained.createObject(shell,{period:"day",selectedProviderId:"all"})
  if (!dashboard) { console.log("AUDIT_ERROR",retained.errorString()); Qt.quit() }
  else dashboard.open()
 }
 Timer { interval: 700; running: true; repeat: true; onTriggered: {
  if (!shell.dashboard) return
  if (shell.step > 0) {
   var diagnostic=JSON.parse(shell.dashboard.diagnostics())
   if (!diagnostic.ready || shell.dashboard.refreshBusy) return
   shell.checks.push(diagnostic)
  }
  if (shell.step === shell.cases.length) { console.log("AUDIT_RESULT",JSON.stringify(shell.checks)); Qt.quit(); return }
  var c=shell.cases[shell.step++]; shell.dashboard.selectedProviderId=c.provider; shell.dashboard.period=c.period
 } }
}
'''.replace('PLUGIN', str(plugin)))
        command=['agent-bench','exec',bench,'--','env','XDG_STATE_HOME='+str(root/'state'),'OMARCHY_TRACKING_STATE='+str(Path.home()/'.local/state/omarchy/agents/tracking'),'timeout','55','quickshell','-p',str(root),'--no-color']
        result=subprocess.run(command,capture_output=True,text=True)
        lines=[line.split('AUDIT_RESULT ',1)[1] for line in result.stdout.splitlines() if 'AUDIT_RESULT ' in line]
        if result.returncode or not lines: raise RuntimeError(result.stdout + result.stderr)
        data=json.loads(lines[-1])
        for view in data:
            assert view['tokens']==view['rowTokens']==sum(view['models'].values())==view['visibleModelTokens'], view
        for a,b in [(0,1),(5,6),(7,8)]:
            assert data[a]['models']==data[b]['models'], (data[a],data[b])
            assert data[a]['tokens']==data[b]['tokens'], (data[a],data[b])
        if not real_data:
            assert data[0]['tokens']==1000, data[0]
            for i,n in [(2,1600),(3,2900),(4,4200)]: assert data[i]['tokens']==n, data[i]
        assert 'HOJE, ACUMULADO'==data[1]['modelPeriod']
        print(json.dumps(dict(checks=len(data),views=data),ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--bench',required=True); parser.add_argument('--real-data',action='store_true')
    args=parser.parse_args(); run(args.bench, args.real_data)
