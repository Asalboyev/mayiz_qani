import os
import sys
import time
import math
import uuid
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


# =========================
# CONFIG
# =========================

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "").strip()

YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
YOLO_CONFIDENCE = float(os.getenv("YOLO_CONFIDENCE", "0.22"))
YOLO_IMGSZ = int(os.getenv("YOLO_IMGSZ", "960"))

ALERT_ENDPOINT = os.getenv("ALERT_ENDPOINT", "http://127.0.0.1:8001/alerts")

CAMERA_NAME = os.getenv("CAMERA_NAME", "Guliston Test Kamerasi 01")
CAMERA_LAT = float(os.getenv("CAMERA_LAT", "40.4897"))
CAMERA_LON = float(os.getenv("CAMERA_LON", "68.7842"))

PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", "2"))
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "6"))

# Stationary endi asosiy trigger emas
STATIONARY_SECONDS_TO_ALERT = float(os.getenv("STATIONARY_SECONDS_TO_ALERT", "999"))

PHOTO_POSE_SECONDS_TO_ALERT = float(os.getenv("PHOTO_POSE_SECONDS_TO_ALERT", "0.15"))
CROUCH_SECONDS_TO_ALERT = float(os.getenv("CROUCH_SECONDS_TO_ALERT", "0.15"))

MOVE_RESET_DISTANCE = float(os.getenv("MOVE_RESET_DISTANCE", "42"))
LOWER_MOTION_THRESHOLD = float(os.getenv("LOWER_MOTION_THRESHOLD", "5.5"))

SMART_ZOOM_ENABLED = os.getenv("SMART_ZOOM_ENABLED", "true").lower() == "true"
SMART_ZOOM_PADDING = float(os.getenv("SMART_ZOOM_PADDING", "0.55"))
SMART_ZOOM_ON_PERSON = os.getenv("SMART_ZOOM_ON_PERSON", "true").lower() == "true"

INSTANT_ALERT_ENABLED = os.getenv("INSTANT_ALERT_ENABLED", "true").lower() == "true"

# Person false positive kamaytirish
PERSON_MIN_CONFIDENCE = float(os.getenv("PERSON_MIN_CONFIDENCE", "0.45"))
PERSON_MIN_AREA_RATIO = float(os.getenv("PERSON_MIN_AREA_RATIO", "0.025"))
PERSON_MAX_AREA_RATIO = float(os.getenv("PERSON_MAX_AREA_RATIO", "0.70"))
PERSON_MIN_HEIGHT = int(os.getenv("PERSON_MIN_HEIGHT", "120"))

# Photo evidence event
FRAME_BUFFER_SIZE = int(os.getenv("FRAME_BUFFER_SIZE", "120"))
EVIDENCE_BURST_COUNT = int(os.getenv("EVIDENCE_BURST_COUNT", "6"))
PHOTO_EVENT_PRE_SECONDS = float(os.getenv("PHOTO_EVENT_PRE_SECONDS", "1.5"))
PHOTO_EVENT_CAPTURE_SECONDS = float(os.getenv("PHOTO_EVENT_CAPTURE_SECONDS", "2.5"))

EVIDENCE_DIR = Path("app/data/evidence")
EVIDENCE_FACES_DIR = EVIDENCE_DIR / "faces"
EVIDENCE_ZOOM_DIR = EVIDENCE_DIR / "zoom"

EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_FACES_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_ZOOM_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# COCO CLASS IDS
# =========================

PERSON_CLASS_ID = 0
CELL_PHONE_CLASS_ID = 67

SUSPICIOUS_OBJECT_CLASS_IDS = {
    24,  # backpack
    26,  # handbag
    28,  # suitcase
    39,  # bottle
    41,  # cup
    45,  # bowl
    67,  # cell phone
}


# =========================
# GLOBAL STATE
# =========================

_model = None

_last_person_box: Optional[Tuple[int, int, int, int, float]] = None
_last_center: Optional[Tuple[int, int]] = None
_stationary_started_at: Optional[float] = None

_baseline_person_height: Optional[float] = None
_photo_pose_started_at: Optional[float] = None
_crouch_started_at: Optional[float] = None
_object_action_started_at: Optional[float] = None

_previous_gray: Optional[np.ndarray] = None

_last_alert_at = 0.0
_last_risk_reasons: List[str] = []
_last_event_type = "normal"
_last_ai_confidence = 0.0

# timestamp bilan frame saqlaymiz: (time.time(), frame)
_frame_buffer = deque(maxlen=FRAME_BUFFER_SIZE)

# Shubhali holat paytida qisqa photo event recording
_photo_event_recording = False
_photo_event_end_at = None
_photo_event_frames = []
_photo_event_best_frame = None
_photo_event_best_person_box = None
_photo_event_best_confidence = 0.0
_photo_event_best_reasons = []
_photo_event_best_event_type = "normal"

camera_status = {
    "camera_open": False,
    "model_loaded": False,
    "person_detected": False,
    "stationary_seconds": 0.0,
    "photo_pose_detected": False,
    "crouch_detected": False,
    "lower_zone_motion": 0.0,
    "object_action_detected": False,
    "photo_event_recording": False,
    "risk_reasons": [],
    "event_type": "normal",
    "last_alert_at": None,
    "last_error": None,
}


# =========================
# BASIC HELPERS
# =========================

