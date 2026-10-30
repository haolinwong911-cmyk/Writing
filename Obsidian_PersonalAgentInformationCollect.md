# 公众号 / 小红书文章收集与 Obsidian 同步指南

> 目标：把在微信、小红书看到的文章和图片，自动整理成 Markdown 笔记，经 GitHub 私有仓库同步到本地 Obsidian 知识库。
> 本文档已去除所有敏感信息（AppID、AppSecret、license、GitHub 令牌等），凭据一律用占位符表示。

## 一、整体架构

```
微信文章 / 小红书笔记
        │
        ▼
  沙箱/服务器端抓取脚本（正文 + 配图）
        │
        ▼
  整理成 Markdown 笔记（frontmatter + 正文 + 图片引用）
        │
        ▼
  git 提交并推送到 GitHub 私有仓库（obsidian_inbox）
        │
        ▼
  Mac 端 Obsidian Git 插件自动拉取（每 10 分钟）
        │
        ▼
  本地 Obsidian 库呈现（Inbox/ 收件箱 → 每周归档到分类文件夹）
```

核心思路：**采集端只管抓内容，Obsidian 端只管用 Git 拉取**，中间靠一个 GitHub 私有仓库做中转。双向同步，手机/网页上收藏的内容最终都会落到本地库。

## 二、目录约定

仓库（Obsidian 库）结构：

```
obsidian_inbox/
├── Inbox/
│   ├── README.md              # 收件箱使用说明
│   ├── 01.想法存储/           # 归档分类
│   ├── 02.AI动手实践/         # 归档分类
│   ├── 03.AI硬件/             # 归档分类（新主题向下续编号）
│   ├── attachments/           # 所有配图、视频附件
│   └── <待整理笔记>.md        # 新笔记先进 Inbox 根目录
```

笔记文件带序号前缀（如 `05. AI硬件最大的幻觉…….md`），图片统一放 `Inbox/attachments/`，命名 `YYYYMMDD-标题缩写-NN.jpg`；子文件夹内笔记用相对路径 `../attachments/...` 引用图片。

笔记格式（统一 frontmatter）：

```markdown
---
title: 文章标题
tags: [来源平台, 主题标签...]
created: 收录日期
source: 原文完整链接
author: 作者
published: 原文发布日期
status: inbox
---
```

## 三、公众号文章收集

### 3.1 两条通道

| 通道 | 适用场景 | 费用 |
|------|----------|------|
| **cimidata 接口（主通道）** | 稳定、抗风控，默认一律走这条 | 约 0.01 元/篇 |
| **直连抓取（备用）** | 接口失效/欠费时兜底 | 免费，但机房 IP 容易触发微信风控 |

### 3.2 cimidata 接口调用方法

服务文档：`https://www.showdoc.com.cn/2265380957870963/11123545047367523`
接口域名：`https://api.cimidata.com`

**第一步：换取 access_token**

```http
POST /api/v2/token
Content-Type: application/json

{
  "app_id": "<你的 AppID>",
  "app_secret": "<你的 AppSecret>"
}
```

返回 `data.access_token`。token 有效期 **7 天**，客户端本地缓存、到期前 1 天自动刷新；token 失效时自动强制刷新并重试一次。

**第二步：抓取文章全文**

```http
POST /api/v3/articles/detail?access_token=<token>
Content-Type: application/json

{
  "url": "<公众号文章链接>",
  "need_text": true
}
```

返回 `data.html`（正文富文本，可直接转 Markdown）和 `data.plain_text`（纯文本）。也有 `/api/v2/articles/detail` 返回含标题作者的完整页面 HTML。

**第三步：查余额（每批抓完后必调）**

```http
GET /api/v2/user/balance?access_token=<token>
```

返回 `data.balance`，单位为**分**。每次处理完告知本次花费与余额。

> 凭据管理：`app_id` / `app_secret` 只存在本地 `cimi_credentials.json`，**禁止提交到任何仓库、禁止写入文档或记忆**。凭据失效时回退直连抓取，并提醒续费。

### 3.3 沙箱网络细节

沙箱 DNS 可能不解析 `api.cimidata.com`：先用 DoH（如 `https://dns.alidns.com/resolve?name=<域名>&type=A`）查 A 记录，写入 `/etc/hosts` 后直连。xhslink.cn 等短链同理（见第四节）。

### 3.4 直连备用抓取要点

- 带浏览器 `User-Agent` + `Referer: https://mp.weixin.qq.com/`，网络异常自动重试 4 次。
- 支持三种页面结构：① 普通图文（`#js_content`）② 文字型小绿书（JS content 字段）③ 纯图片小绿书（`cdn_url` 序列）。
- 失败自动分类：微信风控 / 文章删除 / 页面结构变化。
- **风控注意**：机房 IP 会触发微信风控——静置 10–30 分钟、不要连续重试、一批不超过 20 篇。

### 3.5 入库处理

脚本（`wx_to_ob.py` 思路）做的事：

