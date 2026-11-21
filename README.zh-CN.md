# ai-visibility-checker

[English](README.md)

AI 爬虫和 agent 能不能读懂、用上你的网站？一条命令查 7 类 26 项，满分 100，再写一段提示词，粘给 Claude Code、Cursor、Codex 这类编程 agent 就能照着改。

```bash
uvx --from git+https://github.com/zhuyansen/ai-visibility-checker ai-visibility-checker example.com
```

要 Python 3.10 以上，没有依赖，不要 key，免费。它只对你给的网站发普通的 HTTP 请求：首页（一次用浏览器身份、一次用 AI agent 身份）、robots.txt、站点地图、llms.txt、一个不存在的网址（看缺页是不是返回 404），以及一次要 Markdown 的请求。

网页版用的是同一套检查：[jasonzhu.ai/zh/go-global/ai-readiness](https://jasonzhu.ai/zh/go-global/ai-readiness)。

## 检查项从哪来

7 个类别、26 项检查和每项的分值，对齐 [Hostinger 的免费 AI Visibility Checker](https://www.hostinger.com/)，所以这里的分数可以和那边的对着看。代码、每一项检查和修复建议的文字、提示词都是我们自己写的。本项目和 Hostinger 没有关系，也没有得到它的认可。

## 查什么

| Category (points) | Check | Points |
|---|---|---|
| Crawl permission (20) | robots.txt can be fetched and read | 4 |
| Crawl permission (20) | robots.txt lets the major AI crawlers in | 7 |
| Crawl permission (20) | An AI agent gets the page, not a bot challenge | 6 |
| Crawl permission (20) | robots.txt says how the content may be used (Content-Signal) | 3 |
| Readability (18) | The main text is in the HTML the server sends | 8 |
| Readability (18) | The page is not padded with markup | 3 |
| Readability (18) | The page has a title, a description and a canonical URL | 4 |
| Readability (18) | One H1 that names the page | 3 |
| Findability (16) | A sitemap can be fetched and lists pages | 5 |
| Findability (16) | robots.txt points to the sitemap | 3 |
| Findability (16) | The sitemap says when pages last changed | 3 |
| Findability (16) | A page that does not exist answers 404 | 3 |
| Findability (16) | The homepage loads over HTTPS with at most one redirect | 2 |
| Structured meaning (14) | The page carries JSON-LD | 6 |
| Structured meaning (14) | The Organization (or LocalBusiness) node is filled in | 4 |
| Structured meaning (14) | sameAs ties the site to its profiles elsewhere | 2 |
| Structured meaning (14) | JSON-LD describes more than one kind of thing | 2 |
| Commercial legibility (12) | The homepage links to about, contact and legal pages | 4 |
| Commercial legibility (12) | Contact details are text a machine can read | 4 |
| Commercial legibility (12) | Prices can be read without JavaScript or a login | 4 |
| Agent-native content (10) | /llms.txt exists | 4 |
| Agent-native content (10) | /llms.txt has a title and links | 3 |
| Agent-native content (10) | Asking for Markdown gets Markdown back | 2 |
| Agent-native content (10) | The homepage's Link header points to machine-readable versions | 1 |
| Agent interaction (10) | The page registers WebMCP tools for in-browser agents | 6 |
| Agent interaction (10) | An MCP Server Card is published | 4 |

等级：90 分以上 A，75 以上 B，60 以上 C，40 以上 D，其余 F。

`--json` 输出每一项和它的依据，`--no-prompts` 不输出给编程 agent 的提示词。

## 它说明不了什么

- AI 助手会不会引用你。全部通过只说明网站读得到；会不会被引用，看页面写了什么、别人有没有提到你。
- 首页以外的页面，除了站点地图、robots.txt、llms.txt 和那次 404 探测。
- 更深一层的拦截：限流，或者请求多了才触发的规则。

## 测试

```bash
python -m pytest -q tests      # 不联网：robots.txt 解析、等级、提示词、分值合计
```

## 许可

MIT。作者 [Jason Zhu](https://jasonzhu.ai)。
