#!/usr/bin/env python3
"""
ai-visibility-checker: can AI crawlers and agents read, understand and use a website?

26 checks in two tiers. The 22 that AI crawlers and agents use today make the score, out of 100.
The 4 experimental standards (llms.txt, WebMCP, an MCP Server Card) are reported apart, with their
fixes, and never added to the score: EXPERIMENTAL_WHY says why for each.

The checks and their categories follow Hostinger's free AI Visibility Checker. The scoring does not:
each scored check keeps its share of Hostinger's points (`hostinger`), scaled from 83 to 100. The code,
the wording and the fix prompts are our own; this project is not affiliated with Hostinger.

Usage:
  ai-visibility-checker example.com
  ai-visibility-checker example.com --json
  ai-visibility-checker example.com --no-prompts
"""

from __future__ import annotations

import argparse
import datetime as dt
import html.parser
import json
import re
import secrets
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

__version__ = "0.2.0"

AI_AGENT_UA = (
    "Mozilla/5.0 (compatible; ChatGPT-User/1.0; +https://openai.com/bot) "
    "AppleWebKit/537.36 (KHTML, like Gecko)"
)
TRACKED_CRAWLERS = [
    "GPTBot",
    "ClaudeBot",
    "ChatGPT-User",
    "Google-Extended",
    "PerplexityBot",
]
BOT_CHALLENGE_PATTERNS = re.compile(
    r"just a moment|checking your browser|attention required! \| cloudflare|"
    r"cf-browser-verification|ddos-guard|verify you are human|enable javascript and cookies to continue",
    re.I,
)
EDITORIAL_PATH_RE = re.compile(
    r"/(?:blog|news|post|posts|article|articles)(?:/|$)|/\d{4}/", re.I
)

# The scored categories and their points, out of 100. Experimental checks belong to none of them.
CATEGORIES = [
    ("crawl_permission", "Crawl permission", 23),
    ("readability", "Readability", 23),
    ("findability", "Findability", 20),
    ("structured_meaning", "Structured meaning", 16),
    ("commercial_legibility", "Commercial legibility", 15),
    ("agent_native_content", "Agent-native content", 3),
]
EXPERIMENTAL = ("experimental", "Experimental standards")

# Why each experimental check stays out of the score (sources read 2026-11-21). A check moves into
# the score once agents use it.
_LLMS_TXT_WHY = (
    'Google: "You don\'t need to create new machine readable files, AI text files, or markup to appear in '
    'these features" (developers.google.com/search/docs/appearance/ai-features). Ahrefs, 2026-06-15: 97% of '
    "the llms.txt files on 137,210 sites got no traffic in May 2026 (ahrefs.com/blog/llmstxt-study)."
)
EXPERIMENTAL_WHY = {
    "agent_native_content.llms_txt_exists": _LLMS_TXT_WHY,
    "agent_native_content.llms_txt_quality": _LLMS_TXT_WHY,
    "agent_interaction.webmcp_tools": (
        "WebMCP is still an origin trial in Chrome: Lighthouse's WebMCP audits require registering for it "
        "(developer.chrome.com/docs/lighthouse/agentic-browsing/scoring)."
    ),
    "agent_interaction.mcp_server_card": (
        "Cloudflare, 2026-04-17: on the 200,000 most visited domains, MCP Server Cards and API Catalogs "
        "together appear on fewer than 15 sites (blog.cloudflare.com/agent-readiness)."
    ),
}

