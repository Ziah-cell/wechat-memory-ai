param([Parameter(Mandatory=$true)][string]$ClientPath)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$Report = [ordered]@{
    schema_version=1; status='probe_failed'; client_version=''; process_count=0;
    window_count=0; nodes=0; onscreen_nodes=0; control_types=@{}; limited=$false
}

function Invoke-StructuralProbe {
    if (!(Test-Path -LiteralPath $ClientPath -PathType Leaf)) {
        $Report.status = 'client_not_found'; return
    }
    $Client = Get-Item -LiteralPath $ClientPath
    if ($Client.Name -notin @('Weixin.exe','WeChat.exe')) {
        $Report.status = 'invalid_client'; return
    }
    $Version = $Client.VersionInfo.FileVersion
    if ($Version -match '^\d{1,5}\.\d{1,5}\.\d{1,5}\.\d{1,5}$') {
        $Report.client_version = $Version
    }
    $Matching = @()
    foreach ($Process in @(Get-Process -Name $Client.BaseName -ErrorAction SilentlyContinue)) {
        # Match the specified executable, not a window title or nickname.
        try {
            if (![string]::Equals($Process.MainModule.FileName, $Client.FullName,
                                 [StringComparison]::OrdinalIgnoreCase)) { continue }
            $Matching += $Process
        } catch { $Report.status = 'process_unavailable'; return }
    }
    $Report.process_count = $Matching.Count
    if (!$Matching.Count) { $Report.status = 'not_running'; return }
    $Windows = @($Matching | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero })
    $Report.window_count = $Windows.Count
    if (!$Windows.Count) { $Report.status = 'no_window'; return }
    if ($Windows.Count -ne 1) { $Report.status = 'ambiguous_window'; return }
    $Target = $Windows[0]
    $Handle = $Target.MainWindowHandle
    $Started = $Target.StartTime
    try {
        . (Join-Path $PSScriptRoot 'uia_support.ps1')
        $Snapshot = [WechatReadOnly.TreeProbe]::Read($Handle, $Target.Id, 256, 16)
        $Target.Refresh()
        if ($Snapshot.ScopeChanged -or $Target.HasExited -or $Target.MainWindowHandle -ne $Handle -or $Target.StartTime -ne $Started) {
            $Report.status = 'window_changed'; return
        }
        $Report.nodes = $Snapshot.Nodes
        $Report.onscreen_nodes = $Snapshot.OnscreenNodes
        $Report.control_types = $Snapshot.ControlTypes
        $Report.limited = $Snapshot.Limited
        $Report.status = if ($Snapshot.Nodes -gt 1) { 'structure_observed' } else { 'empty_tree' }
    } catch {
        # Never forward provider exception text, window titles or user data.
        $Report.status = 'uia_unavailable'
    }
}

try { Invoke-StructuralProbe } catch { $Report.status = 'probe_failed' }
$Report | ConvertTo-Json -Depth 4 -Compress
