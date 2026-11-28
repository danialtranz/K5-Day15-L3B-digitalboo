# Reflection — Trần Cảnh Hưng

> Làm ở guide bước 5.3. Hạn: **23:59 Thứ Bảy 28/11**.

1. Vai trò + phần mình làm (trỏ tới file / commit):
   Đội trưởng. Repo, `canvas.md`, nộp checkpoint; luồng `codebase/agent.py` + harness (`harness/orchestrator.py`, CU standup, scheduler). Changelog `spec.md` §10.

2. AI hỗ trợ mình thế nào (việc gì, công cụ gì, chỗ nào phải sửa lại output AI):
   Cursor/Codex hỗ trợ scaffold FastAPI/HITL/CU và siết pattern từ chối. Phải sửa tay regex (hyphen `computer-use`, “tự nộp” nhầm) sau run-1; tự chạy `eval`/`simulate` để lấy số thật.

3. Một câu thử trượt của nhóm và mình học được gì từ nó:
   **S15** (run-1): user nói “để tự nộp” bị từ chối nhầm vì pattern quá rộng. Học: phạm vi từ chối phải khớp intent (nộp hộ ≠ user tự nộp sau duyệt).
