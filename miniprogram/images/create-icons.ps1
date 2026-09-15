# 生成 TabBar PNG 图标
# 使用 .NET C# 生成简单图标

$iconDir = "C:\Users\31911\Desktop\疾控\miniprogram\images"

# 图标配置
$icons = @(
    @{ Name = "survey"; Label = "调查评估"; Color = "#0F8A65"; Bg = "#E8F5F0" },
    @{ Name = "checkin"; Label = "打卡指导"; Color = "#F59E0B"; Bg = "#FEF3C7" },
    @{ Name = "consult"; Label = "免费咨询"; Color = "#EF4444"; Bg = "#FEE2E2" },
    @{ Name = "science"; Label = "科普互动"; Color = "#3B82F6"; Bg = "#DBEAFE" },
    @{ Name = "mine"; Label = "我的"; Color = "#8B5CF6"; Bg = "#EDE9FE" }
)

Add-Type -AssemblyName System.Drawing

foreach ($icon in $icons) {
    $bmp = New-Object System.Drawing.Bitmap(81, 81)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'

    # 背景圆
    $bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($icon.Bg))
    $g.FillEllipse($bgBrush, 0, 0, 80, 80)

    # 绘制图标符号
    $fgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($icon.Color))
    $font = New-Object System.Drawing.Font("Arial", 28, [System.Drawing.FontStyle]::Bold)

    # 根据名称绘制不同符号
    switch ($icon.Name) {
        "survey" {
            # 绘制问卷符号
            $pen = New-Object System.Drawing.Pen($fgBrush, 3)
            $g.DrawRectangle($pen, 22, 20, 36, 40)
            $g.DrawLine($pen, 28, 32, 52, 32)
            $g.DrawLine($pen, 28, 40, 48, 40)
            $g.DrawLine($pen, 28, 48, 44, 48)
        }
        "checkin" {
            # 绘制勾选符号
            $pen = New-Object System.Drawing.Pen($fgBrush, 4)
            $g.DrawEllipse($pen, 22, 22, 36, 36)
            $g.DrawLine($pen, 30, 40, 38, 48)
            $g.DrawLine($pen, 38, 48, 52, 32)
        }
        "consult" {
            # 绘制消息气泡
            $pen = New-Object System.Drawing.Pen($fgBrush, 3)
            $g.DrawEllipse($pen, 18, 18, 44, 36)
            $g.FillPolygon($fgBrush, @(
                (New-Object System.Drawing.Point(30, 52)),
                (New-Object System.Drawing.Point(38, 52)),
                (New-Object System.Drawing.Point(30, 62))
            ))
        }
        "science" {
            # 绘制书本符号
            $pen = New-Object System.Drawing.Pen($fgBrush, 3)
            $g.DrawRectangle($pen, 24, 20, 32, 42)
            $g.DrawLine($pen, 40, 20, 40, 62)
            $g.DrawLine($pen, 28, 28, 36, 28)
            $g.DrawLine($pen, 44, 28, 52, 28)
        }
        "mine" {
            # 绘制人物符号
            $g.FillEllipse($fgBrush, 30, 22, 20, 20)
            $g.FillEllipse($fgBrush, 22, 44, 36, 26)
        }
    }

    $normalPath = Join-Path $iconDir "$($icon.Name).png"
    $bmp.Save($normalPath, [System.Drawing.Imaging.ImageFormat]::Png)

    # 深色版本（选中状态）
    $darkerBg = $icon.Bg -replace '#', '#1a'
    $bgBrush2 = New-Object System.Drawing.SolidBrush([System.Drawing.ColorTranslator]::FromHtml($darkerBg))
    $g.Clear([System.Drawing.Color]::White)
    $g.FillEllipse($bgBrush2, 0, 0, 80, 80)

    switch ($icon.Name) {
        "survey" {
            $pen = New-Object System.Drawing.Pen($fgBrush, 3)
            $g.DrawRectangle($pen, 22, 20, 36, 40)
            $g.DrawLine($pen, 28, 32, 52, 32)
            $g.DrawLine($pen, 28, 40, 48, 40)
            $g.DrawLine($pen, 28, 48, 44, 48)
        }
        "checkin" {
            $pen = New-Object System.Drawing.Pen($fgBrush, 4)
            $g.DrawEllipse($pen, 22, 22, 36, 36)
            $g.DrawLine($pen, 30, 40, 38, 48)
            $g.DrawLine($pen, 38, 48, 52, 32)
        }
        "consult" {
            $pen = New-Object System.Drawing.Pen($fgBrush, 3)
            $g.DrawEllipse($pen, 18, 18, 44, 36)
            $g.FillPolygon($fgBrush, @(
                (New-Object System.Drawing.Point(30, 52)),
                (New-Object System.Drawing.Point(38, 52)),
                (New-Object System.Drawing.Point(30, 62))
            ))
        }
        "science" {
            $pen = New-Object System.Drawing.Pen($fgBrush, 3)
            $g.DrawRectangle($pen, 24, 20, 32, 42)
            $g.DrawLine($pen, 40, 20, 40, 62)
            $g.DrawLine($pen, 28, 28, 36, 28)
            $g.DrawLine($pen, 44, 28, 52, 28)
        }
        "mine" {
            $g.FillEllipse($fgBrush, 30, 22, 20, 20)
            $g.FillEllipse($fgBrush, 22, 44, 36, 26)
        }
    }

    $activePath = Join-Path $iconDir "$($icon.Name)_active.png"
    $bmp.Save($activePath, [System.Drawing.Imaging.ImageFormat]::Png)

    Write-Host "✓ 生成: $($icon.Name).png 和 $($icon.Name)_active.png"

    $g.Dispose()
    $bmp.Dispose()
}

Write-Host "`n✅ 图标生成完成！"
