# The five selected tab icons reuse the licensed Ant Design glyphs in this folder.
# A solid blue badge keeps the current section obvious on the native WeChat tab bar.
Add-Type -AssemblyName System.Drawing

$iconDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
foreach ($name in @('survey', 'checkin', 'chat', 'book', 'user')) {
    $sourcePath = Join-Path $iconDirectory ($name + '-white.png')
    $outputPath = Join-Path $iconDirectory ($name + '-tab-selected.png')
    $source = [System.Drawing.Image]::FromFile($sourcePath)
    $bitmap = New-Object System.Drawing.Bitmap 96, 96, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $fill = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 23, 105, 166))
        $stroke = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 14, 77, 124)), 2
        try {
            $graphics.FillEllipse($fill, 1, 1, 93, 93)
            $graphics.DrawEllipse($stroke, 1, 1, 93, 93)
            $graphics.DrawImage($source, 13, 13, 70, 70)
        } finally {
            $fill.Dispose()
            $stroke.Dispose()
        }
    } finally {
        $graphics.Dispose()
        $source.Dispose()
    }
    try {
        $bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $bitmap.Dispose()
    }
}
