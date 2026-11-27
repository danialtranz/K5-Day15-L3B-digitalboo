# Harness (ngoài lát cắt CP2)

Gmail OAuth + FastAPI + Postgres/Redis + Playwright standup (hybrid computer-use).

`python run.py` / eval CP2 **không** phụ thuộc thư mục này.

## 1. Docker (chỉ Postgres + Redis)

```powershell
cd dockers
docker compose -f dockercompose.yaml --env-file ../.env up -d
```

Port chỉ localhost, non-default: `15432` (Postgres), `16379` (Redis).

## 2. Venv + deps

```powershell
cd D:\src\AIInAction\day15-minihackathon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m harness init-db
```

## 3. Gmail OAuth

Redirect URI: `http://127.0.0.1:8000/email/oauth/google/callback`  
Điền `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` + `API_KEY` (OpenAI) trong `.env`.

```powershell
python -m harness serve
```

## 4. Intent + HITL

| Intent | Việc |
|---|---|
| `conversation` | Chat thường |
| `standup_fill` | Điền standup (yesterday/today/url) hoặc **hẹn lịch daily/weekly** — đến giờ hỏi nội dung (HITL + toast), rồi mới CU |
| `email_watch` | Đọc mail quan trọng; HITL nếu chưa Gmail; có thể **hẹn lịch** |

### Email lịch (timezone `Asia/Ho_Chi_Minh`)

User nói hẹn giờ (vd “mỗi sáng thứ Năm lúc 7h”) → LLM trích:

- `schedule_enabled`, `schedule_time` (`07:00`)
- `schedule_weekday` (0=Mon … 6=Sun; Thứ Năm = 3)
- `schedule_repeat`: `weekly` nếu “mỗi/lặp”; `once` nếu một lần
- `schedule_date`: `YYYY-MM-DD` khi one-shot có ngày
- `run_now`: true nếu vừa muốn kiểm tra ngay

Thiếu giờ/thứ/ngày → HITL (`missing_fields` chứa message LLM thân thiện).  
Đủ → Redis `jobs:delayed`; tới giờ scheduler quét mail → ghi `notifications`.

Query mail mặc định: unread **7 ngày**; user nêu khung thời gian thì theo yêu cầu.

### Desktop notifications

Mỗi `notify.push` ghi Postgres + `outbox/` **và** hiện balloon tip ngay trên desktop Windows (NotifyIcon).

Poll API (tuỳ chọn, app khác đọc):

```http
GET /email/notifications?user_id=u1&unread_only=true
GET /email/notifications?user_id=u1&since_id=42
POST /email/notifications/{id}/read?user_id=u1
POST /email/notifications/read-all?user_id=u1
```

### Computer-use hybrid (standup)

Router trong `harness/computer_use/`:

| URL | Strategy | Cách điền |
|---|---|---|
| Khớp playbook Edufun (`sites.yaml` → `portal-cohort5.edufun.ai` + `/my-submissions`) | **scripted** | Selector YAML (`#standup-yesterday` / `#standup-today`, ≥40 ký tự) |
| HTTPS URL khác user cung cấp | **vision** | Screenshot → multimodal LLM → click/type (tối đa `vision.max_steps`) |

Chung: Playwright mở browser → nếu cần login / chưa thấy form → **HITL `browser_login`** (giữ cửa sổ mở, user đăng nhập rồi nhắn lại) → điền form.  
`STANDUP_ALLOWLIST_URL` vẫn là URL mặc định / grant Edufun.

**Lịch daily/weekly:** payload Redis **không** lưu sẵn yesterday/today. Tới giờ → toast «cần nội dung» + HITL trong đúng `session_id` lúc hẹn → user trả lời chat → CU ngay. Không trả lời trong 2 giờ → toast bỏ lỡ; lịch ngày sau vẫn giữ.

| Method | Path | Việc |
|---|---|---|
| POST | `/ask` | Chat + orchestrator |
| GET | `/auth/sessions?user_id=u1` | Danh sách session chat |
| POST | `/auth/sessions` | Tạo session mới |
| GET | `/auth/chat/history?session_id=...&user_id=u1` | Lịch sử tin trong session |
| GET | `/email/oauth/google/start?format=json&user_id=u1&session_id=...` | `oauth_url` popup |
| GET | `/email/notifications` | Poll notify |
| POST | `/email/notifications/{id}/read` | Đánh dấu đã đọc |

## 5. Scheduler

`python -m harness serve` tự start background thread poll Redis. Weekly job tự `schedule_job` lại sau mỗi lần chạy.
