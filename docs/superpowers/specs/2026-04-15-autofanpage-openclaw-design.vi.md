# AutoFanpage trên OpenClaw — Thiết kế kỹ thuật (Bản tiếng Việt)

**Ngày:** 15/04/2026
**Nền tảng mục tiêu:** [OpenClaw](https://openclaw.ai/) (trợ lý AI self-hosted chạy trên máy cá nhân)
**Workflow nguồn:** `workflow.md` (AutoFanpage AI content automation pipeline)

> ⚠️ Đây là bản dịch để review dễ hơn. Bản tiếng Anh `2026-04-15-autofanpage-openclaw-design.md` là bản chính; nếu có khác biệt thì theo bản tiếng Anh.

---

## 1. Mục đích

Chuyển pipeline 6 phase trong `workflow.md` sang chạy trên nền tảng agent OpenClaw, với các điều chỉnh đã thống nhất trong brainstorm:

- **Multi-page**: mỗi Facebook Page có 1 profile riêng, với topic, ngôn ngữ, token và lịch cron riêng.
- **Ngôn ngữ configurable per-page** (VN, EN, hoặc bất kỳ ngôn ngữ nào model writing hỗ trợ).
- **4 bài/ngày** vào **08:00, 12:00, 16:00, 20:00** (theo timezone của page), thay cho lịch 3 bài cũ.
- 4 loại bài map 1:1 với 4 slot: `news`, `guide`, `opinion`, `case_study`.
- **NotebookLM là bắt buộc** cho Phase 2 — không có fallback. Lỗi NotebookLM = halt + gửi Telegram cho user.
- **Telegram report** dùng channel native của OpenClaw (đã pair với gateway) thay vì bot token riêng.
- **Perplexity** dùng qua HTTP API (cần 2 model call riêng: `sonar-pro` cho news và `sonar` academic cho report, nên map thẳng vào HTTP endpoint tiện hơn).
- **Phase 1 thu thập từ 4 nguồn song song**: YouTube + Perplexity (+Twitter indirect) + Reddit + Hacker News.

**Không thuộc phạm vi spec này:** A/B test tự động, dashboard engagement, image generation, auto-refresh FB access token (user xoay token thủ công khi Telegram báo).

---

## 2. Kiến trúc tổng quan

### 2.1 Vì sao OpenClaw phù hợp

Docs OpenClaw (`docs.openclaw.ai/llms.txt`) xác nhận đầy đủ primitive mình cần:

| Primitive | Docs | Dùng làm gì |
|---|---|---|
| AgentSkills-compatible skill folder | "Skill Creation" | Mỗi phase = 1 skill |
| Cron jobs | `automation/cron-jobs.md` | `openclaw cron add --cron "0 6 * * *" --session isolated --message "/daily_content_pipeline page=<name>"` |
| Sub-agent / Agent Send | "Inter-Skill Communication" | Orchestrator gọi từng phase như sub-agent |
| MCP support | CLI `openclaw mcp` | Đăng ký `notebooklm-mcp` cho Phase 2 |
| Telegram channel (native) | "Chat Integrations" | Reporter gửi thẳng vào chat đã pair |
| Secrets management | `gateway/secrets.md` | FB/YouTube/Perplexity/Reddit keys lưu dạng `secret:<name>` |
| Isolated session | Cron flag `--session isolated` | Mỗi run hàng ngày có session sạch |

### 2.2 Layout file

**Skill package (code mình ship):**

```
~/.openclaw/skills/autofanpage/
├── daily-content-pipeline/        # Orchestrator (skill top-level, user gọi trực tiếp)
│   └── SKILL.md
├── youtube-researcher/
├── perplexity-researcher/
├── reddit-researcher/
├── hackernews-researcher/
├── notebooklm-analyzer/
├── review-agent/
├── writing-agent/
├── facebook-publisher/
├── telegram-reporter/
└── autofanpage-health-check/      # Cron thứ 2: check run daily đã chạy chưa
    └── SKILL.md
```

**Runtime data (không check vào skill package):**

```
~/.openclaw/autofanpage/
├── pages/                          # Mỗi page 1 profile JSON
│   ├── page_vn_ai.json
│   └── page_en_biz.json
├── runs/                           # Artifact mỗi page mỗi ngày
│   └── <page>/<YYYY-MM-DD>/
│       ├── youtube_results.json       # YouTube
│       ├── perplexity_results.json    # Perplexity (news + report + tweet)
│       ├── reddit_results.json         # Reddit
│       ├── hackernews_results.json     # Hacker News
│       ├── merged_sources.json         # URL đã dedupe, feed cho NotebookLM
│       ├── insights.json
│       ├── reviewed_insights.json
│       ├── posts.json
│       ├── publish_results.json
│       └── run.log
└── state/
    └── <page>/last_success.json    # Đánh dấu idempotency: ngày chạy thành công gần nhất
```

Run directory cũ > 30 ngày sẽ bị `autofanpage-health-check` dọn tự động mỗi ngày.

### 2.3 Control plane

- **Cron:** 1 cron/page, tạo qua `openclaw cron add`. Convention tên: `af-<page_name>`.
- **Cú pháp ví dụ:** `openclaw cron add --name "af-page_vn_ai" --cron "0 6 * * *" --session isolated --tz Asia/Ho_Chi_Minh --message "/daily_content_pipeline page=page_vn_ai"`.
- **Cron health-check:** 1 cron duy nhất `af-health` lúc 09:00 Asia/Ho_Chi_Minh, check mọi page có `last_success.json` hôm nay không, page nào thiếu → Telegram alert.
- **Secrets:** lưu qua `openclaw secrets set`; trong profile/skill chỉ reference dạng `secret:<name>`. Không hardcode token trong file JSON hay prompt.

### 2.4 Nguyên tắc data flow

Mỗi sub-skill **đọc JSON input, ghi JSON output** trong `run_dir` mà orchestrator truyền qua. Orchestrator không giữ payload lớn trong prompt — chỉ pass đường dẫn và validate schema sau mỗi phase. Điều này cho phép:

- Test độc lập từng skill chỉ với 1 fixture run directory.
- Resume khi fail giữa chừng: nếu Phase 4 lỗi, output Phase 1–3 vẫn còn trên disk; re-run sẽ skip qua (check presence).
- Audit trail 30 ngày để debug chất lượng content.

---

## 3. Components (11 skills)

Mọi skill đều nhận 2 tham số chuẩn: `run_dir` (đường dẫn) và `page_profile` (đường dẫn tới file profile JSON). Tham số bổ sung liệt kê ở từng skill.

### 3.1 `daily-content-pipeline` (orchestrator)

- **User gọi trực tiếp:** có. Slash command: `/daily_content_pipeline page=<name>` (optional `dry_run=true`).
- **Flow:**
  1. Load `pages/<name>.json`; validate các key bắt buộc (`page_id`, `access_token_ref`, `topic`, `language`, `post_times`, `timezone`). Invalid → halt + Telegram error.
  2. Tính `today = now(timezone).date()`; `run_dir = runs/<name>/<today>/`. Tạo nếu chưa có.
  3. Check idempotency: nếu `state/<name>/last_success.json.date == today` → abort + Telegram info "đã chạy rồi".
  4. Kick Phase 1 song song 4 nhánh (tôn trọng toggle `sources` trong profile):
     - `youtube-researcher` → `youtube_results.json`
     - `perplexity-researcher` → `perplexity_results.json`
     - `reddit-researcher` → `reddit_results.json`
     - `hackernews-researcher` → `hackernews_results.json`
     Đợi hết 4 nhánh. Source disabled ghi artifact dạng object rỗng ngay, không spawn sub-agent. Nếu **cả 4** nguồn trả về 0 item sau retry → halt + Telegram error "no sources found".
  5. **Merge step:** orchestrator đọc cả 4 file, dedupe theo URL, ghi `merged_sources.json` — list gộp `{url, title, platform, score_or_views, created_at}` cap theo `max_sources_per_platform` (default 12 → tối đa 48 URL, vẫn dưới giới hạn 50 source của NotebookLM).
  6. Phase 2: `notebooklm-analyzer` đọc `merged_sources.json`. Fail (sau 1 retry) → halt + Telegram error (NotebookLM bắt buộc).
  7. Phase 3a: `review-agent`. Nếu `approved.length < page_profile.min_posts_required` (default 2) → halt Writing + Publisher, Telegram partial.
  8. Phase 3b: `writing-agent`. Tạo 0–4 bài tùy bao nhiêu insight được duyệt map vào từng type.
  9. Phase 4: `facebook-publisher`. Ở chế độ `dry_run`, bỏ qua Graph API, render `run_dir/preview.md` rồi gửi Telegram cho user duyệt tay.
  10. Thành công: ghi `state/<name>/last_success.json`, gọi `telegram-reporter` với `status=success` + summary.
- **Validate schema** sau mỗi phase; sai schema = coi như phase đó fail (xem §5).

### 3.2 `youtube-researcher`

- **Input:** `run_dir`, `topic`, `api_key_ref=secret:youtube_api`, `filters` (từ profile: `youtube_min_views`, `youtube_min_subs`, default 100k và 10k).
- **Logic:** `GET youtube/v3/search` với `q=<topic>`, `order=viewCount`, `type=video`, `publishedAfter=<today - 7d>`, `maxResults=10`. Post-filter theo `viewCount` và `channelSubscriberCount` (phải call thêm `channels.list` — batch theo channel IDs).
- **Output:** `run_dir/youtube_results.json` — object `{source, fetched_at, items}` trong đó mỗi item là `{title, url, video_id, channel, views, published_at}` (có thể kèm `channel_id` / `subscribers` nếu lấy được).

### 3.3 `perplexity-researcher`

- **Input:** `run_dir`, `topic`, `language`, `api_key_ref=secret:perplexity_api`, `sources.twitter_via_perplexity.enabled` (từ profile).
- **Logic:** 3 POST tới `https://api.perplexity.ai/chat/completions`:
  - `sonar-pro` — "Top 5 {topic} news today, return title/url/summary/source for each." → `type: "news"`
  - `sonar` academic — "Recent {topic} reports 2025–2026, return title/url/summary/source/key_stats for 3 reports." → `type: "report"`
  - `sonar-pro` — "Find 5 viral tweets from the past 7 days about {topic} on x.com/twitter.com. Return title/url/summary/source (tweet author) for each. Restrict results to site:x.com OR site:twitter.com." → `type: "tweet"`. Skip nếu `sources.twitter_via_perplexity.enabled == false`.
- **Output:** `run_dir/perplexity_results.json` — object `{source, fetched_at, news, reports, twitter}`; mỗi bucket chứa item `{title, url, summary, source}`.
- **Lý do dùng Perplexity cho tweet:** X API chính thức giá $100+/tháng và rate limit chặt; Perplexity đã index tweet công khai và trả URL, không tốn thêm chi phí (đã có Perplexity key).

### 3.4 `reddit-researcher`

- **Input:** `run_dir`, `sources.reddit` (từ profile: `subreddits`, `min_score`, `time_filter`), `client_id_ref=secret:reddit_client_id`, `client_secret_ref=secret:reddit_client_secret`.
- **Logic:**
  1. Lấy OAuth token qua `POST https://www.reddit.com/api/v1/access_token` với `grant_type=client_credentials` (flow app "script" / "installed").
  2. Với mỗi subreddit trong list profile: `GET https://oauth.reddit.com/r/<sub>/top?t=<time_filter>&limit=25` kèm `User-Agent` tả rõ (Reddit yêu cầu, ví dụ `openclaw-autofanpage/1.0`).
  3. Filter post theo `score >= min_score`; bỏ NSFW; giữ top N/sub (default top 5).
- **Output:** `run_dir/reddit_results.json` — object `{source, fetched_at, items}` trong đó mỗi item là `{title, url, permalink, subreddit, score, num_comments, author, created_at, is_self}`. `url` là external link nếu là link post, còn self post thì là `permalink`.
- **Skip mode:** nếu `sources.reddit.enabled == false` → ghi object bọc với `items: []` và return ngay (không OAuth).

### 3.5 `hackernews-researcher`

- **Input:** `run_dir`, `topic`, `sources.hackernews` (từ profile: `min_points`).
- **Logic:**
  1. `GET https://hacker-news.firebaseio.com/v0/topstories.json` → lấy 200 story ID đầu.
  2. Batch fetch chi tiết (parallel ≤20 concurrent) qua `/v0/item/<id>.json`.
  3. Filter: `score >= min_points` AND tạo trong 7 ngày gần nhất AND title/URL match từ khoá topic (substring match case-insensitive, không dùng model để giữ skill này rẻ).
  4. Giữ top 10 theo score.
- **Output:** `run_dir/hackernews_results.json` — object `{source, fetched_at, items}` trong đó mỗi item là `{title, url, points, by, descendants, created_at, hn_url}`. `hn_url` là `https://news.ycombinator.com/item?id=<id>`; `url` là link ngoài (bằng `hn_url` nếu là Ask-HN).
- **Skip mode:** nếu `sources.hackernews.enabled == false` → ghi object bọc với `items: []` rồi return ngay.
- **Không cần auth.**

### 3.6 `notebooklm-analyzer` (qua MCP) — **bắt buộc**

- **Input:** `run_dir`, `language`.
- **Depends on:** `notebooklm-mcp-cli` ([jacob-bd/notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli)) cài qua `pip install notebooklm-mcp-cli` (hoặc `uv tool install notebooklm-mcp-cli`). Package cung cấp CLI `nlm` và MCP server binary tên `notebooklm-mcp`. Đăng ký với OpenClaw qua `openclaw mcp add notebooklm-mcp` (cú pháp chính xác confirm khi cài lần đầu).
  - **Tình trạng official:** NotebookLM KHÔNG có MCP server chính thức của Google (khác với Stitch / Developer Knowledge / Firestore dùng `gcloud beta services mcp enable ...`). `notebooklm-mcp-cli` là implementation community active nhất; dùng internal API không công khai của NotebookLM → có thể bị break khi Google thay đổi.
  - **Auth (cookie-based):** user chạy `nlm login` 1 lần — browser mở, đăng nhập Google, cookies được extract và cache local. Cookie thường sống 2–4 tuần; hết hạn → mọi run `notebooklm-analyzer` fail đến khi user chạy lại `nlm login`. Đây là failure mode route qua Telegram (xem §5).
  - **Rate limit:** ~50 query NotebookLM/ngày tier free. 1 page tốn 4 query/ngày (Q1–Q4) → 1 Google account support ~12 page thoải mái. Vượt con số này → cần thêm Google account (với `nlm login --profile <name>` riêng) mỗi batch ~12 page.
- **Logic:**
  1. Đọc `run_dir/merged_sources.json` (do orchestrator tạo sau Phase 1).
  2. Gọi MCP tool `notebook_create` với `title="AI Research {today}"` → capture `notebook_id`.
  3. Với mỗi URL trong `merged_sources.json`, gọi `source_add` với URL đó (≤50, đúng giới hạn NotebookLM).
  4. Gọi `notebook_query` 4 lần (Q1 overview / Q2 pain_points / Q3 insights 5–10 / Q4 gap_topics), phrase theo `language` của profile.
- **Output:** `run_dir/insights.json` — `{overview, pain_points[], insights[], gap_topics[]}`.
- **Failure mode route qua Telegram:**
  - Cookie hết hạn (lỗi auth từ bất kỳ tool call nào) → halt + Telegram error với text chính xác "Chạy `nlm login` để refresh NotebookLM cookies."
  - Rate limit (HTTP 429 hoặc tương đương) → halt + Telegram error; cron ngày mai khả năng cao success.
  - Failure khác → 1 retry (30s backoff), rồi halt + Telegram error kèm MCP log tail.

### 3.7 `review-agent`

- **Input:** `run_dir/insights.json`, `language`.
- **Logic:** chấm mỗi insight 4 tiêu chí (Relevance / Novelty / Viral / Actionable, mỗi cái 1–5). Giữ insight `total ≥ 14`. Mỗi insight đã duyệt gắn `suggested_post_type ∈ {news, guide, opinion, case_study}` (heuristic mô tả trong `review-agent/SKILL.md`) + `hook_angle` gợi ý.
- **Output:** `run_dir/reviewed_insights.json`:
  ```json
  {
    "approved": [
      { "insight": "...", "scores": {"relevance":5,"novelty":4,"viral":4,"actionable":3},
        "total": 16, "suggested_post_type": "news", "hook_angle": "..." }
    ],
    "rejected": [ {"insight": "...", "reason": "..."} ]
  }
  ```
- **Edge:** nếu `approved.length == 0` vẫn ghi file (approved rỗng); orchestrator xử lý case partial.

### 3.8 `writing-agent`

- **Input:** `run_dir/reviewed_insights.json`, `language`, `post_times` (từ profile).
- **Ràng buộc cứng:** chỉ dùng sự kiện/số liệu từ `reviewed_insights.json`. Không bịa thống kê, không kéo context ngoài. Slot nào thiếu insight phù hợp → emit `content: null` cho slot đó, KHÔNG bịa.
- **Slot → type mapping (theo index, không theo giờ):**

  Array `post_times` trong profile định nghĩa giờ đồng hồ cho từng slot. Mapping slot→type là **theo vị trí index**: slot 0 luôn là `news`, slot 1 `guide`, slot 2 `opinion`, slot 3 `case_study`, bất kể clock time. Page đổi giờ đăng sớm/muộn mà không làm loạn type rotation.

  | Slot index | Giờ mặc định | Type | Template |
  |---|---|---|---|
  | 0 | 08:00 | `news` | Hook = sự kiện mới; Body 150–250 từ tóm tắt + ý nghĩa với target business; CTA = "Bạn nghĩ điều này ảnh hưởng thế nào đến công việc của bạn?"; 3–5 hashtag |
  | 1 | 12:00 | `guide` | Hook = kết quả cụ thể/con số; Body = 3–5 bước thực chiến; CTA = "Bạn đã thử bước nào rồi?"; 3–5 hashtag |
  | 2 | 16:00 | `opinion` | Hook = đảo ngược niềm tin phổ biến; Body = lập luận 2 phía; CTA = "Bạn ở phía nào? Comment xuống dưới!"; 3–5 hashtag |
  | 3 | 20:00 | `case_study` | Hook = trước/sau của doanh nghiệp thật áp dụng AI; Body = bối cảnh → giải pháp AI → kết quả đo được; CTA = "Doanh nghiệp bạn đã thử chưa?"; 3–5 hashtag |

  CTA bằng tiếng Việt là default; skill tự dịch sang `language` của profile.

- **First comment** mỗi bài (tránh FB giảm reach khi có link trong body chính):

  | Type | Nội dung first comment |
  |---|---|
  | news | Link nguồn gốc + danh sách resource liên quan |
  | guide | Mở rộng đầy đủ 3–5 bước step-by-step |
  | opinion | 1 câu hỏi phụ để kéo thêm reply |
  | case_study | Link case + phân tích chi tiết kết quả đo được |

- **Output:** `run_dir/posts.json`:
  ```json
  {
    "posts": [
      {"time": "08:00", "type": "news",       "content": "...", "first_comment": "..."},
      {"time": "12:00", "type": "guide",      "content": "...", "first_comment": "..."},
      {"time": "16:00", "type": "opinion",    "content": "...", "first_comment": "..."},
      {"time": "20:00", "type": "case_study", "content": "...", "first_comment": "..."}
    ]
  }
  ```

### 3.9 `facebook-publisher`

- **Input:** `run_dir/posts.json`, `page_profile`.
- **Logic mỗi post** (bỏ qua post có `content: null`):
  1. `POST /v19.0/{page_id}/feed` với `message = content + "\n\n" + hashtags`, `scheduled_publish_time = <unix ts theo timezone profile, ngày hôm nay, post.time>`, `published=false`. Facebook yêu cầu `scheduled_publish_time` cách ít nhất 10 phút so với thời điểm gọi và tối đa 6 tháng — nếu giờ hiện tại đã gần/quá giờ slot (<10 phút), dời slot đó lên +15 phút.
  2. Lưu `post_id` trả về.
  3. `POST /v19.0/{post_id}/comments` với `message = first_comment`. Lưu `comment_id`.
  4. Append `{time, type, post_id, comment_id, status}` vào `run_dir/publish_results.json` NGAY (partial fail vẫn có record sạch).
- **Idempotency:** trước khi post, đọc `publish_results.json` hiện có; skip slot nào đã có `status==200` (tránh duplicate khi resume).
- **Dry-run:** orchestrator truyền `dry_run=true` → bỏ qua Graph API hoàn toàn, render `run_dir/preview.md` với đủ 4 bài, return về orchestrator để gửi Telegram preview.
- **Output:** `run_dir/publish_results.json`:
  ```json
  {
    "page": "page_vn_ai",
    "date": "2026-04-15",
    "posts": [
      {"time": "08:00", "type": "news", "post_id": "123_456", "comment_id": "123_789", "status": 200}
    ]
  }
  ```

### 3.10 `telegram-reporter`

- **Input:** `status` ∈ `{success, error, partial, info}`, `page`, `details` (dict).
- **Transport:** native OpenClaw Telegram channel. Message gửi thẳng vào chat user đã pair — không cần bot token trong skill.
- **Template:**
  - `success`: ✅ + page + date + N bài đã schedule + thời gian chạy
  - `error`: 🚨 + page + phase fail + root cause 1 dòng + 20 dòng cuối `run.log`
  - `partial`: ⚠️ + page + giải thích (ví dụ "Review duyệt 2/4, đăng 2/4 bài") + list post_id đã schedule
  - `info`: ℹ️ + page + message (cho "đã chạy rồi" và dry-run preview)

### 3.11 `autofanpage-health-check`

- **Trigger:** cron riêng (`af-health`, hàng ngày 09:00 Asia/Ho_Chi_Minh).
- **Logic:** loop mọi `pages/*.json`; với mỗi page, check `state/<page>/last_success.json.date`. Thiếu hoặc ≠ hôm nay → Telegram alert cho page đó. Đồng thời dọn `runs/<page>/<date>/` cũ > 30 ngày.

---

## 4. Data Contract

### 4.1 Profile per-page — `pages/<name>.json`

```json
{
  "name": "page_vn_ai",
  "page_id": "123456789",
  "access_token_ref": "secret:fb_page_vn_ai",
  "topic": "AI automation business",
  "language": "vi",
  "post_times": ["08:00", "12:00", "16:00", "20:00"],
  "timezone": "Asia/Ho_Chi_Minh",
  "filters": { "youtube_min_views": 100000, "youtube_min_subs": 10000 },
  "min_posts_required": 2,
  "max_sources_per_platform": 12,
  "sources": {
    "youtube":                  { "enabled": true },
    "perplexity":               { "enabled": true },
    "twitter_via_perplexity":   { "enabled": true },
    "reddit": {
      "enabled": true,
      "subreddits": [
        "ChatGPT",
        "ArtificialIntelligence",
        "artificial",
        "singularity",
        "OpenAI",
        "LocalLLaMA",
        "ClaudeAI",
        "MachineLearning"
      ],
      "min_score": 100,
      "time_filter": "week",
      "top_per_sub": 5
    },
    "hackernews": { "enabled": true, "min_points": 50 }
  }
}
```

- `min_posts_required`: ngưỡng tối thiểu số insight được duyệt để tiếp tục Writing+Publisher (default 2).
- `max_sources_per_platform`: mỗi nguồn đóng góp tối đa N URL vào merged list cho NotebookLM (default 12 × 4 nguồn = 48, dưới giới hạn 50 của NotebookLM). Trong mỗi nguồn, item top lấy theo tín hiệu native: YouTube `viewCount`, Reddit `score`, HN `points`, Perplexity theo thứ tự API trả về.
- **Thêm/xoá subreddit:** chỉ cần sửa array `sources.reddit.subreddits` trong file này, không đụng code.
- **Tắt toàn bộ 1 nguồn:** set `sources.<source>.enabled: false`.

### 4.2 File trung gian

- `youtube_results.json` — `{source, fetched_at, items[]}` chứa metadata video YouTube
- `perplexity_results.json` — `{source, fetched_at, news[], reports[], twitter[]}` chứa citations đã parse từ Perplexity
- `reddit_results.json` — `{source, fetched_at, items[]}` chứa post Reddit đã flatten
- `hackernews_results.json` — `{source, fetched_at, items[]}` chứa story Hacker News đã filter
- `insights.json` — NotebookLM output (`overview`, `pain_points`, `insights`, `gap_topics`)
- `reviewed_insights.json` — `approved[]` + `rejected[]` với score + gợi ý type
- `posts.json` — mảng 4 slot `time`, `type`, `content`, `first_comment`

### 4.3 Artifact mới

- `merged_sources.json` — list URL dedupe + cap đã đưa vào NotebookLM. Shape: `{ "urls": [{"url", "title", "platform", "score_or_views", "created_at"}], "counts_per_platform": {"youtube": N, "perplexity": N, "reddit": N, "hackernews": N} }`
- `publish_results.json` — record audit những gì đã lên FB (xem §3.9)
- `state/<page>/last_success.json` — dấu idempotency: `{ "date": "...", "run_dir": "...", "posts_scheduled": N, "completed_at": "..." }`
- `preview.md` (chỉ dry-run) — markdown preview 4 bài

### 4.4 Validation

Mọi file validate theo 1 JSON-schema fragment nhúng trong skill consumer (key bắt buộc, kiểu dữ liệu, enum check cho `type`/`status`). Schema mismatch = phase fail = halt + Telegram error.

---

## 5. Xử lý lỗi

| Loại | Ví dụ nguyên nhân | Hành vi |
|---|---|---|
| Config invalid | `pages/<name>.json` thiếu key, `post_times` sai format | Halt ngay; Telegram error; không tạo run_dir |
| Đã chạy hôm nay | `last_success.json.date == today` | Abort gracefully; Telegram `info` |
| YouTube fail | Hết quota, key bị revoke, network | Retry 2 lần (30s backoff) → ghi `youtube_results.json` dạng object rỗng và CONTINUE; Telegram warning |
| Perplexity fail | API down, rate limit | Retry 2 lần (30s backoff) → ghi `perplexity_results.json` dạng object rỗng và CONTINUE; Telegram warning |
| Reddit fail | OAuth reject, subreddit banned, 429 | Retry 2 lần (30s backoff) → ghi `reddit_results.json` dạng object rỗng và CONTINUE; Telegram warning |
| Hacker News fail | Firebase lỗi tạm | Retry 2 lần (30s backoff) → ghi `hackernews_results.json` dạng object rỗng và CONTINUE; Telegram warning |
| Cả 4 nguồn Phase 1 rỗng | Mọi source đều fail hoặc trả 0 item | Halt trước NotebookLM; Telegram error "no sources available, cannot analyze" |
| NotebookLM cookie hết hạn | Cookie `nlm login` cũ > 2–4 tuần | Halt + Telegram error với hướng dẫn "Chạy `nlm login` để refresh NotebookLM cookies." (Phase bắt buộc; không auto-refresh.) |
| NotebookLM rate limit | Chạm limit ~50 query/ngày tier free | Halt + Telegram error; cron ngày mai khả năng cao tự chạy lại OK |
| NotebookLM fail khác | MCP server down, tạo notebook lỗi, Q-timeout | Retry 1 lần (30s backoff) → halt + Telegram error kèm MCP log tail. (Phase bắt buộc.) |
| Review duyệt 0 | Không insight nào ≥14 điểm | Ghi file approved rỗng; orchestrator skip Writing+Publisher; Telegram partial kèm top 3 rejected reason |
| Review duyệt 1 | Dưới `min_posts_required` (default 2) | Giống trên — halt Writing+Publisher; Telegram partial |
| Writing under-fill slot | Chỉ 2/4 slot map được insight | Writing emit `content: null` cho slot thiếu; Publisher chỉ đăng slot có content; Telegram partial "đã đăng 2/4" |
| FB scheduled_time < 10 phút | Cron trễ, 08:00 đã qua | Dời slot đó lên +15 phút; Telegram warning |
| FB access token hết hạn | Token expire | Halt Publisher; `posts.json` giữ nguyên; Telegram **error** kèm hướng dẫn refresh tay |
| FB rate limit | OAuthException, đăng quá nhanh | Backoff exponential 1m / 5m / 15m; 3 lần; sau đó halt + Telegram error |
| Partial publish | 1 post OK, post sau fail | `publish_results.json` đã có record cho post succeed; Telegram partial liệt kê `post_id` thành công |
| Exception bất ngờ | Bug code, issue OpenClaw | Catch-all ở orchestrator; dump stack vào `run.log`; Telegram error kèm 20 dòng log cuối |

**Retry policy chung:** default 3 lần với backoff exponential (2s / 10s / 60s), trừ khi bảng trên có override. Mọi retry + outcome log vào `run_dir/run.log`.

**Secret rotation:** pipeline không tự refresh token. Khi lỗi kiểu expired, user rotate thủ công qua `openclaw secrets set ...` và trigger re-run.

---

## 6. Testing Strategy

### 6.1 Unit test (từng skill độc lập)

- Fixture check-in tại `tests/fixtures/sample_run/` gồm file JSON input mẫu sát thực.
- Invoke skill qua `openclaw skills run <skill> --args '{"run_dir": "tests/fixtures/sample_run", "page_profile": "tests/fixtures/page_test.json"}'`.
- Assert: file output tồn tại, schema valid, business rule đúng (ví dụ `review-agent` chỉ giữ `total≥14`; `youtube-researcher` filter đúng threshold).
- Stub external HTTP qua env override (`YOUTUBE_API_BASE`, `PERPLEXITY_API_BASE`) trỏ vào mock server local hoặc fixture replay.

### 6.2 Integration test (cặp skill)

- `youtube-researcher` → `notebooklm-analyzer`: 1 run nhỏ thật với notebook dùng 1 lần, verify MCP wiring.
- `writing-agent` → `facebook-publisher`: dùng **FB Test Page** (không phải page production), verify full flow schedule + first-comment.
- Phát hiện drift data contract: mỗi cặp test producer output parse được dưới schema consumer.

### 6.3 End-to-end dry-run

- `dry_run=true` trên orchestrator bỏ qua Graph API hoàn toàn; tạo `run_dir/preview.md`; gửi preview qua Telegram cho user duyệt.
- Bắt buộc chạy trước khi enable cron cho page mới.

### 6.4 Smoke test checklist (trước khi cài cron)

1. `openclaw skills run daily-content-pipeline --args '{"page":"page_test","dry_run":true}'`
2. Verify 6 file JSON trung gian + `preview.md` ghi đúng.
3. Verify Telegram preview nhận được.
4. Tắt dry-run; chạy tay 1 lần; verify FB Test Page có 4 bài schedule + 4 first comment.
5. Enable cron qua `openclaw cron add …`.

### 6.5 Monitoring runtime

- `run.log` giữ 30 ngày/run (pruning do `autofanpage-health-check` xử lý).
- Hàng tuần (manual): review `publish_results.json` mọi page + xu hướng engagement FB Page Insights.
- Hàng ngày (auto): cron `af-health` 09:00 alert Telegram cho page nào thiếu `last_success.json` hôm nay.

### 6.6 Không scope (YAGNI)

Không CI pipeline, không test framework ngoài `openclaw skills run`, không dashboard, không A/B test content. Cân nhắc lại nếu 1 loại lỗi tái diễn đáng đầu tư.

---

## 7. Checklist triển khai

**Setup 1 lần:**

- [ ] OpenClaw gateway chạy; Telegram channel đã pair; user verify OK.
- [ ] `openclaw secrets set youtube_api <key>`
- [ ] `openclaw secrets set perplexity_api <key>`
- [ ] Tạo Reddit OAuth app tại `https://www.reddit.com/prefs/apps` (type: "script" hoặc "installed"); rồi `openclaw secrets set reddit_client_id <id>` và `openclaw secrets set reddit_client_secret <secret>`.
- [ ] Per-page: `openclaw secrets set fb_<page_name> <token>` (quyền `pages_manage_posts` + `pages_read_engagement`)
- [ ] `pip install notebooklm-mcp-cli` (hoặc `uv tool install notebooklm-mcp-cli`)
- [ ] `nlm login` — mở browser, đăng nhập Google account sở hữu NotebookLM Pro/free. Cookie cache local.
- [ ] `openclaw mcp add notebooklm-mcp ...` — đăng ký MCP server binary với OpenClaw. (Xác nhận cú pháp `openclaw mcp add` chính xác khi cài.)
- [ ] Verify MCP tool resolve: chạy thử `nlm notebook list` trước khi để cron pipeline tin tưởng.
- [ ] Copy 11 skill folder vào `~/.openclaw/skills/autofanpage/`.
- [ ] Viết profile JSON cho mỗi page dưới `~/.openclaw/autofanpage/pages/`.
- [ ] Smoke test từng page với `dry_run=true` (xem §6.4).
- [ ] Tạo 1 cron/page (`openclaw cron add --name "af-<page>" --cron "0 6 * * *" --session isolated --tz <tz> --message "/daily_content_pipeline page=<name>"`).
- [ ] Tạo cron health-check (`openclaw cron add --name "af-health" --cron "0 9 * * *" --message "/autofanpage_health_check"`).

**Vận hành hàng tuần:**

- [ ] Verify Telegram success message đã về cho mọi page.
- [ ] Spot-check engagement FB Page Insights.
- [ ] Check FB access token không expire trong tuần tới.
- [ ] Check YouTube API quota còn dư.
- [ ] Chạy lại `nlm login` nếu lần login gần nhất > 2 tuần (cookie hết hạn 2–4 tuần; refresh chủ động trước khi nó làm fail cron).
- [ ] Đổi topic trong profile nếu content bắt đầu lặp.

---

## 8. Câu hỏi mở (giải quyết khi implement)

1. **Cú pháp sub-agent invocation chính xác của OpenClaw.** Docs liệt kê "Agent Send" và "Sub-Agents" làm capability nhưng chưa có example cụ thể. Task implementation đầu tiên sẽ verify trên 1 orchestrator hello-world trước khi port pipeline thật.
2. **Secret injection vào sub-agent.** Giả định là secret reference resolve transparent trong session của sub-agent; confirm khi smoke test đầu.
3. **Cú pháp `openclaw mcp add` chính xác cho `notebooklm-mcp-cli`.** Tên tool (`notebook_create`, `source_add`, `notebook_query`) đã confirm từ README package. Cú pháp đăng ký OpenClaw chính xác sẽ pin xuống khi cài lần đầu.
4. **Race condition schedule FB.** Nếu cron trễ và slot 08:00 đã qua, hành vi hiện tại là dời +15 phút. Có thể đổi thành đẩy sang ngày hôm sau — quyết định để lại khi quan sát thực tế mức độ trễ.
