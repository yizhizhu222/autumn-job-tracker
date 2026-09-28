param(
  [string]$RuntimeRoot = "$PSScriptRoot/runtime",
  [string]$ModelRoot = "$PSScriptRoot/models",
  [string]$Model = 'qwen3:4b',
  [switch]$DownloadModel
)
$ErrorActionPreference = 'Stop'
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExe = if (Test-Path -LiteralPath "$RuntimeRoot/ollama.exe") { "$RuntimeRoot/ollama.exe" } elseif ($ollamaCommand) { $ollamaCommand.Source } else { throw 'Install Ollama from https://ollama.com/download/windows or extract its official portable ZIP into runtime/.' }
New-Item -ItemType Directory -Path $ModelRoot -Force | Out-Null
$env:OLLAMA_MODELS = [IO.Path]::GetFullPath($ModelRoot)
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_VULKAN = '1'
try { $null=Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 } catch {
  Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden
  for ($attempt=0; $attempt -lt 20; $attempt++) {
    try { $null=Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2; break } catch { Start-Sleep -Seconds 1 }
  }
}
if ($DownloadModel) { & $ollamaExe pull $Model; if($LASTEXITCODE -ne 0) { throw 'Model download failed; run this command again to resume.' } }
(Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3).models | Select-Object name,size
