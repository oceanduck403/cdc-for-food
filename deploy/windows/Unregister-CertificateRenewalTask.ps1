[CmdletBinding()]
param(
    [string]$AppRoot = "E:\CDC-Food",
    [string]$ScriptsDirectory = "E:\CDC-Food\ops\windows",
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$taskName = "CDC-Food-Certificate-Renewal"
$root = Get-NormalizedPath -Path $AppRoot
$scripts = Assert-PathBelowRoot -Path $ScriptsDirectory -Root $root -Label "运维脚本目录"
$expectedScript = Join-Path $scripts "Invoke-CertificateRenewal.ps1"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "计划任务不存在，无需注销：$taskName" -ForegroundColor Green
    exit 0
}
$owned = @($task.Actions | Where-Object {
    $_.Execute -like "*powershell.exe" -and $_.Arguments -like ("*" + $expectedScript + "*")
})
if ($owned.Count -ne 1) {
    throw "同名任务并非本资产创建，拒绝操作：$taskName"
}
Write-PlanLine "只注销已验证归属的计划任务 $taskName；不删除证书、win-acme 状态或备份"
if (-not $Apply) {
    Write-Host "仅显示计划。确认后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "证书续期计划任务已注销。" -ForegroundColor Green

