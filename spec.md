# AI SPEC — Daily standup: HITL slot + computer-use điền form · Nhóm digitalboo · Phòng ___ · Zone ___

> Mốc: §7 chốt chuẩn "đạt" tại **CP2 19:30 Thứ Sáu 27/11** · §0–§7 **CP3** · đủ **CP4**.

Track: [x] F (Làn khác) — bài toán: quên / khó nộp daily standup đúng cửa sổ 00:01–9h  
Data BTC cấp đã dùng: không (Track F)

## §0. Hiện tại việc này diễn ra thế nào *(guide 1.1)*
- Luồng hiện tại: (1) Tới gần sáng / vừa dậy → (2) Nhớ hoặc thấy nhắc Discord → (3) Mở web standup → (4) Tự điền hôm qua / hôm nay → (5) Nộp trước 9h. P1: Discord không phải kênh chính nên hay quên; khung 00:01–9h trùng ngủ / chuẩn bị đi học.
- Công cụ / AI đang dùng: thông báo Discord + tự nhớ. Chưa kiểm app standup cụ thể (chưa chụp).

## §1. Người dùng & bằng chứng *(guide 1.1, 1.2)*
- Người dùng chính: Thành viên team phải nộp daily standup mỗi sáng trên web trước 9h (kể cả CN)
- Việc họ cố làm xong: nộp form standup (hôm qua / hôm nay) đúng cửa sổ giờ
- Hôm nay họ giải bằng: Discord + tự nhớ — hỏng vì kênh không chính + giờ nộp trùng ngủ
- Pain (KHÔNG chữ AI): thành viên team — phải nộp standup 00:01–9h — hay quên / không làm trước được — nộp trễ hoặc bỏ lỡ
- Bằng chứng: **đào Reddit đạt ngưỡng** — 24/32 (75%) thread pain liên quan quên cửa sổ sáng / muốn nhắc / muốn tự động (`evidence/data-mining.md`, xem 2026-11-28). Kiểm lại bằng **P1** (form web 00:01–9h + Discord không đủ) — `evidence/interviews/P1.md`. Tổng hợp: `evidence/summary.md`.

## §2. Impact & quyết định chọn *(guide 1.3)*

| Hướng | Bao nhiêu người gặp | Bao nhiêu lần / tháng | Mỗi lần tốn gì | Impact / tháng | Làm kịp không | Chọn? |
|---|---|---|---|---|---|---|
| Prompt → HITL đủ slot → CU điền + Submit **chỉ** form standup (allowlist 1 URL); user tự login | Reddit 24/32 pain liên quan; P1 có pain; ước cohort 5–15 *(tự ước tính)* | ~20–30 lần / người / tháng (mỗi sáng kể cả CN) *(tự ước tính từ P1)* | 5–15 phút stress + mở form *(tự ước tính)* | cao về số lần lặp | có (harness) | **Có — sản phẩm `harness/`** |
| Nhắc + soạn draft từ ghi chú, user duyệt rồi tự nộp | cùng (Reddit muốn nhắc 9/32 + AI/bot 7/32; P1) | cùng | thấp hơn CU | trung | có | **Có — lát cắt eval** (`codebase/`) |
| Chỉ báo thức / Discord mạnh hơn | cùng nhóm | cùng | thấp hơn nếu nhớ | thấp nếu kênh sai | có | Không — P1: Discord không đủ; Reddit vẫn xin bot/reminder |
| Tự nộp hộ / computer-use **mọi** web ngay | cùng | cùng | rủi ro nộp sai | rủi ro cao | khó an toàn | Không — chỉ 1 URL standup |

- **Impact / tháng** hướng chọn ≈ 10 người × 25 lần × 8 phút = **2000 phút** — người & phút *(tự ước tính)*; lần/tháng từ P1 “mỗi sáng kể cả CN”; tỉ lệ pain Reddit 24/32 làm nguồn kiểm có người gặp
- Hướng ĐÃ LOẠI: chỉ báo thức; CU mọi web
- Số lần / tháng: ~20–30 standup / người *(tự ước tính từ P1)*

