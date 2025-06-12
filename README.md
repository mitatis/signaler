# 🛰️ Signaler

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![OpenAI API](https://img.shields.io/badge/API-OpenAI-green)](https://openai.com)

Automated RSS translation and summarization pipeline for Markdown-based AI blog publishing.

## Overview

**Signaler** is an automated toolchain for fetching, translating, and summarizing tech news from RSS feeds into localized Markdown content. It supports multi-stage processing including full-text extraction, translation into Simplified Chinese, content summarization, and integration into static blog sites.

## Project Structure

| File | Description |
|------|-------------|
| `rss_fetch.py`     | Fetch RSS articles and convert them into `.md` |
| `AI_summarizer.py` | Translate, summarize and enrich Markdown files using OpenAI |
| `main.py`          | Entry point, orchestrates fetch and summarize steps |
| `last_fetched.json`| Cache to avoid duplicate fetching |

- In rss_fetch:
  - *FEED = []*          # list of RSS url
  - *OUTPUT_DIR = ""*    # PATH of fetched files(saved in .md)
  - create new file *last_fetched.json* which saves newest fetching date of each RSS url

- AI_summarizer provides Batch Translation of Markdown + Summary + Description
	1.	Recursively traverse all *.md files under SRC_DIR
	2.	Translate the main content into Simplified Chinese
	3.	Generate a summary (default: < 200 characters) and insert it after the front matter
	4.	Generate a one-sentence introduction and write it to front-matter.description
	5.	Write the new file to DST_DIR following the original relative path; DST_DIR may already exist or will be created automatically; files with the same name will be overwritten
	6.	Rename processed source files by adding the prefix “[ds]” to the filename; files already marked will be skipped in future runs of the script

## Usage

### Dependencies

- feedparser
- newspaper3k
- openai
- tqdm
- python-dotenv
- markdownify （optional）

### Run
```
python main.py
```
### Configuration

 Directly set your OpenAI API key in *AI_summarizer.py*

## Example Output

```md
---
title: 如同人类一般，人工智能正迫使机构重新审视其存在意义
pubDatetime: 2025-06-08 20:00:00+00:00
tags:
- 认知迁移
- AI伦理
- 长期视野
description: AI时代推动认知迁移，要求机构重塑结构、平衡效率与人性化，坚守伦理与人类独特价值，实现制度化转型。
---
*[源信息](https://venturebeat.com/ai/like-humans-ai-is-forcing-institutions-to-rethink-their-purpose/)经过deepseek翻译并总结*
## 摘要：
认知迁移推动个人与机构蜕变，AI颠覆思维、协作与决策，挑战教育、政府等传统机构根基。工业时代设计的机构面临系统性危机，需提升适应性，坚守人类尊严等非算法化价值。部分机构已尝试AI应用，但深层挑战在于结构性重塑，平衡效率与人性化。新时代机构设计原则包括：增强响应力、利用AI解放人力、保留人类关键判断。机构需主动重构身份与功能，在AI时代重建权威，坚守伦理与长期视野，重新定义人类独特价值。智能时代要求机构进化，实现认知迁移的制度化转型。
---
[Content]
```

## TODO

- [ ] Muti-language Translation
- [ ] RSS filter by date, keyword or topic
- [ ] Visualized Web UI

## License

MIT License

## Author

Created by mitatis(zik.ai) – [zik-3.com]