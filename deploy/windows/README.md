# Windows Server 自建部署资产

本目录用于把疾控小程序后端隔离部署到 Windows Server 2016。它不会接管现有 `1tovalue.cn` 服务，也不会修改现有 Nginx、IIS、Windows 防火墙或 PostgreSQL 5432 实例。

## 固定边界

| 项目 | 固定值 |
| --- | --- |
| 应用根目录 | `E:\CDC-Food` |
| API 监听 | `127.0.0.1:18120` |
| PostgreSQL 监听 | `127.0.0.1:55432` |
| PostgreSQL 二进制 | `E:\postgres\bin`（只调用，不修改） |
| 外部路径 | `https://1tovalue.cn/cdc-food-api/` |
| 用户媒体 | `E:\CDC-Food\shared\uploads` |
| 日志 | `E:\CDC-Food\shared\logs` |
| 数据库备份 | `E:\CDC-Food\backups\postgres` |

所有会产生变更的脚本默认只打印计划；必须显式加 `-Apply` 才会执行。脚本遇错立即停止，不查杀进程，不抢占端口，不覆盖已有发布或非空数据库目录。

## 目录布局

```text
E:\CDC-Food
├─ releases\<release-id>\server   每次发布独立且不可覆盖
├─ postgres\data                  独立 PostgreSQL cluster
├─ shared\config\server.env      服务器密钥（禁止提交）
├─ shared\logs                    API 与数据库日志
├─ shared\uploads                 私有用户媒体
└─ backups\postgres               custom 格式数据库备份
```

## 审查与执行顺序

先在代码仓库运行静态检查：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\deploy\windows\Test-Assets.ps1
```

复制 `environment.example.env` 到 `E:\CDC-Food\shared\config\server.env`，只在服务器上填写。数据库密码必须先做 URL 编码后放入 `DATABASE_URL`。实际环境文件应限制为部署账号和运行账号可读，不能上传 Git、聊天或工单。

`APP_LOG_DIR` 必须保持为绝对路径 `E:/CDC-Food/shared/logs`，让不同发布版本共用受控日志目录并保留审计记录。

初始化隔离数据库前先预览。两个凭据通过 `Get-Credential` 交互获取，不出现在命令行或脚本里：

```powershell
$clusterCredential = Get-Credential -Message "新集群管理员（不要使用现有数据库账号）"
$appCredential = Get-Credential -Message "CDC-Food 应用数据库账号"
.\deploy\windows\Initialize-PostgresCluster.ps1 `
  -ClusterCredential $clusterCredential `
  -ApplicationCredential $appCredential

# 审查计划后才执行：
.\deploy\windows\Initialize-PostgresCluster.ps1 `
  -ClusterCredential $clusterCredential `
  -ApplicationCredential $appCredential `
  -Apply -LeaveRunning
```

初始化使用跨 Windows 区域设置稳定的 `C` locale，数据库文本仍统一使用 UTF-8。脚本不会注册 Windows 服务；服务器重启后的自动启动由下方两个唯一命名的计划任务负责，不能复用或修改已有任务或服务。

从一份干净的仓库副本创建发布。第一次先省略 `-Apply` 查看计划：

```powershell
.\deploy\windows\Deploy-Release.ps1 `
  -SourceDirectory E:\CDC-Food-Staging\source `
  -ReleaseId 725f19c `
  -RunMigrations

# 审查计划后才执行：
.\deploy\windows\Deploy-Release.ps1 `
  -SourceDirectory E:\CDC-Food-Staging\source `
  -ReleaseId 725f19c `
  -RunMigrations -Apply
```

启动 API 仍采用显式 ReleaseId，脚本在前台运行，便于明确看到退出状态。它发现 18120 已占用时会报错，不会停止占用者：

```powershell
.\deploy\windows\Start-App.ps1 -ReleaseId 725f19c
.\deploy\windows\Start-App.ps1 -ReleaseId 725f19c -Apply
```

验证前台启动正常后，把本目录完整复制到固定的 `E:\CDC-Food\ops\windows`，再注册两个唯一命名的开机任务。注册动作默认 dry-run，已有同名任务时拒绝覆盖，也不会立即启动任务：

```powershell
E:\CDC-Food\ops\windows\Register-Tasks.ps1 -ReleaseId 725f19c
E:\CDC-Food\ops\windows\Register-Tasks.ps1 -ReleaseId 725f19c -Apply

# 首次注册后按依赖顺序显式启动：
Start-ScheduledTask -TaskName CDC-Food-Postgres
E:\CDC-Food\ops\windows\Test-Health.ps1
Start-ScheduledTask -TaskName CDC-Food-API
```