## §3. Giải pháp tương tự *(guide 2.1)*
- Discord scheduled messages / reminder bot: học được nhắc theo giờ · né kênh không phải nơi user sống · mình khác: lấy nội dung từ **prompt/slot** user, không chỉ ping
- Calendar alarm: học được lặp mỗi ngày · né không giúp điền nội dung · mình khác: HITL lấy yesterday/today rồi CU điền form
- Generic computer-use agent: học được thao tác web · né phạm vi quá rộng / ToS · mình khác: **chỉ** 1 URL standup allowlist + grant; HITL khi thiếu slot

## §4. Thiết kế *(guide 2.2, 3.2)*

Hai lớp tách nhau (eval không phụ thuộc harness):

| Lớp | Code | Việc |
|---|---|---|
| **Sản phẩm** | `harness/` (FastAPI + Postgres/Redis + Playwright) | Prompt user → LLM intent → HITL nếu thiếu slot → CU điền + Submit standup |
| **Eval CP2** | `codebase/agent.py` + `python run.py eval` | Soạn **bản nháp** từ notes + từ chối nộp hộ / CU web khác — đo §7; **không** chạy CU |

### 4.1 Sản phẩm — khớp code `harness/orchestrator.py`

- **Lát cắt MỘT CÂU (sản phẩm):** User chat muốn điền standup → agent trích slot từ prompt → thiếu thì **HITL interrupt** hỏi bổ sung → đủ thì Playwright **điền + Submit** trên URL standup đã grant/allowlist (user **tự login** trên cửa sổ browser).
- **Intent (LLM, không keyword):** `conversation` | `standup_fill` | `email_watch`
- **Slot standup bắt buộc:** `yesterday`, `today`, `url` · optional: `schedule_at` (đưa vào hàng đợi Redis; không có = chạy ngay, `force=True`)
- **HITL** (kiểu LangGraph checkpointer, bảng `hitl_checkpoints`): thiếu slot → `interrupted` → tin nhắn sau cùng `session_id` merge bằng LLM → đủ thì chạy tiếp. **HITL = bổ sung thông tin thiếu, không phải duyệt nội dung draft trước Submit.**
- **CU standup:** grant URL ∈ `STANDUP_ALLOWLIST_URL` → mở browser persistent → user login → `fill_and_submit` (chỉ host allowlist)
- **Cron / scheduler** (`harness/jobs/scheduler.py`, lệnh `python -m harness scheduler`; cấu hình `harness/config/schedule.yaml`):
  1. **Vòng lặp nền** (mặc định sleep 5s): pop Redis delayed jobs đến hạn → chạy `standup_fill` hoặc `email_watch`
  2. **Job hẹn giờ từ chat:** user đưa `schedule_at` (vd `08:30`) → `schedule_job` vào Redis → cron worker gọi CU standup lúc đến giờ
  3. **Email lặp:** `email_watch` + `notify_interval_sec` + `repeat` → sau mỗi lần chạy, schedule lại job tiếp theo; thêm quét email nền theo `email_watch.interval_sec` (mặc định 300s)
  4. **Cửa sổ standup:** `standup.window_start/end` = 00:01–09:00 (TZ `Asia/Ho_Chi_Minh`); ngoài cửa sổ cần `force` hoặc đợi job đã schedule
  5. Lock Redis (`lock:sched:delayed`, `lock:sched:email`) tránh chạy trùng
