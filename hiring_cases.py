"""Small, curated public evidence set. No claims about why a person was hired."""
CASES = [
 {'id':'zhku-data-2024','title':'仲恺农业工程学院：统计学本科毕业生就业访谈',
  'url':'https://jskx.zhku.edu.cn/info/1130/4972.htm','published':'2024-07-18','checked_on':'2026-09-29',
  'company':'广州拓尔思大数据有限公司','role':'数据开发工程师','family':'data',
  'facts':'高校记录了一位统计学本科毕业生进入数据开发岗位；访谈提及数据运营实习、业务指标梳理和可视化报表实践。',
  'skills':['SQL','Python','数据分析','可视化'],
  'lesson':'准备一个可演示的业务分析成果，讲清数据来源、指标定义、工具和核验方式。',
  'limits':'2024年的单个公开案例；数据开发不等于数据运营。未公开完整简历、筛选过程或录用原因，不能据此计算上岸率。'},
 {'id':'yangtze-quantum-2026','title':'长江大学：2026届本科毕业生就业分享',
  'url':'https://psat.yangtzeu.edu.cn/info/1033/2431.htm','published':'2026-05-28','checked_on':'2026-09-29',
  'company':'本源量子计算科技（合肥）股份有限公司','role':'未公开具体岗位','family':'quantum',
  'facts':'高校确认一位2026届量子信息专业本科毕业生签约本源量子；分享中强调专业实践和科创经历。',
  'skills':['量子'],
  'lesson':'将真实量子实践整理为可运行演示、实验记录和个人贡献说明，再逐项对照目标JD。',
  'limits':'只证实行业签约与一般实践建议；没有具体岗位、完整简历、面试分数或录用原因，不能当作同岗位录用标准。'}]

def relevant_cases(job):
    import re
    text=job.get('role','')+' '+str(job.get('group',''))
    family='quantum' if '量子' in text else 'data' if re.search(r'数据|分析|统计|商业智能',text) else ''
    return [dict(c,comparison='同公司公开案例' if c['company']==job.get('company') else '相近方向公开案例，非该岗位录用样本') for c in CASES if c['family']==family]
