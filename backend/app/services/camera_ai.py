import os
import time
import math
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
ALERT_ENDPOINT = os.getenv("ALERT_ENDPOINT", "http://127.0.0.1:8000/alerts")

CAMERA_NAME = os.getenv("CAMERA_NAME", "Guliston Test Kamerasi 01")
CAMERA_LAT = float(os.getenv("CAMERA_LAT", "40.4897"))
CAMERA_LON = float(os.getenv("CAMERA_LON", "68.7842"))

STATIONARY_SECONDS_TO_ALERT = float(os.getenv("STATIONARY_SECONDS_TO_ALERT", "7"))
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "25"))
PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", "3"))

EVIDENCE_DIR = Path("app/data/evidence")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

_model = None
_last_person_box: Optional[Tuple[int, int, int, int, float]] = None
_last_center: Optional[Tuple[int, int]] = None
_stationary_started_at: Optional[float] = None
_last_alert_at = 0.0

camera_status = {
    "camera_open": False,
    "model_loaded": False,
    "person_detected": False,
    "stationary_seconds": 0.0,
    "last_alert_at": None,
    "last_error": None,
}


def get_camera_status():
    return camera_status


def load_model():
    global _model

    if _model is not None:
        return _model

    if YOLO is None:
        camera_status["last_error"] = "Ultralytics YOLO import bo‘lmadi"
        return None

    try:
        _model = YOLO(YOLO_MODEL)
        camera_status["model_loaded"] = True
        return _model
    except Exception as error:
        camera_status["last_error"] = f"YOLO model yuklanmadi: {error}"
        return None


