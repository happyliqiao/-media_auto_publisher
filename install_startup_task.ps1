$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Main = Join-Path $ProjectDir "main.py"
$TaskName = "AI_Content_AutoPublisher"

if (-not (Test-Path -LiteralPath $Main)) {
    throw "main.py not found: $Main"
}

function Test-HasPlaywright([string]$Exe) {
    if (-not $Exe) { return $false }
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    try {
        & $Exe -c "import playwright" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

# 找一个装了 playwright 的解释器：发布环节依赖它，选错会导致静默跳过发布
$candidates = New-Object System.Collections.Generic.List[string]

$venv = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venv) { $candidates.Add($venv) }

foreach ($ver in @('314', '313', '312', '311', '310')) {
    $p = Join-Path $env:LOCALAPPDATA ("Programs\Python\Python" + $ver + "\python.exe")
    if (Test-Path -LiteralPath $p) { $candidates.Add($p) }
}

$managedRoot = Join-Path $env:USERPROFILE ".workbuddy-ai\binaries\python\versions"
if (Test-Path -LiteralPath $managedRoot) {
    foreach ($ver in @('3.13.12', '3.13.13', '3.12')) {
        $p = Join-Path $managedRoot ($ver + "\python.exe")
        if (Test-Path -LiteralPath $p) { $candidates.Add($p) }
    }
}

$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd -and $cmd.Source) { $candidates.Add($cmd.Source) }

$Python = $null
foreach ($exe in $candidates) {
    if (Test-HasPlaywright $exe) { $Python = $exe; break }
}
if (-not $Python) {
    foreach ($exe in $candidates) {
        if (Test-Path -LiteralPath $exe) { $Python = $exe; break }
    }
}
if (-not $Python) { throw "Python interpreter not found" }

# 优先用 pythonw.exe：daemon 不需要控制台窗口，日志由 main.py 自己写文件
$Pythonw = Join-Path (Split-Path -Parent $Python) "pythonw.exe"
$Execute = if (Test-Path -LiteralPath $Pythonw) { $Pythonw } else { $Python }

# 参数用拼接构造，避免嵌套转义引号（这里踩过一次坑）
$ActionArg = '-u "' + $Main + '" daemon'

$Action = New-ScheduledTaskAction -Execute $Execute -Argument $ActionArg -WorkingDirectory $ProjectDir

$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$WatchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 30)

# Interactive：必须能弹出有头浏览器，否则头条发布无法工作
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 0) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($LogonTrigger, $WatchdogTrigger) -Principal $Principal -Settings $Settings -Description "Generate content on schedule and publish to Toutiao while the user is logged in." -Force | Out-Null

Write-Host "task_registered=$TaskName"
Write-Host "execute=$Execute"
Write-Host "arguments=$ActionArg"
Write-Host "working_dir=$ProjectDir"
Write-Host "triggers=AtLogOn + every 30 minutes"
Write-Host "note=interactive logon required so the browser can be shown"
