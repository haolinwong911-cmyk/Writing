# 公众号文章爬取

从一条微信公众号文章链接**免费**提取全文，转成 Markdown。免登录、无需 API key、零费用。

## 能做什么
- 输入一条 `https://mp.weixin.qq.com/s?...` 文章链接，输出一个 `.md` 文件。
- 自动识别三种文章形态：普通图文、文字型小绿书、纯图片小绿书（图片存为 `![]()` 列表）。
- 自动提取：标题、公众号名、发布时间、正文、图片。
- 输出带 front matter（title/author/published/source），方便二次处理。

## 安装依赖
```bash
pip install beautifulsoup4 lxml requests
```
（`requests` 可选；不装会自动用标准库 urllib，功能相同。）

## 用法
```bash
# 单篇
python scripts/wx_extract.py "https://mp.weixin.qq.com/s?__biz=xxx&mid=xxx" -o ./wx_articles

# 多篇（自动限速 1.5s/条）
python scripts/wx_extract.py "URL1" "URL2" "URL3" -o ./wx_articles

# 从文件读链接列表（每行一条，# 开头为注释）
python scripts/wx_extract.py --file urls.txt -o ./wx_articles
```

## 输出
```
wx_articles/
└── 20251124_我用 Gemini 3 一口气做了 10 个应用，附教程.md
```
文件内容：
```markdown
---
title: "我用 Gemini 3 一口气做了 10 个应用，附教程"
author: "空格的键盘"
published: "2025-11-24 08:17:10"
source: "http://mp.weixin.qq.com/s?__biz=..."
---

（正文，图片为 ![]() 形式）
```

## 常见失败
| 终端提示 | 含义 | 怎么办 |
|---|---|---|
| 触发微信风控验证页 | 出口 IP 被临时限流，**不是文章删除** | 静置 10~30 分钟再试，或换网络 |
| 文章已被发布者删除 | 文章真的没了 | 换一篇 |
| 正文为空或过短 | 页面结构可能变了 | 报错信息反馈给维护者 |

## 注意
- 默认 1.5s/条的限速是防微信风控的，一次跑 ~20 篇以内比较安全。
- 提取内容仅供个人存档分析使用，注意版权。
