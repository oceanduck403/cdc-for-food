[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$IssuedFullChain,
    [Parameter(Mandatory = $true)][string]$IssuedPrivateKey,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$NginxRoot = "E:\nginx\nginx-1.28.0",
    [string]$TargetFullChain = "E:\nginx\nginx-1.28.0\ssl\mydomain_fullchain.pem",
    [string]$TargetPrivateKey = "E:\nginx\nginx-1.28.0\ssl\mydomain.key",
    [ValidateRange(1, 60)][int]$MinimumRemainingDays = 14,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

function Get-LeafCertificateFromPem {
    param([Parameter(Mandatory = $true)][string]$Path)

    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::ASCII)
    $match = [regex]::Match(
        $text,
        '-----BEGIN CERTIFICATE-----\s*(?<data>[A-Za-z0-9+/=\s]+?)\s*-----END CERTIFICATE-----'
    )
    if (-not $match.Success) {
        throw "证书链不是有效的 PEM：$Path"
    }
    $der = [Convert]::FromBase64String(($match.Groups["data"].Value -replace '\s', ''))
    return New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 -ArgumentList (, $der)
}

function Invoke-NginxCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string]$Root
    )
    Push-Location $Root
    try {
        & $Executable -p ($Root + "\") -c "conf\nginx.conf" -t
        return $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

function Invoke-NginxReload {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string]$Root
    )
    Push-Location $Root
    try {
        & $Executable -p ($Root + "\") -c "conf\nginx.conf" -s reload
        return $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

$root = Get-NormalizedPath -Path $AppRoot
$issuedRoot = Assert-PathBelowRoot -Path (Join-Path $root "acme\issued") -Root $root -Label "PEM 输出目录"
$sourceChain = Assert-PathBelowRoot -Path $IssuedFullChain -Root $issuedRoot -Label "新证书链"
$sourceKey = Assert-PathBelowRoot -Path $IssuedPrivateKey -Root $issuedRoot -Label "新私钥"
$nginx = Get-NormalizedPath -Path $NginxRoot
$expectedNginx = Get-NormalizedPath -Path "E:\nginx\nginx-1.28.0"
if ($nginx -ne $expectedNginx) {
    throw "NginxRoot 必须为已审查路径 $expectedNginx"
}
$targetChain = Get-NormalizedPath -Path $TargetFullChain
$targetKey = Get-NormalizedPath -Path $TargetPrivateKey
if ($targetChain -ne (Join-Path $nginx "ssl\mydomain_fullchain.pem") -or
    $targetKey -ne (Join-Path $nginx "ssl\mydomain.key")) {
    throw "目标证书路径必须是已审查的 mydomain_fullchain.pem 与 mydomain.key"
}
foreach ($path in @($sourceChain, $sourceKey, $targetChain, $targetKey, (Join-Path $nginx "conf\nginx.conf"))) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "缺少必要文件：$path"
    }
}
$nginxExe = Assert-Executable -Path (Join-Path $nginx "nginx.exe") -Label "nginx.exe"
if (([System.IO.Path]::GetPathRoot($root)) -ne ([System.IO.Path]::GetPathRoot($nginx))) {
    throw "事务替换要求 AppRoot 与 NginxRoot 位于同一卷"
}

$certificate = Get-LeafCertificateFromPem -Path $sourceChain
try {
    $now = [DateTime]::UtcNow
    if ($certificate.NotBefore.ToUniversalTime() -gt $now.AddMinutes(5)) {
        throw "新证书尚未生效"
    }
    if ($certificate.NotAfter.ToUniversalTime() -lt $now.AddDays($MinimumRemainingDays)) {
        throw "新证书剩余有效期少于 $MinimumRemainingDays 天"
    }
    $dnsName = $certificate.GetNameInfo(
        [System.Security.Cryptography.X509Certificates.X509NameType]::DnsName,
        $false
    )
    if ($dnsName -notin @("1tovalue.cn", "www.1tovalue.cn")) {
        throw "新证书主 DNS 名不属于 1tovalue.cn：$dnsName"
    }
}
finally {
    $certificate.Dispose()
}
$keyText = [System.IO.File]::ReadAllText($sourceKey, [System.Text.Encoding]::ASCII)
if ($keyText -notmatch '-----BEGIN (?:RSA |EC )?PRIVATE KEY-----' -or
    $keyText -match '-----BEGIN ENCRYPTED PRIVATE KEY-----') {
    throw "私钥不是 Nginx 可直接读取的未加密 PEM"
}

$sourceChainHash = (Get-FileHash -LiteralPath $sourceChain -Algorithm SHA256).Hash
$sourceKeyHash = (Get-FileHash -LiteralPath $sourceKey -Algorithm SHA256).Hash
$targetChainHash = (Get-FileHash -LiteralPath $targetChain -Algorithm SHA256).Hash
$targetKeyHash = (Get-FileHash -LiteralPath $targetKey -Algorithm SHA256).Hash
if ($sourceChainHash -eq $targetChainHash -and $sourceKeyHash -eq $targetKeyHash) {
    if ((Invoke-NginxCheck -Executable $nginxExe -Root $nginx) -ne 0) {
        throw "证书内容虽未变化，但 nginx -t 失败；未执行 reload"
    }
    Write-Host "Nginx 已使用相同证书，配置检查通过，无需替换或 reload。" -ForegroundColor Green
    exit 0
}

$backupRoot = Assert-PathBelowRoot -Path (Join-Path $root "acme\backups") -Root $root -Label "证书备份目录"
$transactionRoot = Assert-PathBelowRoot -Path (Join-Path $root ("acme\transactions\{0}" -f [Guid]::NewGuid().ToString("N"))) -Root $root -Label "证书事务目录"
Write-PlanLine "备份当前 Nginx 证书到 $backupRoot"
Write-PlanLine "以同卷原子替换两个目标文件，然后执行 nginx -t"
Write-PlanLine "仅在 nginx -t 成功后执行 nginx -s reload；任一步失败都恢复旧证书"
if (-not $Apply) {
    Write-Host "证书与路径预检通过，仅显示计划。确认后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
New-Item -ItemType Directory -Path $transactionRoot -Force | Out-Null
$stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss") + "-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
$archiveChain = Join-Path $backupRoot "$stamp-mydomain_fullchain.pem"
$archiveKey = Join-Path $backupRoot "$stamp-mydomain.key"
$pendingChain = Join-Path $transactionRoot "pending-fullchain.pem"
$pendingKey = Join-Path $transactionRoot "pending-key.pem"
$replaceBackupChain = Join-Path $transactionRoot "original-fullchain.pem"
$replaceBackupKey = Join-Path $transactionRoot "original-key.pem"
$restored = $false
$chainReplaced = $false
$keyReplaced = $false
$committed = $false
try {
    Copy-Item -LiteralPath $targetChain -Destination $archiveChain
    Copy-Item -LiteralPath $targetKey -Destination $archiveKey
    Set-Acl -LiteralPath $archiveChain -AclObject (Get-Acl -LiteralPath $targetChain)
    Set-Acl -LiteralPath $archiveKey -AclObject (Get-Acl -LiteralPath $targetKey)
    Copy-Item -LiteralPath $sourceChain -Destination $pendingChain
    Copy-Item -LiteralPath $sourceKey -Destination $pendingKey
    Set-Acl -LiteralPath $pendingChain -AclObject (Get-Acl -LiteralPath $targetChain)
    Set-Acl -LiteralPath $pendingKey -AclObject (Get-Acl -LiteralPath $targetKey)

    [System.IO.File]::Replace($pendingChain, $targetChain, $replaceBackupChain, $true)
    $chainReplaced = $true
    [System.IO.File]::Replace($pendingKey, $targetKey, $replaceBackupKey, $true)
    $keyReplaced = $true

    if ((Invoke-NginxCheck -Executable $nginxExe -Root $nginx) -ne 0) {
        throw "新证书写入后 nginx -t 失败"
    }
    if ((Invoke-NginxReload -Executable $nginxExe -Root $nginx) -ne 0) {
        throw "新证书通过 nginx -t，但平滑 reload 命令失败"
    }
    $committed = $true
}
catch {
    $originalError = $_
    try {
        if ($keyReplaced) {
            $restoreKey = Join-Path $transactionRoot "restore-key.pem"
            Copy-Item -LiteralPath $archiveKey -Destination $restoreKey
            Set-Acl -LiteralPath $restoreKey -AclObject (Get-Acl -LiteralPath $targetKey)
            [System.IO.File]::Replace($restoreKey, $targetKey, $null, $true)
        }
        if ($chainReplaced) {
            $restoreChain = Join-Path $transactionRoot "restore-fullchain.pem"
            Copy-Item -LiteralPath $archiveChain -Destination $restoreChain
            Set-Acl -LiteralPath $restoreChain -AclObject (Get-Acl -LiteralPath $targetChain)
            [System.IO.File]::Replace($restoreChain, $targetChain, $null, $true)
        }
        $restored = $true
        if ((Invoke-NginxCheck -Executable $nginxExe -Root $nginx) -eq 0) {
            [void](Invoke-NginxReload -Executable $nginxExe -Root $nginx)
        }
    }
    catch {
        throw "证书发布失败且自动回滚也失败。旧证书备份位于 $archiveChain 与 $archiveKey。原始错误：$($originalError.Exception.Message)；回滚错误：$($_.Exception.Message)"
    }
    throw "证书发布失败，已恢复旧证书：$($originalError.Exception.Message)"
}
finally {
    if (Test-Path -LiteralPath $transactionRoot) {
        Remove-Item -LiteralPath $transactionRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
if (-not $committed -or $restored) {
    throw "证书事务未提交"
}
Write-Host "Nginx 证书已安全更新并完成平滑 reload；旧证书备份：$archiveChain" -ForegroundColor Green

