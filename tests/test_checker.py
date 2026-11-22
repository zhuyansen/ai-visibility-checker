"""Offline tests: robots.txt reading, grades, the two tiers, the score and the fix prompts. No network."""
import datetime as dt
import json
import math
import re
from pathlib import Path

import ai_visibility_checker as c

BASE = "https://acme.example"
EXPERIMENTAL = {"llms.txt exists", "llms.txt title and links", "WebMCP tools", "MCP Server Card"}


def test_ai_crawlers_blocked_and_allowed():
    r = c._parse_robots_for_ai("User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\nSitemap: https://x.example/sitemap.xml\n")
    assert r["blocked_bots"] == ["GPTBot"] and "ClaudeBot" in r["allowed_bots"]
    assert r["sitemaps"] == ["https://x.example/sitemap.xml"]


def test_consecutive_user_agent_lines_share_one_group():
    # RFC 9309: user-agent lines in a row start one group, and the rules after them apply to each
    r = c._parse_robots_for_ai("User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n")
    assert {"GPTBot", "ClaudeBot"} <= set(r["blocked_bots"]) and "PerplexityBot" in r["allowed_bots"]


def test_a_longer_allow_beats_a_shorter_disallow_and_signals_are_read():
    r = c._parse_robots_for_ai("User-agent: *\nDisallow: /private\nContent-Signal: search=yes, ai-train=no\n")
    assert r["blocked_bots"] == [] and r["content_signals"] == ["search=yes, ai-train=no"]


def test_grades():
    assert c._grade_for_score(99)[0] == "A" and c._grade_for_score(80)[0] == "B" and c._grade_for_score(10)[0] == "F"


def test_scored_checks_add_up_to_100_and_keep_their_share_of_hostingers_points():
    scored = [s for s in c.CHECK_SPECS if s["tier"] == "scored"]
    experimental = [s for s in c.CHECK_SPECS if s["tier"] == "experimental"]
    for cat, _, weight in c.CATEGORIES:
        assert sum(s["weight"] for s in scored if s["category"] == cat) == weight
    assert sum(w for _, _, w in c.CATEGORIES) == 100 and len(scored) == 22 and len(c.CHECK_SPECS) == 26
    # Hostinger's 26 checks make 100; the 17 points of the experimental ones are what is left out
    assert sum(s["hostinger"] for s in c.CHECK_SPECS) == 100 and sum(s["hostinger"] for s in experimental) == 17
    for s in scored:                        # each one keeps its share, scaled from 83 to 100, to the whole point
        exact = s["hostinger"] * 100 / 83
        assert math.floor(exact) <= s["weight"] <= math.ceil(exact), s["id"]
    assert {s["short_name"] for s in experimental} == EXPERIMENTAL
    assert all(s["weight"] == 0 and s["category"] == c.EXPERIMENTAL[0] for s in experimental)
    assert all(c.EXPERIMENTAL_WHY[s["id"]] for s in experimental) and set(c.EXPERIMENTAL_WHY) == {s["id"] for s in experimental}


def test_prompts_list_failed_checks_most_points_first():
    results = [
        {"name": "One clear H1", "evidence": "3 h1 tags", "fix": "Keep one.", "status": "partial", "earned": 1, "possible": 2},
        {"name": "Sitemap with pages", "evidence": "404", "fix": "Serve one.", "status": "fail", "earned": 0, "possible": 5},
        {"name": "JSON-LD", "evidence": "found", "fix": None, "status": "pass", "earned": 4, "possible": 4},
    ]
    p = c.improve_score_prompt("x.example", results)
    assert p.index("Sitemap with pages") < p.index("One clear H1") and "JSON-LD" not in p
    one = c.single_check_prompt("x.example", results[1])
    assert "x.example" in one and "Serve one." in one and "experimental" not in one
    assert "nothing to fix" in c.improve_score_prompt("x.example", results[2:])


def test_prompts_leave_the_experimental_checks_out():
    llms = {"name": "/llms.txt exists", "short_name": "llms.txt exists", "evidence": "404", "fix": "Serve one.",
            "status": "fail", "earned": 0, "possible": 0, "tier": "experimental"}
    h1 = {"name": "One H1 that names the page", "short_name": "One clear H1", "evidence": "none", "fix": "Add one.",
          "status": "fail", "earned": 0, "possible": 4, "tier": "scored"}
    p = c.improve_score_prompt("x.example", [llms, h1])
    assert "1. One H1 that names the page (4 points)" in p and "/llms.txt exists" not in p
    assert p.endswith("Not in this list: llms.txt exists. These are experimental standards and do not change the score.")
    alone = c.improve_score_prompt("x.example", [llms])
    assert alone.startswith("x.example passed every scored check; nothing to fix.") and "llms.txt exists" in alone
    assert "does not change the score" in c.single_check_prompt("x.example", llms)


