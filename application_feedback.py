"""Free-form feedback reminders and advice grounded in actual resume/JD/cases."""
import hashlib
from datetime import date, datetime, timezone, timedelta
import career
from hiring_cases import relevant_cases
from opportunity_quality import profile_evidence

FILE='application-feedback.json'
TZ=timezone(timedelta(hours=8))

class Feedback:
    def __init__(self,store,today,assistant):self.store,self.today,self.assistant=store,today,assistant
    def read(self):
        return self.store.read(FILE) if (self.store.root/FILE).exists() else {'items':{},'advice':{}}
    def status(self):
        with self.store.lock:
            state=self.read();apps=self.store.read('投递记录.json')['applications'];due=[]
            for key,a in apps.items():
                logs=state['items'].get(key,[])
                elapsed=(self.today()-date.fromisoformat(a['applied_date'])).days
                if not logs and elapsed>=1: due.append({'key':key,'company':a['company'],'role':a['role'],'reason':'投递后还未填写反馈'})
                elif logs and a.get('progress') in ('等待回复','自动回执') and (self.today()-date.fromisoformat(logs[-1]['date'])).days>=7:
                    due.append({'key':key,'company':a['company'],'role':a['role'],'reason':'距上次反馈已满7天，可以更新近况'})
            return {'due':due,'items':state['items'],'advice':state['advice']}
    def save(self,p):
        value=p.get('text','')
        if not isinstance(value,str) or not value.strip() or len(value)>4000:raise ValueError('请写1—4000字，一句“暂无消息”也可以')
        with self.store.lock:
            if p.get('key') not in self.store.read('投递记录.json')['applications']:raise ValueError('投递记录不存在')
            state=self.read();state['items'].setdefault(p['key'],[]).append({'text':value.strip(),'date':self.today().isoformat(),'at':datetime.now(TZ).isoformat()})
            self.store.write(FILE,state)
        return self.status()
    def analyze(self,key):
        with self.store.lock:
            app=self.store.read('投递记录.json')['applications'].get(key)
            if not app:raise ValueError('投递记录不存在')
            job=app.get('job_snapshot') or next((j for j in self.store.read('岗位库.json')['jobs'] if j['key']==key),None)
            if not job:raise ValueError('缺少岗位JD，请先补充岗位要求')
            path=app.get('resume_used','')
        # No feedback, mood, application notes or response text enters this analysis.
        warnings=[];profile='';resume_hash=''
        try:
            file=self.assistant.resume_file(path)
            profile=self.assistant.extract_resume(path)
            resume_hash=hashlib.sha256(file.read_bytes()).hexdigest()
        except (OSError,ValueError,ImportError):warnings.append('登记的实际投递简历无法读取；请补齐该文件后重新分析。本次不使用其他简历替代。')
        ev=profile_evidence(profile);analysis=career.job_analysis(job,set(ev));cases=relevant_cases(job)
        suggestions=[]
        for skill in analysis['missing'][:4]:
            suggestions.append({'action':'检查实际经历是否包含'+skill+'；有则补一条具体任务、个人贡献和成果，无则先完成可核验练习。',
                                'basis':'原JD：'+analysis['evidence'][skill],'kind':'简历与JD对照'})
        for skill in analysis['matched'][:3]:
            suggestions.append({'action':'面试准备一个'+skill+'实例，说明任务、本人操作、结果与验证方式。',
                                'basis':'简历：'+ev[skill]+'；JD：'+analysis['evidence'][skill],'kind':'简历与JD对照'})
        if not profile:suggestions=[]
        for case in cases:
            if profile and set(case['skills']) & set(analysis['evidence']):
                suggestions.append({'action':case['lesson'],'basis':case['facts'],'url':case['url'],'kind':'相近案例启发，非录用原因'})
        if not cases:warnings.append('未找到经过核查、与此方向相近的录用案例；仅给出简历与JD对照，不补造他人背景。')
        warnings.extend(['公开案例有筛选偏差，不代表全体录用者，也不能推出录用概率或本次无回复的原因。','分析读取当前保存的实际投递简历文件；未保存投递当时文件哈希，无法证实文件此后未被修改。'])
        result={'generated_at':datetime.now(TZ).isoformat(),'resume_path':path,'resume_sha256':resume_hash,
                'resume_available':bool(profile),'matched':analysis['matched'] if profile else [],
                'missing':analysis['missing'] if profile else [],'hard_conditions':analysis['hard_conditions'],
                'suggestions':suggestions,'cases':cases,'warnings':warnings,
                'basis':'实际登记的简历文件 + 投递时JD + 带来源的公开就业案例；自由反馈未参与建议生成。'}
        with self.store.lock:
            state=self.read();state['advice'][key]=result;self.store.write(FILE,state)
        return result
