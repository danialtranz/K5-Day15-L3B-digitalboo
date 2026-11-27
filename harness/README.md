# Harness (ngoài lát cắt CP2)

Gmail OAuth + FastAPI + Postgres/Redis + Playwright standup (1 URL allowlist).

`python run.py` / eval CP2 **không** phụ thuộc thư mục này.

## 1. Docker (chỉ Postgres + Redis)

```powershell
# Đảm bảo đã có .env (copy từ .env.example, mật khẩu đã có sẵn trong .env local)
cd dockers
docker compose -f dockercompose.yaml --env-file ../.env up -d
```

Port chỉ localhost, non-default: `15432` (Postgres), `16379` (Redis).

## 2. Venv + deps (trong repo)

```powershell
cd D:\src\AIInAction\day15-minihackathon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m harness init-db
```

Luôn dùng `.\.venv\Scripts\python.exe` hoặc activate trước khi `harness serve` — không cài vào user site-packages.

## 3. Gmail OAuth

1. Google Cloud Console → OAuth client (Web)  
2. Redirect URI: `http://127.0.0.1:8000/email/oauth/google/callback`  
3. Điền `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` vào `.env`  
4. Activate venv rồi chạy API:

```powershell
.\.venv\Scripts\Activate.ps1
python -m harness serve
# Mở: http://127.0.0.1:8000/email/oauth/google/start
```

## 4. API chính

Auth tối giản: `user_id` phải có trong bảng `users` (seed sẵn `u1`).

Orchestrator: **1 lần** LLM detect intent (không keyword) → 3 intent:

| Intent | Việc |
|---|---|
| `conversation` | Chào hỏi / chat thường |
| `standup_fill` | Tự điền standup — cần `yesterday`, `today`, `url`; `schedule_at` optional (Redis delayed job) |
| `email_watch` | Đọc mail quan trọng — HITL nếu chưa Gmail grant (có thể “bỏ qua grant”); `notify_interval_sec` optional |

**HITL** kiểu LangGraph checkpointer: thiếu slot → `hitl_checkpoints` status=`interrupted` → tin nhắn sau cùng `session_id` được merge bằng LLM rồi chạy tiếp.

| Method | Path | Việc |
|---|---|---|
| POST | `/auth/login` | `{"user_id":"u1"}` → `session_id` |
| GET | `/auth/me?user_id=u1` | kiểm tra user |
| GET | `/auth/chat/history?session_id=...&user_id=u1` | lịch sử chat |
| GET | `/health` | health |
| POST | `/ask` | `{"text":"...","user_id":"u1","session_id":"..."}` |
| GET | `/email/oauth/google/start` | Connect Gmail |
| GET | `/email/status` | Trạng thái connect |
| POST | `/email/watch` | Quét mail quan trọng |
| GET | `/email/notifications` | Tin agent báo user |
| POST | `/standup/grant` | `{"url":"https://..."}` |
| POST | `/standup/run` | `{"force":true}` thử ngoài cửa sổ |

## 5. Standup CU

1. Set `STANDUP_ALLOWLIST_URL` đúng form standup  
2. Chỉnh selector trong `harness/config/sites.yaml`  
3. `python -m harness grant-standup --url https://...`  
4. `python -m harness run-standup --now` — cửa sổ browser mở, **bạn tự login**, agent điền + Submit  

## 6. Scheduler

```powershell
python -m harness scheduler
```
