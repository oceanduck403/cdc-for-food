Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Assert-PathBelowRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $normalizedPath = Get-NormalizedPath -Path $Path
    $normalizedRoot = Get-NormalizedPath -Path $Root
    $prefix = $normalizedRoot + [System.IO.Path]::DirectorySeparatorChar
    if (-not $normalizedPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label 必须位于 $normalizedRoot 内，实际为 $normalizedPath"
    }
    return $normalizedPath
}

function Assert-Executable {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            throw "找不到$Label：$Path"
        }
        return (Get-NormalizedPath -Path $Path)
    }

    $command = Get-Command $Path -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "找不到$Label：$Path"
    }
    return $command.Source
}

function Assert-PortAvailable {
    param([Parameter(Mandatory = $true)][ValidateRange(1, 65535)][int]$Port)

    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
        throw "端口 $Port 已被监听（PID：$owners）。脚本不会停止或替换该进程。"
    }
}

function Read-DotEnv {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "环境文件不存在：$Path"
    }

    $values = @{}
    $lineNumber = 0
    foreach ($rawLine in [System.IO.File]::ReadAllLines((Get-NormalizedPath -Path $Path))) {
        $lineNumber += 1
        $line = [string]$rawLine
        if ($lineNumber -eq 1) {
            $line = $line.TrimStart([char]0xFEFF)
        }
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $separator = $line.IndexOf('=')
        if ($separator -lt 1) {
            throw "环境文件第 $lineNumber 行不是 KEY=VALUE 格式"
        }
        $name = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1).Trim()
        if ($name -notmatch '^[A-Z][A-Z0-9_]*$') {
            throw "环境文件第 $lineNumber 行变量名无效：$name"
        }
        if ($values.ContainsKey($name)) {
            throw "环境文件包含重复变量：$name"
        }
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        if ($value.Contains("`r") -or $value.Contains("`n") -or $value.Contains([char]0)) {
            throw "环境变量 $name 含有不允许的控制字符"
        }
        $values[$name] = $value
    }
    return $values
}

function Assert-ProductionEnvironment {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Values,
        [ValidateRange(1, 65535)][int]$ExpectedAppPort = 18120,
        [ValidateRange(1, 65535)][int]$ExpectedDatabasePort = 55432,
        [string]$ExpectedMediaRoot = "E:\CDC-Food\shared\uploads",
        [string]$ExpectedLogRoot = "E:\CDC-Food\shared\logs"
    )

    $required = @(
        "APP_ENV", "APP_HOST", "APP_PORT", "APP_LOG_DIR", "JWT_SECRET", "DATABASE_URL",
        "QWEN_API_KEY", "WECHAT_APPID", "WECHAT_SECRET",
        "MEDIA_STORAGE_BACKEND", "MEDIA_STORAGE_DIR"
    )
    $missing = @($required | Where-Object {
        -not $Values.ContainsKey($_) -or [string]::IsNullOrWhiteSpace([string]$Values[$_])
    })
    if ($missing.Count -gt 0) {
        throw "环境文件缺少必填项：$($missing -join ', ')"
    }
    if ($Values.APP_ENV -ne "production") {
        throw "APP_ENV 必须为 production"
    }
    if ($Values.APP_HOST -ne "127.0.0.1") {
        throw "APP_HOST 必须为 127.0.0.1，禁止直接向公网监听"
    }
    if ($Values.APP_PORT -ne [string]$ExpectedAppPort) {
        throw "APP_PORT 必须为 $ExpectedAppPort"
    }
    if ((Get-NormalizedPath -Path $Values.APP_LOG_DIR) -ne (Get-NormalizedPath -Path $ExpectedLogRoot)) {
        throw "APP_LOG_DIR 必须为 $ExpectedLogRoot"
    }
    if ($Values.JWT_SECRET.Length -lt 32 -or $Values.JWT_SECRET -match '^(change-me|replace-me)') {
        throw "JWT_SECRET 必须为至少 32 位的非示例随机值"
    }
    if ($Values.DATABASE_URL -notmatch '^postgresql\+asyncpg://') {
        throw "DATABASE_URL 必须使用 postgresql+asyncpg://"
    }
    if ($Values.DATABASE_URL -notmatch ("@(?:127\.0\.0\.1|localhost):" + $ExpectedDatabasePort + "/")) {
        throw "DATABASE_URL 必须指向本机隔离端口 $ExpectedDatabasePort"
    }
    if ($Values.MEDIA_STORAGE_BACKEND -ne "local_persistent") {
        throw "自建部署的 MEDIA_STORAGE_BACKEND 必须为 local_persistent"
    }
    if ((Get-NormalizedPath -Path $Values.MEDIA_STORAGE_DIR) -ne (Get-NormalizedPath -Path $ExpectedMediaRoot)) {
        throw "MEDIA_STORAGE_DIR 必须为 $ExpectedMediaRoot"
    }
}

function Set-ProcessEnvironment {
    param([Parameter(Mandatory = $true)][hashtable]$Values)

    foreach ($name in $Values.Keys) {
        [System.Environment]::SetEnvironmentVariable($name, [string]$Values[$name], "Process")
    }
}

function Write-PlanLine {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[计划] $Message" -ForegroundColor Cyan
}

function Invoke-CheckedNative {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage,
        [int[]]$AllowedExitCodes = @(0)
    )

    & $Executable @Arguments
    $exitCode = $LASTEXITCODE
    if ($AllowedExitCodes -notcontains $exitCode) {
        throw "$FailureMessage（退出码 $exitCode）"
    }
}
