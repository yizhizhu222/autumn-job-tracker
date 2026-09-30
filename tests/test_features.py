from quality_fixture import mock_quality
import json
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
from pathlib import Path
import app
import career
import recommendations
from preferences import Preferences, region_matches, platform
from startup import Startup


class FeatureTests(unittest.TestCase):
    def setUp(self):
        mock_quality(self)
        self.temp=tempfile.TemporaryDirectory(); self.store=app.Store(self.temp.name)
        self.prefs=Preferences(self.store,app.same_job)
        self.engine=recommendations.Assistant(self.store,lambda:date(2026,9,29),app.same_job)
        self.engine.save_settings({'search_enabled':False})
    def tearDown(self): self.temp.cleanup()
    def add(self, role='数据分析', url='https://www.nowcoder.com/jobs/1', place='深圳'):
        self.store.change({'op':'add_job','company':'Example','role':role,'url':url,'place':place,'requirements':'SQL查询、数据分析与报表可视化\n本科应届'})
        return self.store.read(app.CATALOG)['jobs'][-1]
    def test_region_province_city_unknown_and_national(self):
        self.assertTrue(region_matches({'place':'深圳 / 上海'},{'province':'广东'}))
        self.assertFalse(region_matches({'place':'杭州'},{'province':'广东'}))
        self.assertTrue(region_matches({'place':'全国多地'},{'province':'贵州','city':'贵阳'}))
        self.assertFalse(region_matches({'place':'待确认'},{'city':'贵阳','include_unknown':False}))
        self.assertFalse(region_matches({'place':'上海，线上面试'},{'city':'贵阳'}))
        self.prefs.change({'op':'region','province':'广东','city':'深圳'})
        self.assertEqual(Preferences(self.store,app.same_job).read()['city'],'深圳')
    def test_exclude_alias_duplicate_restore_and_ledger_unchanged(self):
        j=self.add(); before=self.store.read(app.LEDGER)
        result=self.prefs.change({'op':'exclude','kind':'job','key':j['key'],'reason':'不适合'})
        alias=dict(j,key='other',company='display name',aliases=[j['key']])
        self.assertTrue(self.prefs.excluded(alias))
        self.assertEqual(self.store.read(app.LEDGER),before)
        self.prefs.change({'op':'restore','id':result['rules'][0]['id']})
        self.assertFalse(self.prefs.excluded(j))
    def test_platform_exact_boundary_and_role_keyword(self):
        j=self.add(); self.prefs.change({'op':'exclude','kind':'platform','key':j['key']})
        self.assertTrue(self.prefs.excluded(dict(j,apply_url='https://m.nowcoder.com/jobs/2')))
        self.assertFalse(self.prefs.excluded(dict(j,apply_url='https://nowcoder.com.evil.example/a')))
        self.assertFalse(self.prefs.excluded(dict(j,apply_url='https://company.example/jobs/1')))
        self.prefs.change({'op':'exclude','kind':'role','value':'电话销售'})
        self.assertTrue(self.prefs.excluded({'role':'电话销售管培生'}))
    def test_daily_excludes_rules_and_region_even_after_restart(self):
        blocked=self.add();other=self.add('实施','https://company.example/job','贵阳')
        self.prefs.change({'op':'exclude','kind':'job','key':blocked['key']})
        self.prefs.change({'op':'region','province':'贵州','include_unknown':False})
        self.engine.busy.acquire()
        with patch.object(self.engine,'model_status',return_value={'available':False}): self.engine.run()
        report=self.engine.status()['report'];self.assertEqual([j['key'] for j in report['items']],[other['key']])
        self.prefs.change({'op':'exclude','kind':'job','key':other['key']})
        self.assertEqual(self.engine.status()['report']['items'],[])
    def test_empty_resume_projects_have_evidence_and_no_invented_skills(self):
        j=self.add(); plan=career.build_plan('数据科学与大数据技术','',[j])
        self.assertEqual(plan['evidence'],{})
        self.assertEqual(plan['current_jobs'][0]['matched'],[])
        p=next(p for p in plan['projects'] if p['id']=='data')
        self.assertEqual(p['covered_jobs'],1);self.assertTrue(p['jobs_after'][0]['gained'])
        self.assertGreaterEqual(len(p['acceptance']),4)
        self.assertEqual(p['status'],'planned')
    def test_project_does_not_erase_degree_requirement(self):
        j=self.add();j['requirements']=['硕士及以上，SQL、数据分析']
        plan=career.build_plan('数据科学','Python项目经历',[j])
        self.assertTrue(plan['projects'])
        self.assertTrue(all(p['covered_jobs']==0 and not p['jobs_after'] for p in plan['projects']))
        self.assertTrue(plan['current_jobs'][0]['hard_conditions'])
    def test_career_completion_requires_proof_and_never_mutates_resume(self):
        plan=career.build_plan('数据科学','',[self.add()]);self.store.write(career.FILE,plan)
        with self.assertRaises(ValueError):self.engine.project_progress({'id':plan['projects'][0]['id'],'status':'completed','evidence':''})
        self.engine.project_progress({'id':plan['projects'][0]['id'],'status':'completed','evidence':'成果保存在本地项目目录，已按四项验收标准实际复现并记录问题。'})
        self.assertEqual(self.engine.settings()['profile'],'')
        self.assertEqual(self.store.read(career.FILE)['projects'][0]['status'],'completed')
    def test_career_status_hides_newly_excluded_and_applied(self):
        j=self.add();self.store.write(career.FILE,career.build_plan('数据科学','SQL',[j]))
        self.prefs.change({'op':'exclude','kind':'job','key':j['key']})
        self.assertEqual(self.engine.career_status()['plan']['current_jobs'],[])

    def test_cached_aliases_never_return_after_mark_or_restart(self):
        j=self.add()
        duplicate=dict(j,key='other-platform',aliases=[j['key']])
        catalog=self.store.read(app.CATALOG);catalog['jobs'].append(duplicate);self.store.write(app.CATALOG,catalog)
        self.store.write(recommendations.DAILY,{'items':[j,duplicate]})
        self.store.write(career.FILE,career.build_plan('数据科学','',[j,duplicate]))
        self.assertEqual(len(self.engine.pending_jobs()),1)
        self.store.change({'op':'mark','key':j['key'],'evidence':'真实提交成功'})
        for progress in ('等待回复','拒绝','撤回'):
            self.store.change({'op':'update','key':j['key'],'progress':progress})
            restarted=recommendations.Assistant(app.Store(self.temp.name),lambda:date(2026,9,30),app.same_job)
            self.assertEqual(restarted.pending_jobs(),[])
            self.assertEqual(restarted.status()['report']['items'],[])
            plan=restarted.career_status()['plan']
            self.assertEqual(plan['current_jobs'],[])
            self.assertTrue(all(not p['jobs_after'] for p in plan['projects']))

    def test_stale_report_uses_current_platform_preferences(self):
        j=self.add();old=dict(j,apply_url='https://old.example/job')
        self.store.write(recommendations.DAILY,{'items':[old]})
        self.prefs.change({'op':'exclude','kind':'platform','key':j['key']})
        self.assertEqual(self.engine.status()['report']['items'],[])
    def test_startup_unsupported_and_failed_change_does_not_claim_success(self):
        s=Startup(Path(self.temp.name),18728,Path(self.temp.name))
        with patch('startup.sys.platform','linux'):
            self.assertFalse(s.status()['supported'])
            with self.assertRaises(ValueError):s.set(True)
        with patch('startup.sys.platform','win32'),patch.object(s,'task',return_value={'managed':True}),patch.object(s,'status',return_value={'enabled':False}):
            with self.assertRaises(ValueError):s.set(True)

if __name__=='__main__':unittest.main()
