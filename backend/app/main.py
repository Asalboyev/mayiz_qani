import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.services.camera_ai import generate_camera_frames, get_camera_status
from app.services.telegram_service import send_location, send_message, send_photo


load_dotenv()

app = FastAPI(
    title="SafeDrop AI Backend",
    description="Shubhali harakatlarni aniqlash uchun local MVP backend.",
    version="0.3.0",
)

EVIDENCE_DIR = Path("app/data/evidence")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/evidence",
    StaticFiles(directory=str(EVIDENCE_DIR)),
    name="evidence",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# AI CAMERA ALERT MODELS
# =========================

class AlertCreate(BaseModel):
    camera_name: str = Field(default="Guliston Test Kamerasi 01")
    latitude: float = Field(default=40.4897)
    longitude: float = Field(default=68.7842)
    person_id: str = Field(default="P-001")
    face_match_name: Optional[str] = Field(default="Demo Shaxs")
    face_match_score: Optional[float] = Field(default=76.0)
    confidence: float = Field(default=82.0)
    action: str = Field(
        default="Shaxs bir joyda to‘xtadi, egildi, qo‘lini yerga yaqin olib bordi va hududdan chiqib ketdi"
    )
    status: str = Field(default="operator_tekshiruvi_talab_qilinadi")
    evidence_image_path: Optional[str] = Field(default=None)
    evidence_image_url: Optional[str] = Field(default=None)


class Alert(BaseModel):
    id: str
    created_at: str
    camera_name: str
    latitude: float
    longitude: float
    person_id: str
    face_match_name: Optional[str]
    face_match_score: Optional[float]
    confidence: float
    action: str
    status: str
    evidence_image_path: Optional[str]
    evidence_image_url: Optional[str]
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None


class AlertStatusUpdate(BaseModel):
    status: str = Field(default="operator_tekshiruvi_talab_qilinadi")
    reviewed_by: str = Field(default="operator")
    review_note: Optional[str] = Field(default=None)


# =========================
# DEMO FACEID MODELS
# =========================

class DemoFaceProfile(BaseModel):
    id: str
    full_name: str
    match_score: float
    risk_level: str
    status: str
    camera_name: str
    last_seen: str
    note: str


# =========================
# OPERATOR AUTH MODELS
# =========================

class OperatorLoginRequest(BaseModel):
    username: str
    password: str


# =========================
# CITIZEN PORTAL MODELS
# =========================

class CitizenSessionCreate(BaseModel):
    access_type: str = Field(default="anonymous")  # anonymous / identified
    full_name: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)


class CitizenSession(BaseModel):
    id: str
    created_at: str
    access_type: str
    full_name: Optional[str]
    phone: Optional[str]


class CitizenReportCreate(BaseModel):
    reporter_type: str = Field(default="anonymous")  # anonymous / identified
    full_name: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    description: str = Field(default="")
    location_text: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    evidence_note: Optional[str] = Field(default=None)


class CitizenReport(BaseModel):
    id: str
    created_at: str
    source: str
    reporter_type: str
    full_name: Optional[str]
    phone: Optional[str]
    description: str
    location_text: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    evidence_note: Optional[str]
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None


class CitizenReportStatusUpdate(BaseModel):
    status: str = Field(default="new")
    reviewed_by: str = Field(default="operator")
    review_note: Optional[str] = Field(default=None)


# =========================
# IN-MEMORY STORAGE
# =========================

alerts: List[Alert] = []
citizen_sessions: List[CitizenSession] = []
citizen_reports: List[CitizenReport] = []
audit_logs: List[dict] = []

