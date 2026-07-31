# 关键数据流

## 拍照识膳食

```mermaid
sequenceDiagram
    participant U as 用户
    participant MP as 小程序
    participant API as FastAPI 后端
    participant VL as 限流(Redis)
    participant VS as 视觉 API
    participant DB as PostgreSQL

    U->>MP: 拍照 / 选图
    MP->>MP: 压缩 + base64
    MP->>API: POST /meals/analyze
    API->>VL: 校验当日次数
    VL-->>API: OK / 超限
    API->>VS: 识别菜品
    VS-->>API: 菜品列表 + 置信度
    API->>API: 营养素换算
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