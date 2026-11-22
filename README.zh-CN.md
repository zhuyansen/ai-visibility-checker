# ai-visibility-checker

[English](README.md)

AI 爬虫和 agent 能不能读懂、用上你的网站？一条命令查 26 项。其中 22 项是 AI 爬虫和 agent 现在就会用到的，计入总分，满分 100。另外 4 项是实验标准（llms.txt、WebMCP、MCP Server Card），报告里单独列一节，不计入总分。它还会写一段提示词，粘给 Claude Code、Cursor、Codex 这类编程 agent 就能照着改。

```bash
uvx ai-visibility-checker example.com
```

也可以 `pip install ai-visibility-checker`，再运行 `ai-visibility-checker example.com`。要 Python 3.10 以上，没有依赖，不要 key，免费。想跑仓库里最新的代码：`uvx --from git+https://github.com/zhuyansen/ai-visibility-checker ai-visibility-checker example.com`。

它只对你给的网站发普通的 HTTP 请求，用的是 AI agent 的身份（ChatGPT-User）：首页、再要一次首页的 Markdown 版、robots.txt、站点地图（如果是索引，再读它的第一个文件）、llms.txt、/.well-known/mcp/server-card.json，以及一个不存在的网址（看缺页是不是返回 404）。

网页版用的是同一套检查：[jasonzhu.ai/zh/go-global/ai-readiness](https://jasonzhu.ai/zh/go-global/ai-readiness)。但网页版目前仍把实验标准算进总分，等级的分界线也不同，所以两边的分数暂时对不上。

## 计入总分的

AI 爬虫和 agent 现在就会用到的，满分 100：

| Category (points) | Check | Points | Hostinger's |
|---|---|---|---|
| Crawl permission (23) | robots.txt can be fetched and read | 5 | 4 |
| Crawl permission (23) | robots.txt lets the major AI crawlers in | 8 | 7 |
| Crawl permission (23) | An AI agent gets the page, not a bot challenge | 7 | 6 |
| Crawl permission (23) | robots.txt says how the content may be used (Content-Signal) | 3 | 3 |
| Readability (23) | The main text is in the HTML the server sends | 10 | 8 |
| Readability (23) | The page is not padded with markup | 4 | 3 |
| Readability (23) | The page has a title, a description and a canonical URL | 5 | 4 |
| Readability (23) | One H1 that names the page | 4 | 3 |
| Findability (20) | A sitemap can be fetched and lists pages | 6 | 5 |
| Findability (20) | robots.txt points to the sitemap | 4 | 3 |
| Findability (20) | The sitemap says when pages last changed | 4 | 3 |
| Findability (20) | A page that does not exist answers 404 | 4 | 3 |
| Findability (20) | The homepage loads over HTTPS with at most one redirect | 2 | 2 |
| Structured meaning (16) | The page carries JSON-LD | 7 | 6 |
| Structured meaning (16) | The Organization (or LocalBusiness) node is filled in | 5 | 4 |
| Structured meaning (16) | sameAs ties the site to its profiles elsewhere | 2 | 2 |
| Structured meaning (16) | JSON-LD describes more than one kind of thing | 2 | 2 |
| Commercial legibility (15) | The homepage links to about, contact and legal pages | 5 | 4 |
| Commercial legibility (15) | Contact details are text a machine can read | 5 | 4 |
| Commercial legibility (15) | Prices can be read without JavaScript or a login | 5 | 4 |
| Agent-native content (3) | Asking for Markdown gets Markdown back | 2 | 2 |
| Agent-native content (3) | The homepage's Link header points to machine-readable versions | 1 | 1 |

「要 Markdown 就给 Markdown」计分，因为已经有 agent 这样要了。Cloudflare 2026-02-12 写道："We already see some of the most popular coding agents today – like Claude Code and OpenCode – send these accept headers"（[原文](https://blog.cloudflare.com/markdown-for-agents/)）。

只通过一部分的检查，按比例给分：5 个爬虫放行 3 个，就是 8 分的 3/5，记 5 分。

等级：90 分以上 A，75 以上 B，60 以上 C，40 以上 D，其余 F。

## 实验标准：只报告，不计分

| 检查 | 为什么不计分 |
|---|---|
| /llms.txt exists；/llms.txt has a title and links | Google 原文："You don't need to create new machine readable files, AI text files, or markup to appear in these features"（[AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)）。Ahrefs 2026-06-15：137,210 个站里 28% 放了 llms.txt，其中 97% 在 2026 年 5 月一次访问都没有（[研究原文](https://ahrefs.com/blog/llmstxt-study/)）。 |
| The page registers WebMCP tools for in-browser agents | Chrome 里还在试用期（origin trial）。Lighthouse 写明："WebMCP audits require registering for the WebMCP origin trial"（[Lighthouse 文档](https://developer.chrome.com/docs/lighthouse/agentic-browsing/scoring)）。 |
| An MCP Server Card is published | Cloudflare 扫了访问量最大的 20 万个域名：MCP Server Card 和 API Catalog（RFC 9727）加起来"appear on fewer than 15 sites in the entire dataset"，不到 15 个站有（[Cloudflare 2026-04-17](https://blog.cloudflare.com/agent-readiness/)）。 |

来源都在 2026-11-21 核对过。报告给这几项单列一节：查到了什么、怎么加、为什么不计分。修复提示词只在末尾点名，不要求改。`--json` 里它们标成 `"tier": "experimental"`，分数为 0。等 agent 真用起来，再移进总分。

## 检查项从哪来

26 项检查和类别，对齐 [Hostinger 的免费 AI Visibility Checker](https://www.hostinger.com/)。计分方法不一样。Hostinger 把 26 项都算进 100 分，其中 llms.txt、WebMCP、MCP Server Card 一共 17 分。这里把这 17 分拿掉，其余 22 项各自保留在 Hostinger 那边的占比，从 83 分按比例放大到 100 分，取整数：6 个 3 分的检查里，5 个进到 4 分；Content-Signal 最缺「agent 会照它办」的证据，留在 3 分。所以这里的分数不能和 Hostinger 的直接对比。代码、每一项检查和修复建议的文字、提示词都是我们自己写的。本项目和 Hostinger 没有关系，也没有得到它的认可。

## 输出

2026-11-21 查 example.com（节选）：

```
=== AI Readiness Report: example.com ===
Score: 32/100  |  Grade F (Not agent-ready yet)  |  Scanned: …

## Crawl permission: 15/23 pts (65%)
  ✗ robots.txt readable [0/5 pts]
      What we found: /robots.txt is missing or empty.
      How to fix:    Serve a robots.txt at /robots.txt.
  ✓ AI crawlers allowed [8/8 pts]
      What we found: All tracked AI crawlers may read the homepage.
…

## Experimental standards: not scored
   Few sites publish these and few agents read them yet. The score above leaves them out.
  ✗ llms.txt exists [not scored]
      What we found: /llms.txt is missing or returned an error.
      How to fix:    Serve an /llms.txt with a short summary of the site and links to its main pages.
      Why not scored: Google: "You don't need to create new machine readable files, AI text files, or markup …
…
```

同一天，0.1.0（26 项全部计分）给 example.com 的是 26 分。

`--json` 输出每一项的依据、档位和分数，`--no-prompts` 不输出给编程 agent 的提示词，`--version` 显示版本号。

## 它说明不了什么

- AI 助手会不会引用你。全部通过只说明网站读得到；会不会被引用，看页面写了什么、别人有没有提到你。
- 首页以外的页面，除了站点地图、robots.txt、llms.txt、MCP Server Card 和那次 404 探测。
- 更深一层的拦截：限流，或者请求多了才触发的规则。

## 测试

```bash
python -m pytest -q tests      # 不联网：robots.txt 解析、两档计分、模拟站点的总分、提示词、等级
```

## 许可

MIT。作者 [Jason Zhu](https://jasonzhu.ai)。
