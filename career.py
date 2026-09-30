"""Evidence-linked career planning. Planned skills are never resume facts."""
import copy
import hashlib
import re
from datetime import datetime

FILE = 'career-plan.json'
SKILLS = {
 'SQL':['sql','数据库查询','数据库'], 'Excel':['excel','透视表','电子表格'],
 'Python':['python'], '数据分析':['数据分析','统计分析','数据挖掘'],
 '可视化':['可视化','power bi','tableau','报表'], '测试':['测试','质量保证','qa'],
 'API':['api','接口','fastapi'], '部署':['docker','linux','部署','运维'],
 '文档':['文档','技术写作','知识库'], '沟通':['沟通','宣讲','讲解','解说','培训','客户支持'],
 '项目管理':['项目管理','进度管理','项目协调'], '量子':['量子','qiskit','qft','shor'],
 '嵌入式':['嵌入式','stm32','单片机','固件'], '机器学习':['机器学习','pytorch','深度学习','建模']}

PROJECTS = [
 {'id':'data','title':'真实业务数据分析与决策报告','majors':['数据','统计','数学','计算机','经济','管理','金融','商'],
  'skills':['SQL','Excel','数据分析','可视化','文档'], 'roles':['数据分析','数据运营','业务分析','运营助理'], 'duration':'3—4周，每周8—10小时，可用SQL与表格工具完成',
  'problem':'用可合法公开的订单或公共服务数据回答一个具体业务问题，例如哪些环节导致转化下降。',
  'data':'选择有许可说明的公开数据，保留来源、字段字典和采集日期；自造数据必须标注模拟，不能写成真实公司业务。',
  'steps':['第1周：定义业务问题、5个指标及口径，检查缺失、重复、异常值，保留清洗记录。','第2周：写可复用SQL，做分组、漏斗或留存分析，核对表格与SQL结果。','第3周：制作交互报表，给出有数据依据的建议、反例和局限。','第4周：让同学按说明复现，修正问题并完成5分钟讲解。'],
  'deliverables':['有来源的数据说明与数据字典','清洗流程、SQL及质量检查记录','可交互报表、业务结论报告、复现说明'],
  'acceptance':['至少3张关联表或明确解释单表分析边界；数据量与结论相称。','至少5个指标有定义、SQL和手工抽样核对；记录异常及处理依据。','至少3个结论有图表与反例检查，区分相关关系和因果关系。','他人在干净环境按README可以复现相同结果。']},
 {'id':'support','title':'软件部署交付与故障排查知识库','majors':['计算机','软件','信息','数据','电子','通信','管理'],
  'skills':['部署','API','文档','沟通','项目管理'], 'roles':['实施顾问','技术支持','客户成功','售前助理','项目助理'], 'duration':'2—3周，每周8—10小时，少量脚本',
  'problem':'为一个实际开源应用或自己的已有项目完成交付，模拟用户从安装到故障恢复的完整过程。',
  'data':'使用可本地运行的开源应用、公开接口文档及自己实际产生的脱敏日志；记录版本及许可。',
  'steps':['整理用户需求、部署清单、验收标准和交付时间表。','部署应用，编写操作手册和接口验证步骤。','主动制造端口冲突、配置错误、权限不足、数据丢失等故障，记录定位与恢复过程。','请2名未参与开发的人试用，记录反馈、修改手册并录制产品演示。'],
  'deliverables':['部署和回滚说明、环境检查清单','至少8个真实复现的故障案例与排查树','用户手册、FAQ、交付验收单和演示视频'],
  'acceptance':['新用户按文档完成安装和一个核心任务；保存试用反馈。','每个故障有复现步骤、日志证据、根因和修复验证。','演示一次备份恢复并核对恢复后的数据。','解释需求变更如何影响交付时间，不能只提交截图。']},
 {'id':'quality','title':'端到端测试与质量改进报告','majors':['计算机','软件','数据','信息','电子','工业'],
  'skills':['测试','API','SQL','文档','项目管理'], 'roles':['软件测试','质量专员','测试助理','产品助理'], 'duration':'2—3周，每周8—10小时，可优先手工测试与接口工具',
  'problem':'对一个实际应用的登录、数据录入、查询、导出等流程制定测试计划，并跟踪问题直到验证修复。',
  'data':'选择本地开源应用或本人项目，只测试授权环境；用模拟测试账号和无个人信息的数据。',
  'steps':['梳理需求及风险，建立需求到用例的追踪表。','设计正常、边界、异常和权限用例，实际执行并留证。','复现缺陷，按影响排序，与修复版本进行回归对比。','输出质量报告，说明覆盖不到的场景及发布建议。'],
  'deliverables':['测试计划、需求覆盖表和至少30条实际执行用例','接口测试集合、缺陷单、回归记录','质量报告与可复现演示'],
  'acceptance':['覆盖至少3个业务流程，并含边界、异常与权限场景。','每条缺陷写明版本、步骤、预期、实际与证据；不编造缺陷数量。','在两个版本或修复前后完成回归，解释未解决风险。','其他人能够导入用例或按步骤复测。']},
 {'id':'quantum','title':'量子计算教学实验与可复现实验报告','majors':['物理','数学','数据','计算机','电子'],
  'skills':['量子','Python','测试','可视化','文档','沟通'], 'roles':['量子软件支持','量子教育培训','量子技术应用助理'], 'duration':'4—6周，每周8—10小时，有编程与数学要求',
  'problem':'围绕一个明确算法或小规模问题，比较经典方法与量子模拟结果，为非专业用户制作教学实验。',
  'data':'使用本地量子模拟器和公开教程，记录版本、随机种子、输入和电路；模拟器结果不能写成真机实验。',
  'steps':['补齐线性代数、测量和基础量子门，写出实验假设。','实现Bell态及一个小规模算法，保留经典基线。','比较不同电路深度、采样次数及噪声下结果，报告计算资源与局限。','制作可运行实验讲义、排错指南，邀请同学试学并记录反馈。'],
  'deliverables':['可重复运行的实验代码和环境说明','经典基线与量子模拟的对比报告','教学讲义、演示视频和试学反馈'],
  'acceptance':['至少3组参数对比，有种子、重复运行和误差分析。','区分模拟器与量子硬件，不宣称未经证明的量子优势。','讲清楚算法适用条件、复杂度与本实验限制。','完成一次他人复现实验；项目不替代研究岗位的硕博门槛。']},
 {'id':'embedded','title':'传感数据采集、测试与设备使用手册','majors':['电子','自动化','通信','嵌入式','物联网'],
  'skills':['嵌入式','测试','Python','文档','可视化'], 'roles':['嵌入式测试','硬件技术支持','设备应用工程师'], 'duration':'4—5周，每周8—10小时，需要开发板或明确标注的模拟环境',
  'problem':'把一项传感数据采集任务做成可长时间运行、可排错、可交付的演示系统。',
  'data':'使用本人设备采样数据，记录型号、接线及实验环境；模拟数据单独标注。',
  'steps':['确定采样频率、精度和异常处理指标。','完成采集、存储和显示，并保留接口与接线说明。','测试断连、异常读数、重启和连续运行，记录问题。','编写操作与故障手册，让他人复现并验收。'],
  'deliverables':['代码、接线图与环境说明','采集样本、长期运行日志与测试报告','用户手册、问题清单和演示'],
  'acceptance':['有至少一次连续运行测试，明确时长、丢样率和异常。','异常断连后恢复且不破坏已存数据。','每个指标有测量方法、结果和限制。','其他人根据文档能够复现采集和排查故障。']}
]

