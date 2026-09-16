# 关键数据流

> 当前 AI 限额由 PostgreSQL 记录。下方毒蘑菇 GIS 仅保留为历史设计，不在当前小程序页面中开放。

## 拍照识膳食

```mermaid
sequenceDiagram
    participant U as 用户
    participant MP as 小程序
    participant API as FastAPI 后端
    participant Q as 用量记录(PostgreSQL)
    participant AI as Qwen 服务
    participant DB as PostgreSQL

    U->>MP: 拍照 / 选图
    MP->>MP: 压缩 + base64
    MP->>API: POST /ai/food-analysis
    API->>Q: 原子预占当日次数
    Q-->>API: OK / 超限
    API->>AI: 发送当次食物图片
    AI-->>API: 结构化食物与营养估算
    API->>API: 校验与规范化
    API->>DB: 写入 Meal/MealItem
    API-->>MP: 返回报告数据
    MP->>U: 渲染个性化报告
```

## 知识库检索

```mermaid
flowchart LR
    U[用户] --> MP[小程序]
    MP -->|GET /knowledge| API[FastAPI]
    API --> DB[(PostgreSQL)]
    DB --> API --> MP --> U
```

## 毒蘑菇 GIS

```mermaid
flowchart LR
    U[用户] --> MP[小程序地图]
    MP -->|GET /gis/mushroom-risk| API
    API --> DB[(PostgreSQL)]
    DB --> API
    API --> MP
    MP -->|点击 marker| MP
    MP -->|GET /gis/mushroom-risk/{id}| API
    API --> MP
```
