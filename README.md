# 膳知有伴 · 营养与食品安全科普小程序

原生微信小程序与 Python FastAPI 后端，提供健康评估、健康打卡、AI 科普、科普互动及个人资料管理，另有独立管理员入口。

## 当前交接版本

最新交接代码位于 **`fix/survey-registration-loading`**，不能假定默认分支 `main` 已包含最新修复。2026-10-12 已完成电脑本地试运行；本次不上传、提审或部署。

**接手团队先阅读 [项目技术简介与交接说明](docs/technical-handoff.md)**，其中包含实际架构、技术栈、运行步骤、配置、安全交接材料和未开放功能。

```powershell
git clone --branch fix/survey-registration-loading git@github.com:oceanduck403/cdc-for-food.git
cd cdc-for-food
```

## 目录与架构

```text
miniprogram/       原生微信小程序：JavaScript / WXML / WXSS
server/            FastAPI / SQLAlchemy 异步 ORM / Alembic
deploy/selfhost/   独立本地演示启动器、小程序正式包构建
deploy/windows/    Windows 自建服务器部署与运维脚本
docs/              技术、运行、原始表单及历史方案文档
sync/              未接入当前主链路的历史 RSS 工具
```

小程序通过 HTTP JSON API 访问模块化单体后端。SQLite 用于开发，生产配置要求 PostgreSQL。通义千问由服务端网关调用，密钥不进入小程序。媒体可使用本地持久磁盘或私有云存储；项目不依赖 Railway。

## 原始五套表单

| 表单 | 字段/题数 |
| --- | --- |
| 体重管理门诊就诊信息登记表 | 10 |
| 体重管理门诊病历首页 | 21 |
| 体重管理门诊首诊评估表 | 50 |
| 体重管理门诊防肥分数自测表 | 36，11 个分组 |
| 体重管理门诊复诊评估表 | 26 |

题干、选项与条件依据原始 Word 恢复。原稿未提供计分公式，因此不编造总分或风险等级；提交保存题目快照，避免模板变更影响历史记录。详见 [原始表单说明](docs/survey-registration.md)。

## 电脑本地试运行

Windows、Python 3.12，在仓库根目录执行：

```powershell
py -3.12 -m venv server/.venv
server/.venv/Scripts/python.exe -m pip install -r server/requirements.txt
if (-not (Test-Path -LiteralPath 'server/.env')) {
    Copy-Item server/.env.example server/.env
}
```

仅首次复制 `.env`，不要覆盖已有配置。在本机 `.env` 填写微信和千问配置后：

```powershell
server/.venv/Scripts/python.exe deploy/selfhost/run_local_demo.py
```

后端使用独立运行目录，API 为 `http://127.0.0.1:18121/api/v1`。微信开发者工具导入仓库根目录，并按 [本地预览手册](docs/miniprogram-devtools.md) 配置开发版接口地址。

## 验证与功能边界

业务基线本轮验证：前端 68 项、后端 124 项通过；五表及真实千问文字问答通过本机联调。

当前打卡与 AI 对话历史保存在本机，尚未跨设备同步。医生服务默认关闭；当前用户版没有医生和 GIS 地图入口。会员支付、微信运动、素材 CMS、完整可视化题目编辑器及知识库 RAG 尚未完成。详见 [交接说明](docs/technical-handoff.md#9-未开放与后续优先事项)。

Git 不包含真实密钥、数据库、用户媒体、原始 Word 或本机构建结果，需另行安全交接。完整文档见 [文档索引](docs/README.md)，协作约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。
