[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$')][string]$ReleaseId,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$ScriptsDirectory = "E:\CDC-Food\ops\windows",
    [ValidateSet("SYSTEM")][string]$RunAsUser = "SYSTEM",
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$postgresTaskName = "CDC-Food-Postgres"
$apiTaskName = "CDC-Food-API"
$root = Get-NormalizedPath -Path $AppRoot
$scripts = Assert-PathBelowRoot -Path $ScriptsDirectory -Root $root -Label "运维脚本目录"
$release = Assert-PathBelowRoot -Path (Join-Path $root "releases\$ReleaseId") -Root $root -Label "发布目录"
$runPostgres = Join-Path $scripts "Run-Postgres.ps1"
$startApi = Join-Path $scripts "Start-App.ps1"
$environmentFile = Join-Path $root "shared\config\server.env"

foreach ($requiredFile in @(
    $runPostgres,
    $startApi,
    (Join-Path $scripts "Common.ps1"),
    $environmentFile,
    (Join-Path $release "server\.venv\Scripts\python.exe")
)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "注册前缺少必要文件：$requiredFile"
    }
}

foreach ($name in @($postgresTaskName, $apiTaskName)) {
    if ($null -ne (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue)) {
        throw "计划任务已存在，脚本拒绝覆盖：$name"
    }
}

$powerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
if (-not (Test-Path -LiteralPath $powerShell -PathType Leaf)) {
    throw "找不到 Windows PowerShell：$powerShell"
}
$postgresArguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -AppRoot "{1}" -Apply' -f $runPostgres, $root
$apiArguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -ReleaseId "{1}" -AppRoot "{2}" -EnvironmentFile "{3}" -Apply' -f $startApi, $ReleaseId, $root, $environmentFile

Write-PlanLine "创建唯一计划任务 $postgresTaskName（开机启动，异常退出后重试）"
Write-PlanLine "创建唯一计划任务 $apiTaskName（ReleaseId=$ReleaseId，开机启动，异常退出后重试）"
Write-PlanLine "两个任务以 $RunAsUser 运行，只调用 $scripts 下的脚本"
Write-PlanLine "不启动任务、不覆盖同名任务、不修改其他任务、服务、防火墙或 Nginx"
if (-not $Apply) {
    Write-Host "仅显示计划。确认脚本目录 ACL 和 server.env ACL 后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

$principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType ServiceAccount -RunLevel Highest
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero
    )
$postgresAction = New-ScheduledTaskAction -Execute $powerShell -Argument $postgresArguments -WorkingDirectory $root
$apiAction = New-ScheduledTaskAction -Execute $powerShell -Argument $apiArguments -WorkingDirectory $root
$postgresTask = New-ScheduledTask -Action $postgresAction -Trigger $trigger -Principal $principal -Settings $settings `
    -Description "CDC-Food isolated PostgreSQL 127.0.0.1:55432"
$apiTask = New-ScheduledTask -Action $apiAction -Trigger $trigger -Principal $principal -Settings $settings `
    -Description "CDC-Food API 127.0.0.1:18120 release $ReleaseId"

$created = New-Object System.Collections.Generic.List[string]
try {
    Register-ScheduledTask -TaskName $postgresTaskName -InputObject $postgresTask | Out-Null
    $created.Add($postgresTaskName)
    Register-ScheduledTask -TaskName $apiTaskName -InputObject $apiTask | Out-Null
    $created.Add($apiTaskName)
}
catch {
    foreach ($name in $created) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    }
    throw
}

Write-Host "计划任务注册完成，但尚未手动启动：$postgresTaskName、$apiTaskName" -ForegroundColor Green