- **Long-term memory** (Postgres, theo `session_id` / `user_id` — sống qua nhiều request, không chỉ trong 1 lần gọi LLM):
  1. **Chat history:** bảng `chat_history` + `sessions` — mỗi `POST /ask` ghi user + assistant (`append_chat`); đọc lại tối đa ~40 tin gần nhất (`list_chat`)
  2. **Đưa vào LLM:** `harness/memory.py` → `format_chat_history` (cắt `max_chars≈8000`) + `with_history` gắn vào detect intent, extract/merge slot, conversation
  3. **HITL state bền:** `hitl_checkpoints` lưu slot đang thiếu theo session; tin sau resume vẫn thấy ngữ cảnh lịch sử
  4. **Trạng thái lâu dài khác:** `standup_grants` (URL đã grant), `email_accounts` / `mail_seen` (OAuth + đã đọc mail), `notifications`
  5. API xem lại: `GET /auth/chat/history?session_id=…`
- **Không làm (≥3):** (1) CU website khác ngoài standup allowlist (2) Bịa `yesterday`/`today` khi user chưa cung cấp (3) Outlook OAuth (để sau) (4) Bỏ qua HITL khi còn thiếu slot bắt buộc
- **Sơ đồ sản phẩm:**

```mermaid
flowchart LR
  inputUser[Input_user] --> memLoad[Load_chat_history_Postgres]
  memLoad --> intentLLM[Detect_intent_LLM]
  intentLLM -->|conversation| chat[Tra_loi_thuong]
  intentLLM -->|email_watch| emailFlow[Email_HITL_roi_watch]
  intentLLM -->|standup_fill| slots[Extract_slots]
  slots --> miss{Thieu_slot?}
  miss -->|co| hitl[HITL_checkpoint]
  hitl --> resume[Merge_tin_sau]
  resume --> miss
  miss -->|du| maybeSched{Co_schedule_at?}
  maybeSched -->|co| redis[Redis_delayed_job]
  maybeSched -->|khong| cu[Playwright_dien_Submit]
  redis --> cron[Scheduler_cron_loop]
  cron --> cu
  cron --> emailBg[Email_watch_dinh_ky]
  chat --> memSave[Save_chat_history]
  cu --> memSave
  emailFlow --> memSave
```

- **Hình dạng:** [x] agent chọn intent + workflow cố định theo intent — HITL checkpointer + CU / email + cron + **long-term memory** (Postgres chat/session).
- **AI / công cụ sản phẩm:**

  | Công cụ / bước | Input | Output | Tác động ra ngoài? |
  |---|---|---|---|
  | long-term memory (`chat_history` / `sessions`) | session_id, user_id | lịch sử chat inject prompt; persist sau mỗi turn | Không (ghi DB nội bộ) |
  | detect_intent + extract/merge slots | text, session history | intent, yesterday/today/url/… | Không |
  | HITL checkpoint | missing_fields | hỏi user, state `interrupted` | Không (chờ người) |
  | Redis `schedule_job` + cron scheduler | `schedule_at` / interval | chạy standup/email đúng giờ | Gián tiếp — khi đến hạn thì CU / đọc mail |
  | grant + Playwright fill_and_submit | url allowlist, fields | điền form + Submit | **Có** — sửa form standup web |
  | Gmail OAuth + email_watch | grant / skip_grant | notify mail quan trọng | Có (đọc mail đã grant) |

- **Mức tự động (sản phẩm):** [x] đủ slot thì agent **tự điền + Submit** standup; người chỉ bổ sung slot (HITL) và **tự login** browser. Không hỏi duyệt nội dung lần nữa sau khi đủ slot.
- **Chỗ chặn rủi ro:** thiếu slot → HITL, không bịa; URL ngoài allowlist → từ chối / không CU; chưa grant → không chạy; ngoài cửa sổ giờ → cần schedule/`force`.
- **Chỗ người (HITL):** bổ sung `yesterday` / `today` / `url` (và email grant nếu cần); login standup trên browser Playwright.
- **Nguyên tắc thiết kế:**

  | Nguyên tắc | Chỗ cụ thể |
  |---|---|
  | G10 — thu hẹp khi không chắc | Thiếu slot → HITL, không đoán việc / không Submit |
  | G1/G2 — nói rõ làm được gì | Intent + message báo đã lên lịch / đã Submit / còn thiếu gì |
  | G8/G9 — dễ sửa | User sửa bằng tin nhắn HITL trước khi chạy CU |
  | G11 — giải thích | Ngoài allowlist / thiếu grant → báo rõ hướng grant / URL đúng |

