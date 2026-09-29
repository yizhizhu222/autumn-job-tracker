"""Read-only IMAP headers; authorization codes stay in process memory only."""
import email
from email.header import decode_header, make_header
from email.utils import getaddresses
import hashlib
import imaplib
import re
import ssl
import threading
from datetime import datetime, timezone, timedelta

FILE='mail-checks.json'
PROVIDERS={'gmail':('imap.gmail.com',('gmail.com','googlemail.com')),'qq':('imap.qq.com',('qq.com','foxmail.com'))}

def address(value, optional=False):
    value=str(value or '').strip().lower()
    if optional and not value:return ''
    if len(value)>254 or not re.fullmatch(r'[a-z0-9.!#$%&*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}',value):raise ValueError('请填写有效邮箱地址')
    return value

def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat()

class MailChecks:
    def __init__(self,store):self.store=store;self.credentials={};self.lock=threading.RLock()
    def saved(self):
        with self.store.lock:return self.store.read(FILE) if (self.store.root/FILE).exists() else {'checks':{}}
    def status(self):
        with self.lock: accounts=list(self.credentials)
        return {'connected':accounts,'checks':self.saved()['checks'],'credential_storage':'授权码只保留到本次程序关闭'}
    def login(self,account):
        with self.lock:credential=self.credentials.get(account)
        if not credential:raise ValueError('此邮箱未连接，请先在邮箱检查中填写授权码')
        provider,secret=credential
        client=imaplib.IMAP4_SSL(PROVIDERS[provider][0],993,ssl_context=ssl.create_default_context(),timeout=15)
        try:client.login(account,secret)
        except Exception:
            try:client.logout()
            except Exception:pass
            raise
        return client
    def connect(self,data):
        account=address(data.get('address'));provider=data.get('provider');secret=data.get('secret','')
        if provider not in PROVIDERS or account.split('@')[1] not in PROVIDERS[provider][1]:raise ValueError('邮箱与服务商不匹配，目前支持Gmail及QQ/foxmail')
        if not isinstance(secret,str) or not 8<=len(secret)<=256:raise ValueError('请填写邮箱服务商提供的应用密码或授权码')
        with self.lock:self.credentials[account]=(provider,secret)
        try:
            client=self.login(account);client.logout()
        except (OSError,imaplib.IMAP4.error):
            with self.lock:self.credentials.pop(account,None)
            raise ValueError('连接失败：请检查网络、IMAP开关及授权码。未检查邮件。') from None
        return self.status()
    def disconnect(self,account):
        with self.lock:self.credentials.pop(address(account),None)
        return self.status()
    def check(self,key):
        with self.store.lock:a=self.store.read('投递记录.json')['applications'].get(key)
        if not a:raise ValueError('请先登记实际投递，再跟踪邮箱')
        account=address(a.get('applicant_email'));sender=address(a.get('recruiter_email'))
        result={'checked_at':stamp(),'status':'未检查','messages':[],'account':account,'sender':sender,'warnings':[]}
        client=None
        try:
            client=self.login(account)
            # INBOX and provider-advertised junk folders, never writable SELECT.
            folders=['INBOX'];typ,rows=client.list()
            if typ=='OK':
                for row in rows or []:
                    if not isinstance(row,bytes):continue
                    match=re.match(rb'\((.*?)\) "[^"]*" (.+)$',row)
                    if match and (b'\\junk' in match[1].lower() or b'\\spam' in match[1].lower()):folders.append(match[2].decode('ascii'))
            if len(folders)==1:result['warnings'].append('未识别到垃圾邮件文件夹，请在邮箱网页补查')
            checked=0
            for folder in dict.fromkeys(folders):
                typ,_=client.select(folder,readonly=True)
                if typ!='OK':result['warnings'].append('一个邮件文件夹未能检查');continue
                date=datetime.fromisoformat(a['applied_date']).strftime('%d-%b-%Y')
                typ,ids=client.uid('search',None,'SINCE',date,'FROM','"'+sender+'"')
                if typ!='OK':result['warnings'].append('一个文件夹搜索失败');continue
                checked+=1;uids=(ids[0] or b'').split()
                if len(uids)>30:result['warnings'].append('仅展示最近30封匹配邮件，更多邮件请在网页检查')
                for uid in uids[-30:]:
                    typ,parts=client.uid('fetch',uid,'(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])')
                    if typ!='OK':result['warnings'].append('部分邮件标题读取失败');continue
                    raw=next((p[1] for p in parts if isinstance(p,tuple)),None)
                    if not raw:continue
                    msg=email.message_from_bytes(raw)
                    if sender not in [v.lower() for _,v in getaddresses(msg.get_all('From',[]))]:continue
                    def header(k):
                        try:return str(make_header(decode_header(msg.get(k,''))))[:500]
                        except (ValueError,LookupError):return str(msg.get(k,''))[:500]
                    mid=msg.get('Message-ID') or hashlib.sha256(raw).hexdigest()
                    result['messages'].append({'id':mid,'subject':header('Subject'),'from':header('From'),'date':header('Date')})
            result['messages']=list({m['id']:m for m in result['messages']}.values())
            result['status']='已检查' if checked and not result['warnings'] else '部分已检查' if checked else '未检查'
            result['scope']='仅查登记的招聘方邮箱在投递日期后的来信标题；其他招聘系统地址需补充或自行检查，不据此判定拒绝或无其他来信。'
        except (OSError,imaplib.IMAP4.error,ValueError):
            result['status']='未检查';result['warnings'].append('未连接、授权失效或网络失败；不能判断是否有新邮件')
        finally:
            if client:
                try:client.logout()
                except (OSError,imaplib.IMAP4.error):pass
        with self.store.lock:
            saved=self.saved();old=saved['checks'].get(key,{})
            known={m['id'] for m in old.get('messages',[])}
            result['new_count']=sum(m['id'] not in known for m in result['messages'])
            result['messages']=list({m['id']:m for m in old.get('messages',[])+result['messages']}.values())[-100:]
            result['last_success_at']=result['checked_at'] if result['status']=='已检查' else old.get('last_success_at')
            saved['checks'][key]=result;self.store.write(FILE,saved)
        return result
