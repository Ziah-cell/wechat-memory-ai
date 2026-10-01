# ASCII source for Windows PowerShell 5.1. All pixels/text are generated here.
# No screenshot, window access, input image, file storage, network or configuration.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$Report = [ordered]@{
    schema_version=1; status='ocr_unavailable'; chinese_available=$false
    checks=[ordered]@{}
}
foreach ($Style in @('light','dark','large')) {
    $Report.checks[$Style] = [ordered]@{chinese_duplicates_match=$false; latin_exact_match=$false; line_count_match=$false}
}

function Await-Ocr($Operation, [Type]$ResultType) {
    $Task = $script:AsTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    if (!$Task.Wait(5000)) { throw 'operation_timeout' }
    return $Task.Result
}

function Test-SyntheticPixels($Engine, [string]$Style) {
    $Bitmap = $null; $Graphics = $null; $Font = $null; $SoftwareBitmap = $null
    $TextBrush = $null; $BubbleBrush = $null; $OutgoingBrush = $null; $Locked = $null
    try {
        $Width = 960; $Height = 300
        $Bitmap = [Drawing.Bitmap]::new($Width, $Height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $Graphics = [Drawing.Graphics]::FromImage($Bitmap)
        $Dark = $Style -eq 'dark'
        $Background = if ($Dark) { [Drawing.Color]::FromArgb(25,25,25) } else { [Drawing.Color]::White }
        $Foreground = if ($Dark) { [Drawing.Color]::White } else { [Drawing.Color]::Black }
        $Bubble = if ($Dark) { [Drawing.Color]::FromArgb(55,55,55) } else { [Drawing.Color]::FromArgb(235,235,235) }
        $Outgoing = if ($Dark) { [Drawing.Color]::FromArgb(20,75,40) } else { [Drawing.Color]::FromArgb(170,230,150) }
        $Graphics.Clear($Background)
        $Graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAliasGridFit
        $Size = if ($Style -eq 'large') { 32 } else { 24 }
        $Font = [Drawing.Font]::new('Microsoft YaHei', $Size, [Drawing.FontStyle]::Regular, [Drawing.GraphicsUnit]::Pixel)
        $TextBrush = [Drawing.SolidBrush]::new($Foreground)
        $BubbleBrush = [Drawing.SolidBrush]::new($Bubble)
        $OutgoingBrush = [Drawing.SolidBrush]::new($Outgoing)
        # Fixed fictional line: Chinese test / received / hello. Repeated twice.
        $Chinese = [Regex]::Unescape('\u4e2d\u6587\u6d4b\u8bd5\u6536\u5230\u4f60\u597d')
        $Latin = 'TEST12345'
        $Graphics.FillRectangle($BubbleBrush, 20, 15, 410, 65)
        $Graphics.FillRectangle($BubbleBrush, 20, 105, 410, 65)
        $Graphics.FillRectangle($OutgoingBrush, 570, 195, 360, 65)
        $Graphics.DrawString($Chinese, $Font, $TextBrush, [single]35, [single]25)
        $Graphics.DrawString($Chinese, $Font, $TextBrush, [single]35, [single]115)
        $Graphics.DrawString($Latin, $Font, $TextBrush, [single]590, [single]205)
        $Graphics.Flush()
        $Rectangle = [Drawing.Rectangle]::new(0, 0, $Width, $Height)
        $Locked = $Bitmap.LockBits($Rectangle, [Drawing.Imaging.ImageLockMode]::ReadOnly, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
        if ($Locked.Stride -ne $Width*4) { throw 'unexpected_stride' }
        $Bytes = New-Object byte[] ($Width*$Height*4)
        [Runtime.InteropServices.Marshal]::Copy($Locked.Scan0, $Bytes, 0, $Bytes.Length)
        $Bitmap.UnlockBits($Locked); $Locked = $null
        $Buffer = [Runtime.InteropServices.WindowsRuntime.WindowsRuntimeBufferExtensions]::AsBuffer($Bytes)
        $SoftwareBitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::CreateCopyFromBuffer(
            $Buffer, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, $Width, $Height,
            [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore)
        $Result = Await-Ocr ($Engine.RecognizeAsync($SoftwareBitmap)) ([Windows.Media.Ocr.OcrResult])
        $Lines = @($Result.Lines | ForEach-Object { $_.Text -replace '\s', '' })
        # Compare text only within this synthetic check. No recognized text is emitted.
        return [ordered]@{
            chinese_duplicates_match=(@($Lines | Where-Object { $_ -ceq $Chinese }).Count -eq 2)
            latin_exact_match=(@($Lines | Where-Object { $_ -ceq $Latin }).Count -eq 1)
            line_count_match=($Lines.Count -eq 3)
        }
    } finally {
        if ($Locked -and $Bitmap) { $Bitmap.UnlockBits($Locked) }
        foreach ($Resource in @($SoftwareBitmap, $Graphics, $Font, $TextBrush, $BubbleBrush, $OutgoingBrush, $Bitmap)) {
            if ($null -ne $Resource) { $Resource.Dispose() }
        }
    }
}

try {
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [void][Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
    [void][Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
    [void][Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime]
    [void][Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType=WindowsRuntime]
    [void][Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Foundation, ContentType=WindowsRuntime]
    [void][Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Foundation, ContentType=WindowsRuntime]
    $script:AsTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $Language = [Windows.Globalization.Language]::new('zh-Hans')
    if (![Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($Language)) {
        $Report.status = 'language_unavailable'
    } else {
        $Engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($Language)
        if ($null -eq $Engine) { throw 'engine_unavailable' }
        $Report.chinese_available = $true
        foreach ($Style in @('light','dark','large')) {
            $Report.checks[$Style] = Test-SyntheticPixels $Engine $Style
        }
        $Failures = @($Report.checks.Values | ForEach-Object { $_.Values } | Where-Object { !$_ })
        $Report.status = if ($Failures.Count -eq 0) { 'passed' } else { 'recognition_mismatch' }
    }
} catch {
    # Never expose native exception messages, local paths or recognized text.
    $Report.status = 'ocr_unavailable'; $Report.chinese_available = $false
    foreach ($Fields in $Report.checks.Values) {
        foreach ($Key in @($Fields.Keys)) { $Fields[$Key] = $false }
    }
}
$Report | ConvertTo-Json -Depth 4 -Compress
