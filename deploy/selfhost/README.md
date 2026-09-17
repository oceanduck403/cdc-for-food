# 自建服务器小程序发布包

小程序源码不保存生产 API 地址。正式地址通过本机配置、环境变量或命令行参数注入到
`build/wechat-release/`，源码目录继续用于开发。

## 生成发布包

复制示例文件并只在本机填写：

```powershell
Copy-Item deploy/selfhost/miniprogram.example.json deploy/selfhost/miniprogram.local.json
```

当前部署计划使用：

```json
{
  "apiBase": "https://1tovalue.cn/cdc-food-api/api/v1"
}
```

本机文件已经加入 `.gitignore`。也可在 CI 中使用环境变量，或临时传参；优先级依次为
`--api-base`、`CDC_MINIPROGRAM_API_BASE`、本机 JSON 文件。

```powershell
# 使用本机 JSON
node deploy/selfhost/build_miniprogram.js

# CI 示例
$env:CDC_MINIPROGRAM_API_BASE = 'https://1tovalue.cn/cdc-food-api/api/v1'
node deploy/selfhost/build_miniprogram.js --output build/wechat-release
```

脚本复制必要的小程序源码并写入仅存在于构建目录的 `release-runtime.js`，不会修改源码配置。
微信开发者工具应导入仓库内的 `build/wechat-release/`，不要直接上传仓库根目录或
`miniprogram/` 源码目录。

## 上传前复核

```powershell
node deploy/selfhost/build_miniprogram.js --validate build/wechat-release
```

校验会拒绝以下情况：

- HTTP、IP 地址、localhost、`.local`、示例域名或占位符；
- URL 内含账号密码、查询参数、片段或非 443 端口；
- API 路径未以 `/api/v1` 结尾；
- 构建产物未使用 `direct`、未关闭 mock、AppID 未配置；
- 发布目录结构不完整。

开发版仍可在微信开发者工具控制台设置 `__cdc_api_transport__` 和 `__cdc_api_base__` 做
局域网联调。该覆盖只在 `envVersion=develop` 生效，体验版和正式版固定使用构建时注入的地址。

生成成功只代表前端配置通过静态检查。上传体验版前，还需确认 Nginx 对该路径返回后端响应，
并在微信公众平台把 `https://1tovalue.cn` 配置为 request、uploadFile 和 downloadFile 合法域名。