demo_face_profiles: List[DemoFaceProfile] = [
    DemoFaceProfile(
        id="FACE-001",
        full_name="Demo Foydalanuvchi 01",
        match_score=78.4,
        risk_level="medium",
        status="Kuzatuvda",
        camera_name="Guliston Test Kamerasi 01",
        last_seen="Live camera stream",
        note="Hackathon uchun demo profil. Real davlat bazasi bilan ulanmagan.",
    ),
    DemoFaceProfile(
        id="FACE-002",
        full_name="Demo Foydalanuvchi 02",
        match_score=64.2,
        risk_level="low",
        status="Arxiv",
        camera_name="Guliston Test Kamerasi 01",
        last_seen="Oldingi test holati",
        note="Demo FaceID bazasidagi test profil.",
    ),
    DemoFaceProfile(
        id="FACE-003",
        full_name="Noma’lum shaxs",
        match_score=41.8,
        risk_level="unknown",
        status="Aniqlanmagan",
        camera_name="Guliston Test Kamerasi 01",
        last_seen="Moslik past",
        note="FaceID mosligi yetarli emas. Operator tekshiruvi talab qilinadi.",
    ),
]


# =========================
# HELPERS
# =========================

def format_status(status: str) -> str:
    statuses = {
        "operator_tekshiruvi_talab_qilinadi": "Operator tekshiruvi talab qilinadi",
        "tasdiqlandi": "Tasdiqlandi",
        "rad_etildi": "Rad etildi",
        "new": "Yangi",
        "reviewing": "Ko‘rib chiqilmoqda",
        "confirmed": "Tasdiqlandi",
        "rejected": "Rad etildi",
    }
    return statuses.get(status, status)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def add_audit_log(
    entity_type: str,
    entity_id: str,
    action: str,
    operator: str,
    note: Optional[str] = None,
):
    log = {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "operator": operator,
        "note": note,
    }

    audit_logs.append(log)
    return log


# =========================
# ROOT / HEALTH
# =========================

@app.get("/")
def root():
    return {
        "name": "SafeDrop AI",
        "status": "ishlayapti",
        "message": "Backend ishlayapti. /docs sahifasiga kiring.",
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SafeDrop AI Backend",
        "time": now_iso(),
    }


# =========================
# OPERATOR AUTH
# =========================

@app.post("/auth/operator-login")
def operator_login(payload: OperatorLoginRequest):
    demo_users = {
        "admin": "safedrop123",
        "operator": "operator123",
    }

    if payload.username not in demo_users:
        raise HTTPException(
            status_code=401,
            detail="Username yoki password noto‘g‘ri",
        )

    if demo_users[payload.username] != payload.password:
        raise HTTPException(
            status_code=401,
            detail="Username yoki password noto‘g‘ri",
        )

    return {
        "ok": True,
        "role": "operator",
        "username": payload.username,
        "message": "Operator muvaffaqiyatli kirdi",
    }


# =========================
# AI CAMERA ALERTS
# =========================

@app.get("/alerts")
def get_alerts():
    return {
        "count": len(alerts),
        "alerts": list(reversed(alerts)),
    }


@app.patch("/alerts/{alert_id}/status")
def update_alert_status(alert_id: str, payload: AlertStatusUpdate):
    allowed_statuses = {
        "operator_tekshiruvi_talab_qilinadi",
        "tasdiqlandi",
        "rad_etildi",
    }

    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Noto‘g‘ri status qiymati",
        )

    for alert in alerts:
        if alert.id == alert_id:
            alert.status = payload.status
            alert.reviewed_by = payload.reviewed_by
            alert.reviewed_at = now_iso()
            alert.review_note = payload.review_note

            add_audit_log(
                entity_type="ai_alert",
                entity_id=alert.id,
                action=payload.status,
                operator=payload.reviewed_by,
                note=payload.review_note,
            )

            if payload.status == "tasdiqlandi":
                message = f"""
✅ <b>AI alert tasdiqlandi</b>

<b>Kamera:</b> {alert.camera_name}
<b>Shaxs ID:</b> {alert.person_id}
<b>Vaqt:</b> {alert.created_at}
<b>Ko‘rib chiqqan operator:</b> {alert.reviewed_by}
<b>Review vaqti:</b> {alert.reviewed_at}

<b>Holat:</b> {format_status(alert.status)}
<b>Izoh:</b> {alert.review_note or "-"}
""".strip()

                send_message(message)

            return {
                "ok": True,
                "alert": alert,
            }

    raise HTTPException(
        status_code=404,
        detail="Alert topilmadi",
    )


