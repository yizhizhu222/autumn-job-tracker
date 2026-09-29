import base64
import copy
from email.message import Message
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import app
from crawler import decode_page,Fetcher,MAX_BYTES
from data_lock import DataLock
import recommendations

class Response(io.BytesIO):
    def __init__(self,raw,kind='text/html'):
        super().__init__(raw);self.headers=Message();self.headers['Content-Type']=kind
    def geturl(self):return 'https://example.org/job'

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=app.Store(self.temp.name)
        self.engine=recommendations.Assistant(self.store,app.today,app.same_job)
    def tearDown(self):self.temp.cleanup()
    def upload(self,raw,name='resume.txt'):
        return self.engine.upload_resume({'name':name,'data':base64.b64encode(raw).decode()})
    def test_upload_is_private_deduplicated_and_does_not_touch_ledger(self):
        before=self.store.read(app.LEDGER);raw='本科2027届，使用SQL、Excel完成数据分析项目。'.encode()
        first=self.upload(raw);second=self.upload(raw,'renamed.txt')
        self.assertEqual(first['path'],second['path']);self.assertEqual((self.store.root/first['path']).read_bytes(),raw)
        self.assertEqual(len(self.store.read(app.CATALOG)['originals']),1)
        self.assertEqual(self.engine.settings()['profile'],raw.decode())
        self.assertEqual(self.store.read(app.LEDGER),before)
        for name in ('x.exe','x.docx','fake.pdf'):
            with self.assertRaises(ValueError):self.upload(raw,name)
        with self.assertRaises(ValueError):self.upload(b'x'*5_000_001)
    def test_pdf_upload_validates_bytes_and_preserves_original(self):
        import pypdf
        out=io.BytesIO();writer=pypdf.PdfWriter();writer.add_blank_page(600,800);writer.write(out)
        result=self.upload(out.getvalue(),'actual.pdf')
        self.assertEqual((self.store.root/result['path']).read_bytes(),out.getvalue())
        self.assertEqual(result['text_length'],0)
        self.assertIn('未识别',result['message'])
    def test_data_lock_blocks_another_process_and_releases(self):
        lock=DataLock(self.store.root)
        command=[sys.executable,'-c','from data_lock import DataLock; import sys; DataLock(sys.argv[1])',str(self.store.root)]
        try:self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
        finally:lock.close()
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
    def test_new_user_first_crawled_job_gets_uploaded_resume(self):
        resume=self.upload('2027届本科，SQL、Excel数据分析和可视化项目。'.encode())
        self.engine.save_settings({'enabled':False,'search_enabled':True})
        job={'company':'新公司','role':'数据分析','group':'数据','place':'上海','online':'视频面试','salary':'固定月薪5-8K',
             'evidence':'新公司数据分析招聘，面向2027届本科毕业生，提供专业培养。',
             'requirements':['2027届本科，掌握SQL、Excel和数据分析。'],
             'duties':['清洗业务数据并完成可视化报表，核对指标口径和质量，汇报分析结果。']}
        body='\n'.join([v for v in job.values() if isinstance(v,str)]+job['requirements']+job['duties']+['立即投递'])
        with patch('recommendations.search_public',return_value=[{'url':'https://career.example.edu.cn/jobs/1','title':'招聘'}]),patch('recommendations.fetch_public',return_value=body),patch.object(self.engine,'model_status',return_value={'available':True}),patch('recommendations.ai_json',side_effect=lambda m,t,d:{'job':job} if t.startswith('从网页') else {'items':[]}):
            self.engine.busy.acquire();self.engine.run()
        saved=self.store.read(app.CATALOG)['jobs'][0]
        self.assertEqual(saved['resume']['path'],resume['path'])
        self.assertTrue(self.engine.daily_view()['items'][0]['quality']['ready'])
    def test_bad_pdf_becomes_readable_validation_error(self):
        folder=self.store.root/'resumes';folder.mkdir();(folder/'bad.pdf').write_bytes(b'%PDF-invalid')
        with self.assertRaises(ValueError):self.engine.extract_resume('resumes/bad.pdf')

class CrawlTests(unittest.TestCase):
    def test_charset_from_meta_and_gb18030_fallback(self):
        text='<meta charset="gb2312">招聘岗位，本科应届生'
        self.assertEqual(decode_page(text.encode('gb2312')),text)
        self.assertEqual(decode_page('招聘'.encode('gb18030')),'招聘')
        self.assertEqual(decode_page('招聘'.encode('utf-8'),'bad-codec'),'招聘')
    def test_cache_avoids_duplicate_requests(self):
        fetcher=Fetcher()
        with patch('crawler.build_opener') as opener:
            opener.return_value.open.return_value=Response(b'<html>jobs</html>')
            first=fetcher.fetch('https://example.org/job',lambda u:None,object)
            second=fetcher.fetch('https://example.org/job#anchor',lambda u:None,object)
            self.assertEqual(first,second);self.assertEqual(opener.return_value.open.call_count,1)
    def test_cooldown_does_not_hammer_rate_limited_origin(self):
        fetcher=Fetcher();headers=Message();headers['Retry-After']='60'
        with patch('crawler.build_opener') as opener:
            opener.return_value.open.side_effect=HTTPError('https://example.org/job',429,'rate limit',headers,None)
            for _ in range(2):
                with self.assertRaises(ValueError):fetcher.fetch('https://example.org/job',lambda u:None,object)
            self.assertEqual(opener.return_value.open.call_count,1)
    def test_nontext_and_oversize_are_rejected(self):
        for raw,kind in ((b'binary','application/pdf'),(b'x'*(MAX_BYTES+1),'text/html')):
            with patch('crawler.build_opener') as opener:
                opener.return_value.open.return_value=Response(raw,kind)
                with self.assertRaises(ValueError):Fetcher().fetch('https://example.org/job',lambda u:None,object)

if __name__=='__main__':unittest.main()
