"""Durable Beijing-day batches. Viewing a company never records an application."""
import copy
import re
from datetime import date

import career
from companies import same_company, group_companies

FILE = 'daily-queue.json'
LIMIT = 10
REST_MESSAGE = '今天已经努力得够多了，休息一下，去做点让自己开心的事吧。结果不全由我们掌控，但今天能做的，我们已经认真做了。'


def repeat_reason(job, profile):
    """A high model label alone cannot override the company history."""
    if job.get('match') not in ('高', '高度匹配', '高匹配'): return ''
    if not job.get('direct') or not job.get('online_confirmed'): return ''
    facts = ' '.join(job.get('requirements', [])) + str(job.get('eligibility', ''))
    if '本科' not in facts or not re.search(r'2027|27届', facts): return ''
    if not job.get('salary_min_confirmed') and '量子' not in str(job.get('group', '')) + job.get('role', ''): return ''
    positive = '\n'.join(line for line in profile.splitlines()
                         if not re.search(r'不会|不了解|未掌握|未接触|缺乏|尚未|学习中|计划', line))
    known = {k for k, v in career.evidence(positive).items() if v}
    a = career.job_analysis(job, known)
    if a['hard_conditions'] or a['missing'] or len(a['matched']) < 3: return ''
    if not str(a['url']).startswith(('https://', 'http://')): return ''
    return '高匹配例外：简历与JD均有' + '、'.join(a['matched']) + '证据；本科届别、线上面试及薪资条件已核对。技能覆盖不代表录用概率。'


class DailyQueue:
    def __init__(self, store, today, same_job):
        self.store, self.today, self.same_job = store, today, same_job

    def read(self):
        if (self.store.root / FILE).exists(): return self.store.read(FILE)
        # Preserve the saved batch on upgrade, including slots already handled.
        catalog = self.store.read('岗位库.json')['jobs']
        days = {}
        history = self.store.read('recommendation-history.json') if (self.store.root / 'recommendation-history.json').exists() else {}
        for day, report in history.items():
            if day >= self.today().isoformat(): continue
            entries = [copy.deepcopy(j) for j in catalog if j['key'] in report.get('keys', [])]
            days[day] = {'entries': entries, 'seen': [], 'imported': True}
        if (self.store.root / 'daily-recommendations.json').exists():
            report = self.store.read('daily-recommendations.json')
            day = report.get('date', '')
            if day and day <= self.today().isoformat() and report.get('items'):
                days[day] = {'entries': copy.deepcopy(report['items'][:LIMIT]), 'seen': [], 'imported': True}
        return {'schema': 1, 'days': days}

    def view(self, jobs, profile, applied, excluded):
        with self.store.lock:
            state = self.read(); before = copy.deepcopy(state)
            day = self.today().isoformat()
            batch = state['days'].setdefault(day, {'entries': [], 'seen': []})
            prior = [(d, j) for d, b in state['days'].items() if d < day for j in b['entries']]
            if not batch['entries']:
                candidates = []
                for job in jobs:
                    previous = [(d, j) for d, j in prior if same_company(job, j)]
                    reason = ''
                    if previous:
                        reason = repeat_reason(job, profile)
                        # Avoid recycling yesterday's same role even if the AI calls it high fit.
                        recent_same = any(self.same_job(job, j) and (self.today() - date.fromisoformat(d)).days < 7 for d, j in previous)
                        if not reason or recent_same: continue
                    candidates.append(dict(job, repeat_reason=reason))
                # Breadth first, then a second role per company, never more than ten roles.
                selected = []
                for maximum in (1, 2):
                    for job in candidates:
                        if len(selected) >= LIMIT: break
                        if any(self.same_job(job, j) for j in selected): continue
                        if sum(same_company(job, j) for j in selected) >= maximum: continue
                        selected.append(job)
                batch['entries'] = copy.deepcopy(selected)
            if batch.get('imported') and not batch.get('migration_checked'):
                for entry in batch['entries']:
                    previous = [(d, j) for d, j in prior if same_company(entry, j)]
                    if previous:
                        reason = repeat_reason(entry, profile)
                        recent_same = any(self.same_job(entry, j) and (self.today() - date.fromisoformat(d)).days < 7 for d, j in previous)
                        entry['retired_repeat'] = not reason or recent_same
                        if not entry['retired_repeat']: entry['repeat_reason'] = reason
                batch['migration_checked'] = True
            items, handled = [], 0
            for entry in batch['entries']:
                if entry.get('retired_repeat') or any(same_company(entry, a) for a in applied + batch['seen']) or excluded(entry):
                    handled += 1; continue
                current = next((j for j in jobs if self.same_job(entry, j)), None)
                if current:
                    items.append(dict(current, repeat_reason=entry.get('repeat_reason', '')))
            if state != before or not (self.store.root / FILE).exists(): self.store.write(FILE, state)
            return {'date': day, 'limit': LIMIT, 'allocated': len(batch['entries']), 'handled': handled,
                    'remaining': len(items), 'complete': bool(batch['entries']) and handled == len(batch['entries']),
                    'items': items, 'companies': group_companies(items), 'rest_message': REST_MESSAGE,
                    'seen_companies': [{'key': j['key'], 'company': j['company']} for j in batch['seen']]}

    def change(self, data):
        with self.store.lock:
            state = self.read(); batch = state['days'].get(self.today().isoformat())
            if not batch: raise ValueError('请先打开今日推荐')
            job = next((j for j in batch['entries'] if j['key'] == data.get('key')), None)
            if job is None: raise ValueError('该公司不在今日清单中')
            if data.get('op') == 'seen':
                if not any(same_company(job, j) for j in batch['seen']): batch['seen'].append(copy.deepcopy(job))
            elif data.get('op') == 'undo_seen':
                batch['seen'] = [j for j in batch['seen'] if not same_company(job, j)]
            else: raise ValueError('未知查看操作')
            self.store.write(FILE, state)
            return {'ok': True}
