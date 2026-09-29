"""Follow public recruiting links from already verified publishers."""
from html.parser import HTMLParser
from urllib.parse import urljoin
import re
from opportunity_quality import host, belongs, PLATFORMS

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.rows=[]; self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.current={'url':dict(attrs).get('href',''),'title':''}
    def handle_data(self,text):
        if self.current is not None:self.current['title']+=text
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:self.rows.append(self.current);self.current=None

def recruitment_links(html, source, company, on):
    parser=Links();parser.feed(html);result=[]
    for row in parser.rows:
        url=urljoin(source,row['url']);domain=host(url)
        if not domain or not re.search(r'招聘|投递|网申|申请|职位|岗位|careers?|jobs?',row['title']+' '+url,re.I):continue
        kind='wechat' if belongs(domain,'mp.weixin.qq.com') else 'platform' if any(belongs(domain,d) for d in PLATFORMS) else 'official'
        result.append({'url':url,'title':row['title'],'company':company,'publisher_label':row['title'],'source_proof':{
            'kind':kind,'url':source,'checked_on':on,'basis':'已核对的企业/高校招聘页面直接链接到此入口；目标页还需出现相同公司与具体岗位'}})
    return result[:6]
