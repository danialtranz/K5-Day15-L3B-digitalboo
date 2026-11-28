# Chi phí khi dùng thật

> Điền ở guide bước 4.2, nộp ở CP4 14:30 Thứ Bảy 28/11. Ôn lại: ngày 13, ngày 1, ngày 14 · lab ngày 13, lab ngày 14. Chấm ở rubric R6.
> Số **không điền tay**: điền `cost/personas.yaml` → `python run.py simulate` → chép bảng trong `cost/simulate-N-summary.md` vào đây.
> Lúc build dùng gói miễn phí vẫn tính theo **giá gói trả phí** — đây là chi phí cho lúc đưa vào dùng thật.

## 1. Đầu vào

- **Persona** (`cost/personas.yaml`): ≥3 kiểu — dung_it 30% · dung_vua 50% · dung_nhieu 20%. Nguồn: *(tự ước tính)* từ P1 + Reddit + spec §2 (~20–30 standup/tháng)
- **Số người dùng thật** 3 kịch bản: thấp **5** · cơ sở **10** · cao **30**. Nguồn: *(tự ước tính)* cohort Edufun / team standup ~5–15 (spec.md §2)
- **Giá** ≥2 mức model: gpt-4o-mini **0.15/0.60** · gpt-4o **2.50/10.00** USD/1M (openai.com/api/pricing · 28/11/2026)
- **Tỉ lệ đạt** dùng để tính: **24/24 (100%)** — lượt `run-2`
- Đo token trên model **gpt-6-luna**, tính giá model **gpt-4o-mini** và **gpt-4o**

## 2. Kết quả mô phỏng

Lượt mô phỏng: `cost/simulate-1.csv` · run ID `simulate-1@20261128-124322` · **50** phiên · seed **42**

| Model | Chi phí / phiên | Chi phí / task thành công | / tháng — thấp | / tháng — cơ sở | / tháng — cao | / người / tháng (cơ sở) |
|---|---|---|---|---|---|---|
| gpt-4o-mini | $0.00020 (≈5₫) | $0.00020 (≈5₫) | $0.0244 (≈620₫) | $0.0488 (≈1.239₫) | $0.1464 (≈3.718₫) | $0.0049 (≈124₫) |
| gpt-4o | $0.0034 (≈86₫) | $0.0034 (≈86₫) | $0.4066 (≈10.327₫) | $0.8131 (≈20.654₫) | $2.44 (≈61.962₫) | $0.0813 (≈2.065₫) |

Chi phí / task thành công = chi phí trung bình mỗi phiên ÷ tỉ lệ đạt — **không coi như đạt 100%** (ở đây đạt = 100% nên bằng $/phiên).

## 3. So với impact

- Impact / người / tháng (`spec.md` §2): ~**25 lần × 8 phút ≈ 200 phút**/người · cohort ~10 người ≈ **2.000 phút/tháng** *(tự ước tính)*
- Chi phí / người / tháng (cơ sở, model gpt-4o): **≈2.065₫** (~$0.081)
- **Kết luận một dòng — đáng làm không:** **Đáng làm (Go hướng iterate sản phẩm)** — chi phí model cực thấp so với ~200 phút stress/người/tháng; rủi ro còn lại là HITL/CU thật chứ không phải token.

## 4. *(Muốn sâu hơn, không bắt buộc)*

- Độ nhạy: chuyển gpt-4o → gpt-4o-mini giảm ~17× chi phí (≈2.065₫ → ≈124₫ / người / tháng cơ sở)
- Chi phí ngoài model: hosting Postgres/Redis, Playwright, giờ công user HITL + login
- Quy mô cao 30 người vẫn chỉ ~62k₫/tháng ở gpt-4o
