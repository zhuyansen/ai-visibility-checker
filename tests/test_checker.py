"""Offline tests: robots.txt reading, grades and the fix prompts. No network."""
import ai_visibility_checker as c


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


def test_prompts_list_failed_checks_most_points_first():
    results = [
        {"name": "One clear H1", "evidence": "3 h1 tags", "fix": "Keep one.", "status": "partial", "earned": 1, "possible": 2},
        {"name": "Sitemap with pages", "evidence": "404", "fix": "Serve one.", "status": "fail", "earned": 0, "possible": 5},
        {"name": "JSON-LD", "evidence": "found", "fix": None, "status": "pass", "earned": 4, "possible": 4},
    ]
    p = c.improve_score_prompt("x.example", results)
    assert p.index("Sitemap with pages") < p.index("One clear H1") and "JSON-LD" not in p
    one = c.single_check_prompt("x.example", results[1])
    assert "x.example" in one and "Serve one." in one
    assert "nothing to fix" in c.improve_score_prompt("x.example", results[2:])


def test_every_check_adds_up_to_its_category():
    for cat, _, weight in c.CATEGORIES:
        assert sum(s["weight"] for s in c.CHECK_SPECS if s["category"] == cat) == weight
    assert sum(w for _, _, w in c.CATEGORIES) == 100 and len(c.CHECK_SPECS) == 26