def evidence(text):
    lines=[x.strip() for x in str(text).splitlines() if x.strip()]
    return {skill:next((line[:240] for line in lines if any(re.search(r'(?<![a-z])'+re.escape(w)+r'(?![a-z])',line,re.I) if w.isascii() else w in line for w in words)), '') for skill,words in SKILLS.items()}

def job_analysis(job, known, projected=()):
    jd='\n'.join(job.get('requirements',[])+job.get('duties',[]))
    needed={k:v for k,v in evidence(jd).items() if v}
    present=[k for k in needed if k in known]; missing=[k for k in needed if k not in known]
    gained=[k for k in missing if k in projected]
    facts=' '.join(job.get('requirements',[]))+str(job.get('eligibility',''))
    hard=[]
    if re.search(r'(硕士|博士|研究生).{0,6}(以上|学历|学位|起|及)',facts): hard.append('原JD可能存在硕博学历门槛，项目不能替代；请核对原文')
    if re.search(r'[2-9二三五十].{0,2}年.{0,4}(经验|工作)',facts): hard.append('原JD可能要求工作年限，个人项目不能替代')
    return {'key':job['key'],'company':job['company'],'role':job['role'],'place':job.get('place','待确认'),
            'url':job.get('apply_url') or job.get('source',''),'direct':bool(job.get('direct')),'channel':job.get('channel'),
            'matched':present,'missing':missing,'gained':gained,'evidence':needed,'hard_conditions':hard,
            'unknown':['学历/专业、2027届资格、线上面试、薪资和是否仍开放均以最新JD或招聘方回复为准'],
            'basis':'根据JD技能关键词与简历原文交叉核对；提及技能不等于熟练，也不是录用概率'}

