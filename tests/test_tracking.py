import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('tracking', Path(__file__).parents[1] / 'bin/tracking.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class TrackingTests(unittest.TestCase):
    def test_codex_repeated_counters_cache_and_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'session.jsonl'
            def counter(total):
                return dict(type='event_msg', timestamp='2026-09-06T10:00:00Z', payload=dict(type='token_count', info=dict(total_token_usage=total)))
            first = dict(input_tokens=100, output_tokens=10, cached_input_tokens=60, total_tokens=110)
            second = dict(input_tokens=220, output_tokens=30, cached_input_tokens=130, total_tokens=250)
            p.write_text('\n'.join(map(json.dumps, [dict(type='session_meta', payload=dict(id='a', cwd='/home/test/Projects/example')),
                                                       counter(first), counter(first), counter(second)])) + "\n")
            rows = list(t.json_events(p, 'codex'))
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(sum(r[k] for k in ['input', 'output', 'cacheRead', 'cacheWrite']) for r in rows), 250)
            self.assertEqual(rows[1]['cacheRead'], 70)

    def test_grok_turn_is_not_labeled_single_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / '%2Fhome%2Ftest%2FProjects%2Fexample' / 's' / 'updates.jsonl'
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps(dict(timestamp=1788690000, params=dict(sessionId='s', update=dict(sessionUpdate='turn_completed', prompt_id='p', usage=dict(modelUsage={'grok': dict(inputTokens=100, outputTokens=20, cachedReadTokens=80, modelCalls=4)}))))) + "\n")
            row = list(t.json_events(p, 'grok'))[0]
            self.assertEqual((row['kind'], row['calls'], row['input'], row['cacheRead']), ('turn', 4, 20, 80))
            self.assertEqual(row['cwd'], '/home/test/Projects/example')

    def test_worktree_resolves_to_shared_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work = Path(tmp) / 'repo', Path(tmp) / 'copy'
            meta = root / '.git/worktrees/copy'
            meta.mkdir(parents=True)
            work.mkdir()
            (work / '.git').write_text('gitdir: ' + str(meta))
            (meta / 'commondir').write_text('../..')
            self.assertEqual(t.project(str(work / 'src'))[0], str(root))
            self.assertEqual(t.project('')[1], 'Sem projeto')

    def test_filters_pagination_and_direct_router_in_all(self):
        import sqlite3
        from types import SimpleNamespace
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE events(id TEXT,source TEXT,provider TEXT,project TEXT,model TEXT,timestamp REAL,tokens INTEGER,calls INTEGER,data TEXT)')
        for i in range(50):
            row = t.event(str(i), 'codex', 's', 'm', '/p', 1788690000, 10, 0)
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)', (row['id'], '', 'codex', '/p', 'm', row['timestamp'], 10, 1, json.dumps(row)))
            direct = t.event('d' + str(i), '9router', 's', 'gpt-5.6-sol(medium)', '/p', 1788690000, 10, 0, kind='call', caller='9Router / codex')
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)', (direct['id'], '', '9router', '/p', direct['model'], direct['timestamp'], 10, 1, json.dumps(direct)))
            proxy = t.event('p' + str(i), '9router', 's', 'grok-4.6', '/p', 1788690000, 10, 0, kind='proxy', caller='9Router / grok-cli')
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)', (proxy['id'], '', '9router', '/p', proxy['model'], proxy['timestamp'], 10, 1, json.dumps(proxy)))
        args = SimpleNamespace(period='total', provider='all', project='*', search='', offset=50, limit=50)
        snap = t.snapshot(db, args, [], {})
        self.assertEqual((snap['tokens'], snap['records'], len(snap['rows'])), (1000, 100, 50))
        args.search = 'missing'
        self.assertEqual(t.snapshot(db, args, [], {})['records'], 0)
        args.search = ''
        args.provider = '9router'
        self.assertEqual(t.snapshot(db, args, [], {})['records'], 100)

    def test_hours_buckets_window_models_and_proxy_router_exclusion(self):
        import sqlite3
        import time
        from datetime import datetime
        from types import SimpleNamespace
        db = sqlite3.connect(':memory:')
        t.init_db(db)
        now = time.time()
        this_hour = datetime.fromtimestamp(now).replace(minute=0, second=0, microsecond=0).timestamp()
        rows = [
            ('a', 'devin', 'swe-2-max', this_hour, 100, 2, '{}'),
            ('b', 'devin', 'swe-2-max', this_hour - 3600, 50, 1, '{}'),
            ('c', 'devin', 'swe-2-medium', this_hour - 3600, 10, 1, '{}'),
            ('d', 'codex', 'gpt-5.6', this_hour - 5 * 3600, 30, 1, '{}'),
            ('e', '9router', 'grok-4.6', this_hour, 999, 1, json.dumps(dict(kind='proxy'))),
            ('g', '9router', 'gpt-5.6-sol(medium)', this_hour, 40, 1, json.dumps(dict(kind='call'))),
            ('f', 'devin', 'stale', this_hour - 48 * 3600, 777, 1, '{}'),
        ]
        for rid, provider, model, ts, tokens, calls, data in rows:
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',
                       (rid, '', provider, '/p', model, ts, tokens, calls, data))
        args = SimpleNamespace(hours=24, provider='all')
        snap = t.hourly(db, args, [], {})
        self.assertEqual(len(snap['hours']), 24)
        self.assertTrue(snap['hours'][-1]['current'])
        self.assertEqual(snap['hours'][-1]['tokens'], 140)
        self.assertEqual(snap['hours'][-2]['tokens'], 60)
        self.assertEqual(snap['tokens'], 230)
        self.assertEqual(snap['calls'], 6)
        self.assertEqual(snap['models'], {'swe-2-max': 150, 'swe-2-medium': 10, 'gpt-5.6': 30, 'gpt-5.6-sol(medium)': 40})
        args.provider = 'devin'
        snap = t.hourly(db, args, [], {})
        self.assertEqual(snap['tokens'], 160)
        self.assertNotIn('gpt-5.6', snap['models'])

    def test_hours_today_starts_at_midnight_and_ends_now(self):
        import sqlite3
        import time
        from datetime import datetime
        from types import SimpleNamespace
        db = sqlite3.connect(':memory:')
        t.init_db(db)
        now = datetime.fromtimestamp(time.time()).astimezone()
        this_hour = now.replace(minute=0, second=0, microsecond=0)
        midnight = this_hour.replace(hour=0)
        rows = [
            ('a', 'devin', 'swe-2-max', this_hour.timestamp(), 100, 2, '{}'),
            ('b', 'devin', 'swe-2-max', midnight.timestamp(), 50, 1, '{}'),
            ('c', 'devin', 'swe-2-max', midnight.timestamp() - 3600, 777, 1, '{}'),
        ]
        for rid, provider, model, ts, tokens, calls, data in rows:
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',
                       (rid, '', provider, '/p', model, ts, tokens, calls, data))
        snap = t.hourly(db, SimpleNamespace(hours=24, today=True, provider='all'), [], {})
        self.assertEqual(len(snap['hours']), this_hour.hour + 1)
        self.assertEqual(snap['hours'][0]['start'], midnight.timestamp())
        self.assertEqual(snap['hours'][0]['tokens'], 50)
        self.assertTrue(snap['hours'][-1]['current'])
        self.assertEqual(snap['hours'][-1]['tokens'], 100)
        self.assertEqual(snap['tokens'], 150)


