# AutoFanpage AI — Content Automation Workflow

> Pipeline tự động hoàn toàn: Thu thập nguồn → Phân tích → Chấm điểm → Viết bài + Comment → Đăng Facebook  
> Thời gian chạy: ~5–6 phút/ngày · Không cần can thiệp tay

---

## Tổng quan

```
CRON TRIGGER (6:00 AM)
        │
        ▼
┌─────────────────────────────────────┐
│  PHASE 1 — Thu thập nguồn (song song)│
│  YouTube API v3  ║  Perplexity Sonar │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  PHASE 2 — Phân tích & Tổng hợp    │
│  NotebookLM MCP                     │
│  Output: insights.json              │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  PHASE 3a — Review Agent (Critic)   │
│  Chấm điểm, lọc insight ≥ 14/20    │
│  Output: reviewed_insights.json     │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  PHASE 3b — Writing Agent (Creator) │
│  Viết bài + first_comment           │
│  Output: posts.json                 │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  PHASE 4 — Facebook Publisher       │
│  Lên lịch POST + Auto Comment       │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  PHASE 5 — Bài đăng theo khung giờ │
│  7:00 AM · 12:00 PM · 7:00 PM      │
└─────────────────────────────────────┘
        │
        ▼
  Telegram Bot báo cáo
```

---

## PHASE 1 — Thu thập nguồn (chạy song song)

### YouTube Data API v3

| Tham số | Giá trị |
|---|---|
| Endpoint | `GET https://www.googleapis.com/youtube/v3/search` |
| `q` | `AI automation business` |
| `order` | `viewCount` |
| `publishedAfter` | 7 ngày trước |
| `type` | `video` |
| Lọc thêm | `viewCount > 100,000` và `channelSubscriberCount > 10,000` |
| `maxResults` | 10 |
| Cost | FREE (10,000 units/ngày) |

**Output:** `research_results.json`
```json
[{ "title": "...", "url": "...", "views": 150000, "channel": "...", "published_at": "..." }]
```

### Perplexity Sonar API

| Query | Model | Output |
|---|---|---|
| Top 5 AI automation business news hôm nay | `sonar-pro` | 5 bài tin tức + URL |
| Recent AI business reports 2025–2026 | `sonar` (academic) | 3 báo cáo + key stats |

**Endpoint:** `POST https://api.perplexity.ai/chat/completions` (OpenAI-compatible)  
**Cost:** ~$1–5 / 1,000 requests

**Output:** `news_results.json`
```json
[{ "title": "...", "url": "...", "summary": "...", "source": "...", "type": "news|report" }]
```

---

## PHASE 2 — Phân tích & Tổng hợp Insight

**Công cụ:** NotebookLM MCP (`pip install notebooklm-mcp`)

**Quy trình:**
1. Tạo notebook mới: `notebooklm_create_notebook(title="AI Research {date}")`
2. Đưa toàn bộ URLs từ `research_results.json` + `news_results.json` vào
3. Hỏi 4 câu lần lượt:

| # | Câu hỏi |
|---|---|
| Q1 | Phân tích tổng quan: các nguồn này đang nói về điều gì? |
| Q2 | Pain points chính của business khi dùng AI là gì? |
| Q3 | Liệt kê 5–10 insights hay nhất có thể viết content |
| Q4 | Chủ đề nào chưa được làm nhiều mà có thể viral? |

**Output:** `insights.json`
```json
{
  "overview": "...",
  "pain_points": ["...", "..."],
  "insights": ["...", "...", "..."],
  "gap_topics": ["...", "..."]
}
```

---

## PHASE 3a — Review Agent (Critic)

**Skill file:** `review_agent.md`  
**Role:** Đọc insights thô, chấm điểm, chỉ giữ lại những insight đủ chất

### Tiêu chí chấm điểm (mỗi tiêu chí 1–5 điểm, tổng max 20)

| Tiêu chí | Câu hỏi |
|---|---|
| **Relevance** | Liên quan đến AI automation for business? |
| **Novelty** | Thông tin mới, chưa bị đăng nhiều? |
| **Viral** | Hook mạnh, dễ gây tranh luận? |
| **Actionable** | Người đọc áp dụng được ngay? |

### Ngưỡng lọc

- **≥ 14 / 20 điểm** → APPROVED (giữ lại, chuyển sang Writing Agent)
- **< 14 / 20 điểm** → REJECTED (ghi rõ lý do)