def distance(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def save_evidence_frame(frame) -> tuple[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"evidence_{timestamp}.jpg"
    path = EVIDENCE_DIR / filename

    cv2.imwrite(str(path), frame)

    return str(path), f"/evidence/{filename}"


def post_alert_async(confidence: float, frame=None):
    global _last_alert_at

    now = time.time()
    if now - _last_alert_at < ALERT_COOLDOWN_SECONDS:
        return

    _last_alert_at = now
    camera_status["last_alert_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    evidence_image_path = None
    evidence_image_url = None

    if frame is not None:
        evidence_image_path, evidence_image_url = save_evidence_frame(frame)

    payload = {
        "camera_name": CAMERA_NAME,
        "latitude": CAMERA_LAT,
        "longitude": CAMERA_LON,
        "person_id": "P-CAM-001",
        "face_match_name": "Demo Foydalanuvchi 01",
        "face_match_score": 78.4,
        "confidence": round(confidence, 1),
        "action": (
            "AI kamera shaxsni bir nuqtada uzoq vaqt davomida kuzatdi. "
            "Harakat patterni shubhali deb baholandi: to‘xtab turish, past zona atrofiga yaqinlashish va hududni tark etishga o‘xshash holat."
        ),
        "status": "operator_tekshiruvi_talab_qilinadi",
        "evidence_image_path": evidence_image_path,
        "evidence_image_url": evidence_image_url,
    }

    def worker():
        try:
            requests.post(ALERT_ENDPOINT, json=payload, timeout=5)
        except Exception as error:
            camera_status["last_error"] = f"Alert yuborishda xato: {error}"

    threading.Thread(target=worker, daemon=True).start()


def find_biggest_person(frame):
    global _last_person_box

    model = load_model()
    if model is None:
        return None

    try:
        result = model(frame, imgsz=640, conf=0.45, verbose=False)[0]
    except Exception as error:
        camera_status["last_error"] = f"YOLO detection xatosi: {error}"
        return None

    biggest = None
    biggest_area = 0

    for box in result.boxes:
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])

        # COCO datasetda person class id = 0
        if cls_id != 0:
            continue

        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
        area = max(0, x2 - x1) * max(0, y2 - y1)

        if area > biggest_area:
            biggest_area = area
            biggest = (x1, y1, x2, y2, confidence)

    _last_person_box = biggest
    return biggest


def analyze_behavior(person_box):
    global _last_center, _stationary_started_at

    if person_box is None:
        camera_status["person_detected"] = False
        camera_status["stationary_seconds"] = 0.0
        _last_center = None
        _stationary_started_at = None
        return False, 0.0

    x1, y1, x2, y2, confidence = person_box
    cx = int((x1 + x2) / 2)
    cy = int((y1 + y2) / 2)
    center = (cx, cy)

    camera_status["person_detected"] = True

    if _last_center is None:
        _last_center = center
        _stationary_started_at = time.time()
        return False, 0.0

    move_distance = distance(center, _last_center)

    # Agar odam joyidan ko‘p siljisa, timer reset bo‘ladi
    if move_distance > 40:
        _last_center = center
        _stationary_started_at = time.time()
        camera_status["stationary_seconds"] = 0.0
        return False, 0.0

    if _stationary_started_at is None:
        _stationary_started_at = time.time()

    stationary_seconds = time.time() - _stationary_started_at
    camera_status["stationary_seconds"] = round(stationary_seconds, 1)

    is_suspicious = stationary_seconds >= STATIONARY_SECONDS_TO_ALERT

    ai_confidence = min(
        95.0,
        65.0 + stationary_seconds * 3.0 + confidence * 10.0,
    )

    return is_suspicious, ai_confidence


def draw_text(frame, text, x, y, color=(230, 230, 230), scale=0.55, thickness=1):
    cv2.putText(
        frame,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_camera_ui(frame, person_box, is_suspicious, ai_confidence):
    h, w = frame.shape[:2]

    # Top black bar
    cv2.rectangle(frame, (0, 0), (w, 44), (8, 12, 18), -1)
    draw_text(frame, "SafeDrop AI  |  Live Camera Stream", 14, 28, (210, 220, 230), 0.55, 1)
    draw_text(frame, time.strftime("%Y-%m-%d %H:%M:%S"), w - 210, 28, (150, 160, 170), 0.5, 1)

    # Status panel
    cv2.rectangle(frame, (12, h - 100), (360, h - 14), (8, 12, 18), -1)
    cv2.rectangle(frame, (12, h - 100), (360, h - 14), (38, 49, 64), 1)

    detected_text = "PERSON: YES" if person_box else "PERSON: NO"
    stationary = camera_status["stationary_seconds"]

    draw_text(frame, detected_text, 26, h - 70, (180, 190, 200), 0.5, 1)
    draw_text(frame, f"STATIONARY: {stationary}s", 26, h - 45, (180, 190, 200), 0.5, 1)

    if is_suspicious:
        draw_text(frame, f"RISK: REVIEW REQUIRED  {ai_confidence:.1f}%", 26, h - 22, (0, 220, 255), 0.5, 1)
    else:
        draw_text(frame, "RISK: NORMAL", 26, h - 22, (120, 220, 160), 0.5, 1)

    if person_box is None:
        return frame

    x1, y1, x2, y2, confidence = person_box

    if is_suspicious:
        box_color = (0, 190, 255)
        label = f"P-CAM-001 | REVIEW | {ai_confidence:.1f}%"
    else:
        box_color = (60, 220, 120)
        label = f"P-CAM-001 | TRACKING | {confidence * 100:.1f}%"

    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

    label_w = max(220, len(label) * 9)
    cv2.rectangle(frame, (x1, max(0, y1 - 30)), (x1 + label_w, y1), box_color, -1)
    draw_text(frame, label, x1 + 8, y1 - 9, (5, 10, 15), 0.48, 1)

    return frame


def error_frame(message: str):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:] = (8, 12, 18)

    draw_text(frame, "SafeDrop AI", 40, 60, (230, 230, 230), 1.0, 2)
    draw_text(frame, message, 40, 110, (120, 130, 145), 0.75, 1)
    draw_text(frame, "Kamera indexini .env ichida CAMERA_INDEX=0 yoki 1 qilib tekshiring.", 40, 150, (120, 130, 145), 0.65, 1)

    return frame


def encode_jpeg(frame):
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        return None
    return buffer.tobytes()


def mjpeg_frame(jpeg_bytes):
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
    )


def generate_camera_frames():
    frame_count = 0
    last_box = None

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

    if not cap.isOpened():
        camera_status["camera_open"] = False
        camera_status["last_error"] = f"Kamera ochilmadi. CAMERA_INDEX={CAMERA_INDEX}"

        while True:
            frame = error_frame("Kamera ochilmadi")
            jpeg = encode_jpeg(frame)
            if jpeg:
                yield mjpeg_frame(jpeg)
            time.sleep(1)

    camera_status["camera_open"] = True
    camera_status["last_error"] = None

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    try:
        while True:
            ok, frame = cap.read()

            if not ok:
                camera_status["last_error"] = "Kameradan frame olinmadi"
                frame = error_frame("Kameradan frame olinmadi")
                jpeg = encode_jpeg(frame)
                if jpeg:
                    yield mjpeg_frame(jpeg)
                time.sleep(0.5)
                continue

            frame_count += 1

            if frame_count % PROCESS_EVERY_N_FRAMES == 0:
                last_box = find_biggest_person(frame)

            is_suspicious, ai_confidence = analyze_behavior(last_box)

            frame = draw_camera_ui(frame, last_box, is_suspicious, ai_confidence)

            if is_suspicious:
                post_alert_async(ai_confidence, frame.copy())

            jpeg = encode_jpeg(frame)
            if jpeg:
                yield mjpeg_frame(jpeg)

            time.sleep(0.02)

    finally:
        cap.release()
        camera_status["camera_open"] = False