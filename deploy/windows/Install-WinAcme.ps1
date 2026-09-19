[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ArchivePath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Fa-f0-9]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?$')][string]$Version,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$InstallRoot = "E:\CDC-Food\ops\win-acme",
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$root = Get-NormalizedPath -Path $AppRoot
$install = Assert-PathBelowRoot -Path $InstallRoot -Root $root -Label "win-acme 安装根目录"
$archive = Get-NormalizedPath -Path $ArchivePath
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw "找不到 win-acme ZIP：$archive"
}
$actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToUpperInvariant()
$expectedHash = $ExpectedSha256.ToUpperInvariant()
if ($actualHash -ne $expectedHash) {
    throw "win-acme ZIP 的 SHA-256 与独立核对值不一致"
}
$target = Assert-PathBelowRoot -Path (Join-Path $install $Version) -Root $root -Label "win-acme 版本目录"
$markerPath = Join-Path $target "cdc-food-installation.json"

if (Test-Path -LiteralPath $target) {
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $target "wacs.exe") -PathType Leaf)) {
        throw "版本目录已存在但不是本脚本完成的安装，拒绝覆盖：$target"
    }
    $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
    if ($marker.version -ne $Version -or $marker.archiveSha256 -ne $expectedHash) {
        throw "版本目录与请求的版本或 ZIP 哈希不一致，拒绝覆盖：$target"
    }
    Write-Host "win-acme $Version 已按相同哈希安装，无需重复写入：$target" -ForegroundColor Green
    exit 0
}

Write-PlanLine "从已下载的 ZIP 安装 win-acme $Version 到不可覆盖目录 $target"
Write-PlanLine "ZIP SHA-256 已匹配；不会联网下载或信任“最新版本”浮动地址"
Write-PlanLine "生成独立 settings.json，将状态、缓存与日志限制在 $root\acme"
Write-PlanLine "不创建任务、不申请证书、不修改 Nginx 或防火墙"
if (-not $Apply) {
    Write-Host "仅显示计划。请从独立可信渠道核对 SHA-256 后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
New-Item -ItemType Directory -Path $install -Force | Out-Null
$staging = Join-Path $install (".staging-win-acme-{0}" -f [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($entry in $zip.Entries) {
            $entryName = [string]$entry.FullName
            if ([string]::IsNullOrWhiteSpace($entryName)) {
                continue
            }
            $destination = [System.IO.Path]::GetFullPath((Join-Path $staging $entryName))
            $stagingPrefix = (Get-NormalizedPath -Path $staging) + [System.IO.Path]::DirectorySeparatorChar
            if (-not $destination.StartsWith($stagingPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "ZIP 包含越界路径：$entryName"
            }
            if ($entryName.EndsWith("/") -or $entryName.EndsWith("\")) {
                New-Item -ItemType Directory -Path $destination -Force | Out-Null
                continue
            }
            New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
            $inputStream = $entry.Open()
            try {
                $outputStream = New-Object System.IO.FileStream(
                    $destination,
                    [System.IO.FileMode]::CreateNew,
                    [System.IO.FileAccess]::Write,
                    [System.IO.FileShare]::None
                )
                try {
                    $inputStream.CopyTo($outputStream)
                }
                finally {
                    $outputStream.Dispose()
                }
            }
            finally {
                $inputStream.Dispose()
            }
        }
    }
    finally {
        $zip.Dispose()
    }

    $wacsFiles = @(Get-ChildItem -LiteralPath $staging -Recurse -File -Filter "wacs.exe")
    if ($wacsFiles.Count -ne 1) {
        throw "ZIP 中应当且只能包含一个 wacs.exe"
    }
    $payloadRoot = $wacsFiles[0].Directory.FullName
    $defaultSettingsPath = Join-Path $payloadRoot "settings_default.json"
    if (-not (Test-Path -LiteralPath $defaultSettingsPath -PathType Leaf)) {
        throw "ZIP 缺少 settings_default.json"
    }
    $settings = Get-Content -LiteralPath $defaultSettingsPath -Raw | ConvertFrom-Json
    foreach ($propertyPath in @("Client", "Cache", "ScheduledTask", "Security", "Script")) {
        if ($null -eq $settings.PSObject.Properties[$propertyPath]) {
            throw "win-acme settings_default.json 缺少预期配置节：$propertyPath"
        }
    }
    $settings.Client.ClientName = "cdc-food-win-acme"
    $settings.Client.ConfigurationPath = (Join-Path $root "acme\state")
    $settings.Client.LogPath = (Join-Path $root "acme\logs")
    $settings.Client.VersionCheck = $false
    $settings.Cache.Path = (Join-Path $root "acme\cache")
    $settings.Cache.ReuseDays = 0
    $settings.ScheduledTask.RenewalDays = 55
    $settings.ScheduledTask.RenewalDaysRange = 5
    $settings.ScheduledTask.ExecutionTimeLimit = "02:00:00"
    $settings.Security.EncryptConfig = $true
    $settings.Script.PowershellExecutablePath = (Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe")
    $settingsJson = $settings | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText(
        (Join-Path $payloadRoot "settings.json"),
        $settingsJson,
        (New-Object System.Text.UTF8Encoding($false))
    )
    $marker = [ordered]@{
        version = $Version
        archiveSha256 = $expectedHash
        installedAtUtc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText(
        (Join-Path $payloadRoot "cdc-food-installation.json"),
        $marker,
        (New-Object System.Text.UTF8Encoding($false))
    )

    if (Test-Path -LiteralPath $target) {
        throw "目标目录在安装期间出现，拒绝覆盖：$target"
    }
    Move-Item -LiteralPath $payloadRoot -Destination $target
    if ((Get-NormalizedPath -Path $payloadRoot) -ne (Get-NormalizedPath -Path $staging) -and
        (Test-Path -LiteralPath $staging)) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    throw
}

Write-Host "win-acme 已安装：$target\wacs.exe" -ForegroundColor Green

