[CmdletBinding()]
param(
    [string]$PostgresBin = "E:\postgres\bin",
    [string]$AppRoot = "E:\CDC-Food",
    [string]$BackupDirectory = "E:\CDC-Food\backups\postgres",
    [string]$DatabaseHost = "127.0.0.1",
    [ValidateRange(1, 65535)][int]$DatabasePort = 55432,
    [ValidatePattern('^[a-z][a-z0-9_]{2,62}$')][string]$DatabaseName = "cdc_food",
    [System.Management.Automation.PSCredential]$DatabaseCredential,
    [string]$CredentialFile = "",
    [ValidateRange(1, 3650)][int]$RetentionDays = 30,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

if ($DatabaseHost -notin @("127.0.0.1", "localhost")) {
    throw "备份脚本只允许连接本机隔离数据库"
}
if ($DatabasePort -ne 55432) {
    throw "备份脚本只允许连接隔离端口 55432"
}
$root = Get-NormalizedPath -Path $AppRoot
$backupRoot = Assert-PathBelowRoot -Path $BackupDirectory -Root $root -Label "备份目录"
$pgDump = Assert-Executable -Path (Join-Path $PostgresBin "pg_dump.exe") -Label "pg_dump"
$pgRestore = Assert-Executable -Path (Join-Path $PostgresBin "pg_restore.exe") -Label "pg_restore"

Write-PlanLine "从 $DatabaseHost`:$DatabasePort/$DatabaseName 生成 PostgreSQL custom 格式备份"
Write-PlanLine "备份写入 $backupRoot，校验成功后才改为最终文件名"
Write-PlanLine "成功后清理超过 $RetentionDays 天的本脚本备份；不触碰数据库目录或其他备份"
if (-not $Apply) {
    Write-Host "仅显示计划。执行时请通过 -DatabaseCredential 或 DPAPI 加密的 -CredentialFile 提供凭据，并添加 -Apply。" -ForegroundColor Yellow
    exit 0
}

if ($null -eq $DatabaseCredential) {
    if ([string]::IsNullOrWhiteSpace($CredentialFile)) {
        throw "执行备份必须提供 -DatabaseCredential 或 -CredentialFile"
    }
    if (-not (Test-Path -LiteralPath $CredentialFile -PathType Leaf)) {
        throw "凭据文件不存在：$CredentialFile"
    }
    $DatabaseCredential = Import-Clixml -LiteralPath $CredentialFile
    if ($DatabaseCredential -isnot [System.Management.Automation.PSCredential]) {
        throw "CredentialFile 不是 PSCredential；请用 Export-Clixml 在同一 Windows 账号下创建"
    }
}

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$timestamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
$finalPath = Join-Path $backupRoot ("cdc-food-{0}.dump" -f $timestamp)
$temporaryPath = $finalPath + ".partial"
if ((Test-Path -LiteralPath $finalPath) -or (Test-Path -LiteralPath $temporaryPath)) {
    throw "备份目标已存在，拒绝覆盖：$finalPath"
}

$plainPassword = $DatabaseCredential.GetNetworkCredential().Password
$previousPassword = [System.Environment]::GetEnvironmentVariable("PGPASSWORD", "Process")
try {
    [System.Environment]::SetEnvironmentVariable("PGPASSWORD", $plainPassword, "Process")
    Invoke-CheckedNative -Executable $pgDump -Arguments @(
        "--host=$DatabaseHost", "--port=$DatabasePort",
        "--username=$($DatabaseCredential.UserName)", "--dbname=$DatabaseName",
        "--format=custom", "--compress=6", "--no-owner", "--no-privileges",
        "--file=$temporaryPath"
    ) -FailureMessage "pg_dump 失败"

    Invoke-CheckedNative -Executable $pgRestore -Arguments @("--list", $temporaryPath) `
        -FailureMessage "备份完整性检查失败"
    Move-Item -LiteralPath $temporaryPath -Destination $finalPath
}
catch {
    Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    throw
}
finally {
    [System.Environment]::SetEnvironmentVariable("PGPASSWORD", $previousPassword, "Process")
    $plainPassword = $null
}

$cutoff = [DateTime]::UtcNow.AddDays(-$RetentionDays)
Get-ChildItem -LiteralPath $backupRoot -File -Filter "cdc-food-*.dump" |
    Where-Object { $_.LastWriteTimeUtc -lt $cutoff } |
    Remove-Item -Force

Write-Host "备份完成：$finalPath" -ForegroundColor Green
