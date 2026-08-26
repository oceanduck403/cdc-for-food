# 疾控知识库同步

## 功能

定时从权威公众号抓取健康科普文章，生成小程序可用的知识库 JSON。

## 数据源

| 公众号 | 分类 | 说明 |
|--------|------|------|
| 广东疾控 | 疾病预防 | 广东省疾病预防控制中心 |
| 中国疾控中心 | 疾病预防 | 中国疾病预防控制中心 |
| 营养与健康 | 营养膳食 | 中国疾控中心营养与健康所 |
| 中国好营养 | 营养膳食 | 中国营养学会 |
| 中国营养界 | 营养膳食 | 中国营养学会 |

## 使用方式

### 本地运行

```bash
cd sync
npm install
npm run sync
```

### 自动同步（GitHub Actions）

推送到 GitHub 后，每天会自动运行，生成 `data/knowledge.json`。

数据访问地址：
```
https://raw.githubusercontent.com/{user}/{repo}/main/sync/data/knowledge.json
```

## 小程序接入

将 `request.js` 中的 `useMock` 改为 `false`，添加知识库 API 地址即可。

## 目录结构

```
sync/
├── sync.js          # 同步脚本
├── sources.js       # 数据源配置
├── package.json     # 依赖配置
├── data/            # 生成的数据（.gitignore）
│   ├── knowledge.json
│   └── knowledge-index.json
└── .github/
    └── workflows/
        └── sync.yml  # GitHub Actions 配置
```
