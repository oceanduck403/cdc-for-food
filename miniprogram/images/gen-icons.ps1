Add-Type -AssemblyName System.Drawing

$iconDir = "C:\Users\31911\Desktop\疾控\miniprogram\images"

$icons = @(
    @{Name="survey"; Color="#0F8A65"; Bg="#E8F5F0"},
    @{Name="checkin"; Color="#F59E0B"; Bg="#FEF3C7"},
    @{Name="consult"; Color="#EF4444"; Bg="#FEE2E2"},
    @{Name="science"; Color="#3B82F6"; Bg="#DBEAFE"},
    @{Name="mine"; Color="#8B5CF6"; Bg="#EDE9FE"}
)

foreach ($icon in $icons) {
    $bmp = New-Object System.Drawing.Bitmap(81, 81)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    $bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($icon.Bg))
    $colorBrush = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($icon.Color))
    $pen = New-Object System.Drawing.Pen($colorBrush, 3)

    $g.FillEllipse($bgBrush, 1, 1, 79, 79)

    if ($icon.Name -eq "survey") {
        $g.DrawRectangle($pen, 22, 22, 36, 36)
        $g.DrawLine($pen, 28, 30, 52, 30)
        $g.DrawLine($pen, 28, 38, 48, 38)
        $g.DrawLine($pen, 28, 46, 44, 46)
    }
    elseif ($icon.Name -eq "checkin") {
        $g.DrawEllipse($pen, 22, 22, 36, 36)
        $g.DrawLine($pen, 30, 40, 38, 48)
        $g.DrawLine($pen, 38, 48, 52, 32)
    }
    elseif ($icon.Name -eq "consult") {
        $g.DrawEllipse($pen, 18, 18, 44, 36)
        $point1 = New-Object System.Drawing.Point(30, 52)
        $point2 = New-Object System.Drawing.Point(38, 52)
        $point3 = New-Object System.Drawing.Point(30, 60)
        $g.FillPolygon($colorBrush, @($point1, $point2, $point3))
    }
    elseif ($icon.Name -eq "science") {
        $g.DrawRectangle($pen, 24, 20, 32, 40)
        $g.DrawLine($pen, 40, 20, 40, 60)
        $g.DrawLine($pen, 28, 28, 36, 28)
        $g.DrawLine($pen, 44, 28, 52, 28)
    }
    elseif ($icon.Name -eq "mine") {
        $g.FillEllipse($colorBrush, 30, 22, 20, 20)
        $g.FillEllipse($colorBrush, 22, 44, 36, 26)
    }

    $normalPath = Join-Path $iconDir "$($icon.Name).png"
    $bmp.Save($normalPath, [System.Drawing.Imaging.ImageFormat]::PNG)

    $g.Clear([System.Drawing.Color]::White)
    $darkerBg = $icon.Bg -replace "^#", "#CC"
    $bgBrush2 = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($darkerBg))
    $g.FillEllipse($bgBrush2, 1, 1, 79, 79)

    if ($icon.Name -eq "survey") {
        $g.DrawRectangle($pen, 22, 22, 36, 36)
        $g.DrawLine($pen, 28, 30, 52, 30)
        $g.DrawLine($pen, 28, 38, 48, 38)
        $g.DrawLine($pen, 28, 46, 44, 46)
    }
    elseif ($icon.Name -eq "checkin") {
        $g.DrawEllipse($pen, 22, 22, 36, 36)
        $g.DrawLine($pen, 30, 40, 38, 48)
        $g.DrawLine($pen, 38, 48, 52, 32)
    }
    elseif ($icon.Name -eq "consult") {
        $g.DrawEllipse($pen, 18, 18, 44, 36)
        $point1 = New-Object System.Drawing.Point(30, 52)
        $point2 = New-Object System.Drawing.Point(38, 52)
        $point3 = New-Object System.Drawing.Point(30, 60)
        $g.FillPolygon($colorBrush, @($point1, $point2, $point3))
    }
    elseif ($icon.Name -eq "science") {
        $g.DrawRectangle($pen, 24, 20, 32, 40)
        $g.DrawLine($pen, 40, 20, 40, 60)
        $g.DrawLine($pen, 28, 28, 36, 28)
        $g.DrawLine($pen, 44, 28, 52, 28)
    }
    elseif ($icon.Name -eq "mine") {
        $g.FillEllipse($colorBrush, 30, 22, 20, 20)
        $g.FillEllipse($colorBrush, 22, 44, 36, 26)
    }

    $activePath = Join-Path $iconDir "$($icon.Name)_active.png"
    $bmp.Save($activePath, [System.Drawing.Imaging.ImageFormat]::PNG)

    Write-Host "OK: $($icon.Name).png"

    $g.Dispose()
    $bmp.Dispose()
    $pen.Dispose()
    $bgBrush.Dispose()
    $bgBrush2.Dispose()
    $colorBrush.Dispose()
}

Write-Host "All done!"
