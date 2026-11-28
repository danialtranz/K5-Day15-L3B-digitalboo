# Khai báo dùng AI

README của nhóm có mục "Dùng AI vào việc gì" (2–3 dòng, bắt buộc). Ghi chi tiết vào bảng dưới đây.

> Luật của đề: dùng AI để làm bài thoải mái, nhưng **ai không giải thích được phần có tên mình thì phần đó nhận 0 điểm**. Khai thiếu không bị trừ; giấu mới bị.

| Việc | Công cụ AI | AI làm gì | Người kiểm/sửa gì | Ai phụ trách |
|---|---|---|---|---|
| Code bản chạy thử | Cursor / Codex | Soạn `agent.py`, `tools.py`, harness FastAPI/CU | Hưng review luồng + chạy `eval`/`run.py` | Hưng |
| Prompt / thiết kế lời gọi mô hình | Cursor | Gợi ý system/user prompt soạn draft standup | An/Hưng siết phạm vi từ chối + HITL | An, Hưng |
| Đào data (viết script đếm, gợi ý nhãn) | Cursor | Gợi ý nhãn Reddit / cấu trúc bảng đếm | Duy kiểm tay toàn bộ N=32 thread, khớp nhãn | Duy |
| Rà câu hỏi phỏng vấn / khảo sát | Cursor | Rà câu dẫn dắt | Duy/An hỏi P1, ghi nguyên văn | Duy, An |
| Viết câu thử (benchmark) | Cursor | Gợi ý biến thể thuong/kho/tu_choi | Nhân chốt `source` + pass_criterion; không giấu câu trượt | Nhân |
| Sinh data `synthetic` (nếu có) | Cursor | Gợi ý notes/policy | Seed **20261127** · An kiểm notes u1/u2/u_empty/u_partial | An |
| Chấm cột `pass` bằng LLM (nếu có) | Không dùng LLM chấm | — | Người chấm theo `metric_spec.yaml` (run-1, run-2) | Nhân, Hưng |
| Slide, văn bản | Codex / Cursor | Gen dàn ý + `demo-slides.pdf` từ số eval/cost | Nhân đối chiếu số với `eval/report.md`, `cost-estimate.md` | Nhân |

**Không dùng AI để:** tạo người được phỏng vấn, trích dẫn, câu trả lời khảo sát; sửa kết quả các lượt đã chạy (`eval/run-*.csv`, `cost/simulate-*.csv`, `traces/`).
