import copy
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
import app,career,recommendations
from opportunity_quality import assess
from quality_fixture import qualify

class SupplyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=app.Store(self.temp.name)
        self.day=date(2026,9,30);self.engine=recommendations.Assistant(self.store,lambda:self.day,app.same_job)
    def tearDown(self):self.temp.cleanup()
    def add(self,i):
        self.store.change({'op':'add_job','company':f'企业{i}','role':'数据分析','url':f'https://example.org/{i}'})
        return qualify(self.store,self.engine,self.store.read(app.CATALOG)['jobs'][-1],self.day)
    def test_unknown_conditions_and_low_skill_match_remain_visible(self):
        j=self.add(0);j.update(online_confirmed=False,salary_min_confirmed=False)
        q=assess(j,'SQL',self.day,True)
        self.assertTrue(q['ready']);self.assertTrue(q['recommended'])
        self.assertIn('线上面试待确认',q['unknown'])
        self.assertTrue(assess(j,'',self.day,False)['recommended'])
        self.assertFalse(assess(dict(j,status='closed'),'SQL',self.day,True)['recommended'])
    def test_six_recommendations_when_no_direct_slots_and_no_handled_refill(self):
        jobs=[self.add(i) for i in range(6)]
        catalog=self.store.read(app.CATALOG)
        for j in catalog['jobs']:j['direct']=False
        self.store.write(app.CATALOG,catalog)
        d=self.engine.daily_view();self.assertEqual(d['allocated'],6);self.assertEqual(d['shortfall'],0)
        self.assertEqual(d['lanes']['recommend']['allocated'],6)
        self.assertEqual(len(d['companies']),6)
        for j in d['items']:self.engine.daily_queue.change({'op':'seen','key':j['key']})
        self.add(7);self.assertTrue(self.engine.daily_view()['complete']);self.assertEqual(self.engine.daily_view()['items'],[])
    def test_partial_batch_fills_only_original_minimum_not_handled_slots(self):
        a=self.add(0);self.engine.daily_view();self.engine.daily_queue.change({'op':'seen','key':a['key']})
        for i in range(1,9):self.add(i)
        d=self.engine.daily_view();self.assertEqual(d['allocated'],6);self.assertEqual(d['handled'],1);self.assertEqual(d['remaining'],5)
        self.assertNotIn(a['key'],[j['key'] for j in d['items']])
    def test_projects_survive_empty_today_and_existing_skills(self):
        j=self.add(0);profile=self.engine.settings()['profile']
        plan=career.build_plan('数据科学',profile,[j])
        supported=[p for p in plan['projects'] if p['covered_jobs']]
        self.assertTrue(supported);self.assertTrue(supported[0]['jobs_after'][0]['reinforced'])
        supported[0].update(status='working',completion_evidence='已经建立数据字典')
        self.store.write(career.FILE,plan);self.engine.daily_view()
        self.engine.daily_queue.change({'op':'seen','key':j['key']})
        result=self.engine.career_status()['plan']
        self.assertTrue(result['projects']);self.assertEqual(result['current_jobs'],[])
        self.assertEqual(result['projects'][0]['status'],'working')
    def test_blank_catalog_has_honest_executable_major_projects(self):
        plan=career.build_plan('数据科学','',[])
        self.assertEqual(len(plan['projects']),3)
        for p in plan['projects']:
            self.assertEqual(p['covered_jobs'],0);self.assertEqual(p['jobs_after'],[])
            self.assertIn('等待岗位验证',p['evidence_level'])
            self.assertTrue(p['steps'] and p['acceptance'] and p['resume_outline'])
    def test_public_pool_is_dated_has_six_distinct_companies_and_no_personal_data(self):
        self.assertEqual(recommendations.public_opportunities(date(2026,9,29)),[])
        self.assertEqual(recommendations.public_opportunities(date(2026,11,1)),[])
        jobs=recommendations.public_opportunities(self.day)
        self.assertGreaterEqual(len({j['company'] for j in jobs}),6)
        for j in jobs:
            self.assertNotIn('resume',j);self.assertTrue(j['duties'] and j['requirements'])
            self.assertTrue(assess(j,'SQL Python 数据分析 文档 沟通',self.day,True)['recommended'],j['company'])
    def test_failed_daily_retries_after_backoff_but_not_every_poll(self):
        self.store.write(recommendations.DAILY,{'date':str(self.day),'items':[],'attempt_epoch':1000})
        with patch('recommendations.time.time',return_value=1100):self.assertFalse(self.engine.start()['started'])
        with patch('recommendations.time.time',return_value=2900),patch('recommendations.threading.Thread') as worker:
            self.assertTrue(self.engine.start()['started']);worker.return_value.start.assert_called_once()
        self.engine.busy.release()

if __name__=='__main__':unittest.main()
