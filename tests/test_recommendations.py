import copy
import json
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
import app
import recommendations as rec


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=app.Store(self.temp.name)
        self.engine=rec.Assistant(self.store,lambda:date(2026,9,28),app.same_job)
        self.engine.save_settings({'search_enabled':False})
    def tearDown(self): self.temp.cleanup()
    def add(self,company='Example',role='开发工程师'):
        self.store.change({'op':'add_job','company':company,'role':role,'url':'https://example.org/job'})
        return self.store.read(app.CATALOG)['jobs'][-1]
    def run_daily(self):
        self.engine.busy.acquire()
        with patch.object(self.engine,'model_status',return_value={'available':False}): self.engine.run()
        return self.engine.status()['report']
    def test_low_fit_not_empty_and_submitted_excluded(self):
        first=self.add();second=self.add('Other','支持工程师')
        self.store.change({'op':'mark','key':first['key'],'evidence':'submitted'})
        result=self.run_daily()
        self.assertEqual([j['key'] for j in result['items']],[second['key']])
        self.assertEqual(result['items'][0]['tier'],'待确认')
        self.assertIn('线上面试尚未确认',result['items'][0]['recommendation_warnings'])
    def test_daily_once_and_company_diversity(self):
        for i in range(5): self.add('Company',str(i))
        self.add('Other','Support')
        result=self.run_daily()
        self.assertEqual(len(result['items']),3)
        self.assertFalse(self.engine.start()['started'])
    def test_no_fake_jobs_when_exhausted(self):
        result=self.run_daily()
        self.assertEqual(result['items'],[])
        self.assertTrue(result['empty_reason'])
    def test_resume_only_local_endpoint_and_no_cloud_models(self):
        with self.assertRaises(ValueError): self.engine.save_settings({'model':'qwen:cloud'})
        with patch('recommendations.ollama',return_value={'message':{'content':'{"ok":true}'}}) as mock:
            self.assertTrue(rec.ai_json('qwen3:4b','Return JSON',{'resume':'private'})['ok'])
            self.assertFalse(mock.call_args.args[0]['stream'])
    def test_edits_preserve_structure_and_protected_facts(self):
        text='负责项目文档整理并协助团队沟通。\n维护已有数据处理流程。'
        edits=[{'before':'负责项目文档整理并协助团队沟通。','after':'整理项目文档，协助团队沟通。','reason':'强调文档支持'}]
        self.assertEqual(len(rec.validate_edits(text,edits)),1)
        for bad in ([{'before':'本科毕业于示例大学','after':'硕士毕业于示例大学'}],
                    [{'before':'完成3个项目的整理','after':'完成9个项目的整理'}],
                    [{'before':'负责项目文档整理并协助团队沟通。','after':'新增第一段\n新增第二段'}]):
            with self.assertRaises(ValueError): rec.validate_edits(text+'本科毕业于示例大学完成3个项目的整理',bad)
    def test_variant_is_reused_original_preserved(self):
        source='负责项目文档整理并协助团队沟通。\n维护已有数据处理流程。'
        drafts={'items':[{'id':'abc','source_text':source,'edits':[{'before':'负责项目文档整理并协助团队沟通。','after':'整理项目文档，协助团队沟通。','reason':'更简洁'}]}]}
        self.store.write(rec.DRAFTS,drafts)
        a=self.engine.apply_draft('abc');b=self.engine.apply_draft('abc')
        self.assertEqual(a['path'],b['path'])
        self.assertEqual(len(list((self.store.root/'简历定制').iterdir())),1)
        self.assertEqual(self.store.read(rec.DRAFTS)['items'][0]['source_text'],source)
    def test_resume_path_cannot_escape(self):
        with self.assertRaises(ValueError): self.engine.resume_file('../../secret.txt')
    def test_tailoring_uses_recommended_baseline_not_unrelated_profile(self):
        job=self.add()
        folder=self.store.root/'resumes';folder.mkdir()
        original='负责项目文档整理并协助团队沟通。'
        (folder/'base.txt').write_text(original,encoding='utf-8')
        catalog=self.store.read(app.CATALOG)
        catalog['jobs'][0]['base']='support'
        catalog['originals']={'support':{'path':'resumes/base.txt'}}
        self.store.write(app.CATALOG,catalog)
        self.engine.save_settings({'profile':'An unrelated resume'})
        edits=[{'before':original,'after':'整理项目文档，协助团队沟通。','reason':'强调文档支持'}]
        with patch('recommendations.ai_json',return_value={'edits':edits}) as ai:
            draft=self.engine.draft(job['key'])
        self.assertEqual(ai.call_args.args[2]['resume'],original)
        self.assertEqual(draft['source_path'],'resumes/base.txt')
        self.assertTrue(draft['source_sha256'])
    def test_network_error_keeps_candidates(self):
        self.add();self.engine.save_settings({'search_enabled':True})
        with patch('recommendations.search_public',side_effect=OSError('offline')):
            result=self.run_daily()
        self.assertEqual(len(result['items']),1)
        self.assertTrue(result['errors'])
    def test_private_and_redirect_urls_blocked(self):
        for url in ('file:///a','http://user:pass@example.org','http://127.0.0.1/a'):
            with self.assertRaises(ValueError): rec.public_url(url)


if __name__=='__main__': unittest.main()
