import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'bin'))
import tracking
from usage_accounting import summarize
from datetime import datetime, timedelta
from deploy import deploy

def load(name):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / 'bin' / ('omarchy-agent-usage-' + name)))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

codex = load('codex')
claude = load('claude-daily')
hermes = load('hermes')

class AccountingAuditTests(unittest.TestCase):
    def test_update_all_honors_exclusions_in_both_stock_and_plugin_collectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root/'bin'; folder.mkdir()
            shutil.copy2(ROOT/'bin/update',folder/'update')
            stock = folder/'omarchy-agent-usage-update'
            stock.write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["STOCK_ARGS"]).write_text(json.dumps(sys.argv[1:]))\n')
            stock.chmod(0o755)
            for name in ['codex','grok']:
                script=folder/('omarchy-agent-usage-'+name)
                script.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'id':"+repr(name)+"}))\n"); script.chmod(0o755)
            env=dict(os.environ,PATH=str(folder)+':'+os.environ['PATH'],XDG_STATE_HOME=str(root/'state'),STOCK_ARGS=str(root/'args.json'))
            result=subprocess.run([str(folder/'update'),'all','--except','claude'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            args=json.loads((root/'args.json').read_text())
            self.assertIn('claude',args)
            usage=root/'state/omarchy/agents/usage'
            self.assertEqual(json.loads((usage/'codex.json').read_text())['id'],'codex')
            self.assertTrue((usage/'grok.json').exists())
            self.assertFalse((usage/'claude.json').exists())

    def test_hermes_collector_keeps_cross_day_total_out_of_daily_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'state.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE sessions(id TEXT,parent_session_id TEXT,archived INTEGER,message_count INTEGER,last_activity_at REAL,started_at REAL)')
            db.execute('CREATE TABLE session_model_usage(session_id TEXT,model TEXT,api_call_count INTEGER,input_tokens INTEGER,output_tokens INTEGER,cache_read_tokens INTEGER,cache_write_tokens INTEGER,reasoning_tokens INTEGER,first_seen REAL,last_seen REAL)')
            start = datetime(2026,10,2,23).timestamp(); end = datetime(2026,10,3,9).timestamp()
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',('s',None,0,2,end,start))
            db.execute('INSERT INTO session_model_usage VALUES (?,?,?,?,?,?,?,?,?,?)',('s','opus',2,100,10,0,0,0,start,end))
            db.commit(); db.close()
            result = hermes.scan_db(path)
            self.assertEqual(result['models']['opus']['inputTokens'],100)
            self.assertEqual(dict(result['daily_models']), {})

    def test_claude_enrichment_resets_today_when_all_source_files_are_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'claude.json'
            path.write_text(json.dumps({'todayTotalTokens':500,'todayTokensByModel':{'opus':500}}))
            with patch.object(claude,'save_cache'), patch.object(claude,'load_cache',return_value={}), patch.object(claude,'claude_account',return_value={}):
                claude.enrich(path, Path(tmp)/'missing')
            self.assertEqual(json.loads(path.read_text())['todayTotalTokens'],0)

    def test_cumulative_session_preserves_day_without_inventing_hour(self):
        start = datetime(2026, 10, 3, 8).timestamp()
        end = datetime(2026, 10, 3, 10).timestamp()
        midnight = datetime(2026, 10, 3).timestamp()
        rows = [('hermes', 'opus', end, 100, 2, '/project', 'session', start)]
        part = summarize(rows, midnight, end, 'day')['hermes']
        self.assertEqual(part['tokens'], 100)
        self.assertEqual(part['days'], [{'date':'2026-10-03','messageCount':100}])
        self.assertEqual(part['hours'], [])
        rows[0] = (*rows[0][:-1], midnight - 100)
        part = summarize(rows, midnight, end, 'day')['hermes']
        self.assertEqual(part['tokens'], 0)
        self.assertEqual(part['excludedTokens'], 100)
        part = summarize(rows, 0, end, 'total')['hermes']
        self.assertEqual(part['tokens'], 100)
        self.assertEqual(part['unassignedTokens'], 100)
        self.assertEqual(part['days'], [])

    def test_pi_routes_native_usage_and_splits_cached_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.jsonl'
            rows = [{'type':'session','id':'s','cwd':'/project'},
                    {'type':'message','id':'m','timestamp':'2026-10-03T09:00:00-03:00',
                     'message':{'role':'assistant','provider':'anthropic','model':'opus',
                                'usage':{'input':100,'output':10,'cacheRead':20,'cacheWrite':5}}}]
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            parsed = list(tracking.json_events(path, 'pi'))
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]['provider'], 'claude')
            self.assertEqual(sum(parsed[0][k] for k in ['input','output','cacheRead','cacheWrite']), 135)

    def test_installation_is_idempotent_and_uses_new_urls_after_code_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root/'source'; source.mkdir()
            (source/'bin').mkdir(); (source/'assets').mkdir()
            (source/'Panel.qml').write_text('first')
            (source/'manifest.json').write_text(json.dumps({'version':'1.8.0','entryPoints':{'barWidget':'Panel.qml'}}))
            a = deploy(source, root/'installed'); b = deploy(source, root/'installed')
            self.assertEqual(a, b)
            (source/'Panel.qml').write_text('second')
            c = deploy(source, root/'installed')
            self.assertNotEqual(a['entryPoint'], c['entryPoint'])
            self.assertEqual(Path(a['entryPoint']).read_text(), 'first')
            self.assertEqual(Path(c['entryPoint']).read_text(), 'second')

    def test_nonfinite_timestamps_are_rejected(self):
        for value in [float('nan'),float('inf'),float('-inf')]:
            self.assertEqual(tracking.stamp(value), 0)

    def test_codex_daily_and_ledger_deduplicate_cumulative_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.jsonl'
            count = {'type': 'event_msg', 'timestamp': '2026-10-03T09:00:00-03:00',
                     'payload': {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 100, 'output_tokens': 10, 'total_tokens': 110}, 'last_token_usage': {'input_tokens': 100, 'output_tokens': 10}}}}
            path.write_text(json.dumps(count) + '\n' + json.dumps(count) + '\n')
            daily = sum(sum(b[:4]) for b in codex.parse_native_codex_session(path).values())
            ledger = sum(sum(r[k] for k in ['input', 'output', 'cacheRead', 'cacheWrite']) for r in tracking.json_events(path, 'codex'))
            self.assertEqual(daily, ledger)
            self.assertEqual(daily, 110)

    def test_claude_streaming_usage_keeps_latest_message_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.jsonl'
            rows = [{'type': 'assistant', 'timestamp': '2026-10-03T09:00:00-03:00',
                     'message': {'id': 'msg1', 'model': 'claude-opus-5-5', 'usage': {'input_tokens': 100, 'output_tokens': n}}} for n in [0, 10]]
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            self.assertEqual(claude.scan_file(path)['2026-10-03']['claude-opus-5-5'], 110)

    def test_removed_source_does_not_remain_in_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.jsonl'
            path.write_text(json.dumps({'type': 'assistant', 'timestamp': '2026-10-03T09:00:00-03:00', 'message': {'id': 'm', 'usage': {'input_tokens': 100}}}) + '\n')
            db = sqlite3.connect(':memory:'); self.addCleanup(db.close); tracking.init_db(db)
            with patch.object(tracking, 'sources', return_value=[(path, 'claude', tracking.json_events)]): tracking.scan(db)
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], 1)
            with patch.object(tracking, 'sources', return_value=[]): tracking.scan(db)
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], 0)

    def test_empty_today_resets_claude_daily_fields(self):
        record = {'todayTotalTokens': 500, 'todayTokensByModel': {'opus':500}, 'recentDays': []}
        claude.apply_daily(record, {'2026-09-01': {'opus': 20}})
        self.assertEqual(record['todayTotalTokens'], 0)
        self.assertEqual(record['todayTokensByModel'], {})

if __name__ == '__main__': unittest.main()
