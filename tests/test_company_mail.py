import json
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
import app,career,recommendations
from companies import same_company,group_companies
from mailcheck import MailChecks,address

class CompanyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=app.Store(self.temp.name)
        self.engine=recommendations.Assistant(self.store,lambda:date(2026,9,29),app.same_job)
    def tearDown(self):self.temp.cleanup()
    def add(self,company,role):
        self.store.change({'op':'add_job','company':company,'role':role,'url':'https://example.org/jd','requirements':'本科，SQL数据分析与可视化报表；需要技术文档能力。'})
        return self.store.read(app.CATALOG)['jobs'][-1]
    def test_company_group_and_legacy_application_hide_every_role(self):
        a=self.add('示例科技有限公司','数据分析');b=self.add('示例科技','实施顾问');c=self.add('其他公司','数据分析')
        self.assertEqual(len(group_companies([a,b,c])),2)
        self.store.write(recommendations.DAILY,{'items':[a,b,c]})
        self.store.change({'op':'mark','key':a['key'],'evidence':'提交成功'})
        self.assertEqual([j['key'] for j in self.engine.pending_jobs()],[c['key']])
        self.assertEqual(len(self.engine.status()['report']['companies']),1)
        with self.assertRaises(ValueError):self.store.change({'op':'mark','key':b['key'],'evidence':'重复公司'})
        self.store.change({'op':'undo','key':a['key']})
        self.assertEqual(len(self.engine.pending_jobs()),3)
    def test_company_exclusion_hides_sibling_roles_and_restores(self):
        a=self.add('示例公司','数据分析');self.add('示例公司','数据运营')
        prefs=self.engine.preferences.change({'op':'exclude','kind':'company','key':a['key']})
        self.assertEqual(self.engine.pending_jobs(),[])
        self.engine.preferences.change({'op':'restore','id':prefs['rules'][0]['id']})
        self.assertEqual(len(self.engine.pending_jobs()),2)
    def test_company_identity_is_not_fuzzy(self):
        self.assertFalse(same_company({'company':'量子甲'},{'company':'量子甲分公司'}))
        self.assertFalse(same_company({'company':'量子甲'},{'company':'量子乙'}))
        self.assertTrue(same_company({'company':'甲','company_aliases':['乙']},{'company':'乙有限公司'}))
    def test_fixed_batch_does_not_replace_handled_company(self):
        a=self.add('已投公司','数据分析')
        self.engine.daily_view()
        self.add('新公司','数据分析');self.add('新公司','数据运营')
        self.store.change({'op':'mark','key':a['key'],'evidence':'已提交'})
        report=self.engine.status()['report']
        self.assertEqual(report['companies'],[])
        self.assertTrue(report['daily']['complete'])
    def test_project_needs_relevant_real_jd_not_just_major(self):
        self.assertEqual(career.build_plan('数据科学','',[])['projects'],[])
        job=self.add('Example','电话销售');self.assertEqual(career.build_plan('数据科学','',[job])['projects'],[])
        job['role']='数据分析师';plan=career.build_plan('数据科学','',[job])
        self.assertTrue(plan['projects'])
        for p in plan['projects']:
            self.assertGreater(p['covered_jobs'],0);self.assertTrue(p['demand_map']);self.assertTrue(p['resume_outline'])
            self.assertTrue(all('【' in line for line in p['resume_outline']))
        job['requirements']=['沟通能力，工作认真'];self.assertEqual(career.build_plan('数据科学','',[job])['projects'],[])

class FakeIMAP:
    def __init__(self):self.selections=[];self.calls=[]
    def list(self):return 'OK',[b'(\\HasNoChildren \\Junk) "/" "Spam"']
    def select(self,folder,readonly=False):self.selections.append(readonly);return 'OK',[b'1']
    def uid(self,*args):
        self.calls.append(args)
        if args[0]=='search':return 'OK',[b'42']
        return 'OK',[(b'42',b'From: hr@example.org\r\nTo: person@qq.com\r\nSubject: Interview invitation\r\nDate: Tue, 29 Sep 2026 09:00:00 +0800\r\nMessage-ID: <one@example.org>\r\n')]
    def logout(self):pass

class MailTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=app.Store(self.temp.name);self.mail=MailChecks(self.store)
        self.store.change({'op':'manual','company':'Example','role':'Support','date':app.today().isoformat(),'evidence':'已发送','applicant_email':'person@qq.com','recruiter_email':'hr@example.org','application_channel':'email'})
        self.key=next(iter(self.store.read(app.LEDGER)['applications']))
    def tearDown(self):self.temp.cleanup()
    def test_readonly_headers_spam_dedup_and_no_progress_fabrication(self):
        fake=FakeIMAP();before=self.store.read(app.LEDGER)
        with patch.object(self.mail,'login',return_value=fake):
            first=self.mail.check(self.key);second=self.mail.check(self.key)
        self.assertEqual(first['status'],'已检查');self.assertEqual(first['new_count'],1);self.assertEqual(second['new_count'],0)
        self.assertTrue(all(fake.selections));self.assertTrue(all('BODY.PEEK' in a[2] for a in fake.calls if a[0]=='fetch'))
        self.assertEqual(before,self.store.read(app.LEDGER))
    def test_failed_check_not_no_mail(self):
        with patch.object(self.mail,'login',side_effect=OSError('offline')):result=self.mail.check(self.key)
        self.assertEqual(result['status'],'未检查');self.assertIsNone(result['last_success_at'])
    def test_password_not_persisted_or_returned(self):
        with patch.object(self.mail,'login',return_value=FakeIMAP()):state=self.mail.connect({'provider':'qq','address':'person@qq.com','secret':'a-secret-code'})
        self.assertNotIn('a-secret-code',json.dumps(state))
        self.assertFalse((self.store.root/'mail-checks.json').exists())
        self.mail.disconnect('person@qq.com');self.assertEqual(self.mail.status()['connected'],[])
        for bad in ('x@example.org\r\nALL','x"@example.org'):
            with self.assertRaises(ValueError):address(bad)

if __name__=='__main__':unittest.main()
