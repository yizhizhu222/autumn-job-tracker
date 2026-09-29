"""Bounded, polite public-page fetching. No login, CAPTCHA bypass or cookies."""
import codecs
import re
import threading
import time
from collections import OrderedDict
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener

MAX_BYTES=1_500_000

def decode_page(raw, charset=None):
    if not charset:
        match=re.search(br'charset\s*=\s*[\"\']?\s*([\w-]+)',raw[:4096],re.I)
        if match:charset=match.group(1).decode('ascii')
    encodings=[charset,'utf-8-sig','gb18030']
    for encoding in encodings:
        if not encoding:continue
        try:
            codecs.lookup(encoding)
            return raw.decode(encoding)
        except (LookupError,UnicodeError):pass
    raise ValueError('网页文字编码无法识别，已保留来源等待核查')

class Fetcher:
    def __init__(self):
        self.cache=OrderedDict();self.next_request={};self.lock=threading.RLock()
    def fetch(self,url,validate,redirect):
        p=urlsplit(url);url=urlunsplit((p.scheme,p.netloc,p.path,p.query,''))
        domain=p.hostname
        with self.lock:
            now=time.monotonic();cached=self.cache.get(url)
            if cached and now-cached[0]<900:return cached[1]
            wait=self.next_request.get(domain,0)-now
            if wait>2:raise ValueError('网站要求稍后重试，本轮暂停访问该来源')
            if wait>0:time.sleep(wait)
            self.next_request[domain]=time.monotonic()+0.7
        validate(url)
        request=Request(url,headers={'User-Agent':'AutumnJobTracker/1.7 (+https://github.com/yizhizhu222/autumn-job-tracker)',
                                     'Accept':'text/html,application/xhtml+xml,application/xml,text/xml;q=0.9', 'Accept-Encoding':'identity'})
        try:
            with build_opener(redirect()).open(request,timeout=12) as response:
                validate(response.geturl())
                kind=response.headers.get_content_type()
                if kind not in ('text/html','application/xhtml+xml','text/plain','text/xml','application/xml','application/rss+xml'):
                    raise ValueError('该链接不是可读取的招聘文本网页')
                raw=response.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:raise ValueError('页面过大，已停止读取')
                page=decode_page(raw,response.headers.get_content_charset())
        except HTTPError as error:
            if error.code in (401,403):raise ValueError('来源需要登录或限制访问，未绕过限制') from None
            if error.code in (429,503):
                retry=error.headers.get('Retry-After','60')
                seconds=min(900,max(30,int(retry))) if retry.isdigit() else 60
                with self.lock:self.next_request[domain]=time.monotonic()+seconds
                raise ValueError('来源限流或暂不可用，已延后重试') from None
            raise
        if re.search(r'<title>[^<]*(验证码|安全验证|人机验证|access denied)',page,re.I):
            raise ValueError('来源要求人工验证，未绕过验证')
        with self.lock:
            self.cache[url]=(time.monotonic(),page);self.cache.move_to_end(url)
            while len(self.cache)>32:self.cache.popitem(last=False)
        return page