@app.post("/alerts")
def create_alert(payload: AlertCreate):
    alert = Alert(
        id=str(uuid.uuid4()),
        created_at=now_iso(),
        **payload.model_dump(),
    )

    alerts.append(alert)

    message = f"""
🚨 <b>SafeDrop AI ogohlantirishi</b>

<b>Manba:</b> AI kamera
<b>Kamera:</b> {alert.camera_name}
<b>Vaqt:</b> {alert.created_at}
<b>Joylashuv:</b> {alert.latitude}, {alert.longitude}

<b>Aniqlangan shubhali harakat:</b>
{alert.action}

<b>Shaxs ID:</b> {alert.person_id}
<b>Demo FaceID mosligi:</b> {alert.face_match_name} — {alert.face_match_score}%

<b>Ishonchlilik darajasi:</b> {alert.confidence}%
<b>Holat:</b> {format_status(alert.status)}
""".strip()

    if alert.evidence_image_path:
        telegram_message_result = send_photo(alert.evidence_image_path, message)
    else:
        telegram_message_result = send_message(message)

    telegram_location_result = send_location(alert.latitude, alert.longitude)

    return {
        "ok": True,
        "alert": alert,
        "telegram_message": telegram_message_result,
        "telegram_location": telegram_location_result,
    }


@app.post("/alerts/demo")
def create_demo_alert():
    camera_name = os.getenv("CAMERA_NAME", "Guliston Test Kamerasi 01")
    latitude = float(os.getenv("CAMERA_LAT", "40.4897"))
    longitude = float(os.getenv("CAMERA_LON", "68.7842"))

    payload = AlertCreate(
        camera_name=camera_name,
        latitude=latitude,
        longitude=longitude,
        person_id="P-DEMO-001",
        face_match_name="Demo Foydalanuvchi 01",
        face_match_score=78.4,
        confidence=84.7,
        action="Shaxs 7 soniya davomida bir joyda turdi, devor yonida egildi, qo‘lini yerga yaqin olib bordi va hududdan tez chiqib ketdi",
        status="operator_tekshiruvi_talab_qilinadi",
    )

    return create_alert(payload)


# =========================
# CITIZEN PORTAL
# =========================

@app.post("/citizen/session")
def create_citizen_session(payload: CitizenSessionCreate):
    if payload.access_type not in {"anonymous", "identified"}:
        raise HTTPException(
            status_code=400,
            detail="access_type faqat anonymous yoki identified bo‘lishi mumkin",
        )

    session = CitizenSession(
        id=str(uuid.uuid4()),
        created_at=now_iso(),
        access_type=payload.access_type,
        full_name=payload.full_name,
        phone=payload.phone,
    )

    citizen_sessions.append(session)

    return {
        "ok": True,
        "session": session,
    }


@app.get("/citizen/reports")
def get_citizen_reports():
    return {
        "count": len(citizen_reports),
        "reports": list(reversed(citizen_reports)),
    }


