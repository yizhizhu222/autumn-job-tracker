"""Conservative company identity, shared by queues and company cards."""
import re
import unicodedata

def company_key(name):
    value=unicodedata.normalize('NFKC',str(name or '')).casefold()
    value=re.sub(r'\s+','',value)
    return re.sub(r'(股份有限公司|有限责任公司|有限公司)$','',value)

def company_ids(job):
    return {company_key(n) for n in [job.get('company',''),job.get('canonical_company',''),*(job.get('company_aliases') or [])] if n}

def same_company(a,b):
    return bool(company_ids(a)&company_ids(b))

def channel(job):
    return 'email' if job.get('channel')=='email' else 'web' if job.get('direct') else 'unverified'

def group_companies(jobs):
    groups=[]
    for job in jobs:
        group=next((g for g in groups if any(same_company(job,old) for old in g['jobs'])),None)
        if group is None:
            group={'key':company_key(job['company']),'company':job['company'],'jobs':[]};groups.append(group)
        group['jobs'].append(job)
    return groups
