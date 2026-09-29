"""Current-user Windows logon startup. Preserve existing daily task triggers."""
import json
import os
from pathlib import Path
import subprocess
import sys

TASK_SCRIPT = r'''
$ErrorActionPreference='Stop'
$task=Get-ScheduledTask -TaskName 'AutumnJobTrackerDaily' -ErrorAction SilentlyContinue
if ($task) {
  $expected=Join-Path $env:TRACKER_DATA '本地AI\start-tracker.ps1'
  $ours=@($task.Actions | Where-Object {$_.Arguments -like ('*'+$expected+'*')}).Count -gt 0
  if ($ours) {
    if ($env:TRACKER_ACTION -ne 'status') {
      $triggers=@($task.Triggers | Where-Object {$_.CimClass.CimClassName -ne 'MSFT_TaskLogonTrigger'})
      if ($env:TRACKER_ACTION -eq 'enable') { $triggers+=New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) }
      if ($triggers.Count -eq 0) { throw 'Cannot remove the only trigger from this task' }
      $null=Set-ScheduledTask -TaskName $task.TaskName -Trigger $triggers
      $task=Get-ScheduledTask -TaskName $task.TaskName
    }
    $on=@($task.Triggers | Where-Object {$_.CimClass.CimClassName -eq 'MSFT_TaskLogonTrigger' -and $_.Enabled -ne $false}).Count -gt 0
    @{managed=$true;enabled=($on -and $task.State -ne 'Disabled')} | ConvertTo-Json -Compress
    exit
  }
}
'{"managed":false}'
'''

class Startup:
    def __init__(self, directory, port, base): self.directory,self.port,self.base=Path(directory),port,Path(base)
    def task(self, action):
        env={**os.environ,'TRACKER_DATA':str(self.directory),'TRACKER_ACTION':action}
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',TASK_SCRIPT],env=env,capture_output=True,timeout=20,creationflags=0x08000000)
        if r.returncode: raise OSError('无法读取或修改当前用户启动任务，请确认运行账户权限')
        return json.loads(r.stdout.decode('utf-8-sig',errors='replace').strip())
    def name(self):
        import hashlib
        return 'AutumnJobTracker-'+hashlib.sha256(str(self.directory).casefold().encode()).hexdigest()[:12]
    def command(self):
        python=Path(sys.executable).with_name('pythonw.exe')
        if not python.exists(): python=Path(sys.executable)
        return subprocess.list2cmdline([str(python),str(self.base/'app.py'),'--data-dir',str(self.directory),'--port',str(self.port)])
    def status(self):
        if sys.platform!='win32': return {'supported':False,'enabled':False,'message':'当前自动设置仅支持Windows；其他系统请用系统登录项。'}
        try:
            t=self.task('status')
            if t.get('managed'): return {'supported':True,'enabled':t['enabled'],'message':'开机登录后后台启动；每日定时任务保留。'}
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as k:
                    value=winreg.QueryValueEx(k,self.name())[0]
                    enabled=value==self.command()
            except FileNotFoundError: enabled=False
            return {'supported':True,'enabled':enabled,'message':'开机登录后后台运行；移动程序目录后请重新设置。'}
        except (OSError,ValueError,subprocess.SubprocessError): return {'supported':False,'enabled':None,'message':'无法确认自启动状态，请检查当前Windows账户权限。'}
    def set(self, enabled):
        if sys.platform!='win32' or not isinstance(enabled,bool): raise ValueError('当前系统不支持或开关值无效')
        t=self.task('enable' if enabled else 'disable')
        if not t.get('managed'):
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as k:
                if enabled: winreg.SetValueEx(k,self.name(),0,winreg.REG_SZ,self.command())
                else:
                    try: winreg.DeleteValue(k,self.name())
                    except FileNotFoundError: pass
        state=self.status()
        if state['enabled'] is not enabled: raise ValueError('自启动设置未生效；请检查任务是否被系统禁用')
        return state
