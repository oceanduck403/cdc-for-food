Add-Type -AssemblyName System.Drawing
[System.Drawing.Bitmap]$bmp = New-Object System.Drawing.Bitmap(81,81)
[System.Drawing.Graphics]$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::White)

# survey - 绿色
[System.Drawing.SolidBrush]$bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(232,245,240))
[System.Drawing.Pen]$pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(15,138,101), 2.5)
$g.FillEllipse($bgBrush, 1, 1, 79, 79)
$g.DrawRectangle($pen, 22, 22, 36, 36)
$g.DrawLine($pen, 28, 30, 52, 30)
$g.DrawLine($pen, 28, 38, 48, 38)
$g.DrawLine($pen, 28, 46, 44, 46)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\survey.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created survey.png"

# checkin - 橙色
$g.Clear([System.Drawing.Color]::White)
$bgBrush.Dispose()
$bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(254,243,199))
$g.FillEllipse($bgBrush, 1, 1, 79, 79)
$g.DrawEllipse($pen, 22, 22, 36, 36)
$g.DrawLine($pen, 30, 40, 38, 48)
$g.DrawLine($pen, 38, 48, 52, 32)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\checkin.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created checkin.png"

# consult - 红色
$g.Clear([System.Drawing.Color]::White)
$bgBrush.Dispose()
$bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(254,226,226))
$g.FillEllipse($bgBrush, 1, 1, 79, 79)
$g.DrawEllipse($pen, 18, 18, 44, 36)
[System.Drawing.SolidBrush]$fgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(239,68,68))
$pts = @((New-Object System.Drawing.Point(30,52)),(New-Object System.Drawing.Point(38,52)),(New-Object System.Drawing.Point(30,60)))
$g.FillPolygon($fgBrush, $pts)
$g.FillEllipse($fgBrush, 32, 30, 6, 6)
$g.FillEllipse($fgBrush, 44, 30, 6, 6)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\consult.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created consult.png"

# science - 蓝色
$g.Clear([System.Drawing.Color]::White)
$bgBrush.Dispose()
$fgBrush.Dispose()
$bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(219,234,254))
$fgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(59,130,246))
$g.FillEllipse($bgBrush, 1, 1, 79, 79)
$g.DrawRectangle($pen, 24, 20, 32, 42)
$g.DrawLine($pen, 40, 20, 40, 62)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\science.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created science.png"

# mine - 紫色
$g.Clear([System.Drawing.Color]::White)
$bgBrush.Dispose()
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(237,233,254))), 1, 1, 79, 79)
$g.FillEllipse($fgBrush, 30, 22, 20, 20)
$g.FillEllipse($fgBrush, 22, 44, 36, 26)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\mine.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created mine.png"

# Active versions (darker background)
# survey_active
$g.Clear([System.Drawing.Color]::White)
$bgBrush.Dispose()
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(204,232,224))), 1, 1, 79, 79)
$g.DrawRectangle($pen, 22, 22, 36, 36)
$g.DrawLine($pen, 28, 30, 52, 30)
$g.DrawLine($pen, 28, 38, 48, 38)
$g.DrawLine($pen, 28, 46, 44, 46)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\survey_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created survey_active.png"

# checkin_active
$g.Clear([System.Drawing.Color]::White)
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(252,231,179))), 1, 1, 79, 79)
$g.DrawEllipse($pen, 22, 22, 36, 36)
$g.DrawLine($pen, 30, 40, 38, 48)
$g.DrawLine($pen, 38, 48, 52, 32)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\checkin_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created checkin_active.png"

# consult_active
$g.Clear([System.Drawing.Color]::White)
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(252,202,202))), 1, 1, 79, 79)
$g.DrawEllipse($pen, 18, 18, 44, 36)
$g.FillPolygon((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(220,38,38))), @((New-Object System.Drawing.Point(30,52)),(New-Object System.Drawing.Point(38,52)),(New-Object System.Drawing.Point(30,60))))
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(220,38,38))), 32, 30, 6, 6)
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(220,38,38))), 44, 30, 6, 6)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\consult_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created consult_active.png"

# science_active
$g.Clear([System.Drawing.Color]::White)
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(191,219,254))), 1, 1, 79, 79)
$g.DrawRectangle($pen, 24, 20, 32, 42)
$g.DrawLine($pen, 40, 20, 40, 62)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\science_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created science_active.png"

# mine_active
$g.Clear([System.Drawing.Color]::White)
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(221,214,254))), 1, 1, 79, 79)
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(124,58,237))), 30, 22, 20, 20)
$g.FillEllipse((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(124,58,237))), 22, 44, 36, 26)
$bmp.Save("C:\Users\31911\Desktop\疾控\miniprogram\images\mine_active.png", [System.Drawing.Imaging.ImageFormat]::Png)
Write-Host "Created mine_active.png"

$g.Dispose()
$bmp.Dispose()
$pen.Dispose()
$bgBrush.Dispose()
$fgBrush.Dispose()
Write-Host "All done!"
