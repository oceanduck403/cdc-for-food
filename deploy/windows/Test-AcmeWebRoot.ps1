[CmdletBinding()]
param(
    [string]$AppRoot = "E:\CDC-Food",
    [string]$WebRoot = "E:\CDC-Food\acme\webroot",
    [ValidateSet("1tovalue.cn", "www.1tovalue.cn")][string]$Domain = "1tovalue.cn",
    [ValidateRange(3, 30)][int]$TimeoutSeconds = 10,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

$root = Get-NormalizedPath -Path $AppRoot
$web = Assert-PathBelowRoot -Path $WebRoot -Root $root -Label "ACME webroot"
$challengeDirectory = Join-Path $web ".well-known\acme-challenge"
$tokenName = "cdc-food-preflight-{0}" -f [Guid]::NewGuid().ToString("N")
$tokenValue = "cdc-food-webroot-ok-{0}" -f [Guid]::NewGuid().ToString("N")
$tokenPath = Join-Path $challengeDirectory $tokenName
$uri = "http://$Domain/.well-known/acme-challenge/$tokenName"

Write-PlanLine "临时写入 $tokenPath"
Write-PlanLine "不跟随重定向地请求 $uri，并逐字核对响应"
Write-PlanLine "无论成功失败都只删除本次创建的随机 token 文件"
if (-not $Apply) {
    Write-Host "仅显示计划。确认 Nginx challenge location 已合并并通过 nginx -t 后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Path $challengeDirectory -Force | Out-Null
try {
    [System.IO.File]::WriteAllText($tokenPath, $tokenValue, [System.Text.Encoding]::ASCII)
    $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec $TimeoutSeconds `
        -MaximumRedirection 0 -Headers @{ Accept = "text/plain" }
    if ($response.StatusCode -ne 200 -or $response.Content.Trim() -ne $tokenValue) {
        throw "公网 HTTP-01 webroot 校验失败：$uri"
    }
}
finally {
    Remove-Item -LiteralPath $tokenPath -Force -ErrorAction SilentlyContinue
}
Write-Host "HTTP-01 webroot 校验通过：$uri" -ForegroundColor Green