def get_camera_status():
    return camera_status


def load_model():
    global _model

    if _model is not None:
        return _model

    if YOLO is None:
        camera_status["last_error"] = "Ultralytics YOLO import bo'lmadi"
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


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def file_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def box_center(box: Tuple[int, int, int, int, float]) -> Tuple[int, int]:
    x1, y1, x2, y2, _ = box
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def box_area(box: Tuple[int, int, int, int, float]) -> int:
    x1, y1, x2, y2, _ = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def is_valid_person_box(frame, box) -> bool:
    h, w = frame.shape[:2]
    x1, y1, x2, y2, confidence = box

    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    area_ratio = (box_w * box_h) / max(1, w * h)
    shape_ratio = box_h / box_w

    if confidence < PERSON_MIN_CONFIDENCE:
        return False

    if box_h < PERSON_MIN_HEIGHT:
        return False

    if area_ratio < PERSON_MIN_AREA_RATIO or area_ratio > PERSON_MAX_AREA_RATIO:
        return False

    # Juda yotiq box ko‘pincha divan/yostiq/ko‘rpa bo‘lib ketadi
    if shape_ratio < 0.85:
        return False

    touches_left_edge = x1 <= 4
    touches_top_edge = y1 <= 4

    if (touches_left_edge or touches_top_edge) and confidence < 0.70:
        return False

    return True


def box_intersects(box_a, box_b) -> bool:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    return not (
        ax2 < bx1
        or ax1 > bx2
        or ay2 < by1
        or ay1 > by2
    )


def crop_with_padding(frame, box, padding_ratio=0.18):
    h, w = frame.shape[:2]
    x1, y1, x2, y2, _ = box

    bw = x2 - x1
    bh = y2 - y1

    px = int(bw * padding_ratio)
    py = int(bh * padding_ratio)

    x1 = clamp(x1 - px, 0, w - 1)
    y1 = clamp(y1 - py, 0, h - 1)
    x2 = clamp(x2 + px, 0, w - 1)
    y2 = clamp(y2 + py, 0, h - 1)

    if x2 <= x1 or y2 <= y1:
        return None

    return frame[y1:y2, x1:x2].copy()


def crop_face_from_person(frame, person_box):
    h, w = frame.shape[:2]
    x1, y1, x2, y2, _ = person_box

    person_h = y2 - y1
    person_w = x2 - x1

    fx1 = clamp(x1 + int(person_w * 0.10), 0, w - 1)
    fx2 = clamp(x2 - int(person_w * 0.10), 0, w - 1)
    fy1 = clamp(y1, 0, h - 1)
    fy2 = clamp(y1 + int(person_h * 0.46), 0, h - 1)

    if fx2 <= fx1 or fy2 <= fy1:
        return None

    return frame[fy1:fy2, fx1:fx2].copy()