def site(*, experimental: bool = False, robots_extra: str = ""):
    """A fake site that passes every scored check; with `experimental`, the four experimental ones too."""
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Organization", "name": "Acme", "url": BASE, "telephone": "+1 555 0100", "address": "1 Main St",
         "sameAs": ["https://github.com/acme"]},
        {"@type": "WebSite", "name": "Acme", "url": BASE},
        {"@type": "Product", "name": "Acme Invoices", "offers": {"@type": "Offer", "price": "9", "priceCurrency": "USD"}},
    ]}
    webmcp = "<script>navigator.modelContext.registerTool({name: 'quote'})</script>" if experimental else ""
    home = (
        "<!doctype html><html><head><title>Acme</title><meta name='description' content='Invoices for small shops'>"
        f"<link rel='canonical' href='{BASE}/'><script type='application/ld+json'>{json.dumps(jsonld)}</script></head>"
        f"<body><h1>Acme invoices</h1><p>{' '.join(['Acme makes invoices simple for small shops.'] * 30)}</p>"
        "<a href='/about'>About</a> <a href='/contact'>Contact</a> <a href='/privacy'>Privacy</a> "
        f"<a href='/pricing'>Pricing</a> <a href='mailto:hi@acme.example'>Mail</a>{webmcp}</body></html>"
    )
    pages = {
        "/": (200, home, {"content-type": "text/html", "link": f'<{BASE}/index.md>; rel="alternate"; type="text/markdown"'}),
        "/robots.txt": (200, "User-agent: *\nAllow: /\nContent-Signal: search=yes, ai-train=no\n"
                             f"Sitemap: {BASE}/sitemap.xml\n{robots_extra}", {"content-type": "text/plain"}),
        "/sitemap.xml": (200, "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                              f"<url><loc>{BASE}/</loc><lastmod>{dt.date.today().isoformat()}</lastmod></url></urlset>",
                         {"content-type": "application/xml"}),
    }
    if experimental:
        pages["/llms.txt"] = (200, f"# Acme\n\n- [Pricing]({BASE}/pricing)\n", {"content-type": "text/plain"})
        pages["/.well-known/mcp/server-card.json"] = (200, json.dumps(
            {"name": "acme", "version": "1.0", "url": f"{BASE}/mcp", "tools": [{"name": "quote"}]}),
            {"content-type": "application/json"})

    def fetch(url, headers=None, timeout=12):
        path = url[len(BASE):] or "/"
        if path == "/" and (headers or {}).get("Accept") == "text/markdown":
            return {"status": 200, "url": url, "hops": 0, "headers": {"content-type": "text/markdown"},
                    "text": "# Acme", "error": None}
        status, text, hdrs = pages.get(path, (404, "not found", {"content-type": "text/html"}))
        return {"status": status, "url": url, "hops": 0, "headers": hdrs, "text": text, "error": None}
    return fetch


def scan(monkeypatch, **kw):
    monkeypatch.setattr(c, "_fetch", site(**kw))
    return c.scan_domain("acme.example")


def by_name(result):
    return {r["short_name"]: r for r in result["results"]}


def test_every_scored_check_passed_is_100_whatever_the_experimental_ones_say(monkeypatch):
    plain, full = scan(monkeypatch), scan(monkeypatch, experimental=True)
    assert plain["score"] == full["score"] == 100 and plain["grade"] == "A"
    assert all(r["status"] == "pass" for r in plain["results"] if r["tier"] == "scored")
    assert plain["experimental"] == {"scored": False, "passed": 0, "checks": 4}
    assert full["experimental"] == {"scored": False, "passed": 4, "checks": 4}
    for r in full["results"]:
        if r["tier"] == "experimental":
            assert r["earned"] == r["possible"] == 0 and r["why_not_scored"] and r["category"] == "experimental"
    assert {k: v["earned"] for k, v in plain["categories"].items()} == {cat: w for cat, _, w in c.CATEGORIES}


def test_partial_credit_is_a_share_of_the_weight(monkeypatch):
    # two of the five tracked crawlers shut out: 3/5 of 8 points is 4.8, so 5
    result = scan(monkeypatch, robots_extra="User-agent: GPTBot\nDisallow: /\n\nUser-agent: ClaudeBot\nDisallow: /\n")
    crawlers = by_name(result)["AI crawlers allowed"]
    assert crawlers["status"] == "partial" and (crawlers["earned"], crawlers["possible"]) == (5, 8)
    assert result["score"] == 97
    assert c._points(7, 0.5) == 4 and c._points(5, 2 / 4) == 3 and c._points(5, 1 / 3) == 2


def test_the_report_puts_the_experimental_checks_in_a_section_of_their_own(monkeypatch):
    result = scan(monkeypatch)
    text = c.format_report(result)
    scored_part, experimental_part = text.split("## Experimental standards: not scored")
    assert "llms.txt" not in scored_part and "WebMCP" not in scored_part
    assert "✗ llms.txt exists [not scored]" in experimental_part and "○ llms.txt title and links [Not checked]" in experimental_part
    assert experimental_part.count("Why not scored:") == 3          # the two llms.txt checks share one reason
    assert "fewer than 15 sites" in experimental_part and "origin trial" in experimental_part
    assert result["improve_prompt"].startswith("acme.example passed every scored check; nothing to fix.")
    assert "Not in this list: llms.txt exists, WebMCP tools, MCP Server Card." in result["improve_prompt"]


def test_the_readme_tables_match_the_checks():
    root = Path(__file__).resolve().parents[1]
    scored = {s["name"]: s for s in c.CHECK_SPECS if s["tier"] == "scored"}
    for readme in ("README.md", "README.zh-CN.md"):
        rows = re.findall(r"^\| ([A-Za-z -]+) \((\d+)\) \| (.+?) \| (\d+) \| (\d+) \|$", (root / readme).read_text(), re.M)
        assert len(rows) == 22, readme
        for label, cat_points, name, points, hostinger in rows:
            s = scored[name]
            assert (s["category_label"], s["weight"], s["hostinger"]) == (label, int(points), int(hostinger)), (readme, name)
            assert dict((cid, w) for cid, _, w in c.CATEGORIES)[s["category"]] == int(cat_points), (readme, name)


def test_one_version():
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    assert re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1) == c.__version__
