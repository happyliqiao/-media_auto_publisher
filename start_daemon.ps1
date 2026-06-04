$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "python"
$LogDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$OutLog = Join-Path $LogDir "daemon.out.log"
$ErrLog = Join-Path $LogDir "daemon.err.log"
$Main = Join-Path $ProjectDir "main.py"

Start-Process `
  -FilePath $Python `
  -ArgumentList @($Main, "daemon") `
  -WorkingDirectory $ProjectDir `
  -WindowStyle Hidden `
  -RedirectStandardOutput $OutLog `
  -RedirectStandardError $ErrLog

Write-Host "started=true"
Write-Host "logs=$LogDir"
