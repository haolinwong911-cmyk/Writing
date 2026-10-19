#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章提取（免费、免登录、无需任何 API key）-> Markdown
================================================================
给一条（或多条）公众号文章链接，直接抓取公网页面，把正文提取成 Markdown。
严格区分三种内容结构：
  1. 普通图文文章  -> 正文在 #js_content（服务端渲染，直接解析）
  2. 文字型小绿书  -> 无 #js_content，正文在页面 JS 的 content:'...' 字段
                      （\\xHH / \\n 等转义，需取出反转义再解析）
  3. 纯图片小绿书  -> content 字段为空，正文是图片序列，提取所有
                      cdn_url:'...'（按序去重）存成 ![]() 图片列表

用法:
    python wx_extract.py <URL> [URL2 ...] [-o 输出目录] [--sleep 1.5]
    python wx_extract.py --file urls.txt [-o 输出目录]

输出（每篇一个文件，默认目录 ./wx_articles/）:
    <YYYYMMDD>_<标题>.md     front matter(title/author/published/source) + 正文
    无发布时间时文件名为 <标题>.md

依赖: beautifulsoup4 + lxml（requests 可选，装了更好；都没有则用 urllib）

退出码: 0=全部成功; 1=部分或全部失败（失败原因打印到终端）
"""
import os
import re
import sys
import json
import time
import argparse
from datetime import datetime

try:
    import requests
    _HAS_REQ = True
except Exception:
    _HAS_REQ = False
    import urllib.request
    import urllib.error

from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
HEADERS = {"User-Agent": UA,
           "Referer": "https://mp.weixin.qq.com/",
           "Accept-Language": "zh-CN,zh;q=0.9"}
_session = requests.Session() if _HAS_REQ else None

# 微信风控验证页特征（用于把「被风控」和「文章已删除」区分开）
RISK_MARKERS = ("secitptpage", "verify", "验证", "环境异常")
# 文章已删除特征
DELETED_MARKERS = ("该内容已被发布者删除", "该内容已被删除", "此内容无法查看",
                   "该公众号已迁移", "内容违规无法查看")


# ---------------------------------------------------------------- 抓取
def fetch(url, retries=4, timeout=25):
    """GET 一个 URL，返回 bytes。带简单重试。"""
    last = None
    for i in range(retries):
        try:
            if _HAS_REQ:
                r = _session.get(url, headers=HEADERS, timeout=timeout)
                return r.content
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa
            last = e
            time.sleep(2 + 2 * i)
    raise last


# ------------------------------------------------- HTML -> Markdown
BLOCK = {"p", "section", "div", "li", "ul", "ol", "blockquote", "figure",
         "figcaption", "table", "tr", "td", "th", "pre", "main", "article"}
SKIP = {"script", "style", "iframe", "noscript", "svg", "template"}
H_LEVEL = {"h1": "## ", "h2": "### ", "h3": "#### ",
           "h4": "##### ", "h5": "###### ", "h6": "###### "}


def _md_children(node, out):
    for child in node.children:
        name = getattr(child, "name", None)
        if name is None:
            out.append(str(child))
        elif name in SKIP:
            continue
        elif name == "img":
            # 微信图片是懒加载，真实地址在 data-src
            src = child.get("data-src") or child.get("src") or ""
            if src and src.startswith("http"):
                out.append("\n\n![](%s)\n\n" % src)
        elif name == "br":
            out.append("\n")
        elif name in ("strong", "b"):
            t = []
            _md_children(child, t)
            s = "".join(t).strip()
            if s:
                out.append("**%s**" % s)
        elif name in ("em", "i"):
            t = []
            _md_children(child, t)
            s = "".join(t).strip()
            if s:
                out.append("*%s*" % s)
        elif name == "code":
            t = []
            _md_children(child, t)
            s = "".join(t).strip()
            if s:
                out.append("`%s`" % s)
        elif name in H_LEVEL:
            t = []
            _md_children(child, t)
            s = "".join(t).strip()
            if s:
                out.append("\n\n%s%s\n\n" % (H_LEVEL[name], s))
        elif name == "hr":
            out.append("\n\n---\n\n")
        elif name == "li":
            t = []
            _md_children(child, t)
            s = "".join(t).strip()
            if s:
                out.append("\n- %s" % s)
        elif name == "blockquote":
            t = []
            _md_children(child, t)
            s = "".join(t).strip()
            if s:
                out.append("\n\n" + "\n".join("> " + ln for ln in s.split("\n")) + "\n\n")
        elif name == "a":
            t = []
            _md_children(child, t)
            s = "".join(t).strip()
            href = child.get("href", "")
            if href.startswith("http") and s:
                out.append("[%s](%s)" % (s, href))
            elif s:
                out.append(s)
        elif name in BLOCK:
            out.append("\n")
            _md_children(child, out)
            out.append("\n")
        else:
            _md_children(child, out)


def clean_md(text):
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_js_string(s, key):
    """从页面里提取 key:'...' 的 JS 字符串并反转义(\\xHH/\\n 等)。
    小绿书(图片消息)的正文放在 content 字段里，取最长的一个。"""
    best = None
    for m in re.finditer(re.escape(key) + r"\s*:\s*'", s):
        i = m.end()
        out = []
        while i < len(s):
            c = s[i]
            if c == "\\":
                if i + 1 >= len(s):
                    break
                n = s[i + 1]
                if n == "x" and i + 4 <= len(s):
                    try:
                        out.append(chr(int(s[i + 2:i + 4], 16)))
                    except ValueError:
                        out.append(n)
                    i += 4
                    continue
                mp = {"n": "\n", "t": "\t", "r": "\r",
                      "'": "'", '"': '"', "\\": "\\", "/": "/"}
                out.append(mp.get(n, n))
                i += 2
                continue
            if c == "'":
                break
            out.append(c)
            i += 1
        val = "".join(out)
        if best is None or len(val) > len(best):
            best = val
    return best


# ---------------------------------------------------------------- 解析
def _parse_published(html_text):
    """尝试从页面 JS 里提取发布时间，返回 'YYYY-MM-DD HH:MM:SS' 或 ''。
    常见位置: var ct="unix秒"; var create_time='...'; publish_time 字段。"""
    # var ct="1699999999"
    m = re.search(r'var\s+ct\s*=\s*"(\d{9,11})"', html_text)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    # create_time / publish_time: 'YYYY-MM-DD HH:MM:SS' 或 unix
    m = re.search(r"(?:create_time|publish_time)\s*[:=]\s*['\"](\d{9,11})['\"]", html_text)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    m = re.search(r"(?:create_time|publish_time)\s*[:=]\s*['\"]([^'\"]{8,25})['\"]", html_text)
    if m:
        return m.group(1).replace("T", " ")
    return ""


def parse_article(html_bytes):
    """解析一篇文章，返回 dict(type,title,author,published,body_md,image_count)。
    抓不到正文时抛 RuntimeError，并尽量区分『风控验证页』和『文章已删除』。"""
    html_text = html_bytes.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html_bytes, "lxml")

    # ---- 标题: og:title -> #activity-name
    title = ""
    m = soup.find("meta", property="og:title")
    if m and m.get("content"):
        title = m["content"].strip()
    if not title:
        h = soup.select_one("#activity-name")
        title = h.get_text(strip=True) if h else ""

    # ---- 公众号名: #js_name -> var nickname -> window.name -> nick_name
    author = ""
    jn = soup.select_one("#js_name")
    if jn and jn.get_text(strip=True):
        author = jn.get_text(strip=True)
    if not author:
        m = re.search(r'var\s+nickname\s*=\s*[\'"]([^\'"]+)[\'"]', html_text)
        if m:
            author = m.group(1).strip()
    if not author:
        # 小绿书页面：window.name = "公众号名"
        m = re.search(r'window\.name\s*=\s*"([^"]+)"', html_text)
        if m:
            author = m.group(1).strip()
    if not author:
        # 小绿书页面 JSON 块：nick_name: '公众号名'
        m = re.search(r'nick_name\s*:\s*[\'"]([^\'"]+)[\'"]', html_text)
        if m:
            author = m.group(1).strip()

    # ---- 发布时间
    published = _parse_published(html_text)

    # ---- 正文三种结构
    # 1) 普通图文文章
    content = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
    if content is not None:
        out = []
        _md_children(content, out)
        body = clean_md("".join(out))
        if body and len(body) >= 10:
            return {"type": "图文文章", "title": title, "author": author,
                    "published": published, "body_md": body,
                    "image_count": body.count("![](")}

    # 2) 文字型小绿书: 正文在 JS content 字段
    chtml = extract_js_string(html_text, "content")
    if chtml and len(chtml) > 30:
        csoup = BeautifulSoup(chtml, "lxml")
        out = []
        _md_children(csoup, out)
        body = clean_md("".join(out))
        if body and len(body) >= 10:
            return {"type": "小绿书(文字)", "title": title, "author": author,
                    "published": published, "body_md": body,
                    "image_count": body.count("![](")}

    # 3) 纯图片小绿书: 正文是 cdn_url 图片序列
    imgs = re.findall(r"cdn_url\s*:\s*'([^']+)'", html_text)
    ordered, seen = [], set()
    for u in imgs:
        if u.startswith("http") and u not in seen:
            seen.add(u)
            ordered.append(u)
    if ordered:
        note = "> 本文为小绿书/图片消息，正文由以下图片构成：\n\n"
        body = note + "\n\n".join("![](%s)" % u for u in ordered)
        return {"type": "小绿书(纯图片)", "title": title, "author": author,
                "published": published, "body_md": body,
                "image_count": len(ordered)}

    # ---- 三种都没抓到 -> 判断是风控还是删除
    if any(k in html_text for k in DELETED_MARKERS):
        raise RuntimeError("文章已被发布者删除或无法查看（页面有删除标记）")
    if any(k in html_text for k in RISK_MARKERS) or len(html_text) < 20000:
        raise RuntimeError(
            "触发微信风控验证页（IP 级），不是文章删除。"
            "建议：静置 10~30 分钟后再试；或换网络/代理；单篇之间加 --sleep。")
    raise RuntimeError("正文为空或过短（页面结构可能已改，需人工检查）")


# ---------------------------------------------------------------- 输出
def safe_name(s, maxlen=60):
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().strip(".")
    return (s[:maxlen] or "untitled")


def save_md(article, url, outdir):
    prefix = article["published"][:10].replace("-", "") if article["published"] else ""
    fname = (prefix + "_" if prefix else "") + safe_name(article["title"]) + ".md"
    fpath = os.path.join(outdir, fname)
    fm = ("---\ntitle: \"%s\"\nauthor: \"%s\"\npublished: \"%s\"\nsource: \"%s\"\n---\n\n"
          % (article["title"].replace('"', "'"), article["author"],
             article["published"], url))
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(fm + article["body_md"] + "\n")
    return fpath


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(
        description="微信公众号文章提取（免费/免登录）-> Markdown")
    ap.add_argument("urls", nargs="*", help="文章链接（可多条）")
    ap.add_argument("--file", help="包含链接列表的 txt（每行一条，# 开头为注释）")
    ap.add_argument("-o", "--out", default="./wx_articles", help="输出目录")
    ap.add_argument("--sleep", type=float, default=1.5,
                    help="多条链接之间的间隔秒数（防微信限流，默认 1.5）")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            urls += [ln.strip() for ln in f
                     if ln.strip() and not ln.strip().startswith("#")]
    if not urls:
        ap.print_help()
        return 1
    urls = [u for u in urls if u.startswith("http")]
    if not urls:
        print("错误：没有有效的 http(s) 链接")
        return 1

    os.makedirs(args.out, exist_ok=True)
    ok, fail = 0, 0
    for i, url in enumerate(urls, 1):
        tag = "[%d/%d]" % (i, len(urls))
        try:
            raw = fetch(url)
            art = parse_article(raw)
            del raw
            fpath = save_md(art, url, args.out)
            ok += 1
            print("%s 成功 | %s | %s | %s | %d字 %d图"
                  % (tag, art["type"], art["title"][:40] or "(无标题)",
                     art["author"] or "(未知公众号)", len(art["body_md"]),
                     art["image_count"]))
            print("        -> %s" % fpath)
        except Exception as e:  # noqa
            fail += 1
            print("%s 失败 | %s" % (tag, e))
            print("        URL: %s" % url)
        if i < len(urls):
            time.sleep(args.sleep)

    print("\n完成：成功 %d 篇，失败 %d 篇，输出目录 %s" % (ok, fail, os.path.abspath(args.out)))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