def draw_text(frame, text, x, y, color=(230, 230, 230), scale=0.55, thickness=1):
    cv2.putText(
        frame,
        str(text),
        (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_label(frame, x, y, text, bg=(15, 23, 42), fg=(255, 255, 255)):
    text = str(text)
    label_w = max(120, len(text) * 8 + 16)
    label_h = 26

    x = clamp(int(x), 0, frame.shape[1] - 1)
    y = clamp(int(y), 0, frame.shape[0] - 1)

    cv2.rectangle(
        frame,
        (x, y),
        (
            min(x + label_w, frame.shape[1] - 1),
            min(y + label_h, frame.shape[0] - 1),
        ),
        bg,
        -1,
    )

    draw_text(frame, text, x + 8, y + 18, fg, 0.48, 1)


def smart_zoom_display(frame, person_box):
    if not SMART_ZOOM_ENABLED or person_box is None:
        return frame

    h, w = frame.shape[:2]
    x1, y1, x2, y2, _ = person_box

    person_w = x2 - x1
    person_h = y2 - y1

    pad_x = int(person_w * SMART_ZOOM_PADDING)
    pad_y = int(person_h * SMART_ZOOM_PADDING)

    zx1 = clamp(x1 - pad_x, 0, w - 1)
    zy1 = clamp(y1 - pad_y, 0, h - 1)
    zx2 = clamp(x2 + pad_x, 0, w - 1)
    zy2 = clamp(y2 + pad_y, 0, h - 1)

    if zx2 <= zx1 or zy2 <= zy1:
        return frame

    crop = frame[zy1:zy2, zx1:zx2].copy()
    zoomed = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)

    draw_label(
        zoomed,
        16,
        76,
        "DIGITAL ZOOM ACTIVE",
        (255, 180, 0),
        (0, 0, 0),
    )

    return zoomed


def open_camera():
    if CAMERA_SOURCE:
        if CAMERA_SOURCE.lower().startswith("rtsp://"):
            return cv2.VideoCapture(CAMERA_SOURCE, cv2.CAP_FFMPEG)

        return cv2.VideoCapture(CAMERA_SOURCE)

    if sys.platform == "win32":
        return cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

    if sys.platform == "darwin":
        avfoundation = getattr(cv2, "CAP_AVFOUNDATION", 1200)
        return cv2.VideoCapture(CAMERA_INDEX, avfoundation)

    return cv2.VideoCapture(CAMERA_INDEX)


# =========================
# YOLO DETECTION
# =========================

def find_detections(frame) -> Dict[str, Any]:
    global _last_person_box

    model = load_model()

    if model is None:
        return {
            "person": None,
            "phones": [],
            "objects": [],
        }

    try:
        result = model.predict(
            frame,
            imgsz=YOLO_IMGSZ,
            conf=YOLO_CONFIDENCE,
            iou=0.45,
            verbose=False,
        )[0]
    except Exception as error:
        camera_status["last_error"] = f"YOLO detection xatosi: {error}"
        return {
            "person": None,
            "phones": [],
            "objects": [],
        }

    biggest_person = None
    biggest_area = 0
    phones = []
    objects = []

    if result.boxes is None:
        return {
            "person": None,
            "phones": [],
            "objects": [],
        }

    for box in result.boxes:
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

        detected_box = (x1, y1, x2, y2, confidence)

        if cls_id == PERSON_CLASS_ID:
            if not is_valid_person_box(frame, detected_box):
                continue

            area = box_area(detected_box)
            if area > biggest_area:
                biggest_area = area
                biggest_person = detected_box

        if cls_id == CELL_PHONE_CLASS_ID:
            phones.append(detected_box)

        if cls_id in SUSPICIOUS_OBJECT_CLASS_IDS:
            objects.append(
                {
                    "class_id": cls_id,
                    "box": detected_box,
                    "confidence": confidence,
                }
            )

    _last_person_box = biggest_person

    return {
        "person": biggest_person,
        "phones": phones,
        "objects": objects,
    }


# =========================
# BEHAVIOR ENGINE
# =========================

def phone_in_photo_pose(person_box, phones) -> bool:
    if person_box is None or not phones:
        return False

    x1, y1, x2, y2, _ = person_box

    pw = max(1, x2 - x1)
    ph = max(1, y2 - y1)

    for phone in phones:
        px1, py1, px2, py2, _ = phone

        pcx = (px1 + px2) / 2
        pcy = (py1 + py2) / 2

        nx = (pcx - x1) / pw
        ny = (pcy - y1) / ph

        inside_person = 0.0 <= nx <= 1.0 and 0.0 <= ny <= 0.78
        front_photo_zone = 0.18 <= nx <= 0.82 and 0.10 <= ny <= 0.68

        # Telefon quloq atrofida bo‘lsa, call bo‘lishi mumkin.
        ear_zone = (nx < 0.18 or nx > 0.82) and 0.10 <= ny <= 0.48

        if inside_person and front_photo_zone and not ear_zone:
            return True

    return False


def crouch_or_bending_pose(person_box) -> bool:
    global _baseline_person_height

    if person_box is None:
        return False

    x1, y1, x2, y2, _ = person_box

    height = max(1, y2 - y1)
    width = max(1, x2 - x1)

    if _baseline_person_height is None:
        _baseline_person_height = float(height)

    if height > _baseline_person_height:
        _baseline_person_height = 0.80 * _baseline_person_height + 0.20 * height

    height_ratio = height / max(1.0, _baseline_person_height)
    shape_ratio = height / width

    is_height_drop = height_ratio < 0.88
    is_wide_body = shape_ratio < 1.55

    return bool(is_height_drop or is_wide_body)


def get_lower_zone(frame, person_box):
    h, w = frame.shape[:2]
    x1, y1, x2, y2, _ = person_box

    person_h = y2 - y1
    person_w = x2 - x1

    rx1 = clamp(x1 - int(person_w * 0.30), 0, w - 1)
    rx2 = clamp(x2 + int(person_w * 0.30), 0, w - 1)
    ry1 = clamp(y1 + int(person_h * 0.50), 0, h - 1)
    ry2 = clamp(y2 + int(person_h * 0.18), 0, h - 1)

    if rx2 <= rx1 or ry2 <= ry1:
        return None

    return rx1, ry1, rx2, ry2


def suspicious_object_near_lower_zone(frame, person_box, objects) -> bool:
    if person_box is None:
        return False

    lower_zone = get_lower_zone(frame, person_box)

    if lower_zone is None:
        return False

    for item in objects:
        x1, y1, x2, y2, _ = item["box"]
        if box_intersects(lower_zone, (x1, y1, x2, y2)):
            return True

    return False


def lower_zone_motion_score(frame, person_box) -> float:
    global _previous_gray

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if _previous_gray is None or _previous_gray.shape != gray.shape:
        _previous_gray = gray.copy()
        return 0.0

    if person_box is None:
        _previous_gray = gray.copy()
        return 0.0

    lower_zone = get_lower_zone(frame, person_box)

    if lower_zone is None:
        _previous_gray = gray.copy()
        return 0.0

    rx1, ry1, rx2, ry2 = lower_zone

    current_roi = gray[ry1:ry2, rx1:rx2]
    prev_roi = _previous_gray[ry1:ry2, rx1:rx2]

    diff = cv2.absdiff(current_roi, prev_roi)
    diff = cv2.GaussianBlur(diff, (5, 5), 0)

    motion_score = float(np.mean(diff))

    _previous_gray = gray.copy()

    return motion_score


def update_timer(condition: bool, current_value: Optional[float]) -> Optional[float]:
    if condition:
        if current_value is None:
            return time.time()
        return current_value

    return None


def elapsed_since(value: Optional[float]) -> float:
    if value is None:
        return 0.0

    return time.time() - value


def analyze_behavior(frame, detections):
    global _last_center
    global _stationary_started_at
    global _photo_pose_started_at
    global _crouch_started_at
    global _object_action_started_at
    global _last_risk_reasons
    global _last_event_type
    global _last_ai_confidence

    person_box = detections["person"]
    phones = detections["phones"]
    objects = detections["objects"]

    if person_box is None:
        camera_status["person_detected"] = False
        camera_status["stationary_seconds"] = 0.0
        camera_status["photo_pose_detected"] = False
        camera_status["crouch_detected"] = False
        camera_status["object_action_detected"] = False
        camera_status["lower_zone_motion"] = 0.0
        camera_status["risk_reasons"] = []
        camera_status["event_type"] = "normal"

        _last_center = None
        _stationary_started_at = None
        _photo_pose_started_at = None
        _crouch_started_at = None
        _object_action_started_at = None
        _last_risk_reasons = []
        _last_event_type = "normal"
        _last_ai_confidence = 0.0

        return False, 0.0, [], "normal"

    _, _, _, _, yolo_confidence = person_box
    center = box_center(person_box)

    camera_status["person_detected"] = True

    if _last_center is None:
        _last_center = center
        _stationary_started_at = time.time()

    move_distance = distance(center, _last_center)

    if move_distance > MOVE_RESET_DISTANCE:
        _last_center = center
        _stationary_started_at = time.time()
        _photo_pose_started_at = None
        _crouch_started_at = None
        _object_action_started_at = None

    if _stationary_started_at is None:
        _stationary_started_at = time.time()

    stationary_seconds = time.time() - _stationary_started_at
    camera_status["stationary_seconds"] = round(stationary_seconds, 1)

    raw_photo_pose = phone_in_photo_pose(person_box, phones)
    raw_crouch = crouch_or_bending_pose(person_box)
    lower_motion = lower_zone_motion_score(frame, person_box)
    object_near_lower = suspicious_object_near_lower_zone(frame, person_box, objects)

   
    raw_object_action = (
        object_near_lower
        or (
            lower_motion >= LOWER_MOTION_THRESHOLD
            and (
                raw_crouch
                or raw_photo_pose
                or stationary_seconds >= 2.0
            )
        )
    )

    _photo_pose_started_at = update_timer(raw_photo_pose, _photo_pose_started_at)
    _crouch_started_at = update_timer(raw_crouch, _crouch_started_at)
    _object_action_started_at = update_timer(raw_object_action, _object_action_started_at)

    photo_pose_seconds = elapsed_since(_photo_pose_started_at)
    crouch_seconds = elapsed_since(_crouch_started_at)
    object_action_seconds = elapsed_since(_object_action_started_at)

    photo_pose_detected = raw_photo_pose or photo_pose_seconds >= PHOTO_POSE_SECONDS_TO_ALERT
    crouch_detected = raw_crouch or crouch_seconds >= CROUCH_SECONDS_TO_ALERT
    object_action_detected = raw_object_action and object_action_seconds >= 0.35

    reasons = []

    if photo_pose_detected:
        reasons.append(
            "Telefon rasm olish pozasida aniqlandi: shaxs obyekt yoki hududni suratga olayotgan bo‘lishi mumkin"
        )

    if crouch_detected:
        reasons.append(
            "Shaxs egildi yoki bukildi: pastki zona bilan shubhali harakat kuzatildi"
        )

    if object_action_detected:
        reasons.append(
            "Yer/stol/devor atrofida mayda harakat aniqlandi: obyekt qo‘yish yoki olish ehtimoli bor"
        )

    if lower_motion >= LOWER_MOTION_THRESHOLD and (crouch_detected or photo_pose_detected):
        reasons.append("Pastki zonada tezkor harakat qayd etildi")

    if object_near_lower:
        reasons.append("Pastki zona atrofida kichik obyekt aniqlandi")

    if stationary_seconds >= 2.0 and not reasons:
        reasons.append(f"Shaxs {stationary_seconds:.1f} soniya davomida hududda qoldi")

    score = 45.0
    score += yolo_confidence * 12.0
    score += min(8.0, stationary_seconds * 1.5)

    if photo_pose_detected:
        score += 28.0

    if crouch_detected:
        score += 28.0

    if object_action_detected:
        score += 30.0

    if lower_motion >= LOWER_MOTION_THRESHOLD:
        score += 12.0

    if object_near_lower:
        score += 10.0

    ai_confidence = min(98.0, score)

    event_type = "normal"

    if photo_pose_detected and (crouch_detected or object_action_detected):
        event_type = "photo_during_possible_drop"
    elif crouch_detected and object_action_detected:
        event_type = "possible_hidden_drop"
    elif photo_pose_detected:
        event_type = "photo_pose_detected"
    elif crouch_detected:
        event_type = "crouch_or_bending_detected"
    elif object_action_detected:
        event_type = "lower_zone_object_action"
    elif stationary_seconds >= STATIONARY_SECONDS_TO_ALERT:
        event_type = "loitering_stationary"

    # Oddiy yurib o‘tishni alert qilmaslik uchun movement filter
    is_walking = (
        move_distance > 18
     and not raw_crouch
        and not raw_photo_pose
     and not object_near_lower
    )

    if is_walking:
     is_suspicious = False
    else:
     is_suspicious = (
          stationary_seconds >= STATIONARY_SECONDS_TO_ALERT
         or (photo_pose_detected and stationary_seconds >= 1.5)
         or (crouch_detected and object_action_detected)
         or (photo_pose_detected and crouch_detected)
         or (photo_pose_detected and object_action_detected)
        )
    camera_status["photo_pose_detected"] = photo_pose_detected
    camera_status["crouch_detected"] = crouch_detected
    camera_status["object_action_detected"] = object_action_detected
    camera_status["lower_zone_motion"] = round(lower_motion, 2)
    camera_status["risk_reasons"] = reasons
    camera_status["event_type"] = event_type

    _last_risk_reasons = reasons
    _last_event_type = event_type
    _last_ai_confidence = ai_confidence

    return is_suspicious, ai_confidence, reasons, event_type


# =========================
# EVIDENCE
# =========================
def annotate_frame_for_evidence(frame, confidence, reasons, event_type):
    image = frame.copy()

    try:
        detections = find_detections(image)
        image = draw_detections(
            image,
            detections,
            True,
            confidence,
            reasons or [],
            event_type,
        )
    except Exception as error:
        camera_status["last_error"] = f"Evidence annotation xatosi: {error}"

    return image

def build_evidence_frame(frame, person_box, reasons, confidence, event_type):
    evidence = annotate_frame_for_evidence(
        frame,
        confidence,
        reasons,
        event_type,
    )

    h, w = evidence.shape[:2]

    if person_box is not None:
        x1, y1, x2, y2, _ = person_box

        cv2.rectangle(evidence, (x1, y1), (x2, y2), (0, 190, 255), 3)
        draw_label(
            evidence,
            x1,
            max(0, y1 - 30),
            f"PERSON | REVIEW REQUIRED | {confidence:.1f}%",
            (0, 190, 255),
            (0, 0, 0),
        )

    panel_x = 16
    panel_y = 16
    panel_w = min(680, w - 32)
    panel_h = 152

    overlay = evidence.copy()
    cv2.rectangle(
        overlay,
        (panel_x, panel_y),
        (panel_x + panel_w, panel_y + panel_h),
        (8, 12, 18),
        -1,
    )

    evidence = cv2.addWeighted(overlay, 0.72, evidence, 0.28, 0)
    cv2.rectangle(
        evidence,
        (panel_x, panel_y),
        (panel_x + panel_w, panel_y + panel_h),
        (0, 190, 255),
        1,
    )

    draw_text(evidence, "MayizQani AI Evidence", panel_x + 16, panel_y + 30, (255, 255, 255), 0.68, 2)
    draw_text(evidence, f"Time: {now_label()}", panel_x + 16, panel_y + 58, (210, 220, 230), 0.48, 1)
    draw_text(evidence, f"Event: {event_type}", panel_x + 16, panel_y + 82, (210, 220, 230), 0.48, 1)
    draw_text(evidence, f"Confidence: {confidence:.1f}%", panel_x + 16, panel_y + 108, (0, 220, 255), 0.55, 2)

    reason_y = panel_y + 134
    if reasons:
        draw_text(evidence, f"Reason: {reasons[0][:82]}", panel_x + 16, reason_y, (255, 255, 255), 0.43, 1)
    else:
        draw_text(evidence, "Reason: operator review required", panel_x + 16, reason_y, (255, 255, 255), 0.43, 1)

    return evidence


def get_recent_buffer_frames(seconds: float):
    now = time.time()

    return [
        frame.copy()
        for ts, frame in list(_frame_buffer)
        if now - ts <= seconds
    ]


def pick_burst_frames(frames: List[np.ndarray], count: int) -> List[np.ndarray]:
    if not frames:
        return []

    if len(frames) <= count:
        return [frame.copy() for frame in frames]

    indexes = np.linspace(0, len(frames) - 1, count).astype(int)
    return [frames[index].copy() for index in indexes]


def build_gallery_frame(frame, index, total, event_type, confidence, reasons):
    image = annotate_frame_for_evidence(
        frame,
        confidence,
        reasons,
        event_type,
    )

    h, w = image.shape[:2]

    panel_x = 14
    panel_y = 14
    panel_w = min(640, w - 28)
    panel_h = 112

    overlay = image.copy()

    cv2.rectangle(
        overlay,
        (panel_x, panel_y),
        (panel_x + panel_w, panel_y + panel_h),
        (8, 12, 18),
        -1,
    )

    image = cv2.addWeighted(overlay, 0.68, image, 0.32, 0)

    cv2.rectangle(
        image,
        (panel_x, panel_y),
        (panel_x + panel_w, panel_y + panel_h),
        (0, 190, 255),
        1,
    )

    draw_text(
        image,
        f"MayizQani AI Evidence Frame {index}/{total}",
        panel_x + 14,
        panel_y + 30,
        (255, 255, 255),
        0.58,
        2,
    )

    draw_text(
        image,
        f"Event: {event_type} | Confidence: {confidence:.1f}%",
        panel_x + 14,
        panel_y + 58,
        (210, 220, 230),
        0.46,
        1,
    )

    reason_text = reasons[0] if reasons else "Operator review required"

    draw_text(
        image,
        f"Reason: {reason_text[:88]}",
        panel_x + 14,
        panel_y + 86,
        (255, 255, 255),
        0.42,
        1,
    )

    return image


def save_evidence_gallery(frames, event_type, confidence, reasons):
    gallery_paths = []
    gallery_urls = []

    selected_frames = pick_burst_frames(frames, EVIDENCE_BURST_COUNT)

    timestamp = file_stamp()
    uid = uuid.uuid4().hex[:8]
    total = len(selected_frames)

    for index, frame in enumerate(selected_frames, start=1):
        gallery_frame = build_gallery_frame(
            frame,
            index,
            total,
            event_type,
            confidence,
            reasons,
        )

        filename = f"burst_{timestamp}_{uid}_{index}.jpg"
        path = EVIDENCE_DIR / filename

        cv2.imwrite(str(path), gallery_frame)

        gallery_paths.append(str(path))
        gallery_urls.append(f"/evidence/{filename}")

    return gallery_paths, gallery_urls


def save_evidence_package(frame, person_box, reasons, confidence, event_type):
    timestamp = file_stamp()
    uid = uuid.uuid4().hex[:8]

    evidence_frame = build_evidence_frame(
        frame,
        person_box,
        reasons,
        confidence,
        event_type,
    )

    evidence_filename = f"evidence_{timestamp}_{uid}.jpg"
    evidence_path = EVIDENCE_DIR / evidence_filename
    cv2.imwrite(str(evidence_path), evidence_frame)

    zoom_image_path = None
    zoom_image_url = None
    face_image_path = None
    face_image_url = None

    if person_box is not None:
        zoom_crop = crop_with_padding(frame, person_box, 0.32)
        face_crop = crop_face_from_person(frame, person_box)

        if zoom_crop is not None:
            zoom_filename = f"zoom_{timestamp}_{uid}.jpg"
            zoom_full_path = EVIDENCE_ZOOM_DIR / zoom_filename
            cv2.imwrite(str(zoom_full_path), zoom_crop)

            zoom_image_path = str(zoom_full_path)
            zoom_image_url = f"/evidence/zoom/{zoom_filename}"

        if face_crop is not None:
            face_filename = f"face_{timestamp}_{uid}.jpg"
            face_full_path = EVIDENCE_FACES_DIR / face_filename
            cv2.imwrite(str(face_full_path), face_crop)

            face_image_path = str(face_full_path)
            face_image_url = f"/evidence/faces/{face_filename}"

    return (
        str(evidence_path),
        f"/evidence/{evidence_filename}",
        zoom_image_path,
        zoom_image_url,
        face_image_path,
        face_image_url,
    )


def send_photo_event_alert_async(
    confidence: float,
    frame=None,
    person_box=None,
    reasons=None,
    event_type="normal",
    gallery_paths=None,
    gallery_urls=None,
):
    evidence_image_path = None
    evidence_image_url = None
    zoom_image_path = None
    zoom_image_url = None
    face_image_path = None
    face_image_url = None

    if frame is not None:
        (
            evidence_image_path,
            evidence_image_url,
            zoom_image_path,
            zoom_image_url,
            face_image_path,
            face_image_url,
        ) = save_evidence_package(
            frame,
            person_box,
            reasons or [],
            confidence,
            event_type,
        )

    reason_text = "\n".join([f"• {reason}" for reason in (reasons or [])])

    if not reason_text:
        reason_text = "• Operator tekshiruvi talab qilinadigan holat qayd etildi"

    payload = {
        "camera_name": CAMERA_NAME,
        "latitude": CAMERA_LAT,
        "longitude": CAMERA_LON,
        "person_id": "P-CAM-001",
        "face_match_name": "Demo Foydalanuvchi 01",
        "face_match_score": 78.4,
        "confidence": round(confidence, 1),
        "event_type": event_type,
        "risk_reasons": reasons or [],
        "action": (
            f"AI kamera shubhali harakat patternini aniqladi.\n\n"
            f"Event turi: {event_type}\n"
            f"Aniqlangan belgilar:\n{reason_text}\n\n"
            f"Evidence paket saqlandi: asosiy kadr, zoom crop, yuz crop va bir nechta photo gallery."
        ),
        "status": "operator_tekshiruvi_talab_qilinadi",
        "evidence_image_path": evidence_image_path,
        "evidence_image_url": evidence_image_url,
        "zoom_image_path": zoom_image_path,
        "zoom_image_url": zoom_image_url,
        "face_image_path": face_image_path,
        "face_image_url": face_image_url,
        "evidence_gallery_paths": gallery_paths or [],
        "evidence_gallery_urls": gallery_urls or [],
    }

    def worker():
        try:
            requests.post(ALERT_ENDPOINT, json=payload, timeout=5)
        except Exception as error:
            camera_status["last_error"] = f"Alert yuborishda xato: {error}"

    threading.Thread(target=worker, daemon=True).start()


def start_photo_event(frame, person_box, confidence, reasons, event_type):
    global _photo_event_recording
    global _photo_event_end_at
    global _photo_event_frames
    global _photo_event_best_frame
    global _photo_event_best_person_box
    global _photo_event_best_confidence
    global _photo_event_best_reasons
    global _photo_event_best_event_type
    global _last_alert_at

    now = time.time()

    if _photo_event_recording:
        return

    if now - _last_alert_at < ALERT_COOLDOWN_SECONDS:
        return

    _photo_event_recording = True
    _photo_event_end_at = now + PHOTO_EVENT_CAPTURE_SECONDS

    # Triggerdan oldingi frame'lar + keyingi 2.5 sekund frame'lar yig‘iladi
    _photo_event_frames = get_recent_buffer_frames(PHOTO_EVENT_PRE_SECONDS)

    _photo_event_best_frame = frame.copy()
    _photo_event_best_person_box = person_box
    _photo_event_best_confidence = confidence
    _photo_event_best_reasons = reasons or []
    _photo_event_best_event_type = event_type

    _last_alert_at = now
    camera_status["last_alert_at"] = now_label()
    camera_status["photo_event_recording"] = True


def update_photo_event(frame, person_box, confidence, reasons, event_type):
    global _photo_event_recording
    global _photo_event_end_at
    global _photo_event_frames
    global _photo_event_best_frame
    global _photo_event_best_person_box
    global _photo_event_best_confidence
    global _photo_event_best_reasons
    global _photo_event_best_event_type

    if not _photo_event_recording:
        return

    _photo_event_frames.append(frame.copy())

    if confidence >= _photo_event_best_confidence:
        _photo_event_best_frame = frame.copy()
        _photo_event_best_person_box = person_box
        _photo_event_best_confidence = confidence
        _photo_event_best_reasons = reasons or []
        _photo_event_best_event_type = event_type

    if time.time() >= _photo_event_end_at:
        finish_photo_event()


def finish_photo_event():
    global _photo_event_recording
    global _photo_event_end_at
    global _photo_event_frames
    global _photo_event_best_frame
    global _photo_event_best_person_box
    global _photo_event_best_confidence
    global _photo_event_best_reasons
    global _photo_event_best_event_type

    if not _photo_event_recording:
        return

    frames = [frame.copy() for frame in _photo_event_frames]

    if not frames:
        _photo_event_recording = False
        camera_status["photo_event_recording"] = False
        return

    best_frame = _photo_event_best_frame.copy() if _photo_event_best_frame is not None else frames[-1]
    best_person_box = _photo_event_best_person_box
    confidence = _photo_event_best_confidence
    reasons = _photo_event_best_reasons
    event_type = _photo_event_best_event_type

    gallery_paths, gallery_urls = save_evidence_gallery(
        frames,
        event_type,
        confidence,
        reasons,
    )

    send_photo_event_alert_async(
        confidence=confidence,
        frame=best_frame,
        person_box=best_person_box,
        reasons=reasons,
        event_type=event_type,
        gallery_paths=gallery_paths,
        gallery_urls=gallery_urls,
    )

    _photo_event_recording = False
    _photo_event_end_at = None
    _photo_event_frames = []
    _photo_event_best_frame = None
    _photo_event_best_person_box = None
    _photo_event_best_confidence = 0.0
    _photo_event_best_reasons = []
    _photo_event_best_event_type = "normal"

    camera_status["photo_event_recording"] = False


# =========================
# CAMERA UI
# =========================

def draw_detections(frame, detections, is_suspicious, ai_confidence, reasons, event_type):
    person_box = detections["person"]
    phones = detections["phones"]
    objects = detections["objects"]

    if person_box is not None:
        x1, y1, x2, y2, confidence = person_box

        if is_suspicious:
            box_color = (0, 190, 255)
            label = f"PERSON | REVIEW | {ai_confidence:.1f}%"
        else:
            box_color = (60, 220, 120)
            label = f"PERSON | TRACKING | {confidence * 100:.1f}%"

        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)
        draw_label(frame, x1, max(0, y1 - 30), label, box_color, (0, 0, 0))

    for phone_box in phones:
        px1, py1, px2, py2, pconf = phone_box

        phone_color = (255, 120, 0)
        cv2.rectangle(frame, (px1, py1), (px2, py2), phone_color, 3)
        draw_label(
            frame,
            px1,
            max(0, py1 - 28),
            f"PHONE | {pconf * 100:.0f}%",
            phone_color,
            (0, 0, 0),
        )

    for item in objects:
        if item["class_id"] == CELL_PHONE_CLASS_ID:
            continue

        x1, y1, x2, y2, confidence = item["box"]
        obj_color = (180, 120, 255)

        cv2.rectangle(frame, (x1, y1), (x2, y2), obj_color, 2)
        draw_label(
            frame,
            x1,
            max(0, y1 - 26),
            f"OBJECT | {confidence * 100:.0f}%",
            obj_color,
            (0, 0, 0),
        )

    return frame


