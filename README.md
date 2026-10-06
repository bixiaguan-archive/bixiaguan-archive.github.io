# 壁下观 · 文字归档

[壁下观](https://bixiaguan-archive.github.io/) 是 IPN 播客网络旗下的一档艺术类中文播客。本站提供全部 102 期节目的全文检索和转录文本浏览。

## 访问

**https://bixiaguan-archive.github.io/**

## 功能

- **全文检索** — 按关键词搜索全部 102 期转录文本，关键词高亮
- **节目索引** — 按年份浏览，展开/折叠，支持正倒序
- **全文浏览** — 点击时间戳跳转 YouTube 对应位置
- **登场人物** — 按出场频次索引 17 位主播与嘉宾
- **访古地图** — 节目里提到的 221 处古建筑与遗址标注在地图上（年代、亮点、相关期数），附六条访古路线（沿实际道路）：[`ancient-buildings-map.html`](ancient-buildings-map.html)
- **读者报错** — 选择疑似 ASR 错误的文字后，可提交给编辑审核

## 本地校对模式

完整校对工具只会在本机浏览页面时加载，不会发布到 GitHub Pages。在仓库根目录运行
`python3 -m http.server 8765` 后，可直接访问 <http://127.0.0.1:8765/?ep=1>。

进入任一期全文后，直接选择转录文字即可打开标记菜单。标记仅保存在当前浏览器的
`localStorage`，不会修改线上文本；可在「校对标记」面板中定位、删除，或导出为
JSON / Markdown 后交给 LLM 或人工整理。

「事实勘误」与「ASR 错误」分开保存：前者用于核实主播原话，不应直接改写转录正文。

## 读者报错

读者可在公开页面选择文本并报告 ASR 错误。前端接口配置在
[`bixiaguan_search/crowd-report-config.js`](bixiaguan_search/crowd-report-config.js)。如需临时关闭
公开上报，将其中的 `endpoint` 和 `turnstileSiteKey` 置为空字符串即可。

服务端位于 [`crowd-report-worker/`](crowd-report-worker/)，采用 Cloudflare Worker + D1，
带来源校验、可选 Turnstile 和基于不可逆 IP 摘要的限流。部署步骤见
[`crowd-report-worker/README.md`](crowd-report-worker/README.md)。读者提交仅作为待审核线索，
不得直接写入 SRT。

## 构建

提交转录稿（`bixiaguan_transcripts/*.srt`）后，GitHub Actions 会自动运行 `build_index.py` 生成搜索索引并部署到 GitHub Pages。
