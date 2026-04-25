from __future__ import annotations

import json
import subprocess

from autofanpage.errors import SourceFailedError

_AGENT_BROWSER_TIMEOUT_SECONDS = 60
_LATEST_POST_URL_JS = """
(() => {
  const normalize = (href) => {
    if (typeof href !== "string" || !href.trim()) return "";
    try {
      return new URL(href, window.location.href).toString();
    } catch (_err) {
      return "";
    }
  };
  const isPostUrl = (href) =>
    href.includes("/posts/") ||
    href.includes("story_fbid=") ||
    href.includes("/permalink/");

  const links = Array.from(document.querySelectorAll('a[href]'));
  for (const link of links) {
    const url = normalize(link.getAttribute("href") || "");
    if (!url || !isPostUrl(url)) continue;
    if (!url.startsWith("https://www.facebook.com/") && !url.startsWith("https://facebook.com/")) {
      continue;
    }
    return url;
  }
  return "";
})()
""".strip()
_RECENT_POST_URLS_JS = """
(() => {
  const normalize = (href) => {
    if (typeof href !== "string" || !href.trim()) return "";
    try {
      return new URL(href, window.location.href).toString();
    } catch (_err) {
      return "";
    }
  };
  const isPostUrl = (href) =>
    href.includes("/posts/") ||
    href.includes("story_fbid=") ||
    href.includes("/permalink/");
  const limit = 5;
  const seen = new Set();
  const postUrls = [];

  const links = Array.from(document.querySelectorAll('a[href]'));
  for (const link of links) {
    const url = normalize(link.getAttribute("href") || "");
    if (!url || !isPostUrl(url) || seen.has(url)) continue;
    if (!url.startsWith("https://www.facebook.com/") && !url.startsWith("https://facebook.com/")) {
      continue;
    }
    seen.add(url);
    postUrls.push(url);
    if (postUrls.length >= limit) break;
  }

  return {
    source_page_url: window.location.origin + window.location.pathname,
    fetched_at: new Date().toISOString(),
    search_status: postUrls.length ? "selection_ready" : "fetch_error",
    end_of_feed_reached: false,
    scan_stopped_reason: postUrls.length ? "selection_limit_reached" : "no_posts_found",
    posts_scanned: postUrls.length,
    post_urls: postUrls,
  };
})()
""".strip()
_EXTRACTION_JS = """
(() => {
  const text = (value) => typeof value === "string" ? value.trim() : "";
  const matchRelativeTime = (value) => {
    const raw = text(value);
    if (!raw) return "";
    const exact = raw.match(/^(\\d+\\s*[smhdw]|Yesterday|Today|Just now)$/i);
    if (exact) return exact[1];
    const embedded = raw.match(/(?:^|\\s)(\\d+\\s*[smhdw]|Yesterday|Today|Just now)(?:\\s|$)/i);
    return embedded ? embedded[1] : "";
  };
  const content = (name) => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return text(el?.content || "");
  };
  const relativePublishedAt = (() => {
    const nodes = Array.from(document.querySelectorAll("a[aria-label], a[href], span, div"));
    for (const node of nodes) {
      const candidate = matchRelativeTime(
        node.getAttribute?.("aria-label") || node.textContent || ""
      );
      if (candidate) return candidate;
    }
    return "";
  })();
  const authorLink = document.querySelector("h1 a, h2 a, h3 a, strong a");
  const canonical = text(document.querySelector('link[rel="canonical"]')?.href || "");
  const sourcePostUrl = window.location.origin + window.location.pathname || canonical || content("og:url");
  const publishedAt = content("article:published_time") || text(document.querySelector("time")?.getAttribute("datetime") || "") || relativePublishedAt;
  const author = content("author") || text(document.querySelector('meta[property="article:author"]')?.content || "") || text(authorLink?.textContent || "");
  const bodyText = text(document.body?.innerText || "").replace(/\\s+/g, " ").trim();
  const mediaUrls = Array.from(document.querySelectorAll("img[src], video[src]"))
    .map((el) => text(el.currentSrc || el.src || ""))
    .filter((url) => Boolean(url) && !url.startsWith("data:"));
  return {
    source_page_url: window.location.origin + window.location.pathname,
    source_post_url: sourcePostUrl,
    published_at: publishedAt,
    relative_published_at: relativePublishedAt,
    content_text: bodyText,
    author,
    media_urls: Array.from(new Set(mediaUrls)),
  };
})()
""".strip()


def _parse_agent_browser_json(raw_output: str, *, invalid_message: str) -> str | dict:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise SourceFailedError(f"{invalid_message}: {exc}") from exc
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        raise SourceFailedError("agent_browser returned non-object JSON")

    if "success" in payload and "data" in payload:
        if payload.get("success") is False:
            message = str(payload.get("error") or "agent_browser reported failure").strip()
            raise SourceFailedError(message)
        data = payload.get("data")
        if isinstance(data, dict) and "result" in data:
            result = data["result"]
            if isinstance(result, str):
                return result.strip()
            if isinstance(result, dict):
                return result
            raise SourceFailedError("agent_browser returned unsupported result type")
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            return data.strip()
        raise SourceFailedError("agent_browser returned unsupported data type")

    return payload