def draw_camera_ui(frame, detections, is_suspicious, ai_confidence, reasons, event_type):
    h, w = frame.shape[:2]
    person_box = detections["person"]

    display = frame.copy()
    display = draw_detections(
        display,
        detections,
        is_suspicious,
        ai_confidence,
        reasons,
        event_type,
    )

    if person_box is not None and SMART_ZOOM_ON_PERSON:
        display = smart_zoom_display(display, person_box)

    cv2.rectangle(display, (0, 0), (w, 54), (8, 12, 18), -1)
    draw_text(display, "MayizQani AI  |  Behavior Monitoring Stream", 16, 34, (235, 241, 245), 0.62, 2)
    draw_text(display, now_label(), max(16, w - 220), 34, (150, 160, 170), 0.5, 1)

    panel_x = 14
    panel_y = h - 142
    panel_w = 680
    panel_h = 124

    cv2.rectangle(display, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (8, 12, 18), -1)
    cv2.rectangle(display, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (38, 49, 64), 1)

    detected_text = "PERSON: YES" if person_box else "PERSON: NO"
    phone_text = f"PHONE: {len(detections['phones'])}"
    object_text = f"OBJECTS: {len(detections['objects'])}"
    stationary = camera_status["stationary_seconds"]
    lower_motion = camera_status["lower_zone_motion"]
    photo_event = "YES" if camera_status["photo_event_recording"] else "NO"

    draw_text(display, detected_text, panel_x + 16, panel_y + 28, (210, 220, 230), 0.52, 1)
    draw_text(display, phone_text, panel_x + 180, panel_y + 28, (210, 220, 230), 0.52, 1)
    draw_text(display, object_text, panel_x + 310, panel_y + 28, (210, 220, 230), 0.52, 1)
    draw_text(display, f"PHOTO EVENT: {photo_event}", panel_x + 470, panel_y + 28, (210, 220, 230), 0.52, 1)

    draw_text(display, f"STATIONARY: {stationary}s", panel_x + 16, panel_y + 54, (210, 220, 230), 0.52, 1)
    draw_text(display, f"LOWER MOTION: {lower_motion}", panel_x + 240, panel_y + 54, (210, 220, 230), 0.52, 1)

    draw_text(display, f"EVENT: {event_type}", panel_x + 16, panel_y + 82, (210, 220, 230), 0.52, 1)

    if is_suspicious:
        draw_text(display, f"RISK: CAPTURING PHOTO EVIDENCE  {ai_confidence:.1f}%", panel_x + 16, panel_y + 110, (0, 220, 255), 0.54, 2)
    elif camera_status["photo_event_recording"]:
        draw_text(display, "RISK: PHOTO EVENT RECORDING", panel_x + 16, panel_y + 110, (0, 220, 255), 0.54, 2)
    else:
        draw_text(display, "RISK: NORMAL", panel_x + 16, panel_y + 110, (120, 220, 160), 0.54, 2)

    if reasons:
        rx = 14
        ry = 62
        reason_panel_h = 34 + len(reasons[:3]) * 24

        cv2.rectangle(display, (rx, ry), (rx + 700, ry + reason_panel_h), (8, 12, 18), -1)
        cv2.rectangle(display, (rx, ry), (rx + 700, ry + reason_panel_h), (0, 190, 255), 1)

        draw_text(display, "Behavior signals", rx + 14, ry + 24, (255, 255, 255), 0.52, 2)

        line_y = ry + 50
        for reason in reasons[:3]:
            draw_text(display, f"- {reason[:78]}", rx + 14, line_y, (210, 220, 230), 0.43, 1)
            line_y += 23

    return display


