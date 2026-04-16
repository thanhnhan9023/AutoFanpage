"""Pure helpers for the notebooklm-analyzer skill.

Concretely: reading the Plan 2 ``merged_sources.json`` URL list (already
deduplicated and per-platform-capped by Plan 2's merge step), canonicalizing
URLs for the MCP tool, and applying an optional cap.

No network I/O here — those live in the skill script.
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


DEFAULT_MAX_SOURCES = 48


_STRIP_QUERY_PREFIXES = ("utm_", "ref_", "gclid", "fbclid", "mc_")


def canonicalize(url: str | None) -> str:
    """Return a canonical form of ``url`` suitable for dedup comparison."""
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return ""
    if not p.scheme or not p.netloc:
        return ""
    q = [
        (k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
        if not any(k.lower().startswith(pref) for pref in _STRIP_QUERY_PREFIXES)
    ]
    return urlunparse((
        p.scheme.lower(), p.netloc.lower(), p.path, p.params,
        urlencode(q), "",
    ))


def extract_urls(
    merged: dict,
    *,
    max_sources: int = DEFAULT_MAX_SOURCES,
) -> list[str]:
    """Extract URL list from a Plan 2 ``merged_sources.json``."""
    out: list[str] = []
    for entry in merged.get("urls") or []:
        raw = entry.get("url") if isinstance(entry, dict) else entry
        canon = canonicalize(raw)
        if not canon:
            continue
        out.append(canon)
        if len(out) >= max_sources:
            break
    return out
