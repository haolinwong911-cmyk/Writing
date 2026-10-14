---
name: gzh-research
description: 端到端采集并存档一个微信公众号的全部历史文章。用次幂数据(cimidata)付费 API 取发文列表和阅读/点赞/在看/评论/分享指标，免登录直抓 mp.weixin.qq.com 正文（严格区分「普通图文文章」与「小绿书/图片消息」两种页面结构），多标签内容分类，最终汇总成带指标和分类的 Excel/CSV 表格。当用户要求「采集/爬取某个公众号的全部历史文章并存档」「拉公众号发文+阅读量等数据做成表格」「导出公众号文章为 Markdown」时使用本 skill。涉及次幂付费接口，调用前必须先向用户报价并确认。
agent_created: true
---

# 微信公众号全量采集与存档

## 概述
把一个公众号的全部历史文章抓下来、存成 Markdown、并汇总成带「内容分类 / 类型 / 阅读·点赞·在看·评论·分享」的表格。两条取数通路：
- **次幂数据(cimidata)付费 API**：取发文列表、取文章互动指标（按次计费）。
- **免登录直抓 mp.weixin.qq.com**：取文章正文（免费，但必须区分普通图文与小绿书两种结构）。

## 依赖（自包含，别人拿去即可跑）
- 本 skill 自带次幂 API 客户端 `scripts/cimi_client.py`（token/历史列表/互动指标/余额，内置限速与重试），**无需再装其它 skill**。若本机恰好也装了 `cimidata-gzh-collect` skill，可参考其 `references/endpoints.md`、`references/errors.md` 作补充。
- 运行环境：Python 3 + `requests` + `beautifulsoup4` + `lxml`（xlsx 还需 `openpyxl`）。用托管 venv：`/Users/haolinwong/.workbuddy/binaries/python/envs/default/bin/python`。
- 目录结构：`SKILL.md`(主指南) / `README.md`(给人看的用法) / `scripts/`(cimi_client.py、scrape_content.py、build_report.py) / `references/`(pitfalls.md、cimi_quickref.md)。

## 第一步：向用户索取凭证（按固定格式，避免误用）
动手前必须拿到三样，引导用户按下面的块提供：
```
app_id:        （次幂用户名）
app_secret:    （次幂密钥）
目标公众号:    <名称>  或  wxid: gh_xxxx
```
- **app_id / app_secret 在哪注册**：打开 https://www.cimidata.com 注册并登录 → 打开 https://www.cimidata.com/api-service 开通 API 服务 → 在同页面创建 app_id 和密钥。按次计费，页面有价目表和余额。
- **wxid 怎么拿**：方法1 访问 https://www.cimidata.com/tools/wxid 直接查；方法2 浏览器打开该公众号任意文章 → `Ctrl+U` 看源码 → 搜 `var user_name`，`gh_` 开头的字符串就是。若用户只给了公众号名称，用次幂 `POST /api/v3/accounts/search`（0.10元，计费→先报价）搜出 wxid。
- **安全**：凭证只从环境变量或函数参数读取，**绝不写死进任何 .py/.json/日志**。后台跑脚本时必须显式传 `APP_ID`/`APP_SECRET` 环境变量，否则脚本 `KeyError` 秒退。

## 第二步：付费接口铁律（涉及钱，务必遵守）
次幂所有接口按次计费。**调用任何计费接口前，必须**：
1. 先查余额（`GET /api/v2/user/balance`，免费）；
2. 计算预计花费 = 篇数 × 单价；
3. 明确告诉用户：要调用哪个接口、单价、总价、当前余额是否够；
4. **得到用户明确同意后才执行**。执行中若发现将要超出已确认的预算，立即停止并再次确认，不擅自超花。

常用单价（**参考价，以 https://www.cimidata.com/api-service 实时价目表为准**）：
| 接口 | 用途 | 参考单价 |
|---|---|---|
| `/api/v3/accounts/search` | 按名称搜公众号拿 wxid | 0.10 元/次 |
| `/api/v2/articles/history` | 历史发文列表（约10篇/页） | 0.05 元/页 |
| `/api/v2/articles/data` | 阅读/点赞/在看 | 0.02 元/篇 |
| `/api/v2/articles/data2` | 阅读/点赞/在看/评论/分享 | 0.03 元/篇 |

不计费可重试的错误码：`6021`(阅读获取失败)、`5300`(列表失败)、`1004`(暂无数据，等30秒重试)、`429`(限流)、`1003`(链接转换失败)。`6020`=余额不足（接口未执行、不计费，此时停止并让用户充值）。

## 第三步：执行流程

### 步骤1 取发文列表（次幂 history，计费→先报价）
- 用自带脚本：`python scripts/cimi_client.py history <wxid> articles.json`（内部自动翻页，`last_id` 为 null 到底）。
- **去重坑（重要）**：翻页尾部会混入最近文章的重复项；这些重复项 URL 因微信 `sessionid` 参数不同而**不同**，按 `content_url` 去重无效。必须按**标题归一化**去重（去空白/去内联 HTML 标签/取前若干字）——去重放在步骤2的 `scrape_content.py` 里做。
- 产出 `articles.json`：`[{title, content_url, published_at, digest, idx}]`。

