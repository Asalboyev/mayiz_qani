import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import base64
import json

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.services.camera_ai import generate_camera_frames, get_camera_status, analyze_frame_bytes
from app.services.telegram_service import send_location, send_message, send_photo
from app.services.face_match_service import match_face_against_database


load_dotenv()

app = FastAPI(
    title="SafeDrop AI Backend",
    description="Shubhali harakatlarni aniqlash uchun local MVP backend.",
    version="0.4.1",
)

EVIDENCE_DIR = Path("app/data/evidence")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

CITIZENS_DIR = Path("app/data/citizens")
CITIZEN_FACES_DIR = CITIZENS_DIR / "faces"
CITIZENS_FILE = CITIZENS_DIR / "citizens.json"

CITIZEN_FACES_DIR.mkdir(parents=True, exist_ok=True)

if not CITIZENS_FILE.exists():
    CITIZENS_FILE.write_text("[]", encoding="utf-8")

FACEID_DIR = Path("app/data/faceid")
FACEID_FACES_DIR = FACEID_DIR / "faces"
FACEID_FILE = FACEID_DIR / "faceid_records.json"

FACEID_FACES_DIR.mkdir(parents=True, exist_ok=True)

if not FACEID_FILE.exists():
    FACEID_FILE.write_text("[]", encoding="utf-8")

app.mount(
    "/evidence",
    StaticFiles(directory=str(EVIDENCE_DIR)),
    name="evidence",
)

app.mount(
    "/citizen-files",
    StaticFiles(directory=str(CITIZENS_DIR)),
    name="citizen-files",
)

app.mount(
    "/faceid-files",
    StaticFiles(directory=str(FACEID_DIR)),
    name="faceid-files",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
        default="AI kamera shubhali harakat patternini aniqladi."
    )
    status: str = Field(default="operator_tekshiruvi_talab_qilinadi")

    evidence_image_path: Optional[str] = Field(default=None)
    evidence_image_url: Optional[str] = Field(default=None)

    event_type: Optional[str] = Field(default=None)
    risk_reasons: List[str] = Field(default_factory=list)

    zoom_image_path: Optional[str] = Field(default=None)
    zoom_image_url: Optional[str] = Field(default=None)

    face_image_path: Optional[str] = Field(default=None)
    face_image_url: Optional[str] = Field(default=None)

    evidence_gallery_paths: List[str] = Field(default_factory=list)
    evidence_gallery_urls: List[str] = Field(default_factory=list)


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

    event_type: Optional[str] = None
    risk_reasons: List[str] = Field(default_factory=list)

    zoom_image_path: Optional[str] = None
    zoom_image_url: Optional[str] = None

    face_image_path: Optional[str] = None
    face_image_url: Optional[str] = None

    evidence_gallery_paths: List[str] = Field(default_factory=list)
    evidence_gallery_urls: List[str] = Field(default_factory=list)


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
# FACE ID DATABASE MODELS
# =========================

class FaceIdRecordCreate(BaseModel):
    full_name: str
    phone: Optional[str] = Field(default=None)
    risk_level: str = Field(default="unknown")
    source: str = Field(default="manual")  # citizen / manual
    note: Optional[str] = Field(default=None)
    face_image: str

# =========================
# AI FACE MATCHMAKING
# =========================

@app.get("/face-match/alerts/{alert_id}")
def get_face_match_for_alert(alert_id: str):
    for alert in alerts:
        if alert.id == alert_id:
            if not alert.face_image_url and not alert.face_image_path:
                raise HTTPException(
                    status_code=404,
                    detail="Bu alertda yuz rasmi topilmadi",
                )

            result = match_face_against_database(
                target_face_image_url=alert.face_image_url,
                target_face_image_path=alert.face_image_path,
                limit=10,
            )

            return {
                "ok": result.get("ok", False),
                "alert_id": alert.id,
                "created_at": alert.created_at,
                "camera_name": alert.camera_name,
                "event_type": alert.event_type,
                "confidence": alert.confidence,
                "target_face_image_url": alert.face_image_url,
                "result": result,
            }

    raise HTTPException(
        status_code=404,
        detail="Alert topilmadi",
    )


@app.get("/face-match/latest")
def get_latest_face_match():
    for alert in reversed(alerts):
        if alert.face_image_url or alert.face_image_path:
            result = match_face_against_database(
                target_face_image_url=alert.face_image_url,
                target_face_image_path=alert.face_image_path,
                limit=10,
            )

            return {
                "ok": result.get("ok", False),
                "alert_id": alert.id,
                "created_at": alert.created_at,
                "camera_name": alert.camera_name,
                "event_type": alert.event_type,
                "confidence": alert.confidence,
                "target_face_image_url": alert.face_image_url,
                "result": result,
            }

    return {
        "ok": False,
        "error": "Yuz rasmi bor alert hali mavjud emas",
        "result": None,
    }

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
    access_type: str = Field(default="anonymous")
    full_name: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)


