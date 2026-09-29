"""Launch the actual executable in a clean folder, import a resume, restart."""
import base64
import json
from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request,build_opener,ProxyHandler

exe=Path(sys.argv[1]).resolve()
process_options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
with tempfile.TemporaryDirectory(prefix='tracker-release-') as temp:
    data=(Path(temp)/'fresh data').resolve();data.mkdir()
    (data/'assistant-settings.json').write_text('{"enabled":false,"search_enabled":false}',encoding='utf-8')
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    url=f'http://127.0.0.1:{port}'
    opener=build_opener(ProxyHandler({}))
    def get(path):
        with opener.open(url+path,timeout=3) as response:return json.load(response)
    def post(data,token):
        req=Request(url+'/api/assistant',data=json.dumps(data).encode(),headers={'Origin':url,'X-Tracker-Token':token,'Content-Type':'application/json'})
        with opener.open(req,timeout=10) as response:return json.load(response)
    for phase in (0,1):
        process=subprocess.Popen([str(exe),'--no-browser','--port',str(port),'--data-dir',str(data)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**process_options)
        try:
            for _ in range(120):
                if process.poll() is not None:raise RuntimeError('Executable exited before serving')
                try:state=get('/api/state');break
                except OSError:time.sleep(.25)
            else:raise RuntimeError('Executable startup timed out')
            assert Path(get('/health')['data_dir']).samefile(data),'Executable must serve the requested data directory'
            for resource in ('/','/onboarding.js','/feedback.js'):
                with opener.open(url+resource,timeout=3) as response:assert response.status==200
            if phase==0:
                result=post({'op':'upload_resume','name':'resume.txt','data':base64.b64encode(b'SQL Excel data analysis project').decode()},state['token'])
                assert (data/result['path']).read_bytes()==b'SQL Excel data analysis project'
                second=subprocess.run([str(exe),'--no-browser','--port',str(port),'--data-dir',str(data)],timeout=15,capture_output=True,**process_options)
                assert second.returncode==0,'Repeated launch must reuse the server'
            else:assert len(state['catalog']['originals'])==1
            assert state['ledger']['applications']=={}
        finally:process.terminate();process.wait(timeout=10)
print('PASS: clean executable, local assets, resume upload, repeated launch, data persistence.')
