Add-Type -AssemblyName System.Drawing

$outDir = "$env:TEMP\tabbar_icons"
if (!(Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

function Create-Icon {
    param($fileName, $bgR, $bgG, $bgB, $fgR, $fgG, $fgB, $shape)

    $bmp = New-Object System.Drawing.Bitmap(81, 81)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    $bgColor = [System.Drawing.Color]::FromArgb($bgR, $bgG, $bgB)
    $fgColor = [System.Drawing.Color]::FromArgb($fgR, $fgG, $fgB)

    $bgBrush = New-Object System.Drawing.SolidBrush($bgColor)
    $fgBrush = New-Object System.Drawing.SolidBrush($fgColor)
    $pen = New-Object System.Drawing.Pen($fgColor, 2.5)

    $g.FillEllipse($bgBrush, 1, 1, 79, 79)

    switch ($shape) {
        "survey" {
            $g.DrawRectangle($pen, 22, 22, 36, 36)
            $g.DrawLine($pen, 28, 30, 52, 30)
            $g.DrawLine($pen, 28, 38, 48, 38)
            $g.DrawLine($pen, 28, 46, 44, 46)
        }
        "checkin" {
            $g.DrawEllipse($pen, 22, 22, 36, 36)
            $g.DrawLine($pen, 30, 40, 38, 48)
            $g.DrawLine($pen, 38, 48, 52, 32)
        }
        "consult" {
            $g.DrawEllipse($pen, 18, 18, 44, 36)
            $pts = @(
                (New-Object System.Drawing.Point(30, 52)),
                (New-Object System.Drawing.Point(38, 52)),
                (New-Object System.Drawing.Point(30, 60))
            )
            $g.FillPolygon($fgBrush, $pts)
            $g.FillEllipse($fgBrush, 32, 30, 6, 6)
            $g.FillEllipse($fgBrush, 44, 30, 6, 6)
        }
        "science" {
            $g.DrawRectangle($pen, 24, 20, 32, 42)
            $g.DrawLine($pen, 40, 20, 40, 62)
        }
        "mine" {
            $g.FillEllipse($fgBrush, 30, 22, 20, 20)
            $g.FillEllipse($fgBrush, 22, 44, 36, 26)
        }
    }

    $pen.Dispose()
    $fgBrush.Dispose()
    $bgBrush.Dispose()
    $g.Dispose()

    $filePath = Join-Path $outDir $fileName
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $bytes = $ms.ToArray()
    $ms.Dispose()
    $bmp.Dispose()

    [System.IO.File]::WriteAllBytes($filePath, $bytes)
    Write-Host "OK: $fileName"
}

Create-Icon "survey.png" 232 245 240 15 138 101 "survey"
Create-Icon "checkin.png" 254 243 199 245 158 11 "checkin"
Create-Icon "consult.png" 254 226 226 239 68 68 "consult"
Create-Icon "science.png" 219 234 254 59 130 246 "science"
Create-Icon "mine.png" 237 233 254 139 92 246 "mine"
Create-Icon "survey_active.png" 204 232 224 15 138 101 "survey"
Create-Icon "checkin_active.png" 252 231 179 217 119 6 "checkin"
Create-Icon "consult_active.png" 252 202 202 220 38 38 "consult"
Create-Icon "science_active.png" 191 219 254 37 99 235 "science"
Create-Icon "mine_active.png" 221 214 254 124 58 237 "mine"

Write-Host "`nOutput: $outDir"
Write-Host "Done!"
