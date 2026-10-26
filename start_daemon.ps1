$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-HasPlaywright($exe) {
    if (-not $exe) { return $false }
    try {
        & $exe -c "import playwright" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-Python {
    $candidates = @()

    $venv = Join-Path $ProjectDir ".venv\Scripts\python.exe"
    if (Test-Path $venv) { $candidates += $venv }

    $managed = Join-Path $env:USERPROFILE ".workbuddy-ai\binaries\python\versions"
    if (Test-Path $managed) {
        $hit = Get-ChildItem -Path $managed -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notlike "*\envs\*" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($hit) { $candidates += $hit.FullName }
    }

    $local = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "Programs\Python") -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($local) { $candidates += $local.FullName }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }

    $fallback = $null
    foreach ($exe in $candidates) {
        if (-not $fallback) { $fallback = $exe }
        # 发布功能依赖 playwright，优先选装了的解释器
        if (Test-HasPlaywright $exe) { return $exe }
    }
    if ($fallback) { return $fallback }

    throw "Python not found. Create a venv in the project or install Python 3.10+."
}

$Python = Resolve-Python
$OutLog = Join-Path $LogDir "daemon.out.log"
$ErrLog = Join-Path $LogDir "daemon.err.log"
$Main = Join-Path $ProjectDir "main.py"

$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*main.py*daemon*" -and $_.CommandLine -like "*$ProjectDir*" }

if ($existing) {
    Write-Host "daemon_already_running=true"
    exit 0
}

Start-Process `
  -FilePath $Python `
  -ArgumentList @("-u", $Main, "daemon") `
  -WorkingDirectory $ProjectDir `
  -WindowStyle Hidden `
  -RedirectStandardOutput $OutLog `
  -RedirectStandardError $ErrLog

Start-Sleep -Seconds 2
Write-Host "started=true"
Write-Host "python=$Python"
Write-Host "logs=$LogDir"
