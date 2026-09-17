[CmdletBinding()]
param(
    [string]$AppRoot = "E:\CDC-Food",
    [string]$ScriptsDirectory = "E:\CDC-Food\ops\windows",
    [string]$PostgresBin = "E:\postgres\bin",
    [switch]$Stop,
    [switch]$Unregister,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

if (-not $Stop -and -not $Unregister) {
    throw "必须显式选择 -Stop、-Unregister，或两者都选"
}
$postgresTaskName = "CDC-Food-Postgres"
$apiTaskName = "CDC-Food-API"
$root = Get-NormalizedPath -Path $AppRoot
$scripts = Assert-PathBelowRoot -Path $ScriptsDirectory -Root $root -Label "运维脚本目录"
$expectedFragments = @{
    $postgresTaskName = (Join-Path $scripts "Run-Postgres.ps1")
    $apiTaskName = (Join-Path $scripts "Start-App.ps1")
}
$tasks = @{}
foreach ($name in @($postgresTaskName, $apiTaskName)) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        throw "找不到计划任务，未执行任何操作：$name"
    }
    $owned = @($task.Actions | Where-Object {
        $_.Execute -like "*powershell.exe" -and $_.Arguments -like ("*" + $expectedFragments[$name] + "*")
    })
    if ($owned.Count -ne 1) {
        throw "同名任务并非本部署脚本创建，拒绝操作：$name"
    }
    $tasks[$name] = $task
}

if ($Stop) {
    Write-PlanLine "先停止 $apiTaskName，再用 pg_ctl fast 模式停止 $postgresTaskName 的隔离集群"
}
if ($Unregister) {
    Write-PlanLine "仅注销两个已验证归属的任务：$postgresTaskName、$apiTaskName"
}
Write-PlanLine "不处理任何其他任务、服务或进程"
if (-not $Apply) {
    Write-Host "仅显示计划。确认后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

if ($Stop) {
    Stop-ScheduledTask -TaskName $apiTaskName -ErrorAction SilentlyContinue
    $pgCtl = Assert-Executable -Path (Join-Path $PostgresBin "pg_ctl.exe") -Label "pg_ctl"
    $data = Assert-PathBelowRoot -Path (Join-Path $root "postgres\data") -Root $root -Label "PostgreSQL 数据目录"
    $statusOutput = & $pgCtl status --pgdata=$data 2>&1
    $statusCode = $LASTEXITCODE
    if ($statusCode -eq 0) {
        Invoke-CheckedNative -Executable $pgCtl -Arguments @(
            "stop", "--pgdata=$data", "--mode=fast", "--wait", "--timeout=60"
        ) -FailureMessage "停止隔离 PostgreSQL 失败"
    } elseif ($statusCode -ne 3) {
        throw "无法确认隔离 PostgreSQL 状态（退出码 $statusCode）：$($statusOutput | Out-String)"
    }
    Stop-ScheduledTask -TaskName $postgresTaskName -ErrorAction SilentlyContinue
}
if ($Unregister) {
    foreach ($name in @($apiTaskName, $postgresTaskName)) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
    }
}
Write-Host "请求的 CDC-Food 任务操作已完成。" -ForegroundColor Green

