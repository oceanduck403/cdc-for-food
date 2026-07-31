# 协作约定（Contributing）

本文件定义团队成员在本仓库的日常协作流程，包括分支、提交、评审、发布。
所有参与本项目的开发人员请先阅读一遍再动手。

## 1. 仓库结构

```
疾控/
├── docs/        项目文档（架构、API、部署、合规、路线图）
├── miniprogram/ 微信小程序前端（原生）
└── server/      后端服务（FastAPI）
```

详见根目录 [`README.md`](./README.md) 与 [`docs/README.md`](./docs/README.md)。

## 2. 分支策略

采用「主干 + 功能分支」模型，简单可控。

| 分支 | 用途 | 谁可以 push |
| --- | --- | --- |
| `main` | 稳定、可运行、可演示的版本 | 仅通过 PR 合并，不允许直 push |
| `feat/*` | 新功能，例如 `feat/ai-recognize` | 开发本人 |
| `fix/*` | 修 bug，例如 `fix/login-token-expired` | 开发本人 |
| `chore/*` | 文档、配置、依赖整理 | 开发本人 |
| `hotfix/*` | 生产环境紧急修复 | 仅负责人 |

**约定：**
- 不要在 `main` 上直接开发。
- 功能完成后通过 Pull Request 合并到 `main`，至少 1 人 Review。
- 单个 PR 控制在 300 行以内为佳，超大改动拆成多个 PR。

## 3. 提交规范（Conventional Commits）

格式：`<type>(<scope>): <subject>`

常见 type：

| type | 含义 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 仅文档变更 |
| `style` | 格式调整（不影响代码运行） |
| `refactor` | 重构（既不是新功能也不是修 bug） |
| `test` | 增加或修改测试 |
| `chore` | 构建、依赖、工具链 |

示例：

```bash
feat(miniprogram): 新增AI识图页面 capture
fix(server): 修复 JWT 过期后未刷新的问题
docs: 补充部署文档的 HTTPS 配置说明
chore: 升级 fastapi 到 0.110
```

## 4. 开发流程（一次完整改动）

```bash
# 1. 切到 main 并拉最新
git checkout main
git pull

# 2. 新建功能分支
git checkout -b feat/<name>

# 3. 写代码，本地跑测试
cd server && pytest
# 小程序用微信开发者工具预览

# 4. 暂存 + 提交
git add .
git commit -m "feat: xxx"

# 5. 推送
git push -u origin feat/<name>

# 6. 在 GitHub 上开 Pull Request，填写改动说明
# 7. 等 Review 通过后合并到 main（推荐 Squash and merge）
```

## 5. 敏感信息保护（强制）

以下内容**禁止**提交到仓库：

- 真实数据库密码、Redis 密码
- 微信小程序 `AppID` / `AppSecret`（生产）
- 百度/阿里云 AI 服务的 `API_KEY` / `API_SECRET`
- 对象存储（OSS）AccessKey / SecretKey
- JWT 密钥、生产域名 SSL 证书
- 甲方原始比选文件（含项目编号、预算、联系人电话等敏感信息，已在 `.gitignore` 中屏蔽 `*.docx`）

正确做法：

- 所有密钥写在本地 `server/.env`，**仓库里只保留 `server/.env.example` 作为模板**
- 小程序 AppID 用 `touristappid` 等占位值，发布前在开发者后台替换
- 如果不小心提交了密钥，立刻在对应平台 **revoke** 该密钥，并在 GitHub 上用 `git filter-repo` 清历史（或新建仓库重传）

## 6. 评审（Code Review）要点

Reviewer 请重点关注：

- [ ] 改动是否符合本次任务目标，没有夹带无关修改
- [ ] 是否影响接口契约（API、数据库 schema）
- [ ] 是否引入新的依赖，并写进 `requirements.txt`
- [ ] 是否包含测试用例
- [ ] 是否涉及 `.env`、`server/data/` 等敏感/运行时目录
- [ ] 是否有合规风险（涉及健康数据、未成年人、个人信息）

## 7. 文档维护

- 任何架构、接口、部署变更必须同步更新 `docs/`
- 新增模块需在 [`docs/README.md`](./docs/README.md) 表格中登记
- 合规相关内容统一收口到 [`docs/compliance.md`](./docs/compliance.md)

## 8. 联系方式

- 项目经办：何大学（成都市疾控中心营养与食品安全科）
- 联系电话：87033314
- 技术对接：在 GitHub 仓库开 Issue 或 PR 留言

---

> 本约定适用于「营养与食品安全 AI 小助手」项目实施周期（合同签订日至 2027-07-31）。
> 如需调整请开 Issue 讨论后由负责人修改本文件。