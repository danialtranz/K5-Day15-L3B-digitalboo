# Tóm tắt mô phỏng simulate-1@20261128-124322

Do `python run.py simulate` sinh ra — không sửa tay. Chép bảng sang `cost/cost-estimate.md`.

| Persona | Số phiên mô phỏng | Lượt hỏi / phiên | Token vào / phiên | Token ra / phiên | Gọi model / phiên | Gọi công cụ / phiên |
|---|---:|---:|---:|---:|---:|---:|
| dung_it | 13 | 1 | 81 | 73 | 0.4 | 2.0 |
| dung_vua | 29 | 2 | 275 | 292 | 1.3 | 4.0 |
| dung_nhieu | 8 | 3 | 471 | 539 | 2.2 | 6.0 |

Tỉ lệ đạt dùng để tính: 24/24 (100%) — lượt run-2@20261128-124217

- Tỉ lệ đạt lấy từ lượt nhóm chọn: eval/run-2.csv (--rate-from).

| Model (giá) | Chi phí / phiên | Chi phí / task thành công | Chi phí / câu hỏi đạt | Chi phí / tháng — thấp (5 người) | Chi phí / tháng — cơ sở (10 người) | Chi phí / tháng — cao (30 người) | Chi phí / người / tháng (cơ sở) |
|---|---:|---:|---:|---:|---:|---:|---:|
| gpt-4o-mini (vào 0.15 · ra 0.6 $/1M) | $0.00020 (≈ 5 ₫) | $0.00020 (≈ 5 ₫) | $0.00011 (≈ 3 ₫) | $0.0244 (≈ 620 ₫) | $0.0488 (≈ 1.239 ₫) | $0.1464 (≈ 3.718 ₫) | $0.0049 (≈ 124 ₫) |
| gpt-4o (vào 2.5 · ra 10.0 $/1M) | $0.0034 (≈ 86 ₫) | $0.0034 (≈ 86 ₫) | $0.0018 (≈ 45 ₫) | $0.4066 (≈ 10.327 ₫) | $0.8131 (≈ 20.654 ₫) | $2.44 (≈ 61.962 ₫) | $0.0813 (≈ 2.065 ₫) |

- Chi phí / task thành công = chi phí / phiên ÷ tỉ lệ đạt. Chi phí / câu hỏi đạt = chi phí / phiên ÷ số lượt hỏi trung bình mỗi phiên (1.9) ÷ tỉ lệ đạt — tỉ lệ đạt đo theo từng câu thử.
- Token đo trên model: gpt-6-luna. Giá tính theo từng model trong bảng — model khác bộ tách token thì số token thật có thể lệch; ghi rõ "đo trên model X, tính giá model Y" trong cost/cost-estimate.md.
- Phiên lỗi (không tính vào trung bình): 0/50.
- Tỷ giá: 1 USD = 25.400 ₫ ((tự ước tính) ~25.400 VND/USD · xem 28/11/2026).
