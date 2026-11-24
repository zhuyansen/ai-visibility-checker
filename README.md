# ai-visibility-checker

[中文](https://github.com/zhuyansen/ai-visibility-checker/blob/main/README.zh-CN.md)

Can AI crawlers and agents read, understand and use your website? One command runs 26 checks. The 22 that AI crawlers and agents use today make the score, out of 100. The other 4 are experimental standards (llms.txt, WebMCP, an MCP Server Card): the report lists them apart, and the score leaves them out. It also writes a prompt you can paste into a coding agent (Claude Code, Cursor, Codex) to fix what failed.

> **Archived on 24 November 2026.** This command-line version is no longer maintained. It was never published to PyPI, so `uvx ai-visibility-checker` and `pip install ai-visibility-checker` do not work. Use the web version, [jasonzhu.ai/en/go-global/ai-readiness](https://jasonzhu.ai/en/go-global/ai-readiness), or run this code straight from GitHub:

```bash
uvx --from git+https://github.com/zhuyansen/ai-visibility-checker ai-visibility-checker example.com
```

Python 3.10 or newer, no dependencies, no keys, free.

It makes plain HTTP requests to the site you name, with an AI agent's user agent (ChatGPT-User): the homepage, the homepage again asking for Markdown, robots.txt, the sitemap (and the first file of a sitemap index), llms.txt, /.well-known/mcp/server-card.json, and one made-up URL to see whether missing pages answer 404.

A web version runs the same checks in the browser: [jasonzhu.ai/en/go-global/ai-readiness](https://jasonzhu.ai/en/go-global/ai-readiness). It still scores the experimental standards and draws its grades at other points, so its score differs from this one.

## What makes the score

What AI crawlers and agents use today, 100 points:

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

Asking for Markdown counts because some agents already ask for it: "We already see some of the most popular coding agents today – like Claude Code and OpenCode – send these accept headers" ([Cloudflare, 2026-02-12](https://blog.cloudflare.com/markdown-for-agents/)).

A check that passes in part earns that part of its points: three of the five tracked crawlers let in is 3/5 of 8, so 5.

Grades: A from 90, B from 75, C from 60, D from 40, F below.

## Experimental: reported, not scored

| Check | Why it is not scored |
|---|---|
| /llms.txt exists; /llms.txt has a title and links | Google: "You don't need to create new machine readable files, AI text files, or markup to appear in these features" ([AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)). Ahrefs, 2026-06-15: of 137,210 sites, 28% publish an llms.txt, and 97% of those files got no traffic in May 2026 ([the study](https://ahrefs.com/blog/llmstxt-study/)). |
| The page registers WebMCP tools for in-browser agents | Still an origin trial in Chrome: "WebMCP audits require registering for the WebMCP origin trial" ([Lighthouse](https://developer.chrome.com/docs/lighthouse/agentic-browsing/scoring)). |
| An MCP Server Card is published | Cloudflare scanned the 200,000 most visited domains: MCP Server Cards and API Catalogs (RFC 9727) together "appear on fewer than 15 sites in the entire dataset" ([Cloudflare, 2026-04-17](https://blog.cloudflare.com/agent-readiness/)). |

Sources read on 2026-11-21. The report gives these checks a section of their own, with what was found, how to add each and why it is not scored; the fix prompt names them at the end without asking for them; `--json` marks them `"tier": "experimental"`, with 0 points. A check moves into the score once agents use it.

## Where the checks come from

The 26 checks and their categories follow [Hostinger's free AI Visibility Checker](https://www.hostinger.com/). The scoring does not. Hostinger counts all 26 in its 100 points, 17 of them for llms.txt, WebMCP and the MCP Server Card. Here those are out, and each of the other 22 checks keeps its share of Hostinger's points, scaled from 83 to 100 in whole points: of the six 3-point checks, five round up to 4 and Content-Signal, with the least evidence that agents act on it, stays at 3. A score here is not comparable with Hostinger's. The code, the wording of every check and fix, and the prompts are our own. This project is not affiliated with or endorsed by Hostinger.

## Output

On example.com, 2026-11-21 (shortened):

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

=== Ready-to-Paste AI Coding Agent Prompt (Improve Score) ===
These checks failed on example.com. Fix them in this order, and change only what each one needs:

1. The page carries JSON-LD (7 points)
…
Not in this list: llms.txt exists, WebMCP tools, MCP Server Card. These are experimental standards and do not change the score.
```

0.1.0 scored all 26 checks and gave example.com 26 the same day.

`--json` prints every check with its evidence, tier and points; `--no-prompts` leaves out the prompt for a coding agent; `--version` prints the version.

## What it does not tell you

- Whether any AI assistant cites you. Passing every check makes a site readable; being cited depends on what the page says and who else links to it.
- Anything past the homepage, except the sitemap, robots.txt, llms.txt, the MCP Server Card and the 404 probe.
- Whether a bot is blocked further down, by rate limits or by rules that only fire after many requests.

## Tests

```bash
python -m pytest -q tests      # offline: robots.txt reading, the two tiers, the score of a stand-in site, prompts, grades
```

## License

MIT. Made by [Jason Zhu](https://jasonzhu.ai).
