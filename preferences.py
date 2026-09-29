"""Persistent, reversible exclusions and geographic matching."""
import hashlib
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from companies import same_company, company_key

FILE = 'job-preferences.json'
REGIONS = {
    '北京': ['北京'], '上海': ['上海'], '天津': ['天津'], '重庆': ['重庆'],
    '广东': ['广州','深圳','珠海','佛山','东莞','惠州','中山','汕头','江门','湛江','肇庆','清远','韶关','茂名','梅州','汕尾','河源','阳江','潮州','揭阳','云浮'],
    '浙江': ['杭州','宁波','温州','嘉兴','湖州','绍兴','金华','衢州','舟山','台州','丽水'],
    '江苏': ['南京','苏州','无锡','常州','南通','扬州','镇江','徐州','盐城','泰州','淮安','宿迁','连云港'],
    '安徽': ['合肥','芜湖','蚌埠','淮南','马鞍山','淮北','铜陵','安庆','黄山','滁州','阜阳','宿州','六安','亳州','池州','宣城'],
    '福建': ['福州','厦门','泉州','漳州','莆田','三明','南平','龙岩','宁德'],
    '山东': ['济南','青岛','烟台','潍坊','淄博','临沂','济宁','泰安','威海','日照','德州','聊城','滨州','菏泽','枣庄','东营'],
    '四川': ['成都','绵阳','德阳','宜宾','泸州','南充','乐山','自贡','攀枝花','广元','遂宁','内江','眉山','广安','达州','雅安','巴中','资阳','阿坝','甘孜','凉山'],
    '贵州': ['贵阳','遵义','六盘水','安顺','毕节','铜仁','黔东南','黔南','黔西南'],
    '湖北': ['武汉','宜昌','襄阳','黄石','十堰','荆州','荆门','鄂州','孝感','黄冈','咸宁','随州','恩施','仙桃','潜江','天门','神农架'],
    '湖南': ['长沙','株洲','湘潭','衡阳','邵阳','岳阳','常德','张家界','益阳','郴州','永州','怀化','娄底','湘西'],
    '河南': ['郑州','洛阳','开封','平顶山','安阳','鹤壁','新乡','焦作','濮阳','许昌','漯河','三门峡','南阳','商丘','信阳','周口','驻马店','济源'],
    '河北': ['石家庄','保定','唐山','秦皇岛','邯郸','邢台','张家口','承德','沧州','廊坊','衡水','雄安'],
    '陕西': ['西安','咸阳','宝鸡','铜川','渭南','延安','汉中','榆林','安康','商洛'],
    '山西': ['太原','大同','阳泉','长治','晋城','朔州','晋中','运城','忻州','临汾','吕梁'],
    '江西': ['南昌','九江','赣州','景德镇','萍乡','新余','鹰潭','吉安','宜春','抚州','上饶'],
    '辽宁': ['沈阳','大连','鞍山','抚顺','本溪','丹东','锦州','营口','阜新','辽阳','盘锦','铁岭','朝阳','葫芦岛'],
    '吉林': ['长春','吉林','四平','辽源','通化','白山','松原','白城','延边'],
    '黑龙江': ['哈尔滨','齐齐哈尔','牡丹江','佳木斯','大庆','鸡西','鹤岗','双鸭山','伊春','七台河','黑河','绥化','大兴安岭'],
    '广西': ['南宁','柳州','桂林','梧州','北海','防城港','钦州','贵港','玉林','百色','贺州','河池','来宾','崇左'],
    '云南': ['昆明','曲靖','玉溪','保山','昭通','丽江','普洱','临沧','楚雄','红河','文山','西双版纳','大理','德宏','怒江','迪庆'],
    '海南': ['海口','三亚','三沙','儋州'], '内蒙古': ['呼和浩特','包头','乌海','赤峰','通辽','鄂尔多斯','呼伦贝尔','巴彦淖尔','乌兰察布','兴安盟','锡林郭勒','阿拉善'],
    '甘肃': ['兰州','嘉峪关','金昌','白银','天水','武威','张掖','平凉','酒泉','庆阳','定西','陇南','临夏','甘南'],
    '宁夏': ['银川','石嘴山','吴忠','固原','中卫'], '青海': ['西宁','海东','海北','黄南','海南州','果洛','玉树','海西'],
    '新疆': ['乌鲁木齐','克拉玛依','吐鲁番','哈密','昌吉','博尔塔拉','巴音郭楞','阿克苏','克孜勒苏','喀什','和田','伊犁','塔城','阿勒泰','石河子'],
    '西藏': ['拉萨','日喀则','昌都','林芝','山南','那曲','阿里'], '香港': ['香港'], '澳门': ['澳门'], '台湾': ['台北','新北','台中','台南','高雄','新竹']}
