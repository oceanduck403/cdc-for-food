[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourceDirectory,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$')][string]$ReleaseId,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$PythonExecutable = "python.exe",
    [string]$EnvironmentFile = "E:\CDC-Food\shared\config\server.env",
    [switch]$RunMigrations,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$source = Get-NormalizedPath -Path $SourceDirectory
$root = Get-NormalizedPath -Path $AppRoot
$releaseRoot = Join-Path $root "releases"
$target = Assert-PathBelowRoot -Path (Join-Path $releaseRoot $ReleaseId) -Root $root -Label "发布目录"
$sourceServer = Join-Path $source "server"
$requirements = Join-Path $sourceServer "requirements-selfhost.txt"
$entryPoint = Join-Path $sourceServer "app\main.py"

if (-not (Test-Path -LiteralPath $requirements -PathType Leaf) -or
    -not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "SourceDirectory 必须是本项目仓库根目录，并包含 server\requirements-selfhost.txt 与 server\app\main.py"
}
if (Test-Path -LiteralPath $target) {
    throw "发布目录已存在，脚本不会覆盖：$target"
}

$python = Assert-Executable -Path $PythonExecutable -Label "Python"
Write-PlanLine "从 $sourceServer 创建不可覆盖的新发布目录 $target"
Write-PlanLine "使用 $python 创建发布专用虚拟环境并安装锁定版本依赖"
Write-PlanLine "将发布目录内 logs 连接到 $root\shared\logs"
if ($RunMigrations) {
    Write-PlanLine "使用 $EnvironmentFile 执行 alembic upgrade head"
}
Write-PlanLine "不切换现有服务、不停止任何进程、不修改 Nginx、防火墙或 Windows 服务"

if (-not $Apply) {
    Write-Host "仅显示计划。确认后添加 -Apply；如需迁移数据库，再显式添加 -RunMigrations。" -ForegroundColor Yellow
    exit 0
}

$environment = $null
if ($RunMigrations) {
    $environment = Read-DotEnv -Path $EnvironmentFile
    Assert-ProductionEnvironment -Values $environment
}

$staging = Join-Path $releaseRoot (".staging-{0}-{1}" -f $ReleaseId, [Guid]::NewGuid().ToString("N"))
$stagingServer = Join-Path $staging "server"
try {
    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $root "shared\logs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $root "shared\uploads") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $root "shared\config") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $root "backups\postgres") -Force | Out-Null
    New-Item -ItemType Directory -Path $stagingServer -Force | Out-Null

    $robocopy = Assert-Executable -Path "robocopy.exe" -Label "Robocopy"
    $copyArguments = @(
        $sourceServer, $stagingServer, "/E", "/COPY:DAT", "/DCOPY:DAT", "/R:2", "/W:2",
        "/XD", ".venv", "__pycache__", ".pytest_cache", "tests", "data", "logs", "uploads",
        "/XF", ".env", ".env.*", "*.pyc", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
    )
    Invoke-CheckedNative -Executable $robocopy -Arguments $copyArguments `
        -AllowedExitCodes @(0, 1, 2, 3, 4, 5, 6, 7) -FailureMessage "复制发布文件失败"

    & $python -m venv (Join-Path $stagingServer ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "创建 Python 虚拟环境失败（退出码 $LASTEXITCODE）"
    }
    $releasePython = Join-Path $stagingServer ".venv\Scripts\python.exe"
    Invoke-CheckedNative -Executable $releasePython `
        -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "--requirement", (Join-Path $stagingServer "requirements-selfhost.txt")) `
        -FailureMessage "安装 Python 依赖失败"

    $logsLink = Join-Path $stagingServer "logs"
    New-Item -ItemType Junction -Path $logsLink -Target (Join-Path $root "shared\logs") | Out-Null

    $manifest = [ordered]@{
        releaseId = $ReleaseId
        createdAtUtc = [DateTime]::UtcNow.ToString("o")
        source = $source
        python = $python
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText(
        (Join-Path $staging "deployment.json"),
        $manifest,
        (New-Object System.Text.UTF8Encoding($false))
    )

    Move-Item -LiteralPath $staging -Destination $target

    if ($RunMigrations) {
        Set-ProcessEnvironment -Values $environment
        Push-Location (Join-Path $target "server")
        try {
            Invoke-CheckedNative -Executable (Join-Path $target "server\.venv\Scripts\python.exe") `
                -Arguments @("-m", "alembic", "upgrade", "head") -FailureMessage "数据库迁移失败"
        }
        finally {
            Pop-Location
        }
    }
}
catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    throw
}

Write-Host "发布已准备完成：$target" -ForegroundColor Green
Write-Host "脚本未启动 API；请先运行健康预检，再用 Start-App.ps1 显式启动该 ReleaseId。"
