"""Transparent source and resume evidence checks, not hiring probabilities."""
import re
from datetime import date
from urllib.parse import urlparse
import career

PLATFORMS = ('zhipin.com', 'liepin.com', '51job.com', 'zhaopin.com', 'nowcoder.com', 'yingjiesheng.com', 'shixiseng.com')
OFFICIAL = {'logicalqubit.com':('逻辑比特','https://logicalqubit.com/job-detail.php?id=86'),
            'iqitek.com':('量智开物','https://www.iqitek.com/#careers'),
            'spinq.com':('量旋','https://www.spinq.com/'), 'spinq.cn':('量旋','https://www.spinq.com/')}

def host(url):
    p=urlparse(str(url or ''))
    return (p.hostname or '').lower() if p.scheme in ('http','https') and not p.username and not p.password else ''

def belongs(domain, suffix): return domain == suffix or domain.endswith('.'+suffix)

def source_info(job):
    domain=host(job.get('source'))
    proof=job.get('source_proof') if isinstance(job.get('source_proof'),dict) else {}
    verified=bool(host(proof.get('url')) and proof.get('basis') and proof.get('checked_on'))
    kind=proof.get('kind','unknown')
    for domain_root,(company,url) in OFFICIAL.items():
        if belongs(domain,domain_root) and company in job.get('company',''):
            return {'kind':'official','label':'企业官方招聘','priority':0,'verified':True,
                    'basis':'已核对企业网站身份（2026-09-29）；不代表岗位仍开放','url':url}
    if domain.endswith('.edu.cn'):
        return {'kind':'university','label':'高校就业网','priority':1,'verified':True,'basis':'高校域名发布；岗位时效与招聘主体另行核对'}
    if belongs(domain,'mp.weixin.qq.com'):
        return {'kind':'wechat','label':'公众号','priority':3,'verified':verified and kind=='wechat',
                'basis':proof.get('basis') if verified else '公众号发布主体尚未交叉核实'}
    if any(belongs(domain,d) for d in PLATFORMS):
        return {'kind':'platform','label':'招聘平台','priority':2,'verified':verified and kind=='platform',
                'basis':proof.get('basis') if verified else '平台域名不等于企业信誉；需要官方招聘渠道或高校公告交叉核实'}
    return {'kind':kind,'label':'企业官方招聘' if kind=='official' else '待核实网站','priority':0 if kind=='official' else 4,
            'verified':bool(domain) and verified and kind=='official','basis':proof.get('basis','尚未核实网站与企业的关系')}

def profile_evidence(profile):
    positive='\n'.join(x for x in str(profile).splitlines() if not re.search(r'不会|未掌握|未接触|不了解|缺乏|计划学习',x))
    return {k:v for k,v in career.evidence(positive).items() if v}

def assess(job, profile, on, resume_ready=False):
    source=source_info(job); ev=profile_evidence(profile)
    a=career.job_analysis(job,set(ev))
    jd='\n'.join(job.get('duties',[])+job.get('requirements',[]))
    facts=jd+' '+str(job.get('eligibility',''))
    blockers=[]; unknown=[]
    if not source['verified']: blockers.append(source['basis'])
    if len(jd.strip())<35 or not job.get('requirements') or not job.get('duties'): blockers.append('缺少具体职责或任职要求')
    if not host(job.get('source')): blockers.append('没有可核对的原始网页')
    try:
        age=(on-date.fromisoformat(job.get('verified_on',''))).days
        if age<0 or age>14: blockers.append('岗位超过14天未核查，需重新确认开放状态')
    except (TypeError,ValueError): blockers.append('缺少最近核查日期')
    if str(job.get('status','')).lower() in ('closed','已关闭','停止招聘','已结束'): blockers.append('岗位已关闭')
    try:
        if date.fromisoformat(str(job.get('deadline',''))[:10])<on: blockers.append('申请截止日期已过')
    except ValueError: pass
    blockers.extend(a['hard_conditions'])
    if not re.search(r'2027|27届',facts) or re.search(r'(2027|27届).{0,12}待确认',facts): unknown.append('2027届资格待确认')
    if '本科' not in facts: unknown.append('本科学历资格待确认')
    if not job.get('online_confirmed'): unknown.append('线上面试待确认')
    quantum='量子' in str(job.get('group',''))+job.get('role','')
    if not quantum and not job.get('salary_min_confirmed'): unknown.append('固定月薪4000元以上待确认')
    if not resume_ready: unknown.append('尚未配好本地简历文件')
    if not a['matched']: unknown.append('探索方向：简历暂未展示对应技能，可先查看项目准备方案')
    ratio=len(a['matched'])/max(1,len(a['evidence']))
    # Missing interview/salary details and skill gaps are visible questions, not rejection.
    # A direct link describes the application channel, not confirmed eligibility.
    ready=bool(a['matched']) and not blockers and resume_ready and bool(job.get('direct')) and job.get('channel')!='email' and bool(host(job.get('apply_url')))
    recommended=not blockers
    return {'source':source,'blockers':blockers,'unknown':unknown,'ready':ready,'recommended':recommended,
            'matched':[{'skill':k,'resume':ev[k],'jd':a['evidence'][k]} for k in a['matched']],
            'missing':a['missing'],'score':len(a['matched'])*10+int(ratio*20),
            'reason':'简历与岗位共同涉及'+ '、'.join(a['matched']) if a['matched'] else '探索推荐：岗位真实，先用项目补充技能证据；当前匹配较低'}

def search_queries(year, focus, region):
    roles=focus.split()
    return [f'{year} 量子计算 校园招聘 本科 {region}',
            *[f'{year} 校园招聘 {role} 官网 {region}' for role in roles],
            f'{year} 校园招聘 {roles[0]} site:edu.cn {region}',
            f'{year} 量子 招聘 site:mp.weixin.qq.com {region}',
            f'{year} 校园招聘 {roles[-1]} site:zhipin.com {region}',
            f'{year} 校园招聘 技术支持 site:liepin.com {region}',
            f'{year} 校园招聘 数据运营 site:51job.com {region}']

def diverse_hits(hits, limit=18):
    """Reserve crawl capacity for each channel; never equate discovery with trust."""
    buckets={k:[] for k in ('official','university','platform','wechat')}
    for hit in hits:
        h=host(hit['url'])
        kind='wechat' if belongs(h,'mp.weixin.qq.com') else 'university' if h.endswith('.edu.cn') else 'platform' if any(belongs(h,d) for d in PLATFORMS) else 'official'
        buckets[kind].append(hit)
    out=[]
    for kind,quota in (('official',9),('university',4),('platform',3),('wechat',2)):
        out.extend(buckets[kind][:quota])
    for hit in hits:
        if len(out)>=limit:break
        if hit not in out:out.append(hit)
    return out[:limit]
