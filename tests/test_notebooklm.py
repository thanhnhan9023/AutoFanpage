from autofanpage.notebooklm import (
    extract_urls,
    canonicalize,
    DEFAULT_MAX_SOURCES,
)


def test_canonicalize_strips_utm_and_fragment():
    assert canonicalize("https://example.com/a?utm_source=x&b=1#frag") == \
        "https://example.com/a?b=1"


def test_canonicalize_lowercases_host_keeps_path_case():
    assert canonicalize("HTTPS://Example.COM/Path/Foo") == \
        "https://example.com/Path/Foo"


def test_canonicalize_empty_string_returns_empty():
    assert canonicalize("") == ""
    assert canonicalize(None) == ""


def test_extract_urls_reads_urls_list_directly():
    merged = {
        "topic": "AI",
        "language": "vi",
        "counts_per_platform": {"youtube": 2, "reddit": 1, "hackernews": 1},
        "urls": [
            {"url": "https://y/1",  "title": "a", "platform": "youtube",
             "score_or_views": 150000, "created_at": "2026-04-10T00:00:00Z"},
            {"url": "https://r/1",  "title": "b", "platform": "reddit",
             "score_or_views": 800, "created_at": "2026-04-14T00:00:00Z"},
            {"url": "https://h/1",  "title": "c", "platform": "hackernews",
             "score_or_views": 300, "created_at": "2026-04-14T00:00:00Z"},
            {"url": "https://y/2",  "title": "d", "platform": "youtube",
             "score_or_views": 90000, "created_at": "2026-04-11T00:00:00Z"},
        ],
    }
    urls = extract_urls(merged)
    assert urls == ["https://y/1", "https://r/1", "https://h/1", "https://y/2"]


def test_extract_urls_caps_at_default_limit():
    many = {"topic": "x", "language": "vi", "counts_per_platform": {"youtube": 80},
            "urls": [
        {"url": f"https://y/{i}", "title": str(i), "platform": "youtube",
         "score_or_views": 0, "created_at": ""}
        for i in range(80)
    ]}
    assert len(extract_urls(many)) == DEFAULT_MAX_SOURCES


def test_extract_urls_respects_explicit_cap():
    many = {"topic": "x", "language": "vi", "counts_per_platform": {"youtube": 30},
            "urls": [
        {"url": f"https://y/{i}", "title": str(i), "platform": "youtube",
         "score_or_views": 0, "created_at": ""}
        for i in range(30)
    ]}
    assert len(extract_urls(many, max_sources=10)) == 10
