[CmdletBinding()]
param(
    [string]$PostgresBin = "E:\postgres\bin",
    [string]$AppRoot = "E:\CDC-Food",
    [string]$DataDirectory = "E:\CDC-Food\postgres\data",
    [string]$LogFile = "E:\CDC-Food\shared\logs\postgres\pg-ctl.log",
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
$log = Assert-PathBelowRoot -Path $LogFile -Root $root -Label "PostgreSQL 启动日志"
$pgCtl = Assert-Executable -Path (Join-Path $PostgresBin "pg_ctl.exe") -Label "pg_ctl"
if (-not (Test-Path -LiteralPath (Join-Path $data "PG_VERSION") -PathType Leaf)) {
    throw "指定目录不是已初始化的 PostgreSQL 集群：$data"
}
Assert-PortAvailable -Port $Port

Write-PlanLine "启动隔离集群 $data，仅监听配置文件中的 127.0.0.1:$Port"
Write-PlanLine "不停止或修改任何其他 PostgreSQL 实例"
if (-not $Apply) {
    Write-Host "仅显示计划。确认后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Path (Split-Path -Parent $log) -Force | Out-Null
Invoke-CheckedNative -Executable $pgCtl -Arguments @(
    "start", "--pgdata=$data", "--log=$log", "--wait", "--timeout=60"
) -FailureMessage "启动隔离 PostgreSQL 集群失败"
Write-Host "隔离 PostgreSQL 已启动：127.0.0.1:$Port" -ForegroundColor Green

