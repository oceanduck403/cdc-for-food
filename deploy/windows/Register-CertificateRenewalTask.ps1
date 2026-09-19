[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$WacsExecutable,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$ScriptsDirectory = "E:\CDC-Food\ops\windows",
    [ValidateSet("S-1-5-19")][string]$RunAsUser = "S-1-5-19",
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')][string]$DailyAt = "03:17",
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$taskName = "CDC-Food-Certificate-Renewal"
$root = Get-NormalizedPath -Path $AppRoot
$scripts = Assert-PathBelowRoot -Path $ScriptsDirectory -Root $root -Label "运维脚本目录"
$renewScript = Join-Path $scripts "Invoke-CertificateRenewal.ps1"
$wacs = Assert-Executable -Path $WacsExecutable -Label "wacs.exe"
Assert-PathBelowRoot -Path $wacs -Root (Join-Path $root "ops\win-acme") -Label "wacs.exe" | Out-Null
foreach ($path in @($renewScript, (Join-Path $scripts "Common.ps1"), $wacs)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "注册前缺少必要文件：$path"
    }
}
$powerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -WacsExecutable "{1}" -AppRoot "{2}" -Apply' -f $renewScript, $wacs, $root
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existing) {
    $matchingActions = @($existing.Actions | Where-Object {
        $_.Execute -eq $powerShell -and $_.Arguments -eq $arguments
    })
    if ($matchingActions.Count -eq 1 -and $existing.Principal.UserId -eq $RunAsUser) {
        Write-Host "证书续期任务已按相同动作和低权限账号注册，无需重复创建。" -ForegroundColor Green
        exit 0
    }
    throw "存在同名但配置不同的计划任务，拒绝覆盖：$taskName"
}

Write-PlanLine "创建唯一计划任务 $taskName，每日 $DailyAt 检查是否需要续期"
Write-PlanLine "任务以 LocalService（$RunAsUser）运行，并使用明确的 wacs.exe 与脚本绝对路径"
Write-PlanLine "任务不使用 -Force、不停止 Nginx，也不修改其他任务或服务"
if (-not $Apply) {
    Write-Host "仅显示计划。先运行 Grant-CertificateRenewalPermissions.ps1 并完成正式签发，再添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

$principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType ServiceAccount -RunLevel Limited
$at = [DateTime]::ParseExact($DailyAt, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
$trigger = New-ScheduledTaskTrigger -Daily -At $at
$action = New-ScheduledTaskAction -Execute $powerShell -Argument $arguments -WorkingDirectory $root
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description "CDC-Food 1tovalue.cn certificate renewal via win-acme HTTP-01 webroot"
Register-ScheduledTask -TaskName $taskName -InputObject $task | Out-Null
Write-Host "计划任务已注册但未立即启动：$taskName" -ForegroundColor Green