任务默认以低权限内置账号 `LocalService`（SID `S-1-5-19`）运行。注册前应只向该账号授予项目运行所需的最小权限：数据库、上传和日志目录可写，发布目录与运维脚本只读，`server.env` 只读；不要给 `Everyone` 或 `Users` 写权限。任务动作是前台受管进程，异常退出后由任务计划程序重试，且不会操作已有服务。

停止或注销必须使用单独脚本并显式选择动作；默认同样只显示计划。脚本会核对任务动作确实指向 `E:\CDC-Food\ops\windows`，避免误操作碰巧同名的任务：

```powershell
E:\CDC-Food\ops\windows\Stop-Unregister-Tasks.ps1 -Stop
E:\CDC-Food\ops\windows\Stop-Unregister-Tasks.ps1 -Stop -Apply

# 确认已经停止后，才注销：
E:\CDC-Food\ops\windows\Stop-Unregister-Tasks.ps1 -Unregister
E:\CDC-Food\ops\windows\Stop-Unregister-Tasks.ps1 -Unregister -Apply
```

先验证本机 API：

```powershell
.\deploy\windows\Test-Health.ps1
```

只有在人工审查现有 Nginx 配置并备份后，才可把 `nginx-location.conf.example` 的 `location` 块合并进现有 HTTPS `server {}`。禁止覆盖 `E:\nginx\nginx-1.28.0` 下任何配置。合并后先运行 `nginx.exe -t`；语法通过后才能由运维人员决定是否平滑 reload。外部映射完成后再检查：

```powershell
.\deploy\windows\Test-Health.ps1 `
  -ExternalUri https://1tovalue.cn/cdc-food-api/health
```

备份脚本默认 dry-run，执行时凭据不会作为命令行参数传给 `pg_dump`：

```powershell
$backupCredential = Get-Credential -Message "CDC-Food 备份账号"
.\deploy\windows\Backup-Postgres.ps1 -DatabaseCredential $backupCredential
.\deploy\windows\Backup-Postgres.ps1 -DatabaseCredential $backupCredential -Apply
```

如需无人值守备份，可在计划任务运行账号下用 `Export-Clixml` 保存 DPAPI 加密的 `PSCredential`，再传 `-CredentialFile`。该文件只能由同一台机器、同一 Windows 账号解密；仍需限制 ACL，并定期做异机恢复演练。

## 1tovalue.cn 证书自动续期

现有证书文件为 `E:\nginx\nginx-1.28.0\ssl\mydomain_fullchain.pem` 和 `mydomain.key`。续期流程使用 win-acme 的 HTTP-01 filesystem/webroot 验证，不占用端口、不停止 Nginx。win-acme 只把新 PEM 写入 `E:\CDC-Food\acme\issued`；发布脚本备份旧文件并做同卷原子替换，随后先运行 `nginx -t`，通过后才执行 `nginx -s reload`。检查或 reload 失败时恢复旧证书并再次加载旧配置。

官方参数说明：

- 文件验证：<https://www.win-acme.com/reference/plugins/validation/http/filesystem>
- Nginx PEM 输出：<https://www.win-acme.com/reference/plugins/store/pemfiles>
- 成功签发后的安装脚本：<https://www.win-acme.com/reference/plugins/installation/script>
- 自动续期机制：<https://www.win-acme.com/manual/automatic-renewal>

先从 win-acme 官方发布页下载固定版本的 x64 ZIP，并通过另一个可信渠道核对该文件的 SHA-256。安装脚本不联网下载，也不接受“latest”浮动版本：

```powershell
E:\CDC-Food\ops\windows\Install-WinAcme.ps1 `
  -ArchivePath E:\CDC-Food-Staging\win-acme.v2.2.9.1701.x64.trimmed.zip `
  -ExpectedSha256 <64位官方核对值> `
  -Version 2.2.9.1701

# 审查计划后执行：
E:\CDC-Food\ops\windows\Install-WinAcme.ps1 `
  -ArchivePath E:\CDC-Food-Staging\win-acme.v2.2.9.1701.x64.trimmed.zip `
  -ExpectedSha256 <64位官方核对值> `
  -Version 2.2.9.1701 -Apply
