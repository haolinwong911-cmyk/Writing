#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
次幂数据(cimidata) API 自包含客户端: token / 历史列表 / 互动指标 / 余额。
凭证从环境变量 APP_ID / APP_SECRET 读取, 绝不写死进代码或文件。
依赖: requests。

用法:
  export APP_ID=xxx APP_SECRET=xxx
  python cimi_client.py balance                         # 查余额(免费)
  python cimi_client.py history  <wxid> <out.json>      # 取全部历史发文(计费 0.05元/页)
  python cimi_client.py data2    <articles.json> <out_metrics.json>   # 取互动指标(计费 0.03元/篇)

计费说明(参考价, 以官网为准): history 0.05元/页(约10篇), data2 0.03元/篇。
失败不计费可重试的错误码: 6021/5300/1004/429/1003; 6020=余额不足(接口未执行), 会停止。
调用计费命令前, 务必先向用户报价并得到确认(见 SKILL.md 付费铁律)。
"""
import os, sys, json, time
import requests

HOST = "https://api.cimidata.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# 不计费可重试的错误码 -> (重试前等待秒, 最多重试几次)
RETRY = {1004: (30, 1), 1003: (2, 2), 5300: (2, 2), 6021: (2, 2), 429: (10, 3)}
GAP = 0.4  # 篇/页间隔, 控制在接口 3 次/秒限速内


class Cimi:
    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or os.environ["APP_ID"]
        self.app_secret = app_secret or os.environ["APP_SECRET"]
        self.s = requests.Session()
        self._tok = None
        self.last_balance = None

    def token(self):
        if self._tok:
            return self._tok
        r = self.s.post(f"{HOST}/api/v2/token",
                        json={"app_id": self.app_id, "app_secret": self.app_secret},
                        headers={"User-Agent": UA}, timeout=20)
        j = r.json()
        if j.get("code") != 200:
            raise RuntimeError(f"获取 token 失败: {j}")
        self._tok = j["data"]["access_token"]
        return self._tok

    def _post(self, path, body):
        url = f"{HOST}{path}?access_token={self.token()}"
        for attempt in range(5):
            try:
                r = self.s.post(url, json=body,
                                headers={"User-Agent": UA, "Content-Type": "application/json"},
                                timeout=30)
                j = r.json()
                code = j.get("code")
                if code == 200:
                    if j.get("balance") is not None:
                        self.last_balance = j["balance"]
                    return j
                if code == 6020:
                    return j  # 余额不足, 交上层停止
                if code in RETRY:
                    wait, maxtry = RETRY[code]
                    if attempt < maxtry:
                        time.sleep(wait); continue
                return j  # 其它错误(如 5022 已删除)直接返回, 不重试
            except Exception:
                if attempt < 4:
                    time.sleep(2 + 2 * attempt); continue
                raise
        return {"code": -1, "msg": "重试仍失败"}

    def balance(self):
        url = f"{HOST}/api/v2/user/balance?access_token={self.token()}"
        return self.s.get(url, headers={"User-Agent": UA}, timeout=20).json()

    def history_all(self, wxid, out_json):
        """翻页取全部历史发文, 存 out_json。"""
        arts, last_id, page = [], None, 0
        while True:
            body = {"wxid": wxid}
            if last_id:
                body["last_id"] = last_id
            j = self._post("/api/v2/articles/history", body)
            if j.get("code") != 200:
                print("history 出错:", j); break
            data = j.get("data") or {}
            items = data.get("items") or []
            arts.extend(items)
            last_id = data.get("last_id")
            page += 1
            print(f"第{page}页 +{len(items)} 篇, 累计 {len(arts)}")
            if not last_id or not items:
                break
            time.sleep(GAP)
        json.dump(arts, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"history 完成: {len(arts)} 条 -> {out_json}")
        return arts

    def data2_all(self, articles_json, out_json):
        """逐篇取 阅读/点赞/在看/评论/分享, 断点续传, 余额不足即停。"""
        arts = json.load(open(articles_json, encoding="utf-8"))
        metrics = json.load(open(out_json, encoding="utf-8")) if os.path.exists(out_json) else {}
        done = 0
        for i, a in enumerate(arts, 1):
            url = a["content_url"]
            if url in metrics and "_error" not in metrics[url]:
                continue
            j = self._post("/api/v2/articles/data2", {"url": url})
            if j.get("code") == 6020:
                print(f"[停止] 余额不足, 累计成功 {sum(1 for v in metrics.values() if '_error' not in v)} 篇")
                break
            if j.get("code") == 200:
                d = j.get("data") or {}
                metrics[url] = {
                    "read_num": d.get("read_num"),           # 阅读量
                    "old_like_num": d.get("old_like_num"),   # 点赞
                    "like_num": d.get("like_num"),           # 在看
                    "comment_count": d.get("comment_count"),  # 评论数
                    "share_num": d.get("share_num"),          # 分享数
                    "_balance": j.get("balance"),
                }
                done += 1
                if done % 20 == 0:
                    b = j.get("balance")
                    print(f"[{i}] 新取 {done}, 余额 {b}分 = {round((b or 0)/100, 2)}元", flush=True)
                    json.dump(metrics, open(out_json, "w", encoding="utf-8"), ensure_ascii=False)
            else:
                metrics[url] = {"_error": f"{j.get('code')}:{j.get('msg')}"}
                print(f"[{i}] 跳过 {j.get('code')} | {(a.get('title') or '')[:22]}")
            time.sleep(GAP)
        json.dump(metrics, open(out_json, "w", encoding="utf-8"), ensure_ascii=False)
        ok = sum(1 for v in metrics.values() if "_error" not in v)
        er = sum(1 for v in metrics.values() if "_error" in v)
        print(f"data2 完成: 成功 {ok}, 失败/跳过 {er}")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    c = Cimi()
    cmd = sys.argv[1]
    if cmd == "balance":
        print("余额:", c.balance())
    elif cmd == "history" and len(sys.argv) == 4:
        c.history_all(sys.argv[2], sys.argv[3])
    elif cmd == "data2" and len(sys.argv) == 4:
        c.data2_all(sys.argv[2], sys.argv[3])
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
