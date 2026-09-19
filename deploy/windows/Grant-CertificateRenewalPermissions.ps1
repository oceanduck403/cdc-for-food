[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$WacsDirectory,
    [string]$AppRoot = "E:\CDC-Food",
    [string]$ScriptsDirectory = "E:\CDC-Food\ops\windows",
    [string]$NginxRoot = "E:\nginx\nginx-1.28.0",
    [string]$TargetFullChain = "E:\nginx\nginx-1.28.0\ssl\mydomain_fullchain.pem",
    [string]$TargetPrivateKey = "E:\nginx\nginx-1.28.0\ssl\mydomain.key",
    [ValidateSet("S-1-5-19")][string]$RunAsSid = "S-1-5-19",
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

function Grant-PathRights {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$Identity,
        [switch]$Recurse
    )

    $acl = Get-Acl -LiteralPath $Path
    $inheritance = if ($Recurse) {
        [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    } else {
        [System.Security.AccessControl.InheritanceFlags]::None
    }
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $Identity,
        $Rights,
        $inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.SetAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}

$root = Get-NormalizedPath -Path $AppRoot
$wacs = Assert-PathBelowRoot -Path $WacsDirectory -Root (Join-Path $root "ops\win-acme") -Label "win-acme 目录"
$scripts = Assert-PathBelowRoot -Path $ScriptsDirectory -Root $root -Label "运维脚本目录"
$nginx = Get-NormalizedPath -Path $NginxRoot
if ($nginx -ne (Get-NormalizedPath -Path "E:\nginx\nginx-1.28.0")) {
    throw "NginxRoot 不是已审查路径"
}
$targetChain = Get-NormalizedPath -Path $TargetFullChain
$targetKey = Get-NormalizedPath -Path $TargetPrivateKey
$requiredFiles = @(
    (Join-Path $wacs "wacs.exe"),
    (Join-Path $scripts "Invoke-CertificateRenewal.ps1"),
    (Join-Path $scripts "Publish-NginxCertificate.ps1"),
    (Join-Path $nginx "nginx.exe"),
    (Join-Path $nginx "conf\nginx.conf"),
    $targetChain,
    $targetKey
)
foreach ($path in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "缺少权限目标文件：$path"
    }
}

Write-PlanLine "向 LocalService（$RunAsSid）授予 $root\acme 的递归 Modify"
Write-PlanLine "向 LocalService 授予指定 win-acme、运维脚本和 Nginx 配置的只读/执行权限"
Write-PlanLine "只对两个已审查证书文件授予 Modify，不授予 Nginx 目录写权限"
if (-not $Apply) {
    Write-Host "仅显示 ACL 计划。确认后添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

$acmeRoot = Join-Path $root "acme"
foreach ($directory in @(
    $acmeRoot,
    (Join-Path $acmeRoot "webroot"),
    (Join-Path $acmeRoot "state"),
    (Join-Path $acmeRoot "cache"),
    (Join-Path $acmeRoot "logs"),
    (Join-Path $acmeRoot "issued"),
    (Join-Path $acmeRoot "backups"),
    (Join-Path $acmeRoot "transactions")
)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$identity = New-Object System.Security.Principal.SecurityIdentifier($RunAsSid)
$modify = [System.Security.AccessControl.FileSystemRights]::Modify -bor
    [System.Security.AccessControl.FileSystemRights]::Synchronize
$readExecute = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute -bor
    [System.Security.AccessControl.FileSystemRights]::Synchronize
Grant-PathRights -Path $acmeRoot -Rights $modify -Identity $identity -Recurse
Grant-PathRights -Path $wacs -Rights $readExecute -Identity $identity -Recurse
Grant-PathRights -Path $scripts -Rights $readExecute -Identity $identity -Recurse
Grant-PathRights -Path $nginx -Rights $readExecute -Identity $identity
Grant-PathRights -Path (Join-Path $nginx "conf") -Rights $readExecute -Identity $identity -Recurse
Grant-PathRights -Path (Join-Path $nginx "nginx.exe") -Rights $readExecute -Identity $identity
Grant-PathRights -Path $targetChain -Rights $modify -Identity $identity
Grant-PathRights -Path $targetKey -Rights $modify -Identity $identity
Write-Host "证书续期最小权限已配置。" -ForegroundColor Green

