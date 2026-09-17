[CmdletBinding()]
param(
    [string]$PostgresBin = "E:\postgres\bin",
    [string]$AppRoot = "E:\CDC-Food",
    [string]$DataDirectory = "E:\CDC-Food\postgres\data",
    [ValidateRange(1, 65535)][int]$Port = 55432,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

if ($Port -ne 55432) {
    throw "本项目隔离集群固定使用 55432；脚本拒绝其他端口"
}
$root = Get-NormalizedPath -Path $AppRoot
$data = Assert-PathBelowRoot -Path $DataDirectory -Root $root -Label "PostgreSQL 数据目录"
$postgres = Assert-Executable -Path (Join-Path $PostgresBin "postgres.exe") -Label "postgres"
if (-not (Test-Path -LiteralPath (Join-Path $data "PG_VERSION") -PathType Leaf)) {
    throw "指定目录不是已初始化的 PostgreSQL 集群：$data"
}

$configuredPort = ((& $postgres -D $data -C port) | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $configuredPort -ne [string]$Port) {
    throw "集群配置的端口不是隔离端口 $Port"
}
$listenAddresses = ((& $postgres -D $data -C listen_addresses) | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $listenAddresses -ne "127.0.0.1") {
    throw "集群必须只监听 127.0.0.1，实际为：$listenAddresses"
}
Assert-PortAvailable -Port $Port

Write-PlanLine "以前台受管进程运行隔离集群 $data（127.0.0.1:$Port）"
Write-PlanLine "异常退出时由 CDC-Food-Postgres 计划任务重试；不处理其他 PostgreSQL 进程"
if (-not $Apply) {
    Write-Host "预检通过，仅显示计划。确认后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

& $postgres -D $data
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "隔离 PostgreSQL 进程退出（退出码 $exitCode）"
}