**Output:** `reviewed_insights.json`
```json
{
  "approved": [
    {
      "insight": "...",
      "scores": { "relevance": 5, "novelty": 4, "viral": 4, "actionable": 3 },
      "total": 16,
      "suggested_post_type": "news|guide|opinion",
      "hook_angle": "gợi ý góc tiếp cận"
    }
  ],
  "rejected": [
    { "insight": "...", "reason": "Điểm Novelty thấp (2/5), thông tin đã cũ" }
  ]
}
```

---

## PHASE 3b — Writing Agent (Creator)

**Skill file:** `writing_agent.md`  
**Role:** Nhận insights đã được duyệt, viết bài Facebook chất lượng cao

> ⚠️ **Nguyên tắc quan trọng:** Writing Agent chỉ viết dựa trên `reviewed_insights.json`.  
> Không tự ý thêm thông tin ngoài những gì NotebookLM đã phân tích.  
> Nếu insight không đủ để viết bài → báo lại Review Agent, không tự điền.

### Template theo từng loại bài

**TYPE: `news` → Đăng 7:00 AM**
```
Hook:    Đánh vào sự kiện mới, gây tò mò
Body:    Tóm tắt + ý nghĩa với business Việt Nam (150–250 từ)
CTA:     "Bạn nghĩ điều này ảnh hưởng thế nào đến công việc của bạn?"
Hashtag: 3–5 hashtag liên quan
```

**TYPE: `guide` → Đăng 12:00 PM**
```
Hook:    Kết quả cụ thể (đếm số)
Body:    Hướng dẫn 3–5 bước đơn giản (150–250 từ)
CTA:     "Bạn đã thử bước nào rồi?"
Hashtag: 3–5 hashtag liên quan
```

**TYPE: `opinion` → Đăng 7:00 PM**
```
Hook:    Đảo ngược niềm tin phổ biến
Body:    Lập luận 2 phía rõ ràng (150–250 từ)
CTA:     "Bạn ở phía nào? Comment xuống dưới!"
Hashtag: 3–5 hashtag liên quan
```

### First Comment Strategy

Mỗi bài viết kèm theo một `first_comment` để tăng engagement sớm và đặt link nguồn (tránh bị Facebook giảm reach khi có link trong post):

| Loại bài | Nội dung first_comment |
|---|---|
| news | Link nguồn gốc + danh sách resources liên quan |
| guide | Hướng dẫn chi tiết hơn (step-by-step đầy đủ) |
| opinion | Câu hỏi phụ kéo thêm comment reply |

**Output:** `posts.json`
```json
{
  "posts": [
    {
      "time": "07:00",
      "type": "news",
      "content": "...",
      "first_comment": "Nguon: https://... \n\nResources them:\n- ...\n- ..."
    },
    {
      "time": "12:00",
      "type": "guide",
      "content": "...",
      "first_comment": "Chi tiet tung buoc:\n1. ...\n2. ..."
    },
    {
      "time": "19:00",
      "type": "opinion",
      "content": "...",
      "first_comment": "Them mot cau hoi: ..."
    }
  ]
}
```

---

## PHASE 4 — Facebook Publisher

**Skill file:** `facebook_publisher.md`  
**API:** Facebook Graph API v19.0

### Step 1 — Lên lịch bài viết

```
POST https://graph.facebook.com/v19.0/{PAGE_ID}/feed
{
  "message": "{nội dung bài viết + hashtag}",
  "scheduled_publish_time": {unix timestamp},
  "published": false
}
```

Lịch đăng:
- Bài 1: 7:00 AM hôm nay
- Bài 2: 12:00 PM hôm nay
- Bài 3: 7:00 PM hôm nay

### Step 2 — Auto First Comment

Sau khi POST /feed thành công, lấy `post_id` trả về và ngay lập tức đăng comment:

```
POST https://graph.facebook.com/v19.0/{post_id}/comments
{
  "message": "{first_comment từ posts.json}"
}
```

> **Lưu ý:** Comment được đăng ngay lúc publish skill chạy (không delay), trước khi bài được schedule publish. Facebook sẽ hiển thị comment kèm theo bài khi bài được đăng.

### Step 3 — Báo cáo Telegram

