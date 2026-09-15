# 历史占位说明

本文件描述早期的占位图标方案，当前版本已不再使用。实际页面及 tabBar 图标位于 `images/ui/`，其来源和授权见 [SOURCES.md](ui/SOURCES.md)。当前底栏为 5 个入口，“调查评估”已更名为“健康评估”。

当前目录下需要为新的 4 个 tabBar 板块添加图标：

| 文件名 | 用途 | 建议颜色 |
|--------|------|---------|
| survey.png / survey_active.png | 调查评估 | 绿色系 |
| checkin.png / checkin_active.png | 打卡指导 | 橙色系 |
| consult.png / consult_active.png | 免费咨询 | 红色系 |
| science.png / science_active.png | 科普互动 | 蓝色系 |

## 解决方案

### 方案 1：在微信开发者工具中生成（推荐）
1. 打开微信开发者工具
2. 右键 images 文件夹
3. 选择「新建文件」
4. 使用 emoji 截图工具或在线图标生成器（如 https://www.iconfont.cn/）

### 方案 2：使用在线图标网站
- https://www.iconfont.cn/
- https://www.flaticon.com/
- 搜索关键词：survey / checkin / consult / science
- 下载 24x24 PNG 图标

### 方案 3：临时方案（不推荐）
删除 app.json 中的 tabBar 中除首页和我的之外的4个图标配置
```
{
  "pagePath": "pages/survey/survey",
  "text": "调查评估"
  // 删掉 iconPath 和 selectedIconPath 字段
}
```
这样 tabBar 会显示为文字（不带图标）。

### 方案 4：使用 unicode emoji（实验性）
将 iconPath 指向 SVG 文件：
- 注意：微信小程序 tabBar 不支持 emoji 直接作为图标
- 必须使用 PNG/JPG 格式的图片文件
