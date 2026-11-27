# Data card — dữ liệu bản chạy thử dùng

> Điền ở guide bước 2.4 (bản đầu ở CP2, đủ ở CP3). Data tự dựng **không phải bằng chứng pain**.

## Dataset 1 · standup_policy

| | |
|---|---|
| Dùng để làm gì | nguồn cho công cụ `get_standup_policy` · câu thử về cửa sổ giờ |
| Từ đâu | nhóm tự viết từ insight P1 (cửa sổ 00:01–9h, cả CN) |
| Xử lý những bước gì | rút gọn thành JSON policy · không có PII |
| Số dòng / số đoạn | 1 file policy · 3 field · 4 rules |
| Phiên bản / ngày lấy | v0.1 · 2026-11-27 |
| Nhãn | `synthetic` |
| Giới hạn | chưa nối tool standup thật; giờ cố định VN |

**Data `synthetic`:** viết tay theo mô tả P1; seed khái niệm `20261127`; TV1 kiểm nội dung khớp pain.

## Dataset 2 · user_notes

| | |
|---|---|
| Dùng để làm gì | nguồn cho công cụ `get_user_notes` · soạn draft standup |
| Từ đâu | nhóm tự viết (persona giả u1/u2/u_empty/u_partial) |
| Xử lý những bước gì | JSON theo `user_id` · không tên người thật |
| Số dòng / số đoạn | 4 user giả |
| Phiên bản / ngày lấy | v0.1 · 2026-11-27 |
| Nhãn | `synthetic` |
| Giới hạn | ghi chú ngắn tiếng Việt không dấu một phần; không phản ánh data thật |

**Data `synthetic`:** script/tay, seed `20261127` trong `_meta`; không dùng làm bằng chứng pain.
