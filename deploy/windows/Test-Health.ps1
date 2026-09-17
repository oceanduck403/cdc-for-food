[CmdletBinding()]
param(
    [string]$LocalUri = "http://127.0.0.1:18120/health",
    [string]$ExternalUri = "",
    [ValidateRange(1, 60)][int]$TimeoutSeconds = 10
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-OneHealthEndpoint {
    param([Parameter(Mandatory = $true)][uri]$Uri)

    if ($Uri.Scheme -notin @("http", "https")) {
        throw "健康检查仅支持 HTTP/HTTPS：$Uri"
    }
    $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSeconds `
        -Headers @{ Accept = "application/json" }
    if ($response.StatusCode -ne 200) {
        throw "$Uri 返回 HTTP $($response.StatusCode)"
    }
    try {
        $payload = $response.Content | ConvertFrom-Json
    }
    catch {
        throw "$Uri 未返回有效 JSON"
    }
    if ($payload.status -ne "ok" -or $payload.env -ne "production") {
        throw "$Uri 健康状态异常（期望 status=ok 且 env=production）"
    }
    Write-Host "[通过] $Uri" -ForegroundColor Green
}

Test-OneHealthEndpoint -Uri ([uri]$LocalUri)
if (-not [string]::IsNullOrWhiteSpace($ExternalUri)) {
    Test-OneHealthEndpoint -Uri ([uri]$ExternalUri)
}

