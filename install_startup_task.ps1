$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ProjectDir\start_daemon.ps1`"

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Interactive 模式：必须能弹出有头浏览器，否则头条发布无法工作
$Principal = New-ScheduledTaskPrincipal `
  -UserId $env:USERNAME `
  -LogonType Interactive `
  -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
  -MultipleInstances IgnoreNew

Register-ScheduledTask `
  -TaskName "AI_Content_AutoPublisher" `
  -Action $Action `
  -Trigger $Trigger `
  -Principal $Principal `
  -Settings $Settings `
  -Description "Generate content on schedule and publish to Toutiao while the user is logged in." `
  -Force | Out-Null

Write-Host "task_registered=AI_Content_AutoPublisher"
Write-Host "user=$env:USERNAME"
Write-Host "note=interactive logon required so the browser can be shown"
