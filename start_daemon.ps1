$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LaunchLog = Join-Path $LogDir "launcher.log"

function Write-LaunchLog([string]$Message) {
    try {
        $line = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss") + "  " + $Message
        Add-Content -Path $LaunchLog -Value $line -Encoding UTF8
    } catch {
        # 日志失败不能影响启动
    }
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

try {
    # 这台机器的环境里同时存在 http_proxy 与 HTTP_PROXY（大小写各一份），
    # PowerShell 的环境变量提供程序会因此抛「已添加了具有相同键的项」，
    # 连带 Start-Process 等 cmdlet 一起失败。这里只清理指向本机回环的代理，
    # 避免把正常的公司代理也误删。
    foreach ($name in @('http_proxy', 'https_proxy', 'all_proxy')) {
        try {
            $value = [System.Environment]::GetEnvironmentVariable($name)
            if ($value -and ($value -match '127\.0\.0\.1|localhost')) {
                [System.Environment]::SetEnvironmentVariable($name, $null)
                [System.Environment]::SetEnvironmentVariable($name.ToUpper(), $null)
                Write-LaunchLog ("cleared_loopback_proxy=" + $name + " value=" + $value)
            }
        } catch {
        }
    }

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

    $Main = Join-Path $ProjectDir "main.py"
    if (-not (Test-Path -LiteralPath $Main)) { throw "main.py not found: $Main" }

    # 用 .NET 直接启动子进程：Start-Process 在环境变量存在大小写重复键时会抛
    # ArgumentException，导致启动环节彻底失败。daemon 的日志由 main.py 自己写。
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Python
    $psi.Arguments = '-u "' + $Main + '" daemon'
    $psi.WorkingDirectory = $ProjectDir
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::Start($psi)

    Write-LaunchLog ("started pid=" + $proc.Id + " python=" + $Python)
    Write-Host ("started=true pid=" + $proc.Id)
    Write-Host ("python=" + $Python)
    Write-Host ("logs=" + $LogDir)
} catch {
    Write-LaunchLog ("failed: " + $_.Exception.Message)
    Write-Host ("launcher_failed=" + $_.Exception.Message)
    exit 1
}
