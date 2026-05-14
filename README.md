# 壁下观 · 文字归档

[壁下观](https://bixiaguan-archive.github.io/) 是 IPN 播客网络旗下的一档艺术类中文播客。本站提供全部 102 期节目的全文检索和转录文本浏览。

## 访问

**https://bixiaguan-archive.github.io/**

## 功能

- **全文检索** — 按关键词搜索全部 102 期转录文本，关键词高亮
- **节目索引** — 按年份浏览，展开/折叠，支持正倒序
- **全文浏览** — 点击时间戳跳转 YouTube 对应位置
- **登场人物** — 按出场频次索引 17 位主播与嘉宾

## 构建

提交转录稿（`bixiaguan_transcripts/*.srt`）后，GitHub Actions 会自动运行 `build_index.py` 生成搜索索引并部署到 GitHub Pages。