@app.post("/citizen/reports")
def create_citizen_report(payload: CitizenReportCreate):
    if not payload.description.strip():
        raise HTTPException(
            status_code=400,
            detail="Xabar matni bo‘sh bo‘lishi mumkin emas",
        )

    if payload.reporter_type not in {"anonymous", "identified"}:
        raise HTTPException(
            status_code=400,
            detail="reporter_type faqat anonymous yoki identified bo‘lishi mumkin",
        )

    report = CitizenReport(
        id=str(uuid.uuid4()),
        created_at=now_iso(),
        source="citizen",
        reporter_type=payload.reporter_type,
        full_name=payload.full_name,
        phone=payload.phone,
        description=payload.description,
        location_text=payload.location_text,
        latitude=payload.latitude,
        longitude=payload.longitude,
        evidence_note=payload.evidence_note,
        status="new",
    )

    citizen_reports.append(report)

    reporter_label = "Anonim fuqaro"
    if report.reporter_type == "identified":
        reporter_label = report.full_name or "Fuqaro"

    location_label = report.location_text or "Ko‘rsatilmagan"
    coordinate_label = "-"
    if report.latitude is not None and report.longitude is not None:
        coordinate_label = f"{report.latitude}, {report.longitude}"

    message = f"""
📩 <b>Fuqaro xabari</b>

<b>Manba:</b> Fuqaro portali
<b>Yuboruvchi:</b> {reporter_label}
<b>Telefon:</b> {report.phone or "-"}
<b>Vaqt:</b> {report.created_at}

<b>Joy:</b> {location_label}
<b>Koordinata:</b> {coordinate_label}

<b>Xabar matni:</b>
{report.description}

<b>Qo‘shimcha dalil:</b>
{report.evidence_note or "-"}

<b>Holat:</b> {format_status(report.status)}
""".strip()

    telegram_message_result = send_message(message)

    telegram_location_result = None
    if report.latitude is not None and report.longitude is not None:
        telegram_location_result = send_location(report.latitude, report.longitude)

    return {
        "ok": True,
        "report": report,
        "telegram_message": telegram_message_result,
        "telegram_location": telegram_location_result,
    }


@app.patch("/citizen/reports/{report_id}/status")
def update_citizen_report_status(report_id: str, payload: CitizenReportStatusUpdate):
    allowed_statuses = {
        "new",
        "reviewing",
        "confirmed",
        "rejected",
    }

    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Noto‘g‘ri status qiymati",
        )

    for report in citizen_reports:
        if report.id == report_id:
            report.status = payload.status
            report.reviewed_by = payload.reviewed_by
            report.reviewed_at = now_iso()
            report.review_note = payload.review_note

            add_audit_log(
                entity_type="citizen_report",
                entity_id=report.id,
                action=payload.status,
                operator=payload.reviewed_by,
                note=payload.review_note,
            )

            if payload.status == "confirmed":
                reporter_label = "Anonim fuqaro"
                if report.reporter_type == "identified":
                    reporter_label = report.full_name or "Fuqaro"

                message = f"""
✅ <b>Fuqaro xabari tasdiqlandi</b>

<b>Yuboruvchi:</b> {reporter_label}
<b>Telefon:</b> {report.phone or "-"}
<b>Joy:</b> {report.location_text or "-"}
<b>Vaqt:</b> {report.created_at}

<b>Xabar:</b>
{report.description}

<b>Ko‘rib chiqqan operator:</b> {report.reviewed_by}
<b>Review vaqti:</b> {report.reviewed_at}
<b>Izoh:</b> {report.review_note or "-"}
""".strip()

                send_message(message)

            return {
                "ok": True,
                "report": report,
            }

    raise HTTPException(
        status_code=404,
        detail="Fuqaro xabari topilmadi",
    )


# =========================
# AUDIT LOGS
# =========================

@app.get("/audit/logs")
def get_audit_logs():
    return {
        "count": len(audit_logs),
        "logs": list(reversed(audit_logs)),
    }


# =========================
# FACEID DEMO
# =========================

@app.get("/faceid/demo")
def get_demo_face_profiles():
    return {
        "count": len(demo_face_profiles),
        "profiles": demo_face_profiles,
    }


# =========================
# CAMERA STREAM
# =========================

@app.get("/camera/status")
def camera_status():
    return get_camera_status()


@app.get("/camera/stream")
def camera_stream():
    return StreamingResponse(
        generate_camera_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )