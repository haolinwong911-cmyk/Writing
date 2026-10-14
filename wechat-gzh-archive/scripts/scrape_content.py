#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
免登录直抓微信公众号文章正文 -> Markdown (区分普通图文 / 小绿书)。
用法: python scrape_content.py <articles.json> <输出目录> [--sleep 1.0]
articles.json: [{"title","content_url","published_at","digest","idx"}, ...]
产出: <输出目录>/序号_标题.md (front matter + 正文), _progress.json(断点续传)
依赖: requests, beautifulsoup4, lxml
"""
import os, re, sys, json, time, html
import urllib.parse

try:
    import requests
    _HAS_REQ = True
except Exception:
    _HAS_REQ = False
    import urllib.request, urllib.error

from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://mp.weixin.qq.com/",
           "Accept-Language": "zh-CN,zh;q=0.9"}
_session = requests.Session() if _HAS_REQ else None


def fetch(url, retries=4):
    last = None
    for i in range(retries):
        try:
            if _HAS_REQ:
                return _session.get(url, headers=HEADERS, timeout=25).content
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read()
        except Exception as e:  # noqa
            last = e
            time.sleep(2 + 2 * i)
    raise last


BLOCK = {"p", "section", "div", "li", "ul", "ol", "blockquote", "figure",
         "figcaption", "table", "tr", "td", "th", "pre", "main", "article"}
SKIP = {"script", "style", "iframe", "noscript", "svg", "template"}


def _md_children(node, out):
    for child in node.children:
        name = getattr(child, "name", None)
        if name is None:
            out.append(str(child))
        elif name in SKIP:
            continue
        elif name == "img":
            src = child.get("data-src") or child.get("src") or ""
            if src and src.startswith("http"):
                out.append("\n\n![](%s)\n\n" % src)
        elif name == "br":
            out.append("\n")
        elif name in ("strong", "b"):
            t = []; _md_children(child, t); s = "".join(t).strip()
            if s:
                out.append("**%s**" % s)
        elif name in ("em", "i"):
            t = []; _md_children(child, t); s = "".join(t).strip()
            if s:
                out.append("*%s*" % s)
        elif name == "code":
            t = []; _md_children(child, t); s = "".join(t).strip()
            if s:
                out.append("`%s`" % s)
        elif name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            t = []; _md_children(child, t); s = "".join(t).strip()
            if s:
                lv = {"h1": "## ", "h2": "### ", "h3": "#### ",
                      "h4": "##### ", "h5": "###### ", "h6": "###### "}[name]
                out.append("\n\n%s%s\n\n" % (lv, s))
        elif name == "hr":
            out.append("\n\n---\n\n")
        elif name == "li":
            t = []; _md_children(child, t); s = "".join(t).strip()
            if s:
                out.append("\n- %s" % s)
        elif name == "blockquote":
            t = []; _md_children(child, t); s = "".join(t).strip()
            if s:
                out.append("\n\n" + "\n".join("> " + ln for ln in s.split("\n")) + "\n\n")
        elif name == "a":
            t = []; _md_children(child, t); s = "".join(t).strip()
            href = child.get("href", "")
            if href.startswith("http") and s:
                out.append("[%s](%s)" % (s, href))
            elif s:
                out.append(s)
        elif name in BLOCK:
            out.append("\n"); _md_children(child, out); out.append("\n")
        else:
            _md_children(child, out)


def clean_md(text):
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_js_string(s, key):
    """取页面里 key: '...' 的 JS 字符串并反转义(\\xHH/\\n 等), 取最长的一个(小绿书正文)。"""
    best = None
    for m in re.finditer(re.escape(key) + r"\s*:\s*'", s):
        i = m.end(); out = []
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
                    i += 4; continue
                mp = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "\\": "\\", "/": "/"}
                out.append(mp.get(n, n)); i += 2; continue
            if c == "'":
                break
            out.append(c); i += 1
        val = "".join(out)
        if best is None or len(val) > len(best):
            best = val
    return best


def extract(html_bytes):
    """返回 (body_md, title, author)。依次尝试: 普通文章 #js_content -> 文字型小绿书 content字段 -> 纯图片小绿书 cdn_url。"""
    html_text = html_bytes.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html_bytes, "lxml")
    title = ""
    m = soup.find("meta", property="og:title")
    if m and m.get("content"):
        title = m["content"].strip()
    if not title:
        h = soup.select_one("#activity-name")
        title = h.get_text(strip=True) if h else ""
    author = ""
    jn = soup.select_one("#js_name")
    if jn and jn.get_text(strip=True):
        author = jn.get_text(strip=True)
    # 1) 普通图文文章
    content = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
    if content is not None:
        out = []; _md_children(content, out)
        return clean_md("".join(out)), title, author
    # 2) 文字型小绿书: JS content 字段
    chtml = extract_js_string(html_text, "content")
    if chtml and len(chtml) > 30:
        out = []; _md_children(BeautifulSoup(chtml, "lxml"), out)
        body = clean_md("".join(out))
        if body and len(body) >= 10:
            return body, title, author
    # 3) 纯图片小绿书: cdn_url 图片序列
    imgs = re.findall(r"cdn_url\s*:\s*'([^']+)'", html_text)
    ordered, seen = [], set()
    for u in imgs:
        if u.startswith("http") and u not in seen:
            seen.add(u); ordered.append(u)
    if ordered:
        note = "> 本文为小绿书/图片消息，正文由以下图片构成：\n\n"
        return note + "\n\n".join("![](%s)" % u for u in ordered), title, author
    return None, title, author


