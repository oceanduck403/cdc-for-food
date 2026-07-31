# 营养与食品安全 AI 小助手 · 委托服务项目仓库

成都市疾病预防控制中心「营养与食品安全 AI 小助手」微信小程序及配套后端的代码与文档根目录。

## 目录结构

```
疾控/
├── README.md                本文件
├── .gitignore               Git 忽略配置
├── docs/                    项目文档（架构、API、部署、合规、路线图）
├── miniprogram/             微信小程序前端（原生）
└── server/                  后端服务（Python FastAPI）
```

## 模块一览

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 小程序前端 | `miniprogram/` | 原生微信小程序，包含基础框架、用户管理、AI 识图、个性化建议、知识库、GIS 地图等页面 |
| 后端服务 | `server/` | FastAPI 应用，提供鉴权、用户档案、膳食评估、知识库、GIS 等 API |
| 项目文档 | `docs/` | 架构图、接口规范、部署指南、合规要点、阶段路线图、招标文件要点 |

## 快速开始

### 后端（FastAPI）

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env       # 根据实际情况修改
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

接口文档：<http://localhost:8000/docs>

### 小程序

微信开发者工具导入步骤、模拟器/真机调试、常见问题排查见
[`docs/miniprogram-devtools.md`](docs/miniprogram-devtools.md)。

## 关键约束（来自比选文件）

- 预算 4.7 万元（包干价）
- 服务期：合同签订日起至 2027-07-31
- 履约地点：成都市武侯区龙祥路 4 号
- 验收：账号可登录、模块稳定、数据准确
- 售后：验收合格后 1 年免费咨询

## 阶段路线图速览

- **P0** 立项与需求固化
- **P1** 总体设计与原型
- **P2** MVP（基础框架 + AI 识图 + 个性化建议 + 知识库 V1）
- **P3** 业务闭环（医患互动、知识库 V2、GIS 动态图层）
- **P4** 试点运行与正式验收
- **P5** 1 年免费咨询与持续运营

完整计划参见 [`docs/roadmap.md`](docs/roadmap.md)。

## 联系方式

- 项目经办：何大学（成都市疾控中心营养与食品安全科）
- 联系电话：87033314

> 本仓库由承包团队依据比选文件建立，配置与代码需经甲方书面确认后投入使用。