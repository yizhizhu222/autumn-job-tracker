function renderOnboarding(){
 const el=document.querySelector('#onboarding');if(!el)return;
 const imported=Object.keys(catalog.originals||{}).length>0,hasJobs=catalog.jobs.length>0;
 el.innerHTML=(!imported||!hasJobs)?`<section class="panel"><h2>第一次使用，从这里开始</h2><p class="small">① 导入你的简历 → ② 连接本地AI → ③ 更新岗位信息。资料只保存在这台电脑。</p><div class="actions"><button class="primary" data-upload-resume>导入PDF / 文本简历</button><button id="setupAI">本地AI设置</button><a class="button" href="https://github.com/yizhizhu222/autumn-job-tracker#第一次使用" target="_blank" rel="noreferrer">新手步骤</a></div><p class="small muted">${imported?'简历已导入。':'尚未导入简历。'}${hasJobs?'已有岗位资料。':'岗位库是空的；联网搜索并核查后才会出现岗位，不预装演示公司。'}</p></section>`:'';
 if(document.querySelector('#setupAI'))document.querySelector('#setupAI').onclick=openAISettings;
}
function uploadResume(){
 const input=document.createElement('input');input.type='file';input.accept='.pdf,.txt,.md';
 input.onchange=async()=>{const file=input.files[0];if(!file)return;if(file.size>5000000){alert('请选择不超过5MB的简历');return;}
  const m=featureModal('导入简历','<p id="uploadStatus">正在归档并读取简历…</p>');
  try{const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});
   const result=await assistantCall({op:'upload_resume',name:file.name,data});
   document.querySelector('#uploadStatus').textContent=result.message;
   loadSequence++;lastStateSignature='';signalChange();await syncAll();
  }catch(error){document.querySelector('#uploadStatus').textContent=error.message;}
 };input.click();
}
document.body.addEventListener('click',e=>{if(e.target.closest('[data-upload-resume]'))uploadResume();});