```

脚本为每个版本创建不可覆盖目录，并生成独立 `settings.json`，把账户、续期定义、缓存和日志限制在 `E:\CDC-Food\acme`。版本号只是示例，实际必须使用已下载并核验的固定版本。

把 `nginx-acme-challenge.conf.example` 的 `location` 块人工合并到 **当前负责 `1tovalue.cn` 的 80 端口 server 块**，并放在整站 HTTPS 跳转之前。不要新增冲突的 `listen 80`，不要覆盖现有 Nginx 配置。先执行：

```powershell
Set-Location E:\nginx\nginx-1.28.0
.\nginx.exe -p "E:\nginx\nginx-1.28.0\" -c conf\nginx.conf -t
```

只有语法通过后才由运维人员执行一次 `.\nginx.exe -s reload`。然后用随机 token 从公网验证文件映射；脚本不跟随重定向，因此会发现 challenge 被错误跳转到 HTTPS 或被 IIS/其他站点接管：

```powershell
E:\CDC-Food\ops\windows\Test-AcmeWebRoot.ps1
E:\CDC-Food\ops\windows\Test-AcmeWebRoot.ps1 -Apply
```

HTTP-01 要求公网的 `1tovalue.cn:80` 能访问上述路径。如果 80 端口实际由 IIS 或其他代理接收，应在真正的入口映射同一个 webroot，或改用经过评审的 DNS-01 流程；不要停止现有服务来给 win-acme 让端口。

为低权限 `LocalService` 账号授予精确权限。此步骤只允许写 `E:\CDC-Food\acme` 和两个现有证书文件；win-acme、脚本和 Nginx 配置均为只读/执行：

```powershell
$wacs = "E:\CDC-Food\ops\win-acme\2.2.9.1701\wacs.exe"
$wacsDir = Split-Path -Parent $wacs
E:\CDC-Food\ops\windows\Grant-CertificateRenewalPermissions.ps1 `
  -WacsDirectory $wacsDir
E:\CDC-Food\ops\windows\Grant-CertificateRenewalPermissions.ps1 `
  -WacsDirectory $wacsDir -Apply
```

先用 Let’s Encrypt staging 验证签发链路。staging 证书只写入 `staging-issued`，不会调用发布脚本，也不会替换线上证书：

```powershell
E:\CDC-Food\ops\windows\Initialize-CertificateRenewal.ps1 `
  -EmailAddress <运维邮箱> -WacsExecutable $wacs -Staging
E:\CDC-Food\ops\windows\Initialize-CertificateRenewal.ps1 `
  -EmailAddress <运维邮箱> -WacsExecutable $wacs -Staging -Apply
```

staging 成功后创建正式续期定义。首次正式签发成功后会立即执行安全发布脚本：

```powershell
E:\CDC-Food\ops\windows\Initialize-CertificateRenewal.ps1 `
  -EmailAddress <运维邮箱> -WacsExecutable $wacs
E:\CDC-Food\ops\windows\Initialize-CertificateRenewal.ps1 `
  -EmailAddress <运维邮箱> -WacsExecutable $wacs -Apply
```

确认 HTTPS 证书、Nginx 日志与 `E:\CDC-Food\acme\logs` 正常后，注册我们自己的低权限任务。脚本显式传递 `--notaskscheduler`，因此不会留下 win-acme 默认的 SYSTEM 任务：

```powershell
E:\CDC-Food\ops\windows\Register-CertificateRenewalTask.ps1 `
  -WacsExecutable $wacs
E:\CDC-Food\ops\windows\Register-CertificateRenewalTask.ps1 `
  -WacsExecutable $wacs -Apply
```

任务名固定为 `CDC-Food-Certificate-Renewal`，每日检查一次，默认不带 `-Force`。已有相同任务且动作和身份一致时视为幂等成功；同名但配置不同则拒绝覆盖。人工强制演练必须显式执行，且应注意 Let’s Encrypt 频率限制：

```powershell
E:\CDC-Food\ops\windows\Invoke-CertificateRenewal.ps1 `
  -WacsExecutable $wacs -Force
# 审查计划后才添加 -Apply
```

需要停用时，只注销已验证归属的任务，不删除证书、账户状态或备份：

```powershell
E:\CDC-Food\ops\windows\Unregister-CertificateRenewalTask.ps1
E:\CDC-Food\ops\windows\Unregister-CertificateRenewalTask.ps1 -Apply
```

证书备份保存在 `E:\CDC-Food\acme\backups`，不会自动清理。应在确认多次续期和异机恢复演练成功后制定保留周期。私钥、win-acme 状态目录和备份都不得上传 Git 或发到聊天中。

## 回滚原则

发布脚本不维护“当前版本”指针，也不替换正在运行的进程。回滚时先停止 **CDC-Food 自己的前台 API 进程**，再用 `Start-App.ps1 -ReleaseId <previous-id> -Apply` 启动已验证的旧发布。数据库迁移可能不可逆，因此每次迁移前必须先执行并验证数据库备份；不得通过删除数据库目录来回滚。
