"""ข้อมูลที่ตู้ต้องใช้ก่อนแสดงหน้าจอแรก — ไม่มีข้อมูลส่วนบุคคลใด ๆ"""

from __future__ import annotations

from fastapi import APIRouter

from .. import config, repo, thai
from ..deps import Db

router = APIRouter(prefix="/api", tags=["kiosk"])


@router.get("/health")
def health(conn: Db) -> dict:
    term = repo.get_current_term(conn)
    return {
        "ok": True,
        "time": thai.now().isoformat(timespec="seconds"),
        "term": term["code"] if term else None,
        "aiEnabled": config.AI_ENABLED,
    }


@router.get("/bootstrap")
def bootstrap(conn: Db) -> dict:
    """ทุกอย่างที่หน้าจอพักต้องใช้ ขอครั้งเดียวตอนเปิดตู้"""
    term = repo.get_current_term(conn)
    today = thai.now().date().isoformat()

    data_updated_label = None
    if term and term["data_updated_at"]:
        from datetime import datetime

        data_updated_label = thai.format_datetime(
            datetime.fromisoformat(term["data_updated_at"])
        )

    return {
        "department": repo.get_department(conn),
        "term": {
            "code": term["code"] if term else None,
            "label": term["label"] if term else None,
            "dataUpdatedLabel": data_updated_label,
        },
        "announcements": repo.list_announcements(conn, today),
        "quickQuestions": repo.list_quick_questions(conn),
        "timing": {
            "sessionIdleSeconds": config.SESSION_IDLE_SECONDS,
            "sessionGraceSeconds": config.SESSION_GRACE_SECONDS,
        },
        "consentPolicyVersion": config.CONSENT_POLICY_VERSION,
    }
