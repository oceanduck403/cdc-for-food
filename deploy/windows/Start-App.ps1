[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$')][string]$ReleaseId,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$EnvironmentFile = "E:\CDC-Food\shared\config\server.env",
    [ValidateRange(1, 65535)][int]$Port = 18120,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$root = Get-NormalizedPath -Path $AppRoot
$release = Assert-PathBelowRoot -Path (Join-Path $root "releases\$ReleaseId") -Root $root -Label "发布目录"
$server = Join-Path $release "server"
$python = Join-Path $server ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "发布未准备完成，找不到虚拟环境：$python"
}

$values = Read-DotEnv -Path $EnvironmentFile
Assert-ProductionEnvironment -Values $values -ExpectedAppPort $Port
Assert-PortAvailable -Port $Port

Write-PlanLine "以前台进程启动 ReleaseId=$ReleaseId"
Write-PlanLine "仅监听 http://127.0.0.1:$Port"
Write-PlanLine "工作目录为 $server，日志写入共享日志连接"
Write-PlanLine "脚本不会停止占用端口的进程，也不会变更 Nginx、防火墙或其他服务"

if (-not $Apply) {
    Write-Host "预检通过，仅显示计划。确认后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

Set-ProcessEnvironment -Values $values
Push-Location $server
try {
    & $python -m uvicorn app.main:app `
        --host 127.0.0.1 `
        --port $Port `
        --proxy-headers `
        --forwarded-allow-ips 127.0.0.1
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
if ($exitCode -ne 0) {
    throw "API 进程退出（退出码 $exitCode）"
}

