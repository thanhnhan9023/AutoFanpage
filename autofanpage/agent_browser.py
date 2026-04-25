from __future__ import annotations

import json
import subprocess

from autofanpage.errors import SourceFailedError

_AGENT_BROWSER_TIMEOUT_SECONDS = 60
_AGENT_BROWSER_SELECTION_POST_LIMIT = 12
_AGENT_BROWSER_MAX_SCAN_PASSES = 12
_AGENT_BROWSER_MAX_STALLED_PASSES = 2
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
  const seen = new Set();
  const postUrls = [];
  let candidateCount = 0;
  const feedRoots = Array.from(document.querySelectorAll('div[role="feed"], div[role="main"]'));
  const links = feedRoots.length
    ? feedRoots.flatMap((root) => Array.from(root.querySelectorAll('a[href]')))
    : Array.from(document.querySelectorAll('a[href]'));
  for (const link of links) {
    if (!link.closest('div[role="article"]')) continue;
    const url = normalize(link.getAttribute("href") || "");
    if (!url || !isPostUrl(url)) continue;
    if (!url.startsWith("https://www.facebook.com/") && !url.startsWith("https://facebook.com/")) {
      continue;
    }
    candidateCount += 1;
    if (seen.has(url)) continue;
    seen.add(url);
    postUrls.push(url);
  }

  const scrollingElement = document.scrollingElement || document.documentElement;
  const scrollY = window.scrollY || scrollingElement.scrollTop || 0;
  const viewportHeight = window.innerHeight || scrollingElement.clientHeight || 0;
  const scrollHeight = Math.max(
    scrollingElement.scrollHeight || 0,
    document.body?.scrollHeight || 0,
  );
  const endOfFeedReached = scrollHeight > 0
    && scrollY + viewportHeight >= scrollHeight - 4;

  return {
    source_page_url: window.location.origin + window.location.pathname,
    fetched_at: new Date().toISOString(),
    end_of_feed_reached: endOfFeedReached,
    posts_scanned: candidateCount,
    post_urls: postUrls,
    scroll_y: scrollY,
    viewport_height: viewportHeight,
    scroll_height: scrollHeight,
  };
})()
""".strip()
_SCROLL_FEED_JS = """
(() => {
  const scrollingElement = document.scrollingElement || document.documentElement;
  const viewportHeight = window.innerHeight || scrollingElement.clientHeight || 0;
  const scrollHeight = Math.max(
    scrollingElement.scrollHeight || 0,
    document.body?.scrollHeight || 0,
  );
  const nextY = Math.max(0, scrollHeight - viewportHeight);
  window.scrollTo(0, nextY);
  return {
    scroll_y: window.scrollY || scrollingElement.scrollTop || nextY,
    viewport_height: viewportHeight,
    scroll_height: Math.max(
      scrollingElement.scrollHeight || 0,
      document.body?.scrollHeight || 0,
    ),
  };
})()
""".strip()
_EXTRACTION_JS = """
(() => {
  const text = (value) => typeof value === "string" ? value.trim() : "";
  const normalize = (href) => {
    if (typeof href !== "string" || !href.trim()) return "";
    try {
      return new URL(href, window.location.href).toString();
    } catch (_err) {
      return "";
    }
  };
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
  const canonical = text(document.querySelector('link[rel="canonical"]')?.href || "");
  const sourcePostUrl = window.location.origin + window.location.pathname || canonical || content("og:url");
  const currentPostHref = (node) => {
    const href = normalize(node?.getAttribute?.("href") || "");
    return Boolean(href) && (
      href === sourcePostUrl ||
      href.replace(/#.*$/, "") === sourcePostUrl ||
      sourcePostUrl.replace(/#.*$/, "") === href
    );
  };
  const headerNodes = (() => {
    const selectors = [
      "time[datetime]",
      "a[aria-label][href]",
      "a[href][role='link']",
      "span[aria-label]",
    ];
    const article = document.querySelector("div[role='article']");
    const roots = [article, document.querySelector("main"), document.body].filter(Boolean);
    const nodes = [];
    for (const root of roots) {
      for (const selector of selectors) {
        for (const node of root.querySelectorAll(selector)) {
          if (selector !== "time[datetime]" && node.tagName === "A" && !currentPostHref(node)) {
            continue;
          }
          nodes.push(node);
        }
      }
      if (nodes.length) return nodes;
    }
    return nodes;
  })();
  const headerRelativePublishedAt = (() => {
    for (const node of headerNodes) {
      const candidate = matchRelativeTime(
        node.getAttribute?.("aria-label") || node.textContent || ""
      );
      if (candidate) return candidate;
    }
    return "";
  })();
  const relativePublishedAt = (() => {
    const nodes = Array.from(document.querySelectorAll("time[datetime], a[aria-label][href]"));
    for (const node of nodes) {
      const candidate = matchRelativeTime(
        node.getAttribute?.("aria-label") || node.textContent || ""
      );
      if (candidate) return candidate;
    }
    return "";
  })();
  const authorLink = document.querySelector("h1 a, h2 a, h3 a, strong a");
  const headerPublishedAt = text(
    headerNodes.find((node) => node.tagName === "TIME")?.getAttribute("datetime") || ""
  );
  const publishedAt = content("article:published_time")
    || headerPublishedAt
    || text(document.querySelector("time")?.getAttribute("datetime") || "")
    || headerRelativePublishedAt
    || relativePublishedAt;
  const author = content("author") || text(document.querySelector('meta[property="article:author"]')?.content || "") || text(authorLink?.textContent || "");
  const bodyText = text(document.body?.innerText || "").replace(/\\s+/g, " ").trim();
  const mediaUrls = Array.from(document.querySelectorAll("img[src], video[src]"))
    .map((el) => text(el.currentSrc || el.src || ""))
    .filter((url) => Boolean(url) && !url.startsWith("data:"));
  return {
    source_page_url: window.location.origin + window.location.pathname,
    source_post_url: sourcePostUrl,
    published_at: publishedAt,
    header_published_at: headerPublishedAt,
    header_relative_published_at: headerRelativePublishedAt,
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

    published_at = str(normalized.get("header_published_at") or "").strip()
    if not published_at:
        published_at = str(normalized.get("header_relative_published_at") or "").strip()
    if not published_at:
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


def _run_recent_post_scan(*, base_cmd: list[str]) -> dict:
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
    return scan_payload


def _scroll_recent_post_feed(*, base_cmd: list[str]) -> dict:
    scroll_raw = _run_agent_browser_command(
        base_cmd=base_cmd,
        step_args=["eval", _SCROLL_FEED_JS],
        json_output=True,
    )
    scroll_payload = _parse_agent_browser_json(
        scroll_raw,
        invalid_message="agent_browser returned invalid feed-scroll JSON",
    )
    if isinstance(scroll_payload, str):
        raise SourceFailedError("agent_browser feed scroll returned string instead of object")
    _run_agent_browser_command(base_cmd=base_cmd, step_args=["wait", "--load", "networkidle"])
    return scroll_payload


def _dedupe_extracted_posts(posts: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for post in posts:
        source_post_id = str(post.get("source_post_id") or "").strip()
        source_post_url = str(post.get("source_post_url") or "").strip()
        dedupe_key = (source_post_id, source_post_url)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped.append(post)

    return deduped


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
    collected_post_urls: list[str] = []
    seen_post_urls: set[str] = set()
    scan_payload: dict = {
        "source_page_url": page_url,
        "fetched_at": "",
        "end_of_feed_reached": False,
        "posts_scanned": 0,
    }
    previous_snapshot_key: tuple[tuple[str, ...], int, int] | None = None
    stalled_passes = 0
    search_status = "fetch_error"
    scan_stopped_reason = "no_posts_found"
    end_of_feed_reached = False
    posts_scanned = 0

    for _ in range(_AGENT_BROWSER_MAX_SCAN_PASSES):
        scan_payload = _run_recent_post_scan(base_cmd=base_cmd)
        post_urls = scan_payload["post_urls"]
        discovered_new_url = False
        for post_url in post_urls:
            normalized_url = str(post_url).strip()
            if not normalized_url or normalized_url in seen_post_urls:
                continue
            seen_post_urls.add(normalized_url)
            collected_post_urls.append(normalized_url)
            discovered_new_url = True

        raw_posts_scanned = scan_payload.get("posts_scanned")
        if raw_posts_scanned is None:
            posts_scanned = max(posts_scanned, len(collected_post_urls))
        else:
            posts_scanned = max(posts_scanned, int(raw_posts_scanned))

        reached_loaded_dom_bottom = bool(scan_payload.get("end_of_feed_reached"))
        end_of_feed_reached = bool(scan_payload.get("confirmed_end_of_feed_reached"))
        snapshot_key = (
            tuple(collected_post_urls),
            int(scan_payload.get("scroll_y") or 0),
            int(scan_payload.get("scroll_height") or 0),
        )

        if end_of_feed_reached:
            search_status = "full_search_complete"
            scan_stopped_reason = "end_of_feed"
            break

        if len(collected_post_urls) >= _AGENT_BROWSER_SELECTION_POST_LIMIT:
            search_status = "selection_ready"
            scan_stopped_reason = "selection_limit_reached"
            break

        if reached_loaded_dom_bottom:
            if collected_post_urls:
                search_status = "selection_ready"
                scan_stopped_reason = "loaded_dom_exhausted"
            else:
                search_status = "partial_search_scope"
                scan_stopped_reason = "loaded_dom_exhausted"
            break

        if not discovered_new_url and snapshot_key == previous_snapshot_key:
            stalled_passes += 1
            if stalled_passes >= _AGENT_BROWSER_MAX_STALLED_PASSES:
                search_status = "selection_ready" if collected_post_urls else "partial_search_scope"
                scan_stopped_reason = "dom_stall"
                break
        else:
            stalled_passes = 0
            previous_snapshot_key = snapshot_key

        _scroll_recent_post_feed(base_cmd=base_cmd)
    else:
        search_status = "partial_search_scope"
        scan_stopped_reason = "max_scroll_steps"

    posts = _dedupe_extracted_posts([
        _extract_post_from_url(base_cmd=base_cmd, page_url=page_url, post_url=post_url)
        for post_url in collected_post_urls
    ])

    if search_status == "fetch_error" and posts:
        search_status = "partial_search_scope"
        scan_stopped_reason = "dom_stall"

    return {
        "source_page_url": str(scan_payload.get("source_page_url") or page_url).strip() or page_url,
        "fetched_at": str(scan_payload.get("fetched_at") or "").strip(),
        "search_status": search_status,
        "end_of_feed_reached": end_of_feed_reached,
        "scan_stopped_reason": scan_stopped_reason,
        "posts_scanned": posts_scanned,
        "posts": posts,
    }
