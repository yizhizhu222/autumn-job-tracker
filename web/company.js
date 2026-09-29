let mailboxState={connected:[],checks:{}};
function companyCards(jobs){
 const selected=new Set(jobs.filter(availableJob).map(j=>j.key));
 return companyGroups.map(g=>({...g,jobs:g.jobs.filter(j=>selected.has(j.key))})).filter(g=>g.jobs.length).map(companyCard).join('');
}
function companyCard(group){
 const jobs=group.jobs,channels=[...new Set(jobs.map(j=>j.channel==='email'?'邮件':j.direct?'网申':'待核实'))];
 return `<article class="card company-card" data-company="${esc(group.key)}"><div class="job-top"><div><h3>${esc(group.company)}</h3><p class="small muted">${jobs.length} 个岗位 · ${esc(channels.join(' / '))} · ${esc([...new Set(jobs.map(j=>j.place))].filter(Boolean).join('、'))}</p></div><div class="actions"><button class="primary" data-company-apply="${esc(jobs[0].key)}">查看投递入口</button><button class="quiet" data-seen="${esc(jobs[0].key)}">今天看完了</button><button class="quiet" data-exclude="${esc(jobs[0].key)}">不感兴趣</button></div></div><p class="small muted">${jobs.map(j=>esc(j.role)).join(' / ')}</p>${jobs.map(j=>j.quality?`<div class="small"><b>${esc(j.role)}：</b>${esc(j.quality.reason)}<p class="muted">${esc(j.quality.source.label)}优先级 · ${esc(j.quality.source.basis)}</p>${j.quality.unknown.length?`<p class="muted">待核实：${esc(j.quality.unknown.join('；'))}</p>`:''}<details data-detail="quality-${esc(j.key)}"><summary>为什么适合我：对照简历与JD</summary><p class="muted">对照版本：${esc(j.quality.resume_basis||'已设置简历')}</p>${j.quality.matched.map(e=>`<p><b>${esc(e.skill)}</b><br>简历：${esc(e.resume)}<br>JD：${esc(e.jd)}</p>`).join('')}<p>还缺少的技能证据：${esc(j.quality.missing.join('、')||'仍需核对熟练度及业务经验')}</p></details></div>`:'').join('')}${jobs.some(j=>j.repeat_reason)?`<p class="small">${esc(jobs.find(j=>j.repeat_reason).repeat_reason)}</p>`:''}<details class="job-details company-roles" data-detail="company-${esc(group.key)}"><summary>比较岗位、匹配度与简历</summary>${jobs.map(j=>jobCard(j)).join('')}</details></article>`;
}
function openCompanyApply(key){
 const group=companyGroups.find(g=>g.jobs.some(j=>j.key===key));if(!group)return;
 const jobs=group.jobs.filter(availableJob);if(!jobs.length)return;
 const m=featureModal(group.company,`<p class="small muted">同公司只保留这一张投递卡。选择实际申请岗位；按企业规则选择志愿，完成后登记，整家公司转入跟踪。</p><label>选择岗位<select id="companyRole">${jobs.map(j=>`<option value="${esc(j.key)}">${esc(j.role)} · ${j.channel==='email'?'邮件':j.direct?'网申':'待核实'}</option>`).join('')}</select></label><div id="companyEntry"></div><div class="actions"><button id="companyMark" class="primary">我已投递，登记并跟踪</button></div>`);
 const show=()=>{const j=jobs.find(x=>x.key===$('#companyRole').value),url=safeUrl(j.apply_url||j.source),resume=pathlink(j.resume?.path);
  $('#companyEntry').innerHTML=`<p>${esc(j.online||'线上面试方式待确认')}</p>${j.channel==='email'?`<label>招聘方邮箱（纯文本）<input readonly value="${esc(j.email||'官网未明确，登记时填写实际收件人')}"></label><p class="small muted">在自己的邮箱发送，随后填写发件邮箱、收件邮箱与主题。填写地址本身不会计为已投递。</p>`:''}<div class="actions">${url!=='#'?`<a class="button" href="${esc(url)}" target="_blank" rel="noreferrer">${j.channel==='email'?'查看官网说明':j.direct?'打开网申入口 ↗':'查看待核实来源'}</a>`:''}${resume!=='#'?`<a class="button" href="${resume}" download>下载推荐简历</a>`:''}</div><p class="small muted">${esc(j.resume_reason||j.change_note||'核对岗位要求后选择简历。')}</p>`;
 };show();$('#companyRole').onchange=show;
 $('#companyMark').onclick=()=>{const selected=$('#companyRole').value;m.close();openForm('mark',selected);};
}
function mailFields(a={}){
 return `<label>实际发件邮箱<input name="applicant_email" type="email" value="${esc(a.applicant_email||mailboxState.connected[0]||'')}" required></label><label>招聘方收件 / 回复邮箱<input name="recruiter_email" type="email" value="${esc(a.recruiter_email||a.email||'')}" required></label><label>已发送邮件主题<input name="mail_subject" value="${esc(a.mail_subject||'')}"></label><p class="small muted">只有已实际发送或成功网申才登记。邮箱检查按这里填写的招聘方地址查来信，其他通知地址可在跟踪时修改。</p>`;
}
async function refreshMailbox(){try{mailboxState=await(await fetch('/api/mailbox')).json();}catch{}}
async function openMailSettings(){
 await refreshMailbox();
 const m=featureModal('邮箱只读检查',`<p>已连接：${esc(mailboxState.connected.join('、')||'暂无')}</p><form id="mailConnect"><label>邮箱服务<select name="provider"><option value="qq">QQ / foxmail</option><option value="gmail">Gmail</option></select></label><label>你的邮箱<input name="address" type="email" required autocomplete="off"></label><label>邮箱授权码 / 应用密码<input name="secret" type="password" required autocomplete="new-password"></label><p class="small muted">授权码只留在本次程序内存，关闭程序后需要重新填写。不会发送、删除或标记已读。聊天中的邮箱连接不能直接给本地程序使用。</p><button class="primary">连接并验证</button></form><div class="actions">${mailboxState.connected.map(a=>`<button data-disconnect="${esc(a)}">断开 ${esc(a)}</button>`).join('')}</div><p class="small muted"><a href="https://support.google.com/accounts/answer/185833" target="_blank" rel="noreferrer">Gmail应用密码说明</a> · QQ邮箱请在网页设置中启用IMAP并生成授权码。</p>`);
 $('#mailConnect').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;const data=Object.fromEntries(new FormData(e.target));try{mailboxState=await featureCall('/api/mailbox',{op:'connect',...data});e.target.elements.secret.value='';m.close();await openMailSettings();}catch(err){$('#featureError').textContent=err.message;e.target.elements.secret.value='';}finally{b.disabled=false;}};
 m.querySelectorAll('[data-disconnect]').forEach(b=>b.onclick=async()=>{await featureCall('/api/mailbox',{op:'disconnect',address:b.dataset.disconnect});m.close();openMailSettings();});
}
async function openMailTracking(key){
 const a=ledger.applications[key];await refreshMailbox();const check=mailboxState.checks[key];
 const m=featureModal('跟踪 '+a.company+' · '+a.role,`<form id="mailDetails">${mailFields({...a,email:a.job_snapshot?.email})}<button>保存邮箱资料</button></form><div class="actions"><button id="checkReply" class="primary">只读检查来信</button><button id="connectHere">连接邮箱</button><a class="button" href="${a.applicant_email?.endsWith('@gmail.com')?'https://mail.google.com/':'https://mail.qq.com/'}" target="_blank" rel="noreferrer">打开邮箱网页</a></div><div id="mailResult"></div>`);
 const paint=r=>{$('#mailResult').innerHTML=r?`<p>${esc(r.status)} · ${esc(r.checked_at)} · 本次新发现 ${r.new_count||0} 封</p>${list(r.warnings)}<p class="small muted">${esc(r.scope||'')}</p>${(r.messages||[]).map(x=>`<div class="box"><b>${esc(x.subject||'无主题')}</b><p class="small muted">${esc(x.from)} · ${esc(x.date)}</p></div>`).join('')||'<p>当前没有已保存的匹配来信。失败或部分检查不代表没有邮件。</p>'}`:'<p class="small muted">尚未检查。可以先保存邮箱资料，再连接并检查。新来信内容与截止时间请打开邮箱原文核实。</p>';};paint(check);
 $('#mailDetails').onsubmit=async e=>{e.preventDefault();try{await change({op:'mail_details',key,...Object.fromEntries(new FormData(e.target))});$('#featureError').textContent='邮箱资料已保存';}catch(err){$('#featureError').textContent=err.message;}};
 $('#checkReply').onclick=async e=>{const b=e.target;b.disabled=true;b.textContent='正在检查…';try{await change({op:'mail_details',key,...Object.fromEntries(new FormData($('#mailDetails')))});const r=await featureCall('/api/mailbox',{op:'check',key});paint(r);}catch(err){$('#featureError').textContent=err.message;}finally{b.disabled=false;b.textContent='只读检查来信';}};
 $('#connectHere').onclick=()=>{m.close();openMailSettings();};
}
document.body.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.companyApply)openCompanyApply(b.dataset.companyApply);if(b.dataset.mailTrack)openMailTracking(b.dataset.mailTrack);});

function careerList(jobs,after=false){
 const selected=jobs.filter(availableJob),groups=new Map();
 for(const j of selected){const company=companyGroups.find(g=>g.jobs.some(x=>x.key===j.key));const key=company?.key||normalize(j.company);if(!groups.has(key))groups.set(key,{name:company?.company||j.company,jobs:[]});groups.get(key).jobs.push(j);}
 return [...groups].map(([key,g])=>`<details class="box" data-detail="career-company-${after?'after':'now'}-${esc(key)}"><summary>${esc(g.name)} · ${g.jobs.length}个岗位</summary>${g.jobs.map(j=>careerJob(j,after)).join('')}</details>`).join('');
}

async function setCompanySeen(key, undo=false){
 try{await featureCall('/api/day',{op:undo?'undo_seen':'seen',key});await syncAll();render();}
 catch(e){alert(e.message);}
}
document.body.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.seen)setCompanySeen(b.dataset.seen);if(b.dataset.undoSeen)setCompanySeen(b.dataset.undoSeen,true);});
