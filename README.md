# ai-visibility-checker

[中文](README.zh-CN.md)

Can AI crawlers and agents read, understand and use your website? One command checks 26 things in 7 categories, scores them out of 100, and writes a prompt you can paste into a coding agent (Claude Code, Cursor, Codex) to fix what failed.

```bash
uvx --from git+https://github.com/zhuyansen/ai-visibility-checker ai-visibility-checker example.com
```

Python 3.10 or newer, no dependencies, no keys, free. It makes plain HTTP requests to the site you name: the homepage (once as a browser, once as an AI agent), robots.txt, the sitemap, llms.txt, one made-up URL to see whether missing pages answer 404, and a request for Markdown.

A web version runs the same checks in the browser: [jasonzhu.ai/en/go-global/ai-readiness](https://jasonzhu.ai/en/go-global/ai-readiness).

## Where the checks come from

The 7 categories, the 26 checks and their point values follow [Hostinger's free AI Visibility Checker](https://www.hostinger.com/), so a score here can be read next to a score there. The code, the wording of every check and fix, and the prompts are our own. This project is not affiliated with or endorsed by Hostinger.

## What it checks

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

Grades: A from 90, B from 75, C from 60, D from 40, F below.

## Output

```
=== AI Readiness Report: example.com ===
Score: 26/100  |  Grade F (Not agent-ready yet)

## Crawl permission: 13/20 pts (65%)
  ✗ robots.txt readable [0/4 pts]
      What we found: /robots.txt is missing or empty.
      How to fix:    Serve a robots.txt at /robots.txt.
  ✓ AI crawlers allowed [7/7 pts]
      What we found: All tracked AI crawlers may read the homepage.
...
```

`--json` prints every check with its evidence, `--no-prompts` leaves out the prompt for a coding agent.

## What it does not tell you

- Whether any AI assistant cites you. Passing every check makes a site readable; being cited depends on what the page says and who else links to it.
- Anything past the homepage, except the sitemap, robots.txt, llms.txt and the 404 probe.
- Whether a bot is blocked further down, by rate limits or by rules that only fire after many requests.

## Tests

```bash
python -m pytest -q tests      # offline: robots.txt reading, grades, prompts, point totals
```

## License

MIT. Made by [Jason Zhu](https://jasonzhu.ai).
