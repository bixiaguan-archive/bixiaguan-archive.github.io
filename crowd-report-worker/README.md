# 读者 ASR 报错收件箱

此 Worker 只接收读者的 ASR 错误线索，不会修改转录文本，也不创建公开 GitHub Issue。

## 首次部署

在本目录执行：

```sh
npx wrangler login
npx wrangler d1 create bixiaguan-crowd-reports
```

将输出的数据库 ID 填入 `wrangler.jsonc`，然后执行：

```sh
npx wrangler d1 execute bixiaguan-crowd-reports --remote --file=schema.sql
npx wrangler secret put TURNSTILE_SECRET
npx wrangler secret put IP_HASH_SALT
npx wrangler deploy
```

把部署后的 `https://…workers.dev/api/reports` 填到
`../bixiaguan_search/crowd-report-config.js` 的 `endpoint`；再填入同一 Turnstile
widget 的 site key。Worker 的 `SITE_ORIGIN` 必须保持为 GitHub Pages 的正式域名。

`TURNSTILE_SECRET` 和 `IP_HASH_SALT` 均不得提交到仓库。前者用于人机验证；后者只用来生成限流所需的不可逆 IP 摘要。未配置 Turnstile secret 时，Worker 允许提交，便于本地联调；生产环境必须配置。

## 查看待审核项

不需要为公开站点暴露读取接口。登录 Cloudflare 后，可从本机用 Wrangler 导出待审核记录：

```sh
npx wrangler d1 execute bixiaguan-crowd-reports --remote --command "SELECT id, created_at, episode, timecode, original, suggestion, comment, anchor_json FROM reports WHERE status = 'pending' ORDER BY created_at ASC"
```

处理完成后可标记状态：

```sh
npx wrangler d1 execute bixiaguan-crowd-reports --remote --command "UPDATE reports SET status = 'reviewed' WHERE id = '<report-id>'"
```

## 审核

读者提交进入 D1 后仍是 `pending`。审核时应回听音频、核对读音和上下文，再将确认项纳入校对工作台导出包；不应直接将读者建议写进 SRT。
