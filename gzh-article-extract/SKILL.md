---
name: 公众号文章爬取
description: 从一条微信公众号文章链接免费提取全文并转成 Markdown（免登录、无需任何 API key、零费用）。严格区分三种内容结构：普通图文文章（正文在 #js_content）、文字型小绿书（正文在页面 JS 的 content 字段）、纯图片小绿书（正文是 cdn_url 图片序列）。自动提取标题、公众号名、发布时间，图片转 ![]() 链接，输出带 front matter 的 .md。当用户提供公众号文章链接（形如 https://mp.weixin.qq.com/s?...），要求「提取这篇文章/抓正文/转 Markdown/存成文档/获取文章内容」时使用本 skill。只处理用户给定的链接，不主动批量爬取（批量/全量采集是另一个 skill 的职责）。
agent_created: true
---

# 公众号文章爬取（单篇 / 免登录 / 免费）

给一条公众号文章链接，直接抓公网页面，把正文提取成 Markdown。**不需要登录、不需要 cookie、不需要任何 API key、不产生任何费用。**

## 概述与边界
- **做什么**：用户给 1 条（或几条）文章链接 → 提取标题、公众号名、发布时间、正文、图片 → 每篇存一个 `.md`。
- **不做什么**：不批量爬整个公众号的历史文章（那是 `gzh-research` 的职责，需要付费接口拿文章列表）；不获取阅读量/点赞等指标（同样走付费接口）。本 skill 只碰用户**明确给出链接**的文章。
- **依赖**：Python 3 + `beautifulsoup4` + `lxml`（`requests` 可选，没装则自动降级 urllib）。

## 触发后第一件事
确认用户给的是**文章链接**（形如 `https://mp.weixin.qq.com/s?__biz=...&mid=...`），然后直接跑脚本，不需要问东问西。如果用户给的是公众号名称/主页而不是文章链接，告诉用户：本 skill 需要一条具体文章链接，请对方发一篇该公众号的文章过来。

## 执行流程（一步到位）
```
python scripts/wx_extract.py "<文章URL>" -o <输出目录>
```
- 多条链接：`python scripts/wx_extract.py "<URL1>" "<URL2>" -o <输出目录>`（自动限速 1.5s/条）。
- 链接放在文件里：`python scripts/wx_extract.py --file urls.txt -o <输出目录>`。
- 输出目录默认 `./wx_articles/`；文件名 `<YYYYMMDD>_<标题>.md`（无发布时间时省略日期前缀）。
- 成功后向用户报告：类型（图文/小绿书）、标题、公众号、字数、图片数、文件路径。

## 三种内容结构（核心知识，必须理解）
微信的文章页有三种形态，解析方式完全不同：

| 类型 | 页面特征 | 正文位置 | 本 skill 的处理 |
|---|---|---|---|
| 普通图文文章 | 有 `#js_content` 节点 | `#js_content`（服务端渲染） | BeautifulSoup 直接解析 |
| 文字型小绿书 | 无 `#js_content`，页面 JS 里有 `content:'...'` | JS 字符串，含 `\xHH`/`\n` 转义 | 取出反转义（`\x3c`→`<`）再解析 |
| 纯图片小绿书 | `content` 字段为空 | 一串 `cdn_url:'...'` 图片地址 | 按序去重，存成 `![]()` 图片列表，加说明头 |

**只认 `#js_content` 会把所有小绿书误判为“正文为空”**——这是最常见的坑。脚本已按上表顺序依次尝试并自动兜底。

## 元数据提取规则
- **标题**：`og:title` → `#activity-name`。
- **公众号名**：`#js_name` → `var nickname` → `window.name`（小绿书）→ `nick_name:'...'`（小绿书 JSON 块）。
- **发布时间**：`var ct="unix秒"` → `create_time`/`publish_time`（unix 或字符串）→ 提取不到则留空，文件名省略日期前缀。
- **图片**：微信图片是懒加载，真实地址在 `data-src` 属性（不是 `src`），统一转成 `![](https://...)`。
- **front matter**：`title / author / published / source` 四行，方便后续程序化处理。

## 输出示例
```markdown
---
title: "我用 Gemini 3 一口气做了 10 个应用，附教程"
author: "空格的键盘"
published: "2025-11-24 08:17:10"
source: "http://mp.weixin.qq.com/s?__biz=..."
---

![](https://mmbiz.qpic.cn/...)

我用 Gemini 3 Pro 两三个小时做了十个小应用...
```

## 失败处理（重要：区分三种失败）
脚本失败时会给出明确原因，按类别处理：
1. **微信风控验证页**（约 17KB、含 `verify`/`secitptage` 字样）：不是文章问题，是出口 IP 被临时限流。**告诉用户“触发了微信风控，不是文章删除”，建议静置 10~30 分钟再试，或换网络/代理**。不要疯狂重试——越刷越久。
2. **文章已被删除**（页面含“该内容已被发布者删除”等标记）：如实告知用户该文章已失效。
3. **其他**（网络超时、页面结构变化）：报告错误信息，可重试一次。

## 频率与礼仪
- 默认每条之间 sleep 1.5s；一次不要超过 ~20 条。用户要大量提取时，提醒分批、加 `--sleep`。
- 提取的内容仅用于用户个人存档/分析，提醒用户遵守公众号内容的版权与使用规范。

## 关键坑速查（详见 references/pitfalls.md）
1. 小绿书没有 `#js_content`，必须走 `content` 字段 / `cdn_url` 兜底，否则整批误判“正文为空”。
2. 图片地址在 `data-src`，不在 `src`。
3. 微信风控是 **IP 级**的：高频请求返回验证页，静置会自愈；失败页特征是“小体积 + verify 字样”，别误判成文章删除。
4. 链接里的 `sessionid`/`scene` 等参数不影响抓取，可原样使用；`#rd` 后缀可去掉。
5. 发布时间用 `var ct`（unix 秒）最可靠，注意时区按本地时间呈现即可。

## Resources
- `scripts/wx_extract.py` — 自包含提取脚本（三种结构 + 元数据 + 风控识别 + 限速）。`python wx_extract.py <URL...> [-o 目录] [--sleep 秒] [--file urls.txt]`。
- `references/pitfalls.md` — 完整踩坑与解法清单（含风控自愈机制、页面结构变迁史）。
- `README.md` — 用法入门（安装依赖 → 跑一条 → 看输出）。
