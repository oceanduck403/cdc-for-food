[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$WacsExecutable,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$WebRoot = "E:\CDC-Food\acme\webroot",
    [ValidateSet("cdc-food-1tovalue-cn")][string]$RenewalId = "cdc-food-1tovalue-cn",
    [switch]$Force,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$root = Get-NormalizedPath -Path $AppRoot
$web = Assert-PathBelowRoot -Path $WebRoot -Root $root -Label "ACME webroot"
$state = Assert-PathBelowRoot -Path (Join-Path $root "acme\state") -Root $root -Label "win-acme 状态目录"
$wacs = Assert-Executable -Path $WacsExecutable -Label "wacs.exe"
Assert-PathBelowRoot -Path $wacs -Root (Join-Path $root "ops\win-acme") -Label "wacs.exe" | Out-Null
$renewals = @(Get-ChildItem -LiteralPath $state -Recurse -File -Filter "$RenewalId.renewal.json" -ErrorAction SilentlyContinue)
if ($renewals.Count -ne 1) {
    throw "应当且只能找到一个正式续期定义 $RenewalId，实际为 $($renewals.Count) 个"
}

Write-PlanLine "预检公网 HTTP-01 webroot 后，检查续期定义 $RenewalId"
Write-PlanLine "只有证书到期策略要求时才续期；签发失败不会调用发布脚本"
if ($Force) {
    Write-PlanLine "已显式选择 -Force，将忽略常规到期窗口（仅用于人工演练）"
}
if (-not $Apply) {
    Write-Host "仅显示计划。计划任务只应使用不带 -Force 的 -Apply。" -ForegroundColor Yellow
    exit 0
}

& (Join-Path $PSScriptRoot "Test-AcmeWebRoot.ps1") -AppRoot $root -WebRoot $web -Apply
if ($LASTEXITCODE -ne 0) {
    throw "HTTP-01 webroot 预检失败"
}
$arguments = @("--renew", "--id", $RenewalId, "--notaskscheduler")
if ($Force) {
    $arguments += "--force"
}
Push-Location (Split-Path -Parent $wacs)
try {
    Invoke-CheckedNative -Executable $wacs -Arguments $arguments -FailureMessage "win-acme 续期检查失败"
}
finally {
    Pop-Location
}

