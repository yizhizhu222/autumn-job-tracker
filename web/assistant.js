let assistantState = null, modelState = null, assistantPoll = null;
async function assistantCall(payload) {
  const r = await fetch('/api/assistant', {method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(payload)});
  const d = await r.json(); if(!r.ok) throw Error(d.error||'操作未完成'); return d;
}
async function refreshAssistant(){
  try { const r=await fetch('/api/assistant'); if(!r.ok)throw Error(); assistantState=await r.json();
    if(tab==='recommend')render();
    if(assistantState.progress.running&&!assistantPoll)assistantPoll=setInterval(refreshAssistant,4000);
    if(!assistantState.progress.running&&assistantPoll){clearInterval(assistantPoll);assistantPoll=null;await load();}
  } catch { if($('#aiStatus'))$('#aiStatus').textContent='推荐服务未连接'; }
}
function renderRecommendations(){
  const r=assistantState?.report, p=assistantState?.progress;
  $('#intro').innerHTML='<section class="panel"><div class="row"><div><h2 style="margin-top:0">今日公司推荐</h2><p>优先量子行业，其次少编程与专业相关岗位。低匹配和待确认的机会也会保留，已投岗位自动排除。</p></div><div class="actions"><button class="primary" id="generateDaily">立即更新推荐</button><button id="aiSettings">本地 AI 设置</button></div></div><div id="aiStatus" class="small muted"></div></section>';
  $('#aiStatus').textContent=p?.running?p.message:(r?`${r.date||'尚未生成'} · ${r.message||''}`:'正在读取今日推荐');
  $('#generateDaily').disabled=!!p?.running||!connected;
  $('#generateDaily').onclick=async()=>{try{await assistantCall({op:'generate'});await refreshAssistant();}catch(e){alert(e.message);}};
  $('#aiSettings').onclick=openAISettings;
  if(!r){$('#content').innerHTML='<div class="empty">正在读取推荐…</div>';return;}
  let html=(r.date&&r.date!==today?'<p class="warning">这里是上次推荐，今日更新尚未完成。</p>':'')+(r.errors||[]).map(e=>'<p class="small muted">'+esc(e)+'</p>').join('');
  const items=(r.items||[]).filter(j=>!wasApplied(j)&&commonFilter(j));
  for(const tier of ['优先投递','可以尝试','待确认']){
    const group=items.filter(j=>j.tier===tier); if(!group.length)continue;
    html+=`<h2>${tier} · ${group.length}</h2>`+group.map(j=>`<div class="box small"><b>${esc(j.recommendation_origin)}</b> · ${esc(j.application_mode)}<br>${esc(j.application_note)}${list(j.recommendation_warnings)}${j.resume_reason?'<p>简历建议：'+esc(j.resume_reason)+'</p>':''}<button data-ai="${esc(j.key)}">本地 AI 微调简历</button></div>`+jobCard(j)).join('');
  }
  $('#content').innerHTML=html+(items.length?'':`<div class="empty">${esc(r.empty_reason||'当前筛选下没有岗位；清除筛选或更新推荐。')}</div>`);
}
async function openAISettings(){
  await refreshAssistant();
  const s=assistantState.settings;
  let modal=document.querySelector('#assistantModal');
  if(!modal){modal=document.createElement('dialog');modal.id='assistantModal';document.body.append(modal);}
  const paths=[...new Set([s.resume_path,...Object.values(catalog.originals||{}).map(r=>r.path),...catalog.jobs.map(j=>j.resume?.path)].filter(Boolean))];
  modal.innerHTML=`<form id="assistantForm"><h2>本地 AI 与每日推荐</h2><p id="modelStatus">检查本地模型…</p><label>本地模型名称<input name="model" value="${esc(s.model)}" required></label><p class="small muted">仅连接本机 Ollama（127.0.0.1:11434），不需要 API Key。首次运行需安装 Ollama 并下载模型。</p><label><input type="checkbox" name="enabled" style="width:auto" ${s.enabled?'checked':''}> 开启每日推荐（程序运行期间）</label><label>北京时间每天几点生成<input name="hour" type="number" min="0" max="23" value="${s.hour}"></label><label>每天目标数量<input name="target" type="number" min="3" max="20" value="${s.target}"></label><label><input type="checkbox" name="search_enabled" style="width:auto" ${s.search_enabled?'checked':''}> 联网查找公开招聘网页</label><p class="small muted">关机期间不会执行；当天恢复运行后补跑。未找到足量新岗位时显示已有未投备选，并标注来源与待确认项。</p><label>求职条件<textarea name="preferences">${esc(s.preferences)}</textarea></label><label>用于分析与微调的简历<select name="resume_path"><option value="">手动粘贴正文</option>${paths.map(p=>`<option value="${esc(p)}" ${p===s.resume_path?'selected':''}>${esc(p)}</option>`).join('')}</select></label><button id="extractResume" type="button">读取所选简历正文</button><label>简历正文（只送往本机模型）<textarea name="profile" style="min-height:180px">${esc(s.profile)}</textarea></label><p class="small muted">联网搜索只发送通用岗位关键词，简历正文不进入搜索请求。</p><p id="assistantError" class="error"></p><div class="actions"><button type="submit" class="primary">保存设置</button><button type="button" id="closeAssistant">关闭</button></div></form>`;
  modal.showModal();
  $('#closeAssistant').onclick=()=>modal.close();
  $('#extractResume').onclick=async()=>{try{const f=$('#assistantForm');const d=await assistantCall({op:'extract',path:f.elements.resume_path.value});f.elements.profile.value=d.text;}catch(e){$('#assistantError').textContent=e.message;}};
  $('#assistantForm').onsubmit=async e=>{e.preventDefault();const f=e.target;try{await assistantCall({op:'settings',model:f.elements.model.value,profile:f.elements.profile.value,resume_path:f.elements.resume_path.value,preferences:f.elements.preferences.value,hour:Number(f.elements.hour.value),target:Number(f.elements.target.value),enabled:f.elements.enabled.checked,search_enabled:f.elements.search_enabled.checked});modal.close();await refreshAssistant();}catch(err){$('#assistantError').textContent=err.message;}};
  try{modelState=await (await fetch('/api/assistant/model')).json();$('#modelStatus').textContent=modelState.message+' · '+(modelState.available?'所选模型已就绪':'所选模型尚未就绪');}catch{$('#modelStatus').textContent='模型检查失败';}
}
async function createResumeDraft(key,button){
  button.disabled=true;button.textContent='本地 AI 正在分析…';
  try{
    const d=await assistantCall({op:'draft',key});let modal=document.querySelector('#draftModal');
    if(!modal){modal=document.createElement('dialog');modal.id='draftModal';document.body.append(modal);}
    modal.innerHTML=`<h2>简历小幅修改方案</h2><p>${esc(d.draft.company)} · ${esc(d.draft.role)}</p><p class="small muted">微调底稿：${esc(d.draft.source_path||"设置中的简历正文")}</p>${d.draft.edits.map(e=>`<div class="box"><b>原文</b><p>${esc(e.before)}</p><b>建议改为</b><p>${esc(e.after)}</p><p class="small muted">${esc(e.reason)}</p></div>`).join('')}<p class="small">检查建议是否符合真实经历。可保存微调正文；原文件为PDF时，也可尝试在原位置替换单行。无法保持原排版时会停止导出。原文件保留。</p><div id="draftResult"></div><div class="actions"><button id="saveDraft" class="primary">保存微调正文</button><button id="savePdf">导出微调PDF</button><button id="closeDraft">关闭</button></div>`;
    modal.showModal();$('#savePdf').disabled=!d.draft.source_path?.toLowerCase().endsWith('.pdf');$('#savePdf').onclick=async()=>{try{const saved=await assistantCall({op:'apply_pdf',id:d.draft.id});$('#draftResult').innerHTML=`<p>${esc(saved.message)}</p><a class="button" target="_blank" href="${pathlink(saved.path)}">预览微调PDF</a> <a download href="${pathlink(saved.path)}">下载</a>`;await load();}catch(e){$('#draftResult').textContent=e.message;}};$('#closeDraft').onclick=()=>modal.close();$('#saveDraft').onclick=async()=>{try{const saved=await assistantCall({op:'apply_draft',id:d.draft.id});$('#draftResult').innerHTML=`<p>${esc(saved.message)}</p><a class="button" download href="${pathlink(saved.path)}">下载微调正文</a>`;}catch(e){$('#draftResult').textContent=e.message;}};
  }catch(e){alert(e.message);}finally{button.disabled=false;button.textContent='本地 AI 微调简历';}
}
document.querySelector('#content').addEventListener('click',e=>{const b=e.target.closest('[data-ai]');if(b)createResumeDraft(b.dataset.ai,b);});
refreshAssistant();

setInterval(()=>{if(!document.hidden&&!assistantPoll)refreshAssistant();},30000);