# Each check: `hostinger` is its points in Hostinger's checker (26 checks, 100 points). A scored check's
# `weight` is that times 100/83, the 83 points left once the experimental 17 are out, in whole points that
# add up to 100: largest remainders first; of the six 3-point checks (3.61 each), five round up and
# Content-Signal, the one with the least evidence that agents act on it, stays at 3. Experimental: weight 0.
# The ids are those of 0.1.0, so JSON read before still matches.
CHECK_SPECS: list[dict[str, Any]] = [
    # 1. Crawl permission (23 pts)
    {
        "id": "crawl_permission.robots_txt_valid",
        "category": "crawl_permission",
        "category_label": "Crawl permission",
        "name": "robots.txt can be fetched and read",
        "short_name": "robots.txt readable",
        "weight": 5,
        "tier": "scored",
        "hostinger": 4,
    },
    {
        "id": "crawl_permission.ai_crawlers_allowed",
        "category": "crawl_permission",
        "category_label": "Crawl permission",
        "name": "robots.txt lets the major AI crawlers in",
        "short_name": "AI crawlers allowed",
        "weight": 8,
        "tier": "scored",
        "hostinger": 7,
    },
    {
        "id": "crawl_permission.not_bot_blocked",
        "category": "crawl_permission",
        "category_label": "Crawl permission",
        "name": "An AI agent gets the page, not a bot challenge",
        "short_name": "No bot challenge",
        "weight": 7,
        "tier": "scored",
        "hostinger": 6,
    },
    {
        "id": "crawl_permission.content_signals",
        "category": "crawl_permission",
        "category_label": "Crawl permission",
        "name": "robots.txt says how the content may be used (Content-Signal)",
        "short_name": "Content-Signal line",
        "weight": 3,
        "tier": "scored",
        "hostinger": 3,
    },
    # 2. Readability (23 pts)
    {
        "id": "readability.content_without_js",
        "category": "readability",
        "category_label": "Readability",
        "name": "The main text is in the HTML the server sends",
        "short_name": "Text without JavaScript",
        "weight": 10,
        "tier": "scored",
        "hostinger": 8,
    },
    {
        "id": "readability.token_budget",
        "category": "readability",
        "category_label": "Readability",
        "name": "The page is not padded with markup",
        "short_name": "Lean page",
        "weight": 4,
        "tier": "scored",
        "hostinger": 3,
    },
    {
        "id": "readability.head_metadata",
        "category": "readability",
        "category_label": "Readability",
        "name": "The page has a title, a description and a canonical URL",
        "short_name": "Title, description, canonical",
        "weight": 5,
        "tier": "scored",
        "hostinger": 4,
    },
    {
        "id": "readability.heading_structure",
        "category": "readability",
        "category_label": "Readability",
        "name": "One H1 that names the page",
        "short_name": "One clear H1",
        "weight": 4,
        "tier": "scored",
        "hostinger": 3,
    },
    # 3. Findability (20 pts)
    {
        "id": "findability.sitemap_valid",
        "category": "findability",
        "category_label": "Findability",
        "name": "A sitemap can be fetched and lists pages",
        "short_name": "Sitemap with pages",
        "weight": 6,
        "tier": "scored",
        "hostinger": 5,
    },
    {
        "id": "findability.sitemap_declared",
        "category": "findability",
        "category_label": "Findability",
        "name": "robots.txt points to the sitemap",
        "short_name": "Sitemap in robots.txt",
        "weight": 4,
        "tier": "scored",
        "hostinger": 3,
    },
    {
        "id": "findability.sitemap_freshness",
        "category": "findability",
        "category_label": "Findability",
        "name": "The sitemap says when pages last changed",
        "short_name": "lastmod in the sitemap",
        "weight": 4,
        "tier": "scored",
        "hostinger": 3,
    },
    {
        "id": "findability.real_status_codes",
        "category": "findability",
        "category_label": "Findability",
        "name": "A page that does not exist answers 404",
        "short_name": "Real 404s",
        "weight": 4,
        "tier": "scored",
        "hostinger": 3,
    },
    {
        "id": "findability.redirect_hygiene",
        "category": "findability",
        "category_label": "Findability",
        "name": "The homepage loads over HTTPS with at most one redirect",
        "short_name": "HTTPS, one hop",
        "weight": 2,
        "tier": "scored",
        "hostinger": 2,
    },
    # 4. Structured meaning (16 pts)
    {
        "id": "structured_meaning.json_ld_present",
        "category": "structured_meaning",
        "category_label": "Structured meaning",
        "name": "The page carries JSON-LD",
        "short_name": "JSON-LD",
        "weight": 7,
        "tier": "scored",
        "hostinger": 6,
    },
    {
        "id": "structured_meaning.organization_completeness",
        "category": "structured_meaning",
        "category_label": "Structured meaning",
        "name": "The Organization (or LocalBusiness) node is filled in",
        "short_name": "Organization filled in",
        "weight": 5,
        "tier": "scored",
        "hostinger": 4,
    },
    {
        "id": "structured_meaning.same_as",
        "category": "structured_meaning",
        "category_label": "Structured meaning",
        "name": "sameAs ties the site to its profiles elsewhere",
        "short_name": "sameAs profiles",
        "weight": 2,
        "tier": "scored",
        "hostinger": 2,
    },
    {
        "id": "structured_meaning.schema_breadth",
        "category": "structured_meaning",
        "category_label": "Structured meaning",
        "name": "JSON-LD describes more than one kind of thing",
        "short_name": "Schema variety",
        "weight": 2,
        "tier": "scored",
        "hostinger": 2,
    },
    # 5. Commercial legibility (15 pts)
    {
        "id": "commercial_legibility.trust_anchors",
        "category": "commercial_legibility",
        "category_label": "Commercial legibility",
        "name": "The homepage links to about, contact and legal pages",
        "short_name": "About, contact, legal",
        "weight": 5,
        "tier": "scored",
        "hostinger": 4,
    },
    {
        "id": "commercial_legibility.machine_readable_contact",
        "category": "commercial_legibility",
        "category_label": "Commercial legibility",
        "name": "Contact details are text a machine can read",
        "short_name": "Readable contact",
        "weight": 5,
        "tier": "scored",
        "hostinger": 4,
    },
    {
        "id": "commercial_legibility.pricing_reachable",
        "category": "commercial_legibility",
        "category_label": "Commercial legibility",
        "name": "Prices can be read without JavaScript or a login",
        "short_name": "Readable prices",
        "weight": 5,
        "tier": "scored",
        "hostinger": 4,
    },
    # 6. Agent-native content (3 pts); llms.txt is experimental
    {
        "id": "agent_native_content.llms_txt_exists",
        "category": "experimental",
        "category_label": "Experimental standards",
        "name": "/llms.txt exists",
        "short_name": "llms.txt exists",
        "weight": 0,
        "tier": "experimental",
        "hostinger": 4,
    },
    {
        "id": "agent_native_content.llms_txt_quality",
        "category": "experimental",
        "category_label": "Experimental standards",
        "name": "/llms.txt has a title and links",
        "short_name": "llms.txt title and links",
        "weight": 0,
        "tier": "experimental",
        "hostinger": 3,
    },
    {
        "id": "agent_native_content.markdown_negotiation",
        "category": "agent_native_content",
        "category_label": "Agent-native content",
        "name": "Asking for Markdown gets Markdown back",
        "short_name": "Markdown on request",
        "weight": 2,
        "tier": "scored",
        "hostinger": 2,
    },
    {
        "id": "agent_native_content.link_headers",
        "category": "agent_native_content",
        "category_label": "Agent-native content",
        "name": "The homepage's Link header points to machine-readable versions",
        "short_name": "Link header",
        "weight": 1,
        "tier": "scored",
        "hostinger": 1,
    },
    # 7. Agent interaction: experimental, not scored
    {
        "id": "agent_interaction.webmcp_tools",
        "category": "experimental",
        "category_label": "Experimental standards",
        "name": "The page registers WebMCP tools for in-browser agents",
        "short_name": "WebMCP tools",
        "weight": 0,
        "tier": "experimental",
        "hostinger": 6,
    },
    {
        "id": "agent_interaction.mcp_server_card",
        "category": "experimental",
        "category_label": "Experimental standards",
        "name": "An MCP Server Card is published",
        "short_name": "MCP Server Card",
        "weight": 0,
        "tier": "experimental",
        "hostinger": 4,
    },
]


