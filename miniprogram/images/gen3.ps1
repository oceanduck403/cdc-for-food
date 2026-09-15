$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$outDir = "C:\Users\31911\Desktop\疾控\miniprogram\images"

function New-TabBarIcon {
    param($name, $bgColor, $fgColor, $drawFunc)

    $bmp = New-Object System.Drawing.Bitmap(81, 81)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic

    # 背景
    $bgBrush = New-Object System.Drawing.SolidBrush($bgColor)
    $g.FillEllipse($bgBrush, 0, 0, 80, 80)

    # 绘制图标
    &$drawFunc] $g $fgColor

    $g.Dispose()
    $bgBrush.Dispose()

    return $bmp
}

# 1. checkin 图标
$bmp = New-TabBarIcon "checkin" ([System.Drawing.Color]::FromArgb(254,243,199)) ([System.Drawing.Color]::FromArgb(245,158,11)) {
    param($g, $c)
    $pen = New-Object System.Drawing.Pen($c, 3)
    $g.DrawEllipse($pen, 22, 22, 36, 36)
    $g.DrawLine($pen, 30, 40, 38, 48)
    $g.DrawLine($pen, 38, 48, 52, 32)
    $pen.Dispose()
}
$bmp.Save("$outDir\checkin.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "OK: checkin.png"

# 2. consult 图标
$bmp = New-TabBarIcon "consult" ([System.Drawing.Color]::FromArgb(254,226,226)) ([System.Drawing.Color]::FromArgb(239,68,68)) {
    param($g, $c)
    $pen = New-Object System.Drawing.Pen($c, 2.5)
    $g.DrawEllipse($pen, 18, 18, 44, 36)
    $brush = New-Object System.Drawing.SolidBrush($c)
    $g.FillPolygon($brush, @((New-Object System.Drawing.Point(30,52)), (New-Object System.Drawing.Point(38,52)), (New-Object System.Drawing.Point(30,60))))
    $g.FillEllipse($brush, 32, 30, 6, 6)
    $g.FillEllipse($brush, 44, 30, 6, 6)
    $pen.Dispose()
    $brush.Dispose()
}
$bmp.Save("$outDir\consult.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "OK: consult.png"

# 3. science 图标
$bmp = New-TabBarIcon "science" ([System.Drawing.Color]::FromArgb(219,234,254)) ([System.Drawing.Color]::FromArgb(59,130,246)) {
    param($g, $c)
    $pen = New-Object System.Drawing.Pen($c, 2.5)
    $g.DrawRectangle($pen, 24, 20, 32, 42)
    $g.DrawLine($pen, 40, 20, 40, 62)
    $pen.Dispose()
}
$bmp.Save("$outDir\science.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "OK: science.png"

# 4. survey_active 图标
$bmp = New-TabBarIcon "survey_active" ([System.Drawing.Color]::FromArgb(204,232,224)) ([System.Drawing.Color]::FromArgb(15,138,101)) {
    param($g, $c)
    $pen = New-Object System.Drawing.Pen($c, 2.5)
    $g.DrawRectangle($pen, 22, 22, 36, 36)
    $g.DrawLine($pen, 28, 30, 52, 30)
    $g.DrawLine($pen, 28, 38, 48, 38)
    $g.DrawLine($pen, 28, 46, 44, 46)
    $pen.Dispose()
}
$bmp.Save("$outDir\survey_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "OK: survey_active.png"

# 5. checkin_active 图标
$bmp = New-TabBarIcon "checkin_active" ([System.Drawing.Color]::FromArgb(252,231,179)) ([System.Drawing.Color]::FromArgb(217,119,6)) {
    param($g, $c)
    $pen = New-Object System.Drawing.Pen($c, 3)
    $g.DrawEllipse($pen, 22, 22, 36, 36)
    $g.DrawLine($pen, 30, 40, 38, 48)
    $g.DrawLine($pen, 38, 48, 52, 32)
    $pen.Dispose()
}
$bmp.Save("$outDir\checkin_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "OK: checkin_active.png"

# 6. consult_active 图标
$bmp = New-TabBarIcon "consult_active" ([System.Drawing.Color]::FromArgb(252,202,202)) ([System.Drawing.Color]::FromArgb(220,38,38)) {
    param($g, $c)
    $pen = New-Object System.Drawing.Pen($c, 2.5)
    $g.DrawEllipse($pen, 18, 18, 44, 36)
    $brush = New-Object System.Drawing.SolidBrush($c)
    $g.FillPolygon($brush, @((New-Object System.Drawing.Point(30,52)), (New-Object System.Drawing.Point(38,52)), (New-Object System.Drawing.Point(30,60))))
    $g.FillEllipse($brush, 32, 30, 6, 6)
    $g.FillEllipse($brush, 44, 30, 6, 6)
    $pen.Dispose()
    $brush.Dispose()
}
$bmp.Save("$outDir\consult_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "OK: consult_active.png"

# 7. science_active 图标
$bmp = New-TabBarIcon "science_active" ([System.Drawing.Color]::FromArgb(191,219,254)) ([System.Drawing.Color]::FromArgb(37,99,235)) {
    param($g, $c)
    $pen = New-Object System.Drawing.Pen($c, 2.5)
    $g.DrawRectangle($pen, 24, 20, 32, 42)
    $g.DrawLine($pen, 40, 20, 40, 62)
    $pen.Dispose()
}
$bmp.Save("$outDir\science_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "OK: science_active.png"

Write-Host "All done!"
