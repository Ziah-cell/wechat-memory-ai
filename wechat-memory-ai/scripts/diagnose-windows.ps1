param(
    [string]$Config = 'config.toml',
    [string]$Python = $env:WECHAT_MEMORY_PYTHON
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'windows.ps1') -Action diagnose -Config $Config -Python $Python
exit $LASTEXITCODE
# This script does not install, log in, downgrade, or control WeChat.
# Confirm the exact version manually via the client's About page.
