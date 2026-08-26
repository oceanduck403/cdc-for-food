# 项目文档索引

| 文档 | 路径 | 说明 |
| --- | --- | --- |
| 总体架构 | [architecture.md](./architecture.md) | 系统架构、数据流、关键决策 |
| API 规范 | [api.md](./api.md) | REST 接口约定、错误码、示例 |
| 部署指南 | [deployment.md](./deployment.md) | 本地、Docker、生产部署 |
| 合规与隐私 | [compliance.md](./compliance.md) | 隐私协议、数据合规、健康免责声明 |
| 阶段路线图 | [roadmap.md](./roadmap.md) | P0-P5 长期计划 |
| 招标文件要点 | [procurement-brief.md](./procurement-brief.md) | 比选文件摘要 |
| 上线商用清单 | [go-live-checklist.md](./go-live-checklist.md) | 注册小程序/选类目/域名备案/云资源/类目资质 |
| 数据流图（Mermaid） | [diagrams/dataflow.md](./diagrams/dataflow.md) | 关键流程图 |
| 小程序开发工具手册 | [miniprogram-devtools.md](./miniprogram-devtools.md) | 微信开发者工具导入、本地/真机预览、调试与排查 |
| 隐私政策 | [legal/privacy-policy.md](./legal/privacy-policy.md) | 正式版隐私政策（小程序后台必填） |
| 用户服务条款 | [legal/user-terms.md](./legal/user-terms.md) | 正式版用户服务条款 |
| 类目审核说明 | [legal/category-review-doc.md](./legal/category-review-doc.md) | 健康保健类目审核提交用 |
| ICP 备案模板 | [legal/icp-template.md](./legal/icp-template.md) | 备案信息模板与流程 |
| 生产环境部署手册 | [deploy-prod-manual.md](./deploy-prod-manual.md) | Nginx + HTTPS + Docker + systemd |
| 微信支付接入 | [payment-guide.md](./payment-guide.md) | 微信支付开通、配置、测试指南 |
| 离线地图功能 | [offline-map.md](./offline-map.md) | 毒蘑菇风险地图离线使用说明 |

## 协作约定

- 文档以 Markdown 形式维护，CI 可选地校验链接与拼写
- 章节顺序：先讲目标，再讲结构，最后讲变更与运维
- 所有设计决策附「决策依据 / 备选 / 风险」三段式说明
- 涉及合规与安全的内容统一收口在 `compliance.md`