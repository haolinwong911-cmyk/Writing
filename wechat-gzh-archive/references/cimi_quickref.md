# 次幂数据(cimidata)接口速查

> 完整规格、限流、错误码以已安装的 `cimidata-gzh-collect` skill（`references/endpoints.md`、`references/errors.md`）为准。此处只列本 skill 用到的关键点。

- HOST：`https://api.cimidata.com`
- POST 请求 body 为 JSON，请求头 `Content-Type: application/json`；所有接口带 `access_token`（query 参数 `?access_token=` 或 `Authorization: Bearer`）。
- **只读响应体里的 `code` 判断成败**，别看 HTTP 状态码（业务错误 HTTP 码混用：有 200 有 400 有 401，body 结构一致）。`code=200` 才成功。
- 计费接口响应会多一个顶层 `balance`（单位:分），是本次调用后的余额，÷100 得元。用它实时监控扣费。

## 认证
- `POST /api/v2/token`，body `{"app_id","app_secret"}` → `data.access_token`，**有效期 7 天**，可缓存复用（别每次重取）。
- 凭据无效返回 `code=4102`。

## 本 skill 用到的接口
| 接口 | 用途 | 参考单价 | 限流 | 备注 |
|---|---|---|---|---|
| `GET /api/v2/user/balance` | 查余额 | 免费 | — | 调用计费接口前先查它 |
| `POST /api/v3/accounts/search` | 按名称搜公众号拿 wxid | 0.10 元/次 | 无 | 返回含 `wxid`/`username`/`biz` |
| `POST /api/v2/articles/history` | 历史发文(可翻页) | 0.05 元/页 | 3/s + 120/min | body `{wxid,last_id}`，每页约10篇，`last_id` 为 null 到底；超时设 ≥20s |
| `POST /api/v2/articles/data2` | 阅读+点赞+在看+评论+分享 | 0.03 元/篇 | 3/s | body `{url}`；返回 `read_num/old_like_num(赞)/like_num(在看)/comment_count/share_num` |

## 关键错误码
| code | 含义 | 处理 |
|---|---|---|
| 200 | 成功 | — |
| 2040 | token 无效 | 重新 `/api/v2/token` |
| 4102 | appid 无效/过期 | 核对 app_id/app_secret |
| 429 | 操作过于频繁 | 退避几秒重试；**不计费** |
| 6020 | 余额不足 | 接口未执行、**不计费**；停止并让用户充值 |
| 6021 | 阅读量获取失败 | 重试；**不计费** |
| 5300 | 历史列表获取失败 | 重试；**不计费** |
| 1004 | 数据不存在/暂未就绪 | 等 ~30 秒重试；**不计费** |
| 5022 | 文章已删除 | 跳过，别重试 |

## 计费确认话术模板（调用计费接口前发给用户）
> 当前余额 X 元；要调用 `<接口>`，单价 Y 元/篇，共 N 篇，预计花费 Z 元（失败不计费）。是否开始？
