# Prompt gen video demo (Codex / video agent)

## Mục tiêu
Tạo **1 video demo sản phẩm ~2 phút** (90–120 giây), tiếng Việt, phong cách sôi động, rõ ràng, dễ hiểu cho hackathon.

## Spec kỹ thuật (BẮT BUỘC)

| Hạng mục | Yêu cầu |
|---|---|
| Độ dài | **2 phút** (không vượt quá 2:05) |
| Giọng thuyết trình | **Nam**, tiếng Việt tự nhiên, rõ chữ, tốc độ vừa phải, năng lượng tích cực |
| Nhạc nền | Nhạc **sôi động / upbeat** (electronic / corporate-energetic), không lời hát che giọng |
| Ducking nhạc | Khi **có giọng nam**: nhạc nền **nhỏ hơn ~20%** so với lúc không nói. Khi **không có giọng**: nhạc **to lại** mức bình thường. Chuyển mức âm thanh mượt (fade ngắn ~0.2–0.4s), không cắt cứng |
| Âm thanh chuyển cảnh | Mỗi lần đổi scene / cắt sang clip demo: thêm **SFX đơn giản** (whoosh / soft click / short transition), ngắn 0.2–0.5s, không ồn |
| Tỷ lệ khung | 16:9 |
| Text trên màn hình | Tiếng Việt, ngắn, lớn, dễ đọc; tránh chữ dày đặc |
| Asset clip sẵn có (chèn đúng thời điểm bên dưới) | `asset/computer_use_trên_web.mp4`, `asset/doc_email.mp4`, `asset/schedule_job.mp4`, `asset/notify-desktop.mp4` |

---

## Kịch bản (timeline gợi ý)

### Scene 1 — Mở đầu / nêu vấn đề (0:00–0:25)
**Hình:** background động tối giản + text lớn hiện lần lượt theo lời thoại.  
**SFX:** chuyển cảnh mở đầu.

**Lời thoại (nam):**
> Bạn có bao giờ nhớ ra một việc cần làm… rồi lại quên mất?  
> Task nhiều, lịch dày — lúc nhớ được thì đã muộn.  
> Nếu lúc nào nhớ cũng có thể giao luôn cho agent làm giúp thì sao?

**On-screen text (gợi ý):**
- “Nhớ nhớ… quên quên?”
- “Giao việc cho agent — ngay khi bạn nhớ”

---

### Scene 2 — Agent làm việc theo lệnh người dùng (0:25–0:55)
**Hình:** intro ngắn 2–3 giây (icon / UI tóm tắt), sau đó **chạy lần lượt 2 clip minh họa**:

1. **`asset/computer_use_trên_web.mp4`** — agent thao tác trên website  
2. **`asset/doc_email.mp4`** — agent đọc / kiểm email quan trọng  

Mỗi clip mở bằng **SFX chuyển cảnh**. Có thể chồng caption ngắn góc dưới.

**Lời thoại (nam):**
> Người dùng có thể yêu cầu agent làm việc giúp: xem email xem có thư nào quan trọng không, hoặc truy cập website để thao tác thay mình.  
> Nếu trang web cần đăng nhập, agent chuyển sang chế độ HITL — Human in the Loop — để bạn tự login trên trình duyệt, rồi agent tiếp tục.

**On-screen text (gợi ý):**
- “Xem email quan trọng”
- “Thao tác website giúp bạn”
- “Cần login? → HITL (bạn tự đăng nhập)”

---

### Scene 3 — Lên lịch / chạy theo khung giờ (0:55–1:25)
**Hình:** chuyển sang **`asset/schedule_job.mp4`** (SFX chuyển cảnh). Caption ví dụ lịch.

**Lời thoại (nam):**
> Không chỉ ra lệnh ngay lúc này — bạn còn có thể bảo agent hoàn thành một task cụ thể trong khoảng thời gian nhất định.  
> Ví dụ: mỗi sáng 7 giờ đọc email xem có thông tin quan trọng không.  
> Hoặc 8 giờ 55 sáng vào web và hoàn thành mentor duty.

**On-screen text (gợi ý):**
- “07:00 — Đọc email quan trọng”
- “08:55 — Mentor duty trên web”
- “Schedule job — agent chạy đúng giờ”

---

### Scene 4 — Thông báo kết quả trên desktop (1:25–1:50)
**Hình:** chuyển sang **`asset/notify-desktop.mp4`** (SFX chuyển cảnh).

**Lời thoại (nam):**
> Kết quả job đã lên lịch — dù thành công hay thất bại — đều được thông báo qua ứng dụng desktop.  
> Bạn luôn nắm được agent vừa làm gì, xong chưa, có lỗi không.

**On-screen text (gợi ý):**
- “Thành công / Thất bại → đều có notify”
- “Desktop app — luôn cập nhật”

---

### Scene 5 — Công nghệ + đóng (1:50–2:00)
**Hình:** slide kết, logo / tên sản phẩm (nếu có), keyword “Computer Use”. Nhạc nền **to hơn** vì lời thoại ngắn / nghỉ cuối. SFX kết nhẹ.

**Lời thoại (nam):**
> Phía sau là Computer Use — để agent tự thao tác trên máy và trình duyệt như một người dùng thật.  
> Nhớ việc nào — giao luôn. Đúng giờ — agent lo. Bạn chỉ việc kiểm tra thông báo.

**On-screen text (gợi ý):**
- “Powered by Computer Use”
- “Giao việc khi nhớ · Chạy đúng giờ · Notify trên desktop”

---

## Quy tắc dựng video

1. **Ưu tiên clip thật** trong `asset/` khi minh họa feature; đừng thay bằng mock giả nếu clip đã có.
2. Giọng nam **không chồng** lên đoạn clip quá rối — nếu clip dài, rút gọn / cắt highlight 8–15 giây mỗi feature.
3. Giữ nhịp nhanh: mỗi ý 1 câu ngắn; không giảng dài.
4. Ducking nhạc nền **liên tục** theo có/không có voice (chênh ~20%).
5. Mỗi lần cắt scene / mở clip mới: **1 SFX chuyển cảnh đơn giản**.
6. Không thêm cảnh thừa ngoài kịch bản trên. Demo gọn: vấn đề → 2 feature (web + email) → schedule → notify → tech close.

## Output mong muốn
- File video `.mp4` 16:9, ~2 phút  
- Có voice-over nam tiếng Việt + nhạc nền ducking + SFX chuyển cảnh  
- Đã nhúng đúng 4 clip: `computer_use_trên_web.mp4`, `doc_email.mp4`, `schedule_job.mp4`, `notify-desktop.mp4`

## Checklist trước khi xuất
- [ ] ≤ 2 phút  
- [ ] Giọng nam tiếng Việt  
- [ ] Nhạc sôi động + duck ~20% khi có voice  
- [ ] SFX mỗi lần chuyển cảnh  
- [ ] HITL được nhắc khi web cần login  
- [ ] Schedule ví dụ 7h email / 8:55 mentor duty  
- [ ] Notify desktop (thành công & thất bại)  
- [ ] Kết bằng Computer Use  