class _RedirectTracker(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.hops: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.hops.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 12,
) -> dict[str, Any]:
    tracker = _RedirectTracker()
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        tracker, urllib.request.HTTPSHandler(context=ctx)
    )
    req_headers = {"User-Agent": AI_AGENT_UA}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read(2_500_000)
            text = raw.decode("utf-8", errors="replace")
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return {
                "status": resp.status,
                "url": resp.geturl(),
                "hops": len(tracker.hops),
                "headers": hdrs,
                "text": text,
                "error": None,
            }
    except urllib.error.HTTPError as e:
        raw = e.read(200_000) if e.fp else b""
        hdrs = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        return {
            "status": e.code,
            "url": e.geturl() or url,
            "hops": len(tracker.hops),
            "headers": hdrs,
            "text": raw.decode("utf-8", errors="replace"),
            "error": str(e),
        }
    except Exception as e:
        return {
            "status": 0,
            "url": url,
            "hops": len(tracker.hops),
            "headers": {},
            "text": "",
            "error": str(e),
        }


class _DOMInspector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_tag: list[str] = []
        self.title: str = ""
        self.meta_desc: str = ""
        self.canonical: str = ""
        self.h1_count: int = 0
        self.heading_count: int = 0
        self.links: list[str] = []
        self.json_ld_raw: list[str] = []
        self._curr_json_ld: list[str] = []
        self._in_json_ld: bool = False
        self.text_chunks: list[str] = []
        self.webmcp_forms: list[str] = []
        self.scripts_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        self._in_tag.append(t)
        ad = {k.lower(): (v or "") for k, v in attrs}
        if t == "meta":
            name = ad.get("name", "").lower()
            if name == "description" and ad.get("content", "").strip():
                self.meta_desc = ad["content"].strip()
        elif t == "link":
            rels = [r.lower() for r in ad.get("rel", "").split()]
            if "canonical" in rels and ad.get("href", "").strip():
                self.canonical = ad["href"].strip()
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.heading_count += 1
            if t == "h1":
                self.h1_count += 1
        elif t == "a" and ad.get("href"):
            self.links.append(ad["href"].strip())
        elif t == "form":
            if ad.get("toolname") and ad.get("tooldescription"):
                self.webmcp_forms.append(ad["toolname"])
        elif t == "script":
            if "application/ld+json" in ad.get("type", "").lower():
                self._in_json_ld = True
                self._curr_json_ld = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "script" and self._in_json_ld:
            self._in_json_ld = False
            self.json_ld_raw.append("".join(self._curr_json_ld))
        if self._in_tag and self._in_tag[-1] == t:
            self._in_tag.pop()

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._curr_json_ld.append(data)
        curr = self._in_tag[-1] if self._in_tag else ""
        if curr == "title" and not self.title:
            self.title = data.strip()
        if curr == "script":
            self.scripts_text.append(data)
        self.text_chunks.append(data)


def _parse_robots_for_ai(robots_txt: str) -> dict[str, Any]:
    sitemaps: list[str] = []
    content_signals: list[str] = []
    groups: dict[str, list[tuple[str, str]]] = {}
    current_agents: list[str] = []
    last_was_agent = False          # user-agent lines in a row form one group (RFC 9309)

    for raw_line in robots_txt.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = [p.strip() for p in line.split(":", 1)]
        kl = k.lower()
        if kl == "user-agent":
            agent = v.lower()
            current_agents = current_agents + [agent] if last_was_agent else [agent]
            groups.setdefault(agent, [])
            last_was_agent = True
            continue
        last_was_agent = False
        if kl in ("allow", "disallow"):
            for ag in current_agents or ["*"]:
                groups.setdefault(ag, []).append((kl, v))
        elif kl == "sitemap" and v:
            sitemaps.append(v)
        elif kl in ("content-signal", "content-signals") and v:
            content_signals.append(v)

    def is_allowed(bot: str) -> bool:
        bl = bot.lower()
        rules = groups.get(bl, groups.get("*", []))
        best_len = -1
        allowed = True
        for directive, path in rules:
            if not path:
                continue
            if "/".startswith(path) or path == "/":
                if len(path) > best_len:
                    best_len = len(path)
                    allowed = directive == "allow"
        return allowed

    allowed_bots = [b for b in TRACKED_CRAWLERS if is_allowed(b)]
    blocked_bots = [b for b in TRACKED_CRAWLERS if b not in allowed_bots]
    return {
        "sitemaps": sitemaps,
        "content_signals": content_signals,
        "allowed_bots": allowed_bots,
        "blocked_bots": blocked_bots,
    }


