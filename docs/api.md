# API 规范

所有 REST 接口统一前缀：`/api/v1`，使用 JSON 通讯，鉴权通过 `Authorization: Bearer <jwt>`。

## 统一响应

```json
{
  "code": "OK",
  "message": "success",
  "data": { ... }
}
```

业务错误（4xx）会返回业务码，例如 `VALIDATION_ERROR`、`USER_NOT_FOUND`、`MEAL_NOT_FOUND`、`EMPTY_IMAGE`、`BAD_MEAL_ID`、`BAD_USER_ID`、`INTERNAL_ERROR`。

## 接口清单

### 鉴权

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/wechat` | 微信 code 换 JWT |
| POST | `/auth/bind-phone` | 绑定手机号 |

### 用户

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/users/me` | 获取档案 |
| PUT  | `/users/me` | 更新档案 |
| GET  | `/users/me/quota` | 今日分析配额 |

### 膳食

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/meals/analyze` | 上传图片进行识别（base64） |
| GET  | `/meals/{id}/report` | 单次膳食报告 |
| GET  | `/meals/latest/report` | 最近一次报告 |

### 报告

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/reports/today` | 今日摄入汇总 |

### 知识库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/knowledge` | 列表（category 必填） |
| GET  | `/knowledge/{id}` | 详情 |

### GIS

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/gis/mushroom-risk?city=chengdu` | 风险点列表 |
| GET  | `/gis/mushroom-risk/{id}` | 风险点详情 |

### 视觉识别（中转）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/vision/dish` | 直接调用识别 API（内部调试用） |

### 管理后台

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/admin/stats` | 统计概览 |

## 示例

### 登录

```http
POST /api/v1/auth/wechat
Content-Type: application/json

{ "code": "wx-login-code" }
```

```json
{
  "token": "eyJhbGciOi...",
  "profile": { "id": 1, "nickname": "微信用户" }
}
```

### 上传膳食图片

```http
POST /api/v1/meals/analyze
Authorization: Bearer <token>
Content-Type: application/json

{ "imageBase64": "data:image/jpeg;base64,..." }
```

```json
{
  "mealId": 12,
  "items": [
    { "name": "米饭", "grams": 150, "kcal": 195, "protein": 4, "fat": 0.5, "carbs": 43, "sodium": 5, "confidence": 0.97 }
  ],
  "totalKcal": 595,
  "totalProtein": 29,
  "totalFat": 22.5,
  "totalCarbs": 67,
  "totalSodium": 1005
}
```

### 获取知识库列表

```http
GET /api/v1/knowledge?category=guide&page=1&page_size=20
```

```json
{
  "items": [
    { "id": 1, "title": "中国居民膳食指南核心要点", "category": "guide" }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```