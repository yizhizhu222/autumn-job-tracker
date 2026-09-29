function renderFeedbackReminder(){
 const due=feedbackState.due||[],el=$('#feedbackReminder');
 el.innerHTML=due.length?`<div class="warning small"><b>${due.length} 条投递可以补充反馈</b> · 写一句“暂无消息”也可以。<button class="quiet" id="showFeedbackDue">查看待填写</button></div>`:'';
 if(due.length)$('#showFeedbackDue').onclick=()=>{featureModal('待填写反馈',due.map(a=>`<p><b>${esc(a.company)} · ${esc(a.role)}</b><br><span class="small muted">${esc(a.reason)}</span> <button data-feedback="${esc(a.key)}">写反馈 / 看建议</button></p>`).join(''));};
}
function feedbackAdvice(a){
 if(!a)return '<p class="small muted">保存反馈后可分析，也可以直接分析。建议仅使用实际投递简历、岗位要求及公开案例。</p>';
 return `<div class="box"><b>建议依据</b><p>${esc(a.basis)}</p><p class="small muted">简历：${esc(a.resume_path||'未记录')} · ${esc(a.generated_at)}</p>${list(a.hard_conditions)}${a.suggestions.map(s=>`<p><b>${esc(s.action)}</b><br><span class="small muted">${esc(s.kind)} · ${esc(s.basis)}</span>${s.url?` <a target="_blank" rel="noreferrer" href="${esc(safeUrl(s.url))}">案例原文</a>`:''}</p>`).join('')||'<p>当前证据不足，补齐实际简历和JD后再给具体建议。</p>'}<details data-detail="case-evidence"><summary>录用案例与可比性 · ${a.cases.length} 条</summary>${a.cases.map(c=>`<p><a target="_blank" rel="noreferrer" href="${esc(safeUrl(c.url))}">${esc(c.title)}</a> · ${esc(c.published)}</p><p>${esc(c.facts)}</p><p class="small muted">${esc(c.comparison)}；${esc(c.limits)}</p>`).join('')||'<p>暂无经过核查的相近案例。</p>'}</details><details><summary>证据限制</summary>${list(a.warnings)}</details></div>`;
}
function feedbackLogs(logs){return `<summary>之前的反馈 · ${logs.length} 条</summary>${logs.map(x=>`<p>${esc(x.date)} · ${esc(x.text)}</p>`).join('')}`;}
function openFeedback(key){
 const a=ledger.applications[key];if(!a)return;
 const logs=feedbackState.items[key]||[];
 const m=featureModal('反馈与建议 · '+a.company,`<p>${esc(a.role)} · ${esc(a.applied_date)} 投递</p><form id="feedbackForm"><label>随手写下近况<textarea name="text" maxlength="4000" required placeholder="例如：暂无消息 / 收到面试了 / 今天感觉还不错"></textarea></label><p class="small muted">自由记录，不会自动改变招聘进度，也不会把你的心情当作拒绝或录用原因。首次投递次日提醒填写；等待回复期间每7天提醒更新。</p><button class="primary">保存反馈并给出建议</button></form><button id="analyzeApplication">直接按简历与案例分析</button><details id="feedbackLogs">${feedbackLogs(logs)}</details><div id="applicationAdvice">${feedbackAdvice(feedbackState.advice[key])}</div>`);
 const analyze=async()=>{$('#analyzeApplication').disabled=true;$('#applicationAdvice').innerHTML='<p>正在读取实际投递简历并核对岗位与公开案例…</p>';try{const result=await featureCall('/api/feedback',{op:'analyze',key});$('#applicationAdvice').innerHTML=feedbackAdvice(result);await load();}catch(e){$('#featureError').textContent=e.message;}finally{if($('#analyzeApplication'))$('#analyzeApplication').disabled=false;}};
 $('#analyzeApplication').onclick=analyze;
 $('#feedbackForm').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{feedbackState=await featureCall('/api/feedback',{op:'save',key,text:e.target.elements.text.value});e.target.elements.text.value='';$('#feedbackLogs').innerHTML=feedbackLogs(feedbackState.items[key]||[]);$('#featureError').textContent='反馈已保存';await load();await analyze();}catch(err){$('#featureError').textContent=err.message;}finally{button.disabled=false;}};
}
document.body.addEventListener('click',e=>{const b=e.target.closest('[data-feedback]');if(b)openFeedback(b.dataset.feedback);});
