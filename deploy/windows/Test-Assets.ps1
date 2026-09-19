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
    if ($envExample -match ("(?m)^" + [regex]::Escape($secretName) + "=[^\r\n]+\r?$")) {
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

$acmeNginx = [System.IO.File]::ReadAllText(
    (Join-Path $PSScriptRoot "nginx-acme-challenge.conf.example"),
    (New-Object System.Text.UTF8Encoding($false))
)
if ($acmeNginx -notmatch 'location \^~ /\.well-known/acme-challenge/' -or
    $acmeNginx -notmatch 'root E:/CDC-Food/acme/webroot;') {
    $failures.Add("Nginx ACME 示例未把 HTTP-01 路径映射到隔离 webroot")
}

$requiredAcmeAssets = @(
    "Install-WinAcme.ps1",
    "Test-AcmeWebRoot.ps1",
    "Initialize-CertificateRenewal.ps1",
    "Invoke-CertificateRenewal.ps1",
    "Publish-NginxCertificate.ps1",
    "Grant-CertificateRenewalPermissions.ps1",
    "Register-CertificateRenewalTask.ps1",
    "Unregister-CertificateRenewalTask.ps1",
    "nginx-acme-challenge.conf.example"
)
foreach ($asset in $requiredAcmeAssets) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $asset) -PathType Leaf)) {
        $failures.Add("缺少证书续期资产：$asset")
    }
}

$initializeCertificateText = [System.IO.File]::ReadAllText(
    (Join-Path $PSScriptRoot "Initialize-CertificateRenewal.ps1")
)
foreach ($requiredArgument in @(
    '"--validation", "filesystem"',
    '"--webroot", $web',
    '"--store", "pemfiles"',
    '"--notaskscheduler"'
)) {
    if ($initializeCertificateText -notmatch [regex]::Escape($requiredArgument)) {
        $failures.Add("初始签发脚本缺少安全参数：$requiredArgument")
    }
}

$publishCertificateText = [System.IO.File]::ReadAllText(
    (Join-Path $PSScriptRoot "Publish-NginxCertificate.ps1")
)
$checkIndex = $publishCertificateText.IndexOf('Invoke-NginxCheck -Executable')
$reloadIndex = $publishCertificateText.IndexOf('Invoke-NginxReload -Executable')
if ($checkIndex -lt 0 -or $reloadIndex -lt 0 -or $checkIndex -ge $reloadIndex) {
    $failures.Add("证书发布脚本必须先执行 nginx -t，再执行平滑 reload")
}

$renewTaskText = [System.IO.File]::ReadAllText(
    (Join-Path $PSScriptRoot "Register-CertificateRenewalTask.ps1")
)
if ($renewTaskText -notmatch '\[ValidateSet\("S-1-5-19"\)\]\[string\]\$RunAsUser = "S-1-5-19"') {
    $failures.Add("证书续期任务必须默认使用 LocalService")
}
if ($renewTaskText -match '["'']-Force["'']') {
    $failures.Add("证书续期计划任务不得使用 -Force")
}

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$repositoryEntryPoint = Join-Path $repositoryRoot "server\app\main.py"
if (Test-Path -LiteralPath $repositoryEntryPoint -PathType Leaf) {
    $selfHostRequirementsPath = Join-Path $repositoryRoot "server\requirements-selfhost.txt"
    if (-not (Test-Path -LiteralPath $selfHostRequirementsPath -PathType Leaf)) {
        $failures.Add("缺少 server/requirements-selfhost.txt")
    } else {
        $defaultRequirementsPath = Join-Path $repositoryRoot "server\requirements.txt"
        $selfHostRequirements = [System.IO.File]::ReadAllText($selfHostRequirementsPath)
        if ($selfHostRequirements -match '(?im)^cos-python-sdk-v5(?:[=<>!~].*)?$') {
            $failures.Add("自建部署依赖不得包含 COS SDK")
        }
        if ($selfHostRequirements -notmatch '(?im)^greenlet==3\.5\.5\r?$') {
            $failures.Add("自建部署依赖必须显式锁定 Python 3.13 所需的 greenlet")
        }
        $expectedSelfHost = @(
            Get-Content -LiteralPath $defaultRequirementsPath |
                Where-Object { $_ -notmatch '^cos-python-sdk-v5(?:[=<>!~].*)?$' }
        )
        $actualSelfHost = @(Get-Content -LiteralPath $selfHostRequirementsPath)
        if (@(Compare-Object -ReferenceObject $expectedSelfHost -DifferenceObject $actualSelfHost).Count -gt 0) {
            $failures.Add("自建部署依赖应与默认依赖保持一致，仅排除 COS SDK")
        }
    }
}

$deployReleaseText = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "Deploy-Release.ps1"))
if ($deployReleaseText -notmatch '\(Join-Path \$stagingServer "requirements-selfhost\.txt"\)') {
    $failures.Add("Deploy-Release.ps1 未安装自建部署依赖清单")
}
if ($deployReleaseText -notmatch '\$targetCreated' -or
    $deployReleaseText -notmatch 'Remove-Item -LiteralPath \$target -Recurse -Force') {
    $failures.Add("Deploy-Release.ps1 缺少失败发布目录回滚")
}

$registerTasksText = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "Register-Tasks.ps1"))
if ($registerTasksText -notmatch '\[ValidateSet\("S-1-5-19"\)\]\[string\]\$RunAsUser = "S-1-5-19"') {
    $failures.Add("计划任务必须默认使用低权限 LocalService 账号")
}
if ($registerTasksText -match '\$RunAsUser = "SYSTEM"') {
    $failures.Add("PostgreSQL 计划任务不得默认以 SYSTEM 运行")
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