def _flatten_json_ld(blocks: list[str]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if "@type" in obj:
                nodes.append(obj)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    for raw in blocks:
        try:
            data = json.loads(raw)
            walk(data)
        except Exception:
            continue
    return nodes


def _node_types(node: dict[str, Any]) -> list[str]:
    t = node.get("@type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [str(x) for x in t if isinstance(x, str)]
    return []


def _grade_for_score(score: int) -> tuple[str, str]:
    if score >= 90:
        return "A", "Agent-ready"
    if score >= 75:
        return "B", "Almost agent-ready"
    if score >= 60:
        return "C", "Partly agent-ready"
    if score >= 40:
        return "D", "Not agent-ready yet"
    return "F", "Not agent-ready yet"


def _points(weight: int, share: float) -> int:
    """`share` of a check's `weight`, from 0 to 1, in whole points (halves round up)."""
    return int(weight * share + 0.5)


def single_check_prompt(domain: str, check: dict[str, Any]) -> str:
    """A prompt for a coding agent that fixes one failed check."""
    lines = [
        f"On {domain}, make this true: {check['name']}.",
        f"What the check found: {check['evidence']}",
        f"Suggested change: {check.get('fix') or ''}",
    ]
    if check.get("tier") == "experimental":
        lines.append("This is an experimental standard: few agents use it yet, and it does not change the score.")
    lines.append("Change only what this needs, then tell me which files you touched.")
    return "\n".join(lines)


def improve_score_prompt(domain: str, results: list[dict[str, Any]]) -> str:
    """One prompt for a coding agent with every scored check that failed or passed in part, most points
    first. Failed experimental checks are named at the end and left out: they do not change the score."""
    failing = [r for r in results if r["status"] in ("fail", "partial") and r.get("fix")]
    actionable = [r for r in failing if r.get("tier", "scored") == "scored"]
    left_out = [r["short_name"] for r in failing if r.get("tier") == "experimental"]
    note = (
        [f"Not in this list: {', '.join(left_out)}. These are experimental standards and do not change the score."]
        if left_out
        else []
    )
    if not actionable:
        return "\n\n".join([f"{domain} passed every scored check; nothing to fix.", *note])
    actionable.sort(key=lambda r: r["possible"] - r["earned"], reverse=True)
    items = []
    for idx, r in enumerate(actionable, 1):
        lost = r["possible"] - r["earned"]
        items.append(f"{idx}. {r['name']} ({lost} point{'' if lost == 1 else 's'})\n   Found: {r['evidence']}\n   Change: {r['fix']}")
    return "\n\n".join(
        [f"These checks failed on {domain}. Fix them in this order, and change only what each one needs:", *items, *note]
    )


def scan_domain(raw_domain: str) -> dict[str, Any]:
    domain = (
        raw_domain.strip()
        .lower()
        .removeprefix("https://")
        .removeprefix("http://")
        .removeprefix("www.")
        .split("/")[0]
        .split("?")[0]
        .split("#")[0]
    )
    base_url = f"https://{domain}"

    home_res = _fetch(f"{base_url}/")
    robots_res = _fetch(f"{base_url}/robots.txt")
    llms_res = _fetch(f"{base_url}/llms.txt")
    md_res = _fetch(f"{base_url}/", headers={"Accept": "text/markdown"})
    probe_slug = f"__agent-readiness-probe-{secrets.token_hex(6)}"
    probe_404_res = _fetch(f"{base_url}/{probe_slug}")
    mcp_card_res = _fetch(f"{base_url}/.well-known/mcp/server-card.json")

    dom = _DOMInspector()
    try:
        dom.feed(home_res["text"])
    except Exception:
        pass

    robots_ok = (
        200 <= robots_res["status"] < 300
        and len(robots_res["text"].strip()) > 0
        and "<html" not in robots_res["text"][:300].lower()
    )
    robots_info = _parse_robots_for_ai(robots_res["text"] if robots_ok else "")

    # Sitemap fetch (declared in robots.txt or /sitemap.xml)
    sitemap_url = (
        robots_info["sitemaps"][0]
        if robots_info["sitemaps"]
        else f"{base_url}/sitemap.xml"
    )
    if sitemap_url.startswith("/"):
        sitemap_url = f"{base_url}{sitemap_url}"
    sitemap_res = _fetch(sitemap_url)

    results: list[dict[str, Any]] = []

    def add_result(
        check_id: str,
        status: str,
        share: float,
        evidence: str,
        fix: str | None = None,
    ) -> None:
        """`share`: how much of the check passed, from 0 to 1. A scored check earns that share of its
        weight; an experimental one earns nothing and carries the reason it is not scored."""
        spec = next(s for s in CHECK_SPECS if s["id"] == check_id)
        scored = spec["tier"] == "scored"
        item: dict[str, Any] = {
            "check_id": check_id,
            "name": spec["name"],
            "short_name": spec["short_name"],
            "category": spec["category"],
            "category_label": spec["category_label"],
            "tier": spec["tier"],
            "status": status,
            "earned": _points(spec["weight"], share) if scored else 0,
            "possible": spec["weight"],
            "evidence": evidence,
            "fix": fix,
        }
        if not scored:
            item["why_not_scored"] = EXPERIMENTAL_WHY[check_id]
        if status in ("fail", "partial") and fix:
            item["prompt"] = single_check_prompt(domain, item)
        results.append(item)

    # --- 1. CRAWL PERMISSION (23 pts) ---
    # 1.1 robots_txt_valid (5 pts)
    if robots_ok:
        add_result(
            "crawl_permission.robots_txt_valid",
            "pass",
            1,
            "robots.txt served and parsed.",
        )
    else:
        add_result(
            "crawl_permission.robots_txt_valid",
            "fail",
            0,
            "/robots.txt is missing or empty.",
            "Serve a robots.txt at /robots.txt.",
        )

    # 1.2 ai_crawlers_allowed (8 pts)
    allowed_count = len(robots_info["allowed_bots"])
    if allowed_count == len(TRACKED_CRAWLERS):
        add_result(
            "crawl_permission.ai_crawlers_allowed",
            "pass",
            1,
            "All tracked AI crawlers may read the homepage.",
        )
    elif allowed_count == 0:
        add_result(
            "crawl_permission.ai_crawlers_allowed",
            "fail",
            0,
            f"Blocked by robots.txt: {', '.join(robots_info['blocked_bots'])}.",
            "Remove the Disallow rules for these crawlers, unless keeping them out is the point.",
        )
    else:
        share = allowed_count / len(TRACKED_CRAWLERS)
        add_result(
            "crawl_permission.ai_crawlers_allowed",
            "partial",
            share,
            f"Blocked by robots.txt: {', '.join(robots_info['blocked_bots'])}.",
            "Remove the Disallow rules for these crawlers, unless keeping them out is the point.",
        )

    # 1.3 not_bot_blocked (7 pts)
    if home_res["status"] in (401, 403, 429, 503):
        add_result(
            "crawl_permission.not_bot_blocked",
            "fail",
            0,
            "Homepage blocked an AI agent user-agent.",
            "Let AI agents' user agents through your firewall or bot protection.",
        )
    elif 200 <= home_res["status"] < 300:
        if BOT_CHALLENGE_PATTERNS.search(home_res["text"][:4000]):
            add_result(
                "crawl_permission.not_bot_blocked",
                "partial",
                0.5,
                "Homepage returned a bot challenge page to an AI agent user-agent.",
                "Let AI agents' user agents through your firewall or bot protection.",
            )
        else:
            add_result(
                "crawl_permission.not_bot_blocked",
                "pass",
                1,
                "Homepage loaded for an AI agent user-agent.",
            )
    else:
        add_result(
            "crawl_permission.not_bot_blocked",
            "fail",
            0,
            f"Homepage returned HTTP {home_res['status']}.",
            "Let AI agents' user agents through your firewall or bot protection.",
        )

    # 1.4 content_signals (3 pts)
    if robots_info["content_signals"]:
        add_result(
            "crawl_permission.content_signals",
            "pass",
            1,
            f"Content-Signal declared: {robots_info['content_signals'][0]}.",
        )
    else:
        add_result(
            "crawl_permission.content_signals",
            "fail",
            0,
            "No Content-Signal directive in robots.txt.",
            'Add a Content-Signal line to robots.txt saying how the content may be used, for example "search=yes, ai-train=no".',
        )

    # --- 2. FINDABILITY (20 pts) ---
    sitemap_entries = 0
    sitemap_is_index = False
    newest_lastmod: dt.date | None = None
    if 200 <= sitemap_res["status"] < 300 and sitemap_res["text"].strip():
        try:
            root = ET.fromstring(sitemap_res["text"].strip())
            tag_name = root.tag.split("}")[-1].lower()
            if tag_name in ("urlset", "sitemapindex"):
                sitemap_is_index = tag_name == "sitemapindex"
                locs = [
                    el.text.strip()
                    for el in root.iter()
                    if el.tag.split("}")[-1].lower() == "loc" and el.text
                ]
                sitemap_entries = len(locs)
                lastmods = [
                    el.text.strip()[:10]
                    for el in root.iter()
                    if el.tag.split("}")[-1].lower() == "lastmod" and el.text
                ]
                for lm in lastmods:
                    try:
                        d = dt.date.fromisoformat(lm)
                        if newest_lastmod is None or d > newest_lastmod:
                            newest_lastmod = d
                    except Exception:
                        pass
                if newest_lastmod is None and sitemap_is_index and locs:
                    child_res = _fetch(locs[0])
                    if 200 <= child_res["status"] < 300:
                        croot = ET.fromstring(child_res["text"].strip())
                        for el in croot.iter():
                            if el.tag.split("}")[-1].lower() == "lastmod" and el.text:
                                try:
                                    d = dt.date.fromisoformat(el.text.strip()[:10])
                                    if newest_lastmod is None or d > newest_lastmod:
                                        newest_lastmod = d
                                except Exception:
                                    pass
        except Exception:
            sitemap_entries = 0

    # 2.1 sitemap_valid (6 pts)
    if sitemap_entries > 0:
        kind = "sitemap index" if sitemap_is_index else "sitemap"
        add_result(
            "findability.sitemap_valid",
            "pass",
            1,
            f"Valid {kind} with {sitemap_entries} entries.",
        )
    else:
        add_result(
            "findability.sitemap_valid",
            "fail",
            0,
            "No parseable sitemap found.",
            "Serve a sitemap.xml that lists the pages you want read.",
        )

    # 2.2 sitemap_declared (4 pts)
    if robots_info["sitemaps"]:
        add_result(
            "findability.sitemap_declared",
            "pass",
            1,
            f"Declared: {robots_info['sitemaps'][0]}.",
        )
    else:
        add_result(
            "findability.sitemap_declared",
            "fail",
            0,
            "robots.txt does not declare a Sitemap: directive.",
            'Add a "Sitemap: https://your-domain/sitemap.xml" line to robots.txt.',
        )

    # 2.3 sitemap_freshness (4 pts)
    if sitemap_entries == 0:
        add_result(
            "findability.sitemap_freshness",
            "not_applicable",
            0,
            "No sitemap to assess.",
        )
    elif newest_lastmod and (dt.date.today() - newest_lastmod).days <= 180:
        add_result(
            "findability.sitemap_freshness",
            "pass",
            1,
            f"Newest lastmod is {newest_lastmod.isoformat()}.",
        )
    else:
        ev = (
            f"Newest lastmod is {newest_lastmod.isoformat()} (>180 days old)."
            if newest_lastmod
            else "No <lastmod> dates found in the sitemap."
        )
        add_result(
            "findability.sitemap_freshness",
            "fail",
            0,
            ev,
            "Give each URL in the sitemap a <lastmod> date.",
        )

    # 2.4 real_status_codes (4 pts)
    if probe_404_res["status"] in (404, 410):
        add_result(
            "findability.real_status_codes",
            "pass",
            1,
            "A non-existent URL correctly returned a not-found status.",
        )
    else:
        add_result(
            "findability.real_status_codes",
            "fail",
            0,
            f"A non-existent URL returned HTTP {probe_404_res['status']} instead of 404 or 410.",
            'Answer 404 (or 410) for pages that do not exist, not a redirect or a 200 page that says \"not found\".',
        )

    # 2.5 redirect_hygiene (2 pts)
    if (
        200 <= home_res["status"] < 300
        and home_res["hops"] <= 2
        and home_res["url"].startswith("https://")
    ):
        ev = (
            "Homepage served directly over HTTPS."
            if home_res["hops"] == 0
            else f"Homepage reached over HTTPS in {home_res['hops']} hop(s)."
        )
        add_result(
            "findability.redirect_hygiene",
            "pass",
            1,
            ev,
        )
    else:
        add_result(
            "findability.redirect_hygiene",
            "fail",
            0,
            f"Homepage took {home_res['hops']} redirects or did not end on HTTPS ({home_res['url']}).",
            "Redirect straight to the final address, in one step.",
        )

    # --- 3. READABILITY (23 pts) ---
    full_text = " ".join(t.strip() for t in dom.text_chunks if t.strip())
    text_len = len(full_text)
    html_len = len(home_res["text"])

    # 3.1 content_without_js (10 pts)
    if text_len >= 600:
        add_result(
            "readability.content_without_js",
            "pass",
            1,
            "Raw HTML contains plenty of readable text.",
        )
    elif text_len >= 200:
        add_result(
            "readability.content_without_js",
            "partial",
            0.5,
            "Raw HTML contains little text - thin for a homepage.",
            "Render the main text on the server, so it is in the HTML before any script runs.",
        )
    else:
        add_result(
            "readability.content_without_js",
            "fail",
            0,
            "Raw HTML contains almost no readable text without JavaScript.",
            "Render the main text on the server, so it is in the HTML before any script runs.",
        )

    # 3.2 token_budget (4 pts)
    ratio = (text_len / html_len) if html_len > 0 else 0.0
    if 0 < html_len <= 400_000 and ratio >= 0.05:
        add_result(
            "readability.token_budget",
            "pass",
            1,
            "The HTML is a reasonable size with enough readable text.",
        )
    else:
        add_result(
            "readability.token_budget",
            "fail",
            0,
            f"Raw HTML is {html_len:,} chars with a {ratio:.1%} text-to-HTML ratio.",
            "Move inline scripts and styles out and drop wrapper markup: a reader pays for every token of the page.",
        )

    # 3.3 head_metadata (5 pts)
    missing_head: list[str] = []
    if not dom.title:
        missing_head.append("title")
    if not dom.meta_desc:
        missing_head.append("meta description")
    if not dom.canonical:
        missing_head.append("canonical link")
    present_head = 3 - len(missing_head)
    if present_head == 3:
        add_result(
            "readability.head_metadata",
            "pass",
            1,
            "Title, meta description and canonical link are present.",
        )
    elif present_head > 0:
        share = present_head / 3
        add_result(
            "readability.head_metadata",
            "partial",
            share,
            f"Missing: {', '.join(missing_head)}.",
            "Add the missing <title>, meta description or canonical link.",
        )
    else:
        add_result(
            "readability.head_metadata",
            "fail",
            0,
            "Missing: title, meta description, canonical link.",
            "Add the missing <title>, meta description or canonical link.",
        )

    # 3.4 heading_structure (4 pts)
    if dom.h1_count == 1:
        add_result(
            "readability.heading_structure",
            "pass",
            1,
            f"One <h1> and {dom.heading_count} headings in total.",
        )
    elif dom.h1_count > 1:
        add_result(
            "readability.heading_structure",
            "partial",
            2 / 3,
            f"Found {dom.h1_count} <h1> elements ({dom.heading_count} headings total).",
            "Keep one <h1> and turn the others into <h2>.",
        )
    else:
        add_result(
            "readability.heading_structure",
            "fail",
            0,
            "No <h1> on the homepage.",
            "Add one <h1> that says what the page is about.",
        )

    # --- 4. STRUCTURED MEANING (16 pts) ---
    json_ld_nodes = _flatten_json_ld(dom.json_ld_raw)
    all_types: list[str] = []
    for n in json_ld_nodes:
        for t in _node_types(n):
            if t not in all_types:
                all_types.append(t)

    # 4.1 json_ld_present (7 pts)
    if json_ld_nodes:
        add_result(
            "structured_meaning.json_ld_present",
            "pass",
            1,
            f"Found {len(json_ld_nodes)} JSON-LD node(s): {', '.join(all_types)}.",
        )
    else:
        add_result(
            "structured_meaning.json_ld_present",
            "fail",
            0,
            "No valid JSON-LD found on the homepage.",
            "Add a JSON-LD block saying who runs the site and what it offers: the plainest statement an agent can read.",
        )

    # 4.2 organization_completeness (5 pts)
    org_types = {"Organization", "LocalBusiness", "Store", "Restaurant", "Corporation"}
    org_node = next(
        (n for n in json_ld_nodes if org_types.intersection(_node_types(n))),
        None,
    )
    if org_node is None:
        add_result(
            "structured_meaning.organization_completeness",
            "fail",
            0,
            "No Organization or LocalBusiness node in the structured data.",
            "Add an Organization (or LocalBusiness) node to the JSON-LD.",
        )
    else:
        req_fields = ["name", "url", "telephone", "address"]
        missing_org = [f for f in req_fields if not org_node.get(f)]
        present_org = 4 - len(missing_org)
        if present_org == 4:
            add_result(
                "structured_meaning.organization_completeness",
                "pass",
                1,
                "Organization/LocalBusiness node has name, url, telephone and address.",
            )
        else:
            share = present_org / 4
            add_result(
                "structured_meaning.organization_completeness",
                "partial" if present_org else "fail",
                share,
                f"Business node is missing: {', '.join(missing_org)}.",
                "Fill in the missing fields (name, url, logo, contact) so questions about the business have an answer on the page.",
            )

    # 4.3 same_as (2 pts)
    same_as_links: list[str] = []
    for n in json_ld_nodes:
        sa = n.get("sameAs")
        if isinstance(sa, str) and sa.strip():
            same_as_links.append(sa.strip())
        elif isinstance(sa, list):
            same_as_links.extend(str(x).strip() for x in sa if str(x).strip())
    if same_as_links:
        add_result(
            "structured_meaning.same_as",
            "pass",
            1,
            f"Linked to {len(same_as_links)} external profile(s) via sameAs.",
        )
    else:
        add_result(
            "structured_meaning.same_as",
            "fail",
            0,
            "No sameAs links in the structured data.",
            "List your profiles elsewhere (GitHub, LinkedIn, X, directories) in sameAs, so the site and those profiles read as one entity.",
        )

    # 4.4 schema_breadth (2 pts)
    if len(all_types) >= 3:
        add_result(
            "structured_meaning.schema_breadth",
            "pass",
            1,
            f"Declares {len(all_types)} schema types: {', '.join(all_types)}.",
        )
    elif len(all_types) >= 1:
        add_result(
            "structured_meaning.schema_breadth",
            "partial",
            0.5,
            f"Only declares {len(all_types)} schema type(s): {', '.join(all_types)}.",
            "Give the other things on the site their own types too: products, services, articles, FAQs.",
        )
    else:
        add_result(
            "structured_meaning.schema_breadth",
            "fail",
            0,
            "No schema types declared.",
            "Add JSON-LD for the business, the site and the main kinds of content.",
        )

    # --- 5. COMMERCIAL LEGIBILITY (15 pts) ---
    non_editorial_paths: list[str] = []
    has_mailto_or_tel = False
    for href in dom.links:
        hl = href.lower()
        if hl.startswith(("mailto:", "tel:")):
            has_mailto_or_tel = True
            continue
        parsed = urllib.parse.urlparse(href)
        path = parsed.path.lower()
        if not path or EDITORIAL_PATH_RE.search(path):
            continue
        non_editorial_paths.append(path)

    # 5.1 trust_anchors (5 pts)
    has_about = any("about" in p for p in non_editorial_paths)
    has_contact = any("contact" in p for p in non_editorial_paths)
    has_legal = any(
        any(w in p for w in ("terms", "privacy", "legal", "tos", "policy"))
        for p in non_editorial_paths
    )
    missing_trust: list[str] = []
    if not has_about:
        missing_trust.append("about")
    if not has_contact:
        missing_trust.append("contact")
    if not has_legal:
        missing_trust.append("terms")
    found_trust = 3 - len(missing_trust)
    if found_trust == 3:
        add_result(
            "commercial_legibility.trust_anchors",
            "pass",
            1,
            "About, contact and legal/privacy pages are linked from the homepage.",
        )
    elif found_trust > 0:
        share = found_trust / 3
        add_result(
            "commercial_legibility.trust_anchors",
            "partial",
            share,
            f"No link found for: {', '.join(missing_trust)}.",
            "Link the missing pages from the homepage.",
        )
    else:
        add_result(
            "commercial_legibility.trust_anchors",
            "fail",
            0,
            "No about, contact or legal pages linked from the homepage.",
            "Link about, contact and terms pages from the homepage: they show there is a real business behind the site.",
        )

    # 5.2 machine_readable_contact (5 pts)
    has_schema_contact = any(
        n.get("telephone") or n.get("email") or n.get("contactPoint")
        for n in json_ld_nodes
    )
    if has_schema_contact:
        add_result(
            "commercial_legibility.machine_readable_contact",
            "pass",
            1,
            "Structured data exposes contactPoint.",
        )
    elif has_mailto_or_tel:
        add_result(
            "commercial_legibility.machine_readable_contact",
            "pass",
            1,
            "Homepage includes a mailto: or tel: link.",
        )
    else:
        add_result(
            "commercial_legibility.machine_readable_contact",
            "fail",
            0,
            "No mailto:, tel: or structured contact details on the homepage.",
            "Put an email address or phone number in text: a mailto:/tel: link, or the email/telephone field in JSON-LD. A number inside an image cannot be read.",
        )

    # 5.3 pricing_reachable (5 pts)
    price_types = {"Product", "Offer", "AggregateOffer"}
    has_schema_price = any(
        price_types.intersection(_node_types(n)) or n.get("offers")
        for n in json_ld_nodes
    )
    has_pricing_link = any(
        any(w in p for w in ("pricing", "prices", "plans", "kainos"))
        for p in non_editorial_paths
    )
    if has_schema_price:
        add_result(
            "commercial_legibility.pricing_reachable",
            "pass",
            1,
            "Prices are exposed in structured data.",
        )
    elif has_pricing_link:
        add_result(
            "commercial_legibility.pricing_reachable",
            "pass",
            1,
            "Homepage links directly to a pricing/plans page.",
        )
    else:
        add_result(
            "commercial_legibility.pricing_reachable",
            "fail",
            0,
            "No Offer structured data or pricing page link found on the homepage.",
            "Link a pricing page from the homepage, or add Offer markup with a price and a currency.",
        )

    # --- 6. AGENT-NATIVE CONTENT (3 pts; llms.txt experimental) ---
    llms_text = llms_res["text"].strip()
    llms_is_html = bool(
        re.match(r"^\s*<(?:!doctype\s+html|html|head|body)\b", llms_text, re.I)
    )
    llms_ok = (
        200 <= llms_res["status"] < 300
        and len(llms_text) > 0
        and not llms_is_html
    )

    # 6.1 llms_txt_exists (experimental, not scored)
    if llms_ok:
        add_result(
            "agent_native_content.llms_txt_exists",
            "pass",
            1,
            "/llms.txt is served as a text file.",
        )
    else:
        add_result(
            "agent_native_content.llms_txt_exists",
            "fail",
            0,
            "/llms.txt is missing or returned an error.",
            "Serve an /llms.txt with a short summary of the site and links to its main pages.",
        )

    # 6.2 llms_txt_quality (experimental, not scored)
    if not llms_ok:
        add_result(
            "agent_native_content.llms_txt_quality",
            "not_applicable",
            0,
            "No llms.txt to assess.",
        )
    else:
        has_h1_md = bool(re.search(r"^#\s+\S+", llms_text, re.M))
        md_links = re.findall(r"\[[^\]]+\]\(https?://[^)\s]+\)", llms_text)
        if has_h1_md and md_links:
            add_result(
                "agent_native_content.llms_txt_quality",
                "pass",
                1,
                f"Has a top-level heading and {len(md_links)} link(s).",
            )
        else:
            add_result(
                "agent_native_content.llms_txt_quality",
                "partial",
                1 / 3,
                "llms.txt is missing a top-level '# ' heading or Markdown http(s) links.",
                "Start /llms.txt with a '# Title' line and link the main pages as Markdown links: [Title](https://...).",
            )

    # 6.3 markdown_negotiation (2 pts)
    md_ct = md_res["headers"].get("content-type", "")
    if "text/markdown" in md_ct.lower():
        add_result(
            "agent_native_content.markdown_negotiation",
            "pass",
            1,
            f"Homepage returned '{md_ct}' for Accept: text/markdown.",
        )
    else:
        add_result(
            "agent_native_content.markdown_negotiation",
            "fail",
            0,
            f"Homepage returned '{md_ct or 'unknown'}' for Accept: text/markdown.",
            "Return Markdown when a request asks for text/markdown: it is far shorter than the HTML.",
        )

    # 6.4 link_headers (1 pts)
    link_hdr = home_res["headers"].get("link", "")
    if link_hdr:
        add_result(
            "agent_native_content.link_headers",
            "pass",
            1,
            f"Homepage emits Link header: {link_hdr}.",
        )
    else:
        add_result(
            "agent_native_content.link_headers",
            "fail",
            0,
            "No Link response header on the homepage.",
            "Send a Link header (RFC 8288) that points to llms.txt or to a Markdown version of the page.",
        )

    # --- 7. AGENT INTERACTION (experimental, not scored) ---
    # 7.1 webmcp_tools (experimental, not scored)
    has_js_webmcp = "modelcontext" in home_res["text"].lower() and "registertool" in home_res["text"].lower()
    if dom.webmcp_forms or has_js_webmcp:
        add_result(
            "agent_interaction.webmcp_tools",
            "pass",
            1,
            "WebMCP tool registration or annotated form detected on the homepage.",
        )
    else:
        add_result(
            "agent_interaction.webmcp_tools",
            "fail",
            0,
            "No WebMCP tools registered on page load.",
            "Register a tool when the page loads (navigator.modelContext.registerTool with a name, a description, an input schema and a function), or mark a form with toolname and tooldescription.",
        )

    # 7.2 mcp_server_card (experimental, not scored)
    mcp_ok = False
    mcp_ev = "/.well-known/mcp/server-card.json did not return HTTP 200."
    if 200 <= mcp_card_res["status"] < 300 and mcp_card_res["text"].strip():
        try:
            card = json.loads(mcp_card_res["text"])
            has_name_ver = bool(card.get("name") and card.get("version"))
            has_ep = bool(
                card.get("endpoint")
                or card.get("url")
                or card.get("endpoints")
                or card.get("remotes")
            )
            has_caps = bool(
                card.get("capabilities")
                or card.get("tools")
                or card.get("resources")
                or card.get("prompts")
            )
            if has_name_ver and has_ep and has_caps:
                mcp_ok = True
                mcp_ev = f"Published MCP Server Card: {card.get('name')} v{card.get('version')}."
            else:
                mcp_ev = "/.well-known/mcp/server-card.json is missing name, version, endpoint or capabilities."
        except Exception:
            mcp_ev = "/.well-known/mcp/server-card.json is not valid JSON."

    if mcp_ok:
        add_result(
            "agent_interaction.mcp_server_card",
            "pass",
            1,
            mcp_ev,
        )
    else:
        add_result(
            "agent_interaction.mcp_server_card",
            "fail",
            0,
            mcp_ev,
            "Serve an MCP Server Card (SEP-1649) at /.well-known/mcp/server-card.json: the server's name, version, endpoint and capabilities.",
        )

    # Aggregate categories & total score: the scored categories only; experimental checks are in none
    categories_summary: dict[str, dict[str, int]] = {}
    total_earned = 0
    for cat_id, _cat_label, cat_weight in CATEGORIES:
        cat_checks = [r for r in results if r["category"] == cat_id]
        earned = sum(r["earned"] for r in cat_checks)
        total_earned += earned
        categories_summary[cat_id] = {
            "score": earned,
            "earned": earned,
            "weight": cat_weight,
            "possible": cat_weight,
        }

    experimental = [r for r in results if r["tier"] == "experimental"]
    grade, grade_label = _grade_for_score(total_earned)
    return {
        "domain": domain,
        "status": "completed",
        "score": total_earned,
        "grade": grade,
        "grade_label": grade_label,
        "scanned_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "categories": categories_summary,
        "experimental": {
            "scored": False,
            "passed": sum(r["status"] == "pass" for r in experimental),
            "checks": len(experimental),
        },
        "results": results,
        "improve_prompt": improve_score_prompt(domain, results),
    }


def _check_lines(r: dict[str, Any]) -> list[str]:
    icon = {
        "pass": "✓",
        "partial": "◐",
        "fail": "✗",
        "not_applicable": "○",
    }.get(r["status"], "?")
    if r["status"] == "not_applicable":
        pts_str = "Not checked"
    elif r.get("tier") == "experimental":
        pts_str = "not scored"
    else:
        pts_str = f"{r['earned']}/{r['possible']} pts"
    out = [f"  {icon} {r['short_name']} [{pts_str}]", f"      What we found: {r['evidence']}"]
    if r.get("fix"):
        out.append(f"      How to fix:    {r['fix']}")
    return out


def format_report(scan: dict[str, Any], show_prompts: bool = True) -> str:
    lines: list[str] = []
    lines.append(
        f"=== AI Readiness Report: {scan['domain']} ==="
    )
    lines.append(
        f"Score: {scan['score']}/100  |  Grade {scan['grade']} ({scan['grade_label']})  |  Scanned: {scan['scanned_at']}"
    )
    lines.append("")

    for cat_id, cat_label, cat_weight in CATEGORIES:
        cat_info = scan["categories"][cat_id]
        pct = round(cat_info["earned"] / cat_weight * 100) if cat_weight else 0
        lines.append(
            f"## {cat_label}: {cat_info['earned']}/{cat_weight} pts ({pct}%)"
        )
        for r in scan["results"]:
            if r["category"] == cat_id:
                lines.extend(_check_lines(r))
        lines.append("")

    experimental = [r for r in scan["results"] if r.get("tier") == "experimental"]
    if experimental:
        lines.append(f"## {EXPERIMENTAL[1]}: not scored")
        lines.append("   Few sites publish these and few agents read them yet. The score above leaves them out.")
        reasons_shown: set[str] = set()
        for r in experimental:
            lines.extend(_check_lines(r))
            if r["why_not_scored"] not in reasons_shown:      # the two llms.txt checks share one reason
                reasons_shown.add(r["why_not_scored"])
                lines.append(f"      Why not scored: {r['why_not_scored']}")
        lines.append("")

    if show_prompts:
        lines.append("=== Ready-to-Paste AI Coding Agent Prompt (Improve Score) ===")
        lines.append(scan["improve_prompt"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Can AI crawlers and agents read your site? 22 scored checks out of 100, 4 experimental "
        "standards reported apart, and a prompt for a coding agent to fix what failed."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("domain", help="domain or URL to check, e.g. example.com")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--prompts", action="store_true", help=argparse.SUPPRESS)   # the prompt is shown by default
    parser.add_argument("--no-prompts", dest="prompts", action="store_false", help="Leave out the prompt for a coding agent")
    parser.set_defaults(prompts=True)
    args = parser.parse_args()
    scan = scan_domain(args.domain)
    if args.json:
        print(json.dumps(scan, indent=2, ensure_ascii=False))
    else:
        print(format_report(scan, show_prompts=args.prompts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