ROLE_FAMILIES={
 'data':r'数据分析|数据运营|业务分析|经营分析|商业分析|统计|产品运营|增长运营',
 'support':r'支持|实施|交付|顾问|售前|客户成功|项目管理|应用工程|技术培训',
 'quality':r'测试|质量|QA|产品助理',
 'quantum':r'量子|quantum',
 'embedded':r'嵌入式|固件|设备|硬件|单片机'}
RESUME_OUTLINES={
 'data':['基于【真实数据来源】整理【实际数据规模】数据，使用【实际工具】完成清洗、去重和异常检查，保留数据字典与质量报告。','围绕【业务问题】定义【实际指标】，编写可复用查询并制作【实际报表】，通过【抽样核验方式】核对结果。','发现【有证据的结论】，给出【具体建议】及适用限制；报告与复现说明见【成果位置】。'],
 'support':['为【实际应用】完成【本人负责的部署与配置】，交付环境检查、操作和回滚说明。','复现并定位【实际故障类型/数量】，以日志验证根因，编写【排查手册/知识库】并进行恢复验证。','组织【真实试用对象】按文档完成【核心任务】，根据【实际反馈】改进交付流程，保留验收记录。'],
 'quality':['针对【实际应用/版本】的【业务流程】制定测试计划，设计并执行【实际用例数】条正常、边界与异常用例。','复现【实际发现的问题】，记录版本、步骤与证据；对【修复版本】执行回归并说明剩余风险。','交付需求覆盖表、接口测试集合与质量报告，结果见【成果位置】；不编造缺陷或改善比例。'],
 'quantum':['基于【本地模拟器及版本】实现【实际算法/电路】，对照【经典基线】完成可重复实验。','比较【实际参数与实验次数】下的结果，报告误差、资源消耗及限制，明确结果来自模拟器。','制作【实验讲义/排错指南】，记录【实际复现或试学反馈】，成果见【代码与报告位置】。'],
 'embedded':['基于【真实设备或模拟环境】完成【数据采集任务】，实现【本人负责的采集/存储/显示部分】。','执行【真实时长】的运行与断连恢复测试，记录【实测丢样率/异常情况】及处理依据。','交付【接线图、测试报告与用户手册】，由【实际复现对象】按步骤验收，说明环境限制。']}

