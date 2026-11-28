"""Luồng chính — workflow: policy + notes → draft standup hoặc hỏi lại / từ chối."""
import re

from ai import call_model
from tools import get_standup_policy, get_user_notes
from tracing import note

SYSTEM = (
    "Ban soan BAN NHAP daily standup tu ghi chu user. "
    "Chi dung thong tin trong ghi chu; khong bia viec. "
    "Output tieng Viet: cac o Hom qua / Hom nay / Vuong mac. "
    "Ket thuc bang dong: Ban nhap — vui long duyet truoc khi nop. "
    "Khong bao gio noi da nop form."
)

REFUSE_PATTERNS = [
    r"nop\s*ho",
    r"nộp\s*hộ",
    r"nop\s*luon",
    r"nộp\s*luôn",
    r"tu\s*nop\s*(ho|hộ|giup|giúp|web|form)",
    r"tự\s*nộp\s*(hộ|giúp|web|form)",
    r"submit\s*(ho|hộ|giup|giúp|standup|luôn|luon)",
    r"computer[\s\-]*use",
    r"login\s*(ho|hộ|giup|giúp)|tự\s*login|tu\s*login",
    r"bia\s*(giup|giúp|ho|hộ)",
    r"bịa",
    r"facebook",
    r"github",
    r"web\s*khac",
    r"website\s*khác",
]


def _parse_user_id(text: str) -> str:
    m = re.search(r"user_id\s*[:=]\s*([A-Za-z0-9_]+)", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(u1|u2|u_empty|u_partial)\b", text)
    return m.group(1) if m else "u1"


def _is_refuse(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in REFUSE_PATTERNS)


def _notes_enough(notes: str) -> bool:
    if not notes or len(notes) < 20:
        return False
    # Can co it nhat goi y hom qua / hom nay
    low = notes.lower()
    has_y = any(k in low for k in ("hom qua", "hôm qua", "yesterday"))
    has_t = any(k in low for k in ("hom nay", "hôm nay", "today"))
    return has_y and has_t


def answer(text: str) -> dict:
    text = text or ""
    policy = get_standup_policy()
    window = "%s–%s" % (policy.get("window_start"), policy.get("window_end"))

    if _is_refuse(text):
        note("tu_choi: yeu cau ngoai pham vi / tan cong")
        return {
            "output": (
                "Tu choi. Lat cat hien tai chi soan BAN NHAP standup tu ghi chu de ban duyet; "
                "khong tu Submit web, khong computer-use web khac, khong bia noi dung viec. "
                "Hay de ghi chu (hom qua / hom nay) roi yeu cau soan draft trong cua so %s."
                % window
            )
        }

    user_id = _parse_user_id(text)
    notes_row = get_user_notes(user_id)
    notes = notes_row.get("notes") or ""

    if not notes_row.get("found") or not _notes_enough(notes):
        note("thieu_ghi_chu: hoi lai")
        return {
            "output": (
                "Chua du ghi chu de soan standup (can ro 'hom qua' va 'hom nay'). "
                "Ban hay bo sung ghi chu cho user_id=%s roi goi lai. "
                "Toi se khong bia viec da lam. "
                "Nhac: cua so nop standup la %s (ke ca CN)."
                % (user_id, window)
            )
        }

    note("soan_draft_tu_ghi_chu")
    fields = ", ".join(f["label"] for f in policy.get("fields", []))
    early = bool(
        re.search(
            r"23:\d+|tối\s*qua|toi\s*qua|soạn\s*sẵn|soan\s*san|trước\s*00:01|truoc\s*00:01",
            text,
            re.I,
        )
    )
    prompt = (
        "Policy cua so: %s\nFields: %s\nUser: %s\nGhi chu:\n%s\n\n"
        "Yeu cau nguoi dung:\n%s\n\n"
        "Hay soan ban nhap standup. Khong bia ngoai ghi chu."
        "%s"
        % (
            window,
            fields,
            user_id,
            notes,
            text,
            (
                "\nNeu user soan truoc cua so: nhac ro chi nop hop le trong cua so %s, "
                "khong khuyen khich nop ngoai gio."
                % window
                if early
                else ""
            ),
        )
    )
    reply = call_model(SYSTEM, prompt)
    body = reply.get("text") or ""
    if early and window.split("–")[0][:5] not in body and "00:01" not in body:
        body = (
            "Nhac: cua so nop hop le la %s — co the soan nhap truoc, "
            "chi nop trong cua so.\n\n" % window
        ) + body
    if "duyet" not in body.lower() and "duyệt" not in body.lower():
        body = body.rstrip() + "\n\nBan nhap — vui long duyet truoc khi nop."
    return {"output": body}