class CitizenSession(BaseModel):
    id: str
    created_at: str
    access_type: str
    full_name: Optional[str]
    phone: Optional[str]


class CitizenRegisterRequest(BaseModel):
    full_name: str
    phone: str
    face_image: str


class CitizenLoginRequest(BaseModel):
    phone: str


class CitizenReportCreate(BaseModel):
    reporter_type: str = Field(default="anonymous")
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

    evidence_image_path: Optional[str] = None
    evidence_image_url: Optional[str] = None

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


def load_faceid_records() -> List[dict]:
    try:
        return json.loads(FACEID_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_faceid_records(records: List[dict]):
    FACEID_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_faceid_base64_image(face_image: str, prefix: str) -> str:
    if "," in face_image:
        face_image = face_image.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(face_image)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="FaceID rasmi noto‘g‘ri formatda",
        )

    filename = f"{prefix}_{uuid.uuid4().hex[:10]}.jpg"
    path = FACEID_FACES_DIR / filename
    path.write_bytes(image_bytes)

    return f"/faceid-files/faces/{filename}"


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())

    if digits.startswith("998"):
        digits = digits[3:]

    digits = digits[:9]

    if len(digits) < 9:
        raise HTTPException(
            status_code=400,
            detail="Telefon raqam to‘liq emas. Masalan: +998901234567",
        )

    return f"+998{digits}"


def load_citizens() -> List[dict]:
    try:
        return json.loads(CITIZENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_citizens(citizens: List[dict]):
    CITIZENS_FILE.write_text(
        json.dumps(citizens, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_face_image(face_image: str, citizen_id: str) -> str:
    if "," in face_image:
        face_image = face_image.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(face_image)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="FaceID rasmi noto‘g‘ri formatda",
        )

    filename = f"{citizen_id}.jpg"
    path = CITIZEN_FACES_DIR / filename
    path.write_bytes(image_bytes)

    return f"/citizen-files/faces/{filename}"


def parse_optional_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    try:
        return float(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Latitude yoki longitude noto‘g‘ri formatda",
        )


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


async def save_citizen_evidence(file: UploadFile):
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}

    original_name = file.filename or "evidence.jpg"
    suffix = Path(original_name).suffix.lower()

    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Faqat jpg, jpeg, png yoki webp rasm yuklash mumkin",
        )

    content = await file.read()

    max_size = 5 * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail="Rasm hajmi 5MB dan katta bo‘lishi mumkin emas",
        )

    filename = (
        f"citizen_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
        f"{uuid.uuid4().hex[:8]}{suffix}"
    )

    path = EVIDENCE_DIR / filename
    path.write_bytes(content)

    return str(path), f"/evidence/{filename}"


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

<b>Event turi:</b> {alert.event_type or "-"}
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

    risk_reason_text = "-"

    if alert.risk_reasons:
        risk_reason_text = "\n".join([f"• {reason}" for reason in alert.risk_reasons])

    gallery_count = len(alert.evidence_gallery_urls)

    message = f"""
🚨 <b>SafeDrop AI ogohlantirishi</b>

<b>Manba:</b> AI kamera
<b>Kamera:</b> {alert.camera_name}
<b>Vaqt:</b> {alert.created_at}
<b>Joylashuv:</b> {alert.latitude}, {alert.longitude}

<b>Aniqlangan shubhali harakat:</b>
{alert.action}

<b>Event turi:</b> {alert.event_type or "-"}

<b>Risk sabablari:</b>
{risk_reason_text}

<b>Shaxs ID:</b> {alert.person_id}
<b>Demo FaceID mosligi:</b> {alert.face_match_name} — {alert.face_match_score}%

<b>Ishonchlilik darajasi:</b> {alert.confidence}%
<b>Photo evidence:</b> {gallery_count} ta qo‘shimcha frame
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
        action=(
            "AI kamera shubhali harakat patternini aniqladi. "
            "Shaxs egilish/bukilish holatida pastki zona bilan shubhali harakat qildi."
        ),
        status="operator_tekshiruvi_talab_qilinadi",
        event_type="possible_hidden_drop",
        risk_reasons=[
            "Shaxs egildi yoki bukildi: pastki zona bilan shubhali harakat kuzatildi",
            "Operator tekshiruvi talab qilinadi",
        ],
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


@app.post("/citizen/reports/upload")
async def create_citizen_report_upload(
    reporter_type: str = Form(default="identified"),
    full_name: Optional[str] = Form(default=None),
    phone: Optional[str] = Form(default=None),
    description: str = Form(default=""),
    location_text: Optional[str] = Form(default=None),
    latitude: Optional[str] = Form(default=None),
    longitude: Optional[str] = Form(default=None),
    evidence_note: Optional[str] = Form(default=None),
    evidence_file: Optional[UploadFile] = File(default=None),
):
    if not description.strip():
        raise HTTPException(
            status_code=400,
            detail="Xabar matni bo‘sh bo‘lishi mumkin emas",
        )

    if reporter_type not in {"anonymous", "identified"}:
        raise HTTPException(
            status_code=400,
            detail="reporter_type faqat anonymous yoki identified bo‘lishi mumkin",
        )

    parsed_latitude = parse_optional_float(latitude)
    parsed_longitude = parse_optional_float(longitude)

    evidence_image_path = None
    evidence_image_url = None

    if evidence_file and evidence_file.filename:
        evidence_image_path, evidence_image_url = await save_citizen_evidence(evidence_file)

    report = CitizenReport(
        id=str(uuid.uuid4()),
        created_at=now_iso(),
        source="citizen",
        reporter_type=reporter_type,
        full_name=full_name,
        phone=phone,
        description=description,
        location_text=location_text,
        latitude=parsed_latitude,
        longitude=parsed_longitude,
        evidence_note=evidence_note,
        status="new",
        evidence_image_path=evidence_image_path,
        evidence_image_url=evidence_image_url,
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

<b>Rasm:</b> {"Bor" if report.evidence_image_url else "Yo‘q"}
<b>Holat:</b> {format_status(report.status)}
""".strip()

    if report.evidence_image_path:
        telegram_message_result = send_photo(report.evidence_image_path, message)
    else:
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


