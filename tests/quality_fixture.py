from unittest.mock import patch

def mock_quality(test):
    """Identity/region unit tests isolate eligibility; quality is tested separately."""
    p=patch('recommendations.assess',return_value={'ready':True,'recommended':True,'source':{'priority':0},'score':50})
    p.start();test.addCleanup(p.stop)

def qualify(store,engine,job,on):
    folder=store.root/'resumes';folder.mkdir(exist_ok=True)
    (folder/'test.txt').write_text('使用SQL、Excel完成数据分析与可视化报表项目。',encoding='utf-8')
    catalog=store.read('岗位库.json')
    for j in catalog['jobs']:
        if j['key']!=job['key']:continue
        j.update(requirements=['2027届本科毕业生，要求SQL、Excel及数据分析能力。'],
                 duties=['分析业务数据，核对指标口径并交付可复现的可视化报表与数据质量记录。'],
                 source_proof={'kind':'official','url':'https://example.org/about','basis':'测试用已核查企业页面','checked_on':on.isoformat()},
                 online_confirmed=True,salary_min_confirmed=True,verified_on=on.isoformat(),resume={'path':'resumes/test.txt'})
        job=dict(j)
    store.write('岗位库.json',catalog);engine.save_settings({'profile':'使用SQL、Excel完成数据分析与可视化报表项目。'})
    return job
