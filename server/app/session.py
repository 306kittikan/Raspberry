"""เซสชันของตู้

ตู้ให้บริการทีละคน แต่ยังต้องมีโทเค็นเซสชัน เพราะหน้าเว็บไม่ควรบอกเซิร์ฟเวอร์ได้เอง
ว่า "ฉันคือนักศึกษาคนไหน" มิฉะนั้นใครเปิด DevTools ก็ดูตารางเรียนของคนอื่นได้

โทเค็นเก็บในหน่วยความจำเท่านั้น รีสตาร์ตเซิร์ฟเวอร์แล้วหายหมด
ซึ่งเป็นพฤติกรรมที่ต้องการ: ข้อมูลส่วนบุคคลไม่ค้างอยู่บนดิสก์
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import config, thai

# อายุของ "ผู้ที่ระบบคิดว่าใช่" ก่อนผู้ใช้กดยืนยัน — สั้นมากโดยตั้งใจ
CANDIDATE_TTL = timedelta(seconds=45)


@dataclass(slots=True)
class Session:
    token: str
    student_pk: int | None          # None = ใช้งานแบบไม่ระบุตัวตน
    restricted: bool                # True = เข้ามาด้วยการกรอกรหัส ไม่ได้ยืนยันตัวตน
    method: str                     # 'face' | 'student_id' | 'anonymous'
    created_at: datetime
    last_seen: datetime

    @property
    def expired(self) -> bool:
        idle = timedelta(
            seconds=config.SESSION_IDLE_SECONDS + config.SESSION_GRACE_SECONDS
        )
        return thai.now() - self.last_seen > idle


@dataclass(slots=True)
class Candidate:
    """ผลการรู้จำใบหน้าที่ยังรอผู้ใช้กดยืนยัน"""

    token: str
    student_pk: int
    score: float
    created_at: datetime

    @property
    def expired(self) -> bool:
        return thai.now() - self.created_at > CANDIDATE_TTL


@dataclass(slots=True)
class Store:
    sessions: dict[str, Session] = field(default_factory=dict)
    candidates: dict[str, Candidate] = field(default_factory=dict)

    # ---- ผู้ที่ระบบคิดว่าใช่ ----
    def offer_candidate(self, student_pk: int, score: float) -> Candidate:
        self._sweep()
        cand = Candidate(
            token=secrets.token_urlsafe(16),
            student_pk=student_pk,
            score=score,
            created_at=thai.now(),
        )
        self.candidates[cand.token] = cand
        return cand

    def take_candidate(self, token: str) -> Candidate | None:
        """ใช้ได้ครั้งเดียว — ดึงออกจากคลังทันทีที่เรียก"""
        cand = self.candidates.pop(token, None)
        if cand is None or cand.expired:
            return None
        return cand

    # ---- เซสชัน ----
    def start(self, *, student_pk: int | None, restricted: bool, method: str) -> Session:
        self._sweep()
        now = thai.now()
        sess = Session(
            token=secrets.token_urlsafe(24),
            student_pk=student_pk,
            restricted=restricted,
            method=method,
            created_at=now,
            last_seen=now,
        )
        self.sessions[sess.token] = sess
        return sess

    def get(self, token: str | None) -> Session | None:
        if not token:
            return None
        sess = self.sessions.get(token)
        if sess is None:
            return None
        if sess.expired:
            self.sessions.pop(token, None)
            return None
        return sess

    def touch(self, token: str) -> Session | None:
        sess = self.get(token)
        if sess is not None:
            sess.last_seen = thai.now()
        return sess

    def end(self, token: str | None) -> None:
        if token:
            self.sessions.pop(token, None)

    def _sweep(self) -> None:
        for token, sess in list(self.sessions.items()):
            if sess.expired:
                del self.sessions[token]
        for token, cand in list(self.candidates.items()):
            if cand.expired:
                del self.candidates[token]


store = Store()