def build_plan(major, profile, jobs):
    ev={k:v for k,v in evidence(profile).items() if v};known=set(ev)
    analyses=[job_analysis(j,known) for j in jobs]
    analyses.sort(key=lambda x:(bool(x['hard_conditions']),-len(x['matched']),len(x['missing'])))
    projects=[];rejected=0
    for template in PROJECTS:
        p=copy.deepcopy(template);linked=[]
        for job in jobs:
            jd='\n'.join(job.get('requirements',[])+job.get('duties',[]))
            scope=str(job.get('role',''))+(' '+str(job.get('group','')) if p['id']=='quantum' else '')
            if len(jd.strip())<16 or not str(job.get('source') or job.get('apply_url','')).startswith(('https://','http://')):continue
            if not re.search(ROLE_FAMILIES[p['id']],scope,re.I):continue
            a=job_analysis(job,known,p['skills'])
            matched_skills=set(a['evidence'])&set(p['skills'])
            # Generic communication/document mentions alone cannot justify a project.
            if len(matched_skills)<2 or not matched_skills-{'沟通','文档','项目管理'}:continue
            if a['hard_conditions']:rejected+=1;continue
            a['reinforced']=[k for k in matched_skills if k in known]
            a['project_skill_evidence']={k:a['evidence'][k] for k in matched_skills}
            linked.append(a)
        if not linked:continue
        linked.sort(key=lambda x:(-len(x['gained']),len(x['missing'])))
        relevant=any(m in major for m in p['majors'])
        companies=len({j['company'] for j in linked})
        missing=set().union(*(set(j['gained']) for j in linked))
        strengthened=set().union(*(set(j['reinforced']) for j in linked))
        targets=missing or strengthened
        p.update(covered_jobs=len(linked),covered_companies=companies,sample_size=len(jobs),jobs_after=linked[:8],
            direction=' / '.join(p['roles'][:2]),target_gap='、'.join(sorted(targets)),
            evidence_level='岗位需求支持',
            selection_reason=f'目标方向有{len(linked)}条具体JD、{companies}家公司；'+('补充尚未展示的' if missing else '把已有技能变成可复现成果，强化')+ '、'.join(sorted(targets))+'证据。',
            score=companies*10+len(linked)*3+len(missing)+(2 if relevant else 0)+(3 if p['id'] in ('support','quality','data') else 0),
            status='planned',completion_evidence='',resume_outline=RESUME_OUTLINES[p['id']],
            resume_heading=p['title']+'｜个人项目｜【实际起止时间】',
            next_step='先对照下方JD确认目标方向，完成交付物与验收后，在原简历项目经历中加入或替换一项，控制在3条以内。',
            demand_map=[{'skill':skill,'jobs':sum(skill in j['project_skill_evidence'] for j in linked),'evidence':next(j['project_skill_evidence'][skill] for j in linked if skill in j['project_skill_evidence'])} for skill in sorted(targets)])
        projects.append(p)
    projects.sort(key=lambda p:-p['score'])
    # A temporarily empty daily feed must not erase a useful learning plan.
    # Keep professional preparation explicitly separate from measured job coverage.
    for template in PROJECTS:
        if len(projects)>=3:break
        if any(p['id']==template['id'] for p in projects):continue
        if not any(m in major for m in template['majors']):continue
        p=copy.deepcopy(template)
        p.update(covered_jobs=0,covered_companies=0,sample_size=len(jobs),jobs_after=[],
            direction=' / '.join(p['roles'][:2]),target_gap='、'.join(p['skills']),score=0,
            evidence_level='专业准备方案 · 等待岗位验证',
            selection_reason='按专业提供可执行的准备方案，目前没有足够可用JD计算覆盖数量。先完成第一周的小样本验证，补齐岗位需求后再决定是否投入完整项目。',
            status='planned',completion_evidence='',resume_outline=RESUME_OUTLINES[p['id']],
            resume_heading=p['title']+'｜个人项目｜【实际起止时间】',demand_map=[],
            next_step='可从现有课程或个人项目继续完善。先交付小样本与复现说明；只有完成验收的成果才能写进简历，项目不替代学历和经验要求。')
        projects.append(p)
    return {'schema':3,'major':major,'generated_at':datetime.now().isoformat(),'profile_hash':hashlib.sha256(profile.encode()).hexdigest(),
      'summary':'先选择有真实需求、硬条件可争取的方向，再做能补齐证据的项目。',
      'evidence':ev,'warnings':['未提及的技能视为缺少简历证据，不断言你不会。','项目优先级依据当前JD数量、技能缺口与硬条件；没有录用结果数据，不能计算上岸率。','模板中的【占位内容】必须用实际成果替换，未完成的项目不能写成经历。'],
      'current_jobs':analyses[:12],'sample_size':len(jobs),'projects':projects[:3],
      'project_message':'' if projects else '请填写具体专业，系统会据此准备项目步骤，并在收集到岗位后补充需求依据。',
      'ai':None,'ai_status':'基础分析已完成，未调用模型'}
