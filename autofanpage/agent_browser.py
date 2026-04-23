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
_EXTRACTION_JS = """
(() => {
  const text = (value) => typeof value === "string" ? value.trim() : "";
  const content = (name) => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return text(el?.content || "");
  };
  const canonical = text(document.querySelector('link[rel="canonical"]')?.href || "");
  const sourcePostUrl = canonical || content("og:url") || window.location.href;
  const publishedAt = content("article:published_time") || text(document.querySelector("time")?.getAttribute("datetime") || "");
  const author = content("author") || text(document.querySelector('meta[property="article:author"]')?.content || "");
  const bodyText = text(document.body?.innerText || "").replace(/\\s+/g, " ").trim();
  const mediaUrls = Array.from(document.querySelectorAll("img[src], video[src]"))
    .map((el) => text(el.currentSrc || el.src || ""))
    .filter(Boolean);
  return {
    source_page_url: window.location.origin + window.location.pathname,
    source_post_url: sourcePostUrl,
    published_at: publishedAt,
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
    return payload


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


def run_agent_browser_extract(
    *,
    page_url: str,
    profile: str | None = None,
    session_name: str | None = None,
    state_path: str | None = None,
) -> dict:
    base_cmd = ["agent-browser"]
    if profile:
        base_cmd.extend(["--profile", profile])
    if session_name:
        base_cmd.extend(["--session-name", session_name])
    if state_path:
        base_cmd.extend(["--state", state_path])

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

    _run_agent_browser_command(base_cmd=base_cmd, step_args=["open", latest_post_url])
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
    return payload
