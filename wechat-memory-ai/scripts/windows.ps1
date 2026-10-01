param(
    [ValidateSet('run','status','pause','resume','stop','diagnose','test','backup','restore','review','probe-wechat')]
    [string]$Action = 'run',
    [string]$Config = 'config.toml',
    [string]$Path = '',
    [string]$Guard = '',
    [switch]$Confirm,
    [string]$ClientPath = '',
    [string]$Python = $env:WECHAT_MEMORY_PYTHON
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $Utf8
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8

# Resolve an actual executable; skip Microsoft Store alias placeholders.
$Candidates = @()
if ($Python) {
    $Candidates += $Python
} else {
    $Candidates += (Join-Path $ProjectRoot '.venv/Scripts/python.exe')
    foreach ($Name in @('py.exe', 'python.exe', 'python3.exe')) {
        $Command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($Command -and $Command.Source -notlike '*\Microsoft\WindowsApps\*') {
            $Candidates += $Command.Source
        }
    }
    if ($env:USERPROFILE) {
        $Candidates += (Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
    }
}
$PythonExe = $null
foreach ($Candidate in $Candidates) {
    $Executable = Get-Command $Candidate -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$Executable) { continue }
    $Prefix = @()
    if ([IO.Path]::GetFileName($Executable.Source) -eq 'py.exe') { $Prefix = @('-3') }
    try {
        $Probe = & $Executable.Source @Prefix -X utf8 -c 'import sys; print(sys.executable); sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null
    } catch {
        # Windows PowerShell 5.1 can turn native stderr into a terminating error.
        # A broken candidate must not prevent trying the next interpreter.
        continue
    }
    if ($LASTEXITCODE -eq 0 -and $Probe) {
        $PythonExe = ([string]($Probe | Select-Object -Last 1)).Trim()
        break
    }
}
if (!$PythonExe) {
    throw 'Python 3.11+ not found. Use -Python with a valid python.exe path or set WECHAT_MEMORY_PYTHON.'
}
Push-Location $ProjectRoot
try {
    if ($Action -eq 'test') {
        & $PythonExe -X utf8 'scripts/test.py'
        exit $LASTEXITCODE
    }
    if ($Action -eq 'probe-wechat') {
        if (!$ClientPath) { throw 'Use -ClientPath with the installed Weixin.exe or WeChat.exe.' }
        & $PythonExe -X utf8 'scripts/probe-wechat.py' --client-path $ClientPath
        exit $LASTEXITCODE
    }
    if (!(Test-Path -LiteralPath $Config)) {
        if ($Config -ne 'config.toml') { throw 'Specified config file does not exist.' }
        Copy-Item -LiteralPath 'config.example.toml' -Destination $Config
    }
    $PythonArgs = @('-X','utf8','scripts/run.py','--config',$Config,$Action)
    if ($Action -eq 'backup' -or $Action -eq 'restore') {
        if (!$Path) { throw 'Use -Path with backup or restore.' }
        $PythonArgs += $Path
    }
    if ($Action -eq 'restore') {
        if ($Guard) { $PythonArgs += @('--guard',$Guard) }
        if ($Confirm) { $PythonArgs += '--confirm' }
    }
    & $PythonExe @PythonArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
