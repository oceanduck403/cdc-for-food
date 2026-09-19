[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[^\s@]+@[^\s@]+\.[^\s@]+$')][string]$EmailAddress,
    [Parameter(Mandatory = $true)][string]$WacsExecutable,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$WebRoot = "E:\CDC-Food\acme\webroot",
    [string]$IssuedDirectory = "E:\CDC-Food\acme\issued",
    [string]$PublishScript = "E:\CDC-Food\ops\windows\Publish-NginxCertificate.ps1",
    [ValidateSet("1tovalue.cn,www.1tovalue.cn")][string]$HostNames = "1tovalue.cn,www.1tovalue.cn",
    [switch]$Staging,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$root = Get-NormalizedPath -Path $AppRoot
$web = Assert-PathBelowRoot -Path $WebRoot -Root $root -Label "ACME webroot"
$issued = Assert-PathBelowRoot -Path $IssuedDirectory -Root $root -Label "PEM 输出目录"
$state = Assert-PathBelowRoot -Path (Join-Path $root "acme\state") -Root $root -Label "win-acme 状态目录"
$wacs = Assert-Executable -Path $WacsExecutable -Label "wacs.exe"
$wacsRoot = Get-NormalizedPath -Path (Split-Path -Parent $wacs)
Assert-PathBelowRoot -Path $wacs -Root (Join-Path $root "ops\win-acme") -Label "wacs.exe" | Out-Null

$renewalId = if ($Staging) { "cdc-food-1tovalue-cn-staging" } else { "cdc-food-1tovalue-cn" }
$friendlyName = if ($Staging) { "cdc-food-1tovalue-nginx-staging" } else { "cdc-food-1tovalue-nginx" }
if ($Staging) {
    $issued = Assert-PathBelowRoot -Path (Join-Path $root "acme\staging-issued") -Root $root -Label "测试 PEM 输出目录"
}
$existing = @(Get-ChildItem -LiteralPath $state -Recurse -File -Filter "$renewalId.renewal.json" -ErrorAction SilentlyContinue)
if ($existing.Count -gt 0) {
    Write-Host "续期定义已存在，无需重复创建：$renewalId" -ForegroundColor Green
    exit 0
}
if (-not $Staging -and -not (Test-Path -LiteralPath $PublishScript -PathType Leaf)) {
    throw "找不到证书发布脚本：$PublishScript"
}

Write-PlanLine "用 filesystem/webroot 为 $HostNames 创建续期定义 $renewalId"
Write-PlanLine "PEM 仅写入隔离目录 $issued；不直接覆盖 Nginx 证书"
if ($Staging) {
    Write-PlanLine "使用 Let's Encrypt staging，仅验证签发链路，不执行 Nginx 发布脚本"
} else {
    Write-PlanLine "成功签发后由 $PublishScript 事务化校验、替换和 reload"
}
Write-PlanLine "传递 --notaskscheduler，禁止 win-acme 创建自己的高权限任务"
if (-not $Apply) {
    Write-Host "仅显示计划。建议先使用 -Staging -Apply 验证，再执行正式签发。" -ForegroundColor Yellow
    exit 0
}

& (Join-Path $PSScriptRoot "Test-AcmeWebRoot.ps1") -AppRoot $root -WebRoot $web -Apply
if ($LASTEXITCODE -ne 0) {
    throw "HTTP-01 webroot 预检失败"
}
New-Item -ItemType Directory -Path $issued -Force | Out-Null
$arguments = @(
    "--source", "manual",
    "--host", $HostNames,
    "--id", $renewalId,
    "--friendlyname", $friendlyName,
    "--validation", "filesystem",
    "--validationmode", "http-01",
    "--webroot", $web,
    "--csr", "rsa",
    "--store", "pemfiles",
    "--pemfilespath", $issued,
    "--pemfilesname", "mydomain",
    "--emailaddress", $EmailAddress,
    "--accepttos",
    "--notaskscheduler"
)
if ($Staging) {
    $arguments += "--test"
    $arguments += "--closeonfinish"
} else {
    $issuedFullChain = Join-Path $issued "mydomain-chain.pem"
    $issuedPrivateKey = Join-Path $issued "mydomain-key.pem"
    $scriptParameters = "-IssuedFullChain '$issuedFullChain' -IssuedPrivateKey '$issuedPrivateKey' -Apply"
    $arguments += @(
        "--installation", "script",
        "--script", (Get-NormalizedPath -Path $PublishScript),
        "--scriptparameters", $scriptParameters
    )
}

Push-Location $wacsRoot
try {
    Invoke-CheckedNative -Executable $wacs -Arguments $arguments -FailureMessage "win-acme 初始签发失败"
}
finally {
    Pop-Location
}
Write-Host "续期定义已创建：$renewalId" -ForegroundColor Green

