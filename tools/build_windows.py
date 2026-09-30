"""Build a portable Windows bundle from code only, never from private data."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import VERSION

def build():
    if sys.platform!='win32':raise SystemExit('Build the Windows package on Windows.')
    output=ROOT/'build'/'portable'
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--name','AutumnJobTracker',
        '--distpath',str(output),'--workpath',str(ROOT/'build'/'pyinstaller'), '--specpath',str(ROOT/'build'),
        '--add-data',str(ROOT/'web')+os.pathsep+'web','--add-data',str(ROOT/'public-opportunities.json')+os.pathsep+'.','--collect-all','pypdf',
        '--exclude-module','pymupdf','--exclude-module','fitz',str(ROOT/'launcher.py')],check=True,cwd=ROOT)
    folder=output/'AutumnJobTracker'
    subprocess.run([str(folder/'AutumnJobTracker.exe'),'--self-test'],check=True)
    subprocess.run([sys.executable,str(ROOT/'tools'/'smoke_windows.py'),str(folder/'AutumnJobTracker.exe')],check=True)
    target=ROOT/'dist'/f'autumn-job-tracker-v{VERSION}-windows-x64.zip';target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in folder.rglob('*'):
            rel=file.relative_to(folder)
            if file.is_file() and rel.parts[0] in ('AutumnJobTracker.exe','_internal'):
                archive.write(file,'autumn-job-tracker/'+rel.as_posix())
        for name in ('README.md','config.example.json','setup-ai.cmd','start-local-ai.ps1','docs/QUICKSTART.md'):
            archive.write(ROOT/name,'autumn-job-tracker/'+name)
    print(target)
    return target

if __name__=='__main__':build()
