$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ProjectDir\start_daemon.ps1`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable

Register-ScheduledTask `
  -TaskName "AI_Content_AutoPublisher" `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Description "Generate and queue AI new-media content on a dynamic weekly schedule." `
  -Force | Out-Null

Write-Host "task_registered=AI_Content_AutoPublisher"