### 步骤2 直抓正文（免费，不走次幂）——严格区分两种结构
对每个 `content_url` 直接 `GET`（带浏览器 UA + `Referer: https://mp.weixin.qq.com/`）。**先判断页面属于哪种结构，再解析**：

1. **普通图文文章**：页面有 `#js_content` 元素（服务端渲染）→ 直接解析该节点转 Markdown。图片用 `data-src`（懒加载）。
2. **小绿书 / 图片消息**：页面**没有** `#js_content`，分两个子类：
   - **文字型小绿书**：正文在页面 JS 的 `content: '...'` 字段里（HTML 被转义成 `\x3c`/`\x3e`/`\x0a` 等）→ 按单引号字符串取出并反转义，再当 HTML 解析转 Markdown。
   - **纯图片小绿书**：`content` 字段为空 → 正文就是图片序列，正则提取所有 `cdn_url: '...'`（按出现顺序、去重）存成 `![](url)` 图片列表。
- 标题取 `og:title`；发布时间直接用步骤1的 `published_at`（避免 `var ct` 时区问题）；公众号名取 `#js_name`。
- 每篇存一个 `.md`（front matter：title/author/published/source + 正文），文件名用 `序号_标题.md`。
- **限速 ≥1 秒/篇**。详见 `references/pitfalls.md` 的风控说明。
- 复用脚本：`scripts/scrape_content.py`（输入 articles.json + 输出目录，已含三种结构解析、标题去重、断点续传、限速）。

### 步骤3 取互动指标（次幂 data2，计费→先报价确认）
- 用自带脚本：`python scripts/cimi_client.py data2 articles.json metrics.json`（断点续传，余额不足即停）。
- 字段映射（**命名反直觉，务必看清**）：`read_num`=阅读量、`old_like_num`=点赞、`like_num`=在看、`comment_count`=评论数、`share_num`=分享数。
- 实时读响应里的顶层 `balance`（单位:分）监控扣费；`6020` 立即停止。
- 限速 3 次/秒。已取的 URL 存 `metrics.json`，重跑跳过。

### 步骤4 汇总成表
- 复用脚本：`scripts/build_report.py`（输入 articles.json + 存档目录 + 可选 _classify/_metrics，输出 .xlsx/.csv）。
- 列：序号 / 发布时间 / 标题 / 内容分类 / 类型(文章·图文) / 访问链接 / 是否抓取到 / 阅读量 / 点赞 / 在看数 / 评论数 / 分享数 / 存档位置。
- **匹配已存 .md 用“文件名序号前缀(NNN_)”，不要用 front matter 的 source 链接**——标题含 HTML/换行会把 source 行顶出前端、导致按内容匹配漏判。
- 内容分类用**多标签**（中文逗号分隔）：接广告 / 产品测评 / 干货教程 / 产品发布 / 资讯观点 / 周刊合集 / 个人随笔 / 其他。判定以标题关键词为主、开头500字为辅；**接广告**靠：披露词(赞助/商单/恰饭/邀约/特约…) + 集中推广同一商业产品的“商单系列” + 促销话术(送会员/免费领/限时…)。此为启发式，边界样例需向用户说明可能需人工复核。

## 关键坑速查（详见 references/pitfalls.md）
1. **小绿书无 `#js_content`**——最初只认 `#js_content` 导致整批小绿书“正文为空”；必须按 content 字段 / cdn_url 兜底。
2. **微信风控是 IP 级**——高频直抓会返回验证页(`secitptpage/verify*.css`、约17KB、无正文)；静置冷却一段时间会自愈。本环境出口 IP 固定(走本地代理)，无 VPN 可切换。
3. **余额差一点会缺末尾几篇**——data2 跑大量时，先算 余额 vs 篇数×单价，差几篇就提前告知用户。
4. **后台脚本必带凭证环境变量**。
5. **去重按标题、匹配按文件名前缀**。

## Resources
- `scripts/cimi_client.py` — 次幂 API 自包含客户端（token/历史列表/互动指标/余额，限速+重试+断点续传）。`balance` / `history <wxid> <out.json>` / `data2 <articles.json> <out.json>`。凭证走环境变量 `APP_ID`/`APP_SECRET`。
- `scripts/scrape_content.py` — 免登录直抓正文（普通文章/文字型小绿书/纯图片小绿书）、标题去重、断点续传、限速。用法：`python scrape_content.py <articles.json> <输出目录> [--sleep 1.0]`。
- `scripts/build_report.py` — 组装汇总表（多标签分类、序号前缀匹配、指标列、Excel 着色）。用法：`python build_report.py <articles.json> <存档目录> [metrics.json] [-o 输出名]`。
- `references/pitfalls.md` — 完整踩坑与解法清单。
- `references/cimi_quickref.md` — 次幂接口/单价/错误码速查。