```
POST https://api.telegram.org/bot{TOKEN}/sendMessage
{
  "chat_id": "{CHAT_ID}",
  "text": "✅ AutoFanpage {date}\n📝 3 bài đã lên lịch\n💬 3 first comment đã đăng\n⏱ {thời gian chạy}"
}
```

---

## PHASE 5 — Bài đăng theo khung giờ

| Giờ | Loại bài | Hook style | Mục tiêu |
|---|---|---|---|
| 7:00 AM | Tin tức AI mới | Sự kiện mới, cập nhật | Reach buổi sáng |
| 12:00 PM | Hướng dẫn thực chiến | Kết quả cụ thể, con số | Lưu bài, share |
| 7:00 PM | Quan điểm / Tranh luận | Đảo ngược niềm tin | Comment, reach |

Mỗi bài đều có **First Comment tự động** ngay sau khi publish.

---

## Cấu hình Agent tổng

```
# Agent: daily_content_pipeline
# Cron: 0 6 * * *  (6:00 AM hàng ngày)

Phase 1 (song song):
  - youtube_researcher(topic="AI automation business")
  - perplexity_researcher()

Phase 2:
  - notebooklm_analyzer()
  → Output: insights.json

Phase 3a:
  - review_agent()
  → Chấm điểm Relevance/Novelty/Viral/Actionable
  → Giữ insight ≥ 14/20
  → Output: reviewed_insights.json

Phase 3b:
  - writing_agent()
  → Viết từ reviewed_insights.json, không tự thêm
  → Output: posts.json (content + first_comment)

Phase 4:
  - facebook_publisher()
  → POST /feed (lên lịch)
  → POST /{post_id}/comments (first comment)
  → Báo cáo Telegram
```

**Lệnh khởi chạy trong Claude Code:**
```
/daily_content_pipeline chủ đề: "AI automation"
```

---

## Biến môi trường (.env)

```env
# YouTube
YOUTUBE_API_KEY=AIzaSy...

# Perplexity
PERPLEXITY_API_KEY=pplx-...

# Facebook
FACEBOOK_PAGE_ID=123456789
FACEBOOK_ACCESS_TOKEN=EAABwzLixn...

# Telegram
TELEGRAM_BOT_TOKEN=7123456789:AAF...
TELEGRAM_CHAT_ID=-100123456789

# NotebookLM
NOTEBOOKLM_EMAIL=your@gmail.com
```

---

## Files trung gian

| File | Tạo bởi | Dùng bởi | Nội dung |
|---|---|---|---|
| `research_results.json` | youtube_researcher | notebooklm_analyzer | 10 video URLs |
| `news_results.json` | perplexity_researcher | notebooklm_analyzer | 5 news + 3 reports |
| `insights.json` | notebooklm_analyzer | review_agent | Raw insights từ NLM |
| `reviewed_insights.json` | review_agent | writing_agent | Insights đã chấm điểm ≥14 |
| `posts.json` | writing_agent | facebook_publisher | 3 bài + first_comment |

---

## Checklist triển khai

**Setup (1 lần):**
- [ ] Lấy YouTube API key từ Google Cloud Console
- [ ] Lấy Perplexity API key (perplexity.ai/settings/api)
- [ ] Tạo Facebook App, lấy Page Access Token
- [ ] Request permissions: `pages_manage_posts`, `pages_read_engagement`
- [ ] Tạo Telegram Bot qua @BotFather
- [ ] Cài NotebookLM MCP: `pip install notebooklm-mcp`
- [ ] Điền đầy đủ file `.env`
- [ ] Tạo 6 skill files trong Claude Code
- [ ] Test từng skill riêng lẻ
- [ ] Kiểm tra Review Agent chấm điểm đúng chưa
- [ ] Kiểm tra Writing Agent không thêm thông tin ngoài notebook
- [ ] Kiểm tra First Comment được POST đúng sau mỗi bài
- [ ] Test toàn bộ pipeline 1 lần thủ công
- [ ] Cài Cron Job lúc 6:00 AM

**Vận hành (hàng tuần):**
- [ ] Kiểm tra Telegram có báo cáo thành công mỗi sáng
- [ ] Review engagement rate các bài trong tuần
- [ ] Kiểm tra Facebook Access Token chưa hết hạn
- [ ] Kiểm tra YouTube API quota còn bao nhiêu
- [ ] Điều chỉnh chủ đề nếu nội dung đang bị lặp