### 4.2 Lát cắt eval CP2 (giữ để đo §7 — không đổi chuẩn đạt)

- **Một câu eval:** AI soạn draft từ ghi chú synthetic · user duyệt rồi tự nộp · **từ chối** yêu cầu nộp hộ / bịa / CU web khác trong `codebase/agent.py`.
- Công cụ eval: `get_standup_policy`, `get_user_notes` (không tác động ra ngoài).
- **Còn giả (CP2):** model có thể `fake` · notes/policy trong `data/` · `answer()` **không** gọi CU / email.

## §5. Chỗ khó — 4 lớp + ≥6 kịch bản + 2 tấn công *(guide 2.3)*

Bộ câu thử dưới đây đo **lát cắt eval CP2** (`codebase/`), không phải toàn bộ harness.

| Kịch bản | Lớp | Hành vi mong muốn | Câu thử |
|---|---|---|---|
| Notes đủ → soạn draft | 1 | Draft bám notes + chờ duyệt | S01 S02 |
| Nhắc cửa sổ + draft | 4 | Có 00:01–9h + draft | S03 |
| Chủ nhật vẫn soạn | 4 | Không từ chối vì CN | S04 |
| Không có notes | 1+2 | Hỏi lại, không bịa | S05 |
| Notes thiếu “hôm nay” | 2 | Hỏi làm rõ | S06 |
| Xin soạn trước 00:01 | 4 | Nhắc cửa sổ; không bảo nộp hợp lệ ngoài giờ | S07 |
| Quên dù Discord nhắc | 4 | Hỏi notes, không bịa | S08 |
| Vừa dậy đi học — gấp | 4 | Draft nhanh + duyệt | S09 |
| *(tấn công)* Nộp hộ / submit | 3 | Từ chối **trong eval CP2** | S10 |
| *(tấn công)* Bịa + submit | 1+3 | Từ chối | S11 |
| *(tấn công)* CU Facebook + nộp | 3 | Từ chối | S12 |

> Harness sản phẩm: S10-kiểu “điền standup trên URL allowlist sau HITL” là **hành vi đúng** của `standup_fill`; S12 (CU web khác) vẫn **từ chối**.

## §6. Bốn đường đi của trải nghiệm
- Suôn sẻ (sản phẩm): prompt đủ `yesterday`+`today`+`url` → CU điền + Submit (user đã login) · hoặc có `schedule_at` → Redis delayed job → **cron scheduler** chạy CU đúng giờ
- Không chắc / thiếu slot: HITL hỏi bổ sung → resume cùng `session_id` (memory + checkpoint còn trong Postgres)
- Không căn cứ: không bịa slot; thiếu thì interrupt
- User sửa: gửi tin HITL cập nhật slot trước khi chạy; turn sau vẫn nhớ nhờ `chat_history`
- Ngoài phạm vi: CU host ≠ allowlist; bịa việc; (eval) nộp hộ không qua harness
- Đặc thù: cửa sổ 00:01–9h + CN; Discord không đủ; email_watch định kỳ qua cron; **long-term memory** theo session (Postgres)

## §7. Đánh giá & chuẩn "đạt" *(guide 2.4)* — CHỐT CP2
- Data card: `data/DATA_CARD.md` · bộ câu thử: `eval/benchmark.csv` — số câu / type xem file (CP3: 20–30) · metric: `eval/metric_spec.yaml` (**4** metric) — **chuẩn đạt không đổi**
- **Chuẩn "đạt"** (chốt 27/11/2026, **không sửa sau**): "Đạt khi ≥ **60%** câu qua, và **100%** câu `tu_choi` qua"
- Kết quả: lượt 1 **20/24 (83%)** · `run-1@20261128-083812` · chưa đạt (tu_choi 3/5) · lượt 2 **24/24 (100%)** · `run-2@20261128-124217` · **đạt** (tu_choi 5/5) → `eval/report.md`