class IncrementalTests(unittest.TestCase):
    def test_append_partial_record_and_rewrite(self):
        import sqlite3
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 's.jsonl'
            meta = dict(type='session_meta', payload=dict(id='s', cwd='/home/test/Projects/example'))
            prompt = dict(type='response_item', payload=dict(role='user', content=[dict(type='input_text', text='Corrigir a tela de vendas')]))
            def usage(identity, amount):
                return dict(type='token_usage_record', timestamp='2026-09-06T10:00:00Z', payload=dict(response_id=identity, usage=dict(input_tokens=amount, output_tokens=5)))
            lines = lambda rows: ''.join(json.dumps(row) + '\n' for row in rows)
            p.write_text(lines([meta, prompt, usage('r1', 100)]))
            db = sqlite3.connect(':memory:')
            t.init_db(db)
            with patch.object(t, 'sources', return_value=[(p, 'codex', t.json_events)]):
                self.assertFalse(t.scan(db)[0])
                first_size = p.stat().st_size
                complete = lines([usage('r2', 200)])
                with p.open('a') as out: out.write(complete[:-4])
                t.scan(db)
                self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0], 1)
                with p.open('a') as out: out.write(complete[-4:])
                stats = t.scan(db)[2]
                self.assertEqual(stats['jsonBytesRead'], len(complete.encode()))
                self.assertEqual(db.execute('SELECT sum(tokens) FROM events').fetchone()[0], 310)
                self.assertEqual(t.scan(db)[2]['jsonBytesRead'], 0)
                detail = t.details(db, 'codex:r2')
                self.assertEqual(detail['preview'], 'Corrigir a tela de vendas')
                self.assertNotIn('Corrigir a tela', db.execute('SELECT data FROM events LIMIT 1').fetchone()[0])
                p.write_text(lines([meta, usage('r3', 20)]))
                t.scan(db)
                self.assertEqual(db.execute('SELECT count(*),sum(tokens) FROM events').fetchone(), (1, 25))

    def test_exact_codex_record_suppresses_quota_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 's.jsonl'
            usage = dict(input_tokens=100, cached_input_tokens=70, output_tokens=5, total_tokens=105)
            p.write_text(''.join(json.dumps(row)+'\n' for row in [
                dict(type='token_usage_record', timestamp='2026-09-06T10:00:00Z', payload=dict(response_id='r', usage=usage)),
                dict(type='event_msg', timestamp='2026-09-06T10:00:00Z', payload=dict(type='token_count', info=dict(total_token_usage=usage)))
            ]))
            rows = list(t.json_events(p,'codex'))
            self.assertEqual(len(rows),1)
            self.assertEqual((rows[0]['input'], rows[0]['cacheRead'], rows[0]['output']), (30,70,5))

    def test_project_requires_declared_directory(self):
        self.assertEqual(t.declared_directory('Current working directory: /home/test/Projects/example\nShell: bash'), '/home/test/Projects/example')
        self.assertEqual(t.declared_directory('Please look at /home/test/Projects/example'), '')

    def test_9router_codex_is_direct_and_grok_cli_is_proxy(self):
        import os
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            os.environ['OMARCHY_DAILYWORK_ROOT'] = str(Path(tmp) / 'empty')
            t.dailywork_missions.cache_clear()
            try:
                p = Path(tmp) / 'data.sqlite'
                db = sqlite3.connect(p)
                db.execute('CREATE TABLE usageHistory(id INTEGER PRIMARY KEY, timestamp TEXT, provider TEXT, model TEXT, promptTokens INTEGER, completionTokens INTEGER, status TEXT, meta TEXT)')
                db.execute('INSERT INTO usageHistory VALUES (1,?,?,?,?,?,?,?)',
                           ('2026-09-17T10:00:00.000Z', 'codex', 'gpt-5.6-sol(medium)', 100, 5, 'ok', '{}'))
                db.execute('INSERT INTO usageHistory VALUES (2,?,?,?,?,?,?,?)',
                           ('2026-09-17T10:00:01.000Z', 'grok-cli', 'grok-4.6', 80, 8, 'ok', '{}'))
                db.commit()
                db.close()
                rows = {row['model']: row for row in t.db_events(p, '9router')}
                self.assertEqual(rows['gpt-5.6-sol(medium)']['kind'], 'call')
                self.assertEqual(rows['gpt-5.6-sol(medium)']['caller'], '9Router / codex')
                self.assertEqual(rows['grok-4.6']['kind'], 'proxy')
                self.assertEqual(rows['grok-4.6']['caller'], '9Router / grok-cli')
            finally:
                os.environ.pop('OMARCHY_DAILYWORK_ROOT', None)
                t.dailywork_missions.cache_clear()

    def test_dailywork_mission_attributes_matching_sol_call(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'DailyWork'
            mission = root / 'LucasOL/Private/candidaturas/missoes/abc'
            mission.mkdir(parents=True)
            (mission / 'supervisor.json').write_text(json.dumps(dict(
                modelo='gpt-5-6-sol-medium', provider='9router',
                iniciadoEm='2026-09-17T09:50:00.000Z', atualizadoEm='2026-09-17T10:00:10.000Z',
            )))
            os.environ['OMARCHY_DAILYWORK_ROOT'] = str(root)
            t.dailywork_missions.cache_clear()
            try:
                cwd, caller, origin = t.attribute_direct('gpt-5.6-sol(medium)', '2026-09-17T10:00:00.000Z', '9Router / codex')
                self.assertEqual((cwd, caller, origin), (str(root), 'DailyWork / candidaturas', 'Missão DailyWork'))
                cwd, caller, origin = t.attribute_direct('gpt-5.6-sol(high)', '2026-09-17T10:00:00.000Z', '9Router / codex')
                self.assertEqual((cwd, caller), ('', '9Router / codex'))
            finally:
                os.environ.pop('OMARCHY_DAILYWORK_ROOT', None)
                t.dailywork_missions.cache_clear()


if __name__ == '__main__':
    unittest.main()