1. 调接口拿正文 HTML → 转 Markdown；
2. 正文里的微信图床图片逐张下载到 `Inbox/attachments/`（带 `Referer`），并把链接改写为本地相对路径；
3. 组装 frontmatter（标题、作者、发布时间、原文链接），保存为 `Inbox/<标题>.md`；
4. git 提交并推送（见第五节）。

## 四、小红书笔记收集

小红书无需登录即可抓到图文，关键在短链解析和图片提取。

### 4.1 短链解析（xhslink.cn）

1. 沙箱 DNS 解析不了 `xhslink.cn`：用 DoH（`https://doh.pub/dns-query?name=xhslink.cn&type=A`，`accept: application/dns-json`）拿 A 记录；
2. `curl --resolve "xhslink.cn:443:<IP>"` 直连访问短链，得到 **302 跳转**；
3. `Location` 头即真实地址：`https://www.xiaohongshu.com/discovery/item/<笔记ID>?...&xsec_token=...`。

> **`xsec_token` 会过期**，保存原文链接时要带上 token 的完整地址。

### 4.2 抓正文和图片

用手机 UA 直接 curl 笔记页（HTTP 200，免登录），然后：

1. HTML 里的 `\u002F`、`\/` 还原为 `/`；
2. 定位 `"imageList"` JSON 段，正则提取 `sns-webpic-qc.xhscdn.com` 图片地址；`!h5_1080jpg` 后缀是 1080 原图（每个图片 ID 有原图和缩略两个变体，去重后取原图）；
3. 下载图片必须带 `Referer: https://www.xiaohongshu.com/`，否则拒绝；
4. 正文从 `og:description` 或笔记 JSON 的 `desc` 字段取全文；作者（`nickname`）、发布时间（`time` 毫秒时间戳）、IP 属地（`ipLocation`）同样从 JSON 提取。

### 4.3 视频类笔记

- 封面：同样从 `imageList` 取 `h5_1080jpg`；
- 视频：从 JSON 取 `masterUrl`（`sns-video-*.xhscdn.com` 的 mp4），带同样 Referer 下载。

### 4.4 入库标准

图片下载到 `Inbox/attachments/`，笔记必须带**标题、原文完整链接、全文、图片引用**（`![[attachments/...]]` 或相对路径），另附核心要点和备注。

## 五、Git 同步到 Obsidian

### 5.1 链路

- 中转仓库：GitHub 私有仓库（如 `obsidian_inbox`），remote 用**最小权限 fine-grained 令牌**（仅该仓库 Contents 读写）写在 git remote URL 里，不写入任何文档/记忆；
- Mac 端：Obsidian 库本体放在 Git 仓库目录下，安装 Obsidian Git 插件开启自动拉取（每 10 分钟）+ 自动备份推送，即**双向同步**；
- 为降低 GitHub 偶发 502 概率，git 已设置 `git config http.version HTTP/1.1`。

### 5.2 推送纪律（重要）

1. **任何改动前先 `git pull`**，以远端为准叠加改动，绝不 `push -f` 强推；
2. 推送统一走重试脚本：最多 5 次、间隔递增（10s → 20s → 40s…），每次失败后用 `git ls-remote` 核对远端提交号——GitHub 偶发在服务端已接收时仍返回 5xx，核对可避免无谓重试；
3. 重试全部失败也不丢数据：笔记保留在本地提交里，下次交互或定时唤醒时补推，**推送成功并经远端提交号核对才算同步完成**；
4. 与用户在 Mac 端的改动冲突时，不擅自取舍，先询问。

### 5.3 每周归档

每周日 21:00 定时执行：先拉远端，把 Inbox 根目录已整理笔记按主题移动到对应编号分类文件夹并推送；同时生成本周收藏盘点（篇数、主题分布、2–3 篇值得精读推荐）。本周没有新笔记时不发送、不打扰。

## 六、常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| 推送返回 502/504 | GitHub 服务端偶发不稳定 | 重试脚本自动处理；远端提交号核对兜底 |
| 小红书链接打不开 | `xsec_token` 过期 | 重新从分享口令解析一次短链 |
| 小红书图片下载 403 | 缺 Referer | 请求头加 `Referer: https://www.xiaohongshu.com/` |
| 公众号抓取触发验证 | 机房 IP 风控 | 静置 10–30 分钟，勿连续重试，一批 ≤20 篇 |
| cimidata token 失效 | 超过 7 天未用 | 自动强制刷新重试；仍失败则检查凭据/续费 |
| 沙箱解析不了目标域名 | 沙箱 DNS 限制 | DoH 查 A 记录 + `curl --resolve` 或写 `/etc/hosts` |

## 七、凭据与安全清单

以下信息**只存本地配置文件，不进仓库、不进文档、不进记忆**：

- cimidata 的 `app_id` / `app_secret`（`cimi_credentials.json`）
- GitHub fine-grained 令牌（仅存在 git remote 配置中）
- 任何账号、密钥、license 类字段

分享或交接时，一律以占位符（`<你的 AppID>` 等）替代，并核对 diff 中不含真实凭据。
