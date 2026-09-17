[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$failures = New-Object System.Collections.Generic.List[string]
$scripts = @(Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter "*.ps1")
foreach ($script in $scripts) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $script.FullName,
        [ref]$tokens,
        [ref]$errors
    )
    foreach ($parseError in @($errors)) {
        $failures.Add("$($script.Name):$($parseError.Extent.StartLineNumber): $($parseError.Message)")
    }
}

$envExample = [System.IO.File]::ReadAllText(
    (Join-Path $PSScriptRoot "environment.example.env"),
    (New-Object System.Text.UTF8Encoding($false))
)
foreach ($secretName in @("JWT_SECRET", "QWEN_API_KEY", "WECHAT_APPID", "WECHAT_SECRET", "ADMIN_BOOTSTRAP_PASSWORD")) {
    if ($envExample -match ("(?m)^" + [regex]::Escape($secretName) + "=.+$")) {
        $failures.Add("environment.example.env 不应为 $secretName 提供值")
    }
}
if ($envExample -notmatch '(?m)^APP_PORT=18120\r?$') {
    $failures.Add("environment.example.env 未固定 APP_PORT=18120")
}
if ($envExample -notmatch '(?m)^APP_LOG_DIR=E:/CDC-Food/shared/logs\r?$') {
    $failures.Add("environment.example.env 未固定 APP_LOG_DIR")
}
if ($envExample -notmatch '(?m)^MEDIA_STORAGE_BACKEND=local_persistent\r?$') {
    $failures.Add("environment.example.env 未使用 local_persistent")
}

$nginx = [System.IO.File]::ReadAllText(
    (Join-Path $PSScriptRoot "nginx-location.conf.example"),
    (New-Object System.Text.UTF8Encoding($false))
)
if ($nginx -notmatch 'location /cdc-food-api/' -or
    $nginx -notmatch 'proxy_pass http://127\.0\.0\.1:18120/;') {
    $failures.Add("Nginx 示例未正确映射 /cdc-food-api/ 到 127.0.0.1:18120")
}

$allText = ($scripts | Where-Object { $_.Name -ne "Test-Assets.ps1" } |
    ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }) -join "`n"
foreach ($forbidden in @('Stop-Process', 'taskkill', 'netsh advfirewall', 'Remove-Service')) {
    if ($allText -match [regex]::Escape($forbidden)) {
        $failures.Add("脚本包含禁止操作：$forbidden")
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Host "通过：$($scripts.Count) 个 PowerShell 脚本可解析，环境模板无密钥，端口与 Nginx 映射符合约束。" -ForegroundColor Green
