from quality_fixture import qualify
import json
from pathlib import Path
import tempfile
import threading
import unittest
from datetime import timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import app


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = app.Store(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def job(self):
        self.store.change({'op': 'add_job', 'company': 'Example', 'role': 'Support',
            'url': 'https://example.org/jobs/1', 'resume': 'resumes/demo.pdf',
            'duties': 'Support users', 'requirements': 'Communication'})
        return self.store.read(app.CATALOG)['jobs'][0]

    def test_empty_start_preserves_existing_files(self):
        self.job()
        reopened = app.Store(self.temp.name)
        self.assertEqual(len(reopened.read(app.CATALOG)['jobs']), 1)
        self.assertEqual(reopened.read(app.LEDGER)['applications'], {})

    def test_mark_duplicate_and_snapshot(self):
        job = self.job()
        request = {'op': 'mark', 'key': job['key'], 'evidence': 'Success screen'}
        self.store.change(request)
        self.store.change(request)
        state = self.store.read(app.LEDGER)
        self.assertEqual(len(state['applications']), 1)
        self.assertEqual(state['revision'], 1)
        self.assertEqual(state['applications'][job['key']]['job_snapshot']['duties'], ['Support users'])
        self.assertTrue((Path(self.temp.name) / '投递记录.backup.json').exists())

    def test_alias_duplicate(self):
        a = {'key': 'a', 'aliases': ['b'], 'company': 'C', 'role': 'R'}
        b = {'key': 'b', 'company': 'Different display name', 'role': 'R2'}
        self.assertTrue(app.same_job(a, b))
        self.assertTrue(app.same_job(a, {'key': 'c', 'company': ' c ', 'role': ' r '}))

    def test_weekly_boundary_and_progress(self):
        record = {'applied_date': (app.today() - timedelta(days=6)).isoformat(), 'progress': '等待回复'}
        self.assertFalse(app.overdue(record))
        record['applied_date'] = (app.today() - timedelta(days=7)).isoformat()
        self.assertTrue(app.overdue(record))
        record['progress'] = '自动回执'
        self.assertTrue(app.overdue(record))
        for p in app.PROGRESS[2:]:
            record['progress'] = p
            self.assertFalse(app.overdue(record))

    def test_updates_and_recoverable_undo(self):
        job = self.job()
        self.store.change({'op': 'mark', 'key': job['key'], 'evidence': 'Submitted'})
        self.store.change({'op': 'update', 'key': job['key'], 'progress': '面试邀请', 'notes': 'Tomorrow'})
        self.assertEqual(self.store.read(app.LEDGER)['applications'][job['key']]['last_response_date'], app.today().isoformat())
        self.store.change({'op': 'undo', 'key': job['key']})
        state = self.store.read(app.LEDGER)
        self.assertFalse(state['applications'])
        self.assertEqual(len(state['removed']), 1)

    def test_import_merges_and_rejects_nonweb_urls(self):
        job = self.job()
        self.assertEqual(self.store.change({'op': 'import_catalog', 'catalog': {'jobs': [job]}})['added'], 0)
        for url in ('mailto:a@example.org', 'javascript:alert(1)', 'file:///tmp/a', 'https://user:password@example.org'):
            with self.assertRaises(ValueError):
                self.store.change({'op': 'add_job', 'company': 'X', 'role': 'Y', 'url': url})

    def test_future_date_rejected(self):
        job = self.job()
        with self.assertRaises(ValueError):
            self.store.change({'op': 'mark', 'key': job['key'], 'evidence': 'No', 'date': (app.today() + timedelta(days=1)).isoformat()})


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = app.Server(self.temp.name, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_http_write_requires_token_and_origin(self):
        data = json.dumps({'op': 'add_job', 'company': 'HTTP test', 'role': 'Tester'}).encode()
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.url + '/api/change', data=data))
        self.assertEqual(ctx.exception.code, 403)
        with urlopen(self.url + '/api/state') as r:
            token = json.load(r)['token']
        request = Request(self.url + '/api/change', data=data, headers={'Origin': self.url, 'X-Tracker-Token': token, 'Content-Type': 'application/json'})
        with urlopen(request) as r:
            self.assertEqual(len(json.load(r)['catalog']['jobs']), 1)

    def test_path_boundary_and_host_validation(self):
        for path in ('/app.py', '/resumes/../../app.py', '/config.json'):
            with self.assertRaises(HTTPError) as ctx:
                urlopen(self.url + path)
            self.assertEqual(ctx.exception.code, 404)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.url + '/api/state', headers={'Host': 'foreign.example'}))
        self.assertEqual(ctx.exception.code, 403)

    def test_day_action_requires_auth_and_does_not_record_application(self):
        self.server.store.change({'op':'add_job','company':'HTTP company','role':'Support','url':'https://example.org/job'})
        qualify(self.server.store,self.server.assistant,self.server.store.read(app.CATALOG)['jobs'][-1],app.today())
        with urlopen(self.url+'/api/state') as r: state=json.load(r)
        data=json.dumps({'op':'seen','key':state['allowed_keys'][0]}).encode()
        with self.assertRaises(HTTPError) as ctx: urlopen(Request(self.url+'/api/day',data=data))
        self.assertEqual(ctx.exception.code,403)
        req=Request(self.url+'/api/day',data=data,headers={'Origin':self.url,'X-Tracker-Token':state['token'],'Content-Type':'application/json'})
        with urlopen(req) as r: self.assertTrue(json.load(r)['ok'])
        with urlopen(self.url+'/api/state') as r: state=json.load(r)
        self.assertEqual(state['allowed_keys'],[])
        self.assertEqual(state['ledger']['applications'],{})

    def test_frontend_contains_no_embedded_user_catalog(self):
        with urlopen(self.url + '/') as r:
            html = r.read().decode()
        self.assertIn('AUTUMN JOB TRACKER', html)
        self.assertNotIn('__FALLBACK_DATA__', html)
        self.assertNotIn('mailto:', html)


if __name__ == '__main__':
    unittest.main()
