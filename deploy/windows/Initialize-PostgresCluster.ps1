[CmdletBinding()]
param(
    [string]$PostgresBin = "E:\postgres\bin",
    [string]$AppRoot = "E:\CDC-Food",
    [string]$DataDirectory = "E:\CDC-Food\postgres\data",
    [string]$LogDirectory = "E:\CDC-Food\shared\logs\postgres",
    [ValidateRange(1, 65535)][int]$Port = 55432,
    [ValidatePattern('^[a-z][a-z0-9_]{2,62}$')][string]$DatabaseName = "cdc_food",
    [System.Management.Automation.PSCredential]$ClusterCredential,
    [System.Management.Automation.PSCredential]$ApplicationCredential,
    [switch]$LeaveRunning,
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common.ps1")

if ($Port -ne 55432) {
    throw "本项目隔离集群固定使用 55432；脚本拒绝其他端口，尤其不会触碰现有 5432"
}
$root = Get-NormalizedPath -Path $AppRoot
$data = Assert-PathBelowRoot -Path $DataDirectory -Root $root -Label "PostgreSQL 数据目录"
$logs = Assert-PathBelowRoot -Path $LogDirectory -Root $root -Label "PostgreSQL 日志目录"
$initDb = Assert-Executable -Path (Join-Path $PostgresBin "initdb.exe") -Label "initdb"
$pgCtl = Assert-Executable -Path (Join-Path $PostgresBin "pg_ctl.exe") -Label "pg_ctl"
$psql = Assert-Executable -Path (Join-Path $PostgresBin "psql.exe") -Label "psql"

if (Test-Path -LiteralPath $data) {
    throw "数据目录已存在，脚本拒绝覆盖或接管（即使为空也需先人工核对）：$data"
}
Assert-PortAvailable -Port $Port

Write-PlanLine "用现有二进制 $PostgresBin 初始化全新集群 $data"
Write-PlanLine "集群只监听 127.0.0.1:$Port，使用 SCRAM-SHA-256"
Write-PlanLine "创建独立应用角色和数据库 $DatabaseName"
Write-PlanLine "不注册 Windows 服务、不修改现有 5432 集群、不修改防火墙"
if ($LeaveRunning) {
    Write-PlanLine "初始化完成后保留新集群运行"
} else {
    Write-PlanLine "初始化完成后安全停止新集群"
}
if (-not $Apply) {
    Write-Host "仅显示计划。执行时必须提供两个 PSCredential，并添加 -Apply。" -ForegroundColor Yellow
    exit 0
}
if ($null -eq $ClusterCredential -or $null -eq $ApplicationCredential) {
    throw "执行初始化必须显式提供 -ClusterCredential 与 -ApplicationCredential"
}
if ($ClusterCredential.UserName -notmatch '^[a-z][a-z0-9_]{2,62}$' -or
    $ApplicationCredential.UserName -notmatch '^[a-z][a-z0-9_]{2,62}$') {
    throw "数据库用户名只允许 3 至 63 位小写字母、数字和下划线，且以字母开头"
}
if ($ClusterCredential.UserName -eq $ApplicationCredential.UserName) {
    throw "集群管理员与应用账号必须不同"
}

$clusterPassword = $ClusterCredential.GetNetworkCredential().Password
$appPassword = $ApplicationCredential.GetNetworkCredential().Password
if ($clusterPassword.Length -lt 16 -or $appPassword.Length -lt 16) {
    throw "两个数据库密码都必须至少 16 位"
}

    New-Item -ItemType Directory -Path (Split-Path -Parent $data) -Force | Out-Null
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$passwordFile = Join-Path $root ("shared\config\.pg-init-{0}" -f [Guid]::NewGuid().ToString("N"))
$postgresLog = Join-Path $logs "postgresql.log"
$started = $false
$previousPassword = [System.Environment]::GetEnvironmentVariable("PGPASSWORD", "Process")
try {
    New-Item -ItemType Directory -Path (Split-Path -Parent $passwordFile) -Force | Out-Null
    [System.IO.File]::WriteAllText($passwordFile, $clusterPassword, (New-Object System.Text.UTF8Encoding($false)))
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $acl.SetOwner([System.Security.Principal.WindowsIdentity]::GetCurrent().User)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().User,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $passwordFile -AclObject $acl

    Invoke-CheckedNative -Executable $initDb -Arguments @(
        "--pgdata=$data", "--username=$($ClusterCredential.UserName)",
        "--encoding=UTF8", "--locale=C",
        "--auth-host=scram-sha-256", "--auth-local=scram-sha-256",
        "--pwfile=$passwordFile"
    ) -FailureMessage "initdb 失败"

    $config = @(
        "# CDC-Food isolated cluster settings",
        "listen_addresses = '127.0.0.1'",
        "port = $Port",
        "password_encryption = 'scram-sha-256'",
        "logging_collector = on",
        "log_directory = '$($logs.Replace('\', '/').Replace("'", "''"))'",
        "log_filename = 'postgresql-%Y-%m-%d.log'",
        "log_rotation_age = 1d",
        "log_truncate_on_rotation = on"
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $lineEnding = [System.Environment]::NewLine
    [System.IO.File]::AppendAllText(
        (Join-Path $data "postgresql.conf"),
        (($config -join $lineEnding) + $lineEnding),
        $utf8NoBom
    )
    $hba = @(
        "# TYPE  DATABASE  USER  ADDRESS         METHOD",
        "host    all       all   127.0.0.1/32    scram-sha-256"
    )
    [System.IO.File]::WriteAllText(
        (Join-Path $data "pg_hba.conf"),
        (($hba -join $lineEnding) + $lineEnding),
        $utf8NoBom
    )

    Invoke-CheckedNative -Executable $pgCtl -Arguments @(
        "start", "--pgdata=$data", "--log=$postgresLog", "--wait", "--timeout=60"
    ) -FailureMessage "启动新 PostgreSQL 集群失败"
    $started = $true

    [System.Environment]::SetEnvironmentVariable("PGPASSWORD", $clusterPassword, "Process")
    $escapedPassword = $appPassword.Replace("'", "''")
    $createRole = "CREATE ROLE $($ApplicationCredential.UserName) LOGIN PASSWORD '$escapedPassword';"
    $createRole | & $psql --host=127.0.0.1 --port=$Port `
        --username=$($ClusterCredential.UserName) --dbname=postgres --set=ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) {
        throw "创建应用数据库角色失败（退出码 $LASTEXITCODE）"
    }
    "CREATE DATABASE $DatabaseName OWNER $($ApplicationCredential.UserName);" | & $psql `
        --host=127.0.0.1 --port=$Port --username=$($ClusterCredential.UserName) `
        --dbname=postgres --set=ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) {
        throw "创建应用数据库失败（退出码 $LASTEXITCODE）"
    }
}
finally {
    [System.Environment]::SetEnvironmentVariable("PGPASSWORD", $previousPassword, "Process")
    Remove-Item -LiteralPath $passwordFile -Force -ErrorAction SilentlyContinue
    $clusterPassword = $null
    $appPassword = $null
    if ($started -and -not $LeaveRunning) {
        & $pgCtl stop --pgdata=$data --mode=fast --wait --timeout=60
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "新集群未能自动停止，请只检查 $data 对应的 PostgreSQL 进程；不要处理现有 5432 实例。"
        }
    }
}

Write-Host "隔离 PostgreSQL 集群已初始化：$data" -ForegroundColor Green
