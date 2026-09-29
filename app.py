"""Autumn Job Tracker: a single-user, offline, loopback-only application."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import threading
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse
import webbrowser
from recommendations import Assistant
from preferences import REGIONS
from startup import Startup
from companies import same_company, group_companies
from mailcheck import MailChecks, address
from application_feedback import Feedback

BASE = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))
PROGRESS = ('等待回复', '自动回执', '补材料', '测评邀请', '面试邀请', '面试中', '录用', '拒绝', '撤回')
CATALOG = '岗位库.json'
LEDGER = '投递记录.json'


def today():
    return datetime.now(TZ).date()


def stamp():
    return datetime.now(TZ).isoformat()


def valid_date(value):
    result = date.fromisoformat(value)
    if result > today():
        raise ValueError('日期不能在未来')
    return result.isoformat()


def overdue(record, on=None):
    if record.get('progress') not in ('等待回复', '自动回执'):
        return False
    return ((on or today()) - date.fromisoformat(record['applied_date'])).days >= 7


def normalize(value):
    return ''.join(str(value).casefold().split())


def same_job(a, b):
    aliases_a = {a.get('key'), *(a.get('aliases') or [])} - {None}
    aliases_b = {b.get('key'), *(b.get('aliases') or [])} - {None}
    return bool(aliases_a & aliases_b) or (
        normalize(a.get('company')) == normalize(b.get('company'))
        and normalize(a.get('role')) == normalize(b.get('role'))
    )


def text(value, limit=4000):
    if not isinstance(value, str):
        raise ValueError('字段必须是文本')
    if len(value) > limit:
        raise ValueError('字段内容过长')
    return value.strip()


def web_url(value):
    value = text(value, 3000)
    if not value:
        return ''
    u = urlparse(value)
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
        raise ValueError('链接必须是HTTP/HTTPS网页地址')
    return value


def check_catalog(value):
    if not isinstance(value, dict) or not isinstance(value.get('jobs'), list):
        raise ValueError('岗位库必须含有jobs数组')
    if len(value['jobs']) > 10000:
        raise ValueError('一次最多导入10000条岗位')
    keys = set()
    for j in value['jobs']:
        if not isinstance(j, dict) or not text(j.get('company', ''), 150) or not text(j.get('role', ''), 200):
            raise ValueError('岗位必须有公司和名称')
        key = text(j.get('key', ''), 100)
        if not key or key in keys:
            raise ValueError('岗位key缺失或重复')
        keys.add(key)
        for field in ('duties', 'requirements', 'strengths', 'gaps', 'aliases'):
            if field in j and (not isinstance(j[field], list) or not all(isinstance(item, str) for item in j[field])):
                raise ValueError(field + '必须是文本数组')
        if 'resume' in j and not isinstance(j['resume'], dict):
            raise ValueError('resume必须是对象')
        for field in ('apply_url', 'source', 'entry'):
            if j.get(field):
                web_url(j[field])
    return value


class Store:
    def __init__(self, directory):
        self.root = Path(directory).expanduser().resolve()
        self.lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        initial = {
            CATALOG: {'updated': today().isoformat(), 'jobs': [], 'originals': {}, 'rules': '管理岗位、简历版本和真实投递进展。'},
            LEDGER: {'schema': 1, 'revision': 0, 'applications': {}},
        }
        for name, obj in initial.items():
            if not (self.root / name).exists():
                self.write(name, obj)
        check_catalog(self.read(CATALOG))
        if not isinstance(self.read(LEDGER).get('applications'), dict):
            raise ValueError('投递记录格式不正确，请先检查数据文件')

    def read(self, name):
        return json.loads((self.root / name).read_text(encoding='utf-8-sig'))

    def write(self, name, obj):
        path = self.root / name
        if path.exists():
            shutil.copy2(path, path.with_suffix('.backup.json'))
        tmp = path.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def change(self, p):
        if not isinstance(p, dict):
            raise ValueError('请求格式不正确')
        with self.lock:
            state = self.read(LEDGER)
            apps = state['applications']
            catalog = self.read(CATALOG)
            op = p.get('op')
            key = p.get('key', '')
            if op == 'import_catalog':
                imported = check_catalog(p.get('catalog'))
                added = 0
                for job in imported['jobs']:
                    if not any(same_job(job, old) for old in catalog['jobs']):
                        catalog['jobs'].append(job)
                        added += 1
                catalog['updated'] = today().isoformat()
                self.write(CATALOG, catalog)
                return {'added': added}
            if op == 'add_job':
                company, role = text(p.get('company', ''), 150), text(p.get('role', ''), 200)
                if not company or not role:
                    raise ValueError('请填写公司和岗位')
                key = hashlib.sha256((normalize(company) + '|' + normalize(role)).encode()).hexdigest()[:16]
                url = web_url(p.get('url', ''))
                lines = lambda field: [text(s, 1000) for s in text(p.get(field, '')).splitlines() if s.strip()]
                resume = text(p.get('resume', ''), 500)
                job = {'key': key, 'aliases': [key], 'company': company, 'role': role,
                    'group': text(p.get('group', '其他'), 100), 'source': url, 'entry': url, 'apply_url': url,
                    'direct': bool(url), 'channel': 'web' if url else 'unverified', 'action_label': '打开岗位网页',
                    'place': text(p.get('place', '待确认'), 200), 'salary': text(p.get('salary', '待确认'), 200),
                    'deadline': text(p.get('deadline', '待确认'), 200), 'online': text(p.get('online', '待确认'), 300),
                    'match': text(p.get('match', '待评估'), 100), 'confidence': '本人填写',
                    'duties': lines('duties'), 'requirements': lines('requirements'),
                    'strengths': lines('strengths'), 'gaps': lines('gaps'), 'notes': text(p.get('notes', '')),
                    'variant': 'local' if resume else None, 'base': '本地简历',
                    'resume': {'base': '本地简历', 'path': resume, 'before': '', 'after': ''},
                    'change_note': '使用所登记的本地简历版本。', 'verified_on': today().isoformat()}
                if any(same_job(job, old) for old in catalog['jobs']):
                    raise ValueError('此岗位已在岗位库中')
                catalog['jobs'].append(job)
                self.write(CATALOG, catalog)
                return {'added': 1}
            if op in ('mark', 'manual'):
                job = next((j for j in catalog['jobs'] if j['key'] == key), None)
                if op == 'mark' and job is None:
                    raise ValueError('岗位不存在')
                if op == 'manual':
                    company, role = text(p.get('company', ''), 150), text(p.get('role', ''), 200)
                    if not company or not role:
                        raise ValueError('请填写公司和岗位')
                    job = next((j for j in catalog['jobs'] if normalize(j['company']) == normalize(company) and normalize(j['role']) == normalize(role)), None)
                    if job is None:
                        key = 'manual-' + hashlib.sha256((normalize(company) + '|' + normalize(role)).encode()).hexdigest()[:16]
                        job = {'key': key, 'company': company, 'role': role, 'match': '待分析', 'strengths': [], 'gaps': ['待补齐岗位要求与匹配分析'], 'source': web_url(p.get('source', ''))}
                key = job['key']
                if any(same_job(job, a) for a in apps.values()):
                    if key in apps:
                        return {'duplicate': True}
                    raise ValueError('已登记同一岗位，请更新现有记录')
                if op=='mark' and any(same_company(job,a) for a in apps.values()):
                    raise ValueError('该公司已投递，请到已投记录跟踪；如确实另投了岗位，可用补录登记事实')
                d = valid_date(p.get('date', today().isoformat()))
                evidence = text(p.get('evidence', ''), 2000)
                if not evidence:
                    raise ValueError('请填写成功提交依据')
                used = text(p.get('resume', job.get('resume', {}).get('path', '未记录')), 500)
                a = {k: job.get(k) for k in ('key', 'company', 'role', 'match', 'strengths', 'gaps', 'confidence', 'review_hint', 'source', 'entry', 'aliases')}
                a.update(applied_date=d, applied_at=stamp(), progress='等待回复', last_response_date=None,
                    evidence_type='本人登记', evidence=evidence, resume_used=used, job_snapshot=job,
                    changes=job.get('resume') if used == job.get('resume', {}).get('path') else None,
                    notes=text(p.get('notes', '')), events=[])
                a.update(application_channel=p.get('application_channel') or job.get('channel','web'),
                    applicant_email=address(p.get('applicant_email'),optional=True),
                    recruiter_email=address(p.get('recruiter_email') or job.get('email'),optional=True),
                    mail_subject=text(p.get('mail_subject',''),500))
                apps[key] = a
            elif op == 'mail_details':
                if key not in apps:raise ValueError('投递记录不存在')
                apps[key].update(applicant_email=address(p.get('applicant_email')),recruiter_email=address(p.get('recruiter_email')),
                    mail_subject=text(p.get('mail_subject',''),500))
            elif op == 'update':
                if key not in apps or p.get('progress') not in PROGRESS:
                    raise ValueError('记录或进度不正确')
                a = apps[key]
                a['progress'] = p['progress']
                a['notes'] = text(p.get('notes', ''))
                a['applied_date'] = valid_date(p.get('date', a['applied_date']))
                a['last_response_date'] = valid_date(p.get('response_date') or today().isoformat()) if a['progress'] not in PROGRESS[:2] else None
            elif op == 'undo':
                if key not in apps:
                    raise ValueError('记录不存在')
                state.setdefault('removed', []).append(dict(apps.pop(key), removed_at=stamp()))
            else:
                raise ValueError('未知操作')
            if key in apps:
                apps[key].setdefault('events', []).append({'at': stamp(), 'action': op, 'progress': apps[key]['progress']})
            state['revision'] = state.get('revision', 0) + 1
            state['updated_at'] = stamp()
            self.write(LEDGER, state)
            return {'ok': True}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, directory, port=18728):
        self.store = Store(directory)
        self.assistant = Assistant(self.store, today, same_job)
        self.feedback = Feedback(self.store,today,self.assistant)
        self.token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), Handler)
        self.startup = Startup(directory, self.server_port, BASE)
        self.mailchecks = MailChecks(self.store)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def host_ok(self):
        port = self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

    def send(self, data, status=200, mime='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        for k, v in {'Content-Type': mime, 'Content-Length': str(len(data)), 'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
            'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.host_ok():
            return self.send({'error': 'Invalid host'}, 403)
        path = unquote(urlparse(self.path).path)
        store = self.server.store
        if path == '/health':
            return self.send({'app': 'autumn-job-tracker', 'version': '1.6.0', 'data_dir': str(store.root)})
        if path == '/api/mailbox': return self.send(self.server.mailchecks.status())
        if path == '/api/startup':
            return self.send(self.server.startup.status())
        if path == '/api/career':
            return self.send(self.server.assistant.career_status())
        if path == '/api/assistant':
            return self.send(self.server.assistant.status())
        if path == '/api/assistant/model':
            return self.send(self.server.assistant.model_status())
        if path == '/api/state':
            with store.lock:
                return self.send({'catalog': store.read(CATALOG), 'ledger': store.read(LEDGER),
                    'token': self.server.token, 'today': today().isoformat(), 'data_dir': str(store.root),
                    'preferences':self.server.assistant.preferences.read(), 'regions':REGIONS,
                    'feedback':self.server.feedback.status(),
                    'excluded_keys':[j['key'] for j in store.read(CATALOG)['jobs'] if self.server.assistant.preferences.excluded(j)],
                    'allowed_keys':[j['key'] for j in self.server.assistant.visible_jobs()],
                    'companies':group_companies(self.server.assistant.visible_jobs())})
        if path == '/':
            return self.send((BASE / 'web' / 'index.html').read_bytes(), mime='text/html; charset=utf-8')
        if path == '/assistant.js':
            return self.send((BASE / 'web' / 'assistant.js').read_bytes(), mime='text/javascript; charset=utf-8')
        if path == '/feedback.js':
            return self.send((BASE / 'web' / 'feedback.js').read_bytes(), mime='text/javascript; charset=utf-8')
        if path == '/company.js':
            return self.send((BASE / 'web' / 'company.js').read_bytes(), mime='text/javascript; charset=utf-8')
        if path == '/features.js':
            return self.send((BASE / 'web' / 'features.js').read_bytes(), mime='text/javascript; charset=utf-8')
        if path in ('/api/export/ledger', '/' + LEDGER, '/api/export/catalog'):
            with store.lock:
                return self.send(store.read(CATALOG if path.endswith('catalog') else LEDGER))
        if path.startswith(('/原版简历/', '/简历定制/', '/resumes/')):
            file = (store.root / path.lstrip('/')).resolve()
            if store.root not in file.parents or file.suffix.lower() not in ('.pdf', '.docx', '.doc', '.txt', '.md') or not file.is_file():
                return self.send({'error': 'Not found'}, 404)
            return self.send(file.read_bytes(), mime=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        self.send({'error': 'Not found'}, 404)

    def do_POST(self):
        port = self.server.server_port
        if not self.host_ok() or self.headers.get('Origin') not in (f'http://127.0.0.1:{port}', f'http://localhost:{port}') or not secrets.compare_digest(self.headers.get('X-Tracker-Token', ''), self.server.token):
            return self.send({'error': '请从本机看板操作'}, 403)
        endpoint = urlparse(self.path).path
        if endpoint not in ('/api/change', '/api/assistant', '/api/preferences', '/api/startup', '/api/career', '/api/mailbox', '/api/day', '/api/feedback'):
            return self.send({'error': 'Not found'}, 404)
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 8_000_000:
                raise ValueError('请求内容为空或超过8MB')
            p = json.loads(self.rfile.read(n))
            if not isinstance(p,dict): raise ValueError('请求必须是对象')
            if endpoint == '/api/feedback':
                if p.get('op')=='save':return self.send(self.server.feedback.save(p))
                if p.get('op')=='analyze':return self.send(self.server.feedback.analyze(p.get('key')))
                raise ValueError('未知反馈操作')
            if endpoint == '/api/day': return self.send(self.server.assistant.daily_queue.change(p))
            if endpoint == '/api/mailbox':
                engine=self.server.mailchecks
                if p.get('op')=='connect':return self.send(engine.connect(p))
                if p.get('op')=='disconnect':return self.send(engine.disconnect(p.get('address')))
                if p.get('op')=='check':return self.send(engine.check(p.get('key')))
                raise ValueError('未知邮箱操作')
            if endpoint == '/api/preferences': return self.send(self.server.assistant.preferences.change(p))
            if endpoint == '/api/startup': return self.send(self.server.startup.set(p.get('enabled')))
            if endpoint == '/api/career':
                engine=self.server.assistant
                if p.get('op')=='analyze': return self.send(engine.analyze_career(p))
                if p.get('op')=='progress': return self.send(engine.project_progress(p))
                raise ValueError('未知分析操作')
            if endpoint == '/api/assistant':
                engine = self.server.assistant
                op = p.get('op')
                if op == 'settings': result = {'settings': engine.save_settings(p)}
                elif op == 'generate': result = engine.start(force=True)
                elif op == 'extract': result = {'text': engine.extract_resume(p.get('path', ''))}
                elif op == 'draft': result = {'draft': engine.draft(p.get('key'))}
                elif op == 'apply_draft': result = engine.apply_draft(p.get('id'))
                elif op == 'apply_pdf': result = engine.apply_pdf(p.get('id'))
                else: raise ValueError('未知AI操作')
                return self.send(result)
            with self.server.store.lock:
                result = self.server.store.change(p)
                self.send({**result, 'ledger': self.server.store.read(LEDGER), 'catalog': self.server.store.read(CATALOG)})
        except (ValueError, TypeError, KeyError) as e:
            self.send({'error': str(e)}, 400)
        except OSError:
            self.send({'error': '本地模型未就绪或连接中断，请查看AI设置' if endpoint == '/api/assistant' else '文件写入失败，请检查数据目录权限'}, 500)


def main():
    parser = argparse.ArgumentParser(description='Offline job tracker (localhost only)')
    parser.add_argument('--data-dir', type=Path, help='Existing data folder, or a new empty folder')
    parser.add_argument('--port', type=int, default=18728)
    parser.add_argument('--open', action='store_true', help='Open the dashboard in your browser')
    args = parser.parse_args()
    config_path = BASE / 'config.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
    directory = args.data_dir or Path(config.get('data_dir', str(BASE / 'data')))
    if not directory.is_absolute():
        directory = BASE / directory
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    try:
        server = Server(directory, args.port)
    except (OSError, ValueError) as e:
        parser.exit(1, f'Cannot start tracker: {e}\n')
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'Autumn Job Tracker: {url}\nData: {server.store.root}\nCtrl+C to stop.', flush=True)
    if args.open:
        webbrowser.open(url)
    threading.Thread(target=server.assistant.scheduler, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.assistant.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