def norm_title(t):
    t = (t or "").strip()
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", "", t)
    return t[:40]


def safe_name(s, maxlen=44):
    s = re.sub(r"<[^>]*>", "", s or "")
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().strip(".")
    return (s[:maxlen] or "untitled")


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    src = sys.argv[1]
    outdir = sys.argv[2]
    sleep_s = 1.0
    if "--sleep" in sys.argv:
        sleep_s = float(sys.argv[sys.argv.index("--sleep") + 1])
    os.makedirs(outdir, exist_ok=True)
    prog_f = os.path.join(outdir, "_progress.json")
    progress = json.load(open(prog_f, encoding="utf-8")) if os.path.exists(prog_f) else {}

    raw = json.load(open(src, encoding="utf-8"))
    # 按标题归一化去重(微信 history 尾部会混入重复, 且 URL 因 sessionid 不同, 必须按标题去重)
    seen, arts = set(), []
    for a in raw:
        k = norm_title(a.get("title"))
        if k in seen:
            continue
        seen.add(k); arts.append(a)
    print(f"输入 {len(raw)} 条, 标题去重后 {len(arts)} 篇")

    done = 0
    for i, a in enumerate(arts, 1):
        url = a["content_url"]
        if progress.get(url) == "done":
            continue
        try:
            body, ptitle, author = extract(fetch(url))
            if body is None or len(body) < 10:
                raise RuntimeError("正文为空(可能已删除/被风控验证页拦截)")
            pub = (a.get("published_at") or "").replace("T", " ")
            fm = ('---\ntitle: "%s"\nauthor: "%s"\npublished: "%s"\nsource: "%s"\n---\n\n'
                  % ((ptitle or a.get("title") or "").replace('"', "'"), author, pub, url))
            with open(os.path.join(outdir, "%03d_%s.md" % (i, safe_name(ptitle or a.get("title")))), "w", encoding="utf-8") as f:
                f.write(fm + body + "\n")
            progress[url] = "done"; done += 1
            if done % 20 == 0:
                print(f"已存 {done} 篇", flush=True)
                json.dump(progress, open(prog_f, "w", encoding="utf-8"))
        except Exception as e:  # noqa
            print(f"[{i}] 失败: {e} | {(a.get('title') or '')[:24]}", flush=True)
        time.sleep(sleep_s)   # 限速, 防微信风控
    json.dump(progress, open(prog_f, "w", encoding="utf-8"))
    print(f"\n完成: 本次新存 {done} 篇, 累计 {sum(1 for v in progress.values() if v=='done')} 篇")


if __name__ == "__main__":
    main()