def _normalize_agent_browser_extract(
    payload: dict,
    *,
    page_url: str,
    latest_post_url: str,
) -> dict:
    normalized = dict(payload)
    normalized["source_page_url"] = page_url
    normalized["source_post_url"] = str(
        normalized.get("source_post_url") or latest_post_url
    ).strip() or latest_post_url

    published_at = str(normalized.get("published_at") or "").strip()
    if not published_at:
        published_at = str(normalized.get("relative_published_at") or "").strip()
    if published_at:
        normalized["published_at"] = published_at

    return normalized


def _run_agent_browser_command(
    *,
    base_cmd: list[str],
    step_args: list[str],
    json_output: bool = False,
) -> str:
    cmd = [*base_cmd, *step_args]
    if json_output:
        cmd.append("--json")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_AGENT_BROWSER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise SourceFailedError(
            f"agent_browser timed out after {_AGENT_BROWSER_TIMEOUT_SECONDS} seconds"
        ) from exc
    except OSError as exc:
        raise SourceFailedError(f"agent_browser failed to launch: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise SourceFailedError(f"agent_browser exited with code {proc.returncode}: {detail}")
    return proc.stdout


def _build_base_cmd(
    *,
    profile: str | None = None,
    session_name: str | None = None,
    state_path: str | None = None,
) -> list[str]:
    base_cmd = ["agent-browser"]
    if profile:
        base_cmd.extend(["--profile", profile])
    if session_name:
        base_cmd.extend(["--session-name", session_name])
    if state_path:
        base_cmd.extend(["--state", state_path])
    return base_cmd


def _extract_post_from_url(*, base_cmd: list[str], page_url: str, post_url: str) -> dict:
    _run_agent_browser_command(base_cmd=base_cmd, step_args=["open", post_url])
    _run_agent_browser_command(base_cmd=base_cmd, step_args=["wait", "--load", "networkidle"])
    extraction_raw = _run_agent_browser_command(
        base_cmd=base_cmd,
        step_args=["eval", _EXTRACTION_JS],
        json_output=True,
    )
    payload = _parse_agent_browser_json(
        extraction_raw,
        invalid_message="agent_browser returned invalid extraction JSON",
    )
    if isinstance(payload, str):
        raise SourceFailedError("agent_browser extraction returned string instead of object")
    return _normalize_agent_browser_extract(
        payload,
        page_url=page_url,
        latest_post_url=post_url,
    )


def run_agent_browser_extract(
    *,
    page_url: str,
    profile: str | None = None,
    session_name: str | None = None,
    state_path: str | None = None,
) -> dict:
    base_cmd = _build_base_cmd(
        profile=profile,
        session_name=session_name,
        state_path=state_path,
    )

    _run_agent_browser_command(base_cmd=base_cmd, step_args=["open", page_url])
    _run_agent_browser_command(base_cmd=base_cmd, step_args=["wait", "--load", "networkidle"])
    latest_post_raw = _run_agent_browser_command(
        base_cmd=base_cmd,
        step_args=["eval", _LATEST_POST_URL_JS],
        json_output=True,
    )
    latest_post_url = _parse_agent_browser_json(
        latest_post_raw,
        invalid_message="agent_browser returned invalid latest-post JSON",
    )
    if not isinstance(latest_post_url, str) or not latest_post_url:
        raise SourceFailedError("agent_browser could not find latest post URL")

    return _extract_post_from_url(
        base_cmd=base_cmd,
        page_url=page_url,
        post_url=latest_post_url,
    )


def run_agent_browser_extract_posts(
    *,
    page_url: str,
    profile: str | None = None,
    session_name: str | None = None,
    state_path: str | None = None,
) -> dict:
    base_cmd = _build_base_cmd(
        profile=profile,
        session_name=session_name,
        state_path=state_path,
    )

    _run_agent_browser_command(base_cmd=base_cmd, step_args=["open", page_url])
    _run_agent_browser_command(base_cmd=base_cmd, step_args=["wait", "--load", "networkidle"])
    scan_raw = _run_agent_browser_command(
        base_cmd=base_cmd,
        step_args=["eval", _RECENT_POST_URLS_JS],
        json_output=True,
    )
    scan_payload = _parse_agent_browser_json(
        scan_raw,
        invalid_message="agent_browser returned invalid recent-post JSON",
    )
    if isinstance(scan_payload, str):
        raise SourceFailedError("agent_browser recent-post scan returned string instead of object")

    post_urls = scan_payload.get("post_urls")
    if not isinstance(post_urls, list):
        raise SourceFailedError("agent_browser recent-post scan missing post_urls")

    posts = [
        _extract_post_from_url(base_cmd=base_cmd, page_url=page_url, post_url=str(post_url))
        for post_url in post_urls
        if str(post_url).strip()
    ]

    return {
        "source_page_url": str(scan_payload.get("source_page_url") or page_url).strip() or page_url,
        "fetched_at": str(scan_payload.get("fetched_at") or "").strip(),
        "search_status": str(scan_payload.get("search_status") or "").strip() or "selection_ready",
        "end_of_feed_reached": (
            scan_payload.get("end_of_feed_reached")
            if isinstance(scan_payload.get("end_of_feed_reached"), bool)
            else False
        ),
        "scan_stopped_reason": (
            str(scan_payload.get("scan_stopped_reason") or "").strip()
            or "selection_limit_reached"
        ),
        "posts_scanned": int(scan_payload.get("posts_scanned") or len(posts)),
        "posts": posts,
    }
