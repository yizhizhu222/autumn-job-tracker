import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

import app
import recommendations
from daily_queue import FILE, repeat_reason


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = app.Store(self.temp.name)
        self.day = date(2026, 9, 29)
        self.engine = recommendations.Assistant(self.store, lambda: self.day, app.same_job)

    def tearDown(self): self.temp.cleanup()

    def add(self, company, role='数据分析'):
        self.store.change({'op':'add_job', 'company':company, 'role':role, 'url':'https://example.org/jd'})
        return self.store.read(app.CATALOG)['jobs'][-1]

    def seen(self, j): self.engine.daily_queue.change({'op':'seen', 'key':j['key']})

    def test_ten_roles_fixed_no_refill_restart_and_next_day_new_companies(self):
        for i in range(16):
            self.add('公司'+str(i)); self.add('公司'+str(i), '数据运营')
        first = self.engine.daily_view()
        self.assertEqual(first['allocated'], 10)
        self.assertEqual(len(first['companies']), 10)
        before = self.store.read(app.LEDGER)
        for job in first['items']: self.seen(job)
        self.assertEqual(self.store.read(app.LEDGER), before)
        self.assertTrue(self.engine.daily_view()['complete'])
        self.engine = recommendations.Assistant(self.store, lambda:self.day, app.same_job)
        self.assertEqual(self.engine.visible_jobs(), [])
        self.engine.save_settings({'target':20})
        self.assertEqual(self.engine.settings()['target'], 10)
        self.store.write(recommendations.DAILY, {'date':self.day.isoformat(), 'items':self.store.read(app.CATALOG)['jobs']})
        self.assertEqual(self.engine.status()['report']['items'], [])
        self.engine.save_settings({'search_enabled':False})
        self.engine.busy.acquire()
        with patch.object(self.engine,'model_status',return_value={'available':False}): self.engine.run()
        self.assertEqual(self.engine.visible_jobs(), [])
        self.day += timedelta(days=1)
        second = self.engine.daily_view()
        self.assertEqual(second['allocated'], 10)
        self.assertFalse({j['company'] for j in first['items']} & {j['company'] for j in second['items']})

    def test_company_seen_hides_siblings_and_undo_restores_only_original_slots(self):
        self.add('同一公司'); self.add('同一公司', '运营'); self.add('其他公司')
        first = self.engine.daily_view(); target = next(j for j in first['items'] if j['company']=='同一公司')
        self.seen(target)
        self.assertEqual(self.engine.daily_view()['handled'],2)
        self.assertEqual(len(self.engine.visible_jobs()),1)
        self.add('后来加入的公司')
        self.engine.daily_queue.change({'op':'undo_seen', 'key':target['key']})
        self.assertEqual(len(self.engine.visible_jobs()),3)
        self.assertEqual(self.engine.daily_view()['allocated'],3)

    def test_applied_company_never_qualifies_for_repeat(self):
        a=self.add('甲');self.add('甲','运营');self.add('乙')
        self.engine.daily_view()
        self.store.change({'op':'mark','key':a['key'],'evidence':'提交成功'})
        self.assertTrue(all(j['company']!='甲' for j in self.engine.visible_jobs()))
        self.day+=timedelta(days=8)
        self.assertTrue(all(j['company']!='甲' for j in self.engine.visible_jobs()))

    def strong(self, j):
        catalog=self.store.read(app.CATALOG)
        job=next(x for x in catalog['jobs'] if x['key']==j['key'])
        job.update(match='高', online_confirmed=True, salary_min_confirmed=True, direct=True,
                   requirements=['2027届本科，SQL、Excel、数据分析'], duties=[])
        self.store.write(app.CATALOG,catalog)
        self.engine.save_settings({'profile':'使用SQL和Excel完成数据分析项目'})
        return job

    def test_high_fit_requires_evidence_and_cooldown_with_visible_reason(self):
        a=self.add('甲');self.engine.daily_view();self.seen(a)
        a=self.strong(a)
        self.assertFalse(repeat_reason(a,''))
        self.assertFalse(repeat_reason(a,'计划学习SQL、Excel和数据分析'))
        self.assertTrue(repeat_reason(a,self.engine.settings()['profile']))
        self.day+=timedelta(days=1)
        self.assertEqual(self.engine.visible_jobs(),[])
        b=self.add('甲','数据运营'); self.strong(b)
        result=self.engine.daily_view()
        self.assertEqual([j['key'] for j in result['items']],[b['key']])
        self.assertIn('高匹配例外',result['items'][0]['repeat_reason'])
        self.day+=timedelta(days=7)
        self.assertTrue(self.engine.visible_jobs())

    def test_upgrade_preserves_allocated_applied_slots_and_legacy_company_history(self):
        a=self.add('昨天公司');b=self.add('今日公司');c=self.add('新公司')
        self.store.write('recommendation-history.json',{'2026-09-28':{'keys':[a['key']]}})
        self.store.write(recommendations.DAILY,{'date':self.day.isoformat(),'items':[b]})
        self.store.change({'op':'mark','key':b['key'],'evidence':'已提交'})
        self.assertTrue(self.engine.daily_view()['complete'])
        self.assertEqual(self.engine.daily_view()['allocated'],1)
        self.day+=timedelta(days=1)
        self.assertEqual([j['key'] for j in self.engine.visible_jobs()],[c['key']])

    def test_filter_does_not_reset_batch_or_claim_done_and_unknown_key_rejected(self):
        a=self.add('甲');self.engine.daily_view()
        with self.assertRaises(ValueError):self.seen({'key':'missing'})
        prefs=self.engine.preferences
        prefs.change({'op':'region','province':'广东','city':'深圳','include_unknown':False})
        d=self.engine.daily_view()
        self.assertEqual(d['allocated'],1)
        self.assertFalse(d['complete'])
        self.assertEqual(d['remaining'],0)
        self.assertTrue((self.store.root/FILE).exists())

    def test_empty_pool_can_later_receive_first_batch(self):
        self.assertFalse(self.engine.daily_view()['complete'])
        self.add('新公司')
        self.assertEqual(self.engine.daily_view()['allocated'],1)

    def test_upgrade_retires_old_repeated_companies_without_replacing_slots(self):
        a=self.add('历史重复公司');self.add('以后再看的公司')
        self.store.write('recommendation-history.json',{'2026-09-28':{'keys':[a['key']]}})
        self.store.write(recommendations.DAILY,{'date':self.day.isoformat(),'items':[a]})
        result=self.engine.daily_view()
        self.assertEqual(result['allocated'],1)
        self.assertEqual(result['items'],[])
        self.assertTrue(result['complete'])


if __name__=='__main__': unittest.main()
