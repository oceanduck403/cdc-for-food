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

初始化脚本不会注册 Windows 服务。服务器重启后的自动启动方式应在确认专用运行账号与恢复方案后单独配置，不能复用或修改已有服务。

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

任务默认以 `SYSTEM` 服务账号运行，因此 `server.env`、数据库目录、上传目录与日志目录无需向普通用户开放。注册前仍应人工检查这些路径的 ACL；不要给 `Everyone` 或 `Users` 写权限。任务动作是前台受管进程，异常退出后由任务计划程序重试，且不会操作已有服务。

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

## 回滚原则

发布脚本不维护“当前版本”指针，也不替换正在运行的进程。回滚时先停止 **CDC-Food 自己的前台 API 进程**，再用 `Start-App.ps1 -ReleaseId <previous-id> -Apply` 启动已验证的旧发布。数据库迁移可能不可逆，因此每次迁移前必须先执行并验证数据库备份；不得通过删除数据库目录来回滚。
