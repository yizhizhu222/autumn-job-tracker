let careerState=null, careerPoll=null;
async function featureCall(path,payload){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(payload)});
  const d=await r.json();if(!r.ok)throw Error(d.error||'操作失败');loadSequence++;lastStateSignature='';signalChange();return d;
}
function featureModal(title,html){
  let m=$('#featureModal');if(!m){m=document.createElement('dialog');m.id='featureModal';document.body.append(m);}
  m.innerHTML=`<h2>${esc(title)}</h2>${html}<p class="error" id="featureError"></p><button id="closeFeature" type="button">关闭</button>`;
  if(!m.open)m.showModal();$('#closeFeature').onclick=()=>m.close();return m;
}
function setupRegion(){
  $('#regionLabel').textContent='地域：'+([jobPreferences.province,jobPreferences.city].filter(Boolean).join(' / ')||'不限');
}
function openRegion(){
  const p=jobPreferences;
  const m=featureModal('按地域找岗位',`<p>保存后立即筛选现有岗位，后续每日搜索也使用此地域。筛选本地岗位不耗流量；联网找新岗位需要流量。</p><form id="regionForm"><label>省份 / 直辖市<select name="province" id="province"><option value="">不限</option>${Object.keys(regions).map(r=>`<option ${r===p.province?'selected':''}>${esc(r)}</option>`).join('')}</select></label><label>城市（可选或输入）<input name="city" id="city" list="cityOptions" value="${esc(p.city)}" placeholder="留空为所选省份全部城市"><datalist id="cityOptions"></datalist></label><label><input type="checkbox" name="include_unknown" style="width:auto" ${p.include_unknown?'checked':''}> 保留地点尚未确认的岗位</label><p class="small muted">“全国招聘”保留为可选城市待确认；线上面试不代表远程工作。岗位直达和每日推荐使用此筛选，已投档案保留完整历史。</p><button class="primary">保存地域</button></form>`);
  const cities=()=>{$('#cityOptions').innerHTML=(regions[$('#province').value]||[]).map(c=>`<option value="${esc(c)}">`).join('');};cities();
  $('#province').onchange=()=>{$('#city').value='';cities();};
  $('#regionForm').onsubmit=async e=>{e.preventDefault();try{await featureCall('/api/preferences',{op:'region',province:e.target.elements.province.value,city:e.target.elements.city.value,include_unknown:e.target.elements.include_unknown.checked});m.close();await load();await refreshAssistant();await refreshCareer();}catch(err){$('#featureError').textContent=err.message;}};
}
async function openStartup(){
  const m=featureModal('开机自启动','<p id="startupState">正在读取Windows设置…</p><button id="toggleStartup" disabled>读取中</button><p class="small muted">这里控制开机登录后的后台启动，不会自动打开网页。每日推荐仍由“本地AI设置”中的开关控制。关闭后当前程序仍可使用。</p>');
  try{
    let s=await (await fetch('/api/startup')).json();
    const paint=()=>{$('#startupState').textContent=(s.enabled===null?'状态未知':s.enabled?'当前已开启':'当前已关闭')+'。'+s.message;$('#toggleStartup').textContent=s.enabled?'关闭开机自启动':'开启开机自启动';$('#toggleStartup').disabled=!s.supported;};paint();
    $('#toggleStartup').onclick=async()=>{const b=$('#toggleStartup');b.disabled=true;try{s=await featureCall('/api/startup',{enabled:!s.enabled});paint();}catch(e){$('#featureError').textContent=e.message;b.disabled=false;}};
  }catch(e){$('#featureError').textContent='无法读取自启动状态';}
}
function openExclude(key){
  const j=catalog.jobs.find(x=>x.key===key);if(!j)return;
  let domain='';try{domain=new URL(j.apply_url||j.source||j.entry).hostname;}catch{}
  const m=featureModal('删除推荐并记住偏好',`<p>${esc(j.company)} · ${esc(j.role)}</p><form id="excludeForm"><label>以后不再推荐<select name="kind" id="excludeKind"><option value="job">仅此岗位（含同岗位重复来源）</option><option value="platform" ${domain?'':'disabled'}>此岗位来源平台 / 网站：${esc(j.platform||domain||'无网页')}</option><option value="role">包含指定关键词的岗位类型</option></select></label><label id="keywordLabel" class="hidden">岗位名称关键词<input name="value" placeholder="例如：电话销售、算法工程师"></label><label>不感兴趣的原因（可选）<textarea name="reason" placeholder="例如：编程过多、通勤不合适"></textarea></label><p class="small muted">从待投与推荐列表移除，并长期记录。原始岗位与已投历史保留，可在“不感兴趣”里恢复。网站规则只排除该来源，其他平台上的同公司岗位仍可出现。</p><button class="primary">移除并记住</button></form>`);
  $('#excludeKind').onchange=e=>$('#keywordLabel').classList.toggle('hidden',e.target.value!=='role');
  $('#excludeForm').onsubmit=async e=>{e.preventDefault();try{const p=Object.fromEntries(new FormData(e.target));await featureCall('/api/preferences',{op:'exclude',key,...p});m.close();await load();await refreshAssistant();await refreshCareer();}catch(err){$('#featureError').textContent=err.message;}};
}
function renderExclusions(){
  $('#intro').innerHTML='<section class="panel"><h2>记住你不想要的机会</h2><p>每次更新推荐都会使用这些规则。恢复后，符合地域且未投递的岗位可重新显示；已有投递记录不会被删除。</p><button id="addRoleRule">添加岗位关键词</button></section>';
  const active=(jobPreferences.rules||[]).filter(r=>r.active);
  $('#content').innerHTML=active.map(r=>`<article class="card"><span class="tag">${esc({job:'单个岗位',platform:'平台 / 网站',role:'岗位关键词'}[r.kind])}</span><h3>${esc(r.label)}</h3><p>${esc(r.reason||'未填写原因')}</p><p class="small muted">${esc(r.value)} · ${esc(r.at)}</p><button data-restore="${esc(r.id)}">恢复推荐</button></article>`).join('')||'<div class="empty">还没有不感兴趣记录。岗位卡片上的“不感兴趣”可以添加。</div>';
  $('#addRoleRule').onclick=()=>{const m=featureModal('排除岗位类型','<form id="roleRuleForm"><label>岗位名称中包含<input name="value" required placeholder="例如：电话销售"></label><label>原因<textarea name="reason"></textarea></label><button class="primary">记录偏好</button></form>');$('#roleRuleForm').onsubmit=async e=>{e.preventDefault();try{await featureCall('/api/preferences',{op:'exclude',kind:'role',...Object.fromEntries(new FormData(e.target))});m.close();await load();await refreshAssistant();await refreshCareer();}catch(err){$('#featureError').textContent=err.message;}};};
}
async function refreshCareer(){
  try{careerState=await (await fetch('/api/career')).json();if(tab==='career')render();
    if(careerState.progress.running&&!careerPoll)careerPoll=setInterval(refreshCareer,4000);
    if(!careerState.progress.running&&careerPoll){clearInterval(careerPoll);careerPoll=null;}
  }catch{if(tab==='career')$('#content').textContent='简历分析服务未连接';}
}
function careerJob(j,after=false){
  if(!availableJob(j))return '';return `<details class="box" data-detail="career-${after?'after':'now'}-${esc(j.key)}"><summary>${esc(j.company)} · ${esc(j.role)}</summary><b>${esc(j.company)} · ${esc(j.role)}</b><p class="small muted">${esc(j.place)}</p><p>简历已提及：${esc(j.matched.join('、')||'暂无对应证据')}</p>${after?`<p class="ok">完成并验收项目后可补充：${esc(j.gained.join('、'))}</p>`:''}<p>当前缺少明确证据：${esc(j.missing.join('、')||'仍需核实熟练度及业务经验')}</p>${list(j.hard_conditions)}<details><summary>核对原JD证据及资格</summary>${Object.entries(j.evidence).map(([k,v])=>`<p><b>${esc(k)}</b>：${esc(v)}</p>`).join('')}${list(j.unknown)}<p>${esc(j.basis)}</p></details><button data-inspect="${esc(j.key)}">查看完整岗位与推荐简历</button> ${safeUrl(j.url)!=='#'?`<a class="button" href="${esc(safeUrl(j.url))}" target="_blank" rel="noreferrer">${j.direct&&j.channel!=='email'?'打开岗位网页':'查看来源（入口待核实）'}</a>`:''}</details>`;
}
function renderCareer(){
  const p=careerState?.plan,progress=careerState?.progress;
  $('#intro').innerHTML=`<section class="panel"><div class="row"><div><h2>简历诊断与项目路线</h2><p>已有经历找缺口；空白简历从专业出发。项目要有可复现的交付物和验收结果。</p></div><button class="primary" id="analyzeCareer" ${progress?.running?'disabled':''}>${p?'重新分析简历':'开始分析简历'}</button></div><p class="small muted">${esc(progress?.running?progress.message:p?.ai_status||'可以读取本地简历，也可以只填写专业。')}</p></section>`;
  $('#analyzeCareer').onclick=openCareerForm;
  if(!p){$('#content').innerHTML='<div class="empty">先填写专业并选择简历，即可查看当前方向、项目方案与完成后的岗位机会。</div>';return;}
  let h=`<section class="card"><span class="tag">${esc(p.major)}</span><h3>${esc(p.summary)}</h3><p>分析时间：${esc(p.generated_at)} · 当时符合地域与偏好的未投岗位样本：${p.sample_size}条</p>${list(p.warnings)}<details><summary>简历中识别到的技能原文</summary>${Object.entries(p.evidence).map(([k,v])=>`<p><b>${esc(k)}</b>：${esc(v)}</p>`).join('')||'<p>暂无证据；专业名称不会被当作已掌握技能。</p>'}</details></section>`;
  if(p.ai)h+=`<section class="card"><h3>本地AI诊断</h3><p>${esc(p.ai.summary)}</p>${list(p.ai.improvements)}<details><summary>项目实施建议</summary>${list(p.ai.project_advice)}</details></section>`;
  h+='<h2>现在可以尝试 / 继续核实</h2><p class="small muted">按已提及技能和条件缺口排序；低匹配保留供探索，不能据此认定满足资格。</p>'+(p.current_jobs.map(j=>careerJob(j)).join('')||'<p>当前没有可展示的真实岗位；保留项目方案，继续更新岗位库。</p>');
  h+='<h2>建议先完成的项目</h2>';
  for(const project of p.projects){
    h+=`<details class="card career-project" data-detail="project-${esc(project.id)}"><summary>${esc(project.title)}</summary><span class="tag">${esc({planned:'待开始',working:'进行中',completed:'本人登记已验收'}[project.status])}</span><h3>${esc(project.title)}</h3><p>${esc(project.duration)}</p><p><b>要解决的问题：</b>${esc(project.problem)}</p><p><b>数据与环境：</b>${esc(project.data)}</p><p>${esc(project.selection_reason)}</p><p class="small muted">覆盖${project.covered_jobs}条岗位 / ${project.covered_companies}家公司；分母${project.sample_size}条本地JD。计数为分析时快照，排除偏好变化后可重新分析。</p><div class="columns"><div><b>实施步骤</b>${list(project.steps)}<b>最终交付物</b>${list(project.deliverables)}</div><div><b>验收标准</b>${list(project.acceptance)}<p><b>通用岗位方向：</b>${esc(project.roles.join('、'))}（方向示例，不表示当前有招聘）</p></div></div><button data-project="${esc(project.id)}">记录项目进度与验收依据</button>${project.completion_evidence?`<p>${esc(project.completion_evidence)}</p>`:''}<details><summary>完成后可争取的真实岗位（${project.jobs_after.length}条示例）</summary><p class="warning small">仅在确实完成并能展示成果后，才能把相关经历写入简历。未补齐的硬条件仍然有效。</p>${project.jobs_after.map(j=>careerJob(j,true)).join('')||'<p>当前岗位库没有可证实的新增技能匹配；上方为通用方向，需继续收集JD。</p>'}</details></details>`;
  }
  $('#content').innerHTML=h;
}
async function openCareerForm(){
  if(!assistantState)await refreshAssistant();
  const s=assistantState?.settings||{};
  const paths=[...new Set([s.resume_path,...Object.values(catalog.originals||{}).map(r=>r.path),...catalog.jobs.map(j=>j.resume?.path)].filter(Boolean))];
  const m=featureModal('分析简历与推荐项目',`<form id="careerForm"><label>专业<input name="major" required value="${esc(careerState?.plan?.major||'')}" placeholder="例如：数据科学与大数据技术"></label><label>本地简历<select name="path"><option value="">不选文件，直接填写正文</option>${paths.map(p=>`<option value="${esc(p)}" ${s.resume_path===p?'selected':''}>${esc(p)}</option>`).join('')}</select></label><button type="button" id="readCareerResume">读取所选简历</button><label>简历正文<textarea name="profile" style="min-height:180px">${esc(s.profile||'')}</textarea></label><button type="button" id="blankCareer">我还没有简历内容，按专业分析</button><p class="small muted">诊断只发给本机模型，不修改原简历。可以删去姓名、电话等与分析无关的内容。仅凭专业不会认定已掌握技能。</p><button class="primary" id="submitCareer">开始分析</button></form>`);
  $('#blankCareer').onclick=()=>{$('#careerForm').elements.profile.value='';$('#careerForm').elements.path.value='';};
  $('#readCareerResume').onclick=async()=>{try{const f=$('#careerForm');f.elements.profile.value=(await assistantCall({op:'extract',path:f.elements.path.value})).text;}catch(e){$('#featureError').textContent=e.message;}};
  $('#careerForm').onsubmit=async e=>{e.preventDefault();$('#submitCareer').disabled=true;try{await featureCall('/api/career',{op:'analyze',major:e.target.elements.major.value,profile:e.target.elements.profile.value});m.close();await refreshCareer();}catch(err){$('#featureError').textContent=err.message;$('#submitCareer').disabled=false;}};
}
function openProject(id){
  const p=careerState.plan.projects.find(x=>x.id===id);
  const m=featureModal(p.title,`<form id="projectForm"><label>进度<select name="status">${Object.entries({planned:'待开始',working:'进行中',completed:'已完成并验收（本人登记）'}).map(([k,v])=>`<option value="${k}" ${p.status===k?'selected':''}>${v}</option>`).join('')}</select></label><label>成果位置、验收结果和仍存在的问题<textarea name="evidence">${esc(p.completion_evidence)}</textarea></label><p class="small muted">完成记录不会自动变成简历经历，也不会改变原岗位的学历和经验要求。</p><button class="primary">保存进度</button></form>`);
  $('#projectForm').onsubmit=async e=>{e.preventDefault();try{await featureCall('/api/career',{op:'progress',id,...Object.fromEntries(new FormData(e.target))});m.close();await refreshCareer();}catch(err){$('#featureError').textContent=err.message;}};
}
$('#regionButton').onclick=openRegion;$('#startupButton').onclick=openStartup;
$('#content').addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;
  if(b.dataset.exclude)openExclude(b.dataset.exclude);
  if(b.dataset.restore){try{await featureCall('/api/preferences',{op:'restore',id:b.dataset.restore});await load();await refreshAssistant();await refreshCareer();}catch(err){alert(err.message);}}
  if(b.dataset.project)openProject(b.dataset.project);
  if(b.dataset.inspect){const j=catalog.jobs.find(x=>x.key===b.dataset.inspect);if(j)featureModal('岗位详情',jobCard(j));}
});
document.body.addEventListener('click',e=>{if(e.target.closest('#featureModal')){const b=e.target.closest('[data-mark]');if(b){$('#featureModal').close();openForm('mark',b.dataset.mark);}const x=e.target.closest('[data-exclude]');if(x){$('#featureModal').close();openExclude(x.dataset.exclude);}}});