@app.post("/citizens/register")
def register_citizen(payload: CitizenRegisterRequest):
    full_name = payload.full_name.strip()

    if not full_name:
        raise HTTPException(
            status_code=400,
            detail="Ism familiya kiritilishi kerak",
        )

    phone = normalize_phone(payload.phone)
    citizens = load_citizens()

    for citizen in citizens:
        if citizen["phone"] == phone:
            raise HTTPException(
                status_code=400,
                detail="Bu telefon raqam oldin ro‘yxatdan o‘tgan",
            )

    citizen_id = f"CIT-{uuid.uuid4().hex[:10].upper()}"
    face_id = f"FACE-{uuid.uuid4().hex[:8].upper()}"
    face_image_url = save_face_image(payload.face_image, citizen_id)

    citizen = {
        "id": citizen_id,
        "face_id": face_id,
        "full_name": full_name,
        "phone": phone,
        "face_image_url": face_image_url,
        "created_at": now_iso(),
    }

    citizens.append(citizen)
    save_citizens(citizens)

    face_records = load_faceid_records()

    face_records.append(
        {
            "id": face_id,
            "full_name": full_name,
            "phone": phone,
            "source": "citizen",
            "risk_level": "registered",
            "face_image_url": face_image_url,
            "linked_citizen_id": citizen_id,
            "created_at": now_iso(),
            "note": "Fuqaro ro‘yxatdan o‘tganida avtomatik qo‘shilgan",
        }
    )

    save_faceid_records(face_records)

    return {
        "ok": True,
        "citizen": citizen,
    }


@app.post("/citizens/login")
def login_citizen(payload: CitizenLoginRequest):
    phone = normalize_phone(payload.phone)
    citizens = load_citizens()

    for citizen in citizens:
        if citizen["phone"] == phone:
            return {
                "ok": True,
                "citizen": citizen,
            }

    raise HTTPException(
        status_code=404,
        detail="Bu telefon raqam bo‘yicha user topilmadi",
    )


@app.get("/citizens")
def get_citizens():
    citizens = load_citizens()

    return {
        "count": len(citizens),
        "citizens": citizens,
    }


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
# FACE ID DATABASE
# =========================

@app.get("/faceid/records")
def get_faceid_records(source: str = "all"):
    records = load_faceid_records()

    if source != "all":
        records = [record for record in records if record.get("source") == source]

    return {
        "count": len(records),
        "records": list(reversed(records)),
    }


@app.post("/faceid/records")
def create_faceid_record(payload: FaceIdRecordCreate):
    full_name = payload.full_name.strip()

    if not full_name:
        raise HTTPException(
            status_code=400,
            detail="Ism familiya kiritilishi kerak",
        )

    if payload.source not in {"manual", "citizen"}:
        raise HTTPException(
            status_code=400,
            detail="source faqat manual yoki citizen bo‘lishi mumkin",
        )

    face_id = f"FACE-{uuid.uuid4().hex[:8].upper()}"
    face_image_url = save_faceid_base64_image(payload.face_image, "manual")

    record = {
        "id": face_id,
        "full_name": full_name,
        "phone": payload.phone,
        "source": payload.source,
        "risk_level": payload.risk_level,
        "face_image_url": face_image_url,
        "linked_citizen_id": None,
        "created_at": now_iso(),
        "note": payload.note,
    }

    records = load_faceid_records()
    records.append(record)
    save_faceid_records(records)

    return {
        "ok": True,
        "record": record,
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


# =========================
# PHONE CAMERA AI ANALYSIS
# =========================

@app.post("/camera/analyze")
async def analyze_phone_frame(file: UploadFile = File(...)):
    data = await file.read()
    result_jpeg = analyze_frame_bytes(data)
    if result_jpeg is None:
        raise HTTPException(status_code=500, detail="Frame tahlil qilinmadi")
    return StreamingResponse(
        iter([result_jpeg]),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )