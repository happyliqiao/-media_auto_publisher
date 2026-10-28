$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ProjectDir "start_daemon.ps1"
$TaskName = "AI_Content_AutoPublisher"

if (-not (Test-Path $ScriptPath)) {
    throw "start_daemon.ps1 not found: $ScriptPath"
}

# 用字符串拼接构造参数，避免嵌套转义引号导致的语法错误
$ActionArg = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $ScriptPath + '"'

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ActionArg

# 触发器 1：登录时启动
$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# 触发器 2：每 30 分钟巡检一次（start_daemon.ps1 自带「已在运行则跳过」判断，
# 相当于看门狗：daemon 崩溃或睡眠唤醒后会在这里被拉起来）
$WatchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 30)

# Interactive：必须能弹出有头浏览器，否则头条发布无法工作
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 0) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($LogonTrigger, $WatchdogTrigger) -Principal $Principal -Settings $Settings -Description "Generate content on schedule and publish to Toutiao while the user is logged in." -Force | Out-Null

Write-Host "task_registered=$TaskName"
Write-Host "script=$ScriptPath"
Write-Host "user=$env:USERNAME"
Write-Host "triggers=AtLogOn + every 30 minutes"
Write-Host "note=interactive logon required so the browser can be shown"
