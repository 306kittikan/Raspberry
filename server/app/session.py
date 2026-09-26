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
from typing import Any

from . import config, thai

# อายุของ "ผู้ที่ระบบคิดว่าใช่" ก่อนผู้ใช้กดยืนยัน — สั้นมากโดยตั้งใจ
CANDIDATE_TTL = timedelta(seconds=45)

# อายุของใบหน้าที่ถ่ายไว้แล้วแต่ยังไม่รู้ว่าเป็นของใคร
# ให้เวลาพอกรอกรหัสนักศึกษา 10 หลักแบบไม่ต้องรีบ แต่ไม่ค้างทิ้งไว้ทั้งวัน
PENDING_ENROLL_TTL = timedelta(minutes=3)


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
class PendingEnrollment:
    """ใบหน้าที่ถ่ายเสร็จแล้วแต่ยังไม่รู้ว่าเป็นของนักศึกษาคนใด

    เก็บไว้ในหน่วยความจำเท่านั้น ไม่เขียนลงดิสก์
    เวกเตอร์จะถูกบันทึกลงฐานข้อมูลก็ต่อเมื่อผู้ใช้กรอกรหัสนักศึกษาครบแล้ว
    ถ้าเดินจากไปกลางคัน ข้อมูลจะหมดอายุแล้วหายไปเอง
    """

    token: str
    vector: Any            # numpy array — ไม่ import numpy ที่นี่เพื่อไม่ผูกกับไลบรารีภาพ
    quality: float
    consent_at: datetime   # เวลาที่ผู้ใช้กดยินยอมจริง ๆ ใช้บันทึกเป็นหลักฐาน
    policy_version: str
    created_at: datetime

    @property
    def expired(self) -> bool:
        return thai.now() - self.created_at > PENDING_ENROLL_TTL


@dataclass(slots=True)
class Store:
    sessions: dict[str, Session] = field(default_factory=dict)
    candidates: dict[str, Candidate] = field(default_factory=dict)
    pending: dict[str, PendingEnrollment] = field(default_factory=dict)

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

    # ---- ใบหน้าที่รอระบุตัวตน ----
    def hold_enrollment(
        self, vector: Any, quality: float, consent_at: datetime, policy_version: str
    ) -> PendingEnrollment:
        self._sweep()
        item = PendingEnrollment(
            token=secrets.token_urlsafe(16),
            vector=vector,
            quality=quality,
            consent_at=consent_at,
            policy_version=policy_version,
            created_at=thai.now(),
        )
        self.pending[item.token] = item
        return item

    def take_enrollment(self, token: str) -> PendingEnrollment | None:
        """ใช้ได้ครั้งเดียว — ดึงออกจากคลังทันทีที่เรียก"""
        item = self.pending.pop(token, None)
        if item is None or item.expired:
            return None
        return item

    def drop_enrollment(self, token: str | None) -> None:
        if token:
            self.pending.pop(token, None)

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
        for token, item in list(self.pending.items()):
            if item.expired:
                del self.pending[token]


store = Store()
