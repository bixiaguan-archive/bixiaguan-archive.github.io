# 壁下观 · 文字归档

[壁下观](https://bixiaguan-archive.github.io/) 是 IPN 播客网络旗下的一档艺术类中文播客。本站提供全部 102 期节目的全文检索和转录文本浏览。

## 访问

**https://bixiaguan-archive.github.io/**

## 功能

- **全文检索** — 按关键词搜索全部 102 期转录文本，关键词高亮
- **节目索引** — 按年份浏览，展开/折叠，支持正倒序
- **全文浏览** — 点击时间戳跳转 YouTube 对应位置；`?ep=5&t=754` 直接定位到该期第 754 秒所在段落
- **词条索引** — 全部注释词条按拼音首字母排列，可只看地点、输入即过滤；每条列出讲到它的各期与时间点，点开直达转录原文。默认按出现期数多少排在前，跨期反复讲到的人和地方一眼可见
- **勘误总表** — 主播口误与事实错误按期汇总，可按关键词过滤，每条链接到原文时间点；首页节目列表也标出每期勘误条数
- **登场人物** — 按出场频次索引 17 位主播与嘉宾
- **访古地图** — 节目里讲到的古建筑与遗址：按年代、类型筛选，每处列出在哪几期、第几分钟讲到，点开直达转录原文，并列出收入它的访古路线；附 33 条分地区访古路线（沿实际道路，每条一张木刻海报风封面），也可以在「自选路线」里自己点选一批地点，按就近原则排成不走回头路的路线（`?pick=名1|名2` 可分享）。见下文「访古地图」
- **读者报错** — 选择疑似 ASR 错误的文字后，可提交给编辑审核
- **单期静态页** — 每期另有一张不依赖脚本的纯 HTML 页面（`episode/<期号>.html`：简介、登场人物、勘误、带时间点的全文），连同 `sitemap.xml` 供搜索引擎收录；页面顶部链回交互式全文浏览

## 本地校对模式

完整校对工具只会在本机浏览页面时加载，不会发布到 GitHub Pages。在仓库根目录运行
`python3 build_index.py && python3 -m http.server 8765 -d bixiaguan_search` 后，
可直接访问 <http://127.0.0.1:8765/?ep=1>。

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

## 访古地图

页面 [`bixiaguan_search/ancient-buildings-map.html`](bixiaguan_search/ancient-buildings-map.html)，用 Leaflet 和 Leaflet.markercluster 绘制，底图为高德瓦片（GCJ-02，页面内把 WGS-84 坐标转换过去）。数据分两份人工维护的文件：

- [`bixiaguan_transcripts/map/places.json`](bixiaguan_transcripts/map/places.json)：每个地点的名称、别名、位置、年代、年代段、类型、是否已毁、WGS-84 坐标与坐标来源 `coordSource`（`wikidata:Q…`、`osm:way/…`，两处都查不到的写 `estimate`，页面上注明「大致位置」），以及它对应的注释词条 `annotations`（`annotations.json` 里的 `keyword`；一条注释混讲几处时写成 `{"keyword": …, "eps": [期数]}`，只取讲到该处的那几期）。简介取第一条注释，期数与时间点取全部关联注释，构建时生成，不在这里重复。
- [`bixiaguan_transcripts/map/routes.json`](bixiaguan_transcripts/map/routes.json)：访古路线的所属地区（页面按地区分组）、名称、天数、说明、封面文件名 `cover`、按顺序排列的站点名，以及预先算好的沿路轨迹（OSRM，改了站点后运行 `python3 tools/route_paths.py` 重算），页面不再实时请求路由服务。路线参考了山西文旅推荐的主题线路（土木华章、浊漳河谷、壁彩精华）与各地常见行程，按节目讲到次数多的地点优先串入。

路线封面放在 [`bixiaguan_search/route-covers/`](bixiaguan_search/route-covers/)：480 px 宽的大图显示在路线详情顶部，`thumb/` 下同名的 120 px 缩略图显示在路线列表里，都是 WebP。封面用 Qwen-Image 2.1 Turbo 按同一段木刻版画海报描述生成，图上印着路线名和天数，改了这两项要重新出图。

自选路线在页面里现算：从每个地点出发各走一遍「下一站去最近的」，再用 2-opt 把会走回头路的段反转，取总路程最短的一条；距离按直线计，地图上画虚线，不请求路由服务。

`build_index.py` 把两者与注释合并成 `map.json`。地点引用的注释词条不存在、期数超出节目范围、路线站点不在地点表里、路线封面文件缺失时，构建直接失败。新增地点：在 `places.json` 加一条，`annotations` 填对应注释的 `keyword`；第一条用作地点简介，必须是该地点自己的词条，不能是话题条（`topic`），否则构建失败。

## 构建

提交转录稿（`bixiaguan_transcripts/*.srt`）后，GitHub Actions 会自动运行 `build_index.py` 生成数据并部署到 GitHub Pages。构建依赖 `pypinyin`（`pip install pypinyin`）。
生成物不入库，页面按需加载：

| 文件 | 内容 | 何时加载 |
| --- | --- | --- |
| `episodes.json`（入库） | 节目元数据、登场人物 | 打开首页 / 登场人物页 |
| `ep/<期号>.json` | 单期转录 + 该期勘误与附注 | 浏览某期全文 |
| `search_index.json` | 全部转录（每段只留起始秒数与文本） | 首页搜索框获得焦点时预取，全文检索时使用 |
| `map.json` | 地点（含注释简介、期数与时间点）与路线 | 打开访古地图 |
| `terms.json` | 注释词条列表（按拼音排好序）：词条、首字母、是否地点、各期时间点；附各期标题 | 打开词条索引 |
| `terms/<首字母>.json` | 该字母下各词条的简介、出处与各期备注（`#` 组为 `_.json`） | 展开某个词条时 |
| `errata.json` | 全部勘误（按期） | 打开勘误总表 |
| `counts.json` | 每期勘误条数 | 打开首页 |
| `episode/<期号>.html`、`sitemap.xml`、`robots.txt` | 单期静态页与站点地图 | 搜索引擎抓取 |

词条按 [pypinyin](https://github.com/mozillazg/python-pinyin) 取拼音排序（处理多音字词组，比自建字表可靠）；英文词条按首字母归组，以数字或其他符号开头的归入「#」。同一对象只建一个词条：某词条的标签（去掉括注与「本期：」）恰是另一词条的关键词、或两条标签相同，构建直接失败，须合并为一条（各期出处并入，地图 `places.json` 的引用改指保留的关键词）。附注的写法（标签、简介、各期备注、出处的分工）见 [`.agents/skills/transcript-proofreading/SKILL.md`](.agents/skills/transcript-proofreading/SKILL.md)「附注词条的写法」；标了 `"topic": true` 的话题条只在单期页面显示，不进词条索引。「地点」取自访古地图：被 `places.json` 引用的词条即为地点。人物不分类——按生卒年等规则推断误差太大（年号、书名、题记都会混进来），注释里没有人工类别字段，不做猜测。

全文检索没有改用 [Pagefind](https://pagefind.app/)：它按分词建索引，中文检索只能命中整词（搜「照夜」找不到「照夜白」），也不给出逐期全部命中与出现次数，而本站检索恰恰需要逐字子串匹配——ASR 误字、人名异写都靠它查。因此保留整份转录在浏览器里逐字匹配，只压缩数据格式（gzip 后约 3.6 MB → 3.1 MB），并在用户点进搜索框时就开始下载。

## 测试

```bash
python3 build_index.py && python3 -m pytest tests -q
```

用本机 Chrome（Playwright `channel="chrome"`）打开本地站点，检查首页加载量与每期勘误数、全文浏览与按时间定位、检索、返回键、手机宽度，词条索引的拼音分组、筛选与跳转原文，勘误总表的过滤，单期静态页与站点地图，以及访古地图的筛选、地点详情跳转原文、分享链接、路线与路线封面。