BOARDS = {'nowcoder.com':'牛客', 'zhipin.com':'BOSS直聘', 'zhaopin.com':'智联招聘', '51job.com':'前程无忧', 'liepin.com':'猎聘', 'shixiseng.com':'实习僧'}

def host(url):
    return (urlparse(str(url or '')).hostname or '').lower().removeprefix('www.')

def platform(job):
    domain = host(job.get('apply_url') or job.get('source') or job.get('entry'))
    for root, name in BOARDS.items():
        if domain == root or domain.endswith('.' + root): return root, name
    return domain, job.get('platform') or domain

def region_matches(job, prefs):
    province, city = prefs.get('province',''), prefs.get('city','')
    if not province and not city: return True
    place = str(job.get('place') or '')
    if not place or any(x in place for x in ('待确认','未公布','未知')):
        return prefs.get('include_unknown', True)
    if '全国' in place or '城市不限' in place: return True
    if city: return city in place
    return province in place or any(c in place for c in REGIONS.get(province, []))

class Preferences:
    def __init__(self, store, same_job): self.store, self.same_job = store, same_job
    def read(self):
        with self.store.lock:
            return self.store.read(FILE) if (self.store.root/FILE).exists() else {'province':'','city':'','include_unknown':True,'rules':[]}
    def excluded(self, job, prefs=None):
        p = prefs if prefs is not None else self.read()
        for rule in p['rules']:
            if not rule.get('active', True): continue
            if rule['kind']=='job' and self.same_job(job,rule['job']): return True
            if rule['kind']=='company' and same_company(job,rule['job']):return True
            if rule['kind']=='platform' and platform(job)[0]==rule['value']: return True
            if rule['kind']=='role' and rule['value'].casefold() in str(job.get('role','')).casefold(): return True
        return False
    def allowed(self, job, prefs=None):
        p = prefs if prefs is not None else self.read()
        return not self.excluded(job,p) and region_matches(job,p)
    def change(self, data):
        with self.store.lock:
            p = self.read(); op=data.get('op')
            if op=='region':
                province, city = data.get('province',''),data.get('city','')
                if province and province not in REGIONS: raise ValueError('请选择有效省份')
                if not isinstance(city,str) or len(city)>30 or (city and not re.fullmatch(r'[\u4e00-\u9fffA-Za-z ·-]+',city)): raise ValueError('城市格式不正确')
                if not isinstance(data.get('include_unknown',True),bool): raise ValueError('地点未知开关格式错误')
                p.update(province=province,city=city,include_unknown=data.get('include_unknown',True))
            elif op=='restore':
                rule=next((r for r in p['rules'] if r['id']==data.get('id')),None)
                if rule is None: raise ValueError('规则不存在')
                rule['active']=False
            elif op=='exclude':
                kind=data.get('kind'); job=next((j for j in self.store.read('岗位库.json')['jobs'] if j['key']==data.get('key')),None)
                if kind not in ('job','platform','role','company'): raise ValueError('请选择公司、岗位、平台或岗位关键词')
                if kind!='role' and job is None: raise ValueError('岗位不存在')
                value = company_key(job['company']) if kind=='company' else job['key'] if kind=='job' else platform(job)[0] if kind=='platform' else str(data.get('value','')).strip()[:80]
                if not value: raise ValueError('缺少可记录的内容')
                rid=hashlib.sha256((kind+'|'+value.casefold()).encode()).hexdigest()[:20]
                rule={'id':rid,'kind':kind,'value':value,'active':True,'reason':str(data.get('reason',''))[:500], 'at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
                      'label':job['company'] if kind=='company' else job['company']+' · '+job['role'] if kind=='job' else platform(job)[1] if kind=='platform' else value}
                if kind in ('job','company'): rule['job']={k:job.get(k) for k in ('key','aliases','company','role','canonical_company','company_aliases')}
                p['rules']=[r for r in p['rules'] if r['id']!=rid]+[rule]
            else: raise ValueError('未知偏好操作')
            self.store.write(FILE,p)
            return p