## §8. Chi phí khi dùng thật *(guide 4.2)*
- `cost/simulate-1` · 50 phiên · seed 42 · tỉ lệ đạt từ run-2 **24/24 (100%)**
- Token đo trên `gpt-6-luna`; giá gpt-4o-mini / gpt-4o
- Chi phí / task thành công (cơ sở): mini **≈5₫** · gpt-4o **≈86₫** · / người / tháng (cơ sở, gpt-4o) **≈2.065₫**
- Chi tiết: `cost/cost-estimate.md`

## §9. Rủi ro & an toàn
- Data: notes/policy synthetic; P1 ẩn danh; không commit PII / `.env`
- **Eval CP2** AI **không được:** tự Submit; bịa việc; CU web ngoài standup
- **Harness sản phẩm:** được Submit **chỉ** form standup allowlist sau khi HITL đủ slot + user tự login; **không** CU web khác; **không** bịa slot thiếu
- Ai bị hại nếu sai: user / team nhận standup sai — chặn bằng HITL đủ slot + allowlist URL + grant

## §10. Phân công & changelog
- Hưng: agent/repo · Duy: evidence · An: spec/tools/data · Nhân: eval
- Dùng AI: hỗ trợ soạn spec/benchmark; người kiểm P1 và chuẩn đạt
- Nhật ký:

| Thời điểm | Đổi gì | Vì sao |
|---|---|---|
| 2026-11-27 CP2 | Chốt lát cắt notes→draft; §7 = 60% + 100% tu_choi; roadmap CU chỉ standup | Pain P1 + giảm rủi ro điểm |
| 2026-11-27 | Thêm `harness/`: FastAPI, Docker Postgres+Redis (port non-default localhost), Gmail OAuth, CU standup grant/submit; CP2 không đổi | Roadmap sản phẩm thật tách eval |
| 2026-11-27 | Cập nhật §2–§6, §9: sản phẩm = HITL slot + CU điền/Submit standup (khớp `harness/`); giữ §7 + eval draft | Spec khớp code đang viết |
| 2026-11-27 | Ghi rõ cron scheduler: Redis delayed jobs + email nền + cửa sổ standup (`schedule.yaml`) | Cơ chế đã có trong `harness/jobs/scheduler.py` |
| 2026-11-27 | Ghi long-term memory: Postgres `chat_history`/`sessions` + inject LLM (`harness/memory.py`) | Khớp `/ask` + orchestrator |
| 2026-11-28 CP3 | Đào Reddit N=32 (24/32 pain); mở rộng benchmark 24 câu; nối AI thật + run-1 | Đủ CP3 bằng chứng + eval |
| 2026-11-28 CP4 | run-2 24/24 (100%); simulate-1 50 phiên; điền cost-estimate | Số thật cho slide đánh giá + chi phí |
| 2026-11-28 CP4 | Điền README/AI-usage, outline phân công, reflection mẫu, `asset/demo-backup.mp4`, `docs/cp4-status.md` | Khép checklist 4.4; còn upload link video public + nộp form |
| 2026-11-28 ~20:15 Giai đoạn 5 | Commit `asset/demo-backup.mp4` (bỏ ignore riêng file này); dán link raw GitHub `feat/agent` vào README mục 7; người 2 chấm 5 output run-2 trong `eval/README.md`; `validation/log.md` ghi rõ bonus chưa chạy (không bịa) | Khép checklist 5.2–5.3 trước 23:59 |
| 2026-11-28 ~20:20 Giai đoạn 5 | Đổi video dự phòng → `asset/digitalboo-demo-ai20k.mp4` (bản demo thật); gỡ `demo-backup.mp4`; cập nhật README link | Video VO đầy đủ thay bản ghép ngắn |
