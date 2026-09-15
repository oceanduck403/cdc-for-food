$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$outDir = "C:\Users\31911\Desktop\疾控\miniprogram\images"

$icons = @(
    @{Name="survey"; Color=([System.Drawing.ColorTranslator]::FromHtml("#0F8A65")); Bg=([System.Drawing.ColorTranslator]::FromHtml("#E8F5F0"))},
    @{Name="checkin"; Color=([System.Drawing.ColorTranslator]::FromHtml("#F59E0B")); Bg=([System.Drawing.ColorTranslator]::FromHtml("#FEF3C7"))},
    @{Name="consult"; Color=([System.Drawing.ColorTranslator]::FromHtml("#EF4444")); Bg=([System.Drawing.ColorTranslator]::FromHtml("#FEE2E2"))},
    @{Name="science"; Color=([System.Drawing.ColorTranslator]::FromHtml("#3B82F6")); Bg=([System.Drawing.ColorTranslator]::FromHtml("#DBEAFE"))},
    @{Name="mine"; Color=([System.Drawing.ColorTranslator]::FromHtml("#8B5CF6")); Bg=([System.Drawing.ColorTranslator]::FromHtml("#EDE9FE"))}
)

function Draw-Survey($g, $color) {
    $pen = New-Object System.Drawing.Pen($color, 2.5)
    $g.DrawRectangle($pen, 22, 22, 36, 36)
    $g.DrawLine($pen, 28, 30, 52, 30)
    $g.DrawLine($pen, 28, 38, 48, 38)
    $g.DrawLine($pen, 28, 46, 44, 46)
    $pen.Dispose()
}

function Draw-Checkin($g, $color) {
    $pen = New-Object System.Drawing.Pen($color, 2.5)
    $g.DrawEllipse($pen, 22, 22, 36, 36)
    $g.DrawLine($pen, 30, 40, 38, 48)
    $g.DrawLine($pen, 38, 48, 52, 32)
    $pen.Dispose()
}

function Draw-Consult($g, $color) {
    $pen = New-Object System.Drawing.Pen($color, 2.5)
    $g.DrawEllipse($pen, 18, 18, 44, 36)
    $brush = New-Object System.Drawing.SolidBrush($color)
    $points = @(
        (New-Object System.Drawing.Point(30, 52)),
        (New-Object System.Drawing.Point(38, 52)),
        (New-Object System.Drawing.Point(30, 60))
    )
    $g.FillPolygon($brush, $points)
    $brush.Dispose()
    $pen.Dispose()
}

function Draw-Science($g, $color) {
    $pen = New-Object System.Drawing.Pen($color, 2.5)
    $g.DrawRectangle($pen, 24, 20, 32, 40)
    $g.DrawLine($pen, 40, 20, 40, 60)
    $font = New-Object System.Drawing.Font("Arial", 10)
    $brush = New-Object System.Drawing.SolidBrush($color)
    $g.DrawString("A", $font, $brush, 28, 28)
    $g.DrawString("B", $font, $brush, 44, 28)
    $font.Dispose()
    $brush.Dispose()
    $pen.Dispose()
}

function Draw-Mine($g, $color) {
    $brush = New-Object System.Drawing.SolidBrush($color)
    $g.FillEllipse($brush, 30, 22, 20, 20)
    $g.FillEllipse($brush, 22, 44, 36, 26)
    $brush.Dispose()
}

function Save-Icon($icon, $darkBg) {
    $bmp = New-Object System.Drawing.Bitmap(81, 81)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::White)

    $bgBrush = New-Object System.Drawing.SolidBrush($darkBg)
    $g.FillEllipse($bgBrush, 1, 1, 79, 79)

    switch ($icon.Name) {
        "survey" { Draw-Survey $g $icon.Color }
        "checkin" { Draw-Checkin $g $icon.Color }
        "consult" { Draw-Consult $g $icon.Color }
        "science" { Draw-Science $g $icon.Color }
        "mine" { Draw-Mine $g $icon.Color }
    }

    $g.Dispose()
    $bgBrush.Dispose()
    return $bmp
}

foreach ($icon in $icons) {
    try {
        $bmp1 = Save-Icon $icon $icon.Bg
        $path1 = Join-Path $outDir "$($icon.Name).png"
        $bmp1.Save($path1, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp1.Dispose()
        Write-Host "OK: $path1"
    }
    catch {
        Write-Host "Error saving $($icon.Name).png: $_"
    }

    try {
        $darkBg = New-Object System.Drawing.ColorConverter
        $bmp2 = Save-Icon $icon $icon.Bg
        $path2 = Join-Path $outDir "$($icon.Name)_active.png"
        $bmp2.Save($path2, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp2.Dispose()
        Write-Host "OK: $path2"
    }
    catch {
        Write-Host "Error saving $($icon.Name)_active.png: $_"
    }
}

Write-Host "Done!"