# =========================
# ERROR / STREAM HELPERS
# =========================

def error_frame(message: str):
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame[:] = (8, 12, 18)

    draw_text(frame, "MayizQani AI", 40, 60, (230, 230, 230), 1.0, 2)
    draw_text(frame, message, 40, 110, (120, 130, 145), 0.75, 1)
    draw_text(frame, "Kamera indexini .env ichida CAMERA_INDEX=0 yoki 1 qilib tekshiring.", 40, 150, (120, 130, 145), 0.65, 1)

    return frame


def encode_jpeg(frame):
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 84])

    if not ok:
        return None

    return buffer.tobytes()


def analyze_frame_bytes(jpeg_bytes: bytes):
    arr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return None

    detections = find_detections(frame)
    is_suspicious, ai_confidence, reasons, event_type = analyze_behavior(frame, detections)
    frame = draw_camera_ui(frame, detections, is_suspicious, ai_confidence, reasons, event_type)

    if is_suspicious:
        person_box = detections.get("person")
        start_photo_event(frame.copy(), person_box, ai_confidence, reasons, event_type)

    return encode_jpeg(frame)


def mjpeg_frame(jpeg_bytes):
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
    )


# =========================
# MAIN STREAM
# =========================

def generate_camera_frames():
    global _frame_buffer

    frame_count = 0

    last_detections = {
        "person": None,
        "phones": [],
        "objects": [],
    }

    cap = open_camera()

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
    cap.set(cv2.CAP_PROP_FPS, 30)

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

            _frame_buffer.append((time.time(), frame.copy()))

            frame_count += 1

            if frame_count % PROCESS_EVERY_N_FRAMES == 0:
                last_detections = find_detections(frame)

            is_suspicious, ai_confidence, reasons, event_type = analyze_behavior(
                frame,
                last_detections,
            )

            display_frame = draw_camera_ui(
                frame.copy(),
                last_detections,
                is_suspicious,
                ai_confidence,
                reasons,
                event_type,
            )

            if is_suspicious:
                start_photo_event(
                    frame=frame.copy(),
                    person_box=last_detections["person"],
                    confidence=ai_confidence,
                    reasons=reasons,
                    event_type=event_type,
                )

            update_photo_event(
                frame=frame.copy(),
                person_box=last_detections["person"],
                confidence=ai_confidence,
                reasons=reasons,
                event_type=event_type,
            )

            jpeg = encode_jpeg(display_frame)

            if jpeg:
                yield mjpeg_frame(jpeg)

            time.sleep(0.02)

    finally:
        cap.release()
        camera_status["camera_open"] = False